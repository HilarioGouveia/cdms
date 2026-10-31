"""Ritual guiado com rascunhos de sessão por ciclo e gravação única ao concluir."""
from datetime import timedelta

import streamlit as st

from cdms.adapters.parsers.platform_parser import PlatformMetricsParser
from cdms.adapters.ui.components.decision_form import render_decision_form
from cdms.adapters.ui.components.metric_inputs import render_metric_snapshots_form
from cdms.adapters.ui.components.scenario_card import render_scenario_card
from cdms.domain.entities.learning import HypothesisOutcome
from cdms.domain.entities.metric import MetricSnapshot
from cdms.domain.services.canonical_metrics import CANONICAL_DEFINITIONS, DEFAULT_CALIBRATIONS
from cgs.adapters.persistence.sqlite_growth_repo import SQLiteGrowthRepository
from cgs.domain.entities.hypothesis import HypothesisStatus, MetricDirection


STEPS = {1: "Aprendizado", 2: "Métricas", 3: "Diagnóstico", 4: "Decisão"}
DRAFT_PREFIXES = ("dec_", "val_", "avail_", "reason_", "custom_reason_", "ritual_learning_")
DRAFT_KEYS = {
    "ritual_proposal", "_decision_form_source", "_ritual_step",
    "_ritual_learning_target", "parsed_metrics_dto",
}
OUTCOMES = [
    ("ACHIEVED", "✅ Meta Atingida"),
    ("PARTIAL", "🟡 Meta Parcialmente Atingida"),
    ("NOT_ACHIEVED", "❌ Meta Não Atingida"),
    ("INCONCLUSIVE", "⚪ Inconclusivo / Fatores Externos"),
]


def sync_cycle(cycle):
    """Swap only ritual fields before rendering widgets for the selected cycle."""
    previous = st.session_state.get("_ritual_active_cycle")
    if previous == cycle:
        return
    drafts = st.session_state.setdefault("_ritual_drafts", {})
    keys = [key for key in st.session_state if key.startswith(DRAFT_PREFIXES) or key in DRAFT_KEYS]
    if previous is not None:
        drafts[previous] = {key: st.session_state[key] for key in keys}
    for key in keys:
        del st.session_state[key]
    st.session_state.update(drafts.get(cycle, {}))
    st.session_state["_ritual_active_cycle"] = cycle
    st.session_state.setdefault("_ritual_step", 1)


def set_step(step):
    st.session_state["_ritual_step"] = step


def select_step():
    st.session_state["_ritual_step"] = st.session_state.ritual_step_selector or st.session_state["_ritual_step"]


def snapshots_from_draft(calibrations):
    snapshots = []
    for definition in CANONICAL_DEFINITIONS:
        key = definition.key
        if f"avail_{key}" not in st.session_state:
            raise ValueError("Revise as métricas na etapa 2 antes de concluir o ritual.")
        available = st.session_state[f"avail_{key}"]
        reason = None
        value = None
        if available:
            value = st.session_state.get(f"val_{key}")
            if value is None:
                raise ValueError(f"Preencha o valor de {definition.name} na etapa 2.")
        else:
            reason = st.session_state.get(f"reason_{key}")
            if reason == "OUTRO":
                reason = st.session_state.get(f"custom_reason_{key}", "").strip()
            if not reason:
                raise ValueError(f"Informe o motivo de indisponibilidade de {definition.name} na etapa 2.")
        snapshots.append(MetricSnapshot(
            definition=definition,
            calibration=calibrations.get(key, DEFAULT_CALIBRATIONS[key]),
            observed_value=float(value) if available else None,
            is_available=available, unavailability_reason=reason,
        ))
    return snapshots


def render_learning(pending):
    if not pending:
        st.info("Sem auditoria pendente. Você pode avançar para as métricas.")
        return
    st.write(f"**Decisão do ciclo {pending.cycle_id}:** {pending.summary}")
    st.write(f"**Hipótese:** {pending.hypothesis}")
    st.write(f"**Critério:** {pending.success_criterion}")
    st.caption(f"Prazo de avaliação · {pending.evaluation_due_date:%d/%m/%Y}")
    st.selectbox(
        "Resultado Observado:", [None, *OUTCOMES],
        format_func=lambda value: "Selecione o resultado" if value is None else value[1],
        key="ritual_learning_outcome",
    )
    st.text_area("Evidências e Aprendizados Observados:", key="ritual_learning_notes",
                 placeholder="Descreva os dados que confirmaram ou refutaram o critério...")


def render_metrics(cycle, calibrations):
    with st.expander("Importar relatório da plataforma (CSV / XLSX)"):
        scope = st.session_state.get("_studio_upload_scope", "local")
        report = st.file_uploader("Carregar relatório da plataforma", type=["csv", "xlsx", "xls"],
                                  key=f"platform_file_uploader_{scope}_{cycle}")
        if report is not None:
            try:
                parsed = PlatformMetricsParser.parse_file(report.getvalue(), report.name)
                st.session_state["parsed_metrics_dto"] = parsed
            except Exception as error:
                st.error(f"Erro ao processar ficheiro: {error}")
        parsed = st.session_state.get("parsed_metrics_dto")
        if parsed is not None:
            st.caption("Confira os dados extraídos e preencha os campos abaixo. A importação não substitui os valores automaticamente.")
            st.json({"Alcance": parsed.reach, "Retenção (%)": parsed.retention_pct,
                     "CTR (%)": parsed.ctr_pct, "Conversões": parsed.conversions})
    render_metric_snapshots_form(calibrations)


def render_decision(growth, week_start):
    proposals = {
        item.id: item for item in growth.list_hypotheses(status=HypothesisStatus.PENDING, limit=100)
        if item.target_cycle_id == week_start.isoformat() and item.promoted_decision_id is None
    }
    if st.session_state.get("ritual_proposal") not in proposals:
        st.session_state["ritual_proposal"] = None
    proposal_id = st.selectbox(
        "Proposta CGS para este ciclo", [None, *proposals], key="ritual_proposal",
        format_func=lambda value: "Decisão manual" if value is None else f"#{value} — {proposals[value].action_description}",
    )
    source = (week_start.isoformat(), proposal_id)
    previous = st.session_state.get("_decision_form_source")
    if previous != source:
        if proposal_id is not None:
            proposal = proposals[proposal_id]
            comparison = "≥" if proposal.metric_direction == MetricDirection.HIGHER_IS_BETTER else "≤"
            st.session_state.update({
                "dec_summary": proposal.action_description,
                "dec_hypothesis": proposal.expected_impact_description,
                "dec_criterion": f"{proposal.target_metric_key} {comparison} {proposal.success_metric_target}{proposal.target_metric_unit}; limite de invalidação {proposal.invalidation_floor}{proposal.target_metric_unit}.",
                "dec_due_date": week_start + timedelta(days=proposal.window_days),
            })
        elif previous is not None:
            for key in ("dec_summary", "dec_hypothesis", "dec_criterion", "dec_due_date"):
                st.session_state.pop(key, None)
        st.session_state["_decision_form_source"] = source
    values = render_decision_form(default_due_date=week_start + timedelta(days=7))
    return proposal_id, values


def render_review(container, pending):
    st.subheader("Revisão do ritual")
    if pending:
        outcome = st.session_state.get("ritual_learning_outcome")
        st.write(f"**Aprendizado:** {outcome[1] if outcome else 'Resultado ainda não selecionado'}")
        st.write(st.session_state.get("ritual_learning_notes", "") or "Sem evidências registradas.")
    else:
        st.caption("Aprendizado · sem auditoria pendente")
    try:
        snapshots = snapshots_from_draft(st.session_state["active_calibs"])
    except ValueError as error:
        st.warning(str(error))
        return
    for snapshot in snapshots:
        value = f"{snapshot.observed_value:g} {snapshot.definition.unit}" if snapshot.is_available else f"Indisponível · {snapshot.unavailability_reason}"
        st.write(f"**{snapshot.definition.name}:** {value}")
    render_scenario_card(container.classifier.classify(snapshots))


def render_ritual_wizard(container, today):
    st.session_state.setdefault("cycle_week_start", today - timedelta(days=today.weekday()))
    week_start = st.date_input("Segunda-feira de Referência do Ciclo",
                               key="cycle_week_start")
    if week_start.weekday() != 0:
        st.error("O ciclo deve iniciar numa segunda-feira.")
        return
    cycle = week_start.isoformat()
    sync_cycle(cycle)
    # Retain step fields while other steps are hidden, including standalone use.
    for key in list(st.session_state):
        if key.startswith(DRAFT_PREFIXES) or key == "ritual_proposal":
            st.session_state[key] = st.session_state[key]
    st.caption(f"Ciclo {week_start:%d/%m/%Y} · {container.settings.TIMEZONE_NAME} · rascunho nesta sessão")
    existing = container.repository.get_ritual_by_cycle(cycle)
    from cdms.adapters.persistence.sqlite_ingestion_repo import SQLiteIngestionRepository
    source=SQLiteIngestionRepository(container.settings.DB_PATH).ritual_source(cycle)
    if source:
        st.caption(f"Métricas preparadas da importação Meta {source['job_id']} · revisão em {source['reviewed_at']}. Confira os valores antes de concluir.")
    if existing:
        st.success(f"Ritual do ciclo {cycle} concluído. Cenário: {existing.scenario.type.value}")
        st.write(existing.decision.summary)
        return
    pending = container.repository.get_pending_decision(before_week_start=week_start, evaluation_as_of=today)
    target = pending.id if pending else None
    if st.session_state.get("_ritual_learning_target") != target:
        for key in ("ritual_learning_outcome", "ritual_learning_notes"):
            st.session_state.pop(key, None)
        st.session_state["_ritual_learning_target"] = target
    step = st.session_state["_ritual_step"]
    with st.container(key="ritual_wizard"):
        with st.container(key="ritual_steps"):
            st.session_state["ritual_step_selector"] = step
            st.segmented_control("Etapas do ritual", list(STEPS),
                                 format_func=lambda value: f"{value} · {STEPS[value]}",
                                 key="ritual_step_selector", on_change=select_step, width="stretch")
        st.subheader(f"Etapa {step} de 4 · {STEPS[step]}")
        if step == 1:
            render_learning(pending)
        elif step == 2:
            render_metrics(cycle, st.session_state["active_calibs"])
        elif step == 3:
            try:
                snapshots = snapshots_from_draft(st.session_state["active_calibs"])
                render_scenario_card(container.classifier.classify(snapshots))
                st.caption("O diagnóstico é recalculado a partir das métricas e calibrações atuais.")
            except ValueError as error:
                st.info(str(error))
        else:
            growth = SQLiteGrowthRepository(str(container.settings.DB_PATH))
            proposal_id, values = render_decision(growth, week_start)
            with st.container(border=True):
                render_review(container, pending)
            if st.button("Concluir ritual", type="primary", key="ritual_finish", width="stretch"):
                try:
                    summary, hypothesis, criterion, due_date, owner = values
                    if not all(value.strip() for value in (summary, hypothesis, criterion)):
                        raise ValueError("Preencha os campos obrigatórios da decisão: ação, hipótese e critério de sucesso.")
                    snapshots = snapshots_from_draft(st.session_state["active_calibs"])
                    outcome = st.session_state.get("ritual_learning_outcome")
                    if pending and not outcome:
                        raise ValueError("Selecione o resultado observado na etapa 1.")
                    container.run_weekly_ritual_use_case.execute(
                        week_start=week_start, snapshots=snapshots,
                        decision_summary=summary, decision_hypothesis=hypothesis,
                        decision_success_criterion=criterion, decision_evaluation_due_date=due_date,
                        decision_owner=owner, target_decision_id=target,
                        learning_outcome=HypothesisOutcome(outcome[0]) if pending else None,
                        learning_evidence_notes=st.session_state.get("ritual_learning_notes") if pending else None,
                        evaluation_as_of=today, source_hypothesis_id=proposal_id,
                    )
                    st.rerun()
                except Exception as error:
                    st.error(f"Não foi possível concluir: {error}")
        st.divider()
        with st.container(horizontal=True, key="ritual_navigation"):
            st.button("Anterior", icon=":material/arrow_back:", disabled=step == 1,
                      key="ritual_previous", on_click=set_step, args=(step - 1,))
            if step < 4:
                st.button("Próxima", icon=":material/arrow_forward:", type="primary",
                          key="ritual_next", on_click=set_step, args=(step + 1,))
