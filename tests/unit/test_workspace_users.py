"""Permissões e isolamento da gestão de usuários independente do transporte."""
import pytest

from cdms.adapters.persistence.sqlite_identity_repo import SQLiteIdentityRepository
from cdms.application.services.workspace_users import WorkspaceUsers
from cdms.domain.entities.tenant import UserRole


def test_role_changes_removal_and_revoked_manager_are_revalidated(tmp_path):
    repo = SQLiteIdentityRepository(tmp_path / 'identity.db')
    owner = repo.create_user('owner@example.com', 'unused', 'Owner')
    admin = repo.create_user('admin@example.com', 'unused', 'Admin')
    member = repo.create_user('member@example.com', 'unused', 'Member')
    workspace = repo.create_workspace('Empresa', 'empresa', owner['id'])
    repo.set_member(workspace, admin['id'], UserRole.ADMIN)
    repo.set_member(workspace, member['id'], UserRole.MEMBER)
    service = WorkspaceUsers(repo)
    owner_context = repo.get_tenant(owner['id'], workspace)
    admin_context = repo.get_tenant(admin['id'], workspace)
    with pytest.raises(ValueError):
        service.set_role(admin_context, member['id'], UserRole.ADMIN)
    with pytest.raises(ValueError):
        service.remove(admin_context, owner['id'])
    with pytest.raises(ValueError):
        service.remove(owner_context, owner['id'])
    service.set_role(owner_context, member['id'], UserRole.ADMIN)
    with pytest.raises(ValueError):
        service.remove(admin_context, member['id'])
    service.set_role(owner_context, member['id'], UserRole.VIEWER)
    service.remove(admin_context, member['id'])
    assert repo.get_tenant(member['id'], workspace) is None
    assert repo.get_user(member['id']) is not None
    service.set_role(owner_context, admin['id'], UserRole.MEMBER)
    with pytest.raises(ValueError):
        service.members(admin_context)


def test_schema_upgrade_preserves_existing_account(tmp_path):
    import sqlite3
    path = tmp_path / 'legacy.db'
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, hashed_password TEXT NOT NULL, full_name TEXT NOT NULL, is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL)')
        conn.execute("INSERT INTO users VALUES ('legacy','old@example.com','preserved','Old',1,'2026-01-01')")
    repo = SQLiteIdentityRepository(path)
    user = repo.get_user('legacy')
    assert user['hashed_password'] == 'preserved'
    assert user['must_change_password'] == 0
    assert user['token_version'] == 0
    assert user['theme_preference'] == 'dark-premium'
    repo.set_theme_preference('legacy', 'soft-light')
    assert repo.get_user('legacy')['theme_preference'] == 'soft-light'
    with pytest.raises(ValueError):
        repo.set_theme_preference('legacy', '../invalid')
