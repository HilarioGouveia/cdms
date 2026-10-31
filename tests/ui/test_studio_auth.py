"""Login real do Studio, com identidade e bancos operacionais temporários."""
from datetime import timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from cdms.adapters.persistence.sqlite_identity_repo import SQLiteIdentityRepository
from cdms.adapters.persistence.sqlite_repo import SQLiteRepository
from cdms.application.services.workspace_auth import WorkspaceAuth, AuthenticationError
from cdms.config.security import get_password_hash, create_access_token, decode_access_token
from cdms.config.workspace_storage import workspace_db_path
from cdms.domain.entities.tenant import UserRole
from cgs.adapters.persistence.sqlite_growth_repo import SQLiteGrowthRepository

APP = Path(__file__).resolve().parents[2] / "app.py"
PASSWORD = "test-only-password-123"
KEY = "test-only-studio-signing-key-at-least-32-bytes"


@pytest.fixture
def account(tmp_path, monkeypatch):
    monkeypatch.delenv("CDMS_STUDIO_MODE", raising=False)
    monkeypatch.setenv("CDMS_SECRET_KEY", KEY)
    monkeypatch.setenv("CDMS_IDENTITY_DB_PATH", str(tmp_path / "identity.db"))
    root = tmp_path / "workspaces"
    monkeypatch.setenv("CDMS_WORKSPACE_DATA_DIR", str(root))
    identity = SQLiteIdentityRepository(tmp_path / "identity.db")
    hashed = get_password_hash(PASSWORD)
    user = identity.create_user("owner@example.com", hashed, "Proprietário")
    first = identity.create_workspace("Empresa A", "empresa-a", user["id"])
    second = identity.create_workspace("Empresa B", "empresa-b", user["id"])
    outsider = identity.create_user("other@example.com", hashed, "Outro")
    private = identity.create_workspace("Privado", "privado", outsider["id"])
    service = WorkspaceAuth(identity, KEY, hashed)
    return identity, user, first, second, private, root, service


def app():
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception
    return at


def login(at, password=PASSWORD):
    at.text_input(key="login_email").set_value("owner@example.com")
    at.text_input(key="login_password").set_value(password)
    next(b for b in at.button if b.label == "Entrar").click().run()
    assert not at.exception, [e.message for e in at.exception]


def test_login_gate_and_invalid_credentials_never_open_workspace(account):
    *_, root, service = account
    at = app()
    assert not root.exists()
    assert not any(b.key == "studio_open_growth" for b in at.button)
    login(at, "wrong")
    assert at.error
    assert not root.exists()
    login(at)
    assert not at.error
    assert at.button(key="studio_open_growth")
    assert "login_password" not in at.session_state
    assert service.resolve(at.session_state["_auth_token"]).tenant.workspace_id == account[2]


def test_workspace_switch_clears_drafts_and_saves_to_selected_bank(account):
    identity, user, first, second, private, root, service = account
    at = app()
    login(at)
    at.button(key="studio_nav_Experimentos").click().run()
    at.button(key="studio_page_baseline").click().run()
    next(b for b in at.button if b.label == "Salvar Baseline Ativa").click().run()
    assert not at.exception
    assert SQLiteGrowthRepository(str(workspace_db_path(root, first))).get_active_baseline()
    at.button(key="studio_nav_Governança").click().run()
    at.button(key="studio_page_calibration").click().run()
    next(b for b in at.button if b.label == "Salvar Novas Calibrações").click().run()
    assert not at.exception
    assert SQLiteRepository(workspace_db_path(root, first)).get_active_calibrations()
    at.session_state["growth_secret_draft"] = "only-company-a"
    at.session_state["_studio_workspace_drafts"] = {"a": {"private": "old"}}
    at.selectbox(key="account_workspace").set_value(second).run()
    assert not at.exception
    assert "growth_secret_draft" not in at.session_state
    assert "_studio_workspace_drafts" not in at.session_state
    assert service.resolve(at.session_state["_auth_token"]).tenant.workspace_id == second
    assert SQLiteGrowthRepository(str(workspace_db_path(root, second))).get_active_baseline() is None
    assert not workspace_db_path(root, private).exists()


def test_unknown_user_and_account_without_membership_are_rejected(account):
    identity, user, first, second, private, root, service = account
    identity.create_user("unassigned@example.com", get_password_hash(PASSWORD), "Sem workspace")
    for email in ("missing@example.com", "unassigned@example.com"):
        with pytest.raises(AuthenticationError):
            service.login(email, PASSWORD)
    assert not root.exists()


def test_theme_preference_persists_per_account_and_logout_clears_it(account):
    identity, user, first, *_ = account
    at = app()
    login(at)
    at.selectbox(key='account_theme').set_value('soft-light').run()
    assert not at.exception
    assert identity.get_user(user['id'])['theme_preference'] == 'soft-light'
    assert identity.get_user_by_email('other@example.com')['theme_preference'] == 'dark-premium'
    assert at.session_state['_theme_profile'] == 'soft-light'
    at.button(key='account_logout').click().run()
    assert '_theme_profile' not in at.session_state
    login(at)
    assert at.selectbox(key='account_theme').value == 'soft-light'
    at.selectbox(key='account_theme').set_value('dark-premium').run()
    assert not at.exception
    assert identity.get_user(user['id'])['theme_preference'] == 'dark-premium'


def test_sidebar_and_mobile_context_controls_stay_in_sync(account):
    from datetime import date
    at = app()
    login(at)
    at.date_input(key='studio_cycle').set_value(date(2026, 10, 19)).run()
    assert not at.exception
    assert at.date_input(key='mobile_studio_cycle').value == date(2026, 10, 19)
    at.date_input(key='mobile_studio_cycle').set_value(date(2026, 10, 20)).run()
    assert at.error
    assert at.date_input(key='studio_cycle').value == date(2026, 10, 20)
    at.date_input(key='studio_cycle').set_value(date(2026, 10, 26)).run()
    assert not at.error
    at.button(key='studio_toggle_explorer').click().run()
    assert not at.exception
    assert at.session_state['studio_cycle'] == date(2026, 10, 26)
    at.selectbox(key='mobile_account_workspace').set_value(account[3]).run()
    assert not at.exception
    assert at.selectbox(key='account_workspace').value == account[3]


def test_manage_users_and_temporary_password_gate(account):
    identity, user, first, second, private, root, service = account
    at = app()
    login(at)
    at.button(key='studio_nav_Configurações').click().run()
    assert at.button(key='studio_nav_Cockpit')
    assert at.button(key='studio_page_users')
    assert not at.exception
    at.text_input(key='users_name').set_value('Nova pessoa')
    at.text_input(key='users_email').set_value('new@example.com')
    at.text_input(key='users_temporary_password').set_value('temporary-password-123')
    next(b for b in at.button if b.label == 'Adicionar ao workspace').click().run()
    assert not at.exception
    created = identity.get_user_by_email('new@example.com')
    assert created and created['must_change_password']
    at.button(key='studio_nav_Cockpit').click().run()
    assert at.button(key='studio_open_growth')
    at.button(key='studio_nav_Configurações').click().run()
    assert at.button(key='studio_page_users')
    at.button(key='account_logout').click().run()
    at.text_input(key='login_email').set_value('new@example.com')
    at.text_input(key='login_password').set_value('temporary-password-123')
    next(b for b in at.button if b.label == 'Entrar').click().run()
    assert not at.exception
    assert not any(b.key == 'studio_open_growth' for b in at.button)
    next(t for t in at.text_input if t.label == 'Senha atual').set_value('temporary-password-123')
    next(t for t in at.text_input if t.label == 'Nova senha').set_value('permanent-password-456')
    next(t for t in at.text_input if t.label == 'Confirme a nova senha').set_value('permanent-password-456')
    next(b for b in at.button if b.label == 'Salvar nova senha').click().run()
    assert not at.exception
    assert at.text_input(key='login_email')
    assert not identity.get_user(created['id'])['must_change_password']


def test_member_cannot_manage_users_even_with_forged_navigation(account):
    identity, user, first, *_ = account
    identity.set_member(first, user['id'], UserRole.MEMBER)
    at = app()
    login(at)
    assert not any(b.key == 'studio_nav_Configurações' for b in at.button)
    at.session_state['studio_section'] = 'Configurações'
    at.run()
    assert at.error
    assert not any(t.key == 'users_email' for t in at.text_input)


@pytest.mark.parametrize("revoke", ["membership", "disabled", "version", "expiry", "signature"])
def test_session_revalidated_before_rendering(account, revoke):
    identity, user, first, second, private, root, service = account
    at = app()
    login(at)
    if revoke == "membership":
        identity.remove_member(first, user["id"])
    elif revoke == "disabled":
        with identity.connection() as conn:
            conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user["id"],))
    elif revoke == "version":
        identity.revoke_tokens(user["id"])
    else:
        at.session_state["_auth_token"] = create_access_token(
            {"sub": user["id"], "workspace_id": first},
            expires_delta=timedelta(seconds=-1) if revoke == "expiry" else timedelta(hours=1),
            secret_key=KEY if revoke == "expiry" else KEY + "wrong",
        )
    at.session_state["growth_secret_draft"] = "private"
    at.run()
    assert not at.exception
    assert at.text_input(key="login_email")
    assert "_auth_token" not in at.session_state
    assert "growth_secret_draft" not in at.session_state


def test_logout_revokes_api_compatible_token_and_clears_state(account):
    identity, user, first, second, private, root, service = account
    at = app()
    login(at)
    token = at.session_state["_auth_token"]
    assert decode_access_token(token, secret_key=KEY)["sub"] == user["id"]
    at.session_state["dec_summary"] = "private"
    at.button(key="account_logout").click().run()
    assert not at.exception
    assert "dec_summary" not in at.session_state
    assert at.text_input(key="login_email")
    with pytest.raises(AuthenticationError):
        service.resolve(token)


def test_viewer_role_change_blocks_mutation_pages(account):
    identity, user, first, second, private, root, service = account
    at = app()
    login(at)
    identity.set_member(first, user["id"], UserRole.VIEWER)
    at.button(key="studio_nav_Experimentos").click().run()
    for page in ("baseline", "diagnosis", "backlog"):
        at.button(key=f"studio_page_{page}").click().run()
        assert not at.exception
        assert not any(b.label in {"Salvar Baseline Ativa", "Executar Diagnóstico Financeiro", "Nova hipótese"}
                       for b in at.button)
    at.button(key="studio_nav_Governança").click().run()
    assert not any(b.key == "ritual_finish" for b in at.button)
    at.button(key="studio_page_calibration").click().run()
    assert not any(b.label == "Salvar Novas Calibrações" for b in at.button)
    at.button(key="studio_page_history").click().run()
    assert not at.exception
    at.button(key="studio_nav_Experimentos").click().run()
    at.button(key="studio_page_report").click().run()
    assert not at.exception
    assert SQLiteGrowthRepository(str(workspace_db_path(root, first))).get_active_baseline() is None


def test_switch_requires_membership_and_does_not_extend_expiry(account):
    identity, user, first, second, private, root, service = account
    token = service.login(user["email"], PASSWORD)
    with pytest.raises(AuthenticationError):
        service.switch(token, private)
    switched = service.switch(token, second)
    assert decode_access_token(switched, secret_key=KEY)["exp"] <= decode_access_token(token, secret_key=KEY)["exp"]
    assert service.resolve(switched).tenant.workspace_id == second


def test_missing_key_fails_closed(account, monkeypatch):
    monkeypatch.setenv("CDMS_SECRET_KEY", "")
    at = app()
    assert at.error
    assert not account[5].exists()
    assert not any(b.label == "Entrar" for b in at.button)
