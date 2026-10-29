"""Worker e agendador Celery: IDs na fila; credenciais somente no banco cifrado."""
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from celery import Celery
from celery.schedules import crontab

from cdms.adapters.tasks.ingestion_runtime import process_job, dispatch_job, authorize
from cdms.adapters.persistence.sqlite_identity_repo import SQLiteIdentityRepository
from cdms.adapters.persistence.sqlite_ingestion_repo import SQLiteIngestionRepository
from cdms.config.workspace_storage import identity_db_path, workspace_data_dir, workspace_db_path

REDIS_URL = os.getenv("CDMS_REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("cdms_tasks", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.update(
    task_serializer="json", result_serializer="json", accept_content=["json"],
    timezone="America/Sao_Paulo", enable_utc=True, task_track_started=True,
    task_acks_late=True, task_reject_on_worker_lost=True, worker_prefetch_multiplier=1,
    task_publish_retry=False, broker_connection_timeout=2,
    broker_transport_options={"socket_connect_timeout": 2, "socket_timeout": 2},
    result_expires=3600,
    beat_schedule={
        "dispatch-pending-ingestions": {"task": "tasks.dispatch_pending", "schedule": 60.0},
        "schedule-weekly-ingestions": {"task": "tasks.schedule_weekly", "schedule": crontab(minute=5)},
    },
)


@celery_app.task(bind=True, name="tasks.sync_platform_metrics", max_retries=2)
def task_sync_platform_metrics(self, workspace_id, job_id):
    job = process_job(workspace_id, job_id)
    if job and job["status"] == 'PENDING':
        raise self.retry(countdown=min(60 * (2 ** job["attempts"]), 300))
    return {"workspace_id": workspace_id, "job_id": job_id, "status": job["status"] if job else "NOT_FOUND"}


def scan_workspaces():
    if not identity_db_path().is_file():
        return
    identity = SQLiteIdentityRepository(identity_db_path())
    for workspace_id in identity.workspace_ids():
        path = workspace_db_path(workspace_data_dir(), workspace_id)
        if path.is_file():
            yield identity, workspace_id, SQLiteIngestionRepository(path)


@celery_app.task(name="tasks.dispatch_pending")
def dispatch_pending():
    sent = 0
    for _, workspace_id, repo in scan_workspaces():
        for job_id in repo.dispatchable_jobs():
            try:
                dispatch_job(workspace_id, job_id)
                sent += 1
            except Exception:
                return {"dispatched": sent, "broker_available": False}
    return {"dispatched": sent, "broker_available": True}


@celery_app.task(name="tasks.schedule_weekly")
def schedule_weekly():
    created = 0
    for identity, workspace_id, repo in scan_workspaces():
        for connection in repo.list_connections():
            if not connection["is_active"] or not connection["automatic_sync"]:
                continue
            if not authorize(identity, workspace_id, connection["created_by"]):
                continue
            today = datetime.now(ZoneInfo(connection["timezone_name"])).date()
            cycle = today - timedelta(days=today.weekday() + 7)
            _, changed = repo.enqueue(connection["id"], cycle.isoformat(), connection["created_by"])
            created += int(changed)
    # O próximo tick da outbox envia os jobs, mesmo se o broker estiver indisponível agora.
    return {"created": created}
