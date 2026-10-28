"""Rotas de autenticação e seleção de workspace."""

from datetime import timedelta
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

from cdms.config.security import create_access_token, verify_password, get_password_hash

router = APIRouter(prefix="/auth", tags=["Autenticação"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    workspace_id: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_hours: int = 24


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    """Autentica o utilizador e emite token JWT com escopo de Workspace."""
    # Demonstração padrão para ambiente dev/cloud
    # Em produção, consulta o repositório de users e workspaces
    if payload.email == "creator@cdms.dev" and payload.password == "Secret123!":
        token = create_access_token(
            data={
                "sub": "user_dev_01",
                "workspace_id": payload.workspace_id,
                "role": "OWNER",
            }
        )
        return TokenResponse(access_token=token)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou utilizador sem acesso ao workspace.",
    )