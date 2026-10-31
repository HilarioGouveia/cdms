"""Inspector contextual de evidências persistidas, sem alterar rascunhos."""
from datetime import date
import streamlit as st
from cgs.adapters.persistence.sqlite_cgs_fase2_repo import SQLiteCGSPhase2Repository
from cdms.adapters.persistence.sqlite_ingestion_repo import SQLiteIngestionRepository


def inspect_hypothesis(hypothesis_id):
    st.session_state['_evidence_selection']={
        'id':hypothesis_id,'workspace':st.session_state.get('_studio_upload_scope'),
        'cycle':st.session_state['studio_cycle'].isoformat()}
    st.session_state['studio_evidence']=True


def close_evidence():
    st.session_state['studio_evidence']=False


def evidence_context(growth,cycle,session=None):
    section=st.session_state.get('studio_section','Cockpit')
    page=st.session_state.get(f'studio_page_{section}')
    selected=None
    if section=='Governança' and page=='ritual':
        cycle=st.session_state.get('cycle_week_start',date.fromisoformat(cycle)).isoformat()
    if section=='Experimentos' and page in ('budget','ab_evaluation'):
        scope=session.tenant.workspace_id if session else st.session_state.get('studio_workspace','local')
        selected=st.session_state.get(f'finance_hypothesis_{scope}_{page}')
    elif section=='Experimentos' and page=='backlog':
        selection=st.session_state.get('_evidence_selection',{})
        if selection.get('workspace')==st.session_state.get('_studio_upload_scope') and selection.get('cycle')==cycle:
            selected=selection.get('id')
    elif section=='Experimentos' and page=='report':
        value=st.session_state.get('growth_selected_cycle',cycle)
        try:
            cycle=date.fromisoformat(str(value)).isoformat()
        except ValueError:
            pass
    hypothesis=growth.get_hypothesis_by_id(selected) if type(selected) is int else None
    if section=='Experimentos' and page in ('budget','ab_evaluation') and hypothesis and hypothesis.target_cycle_id not in (None,cycle):
        hypothesis=None
    if hypothesis and hypothesis.target_cycle_id:
        cycle=hypothesis.target_cycle_id
    return cycle,hypothesis


def render_evidence(core,growth,cycle,session=None):
    cycle,h=evidence_context(growth,cycle,session)
    with st.container(horizontal=True):
        st.subheader('Evidências do ciclo')
        st.button('Fechar evidências',icon=':material/close:',key='evidence_close',on_click=close_evidence,
                  help='Fechar sem alterar o conteúdo principal')
    st.caption(f"{session.workspace_name if session else st.session_state.get('studio_workspace','Local')} · {cycle}")
    if h:
        st.markdown(f'**Hipótese #{h.id}**')
        st.write(h.action_description)
        st.caption(f'{h.status.value} · {h.tested_variable.value} · ICE {h.ice_score}')
        st.write(f'Métrica: {h.target_metric_key} · Meta: {h.success_metric_target} {h.target_metric_unit}')
        finance=SQLiteCGSPhase2Repository(core.settings.DB_PATH)
        budget=finance.get_budget_by_hypothesis(h.id,cycle)
        st.divider()
        st.markdown('**Investimento desta hipótese**')
        if budget:
            st.write(f'Alocado: R$ {budget.allocated_reais:,.2f} · Gasto: R$ {budget.spent_reais:,.2f}')
            st.caption(f'Consumo: {budget.burn_rate_pct}% · Risco: {budget.risk_tier.value}')
            if budget.spent_amount_cents>budget.allocated_amount_cents:
                st.warning('Gasto acima da alocação.')
        else:
            st.caption('Sem orçamento registrado para esta hipótese neste ciclo.')
        result=finance.get_evaluation_by_hypothesis(h.id,cycle)
        st.markdown('**Última avaliação A/B**')
        if result:
            st.write(f'Probabilidade de ganho: {result.probability_to_beat_control}%')
            st.caption(f'Evento: {result.event_definition}')
            st.write(f'Controle: {result.control_conversions}/{result.control_sample} · Tratamento: {result.treatment_conversions}/{result.treatment_sample}')
            st.caption(f'Intervalo de 95% da diferença: [{result.difference_low_pp}, {result.difference_high_pp}] pontos percentuais · {result.evaluated_at:%d/%m/%Y %H:%M} UTC')
            st.caption('Amostra insuficiente nos grupos.' if result.verdict.value=='INCONCLUSIVE_INSUFFICIENT_SAMPLE'
                       else 'Estimativa Beta-Binomial. Revise o desenho e a amostra antes de decidir.')
        else:
            st.caption('Sem avaliação A/B para esta hipótese neste ciclo.')
        st.divider()
    else:
        st.caption('Contexto do ciclo. Em Experimentos, selecione uma hipótese para inspecionar orçamento e avaliação A/B.')
    audit=growth.get_funnel_audit(cycle)
    st.markdown('**Diagnóstico salvo**')
    if audit:
        st.write(audit.diagnosis_summary)
        st.caption(f'Cálculo v{audit.calculation_version} · Oportunidade estimada: R$ {audit.total_opportunity_reais:,.2f}')
    else:
        st.caption('Nenhum diagnóstico salvo para este ciclo.')
    ritual=core.repository.get_ritual_by_cycle(cycle)
    st.markdown('**Decisão do ciclo**')
    if ritual:
        st.write(ritual.decision.summary)
        st.caption(f'Cenário: {ritual.scenario.type.value} · Responsável: {ritual.decision.owner}')
    else:
        st.caption('Ritual ainda não concluído.')
    source_repo=SQLiteIngestionRepository(core.settings.DB_PATH)
    source=source_repo.ritual_source(cycle)
    st.markdown('**Origem das métricas**')
    if source:
        batch=source_repo.get_batch(source['job_id'])
        if batch:
            st.write(f"{'[SIMULADO] ' if batch.get('simulated') else ''}Meta Ads · {batch['account_id']}")
            st.caption(f"{batch.get('period_start',cycle)} a {batch.get('period_end','—')} · {batch.get('timezone_name','—')} · {batch.get('currency') or 'moeda não informada'}")
            st.caption(f"Revisão: {source['reviewed_at']} · Importação {source['job_id']}")
            st.caption('Importação revisada para o rascunho; os valores podem ter sido ajustados antes do fechamento.')
    else:
        st.caption('Sem importação Meta vinculada a este ciclo.')
    st.divider()
    st.caption(f'Regras v{core.settings.RULES_VERSION} · Dados salvos; alterações ainda no formulário não aparecem aqui.')
