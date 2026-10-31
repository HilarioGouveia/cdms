"""Gestão de membros com autorização revalidada e proteção de contas compartilhadas."""
import sqlite3
from pydantic import EmailStr, TypeAdapter

from cdms.config.security import get_password_hash, verify_password
from cdms.domain.entities.tenant import UserRole


class WorkspaceUsers:
    def __init__(self, identity):
        self.identity = identity

    def manager(self, actor):
        current = self.identity.get_tenant(actor.user_id, actor.workspace_id)
        user = self.identity.get_user(actor.user_id)
        if not current or current.role not in (UserRole.OWNER, UserRole.ADMIN) or user['must_change_password']:
            raise ValueError('Acesso de gestão indisponível.')
        return current

    def members(self, actor):
        actor = self.manager(actor)
        return self.identity.list_members(actor.workspace_id)

    def check(self, actor, user_id, role=None):
        actor = self.manager(actor)
        current = self.identity.get_member_role(actor.workspace_id, user_id)
        if current is None:
            raise ValueError('Membro não encontrado neste workspace.')
        if current == UserRole.OWNER or role == UserRole.OWNER or user_id == actor.user_id:
            raise ValueError('Não é permitido alterar o proprietário ou o próprio acesso.')
        if actor.role != UserRole.OWNER and (current == UserRole.ADMIN or role == UserRole.ADMIN):
            raise ValueError('Somente o proprietário pode alterar administradores.')
        return actor

    def add(self, actor, email, name, role, temporary_password):
        actor = self.manager(actor)
        role = UserRole(role)
        if role == UserRole.OWNER or (role == UserRole.ADMIN and actor.role != UserRole.OWNER):
            raise ValueError('Somente o proprietário pode cadastrar administradores.')
        email = str(TypeAdapter(EmailStr).validate_python(email.strip()))
        name = name.strip()
        if not name or len(name) > 200:
            raise ValueError('Informe um nome com até 200 caracteres.')
        user = self.identity.get_user_by_email(email)
        if user:
            if self.identity.get_member_role(actor.workspace_id, user['id']):
                raise ValueError('Este usuário já pertence ao workspace.')
            if not user['is_active']:
                raise ValueError('Não foi possível adicionar esta conta.')
            self.identity.set_member(actor.workspace_id, user['id'], role)
            return False
        self.validate_password(temporary_password)
        # Cadastro e vínculo são gravados juntos, sem conta órfã em caso de falha.
        from uuid import uuid4
        from datetime import datetime, timezone
        uid = str(uuid4())
        hashed = get_password_hash(temporary_password)
        try:
            with self.identity.connection() as conn:
                conn.execute('INSERT INTO users (id,email,hashed_password,full_name,created_at,must_change_password) VALUES (?,?,?,?,?,1)',
                             (uid, email.casefold(), hashed, name, datetime.now(timezone.utc).isoformat()))
                conn.execute('INSERT INTO workspace_members (workspace_id,user_id,role,joined_at) VALUES (?,?,?,?)',
                             (actor.workspace_id, uid, role.value, datetime.now(timezone.utc).isoformat()))
        except sqlite3.IntegrityError:
            raise ValueError('Cadastro não concluído. Atualize a lista e tente novamente.') from None
        return True

    def set_role(self, actor, user_id, role):
        role = UserRole(role)
        actor = self.check(actor, user_id, role)
        self.identity.set_member(actor.workspace_id, user_id, role)

    def remove(self, actor, user_id):
        actor = self.check(actor, user_id)
        self.identity.remove_member(actor.workspace_id, user_id)

    def reset_password(self, actor, user_id, temporary_password):
        actor = self.check(actor, user_id)
        # Uma senha é global: gestores de um workspace não podem tomar contas de outros.
        if any(w['id'] != actor.workspace_id for w in self.identity.list_workspaces(user_id)):
            raise ValueError('Conta compartilhada com outro workspace. A redefinição deve ser feita pelo próprio usuário ou pelo operador da instalação.')
        self.validate_password(temporary_password)
        self.identity.change_password(user_id, get_password_hash(temporary_password), temporary=True)

    @staticmethod
    def validate_password(password):
        if not isinstance(password, str) or not 12 <= len(password) <= 1024:
            raise ValueError('A senha deve ter entre 12 e 1024 caracteres.')

    def change_password(self, user_id, current_password, new_password):
        self.validate_password(new_password)
        user = self.identity.get_user(user_id)
        if not user or not user['is_active'] or not verify_password(current_password, user['hashed_password']):
            raise ValueError('Senha atual inválida.')
        if current_password == new_password:
            raise ValueError('Escolha uma senha diferente da atual.')
        self.identity.change_password(user_id, get_password_hash(new_password))
