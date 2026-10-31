"""Autorização revalidada no banco a cada requisição e armazenamento por workspace."""
from dataclasses import dataclass
from pathlib import Path
from cdms.config.workspace_storage import workspace_db_path

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

from cdms.adapters.persistence.sqlite_identity_repo import SQLiteIdentityRepository
from cdms.adapters.persistence.sqlite_repo import SQLiteRepository
from cdms.config.security import decode_access_token
from cdms.domain.entities.tenant import TenantContext, UserRole
from cgs.adapters.persistence.sqlite_growth_repo import SQLiteGrowthRepository
from cgs.adapters.persistence.sqlite_cgs_fase2_repo import SQLiteCGSPhase2Repository
from cgs.adapters.persistence.sqlite_cgs_fase3_repo import SQLiteCGSPhase3Repository

security_scheme = HTTPBearer(auto_error=False)


def get_identity_repo(request: Request) -> SQLiteIdentityRepository:
    return request.app.state.identity


def get_signing_key(request: Request) -> str:
    return request.app.state.secret_key


def get_current_tenant(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
    identity: SQLiteIdentityRepository = Depends(get_identity_repo),
    secret_key: str = Depends(get_signing_key),
) -> TenantContext:
    unauthorized = HTTPException(401, "Credenciais de acesso inválidas ou expiradas.", headers={"WWW-Authenticate": "Bearer"})
    if credentials is None:
        raise unauthorized
    try:
        payload = decode_access_token(credentials.credentials, secret_key=secret_key)
        user_id, workspace_id = payload["sub"], payload["workspace_id"]
        if not isinstance(user_id, str) or not isinstance(workspace_id, str):
            raise unauthorized
        user = identity.get_user(user_id)
        tenant = identity.get_tenant(user_id, workspace_id)
        version = payload["token_version"]
        if not user or not tenant or type(version) is not int or version != user["token_version"]:
            raise unauthorized
        if user['must_change_password']:
            raise HTTPException(403, 'Troque a senha temporária antes de acessar o workspace.')
        return tenant  # O papel vigente vem do banco, não do token.
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        raise unauthorized


def require_writer(tenant: TenantContext = Depends(get_current_tenant)) -> TenantContext:
    if tenant.role == UserRole.VIEWER:
        raise HTTPException(403, "Este perfil tem acesso somente de leitura.")
    return tenant


def require_manager(tenant: TenantContext = Depends(get_current_tenant)) -> TenantContext:
    if tenant.role not in (UserRole.OWNER, UserRole.ADMIN):
        raise HTTPException(403, "Somente o proprietário ou administrador pode gerenciar membros.")
    return tenant


@dataclass
class WorkspaceRepositories:
    path: Path
    core: SQLiteRepository
    growth: SQLiteGrowthRepository

    def hypothesis(self, hypothesis_id: int):
        hypothesis = self.growth.get_hypothesis_by_id(hypothesis_id)
        if hypothesis is None:
            raise HTTPException(404, "Hipótese não encontrada neste workspace.")
        return hypothesis

    def phase2(self):
        return SQLiteCGSPhase2Repository(str(self.path))

    def phase3(self):
        return SQLiteCGSPhase3Repository(str(self.path))


def get_workspace_repositories(request: Request, tenant: TenantContext = Depends(get_current_tenant)) -> WorkspaceRepositories:
    # UUID gerado pelo servidor: nunca usar nomes, cabeçalhos ou caminhos enviados pelo cliente.
    try:
        path = workspace_db_path(request.app.state.workspace_data_dir, tenant.workspace_id)
    except ValueError:
        raise HTTPException(403, "Identificador de workspace inválido.")
    path.parent.mkdir(parents=True, exist_ok=True)
    return WorkspaceRepositories(path, SQLiteRepository(path), SQLiteGrowthRepository(str(path)))
