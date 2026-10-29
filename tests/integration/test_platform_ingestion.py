"""API, banco, adaptador HTTP e worker de ingestão isolados por workspace."""
from datetime import datetime, timedelta, timezone, date
from functools import partial
from types import SimpleNamespace
from unittest.mock import Mock
import json
import os
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from test_workspace_api import api, password_hash, PREFIX, ritual
from cdms.adapters.connectors.meta_ads import MetaAdsConnector
from cdms.adapters.persistence.sqlite_ingestion_repo import SQLiteIngestionRepository
from cdms.adapters.tasks.ingestion_runtime import process_job
from cdms.config.credential_vault import CredentialVault
from cdms.config.workspace_storage import workspace_db_path

TOKEN = "test-ingestion-token-never-persist-in-clear"


@pytest.fixture
def ingestion(api):
    session = Mock()
    def response(url, **kwargs):
        body = ({"data": [{"account_id": "123", "account_currency": "BRL", "date_start": "2026-10-19",
                          "date_stop": "2026-10-25", "reach": "2000", "impressions": "3000",
                          "inline_link_clicks": "90", "spend": "50.00",
                          "actions": [{"action_type": "offsite_conversion.fb_pixel_purchase", "value": "4"}]}]}
                if url.endswith("/insights") else
                {"account_id": "123", "currency": "BRL", "timezone_name": "America/Sao_Paulo"})
        result = Mock(status_code=200)
        result.json.return_value = body
        return result
    session.get.side_effect = response
    factory = lambda connection, token: MetaAdsConnector(token, session=session,
        api_version=connection["api_version"], timezone_name=connection["timezone_name"] ,
        conversion_action_type=connection["conversion_action_type"])
    key = Fernet.generate_key()
    api.client.app.state.credential_key = key
    api.client.app.state.platform_connector_factory = factory
    dispatcher = Mock()
    api.client.app.state.ingestion_dispatcher = dispatcher
    headers = api.login()
    def connect(**changes):
        payload = {"platform": "META_ADS", "account_id": "act_123", "access_token": TOKEN}
        payload.update(changes)
        return api.client.post(PREFIX + "/automation/connect-platform", headers=headers, json=payload)
    def enqueue(connection_id, **changes):
        payload = {"cycle_id": "2026-10-19", **changes}
        return api.client.post(PREFIX + f"/automation/connections/{connection_id}/sync", json=payload, headers=headers)
    def run(job_id, **changes):
        return process_job(api.wa, job_id, identity=api.identity, root=api.root,
                           vault=changes.pop("vault", CredentialVault(key)), connector_factory=factory, **changes)
    return SimpleNamespace(api=api, headers=headers, connect=connect, enqueue=enqueue, run=run,
                           session=session, response=response, dispatcher=dispatcher, key=key, factory=factory,
                           repo=SQLiteIngestionRepository(workspace_db_path(api.root, api.wa)))


def test_connection_token_is_encrypted_and_never_serialized(ingestion):
    x = ingestion
    response = x.connect()
    assert response.status_code == 200, response.text
    connection_id = response.json()["id"]
    stored = x.repo.get_connection(connection_id)
    assert stored["encrypted_credentials"] != TOKEN
    assert CredentialVault(x.key).decrypt(stored["encrypted_credentials"]) == TOKEN
    assert TOKEN not in x.repo.path.read_bytes().decode("latin1")
    assert "encrypted_credentials" not in response.text and TOKEN not in response.text
    assert TOKEN not in x.api.client.get(PREFIX + "/automation/connections", headers=x.headers).text
    x.dispatcher.assert_not_called()


def test_complete_pipeline_prepares_metrics_without_closing_ritual(ingestion):
    x = ingestion
    connection_id = x.connect().json()["id"]
    queued = x.enqueue(connection_id)
    assert queued.status_code == 202, queued.text
    job_id = queued.json()["job"]["id"]
    assert queued.json()["dispatch_status"] == "ENQUEUED"
    assert x.enqueue(connection_id).json()["job"]["id"] == job_id
    x.dispatcher.assert_called_once_with(x.api.wa, job_id)
    assert x.run(job_id)["status"] == "SUCCESS"
    assert x.run(job_id)["attempts"] == 1
    assert x.session.get.call_count == 2  # Uma validação de conta e uma coleta; sem duplicação.
    assert x.api.client.get(PREFIX + "/rituals", headers=x.headers).json() == []
    draft = x.api.client.get(PREFIX + f"/automation/jobs/{job_id}/ritual-input", headers=x.headers)
    assert draft.status_code == 200
    retention = next(s for s in draft.json()["snapshots"] if s["key"] == "avg_retention_pct")
    assert retention == {"key": "avg_retention_pct", "observed_value": None,
                         "is_available": False, "unavailability_reason": "NOT_SUPPORTED"}
    payload = {**ritual(), **draft.json()}
    saved = x.api.client.post(PREFIX + "/rituals", json=payload, headers=x.headers)
    assert saved.status_code == 200, saved.text
    assert next(s for s in saved.json()["snapshots"] if s["definition"]["key"] == "reach")["observed_value"] == 2000
    with x.repo.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM ingestion_batches").fetchone()[0] == 1


def test_connection_jobs_and_results_cannot_cross_workspace(ingestion):
    x = ingestion
    cid = x.connect().json()["id"]
    jid = x.enqueue(cid).json()["job"]["id"]
    x.run(jid)
    other = x.api.login("bob")
    assert x.api.client.get(PREFIX + "/automation/connections", headers=other).json() == []
    for suffix in ("", "/result", "/ritual-input"):
        assert x.api.client.get(PREFIX + f"/automation/jobs/{jid}" + suffix, headers=other).status_code == 404
    assert x.api.client.post(PREFIX + f"/automation/connections/{cid}/sync", headers=other,
                            json={"cycle_id": "2026-10-19"}).status_code == 404
    assert x.api.client.delete(PREFIX + f"/automation/connections/{cid}", headers=other).status_code == 404
    assert process_job(x.api.wb, jid, identity=x.api.identity, root=x.api.root, vault=CredentialVault(x.key),
                       connector_factory=x.factory) is None


def test_only_managers_can_set_credentials_and_missing_key_fails_closed(ingestion, monkeypatch):
    x = ingestion
    payload = {"platform": "META_ADS", "account_id": "act_123", "access_token": TOKEN}
    for name in ("member", "viewer"):
        assert x.api.client.post(PREFIX + "/automation/connect-platform", json=payload, headers=x.api.login(name)).status_code == 403
    monkeypatch.delenv("CDMS_CREDENTIAL_KEY", raising=False)
    x.api.client.app.state.credential_key = None
    assert x.connect().status_code == 503
    x.session.get.assert_not_called()


def test_account_access_denied_is_sanitized_and_not_saved(ingestion):
    x = ingestion
    response = Mock(status_code=403)
    response.json.return_value = {"error": {"code": 190, "message": TOKEN}}
    x.session.get.side_effect = None
    x.session.get.return_value = response
    result = x.connect()
    assert result.status_code == 502
    assert TOKEN not in result.text
    assert x.repo.list_connections() == []


def test_open_week_and_non_monday_are_rejected(ingestion):
    x = ingestion
    cid = x.connect().json()["id"]
    future = date(2099,1,1)
    future -= timedelta(days=future.weekday())
    assert x.enqueue(cid, cycle_id=future.isoformat()).status_code == 400
    assert x.enqueue(cid, cycle_id="2026-10-20").status_code == 400
    assert x.repo.list_jobs() == []


def unavailable_response(status=429):
    response = Mock(status_code=status)
    response.json.return_value = {"error": {"code": 190 if status == 403 else 4, "message": TOKEN}}
    return response


def test_retryable_errors_are_bounded_and_keep_credentials_private(ingestion):
    x = ingestion
    cid = x.connect().json()["id"]
    jid = x.enqueue(cid).json()["job"]["id"]
    x.session.get.side_effect = None
    x.session.get.return_value = unavailable_response()
    assert x.run(jid)["status"] == "PENDING"
    assert x.run(jid)["status"] == "PENDING"
    assert x.run(jid)["status"] == "FAILED"
    assert x.run(jid)["attempts"] == 3
    assert x.repo.get_batch(jid) is None
    assert TOKEN not in json.dumps(x.repo.get_job(jid))
    x.session.get.side_effect = x.response
    assert x.enqueue(cid, retry_failed=True).json()["job"]["id"] == jid
    assert x.run(jid)["status"] == "SUCCESS"


def test_permanent_errors_are_not_automatically_retried(ingestion):
    x = ingestion
    cid = x.connect().json()["id"]
    jid = x.enqueue(cid).json()["job"]["id"]
    x.session.get.side_effect = None
    x.session.get.return_value = unavailable_response(403)
    assert x.run(jid)["status"] == "FAILED"
    assert x.run(jid)["attempts"] == 1
    assert x.session.get.call_count == 2


def test_revoked_requester_cannot_run_queued_job(ingestion):
    from cdms.domain.entities.tenant import UserRole
    x = ingestion
    cid = x.connect().json()["id"]
    response = x.api.client.post(PREFIX + f"/automation/connections/{cid}/sync", headers=x.api.login("member"),
                                 json={"cycle_id": "2026-10-19"})
    jid = response.json()["job"]["id"]
    x.api.identity.set_member(x.api.wa, x.api.users["member"]["id"], UserRole.VIEWER)
    assert x.run(jid)["error_code"] == "ACCESS_REVOKED"
    assert x.session.get.call_count == 1
    assert x.repo.get_batch(jid) is None


@pytest.mark.parametrize("change", ["deactivate", "reconnect"])
def test_connection_changes_invalidate_queued_work(ingestion, change):
    x = ingestion
    cid = x.connect().json()["id"]
    jid = x.enqueue(cid).json()["job"]["id"]
    if change == "deactivate":
        assert x.api.client.delete(PREFIX + f"/automation/connections/{cid}", headers=x.headers).status_code == 204
    else:
        assert x.connect().json()["revision"] == 2
    assert x.run(jid)["error_code"] == "CONNECTION_CHANGED"
    assert x.repo.get_batch(jid) is None


def test_wrong_encryption_key_fails_without_exposing_ciphertext(ingestion):
    x = ingestion
    cid = x.connect().json()["id"]
    jid = x.enqueue(cid).json()["job"]["id"]
    failed = x.run(jid, vault=CredentialVault(Fernet.generate_key()))
    assert failed["status"] == "FAILED" and failed["error_code"] == "CREDENTIALS_UNAVAILABLE"
    assert x.session.get.call_count == 1


def test_expired_lease_fences_out_old_worker_and_prevents_duplicate_batch(ingestion):
    x = ingestion
    cid = x.connect().json()["id"]
    jid = x.enqueue(cid).json()["job"]["id"]
    now = datetime.now(timezone.utc)
    first = x.repo.claim(jid, now=now)
    assert x.repo.claim(jid, now=now + timedelta(seconds=1)) is None
    second = x.repo.claim(jid, now=now + timedelta(seconds=301))
    payload = x.factory(x.repo.get_connection(cid), TOKEN).fetch_weekly_metrics("act_123", "2026-10-19")
    assert x.repo.finish(first, payload) is False
    assert x.repo.finish(second, payload) is True
    assert x.repo.fail(first, "OLD_WORKER", retryable=True)["status"] == "SUCCESS"
    with x.repo.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM ingestion_batches").fetchone()[0] == 1


def test_explicit_refresh_keeps_old_batch_immutable(ingestion):
    x = ingestion
    cid = x.connect().json()["id"]
    first = x.enqueue(cid).json()["job"]["id"]
    x.run(first)
    original = x.repo.get_batch(first)
    second = x.enqueue(cid, force_refresh=True).json()["job"]["id"]
    assert second != first
    assert x.run(second)["status"] == "SUCCESS"
    assert x.repo.get_batch(first) == original
    with x.repo.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM ingestion_batches").fetchone()[0] == 2


def test_broker_outage_preserves_outbox_and_dispatcher_can_recover(ingestion, monkeypatch):
    from cdms.adapters.tasks import celery_app as module
    x = ingestion
    cid = x.connect().json()["id"]
    x.dispatcher.side_effect = RuntimeError(TOKEN)
    queued = x.enqueue(cid)
    assert queued.status_code == 202 and queued.json()["dispatch_status"] == "DEFERRED"
    jid = queued.json()["job"]["id"]
    assert x.repo.get_job(jid)["status"] == "PENDING"
    monkeypatch.setenv("CDMS_IDENTITY_DB_PATH", str(x.api.identity.db_path))
    monkeypatch.setenv("CDMS_WORKSPACE_DATA_DIR", str(x.api.root))
    dispatcher = Mock()
    monkeypatch.setattr(module, "dispatch_job", dispatcher)
    assert module.dispatch_pending.run()["dispatched"] == 1
    dispatcher.assert_called_once_with(x.api.wa, jid)
    assert TOKEN not in json.dumps(dispatcher.call_args.args)


def test_weekly_scheduler_is_opt_in_idempotent_and_revalidates_membership(ingestion, monkeypatch):
    from cdms.adapters.tasks import celery_app as module
    x = ingestion
    monkeypatch.setenv("CDMS_IDENTITY_DB_PATH", str(x.api.identity.db_path))
    monkeypatch.setenv("CDMS_WORKSPACE_DATA_DIR", str(x.api.root))
    x.connect()
    assert module.schedule_weekly.run()["created"] == 0
    x.connect(automatic_sync=True)
    assert module.schedule_weekly.run()["created"] == 1
    assert module.schedule_weekly.run()["created"] == 0
    x.api.identity.remove_member(x.api.wa, x.api.users["alice"]["id"])
    assert module.schedule_weekly.run()["created"] == 0


@pytest.mark.parametrize("broker", ["memory://", pytest.param(os.getenv("CDMS_TEST_REDIS_URL"),
    marks=pytest.mark.skipif(not os.getenv("CDMS_TEST_REDIS_URL"), reason="Redis de teste não configurado"), id="redis")])
def test_real_celery_worker_consumes_ids_and_persists_ingestion(ingestion, monkeypatch, broker):
    from celery import Celery
    from celery.contrib.testing.worker import start_worker
    from cdms.adapters.tasks import celery_app as module
    x = ingestion
    cid = x.connect().json()["id"]
    jid = x.enqueue(cid).json()["job"]["id"]
    monkeypatch.setattr(module, "process_job", partial(process_job, identity=x.api.identity, root=x.api.root,
                                                      vault=CredentialVault(x.key), connector_factory=x.factory))
    app = Celery("ingestion-test", broker=broker, backend="cache+memory://" if broker == "memory://" else broker, set_as_current=False)
    app.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"],
                    task_default_queue="cdms-ingestion-test-" + uuid4().hex, result_expires=60)
    def consume(workspace_id, job_id):
        return module.task_sync_platform_metrics.run(workspace_id, job_id)
    task = app.task(name="tests.sync_platform_metrics")(consume)
    with start_worker(app, pool="solo", perform_ping_check=False, shutdown_timeout=15):
        pending = task.delay(x.api.wa, jid)
        result = pending.get(timeout=20, disable_sync_subtasks=False)
        pending.forget()
    app.close()
    assert result["status"] == "SUCCESS"
    assert x.repo.get_job(jid)["status"] == "SUCCESS"
    assert x.repo.get_batch(jid)["metrics"]["reach"] == 2000


def test_revocation_during_fetch_prevents_persistence(ingestion):
    x = ingestion
    cid = x.connect().json()["id"]
    member = x.api.users["member"]["id"]
    queued = x.api.client.post(PREFIX + f"/automation/connections/{cid}/sync", headers=x.api.login("member"),
                               json={"cycle_id": "2026-10-19"})
    jid = queued.json()["job"]["id"]
    def revoke(url, **kwargs):
        x.api.identity.remove_member(x.api.wa, member)
        return x.response(url, **kwargs)
    x.session.get.side_effect = revoke
    assert x.run(jid)["error_code"] == "ACCESS_REVOKED"
    assert x.repo.get_batch(jid) is None


def test_connection_change_during_fetch_rolls_back_batch(ingestion):
    x = ingestion
    cid = x.connect().json()["id"]
    jid = x.enqueue(cid).json()["job"]["id"]
    def deactivate(url, **kwargs):
        x.repo.deactivate(cid)
        return x.response(url, **kwargs)
    x.session.get.side_effect = deactivate
    assert x.run(jid)["status"] == "FAILED"
    assert x.repo.get_batch(jid) is None
    assert x.repo.get_connection(cid)["last_synced_at"] is None


def test_expired_final_attempt_is_terminal_instead_of_stuck_running(ingestion):
    x = ingestion
    cid = x.connect().json()["id"]
    jid = x.enqueue(cid).json()["job"]["id"]
    now = datetime.now(timezone.utc)
    assert x.repo.claim(jid, now=now)["attempts"] == 1
    assert x.repo.claim(jid, now=now + timedelta(seconds=301))["attempts"] == 2
    assert x.repo.claim(jid, now=now + timedelta(seconds=602))["attempts"] == 3
    assert x.repo.claim(jid, now=now + timedelta(seconds=903)) is None
    assert x.repo.get_job(jid)["status"] == "FAILED"
    assert x.repo.get_job(jid)["error_code"] == "RETRY_EXHAUSTED"


def test_optional_app_secret_is_encrypted_and_used_by_production_factory(ingestion, monkeypatch):
    from cdms.adapters.tasks.ingestion_runtime import meta_connector_factory
    x = ingestion
    x.api.client.app.state.platform_connector_factory = meta_connector_factory
    monkeypatch.setattr("cdms.adapters.connectors.meta_ads.requests.get", x.response)
    response = x.connect(app_secret="test-only-app-secret")
    assert response.status_code == 200, response.text
    cid = response.json()["id"]
    decoded = json.loads(CredentialVault(x.key).decrypt(x.repo.get_connection(cid)["encrypted_credentials"]))
    assert decoded == {"access_token": TOKEN, "app_secret": "test-only-app-secret"}
    assert "test-only-app-secret" not in x.repo.path.read_bytes().decode("latin1")
    jid = x.enqueue(cid).json()["job"]["id"]
    result = process_job(x.api.wa, jid, identity=x.api.identity, root=x.api.root,
                         vault=CredentialVault(x.key), connector_factory=meta_connector_factory)
    assert result["status"] == "SUCCESS"
