"""Consulta de workspaces e administração dos vínculos existentes."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from cdms.adapters.api.dependencies import get_current_tenant, get_identity_repo, require_manager
from cdms.adapters.persistence.sqlite_identity_repo import SQLiteIdentityRepository
from cdms.domain.entities.tenant import TenantContext, UserRole

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


class MemberRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: UserRole


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
