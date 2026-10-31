"""Conexões no painel de Configurações e importações revisadas no Cockpit."""
from datetime import date
import os
import streamlit as st
from cdms.adapters.persistence.sqlite_ingestion_repo import SQLiteIngestionRepository
from cdms.application.services.platform_ingestion import PlatformIngestion
from cdms.application.ports.platform_connector import PlatformError
from cdms.config.credential_vault import CredentialVault
from cdms.domain.entities.tenant import UserRole
from cdms.domain.services.canonical_metrics import CANONICAL_DEFINITIONS


def integration_service(core,session):
    if session is None and st.session_state.get('studio_workspace')=='CDMS Demo':
        from cdms.application.demo_ingestion import DemoPlatformIngestion
        from cdms.config.container import get_container
        return DemoPlatformIngestion(core.settings.DB_PATH,get_container().settings.DATA_DIR/'demo')
    from cdms.adapters.ui.studio_auth import auth_service
    from cdms.adapters.tasks.ingestion_runtime import meta_connector_factory,dispatch_job
    return PlatformIngestion(SQLiteIngestionRepository(core.settings.DB_PATH),auth_service().identity,session.tenant,
                             meta_connector_factory,CredentialVault,dispatch_job)


def render_integrations(core,session):
    if session is None and st.session_state.get('studio_workspace')=='CDMS Demo':
        service=integration_service(core,session)
        st.info('SIMULAÇÃO OFFLINE · Conta fictícia. Nenhuma credencial, chamada à Meta ou fila Redis é utilizada.')
        rows=service.repo.list_connections()
        if rows:
            st.dataframe([{'Conta fictícia':r['account_id'],'Moeda':r['currency'],'Fuso':r['timezone_name'],
                           'Modo':'Simulado · sem conexão externa'} for r in rows],hide_index=True)
            st.caption('Abra o Cockpit no ciclo de prática do Demo para simular coleta, falha, conclusão e importação revisada.')
        else:
            st.info('Carregue o pacote em Demonstração para preparar os exemplos.')
        return
    if not session or session.tenant.role not in (UserRole.OWNER,UserRole.ADMIN):
        st.info('Conexões são gerenciadas pelo proprietário ou administrador.')
        return
    service=integration_service(core,session)
    st.info('Meta Ads: leitura semanal. Cadastre um token com acesso à conta e aos Insights. Não há consentimento OAuth ou renovação automática nesta versão.')
    if not os.getenv('CDMS_CREDENTIAL_KEY'):
        st.warning('O servidor precisa de CDMS_CREDENTIAL_KEY para cifrar credenciais. Configure a chave no painel e no worker antes de conectar.')
    with st.form('meta_connect',clear_on_submit=True):
        account=st.text_input('ID da conta Meta',placeholder='act_123456789',max_chars=100)
        token=st.text_input('Token de acesso Meta',type='password',max_chars=4096)
        secret=st.text_input('App secret (opcional)',type='password',max_chars=4096)
        version=st.text_input('Versão da API',value=os.getenv('CDMS_META_API_VERSION','v26.0'),max_chars=10)
        event=st.text_input('Evento de conversão',value='offsite_conversion.fb_pixel_purchase',max_chars=200)
        automatic=st.checkbox('Sincronizar automaticamente a última semana encerrada')
        confirmed=st.checkbox('Autorizo a validação da conta e o armazenamento cifrado da credencial')
        save=st.form_submit_button('Validar e salvar conexão')
    if save:
        try:
            if not confirmed:
                raise ValueError('Confirme a autorização para conectar a conta.')
            with st.spinner('Validando acesso à conta Meta…'):
                service.connect(account,token,version,event,secret or None,automatic)
            st.success('Conexão validada e salva. Consulte as importações no Cockpit.')
        except PlatformError as error:
            st.error(f'A Meta não confirmou o acesso: {error.code}. Revise a credencial e as permissões.')
        except (RuntimeError,ValueError) as error:
            st.error(str(error))
    connections=service.repo.list_connections()
    if connections:
        st.dataframe([{'Conta':c['account_id'],'Moeda':c['currency'],'Fuso':c['timezone_name'],
            'Ativa':bool(c['is_active']),'Automática':bool(c['automatic_sync']),'Última coleta':c['last_synced_at']} for c in connections],hide_index=True)
        active={c['id']:c for c in connections if c['is_active']}
        if active:
            selected=st.selectbox('Conexão para desativar',list(active),format_func=lambda uid:active[uid]['account_id'])
            confirmed=st.checkbox('Confirmo a desativação local desta conexão')
            if st.button('Desativar conexão',disabled=not confirmed):
                service.deactivate(selected)
                st.rerun()
    st.caption('Recadastrar uma conta atualiza sua credencial e revisão. Desativar localmente não revoga o token na Meta. Redis, worker e beat precisam estar em execução para processar e agendar coletas.')


def apply_ritual_import(result):
    from cdms.adapters.ui.ritual_wizard import sync_cycle
    cycle=result['cycle_id']
    sync_cycle(cycle)
    st.session_state['cycle_week_start']=date.fromisoformat(cycle)
    for definition in CANONICAL_DEFINITIONS:
        key=definition.key
        value=result['metrics'].get(key)
        st.session_state[f'avail_{key}']=value is not None
        if value is not None:
            st.session_state[f'val_{key}']=int(value) if key in ('reach','conversions') else float(value)
        else:
            st.session_state[f'reason_{key}']='OUTRO'
            st.session_state[f'custom_reason_{key}']=result.get('unavailability_reasons',{}).get(key,'NOT_SUPPORTED')
    st.session_state['_ritual_step']=2
    st.session_state['ritual_step_selector']=2
    st.session_state['studio_section']='Governança'
    st.session_state['studio_page_Governança']='ritual'
    st.session_state['studio_explorer']=True


def render_imports(core,session,cycle):
    demo=session is None and st.session_state.get('studio_workspace')=='CDMS Demo'
    if not session and not demo:
        return
    st.subheader('Importações Meta Ads')
    service=integration_service(core,session)
    connections={c['id']:c for c in service.repo.list_connections()}
    active={uid:c for uid,c in connections.items() if c['is_active']}
    writer=demo or session.tenant.role != UserRole.VIEWER
    if not connections:
        st.caption('Carregue o pacote em Demonstração para preparar as contas fictícias.' if demo else
                   'Nenhuma conta conectada. O administrador pode configurar Meta Ads em Configurações → Integrações.')
        return
    if demo:
        st.info('SIMULAÇÃO OFFLINE · Os resultados são fictícios. Nenhum acesso à Meta, credencial ou Redis é necessário. O ciclo de prática pode usar a semana atual.')
    else:
        st.caption('Somente semanas encerradas no fuso da conta. O agendamento precisa de Redis, worker e beat; a existência de uma conexão não confirma que esses processos estão ativos.')
    if writer and active:
        with st.form('meta_sync'):
            selected=st.selectbox('Conta para sincronizar',list(active),format_func=lambda uid:active[uid]['account_id'])
            st.write(f'Semana selecionada: {cycle}')
            action=st.selectbox('Tipo de solicitação',['Coleta','Repetir falha','Nova versão dos dados'])
            submit=st.form_submit_button('Solicitar sincronização')
        if submit:
            try:
                _,status=service.enqueue(selected,cycle,retry_failed=action=='Repetir falha',force_refresh=action=='Nova versão dos dados')
                if status=='DEFERRED':
                    st.warning('Solicitação salva. O envio à fila está pendente; o dispatcher tentará novamente.')
                elif status=='SIMULATED':
                    st.success('Coleta simulada concluída localmente. Revise o resultado abaixo.')
                else:
                    st.success('Solicitação registrada. Atualize a lista para acompanhar o processamento.')
            except ValueError as error:
                st.error(str(error))
    st.button('Atualizar importações',key='meta_refresh')
    jobs=[j for j in service.repo.list_jobs() if j['cycle_id']==cycle]
    if not jobs:
        st.caption('Nenhuma sincronização para o ciclo selecionado.')
        return
    st.dataframe([{'Conta':connections.get(j['connection_id'],{}).get('account_id','—'), 'Estado':j['status'],
        'Tentativas':j['attempts'],'Erro':j['error_code'],'Versão':j['generation'],'Solicitado':j['created_at']} for j in jobs],hide_index=True)
    if demo:
        pending={j['id']:j for j in jobs if j['status']=='PENDING'}
        if pending:
            chosen=st.selectbox('Coleta simulada pendente',list(pending),format_func=lambda uid:f"Versão {pending[uid]['generation']}")
            if st.button('Concluir coleta simulada',key='demo_complete_import'):
                service.complete_pending(chosen)
                st.rerun()
    completed={j['id']:j for j in jobs if j['status']=='SUCCESS'}
    if not completed:
        return
    selected=st.selectbox('Resultado para revisar',list(completed),format_func=lambda uid:
        f"{connections[completed[uid]['connection_id']]['account_id']} · versão {completed[uid]['generation']} · {completed[uid]['finished_at']}",key='meta_result')
    result=service.repo.get_batch(selected)
    if not result:
        st.error('Resultado indisponível.')
        return
    st.caption(f"Conta {result['account_id']} · {result.get('period_start',cycle)} a {result.get('period_end','—')} · Fuso {result.get('timezone_name','—')} · Moeda {result.get('currency') or 'não informada'}")
    st.dataframe([{'Métrica':d.name,'Valor':str(result['metrics'].get(d.key)) if result['metrics'].get(d.key) is not None else 'Indisponível',
                   'Unidade':d.unit,'Motivo':result.get('unavailability_reasons',{}).get(d.key,'—')}
                  for d in CANONICAL_DEFINITIONS],hide_index=True)
    if result['metrics'].get('spend') is not None:
        st.write(f"Gasto da conta no período: {result['metrics']['spend']} {result.get('currency') or '(moeda não informada)'}")
    st.caption(f"Evento: {result.get('conversion_action_type','—')} · Definição de clique: {result.get('click_definition','—')} · Atribuição: {result.get('attribution','—')}")
    st.caption('Meta Ads não fornece retenção média neste adaptador. Valores indisponíveis serão preservados como indisponíveis; moeda e gasto não são convertidos nem atribuídos automaticamente a uma hipótese.')
    if writer:
        confirmed=st.checkbox('Revisei período, origem e métricas; quero preencher o rascunho do ritual',key=f'meta_review_{selected}')
        closed=core.repository.get_ritual_by_cycle(cycle) is not None
        if closed:
            st.info('O ritual deste ciclo já foi encerrado. A importação não irá sobrescrevê-lo.')
        if st.button('Usar no rascunho do ritual',disabled=not confirmed or closed,key='meta_apply'):
            try:
                imported=service.prepare_ritual(selected,core.repository)
                apply_ritual_import(imported)
                st.rerun()
            except ValueError as error:
                st.error(str(error))
