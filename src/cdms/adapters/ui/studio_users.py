"""Cadastro e gestão de membros do workspace autenticado."""
import streamlit as st

from cdms.application.services.workspace_users import WorkspaceUsers
from cdms.domain.entities.tenant import UserRole


def password_form(service, session, *, required=False):
    from cdms.adapters.ui.studio_auth import reset_session
    st.subheader('Definir nova senha' if required else 'Trocar minha senha')
    if required:
        st.info('Sua senha é temporária. Defina uma nova senha para acessar o workspace.')
    with st.form('account_password', clear_on_submit=True):
        current = st.text_input('Senha atual', type='password', max_chars=1024)
        new = st.text_input('Nova senha', type='password', max_chars=1024,
                            help='Use pelo menos 12 caracteres.')
        confirm = st.text_input('Confirme a nova senha', type='password', max_chars=1024)
        submitted = st.form_submit_button('Salvar nova senha')
    if submitted:
        try:
            if new != confirm:
                raise ValueError('As senhas não coincidem.')
            WorkspaceUsers(service.identity).change_password(session.tenant.user_id, current, new)
        except ValueError as error:
            st.error(str(error))
        else:
            reset_session(notice='Senha alterada. Entre novamente com a nova senha.')
            st.rerun()


def render_users(service, session):
    st.title('Usuários do workspace')
    st.caption(session.workspace_name)
    users = WorkspaceUsers(service.identity)
    try:
        members = users.members(session.tenant)
    except ValueError as error:
        st.error(str(error))
        return
    notice = st.session_state.pop('_users_notice', None)
    if notice:
        st.success(notice)
    st.dataframe([{'Nome': m['full_name'], 'Email': m['email'], 'Perfil': m['role']} for m in members],
                 hide_index=True, width='stretch')
    roles = [UserRole.MEMBER, UserRole.VIEWER]
    if session.tenant.role == UserRole.OWNER:
        roles.insert(0, UserRole.ADMIN)
    st.subheader('Adicionar usuário')
    st.caption('Contas novas recebem senha temporária e precisam trocá-la no primeiro acesso. Contas já cadastradas mantêm nome e senha atuais.')
    with st.form('users_add', clear_on_submit=True):
        name = st.text_input('Nome completo', max_chars=200, key='users_name')
        email = st.text_input('Email do usuário', max_chars=320, key='users_email')
        role = st.selectbox('Perfil de acesso', roles, format_func=lambda r: r.value, key='users_new_role')
        password = st.text_input('Senha temporária para conta nova', type='password', max_chars=1024, key='users_temporary_password')
        st.caption('ADMIN gerencia membros; MEMBER opera os fluxos; VIEWER tem acesso somente de leitura. Entregue a senha por um canal privado.')
        add = st.form_submit_button('Adicionar ao workspace')
    if add:
        try:
            created = users.add(session.tenant, email, name, role, password)
        except ValueError as error:
            st.error(str(error))
        else:
            st.session_state['_users_notice'] = ('Usuário cadastrado. Entregue a senha temporária por um canal privado.' if created
                                                  else 'Conta existente adicionada. A pessoa pode entrar com sua senha atual.')
            st.rerun()
    editable = {m['id']: m for m in members if m['role'] != 'OWNER' and m['id'] != session.tenant.user_id
                and (session.tenant.role == UserRole.OWNER or m['role'] != 'ADMIN')}
    if not editable:
        return
    st.subheader('Gerenciar acesso')
    selected = st.selectbox('Usuário', list(editable),
                            format_func=lambda uid: f"{editable[uid]['full_name']} · {editable[uid]['email']}", key='users_selected')
    member = editable[selected]
    # Key by identity to avoid carrying a previous member's chosen role or confirmation.
    with st.form(f'users_manage_{selected}', clear_on_submit=True):
        role = st.selectbox('Novo perfil', roles, index=roles.index(UserRole(member['role'])), format_func=lambda r: r.value)
        action = st.selectbox('Ação', ['Alterar perfil', 'Remover do workspace', 'Redefinir senha temporária'])
        temporary = st.text_input('Nova senha temporária', type='password', max_chars=1024)
        confirmed = st.checkbox('Confirmo a alteração para este usuário')
        submit = st.form_submit_button('Aplicar alteração')
    if submit:
        try:
            if not confirmed:
                raise ValueError('Confirme a alteração antes de continuar.')
            if action == 'Alterar perfil':
                users.set_role(session.tenant, selected, role)
            elif action == 'Remover do workspace':
                users.remove(session.tenant, selected)
            else:
                users.reset_password(session.tenant, selected, temporary)
        except ValueError as error:
            st.error(str(error))
        else:
            st.session_state['_users_notice'] = 'Alteração concluída.'
            st.rerun()
