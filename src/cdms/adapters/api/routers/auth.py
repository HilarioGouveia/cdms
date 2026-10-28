"""Login real com senha e vínculo de workspace; logout revoga tokens do usuário."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from cdms.adapters.api.dependencies import get_current_tenant, get_identity_repo
from cdms.adapters.persistence.sqlite_identity_repo import SQLiteIdentityRepository
from cdms.config.security import create_access_token, verify_password, get_password_hash
from cdms.domain.entities.tenant import TenantContext

router = APIRouter(prefix="/auth", tags=["Autenticação"])


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)
    workspace_id: str = Field(min_length=1, max_length=64)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_hours: int = 24


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, identity: SQLiteIdentityRepository = Depends(get_identity_repo)):
    user = identity.get_user_by_email(str(payload.email))
    password_hash = user["hashed_password"] if user else request.app.state.dummy_password_hash
    password_ok = verify_password(payload.password, password_hash)
    tenant = identity.get_tenant(user["id"], payload.workspace_id) if user else None
    if not password_ok or not tenant:
        raise HTTPException(401, "Credenciais inválidas ou acesso ao workspace indisponível.",
                            headers={"WWW-Authenticate": "Bearer"})
    token = create_access_token(
        {"sub": user["id"], "workspace_id": tenant.workspace_id, "token_version": user["token_version"]},
        secret_key=request.app.state.secret_key,
    )
    return TokenResponse(access_token=token)


@router.post("/logout", status_code=204)
def logout(tenant: TenantContext = Depends(get_current_tenant), identity: SQLiteIdentityRepository = Depends(get_identity_repo)):
    identity.revoke_tokens(tenant.user_id)


class PasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=12, max_length=1024)


@router.post("/password", status_code=204)
def change_password(payload: PasswordChangeRequest, tenant: TenantContext = Depends(get_current_tenant),
                    identity: SQLiteIdentityRepository = Depends(get_identity_repo)):
    user = identity.get_user(tenant.user_id)
    if not verify_password(payload.current_password, user["hashed_password"]):
        raise HTTPException(401, "Senha atual inválida.")
    identity.change_password(tenant.user_id, get_password_hash(payload.new_password))
