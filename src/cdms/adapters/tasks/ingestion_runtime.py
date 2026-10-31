"""Composição da ingestão compartilhada por API e workers."""
from pathlib import Path
import json
from cdms.adapters.connectors.meta_ads import MetaAdsConnector
from cdms.adapters.persistence.sqlite_identity_repo import SQLiteIdentityRepository
from cdms.adapters.persistence.sqlite_ingestion_repo import SQLiteIngestionRepository
from cdms.application.ports.platform_connector import PlatformError
from cdms.application.use_cases.sync_platform_metrics import SyncPlatformMetricsUseCase
from cdms.config.credential_vault import CredentialVault
from cdms.config.workspace_storage import identity_db_path, workspace_data_dir, workspace_db_path
from cdms.domain.entities.tenant import UserRole


def meta_connector_factory(connection, token):
    if connection["platform"] != 'META_ADS':
        raise PlatformError("PLATFORM_NOT_IMPLEMENTED")
    credentials = json.loads(token) if token.startswith("{") else {"access_token": token}
    return MetaAdsConnector(credentials["access_token"], app_secret=credentials.get("app_secret"), api_version=connection["api_version"], timezone_name=connection["timezone_name"],
                            conversion_action_type=connection["conversion_action_type"])


def authorize(identity, workspace_id, user_id):
    tenant = identity.get_tenant(user_id, workspace_id)
    user = identity.get_user(user_id)
    return tenant is not None and not user['must_change_password'] and tenant.role != UserRole.VIEWER


def process_job(workspace_id, job_id, *, identity=None, root=None, vault=None, connector_factory=None):
    if identity is None:
        if not identity_db_path().is_file():
            return None
        identity = SQLiteIdentityRepository(identity_db_path())
    if not identity.workspace_exists(workspace_id):
        return None
    path = workspace_db_path(root or workspace_data_dir(), workspace_id)
    if not path.is_file():
        return None
    repo = SQLiteIngestionRepository(path)
    try:
        vault = vault or CredentialVault()
    except RuntimeError:
        job = repo.claim(job_id)
        return repo.fail(job, "CREDENTIALS_UNAVAILABLE") if job else repo.get_job(job_id)
    return SyncPlatformMetricsUseCase(
        repo, connector_factory or meta_connector_factory, vault,
        lambda user: authorize(identity, workspace_id, user),
    ).execute(job_id)


def dispatch_job(workspace_id, job_id):
    from cdms.adapters.tasks.celery_app import task_sync_platform_metrics
    task_sync_platform_metrics.apply_async(args=[workspace_id, job_id], retry=False)
