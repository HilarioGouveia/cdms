"""Entidades de domínio para conectores de plataformas e ingestão automatizada."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class PlatformType(str, Enum):
    META_ADS = "META_ADS"
    YOUTUBE_STUDIO = "YOUTUBE_STUDIO"
    TIKTOK_ADS = "TIKTOK_ADS"


class SyncStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


@dataclass(frozen=True)
class PlatformConnection:
    """Credenciais e metadados de conexão com APIs oficiais de criadores."""
    id: str
    workspace_id: str
    platform: PlatformType
    account_id: str
    is_active: bool = True
    encrypted_credentials: str = ""
    last_synced_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class RawIngestionPayload:
    """Dados brutos capturados das plataformas para auditoria imutável."""
    id: str
    workspace_id: str
    platform: PlatformType
    cycle_id: str
    payload_json: Dict[str, Any]
    status: SyncStatus
    error_message: Optional[str] = None
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))