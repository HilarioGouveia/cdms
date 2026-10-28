"""Configuração de tarefas assíncronas Celery + Redis para automação contínua de ingestão."""

import os
from celery import Celery

REDIS_URL = os.getenv("CDMS_REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "cdms_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_track_started=True,
)


@celery_app.task(name="tasks.sync_platform_metrics")
def task_sync_platform_metrics(workspace_id: str, platform: str, account_id: str, cycle_id: str):
    """Tarefa assíncrona que executa o polling automatizado e alimenta o snapshot semanal."""
    from cdms.adapters.connectors.mock_connectors import MockMetaAdsConnector, MockYouTubeStudioConnector

    if platform == "META_ADS":
        connector = MockMetaAdsConnector()
    else:
        connector = MockYouTubeStudioConnector()

    data = connector.fetch_weekly_metrics(account_id=account_id, cycle_id=cycle_id)
    return {
        "status": "SUCCESS",
        "workspace_id": workspace_id,
        "platform": platform,
        "metrics": data,
    }