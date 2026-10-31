"""Autenticação compartilhada pelo Studio e pela API, sem dependência de UI."""
from dataclasses import dataclass
from datetime import datetime, timezone

import jwt

from cdms.config.security import create_access_token, decode_access_token, verify_password
from cdms.domain.entities.tenant import TenantContext


class AuthenticationError(ValueError):
    pass


@dataclass(frozen=True)
class WorkspaceSession:
    tenant: TenantContext
    full_name: str
    email: str
    workspaces: list[dict]
    must_change_password: bool = False

    @property
    def workspace_name(self):
        return next(w["name"] for w in self.workspaces if w["id"] == self.tenant.workspace_id)


class WorkspaceAuth:
    def __init__(self, identity, secret_key, dummy_password_hash):
        self.identity = identity
        self.secret_key = secret_key
        self.dummy_password_hash = dummy_password_hash

    def login(self, email, password, workspace_id=None):
        user = self.identity.get_user_by_email(email)
        password_hash = user["hashed_password"] if user else self.dummy_password_hash
        valid = isinstance(password, str) and 0 < len(password) <= 1024
        password_ok = verify_password(password if valid else "", password_hash)
        if not valid or not password_ok or not user or not user["is_active"]:
            raise AuthenticationError("Credenciais inválidas ou acesso ao workspace indisponível.")
        workspaces = self.identity.list_workspaces(user["id"])
        selected = workspace_id if workspace_id is not None else (workspaces[0]["id"] if workspaces else None)
        tenant = self.identity.get_tenant(user["id"], selected)
        if not tenant:
            raise AuthenticationError("Credenciais inválidas ou acesso ao workspace indisponível.")
        return self._issue(user, tenant.workspace_id)

    def _issue(self, user, workspace_id):
        return create_access_token(
            {"sub": user["id"], "workspace_id": workspace_id, "token_version": user["token_version"]},
            secret_key=self.secret_key,
        )

    def resolve(self, token):
        try:
            payload = decode_access_token(token, secret_key=self.secret_key)
            user_id, workspace_id = payload["sub"], payload["workspace_id"]
            if not isinstance(user_id, str) or not isinstance(workspace_id, str):
                raise ValueError("Identidade inválida")
            user = self.identity.get_user(user_id)
            tenant = self.identity.get_tenant(user_id, workspace_id)
            version = payload["token_version"]
            if not user or not tenant or type(version) is not int or version != user["token_version"]:
                raise ValueError("Sessão revogada")
            workspaces = self.identity.list_workspaces(user_id)
            if not any(w["id"] == workspace_id for w in workspaces):
                raise ValueError("Vínculo removido")
            return WorkspaceSession(tenant, user["full_name"], user["email"],
                                    workspaces, bool(user['must_change_password']))
        except (jwt.PyJWTError, ValueError, KeyError, TypeError, StopIteration) as error:
            raise AuthenticationError("Sessão inválida ou expirada. Entre novamente.") from error

    def switch(self, token, workspace_id):
        session = self.resolve(token)
        if not self.identity.get_tenant(session.tenant.user_id, workspace_id):
            raise AuthenticationError("Acesso ao workspace indisponível.")
        # Preserve expiry: switching workspaces must not extend the session indefinitely.
        payload = decode_access_token(token, secret_key=self.secret_key)
        payload["workspace_id"] = workspace_id
        expires = datetime.fromtimestamp(payload["exp"], timezone.utc) - datetime.now(timezone.utc)
        return create_access_token(payload, expires_delta=expires, secret_key=self.secret_key)

    def logout(self, token):
        session = self.resolve(token)
        self.identity.revoke_tokens(session.tenant.user_id)
