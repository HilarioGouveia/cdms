"""Testes de autenticação JWT e validação de contexto de Tenant."""

from datetime import timedelta
import pytest
from fastapi import HTTPException
from cdms.config.security import create_access_token, decode_access_token, verify_password, get_password_hash
from cdms.domain.entities.tenant import TenantContext, UserRole
from cdms.adapters.api.dependencies import get_current_tenant
from cdms.adapters.persistence.sqlite_identity_repo import SQLiteIdentityRepository


@pytest.fixture(autouse=True)
def signing_key(monkeypatch):
    monkeypatch.setenv("CDMS_SECRET_KEY", "unit-test-signing-key-with-at-least-32-bytes")


class DummyCredentials:
    def __init__(self, token: str):
        self.credentials = token


def test_password_hashing():
    pwd = "MySecretPassword123"
    hashed = get_password_hash(pwd)
    assert hashed.startswith("$pbkdf2-sha256$600000$")
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_token_encode_decode():
    payload = {"sub": "user_42", "workspace_id": "ws_alpha", "role": "OWNER"}
    token = create_access_token(payload, expires_delta=timedelta(minutes=10))
    decoded = decode_access_token(token)
    assert decoded["sub"] == "user_42"
    assert decoded["workspace_id"] == "ws_alpha"
    assert decoded["role"] == "OWNER"


def test_tenant_dependency_resolution(tmp_path):
    repo = SQLiteIdentityRepository(tmp_path / "identity.db")
    user = repo.create_user("admin@example.com", get_password_hash("MySecretPassword123"), "Admin")
    workspace_id = repo.create_workspace("Workspace", "workspace", user["id"])
    token = create_access_token({"sub": user["id"], "workspace_id": workspace_id, "role": "VIEWER"})
    tenant = get_current_tenant(DummyCredentials(token), repo, "unit-test-signing-key-with-at-least-32-bytes")
    assert tenant.user_id == user["id"]
    assert tenant.workspace_id == workspace_id
    assert tenant.role == UserRole.OWNER
