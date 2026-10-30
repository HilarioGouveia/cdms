"""Backlog contextual: criação recolhível, propostas e resultados auditados."""
from datetime import date, timedelta
from decimal import Decimal

import streamlit as st
from cdms.adapters.ui.components.identity import render_tag

from cgs.application.use_cases.manage_hypotheses import ManageHypothesesUseCase
from cgs.application.use_cases.prepare_cdms_proposal import PrepareCDMSProposalUseCase
from cgs.domain.entities.hypothesis import HypothesisStatus, MetricDirection, VariableType


NEW_FIELDS = (
    "growth_action", "growth_var_type", "growth_metric_key", "growth_metric_unit",
    "growth_direction", "growth_base_val", "growth_target_val", "growth_floor_val",
    "growth_impact", "growth_conf", "growth_ease",
)
OUTCOME_LABELS = {
    "ACHIEVED": "Meta atingida", "PARTIAL": "Meta parcialmente atingida",
    "NOT_ACHIEVED": "Meta não atingida", "INCONCLUSIVE": "Inconclusivo",
}


def toggle_new():
    st.session_state["growth_show_new_hypothesis"] = not st.session_state.get("growth_show_new_hypothesis", False)


def comparison(hypothesis):
    return "≥" if hypothesis.metric_direction == MetricDirection.HIGHER_IS_BETTER else "≤"


def render_new_hypothesis(use_case):
    with st.expander("Nova hipótese", expanded=True):
        action = st.text_input("Ação Prática", placeholder="Ex: Adicionar CTA verbal nos primeiros 5s", key="growth_action")
        var_col, metric_col = st.columns(2)
        var_type = var_col.selectbox("Variável Única", [item.value for item in VariableType], key="growth_var_type")
        metric_key = metric_col.text_input("Chave da Métrica", value="ctr_pct", key="growth_metric_key")
        unit_col, direction_col = st.columns(2)
        unit = unit_col.text_input("Unidade", value="%", key="growth_metric_unit")
        direction = direction_col.selectbox("Direção", [item.value for item in MetricDirection], key="growth_direction")
        base_col, target_col, floor_col = st.columns(3)
        base = base_col.number_input("Referência Atual", value=3.0, step=0.1, key="growth_base_val")
        target = target_col.number_input("Meta de Sucesso", value=4.5, step=0.1, key="growth_target_val")
        floor = floor_col.number_input("Piso/Teto Invalidação", value=2.5, step=0.1, key="growth_floor_val")
        impact_col, conf_col, ease_col = st.columns(3)
        impact = impact_col.slider("Impacto (1-10)", 1, 10, 7, key="growth_impact")
        confidence = conf_col.slider("Confiança (1-10)", 1, 10, 7, key="growth_conf")
        ease = ease_col.slider("Facilidade (1-10)", 1, 10, 8, key="growth_ease")
        if st.button("Adicionar ao Backlog", type="primary"):
            try:
                hypothesis = use_case.create_hypothesis(
                    action_description=action, tested_variable=VariableType(var_type),
                    target_metric_key=metric_key, target_metric_unit=unit,
                    metric_direction=MetricDirection(direction),
                    baseline_reference_value=Decimal(str(base)), success_metric_target=Decimal(str(target)),
                    invalidation_floor=Decimal(str(floor)), expected_impact_description=f"Destravar {metric_key}",
                    impact_score=impact, confidence_score=confidence, ease_score=ease,
                )
                st.session_state["growth_backlog_notice"] = f"Hipótese #{hypothesis.id} adicionada ao backlog."
                st.session_state["growth_show_new_hypothesis"] = False
                st.session_state["growth_reset_new_hypothesis"] = True
                st.rerun()
            except Exception as error:
                st.error(f"Não foi possível criar a hipótese: {error}")


def render_details(hypothesis):
    with st.expander("Detalhes da hipótese"):
        st.write(f"**Referência atual:** {hypothesis.baseline_reference_value}{hypothesis.target_metric_unit}")
        st.write(f"**Limite de invalidação:** {hypothesis.invalidation_floor}{hypothesis.target_metric_unit}")
        st.write(f"**ICE:** Impacto {hypothesis.impact_score} · Confiança {hypothesis.confidence_score} · Facilidade {hypothesis.ease_score}")
        st.caption(f"Janela de teste · {hypothesis.window_days} dias")
        st.write(hypothesis.expected_impact_description)


def render_heading(hypothesis):
    st.markdown(f"**{hypothesis.action_description}**")
    with st.container(horizontal=True):
        tone = {"HOOK": "violet", "OFFER": "amber", "CTA": "cobalt"}.get(hypothesis.tested_variable.value, "neutral")
        render_tag(hypothesis.tested_variable.value.replace("_", " "), tone)
        render_tag(f"ICE {hypothesis.ice_score}")
    st.caption(f"Hipótese #{hypothesis.id}")
    st.write(f"**Meta:** {hypothesis.target_metric_key} {comparison(hypothesis)} {hypothesis.success_metric_target}{hypothesis.target_metric_unit}")


def render_proposal(hypothesis, proposal_case, today):
    with st.popover("Preparar para ritual", icon=":material/playlist_add:"):
        st.caption("Preparar reserva a hipótese para um ciclo. O teste começa quando o ritual for concluído.")
        default_cycle = today - timedelta(days=today.weekday())
        if hypothesis.target_cycle_id:
            try:
                default_cycle = date.fromisoformat(hypothesis.target_cycle_id)
            except ValueError:
                pass
        key = f"growth_proposal_cycle_{hypothesis.id}"
        st.session_state.setdefault(key, default_cycle)
        target_cycle = st.date_input("Ciclo alvo da proposta CDMS", key=key)
        if st.button("Confirmar proposta", key=f"btn_prop_{hypothesis.id}", type="primary"):
            try:
                result = proposal_case.execute(hypothesis_id=hypothesis.id, target_cycle_start=target_cycle)
                st.session_state["growth_backlog_notice"] = (
                    f"Proposta #{hypothesis.id} preparada para {result.target_cycle_id}. Conclua o ritual para iniciar o teste."
                )
                st.rerun()
            except Exception as error:
                st.error(f"Não foi possível preparar a proposta: {error}")


def render_pending(use_case, proposal_case, today):
    st.button("Fechar formulário" if st.session_state.get("growth_show_new_hypothesis") else "Nova hipótese",
              icon=":material/add:", key="backlog_new_hypothesis", on_click=toggle_new)
    if st.session_state.get("growth_show_new_hypothesis"):
        render_new_hypothesis(use_case)
    backlog = use_case.get_ranked_backlog(limit=500)
    if not backlog:
        st.info("Nenhuma hipótese pendente. Crie uma nova hipótese para começar.")
        return
    var_col, cycle_col = st.columns(2)
    variable = var_col.selectbox("Filtrar por variável", [None, *[item.value for item in VariableType]],
                                 format_func=lambda value: value or "Todas as variáveis", key="growth_backlog_variable")
    cycles = [None, "unassigned", *sorted({item.target_cycle_id for item in backlog if item.target_cycle_id}, reverse=True)]
    if st.session_state.get("growth_backlog_cycle") not in cycles:
        st.session_state["growth_backlog_cycle"] = None
    cycle = cycle_col.selectbox("Filtrar por ciclo", cycles,
                                format_func=lambda value: "Todos os ciclos" if value is None else "Sem ciclo reservado" if value == "unassigned" else value,
                                key="growth_backlog_cycle")
    filtered = [item for item in backlog if (variable is None or item.tested_variable.value == variable)
                and (cycle is None or (cycle == "unassigned" and not item.target_cycle_id) or item.target_cycle_id == cycle)]
    st.caption(f"{len(filtered)} hipótese(s) · ordem decrescente de ICE")
    if not filtered:
        st.info("Nenhuma hipótese corresponde aos filtros selecionados.")
    for hypothesis in filtered:
        with st.container(border=True, key=f"growth_hypothesis_{hypothesis.id}"):
            render_heading(hypothesis)
            if hypothesis.target_cycle_id:
                st.caption(f"Proposta preparada · ciclo {hypothesis.target_cycle_id} · aguarda conclusão do ritual")
            else:
                st.caption("Pendente · sem ciclo reservado")
            render_details(hypothesis)
            with st.container(horizontal=True):
                render_proposal(hypothesis, proposal_case, today)
                if st.button("Descartar", key=f"btn_disc_pend_{hypothesis.id}"):
                    try:
                        use_case.discard_hypothesis(hypothesis.id)
                        st.session_state["growth_backlog_notice"] = f"Hipótese #{hypothesis.id} descartada."
                        st.rerun()
                    except Exception as error:
                        st.error(str(error))


def render_active(use_case, core):
    hypotheses = use_case.list_by_status(HypothesisStatus.ACTIVE, limit=500)
    if not hypotheses:
        st.info("Nenhum experimento em teste no momento.")
    for hypothesis in hypotheses:
        with st.container(border=True, key=f"growth_hypothesis_{hypothesis.status.value}_{hypothesis.id}"):
            render_heading(hypothesis)
            st.caption(f"Em teste · ciclo {hypothesis.target_cycle_id or 'não informado'}")
            record = core.get_ritual_by_cycle(hypothesis.target_cycle_id) if hypothesis.target_cycle_id else None
            if record and record.decision.id == hypothesis.promoted_decision_id:
                st.caption(f"Decisão CDMS #{record.decision.id} · avaliação em {record.decision.evaluation_due_date:%d/%m/%Y}")
            else:
                st.caption("Sem decisão CDMS vinculada ao registro consultado.")
                if hypothesis.target_cycle_id:
                    try:
                        due = date.fromisoformat(hypothesis.target_cycle_id) + timedelta(days=hypothesis.window_days)
                        st.caption(f"Fim da janela · {due:%d/%m/%Y}")
                    except ValueError:
                        pass
            st.write(f"**Limite de invalidação:** {hypothesis.invalidation_floor}{hypothesis.target_metric_unit}")
            render_details(hypothesis)
            st.caption("O resultado auditado é registrado no ritual. Encerrar manualmente altera somente o status do experimento.")
            with st.expander("Ações de encerramento manual"):
                if st.button("Concluir teste", key=f"btn_comp_{hypothesis.id}"):
                    try:
                        use_case.complete_hypothesis(hypothesis.id)
                        st.rerun()
                    except Exception as error:
                        st.error(str(error))
                if st.button("Invalidar / descartar", key=f"btn_disc_act_{hypothesis.id}"):
                    try:
                        use_case.discard_hypothesis(hypothesis.id)
                        st.rerun()
                    except Exception as error:
                        st.error(str(error))


def render_history(use_case, core):
    completed = use_case.list_by_status(HypothesisStatus.COMPLETED, limit=500)
    discarded = use_case.list_by_status(HypothesisStatus.DISCARDED, limit=500)
    st.caption(f"Concluídas · {len(completed)}   |   Descartadas · {len(discarded)}")
    if not completed and not discarded:
        st.info("Nenhum experimento encerrado até o momento.")
    for hypothesis in [*completed, *discarded]:
        with st.container(border=True, key=f"growth_hypothesis_{hypothesis.status.value}_{hypothesis.id}"):
            render_heading(hypothesis)
            status = "Concluído" if hypothesis.status == HypothesisStatus.COMPLETED else "Descartado"
            st.caption(f"{status} · ciclo {hypothesis.target_cycle_id or 'não informado'}")
            if hypothesis.promoted_decision_id:
                st.caption(f"Decisão CDMS #{hypothesis.promoted_decision_id}")
            learning = core.get_learning_by_decision_id(hypothesis.promoted_decision_id) if hypothesis.promoted_decision_id else None
            if learning:
                st.write(f"**Resultado auditado:** {OUTCOME_LABELS[learning.outcome.value]}")
                st.write(learning.evidence_notes or "Sem notas adicionais de evidência.")
                st.caption(f"Auditado em {learning.recorded_at:%d/%m/%Y}")
            else:
                st.caption("Sem aprendizado auditado vinculado. O status, isoladamente, não comprova resultado.")
            render_details(hypothesis)


def render_backlog_page(growth, core, today):
    if st.session_state.pop("growth_reset_new_hypothesis", False):
        for key in NEW_FIELDS:
            st.session_state.pop(key, None)
    use_case = ManageHypothesesUseCase(growth)
    proposal_case = PrepareCDMSProposalUseCase(growth_repository=growth)
    with st.container(key="growth_backlog"):
        notice = st.session_state.pop("growth_backlog_notice", None)
        if notice:
            st.success(notice)
        pending_tab, active_tab, history_tab = st.tabs(
            ["Backlog", "Em teste", "Histórico"], key="growth_backlog_tab", on_change="rerun",
        )
        with pending_tab:
            if pending_tab.open:
                render_pending(use_case, proposal_case, today)
        with active_tab:
            if active_tab.open:
                render_active(use_case, core)
        with history_tab:
            if history_tab.open:
                render_history(use_case, core)
