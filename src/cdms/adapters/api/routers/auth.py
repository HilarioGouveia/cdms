"""Login real com senha e vínculo de workspace; logout revoga tokens do usuário."""
from fastapi import APIRouter, Depends, HTTPException, Request, Security
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from cdms.adapters.api.dependencies import get_current_tenant, get_identity_repo, security_scheme
from cdms.adapters.persistence.sqlite_identity_repo import SQLiteIdentityRepository
from cdms.domain.entities.tenant import TenantContext
from cdms.application.services.workspace_auth import WorkspaceAuth, AuthenticationError

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
    service = WorkspaceAuth(identity, request.app.state.secret_key, request.app.state.dummy_password_hash)
    try:
        token = service.login(str(payload.email), payload.password, payload.workspace_id)
    except AuthenticationError as error:
        raise HTTPException(401, str(error), headers={"WWW-Authenticate": "Bearer"}) from error
    return TokenResponse(access_token=token)


@router.post("/logout", status_code=204)
def logout(tenant: TenantContext = Depends(get_current_tenant), identity: SQLiteIdentityRepository = Depends(get_identity_repo)):
    identity.revoke_tokens(tenant.user_id)


class PasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=12, max_length=1024)


def password_session(request: Request, credentials=Security(security_scheme),
                     identity: SQLiteIdentityRepository = Depends(get_identity_repo)):
    service = WorkspaceAuth(identity, request.app.state.secret_key, request.app.state.dummy_password_hash)
    try:
        return service.resolve(credentials.credentials if credentials else '')
    except AuthenticationError as error:
        raise HTTPException(401, str(error)) from error


@router.post("/password", status_code=204)
def change_password(payload: PasswordChangeRequest, session=Depends(password_session),
                    identity: SQLiteIdentityRepository = Depends(get_identity_repo)):
    from cdms.application.services.workspace_users import WorkspaceUsers
    try:
        WorkspaceUsers(identity).change_password(session.tenant.user_id, payload.current_password, payload.new_password)
    except ValueError as error:
        raise HTTPException(401 if str(error) == 'Senha atual inválida.' else 400, str(error)) from error
