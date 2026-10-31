"""Conexões de mídia, fila de sincronização e dados preparados para o ritual."""
from datetime import date
import os
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field, SecretStr
from cdms.adapters.api.dependencies import get_workspace_repositories, require_writer, require_manager, WorkspaceRepositories
from cdms.adapters.api.routers.growth import InputModel
from cdms.adapters.persistence.sqlite_ingestion_repo import SQLiteIngestionRepository
from cdms.application.ports.platform_connector import PlatformError
from cdms.config.credential_vault import CredentialVault
from cdms.domain.entities.integrations import PlatformType
from cdms.domain.entities.tenant import TenantContext
from cdms.domain.services.canonical_metrics import CANONICAL_DEFINITIONS

router = APIRouter(prefix="/automation", tags=["Ingestão de plataformas"])


class ConnectPlatformRequest(InputModel):
    platform: PlatformType
    account_id: str = Field(min_length=1, max_length=100)
    access_token: SecretStr
    app_secret: SecretStr | None = None
    api_version: str = Field(default_factory=lambda: os.getenv("CDMS_META_API_VERSION", "v26.0"), pattern=r"^v[0-9]{1,3}\.[0-9]{1,2}$")
    conversion_action_type: str = Field(default="offsite_conversion.fb_pixel_purchase", pattern=r"^[A-Za-z0-9_.]{1,200}$")
    automatic_sync: bool = False


class SyncRequest(InputModel):
    cycle_id: date
    retry_failed: bool = False
    force_refresh: bool = False


def public_connection(row):
    return {key: row[key] for key in ("id", "platform", "account_id", "api_version", "conversion_action_type",
                                    "timezone_name", "currency", "is_active", "revision", "automatic_sync", "last_synced_at", "created_at")}


def public_job(row):
    return {key: row[key] for key in ("id", "connection_id", "connection_revision", "generation", "cycle_id", "requested_by",
                                    "status", "attempts", "error_code", "created_at", "finished_at")}


def get_repo(store):
    return SQLiteIngestionRepository(store.path)


def required_job(repo, job_id):
    job = repo.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Sincronização não encontrada neste workspace.")
    return job


@router.post("/connect-platform")
def connect_platform(payload: ConnectPlatformRequest, request: Request,
                     tenant: TenantContext = Depends(require_manager),
                     store: WorkspaceRepositories = Depends(get_workspace_repositories)):
    if payload.platform != PlatformType.META_ADS:
        raise HTTPException(501, "Este adaptador ainda não foi implementado. A etapa atual suporta Meta Ads.")
    from cdms.application.services.platform_ingestion import PlatformIngestion
    service = PlatformIngestion(get_repo(store), request.app.state.identity, tenant,
        request.app.state.platform_connector_factory, lambda: CredentialVault(request.app.state.credential_key),
        request.app.state.ingestion_dispatcher)
    try:
        row = service.connect(payload.account_id, payload.access_token.get_secret_value(), payload.api_version,
            payload.conversion_action_type, payload.app_secret.get_secret_value() if payload.app_secret else None,
            payload.automatic_sync)
    except RuntimeError:
        raise HTTPException(503, 'Configure CDMS_CREDENTIAL_KEY antes de cadastrar conexões.') from None
    except PlatformError as exc:
        raise HTTPException(503 if exc.retryable else 502, exc.code) from None
    return public_connection(row)


@router.get("/connections")
def list_connections(store: WorkspaceRepositories = Depends(get_workspace_repositories)):
    return [public_connection(row) for row in get_repo(store).list_connections()]


@router.delete("/connections/{connection_id}", status_code=204)
def deactivate_connection(connection_id: str, _manager: TenantContext = Depends(require_manager),
                          store: WorkspaceRepositories = Depends(get_workspace_repositories)):
    if not get_repo(store).deactivate(connection_id):
        raise HTTPException(404, "Conexão não encontrada neste workspace.")


@router.post("/connections/{connection_id}/sync", status_code=202)
def enqueue_sync(connection_id: str, payload: SyncRequest, request: Request,
                 tenant: TenantContext = Depends(require_writer),
                 store: WorkspaceRepositories = Depends(get_workspace_repositories)):
    from cdms.application.services.platform_ingestion import PlatformIngestion
    repo = get_repo(store)
    if repo.get_connection(connection_id) is None:
        raise HTTPException(404, 'Conexão não encontrada neste workspace.')
    service = PlatformIngestion(repo, request.app.state.identity, tenant,
        request.app.state.platform_connector_factory, lambda: CredentialVault(request.app.state.credential_key),
        request.app.state.ingestion_dispatcher)
    job, status = service.enqueue(connection_id, payload.cycle_id.isoformat(), payload.retry_failed, payload.force_refresh)
    return {'job': public_job(job), 'dispatch_status': status}


@router.get("/jobs")
def list_jobs(store: WorkspaceRepositories = Depends(get_workspace_repositories)):
    return [public_job(row) for row in get_repo(store).list_jobs()]


@router.get("/jobs/{job_id}")
def get_job(job_id: str, store: WorkspaceRepositories = Depends(get_workspace_repositories)):
    return public_job(required_job(get_repo(store), job_id))


@router.get("/jobs/{job_id}/result")
def get_result(job_id: str, store: WorkspaceRepositories = Depends(get_workspace_repositories)):
    repo = get_repo(store)
    job = required_job(repo, job_id)
    if job["status"] != 'SUCCESS':
        raise HTTPException(409, "A sincronização ainda não possui resultado concluído.")
    return repo.get_batch(job_id)


@router.get("/jobs/{job_id}/ritual-input")
def get_ritual_input(job_id: str, store: WorkspaceRepositories = Depends(get_workspace_repositories)):
    result = get_result(job_id, store)
    snapshots = [{"key": d.key, "observed_value": result["metrics"][d.key],
                  "is_available": result["metrics"][d.key] is not None,
                  "unavailability_reason": result["unavailability_reasons"].get(d.key)}
                 for d in CANONICAL_DEFINITIONS]
    return {"week_start": date.fromisoformat(result["cycle_id"]), "snapshots": snapshots}
