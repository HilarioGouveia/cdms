"""Sessão individual do Studio usando identidade e JWT existentes da suíte."""
import os
from dataclasses import replace

import streamlit as st


def studio_mode():
    mode = os.getenv("CDMS_STUDIO_MODE", "authenticated").strip().lower()
    if mode not in {"authenticated", "local"}:
        raise ValueError("CDMS_STUDIO_MODE deve ser authenticated ou local.")
    return mode


@st.cache_resource
def dummy_password_hash():
    from cdms.config.security import get_password_hash
    return get_password_hash("CDMS timing placeholder for unknown accounts")


def auth_service():
    from cdms.adapters.persistence.sqlite_identity_repo import SQLiteIdentityRepository
    from cdms.application.services.workspace_auth import WorkspaceAuth
    from cdms.config.security import get_secret_key
    from cdms.config.workspace_storage import identity_db_path
    key = os.getenv("CDMS_SECRET_KEY")
    if key is None:
        try:
            key = st.secrets.get("CDMS_SECRET_KEY", "")
        except FileNotFoundError:
            key = ""
    key = get_secret_key(key)
    return WorkspaceAuth(SQLiteIdentityRepository(identity_db_path()), key, dummy_password_hash())


def reset_session(token=None, notice=None):
    # Do not retain forms, uploads, repositories, or cached drafts across identities/workspaces.
    for key in list(st.session_state):
        del st.session_state[key]
    if token:
        st.session_state["_auth_token"] = token
    if notice:
        st.session_state["_auth_notice"] = notice


def require_session():
    """Stop before opening operational databases unless the session is valid."""
    try:
        mode = studio_mode()
    except ValueError as error:
        st.error(str(error))
        st.stop()
    if mode == "local":
        return None
    try:
        service = auth_service()
    except (RuntimeError, ImportError):
        st.title("Entrar no CDMS Studio")
        st.error("A configuração de autenticação do painel precisa ser concluída.")
        st.caption("Configure CDMS_SECRET_KEY no servidor do Streamlit e instale os extras de API. Consulte docs/etapa-13-login-studio.md.")
        st.stop()
    from cdms.application.services.workspace_auth import AuthenticationError
    token = st.session_state.get("_auth_token")
    if token:
        try:
            session = service.resolve(token)
            st.session_state['_theme_profile'] = service.identity.get_user(session.tenant.user_id)['theme_preference']
            if session.must_change_password:
                from cdms.adapters.ui.studio_users import password_form
                password_form(service, session, required=True)
                if st.button('Sair', key='temporary_logout'):
                    service.logout(token)
                    reset_session()
                    st.rerun()
                st.stop()
            st.session_state["studio_workspace"] = session.workspace_name
            return session
        except AuthenticationError as error:
            reset_session(notice=str(error))
            st.rerun()
    with st.container(key='studio_login_page', horizontal_alignment='center'):
        with st.container(key='studio_login_card', width=440, border=True):
            st.markdown(':material/space_dashboard: **CDMS STUDIO**')
            st.title('Bem-vindo de volta')
            st.write('Entre para acessar seu workspace e acompanhar suas decisões.')
            notice = st.session_state.pop('_auth_notice', None)
            if notice:
                if st.session_state.pop('_auth_notice_error', False):
                    st.error(notice)
                else:
                    st.info(notice)
            with st.form('studio_login', clear_on_submit=True, border=False):
                email = st.text_input('Email', key='login_email', max_chars=320,
                                      placeholder='voce@empresa.com')
                password = st.text_input('Senha', type='password', key='login_password', max_chars=1024,
                                         placeholder='Digite sua senha')
                submitted = st.form_submit_button('Entrar', type='primary', width='stretch')
            st.divider()
            st.caption('Precisa de acesso ou esqueceu sua senha? Fale com o administrador do seu workspace.')
        st.caption('CDMS · Evidência, hipótese e decisão.')
    if submitted:
        try:
            token = service.login(email, password)
        except AuthenticationError as error:
            reset_session(notice=str(error))
            st.session_state["_auth_notice_error"] = True
            st.rerun()
        else:
            reset_session(token=token)
            st.rerun()
    st.stop()


def session_container(session):
    from cdms.config.container import Container
    from cdms.config.settings import settings
    from cdms.config.workspace_storage import workspace_data_dir, workspace_db_path
    path = workspace_db_path(workspace_data_dir(), session.tenant.workspace_id)
    st.session_state["_studio_upload_scope"] = session.tenant.workspace_id
    return Container(app_settings=replace(settings, DATA_DIR=path.parent, DB_PATH=path))


def render_account(session):
    """Render before operational controls so switching/logout cannot submit old drafts."""
    from cdms.application.services.workspace_auth import AuthenticationError
    with st.popover("Minha conta", icon=":material/account_circle:"):
        with st.container():
            st.write(f"{session.full_name} · {session.tenant.role.value}")
            st.write(session.email)
            profiles = {'dark-premium': 'Escuro', 'soft-light': 'Claro'}
            saved = st.session_state.get('_theme_profile', 'dark-premium')
            selected_theme = st.selectbox('Tema', list(profiles), index=list(profiles).index(saved),
                                           format_func=profiles.get, key='account_theme')
            if selected_theme != saved:
                auth_service().identity.set_theme_preference(session.tenant.user_id, selected_theme)
                st.session_state['_theme_profile'] = selected_theme
                st.rerun()
            if st.button('Trocar minha senha', key='account_password_page'):
                st.session_state['_account_page'] = 'password'
                st.rerun()
            if st.button("Sair", key="account_logout", icon=":material/logout:"):
                try:
                    auth_service().logout(st.session_state["_auth_token"])
                except AuthenticationError:
                    pass
                reset_session(notice="Você saiu da conta.")
                st.rerun()


def render_workspace_selector(session, key='account_workspace'):
    from cdms.application.services.workspace_auth import AuthenticationError
    names = {w['id']: w['name'] for w in session.workspaces}
    selected = st.selectbox('Workspace', list(names), format_func=names.get,
                            index=list(names).index(session.tenant.workspace_id), key=key)
    if selected != session.tenant.workspace_id:
        try:
            token = auth_service().switch(st.session_state['_auth_token'], selected)
        except AuthenticationError as error:
            reset_session(notice=str(error))
        else:
            reset_session(token=token)
        st.rerun()
