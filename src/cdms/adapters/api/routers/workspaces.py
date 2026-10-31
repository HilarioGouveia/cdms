"""Consulta de workspaces e administração dos vínculos existentes."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from cdms.application.services.workspace_users import WorkspaceUsers
from cdms.adapters.api.dependencies import get_current_tenant, get_identity_repo, require_manager
from cdms.adapters.persistence.sqlite_identity_repo import SQLiteIdentityRepository
from cdms.domain.entities.tenant import TenantContext, UserRole

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


class MemberRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: UserRole


class MemberCreateRequest(MemberRoleRequest):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    temporary_password: str = Field(default='', max_length=1024)


class MemberResetRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    temporary_password: str = Field(min_length=12, max_length=1024)


@router.post('/current/members', status_code=201)
def create_member(payload: MemberCreateRequest, tenant: TenantContext = Depends(require_manager),
                  identity: SQLiteIdentityRepository = Depends(get_identity_repo)):
    try:
        created = WorkspaceUsers(identity).add(tenant, str(payload.email), payload.full_name,
                                                payload.role, payload.temporary_password)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    return {'created': created}


@router.post('/current/members/{user_id}/password', status_code=204)
def reset_member_password(user_id: str, payload: MemberResetRequest,
                          tenant: TenantContext = Depends(require_manager),
                          identity: SQLiteIdentityRepository = Depends(get_identity_repo)):
    try:
        WorkspaceUsers(identity).reset_password(tenant, user_id, payload.temporary_password)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.get("")
def list_workspaces(tenant: TenantContext = Depends(get_current_tenant), identity: SQLiteIdentityRepository = Depends(get_identity_repo)):
    return identity.list_workspaces(tenant.user_id)


@router.get("/current")
def current_workspace(tenant: TenantContext = Depends(get_current_tenant), identity: SQLiteIdentityRepository = Depends(get_identity_repo)):
    return next(w for w in identity.list_workspaces(tenant.user_id) if w["id"] == tenant.workspace_id)


@router.get("/current/members")
def list_members(tenant: TenantContext = Depends(require_manager), identity: SQLiteIdentityRepository = Depends(get_identity_repo)):
    return identity.list_members(tenant.workspace_id)


def check_member_change(identity, tenant, user_id, requested_role=None):
    if identity.get_user(user_id) is None:
        raise HTTPException(404, "Usuário não encontrado.")
    current = identity.get_member_role(tenant.workspace_id, user_id)
    if requested_role == UserRole.OWNER or current == UserRole.OWNER:
        raise HTTPException(403, "O proprietário não pode ser alterado por este endpoint.")
    if user_id == tenant.user_id:
        raise HTTPException(403, "Não é permitido alterar o próprio acesso.")
    if tenant.role != UserRole.OWNER and (requested_role == UserRole.ADMIN or current == UserRole.ADMIN):
        raise HTTPException(403, "Somente o proprietário pode alterar administradores.")


@router.put("/current/members/{user_id}", status_code=204)
def set_member(user_id: str, payload: MemberRoleRequest, tenant: TenantContext = Depends(require_manager),
               identity: SQLiteIdentityRepository = Depends(get_identity_repo)):
    check_member_change(identity, tenant, user_id, payload.role)
    identity.set_member(tenant.workspace_id, user_id, payload.role)


@router.delete("/current/members/{user_id}", status_code=204)
def remove_member(user_id: str, tenant: TenantContext = Depends(require_manager),
                  identity: SQLiteIdentityRepository = Depends(get_identity_repo)):
    check_member_change(identity, tenant, user_id)
    identity.remove_member(tenant.workspace_id, user_id)
