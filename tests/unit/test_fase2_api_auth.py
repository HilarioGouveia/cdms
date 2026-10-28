"""Testes de autenticação JWT e validação de contexto de Tenant."""

from datetime import timedelta
import pytest
from fastapi import HTTPException
from cdms.config.security import create_access_token, decode_access_token, verify_password, get_password_hash
from cdms.domain.entities.tenant import TenantContext, UserRole
from cdms.adapters.api.dependencies import get_current_tenant


class DummyCredentials:
    def __init__(self, token: str):
        self.credentials = token


def test_password_hashing():
    pwd = "MySecretPassword123"
    hashed = get_password_hash(pwd)
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_token_encode_decode():
    payload = {"sub": "user_42", "workspace_id": "ws_alpha", "role": "OWNER"}
    token = create_access_token(payload, expires_delta=timedelta(minutes=10))
    decoded = decode_access_token(token)
    assert decoded["sub"] == "user_42"
    assert decoded["workspace_id"] == "ws_alpha"
    assert decoded["role"] == "OWNER"


def test_tenant_dependency_resolution():
    token = create_access_token({"sub": "user_100", "workspace_id": "ws_florianopolis", "role": "ADMIN"})
    tenant = get_current_tenant(DummyCredentials(token))
    assert tenant.user_id == "user_100"
    assert tenant.workspace_id == "ws_florianopolis"
    assert tenant.role == UserRole.ADMIN