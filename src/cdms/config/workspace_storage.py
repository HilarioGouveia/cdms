"""Caminhos compartilhados pela API e pelos workers, sem caminhos do cliente."""
import os
from pathlib import Path
from uuid import UUID
from cdms.config.settings import settings


def identity_db_path():
    return Path(os.getenv("CDMS_IDENTITY_DB_PATH", str(settings.DATA_DIR / "identity.db")))


def workspace_data_dir():
    return Path(os.getenv("CDMS_WORKSPACE_DATA_DIR", str(settings.DATA_DIR / "workspaces")))


def workspace_db_path(root, workspace_id):
    return Path(root).resolve() / f"{UUID(workspace_id).hex}.db"
