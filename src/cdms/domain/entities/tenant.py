"""Entidades de domínio para Multi-Tenancy e Workspaces."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class UserRole(str, Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"


@dataclass(frozen=True)
class Workspace:
    id: str
    name: str
    slug: str
    owner_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class TenantContext:
    workspace_id: str
    user_id: str
    role: UserRole