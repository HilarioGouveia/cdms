"""Dependências de injeção para rotas FastAPI com isolamento por Workspace."""

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

from cdms.config.security import decode_access_token
from cdms.domain.entities.tenant import TenantContext, UserRole

security_scheme = HTTPBearer()


def get_current_tenant(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
) -> TenantContext:
    """Extrai e valida o token JWT garantindo o contexto de workspace ativo."""
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        workspace_id: str = payload.get("workspace_id")
        role_str: str = payload.get("role", "MEMBER")

        if not user_id or not workspace_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de acesso inválido: payload incompleto.",
            )

        return TenantContext(
            workspace_id=workspace_id,
            user_id=user_id,
            role=UserRole(role_str),
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado. Por favor, autentique-se novamente.",
        )
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais de autenticação inválidas.",
        )