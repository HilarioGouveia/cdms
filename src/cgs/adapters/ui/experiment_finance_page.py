"""Orçamento e avaliação A/B dentro de Experimentos."""
from dataclasses import asdict
from decimal import Decimal
import json
import streamlit as st
from cgs.adapters.persistence.sqlite_cgs_fase2_repo import SQLiteCGSPhase2Repository
from cgs.application.use_cases.experiment_finance import ExperimentFinance, money_cents
from cgs.domain.entities.budget_allocation import ExperimentRiskTier
from cdms.domain.entities.tenant import UserRole


def render_experiment_finance(core, growth, cycle, page, session=None):
    repo=SQLiteCGSPhase2Repository(core.settings.DB_PATH)
    service=ExperimentFinance(repo,growth,actor=session.tenant.user_id if session else 'local')
    writer=session is None or session.tenant.role != UserRole.VIEWER
    manager=session is None or session.tenant.role in (UserRole.OWNER,UserRole.ADMIN)
    scope=session.tenant.workspace_id if session else st.session_state.get('studio_workspace','local')
    st.caption(f'Ciclo {cycle} · Valores em BRL')
    if page == 'budget':
        budgets=repo.list_budgets_by_cycle(cycle)
        limit=repo.get_cycle_limit(cycle)/100
        allocated=sum(b.allocated_amount_cents for b in budgets)/100
        spent=sum(b.spent_amount_cents for b in budgets)/100
        cols=st.columns(3)
        for col,label,value in zip(cols,['Teto do ciclo','Comprometido','Gasto acumulado'],[limit,allocated,spent]):
            col.metric(label,f'R$ {value:,.2f}')
        if spent > allocated:
            st.warning('O gasto registrado excede o orçamento alocado. Revise os experimentos antes de investir mais.')
        st.caption(f'Saldo para alocar: R$ {limit-allocated:,.2f}')
        if budgets:
            st.dataframe([{'Hipótese':b.hypothesis_id,'Alocado (R$)':float(b.allocated_reais),
                'Gasto (R$)':float(b.spent_reais),'Consumo (%)':float(b.burn_rate_pct),'Risco':b.risk_tier.value} for b in budgets],hide_index=True)
        if manager:
            with st.container(border=True):
                ceiling=st.number_input('Teto do ciclo (R$)',min_value=0.01,value=float(limit),step=100.0,key=f'experiment_draft_{scope}_{cycle}_limit')
                save=st.button('Salvar teto',key=f'experiment_save_limit_{scope}_{cycle}')
            if save:
                try:
                    repo.set_cycle_limit(cycle,money_cents(ceiling),service.actor)
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
    hypotheses=[h for h in growth.list_hypotheses(limit=10000) if not h.target_cycle_id or h.target_cycle_id == cycle]
    if not hypotheses:
        st.info('Cadastre uma hipótese no Backlog para este ciclo antes de continuar.')
        return
    mapping={h.id:h for h in hypotheses}
    selected=st.selectbox('Hipótese do experimento',list(mapping),format_func=lambda uid:f'#{uid} · {mapping[uid].action_description}',
                           key=f'finance_hypothesis_{scope}_{page}')
    h=mapping[selected]
    key=f'{scope}_{page}_{cycle}_{selected}'
    def draft(name):
        return f'experiment_draft_{key}_{name}'
    st.caption(f'Métrica da hipótese: {h.target_metric_key} · Estado: {h.status.value}')
    if page == 'budget':
        budget=repo.get_budget_by_hypothesis(selected,cycle)
        if writer:
            with st.container(border=True):
                amount=st.number_input('Valor alocado (R$)',min_value=0.01,value=float(budget.allocated_reais) if budget else 100.0,key=draft('amount'))
                risks=list(ExperimentRiskTier)
                risk=st.selectbox('Risco',risks,index=risks.index(budget.risk_tier) if budget else 0,format_func=lambda r:r.value,key=draft('risk'))
                cpa=st.number_input('CPA máximo (R$; zero significa não definido)',min_value=0.0,value=budget.max_cpa_target_cents/100 if budget and budget.max_cpa_target_cents else 0.0,key=draft('cpa'))
                save=st.button('Salvar alocação',key='experiment_allocate_'+key,disabled=h.status.value in {'COMPLETED','DISCARDED','CANCELLED','ARCHIVED'})
            if save:
                try:
                    service.allocate(selected,cycle,amount,risk,cpa if cpa else None)
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
            if budget:
                with st.container(border=True):
                    spend=st.number_input('Gasto acumulado real (R$)',min_value=0.0,value=float(budget.spent_reais),key=draft('spend'))
                    save=st.button('Registrar gasto',key='experiment_spend_'+key)
                if save:
                    try:
                        service.spend(selected,cycle,spend)
                        st.rerun()
                    except ValueError as error:
                        st.error(str(error))
        else:
            st.info('Seu perfil permite somente consulta.')
        with st.expander('Histórico do orçamento'):
            events=[]
            for row in repo.budget_history(cycle):
                data=json.loads(row['payload'])
                if 'limit_cents' in data:
                    detail=f"Teto definido: R$ {data['limit_cents']/100:,.2f}"
                elif 'spent_cents' in data:
                    detail=f"Gasto acumulado: R$ {data['spent_cents']/100:,.2f}"
                else:
                    detail=f"Alocação: R$ {data['allocated_cents']/100:,.2f} · risco {data['risk']}"
                events.append({'Data':row['created_at'],'Hipótese':str(row['hypothesis_id'] or '—'),
                               'Alteração':detail,'Responsável':row['actor'] or 'Operador'})
            st.dataframe(events,hide_index=True)
        return
    st.info('Avaliação de conversão binária: informe unidades independentes expostas e unidades que converteram. Use a mesma métrica e janela nos dois grupos; o resultado não garante causalidade sem um desenho de teste adequado.')
    if writer:
        with st.container(border=True):
            definition=st.text_input('Evento de sucesso e unidade de exposição',value='Compra por visitante único',max_chars=500,key=draft('event'))
            cols=st.columns(2)
            with cols[0]:
                control_sample=st.number_input('Amostra de controle',min_value=1,value=1000,step=1,key=draft('control_sample'))
                control_conversions=st.number_input('Conversões de controle',min_value=0,value=20,step=1,key=draft('control_conversions'))
            with cols[1]:
                treatment_sample=st.number_input('Amostra de tratamento',min_value=1,value=1000,step=1,key=draft('treatment_sample'))
                treatment_conversions=st.number_input('Conversões de tratamento',min_value=0,value=30,step=1,key=draft('treatment_conversions'))
            minimum=st.number_input('Amostra mínima por grupo',min_value=1,value=100,step=1,key=draft('minimum'))
            reviewed=st.checkbox('Conferi a mesma métrica, janela e separação dos grupos',key=draft('reviewed'))
            save=st.button('Avaliar e salvar',key='experiment_evaluate_'+key)
        if save:
            try:
                if not reviewed:
                    raise ValueError('Revise os grupos antes de avaliar.')
                service.evaluate(selected,cycle,control_conversions=control_conversions,control_sample=control_sample,
                    treatment_conversions=treatment_conversions,treatment_sample=treatment_sample,sample_minimum=minimum,
                    event_definition=definition)
                st.success('Avaliação registrada no histórico.')
            except ValueError as error:
                st.error(str(error))
    history=repo.evaluation_history(selected,cycle)
    if history:
        result=history[0]
        st.caption(f'Evento avaliado: {result.event_definition} · Janela: ciclo semanal {cycle}')
        cols=st.columns(3)
        cols[0].metric('Probabilidade de ganho',f'{result.probability_to_beat_control}%')
        cols[1].metric('Lift observado',f'{result.lift_pct}%' if result.lift_pct is not None else 'Indefinido')
        cols[2].metric('Cobertura da amostra mínima',f'{result.sample_adequacy_ratio*100:.0f}%')
        labels={'STATISTICALLY_SIGNIFICANT':'Evidência de ganho no limiar de 95%',
                'INCONCLUSIVE_INSUFFICIENT_SAMPLE':'Amostra insuficiente: continue coletando dados',
                'EARLY_STOPPED_HIGH_LOSS':'Evidência de perda: considere interromper o teste',
                'NO_EFFECT_DETECTED':'Sem evidência suficiente de ganho: resultado inconclusivo'}
        st.write(labels[result.verdict.value])
        st.caption(f'Diferença entre taxas: intervalo de credibilidade de 95% [{result.difference_low_pp}, {result.difference_high_pp}] pontos percentuais. Prior Beta(1,1), 30.000 simulações reproduzíveis; aproximação Monte Carlo. Nenhuma campanha é pausada automaticamente.')
        with st.expander('Histórico das avaliações'):
            st.dataframe([{'Data':r.evaluated_at.isoformat(),'Controle':f'{r.control_conversions}/{r.control_sample}',
                'Tratamento':f'{r.treatment_conversions}/{r.treatment_sample}','Probabilidade (%)':float(r.probability_to_beat_control),
                'Resultado':labels[r.verdict.value]} for r in history],hide_index=True)
