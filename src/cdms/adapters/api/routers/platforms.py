"""Conexões de mídia, fila de sincronização e dados preparados para o ritual."""
from datetime import date
import os
import json
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field, SecretStr
from cdms.adapters.api.dependencies import get_workspace_repositories, require_writer, require_manager, WorkspaceRepositories
from cdms.adapters.api.routers.growth import InputModel
from cdms.adapters.connectors.meta_ads import MetaAdsConnector, closed_week
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
    MetaAdsConnector.account_id(payload.account_id)
    token = payload.access_token.get_secret_value()
    if not token or len(token) > 4096 or not token.isascii() or any(c.isspace() for c in token):
        raise ValueError("Token da plataforma inválido.")
    try:
        vault = CredentialVault(request.app.state.credential_key)
    except RuntimeError:
        raise HTTPException(503, "Configure CDMS_CREDENTIAL_KEY antes de cadastrar conexões.")
    secret = payload.app_secret.get_secret_value() if payload.app_secret is not None else None
    if secret is not None and (not secret or len(secret) > 4096 or not secret.isascii() or any(c.isspace() for c in secret)):
        raise ValueError("App secret inválido.")
    credentials = json.dumps({"access_token": token, "app_secret": secret}) if secret else token
    connection = {"platform": payload.platform.value, "api_version": payload.api_version,
                  "timezone_name": "UTC", "conversion_action_type": payload.conversion_action_type}
    try:
        metadata = request.app.state.platform_connector_factory(connection, credentials).validate_account(payload.account_id)
    except PlatformError as exc:
        raise HTTPException(503 if exc.retryable else 502, exc.code)
    row = get_repo(store).save_connection(account_id=payload.account_id, encrypted_credentials=vault.encrypt(credentials),
                                         api_version=payload.api_version, conversion_action_type=payload.conversion_action_type,
                                         timezone_name=metadata["timezone_name"], currency=metadata["currency"],
                                         created_by=tenant.user_id, automatic_sync=payload.automatic_sync)
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
    if payload.retry_failed and payload.force_refresh:
        raise ValueError("Escolha retentativa ou atualização, não ambas.")
    repo = get_repo(store)
    connection = repo.get_connection(connection_id)
    if connection is None:
        raise HTTPException(404, "Conexão não encontrada neste workspace.")
    closed_week(payload.cycle_id.isoformat(), connection["timezone_name"])
    job, changed = repo.enqueue(connection_id, payload.cycle_id.isoformat(), tenant.user_id,
                                retry_failed=payload.retry_failed, force_refresh=payload.force_refresh)
    dispatch_status = 'EXISTING'
    if changed:
        try:
            request.app.state.ingestion_dispatcher(tenant.workspace_id, job["id"])
            dispatch_status = 'ENQUEUED'
        except Exception:
            dispatch_status = 'DEFERRED'  # O job permanece persistido para o dispatcher periódico.
    return {"job": public_job(job), "dispatch_status": dispatch_status}


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
