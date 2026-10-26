import streamlit as st
from datetime import date, timedelta
from pathlib import Path

from cdms.config.container import get_container
from cdms.domain.entities.learning import HypothesisOutcome
from cdms.application.use_cases.run_weekly_ritual import (
    CycleAlreadyClosedError,
    InvalidCycleDateError,
)
from cdms.adapters.ui.components.metric_inputs import (
    render_calibration_editor,
    render_metric_snapshots_form,
)
from cdms.adapters.ui.components.scenario_card import render_scenario_card
from cdms.adapters.ui.components.decision_form import render_decision_form

def load_css():
    css_path = Path(__file__).parent / "styles" / "main.css"
    if css_path.exists():
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def run_app():
    st.set_page_config(
        page_title="CDMS — Creator Data Marketing System",
        page_icon="🎯",
        layout="wide"
    )
    load_css()

    container = get_container()
    repo = container.repository
    settings = container.settings

    st.title("🎯 CDMS — Creator Data Marketing System")
    st.caption(f"Governança de Decisão e Diagnóstico Heurístico | Regras v{settings.RULES_VERSION}")

    tab_ritual, tab_history, tab_export, tab_config = st.tabs([
        "📋 Ritual da Semana",
        "📈 Linha do Tempo & Histórico",
        "📄 Exportar Resumo (.md)",
        "⚙️ Configurações & Calibração"
    ])

    # =========================================================
    # TAB 1: RITUAL SEMANAL (4 Passos Canónicos)
    # =========================================================
    with tab_ritual:
        # Passo 0: Data do Ciclo (Segunda-feira)
        today = date.today()
        default_monday = today - timedelta(days=today.weekday())
        
        col_c1, col_c2 = st.columns([1, 2])
        with col_c1:
            week_start = st.date_input("Segunda-feira de Referência do Ciclo", value=default_monday, key="cycle_week_start")
        with col_c2:
            st.info(f"Ciclo canónico: `{week_start.isoformat()}` (Fuso: {settings.TIMEZONE_NAME})")

        if week_start.weekday() != 0:
            st.error("⚠️ Atenção: O ciclo deve iniciar obrigatoriamente numa segunda-feira conforme a governança da SDD.")

        # Passo 1: Avaliar decisão anterior elegível
        st.markdown("---")
        st.subheader("1. Auditoria do Ciclo Anterior (Loop de Aprendizagem)")
        pending_decision = repo.get_pending_decision(before_week_start=week_start, evaluation_as_of=today)

        target_decision_id = None
        learning_outcome = None
        learning_notes = None

        if pending_decision:
            st.warning(
                f"📌 **Decisão Elegível para Auditoria (Ciclo {pending_decision.cycle_id}):** {pending_decision.summary}\n\n"
                f"🔬 **Hipótese:** {pending_decision.hypothesis}\n\n"
                f"🎯 **Critério:** {pending_decision.success_criterion} | **Prazo:** {pending_decision.evaluation_due_date.strftime('%d/%m/%Y')}"
            )
            col_l1, col_l2 = st.columns([1, 2])
            with col_l1:
                target_decision_id = pending_decision.id
                outcome_label = st.selectbox(
                    "Resultado Observado:",
                    options=[
                        ("ACHIEVED", "✅ Meta Atingida"),
                        ("PARTIAL", "🟡 Meta Parcialmente Atingida"),
                        ("NOT_ACHIEVED", "❌ Meta Não Atingida"),
                        ("INCONCLUSIVE", "⚪ Inconclusivo / Fatores Externos"),
                    ],
                    format_func=lambda x: x[1]
                )[0]
                learning_outcome = HypothesisOutcome(outcome_label)
            with col_l2:
                learning_notes = st.text_area(
                    "Evidências e Aprendizados Observados:",
                    placeholder="Descreva os dados que confirmaram ou refutaram o critério..."
                )
        else:
            st.caption("ℹ️ Nenhuma decisão pendente elegível para auditoria neste ciclo.")

        # Passo 2: Ingestão de Métricas
        st.markdown("---")
        st.subheader("2. Ingestão de Métricas Observadas")
        active_calibs = {c.metric_key: c for c in repo.get_active_calibrations()}
        snapshots = render_metric_snapshots_form(active_calibs)

        # Passo 3: Diagnóstico Heurístico em Tempo Real
        st.markdown("---")
        st.subheader("3. Diagnóstico Heurístico do Momento Operacional")
        scenario = container.classifier.classify(snapshots)
        render_scenario_card(scenario)

        # Passo 4: Trava da Decisão Única e Finalização
        st.markdown("---")
        st.subheader("4. Trava da Decisão Única da Semana")
        next_eval_date = week_start + timedelta(days=7)
        dec_summary, dec_hypothesis, dec_criterion, dec_due_date, dec_owner = render_decision_form(default_due_date=next_eval_date)

        st.markdown("---")
        if st.button("💾 Concluir e Gravar Ritual Semanal", type="primary"):
            if not dec_summary or not dec_hypothesis or not dec_criterion:
                st.error("Por favor, preencha todos os campos obrigatórios da Decisão (Ação, Hipótese e Critério de Sucesso).")
            else:
                try:
                    record = container.run_weekly_ritual_use_case.execute(
                        week_start=week_start,
                        snapshots=snapshots,
                        decision_summary=dec_summary,
                        decision_hypothesis=dec_hypothesis,
                        decision_success_criterion=dec_criterion,
                        decision_evaluation_due_date=dec_due_date,
                        decision_owner=dec_owner,
                        target_decision_id=target_decision_id,
                        learning_outcome=learning_outcome,
                        learning_evidence_notes=learning_notes,
                        evaluation_as_of=today
                    )
                    st.success(f"🎉 Ritual do ciclo {record.cycle_id} finalizado com sucesso! Cenário: {record.scenario.type.value}")
                    st.rerun()
                except CycleAlreadyClosedError as e:
                    st.error(f"❌ {str(e)}")
                except InvalidCycleDateError as e:
                    st.error(f"❌ {str(e)}")
                except Exception as e:
                    st.error(f"❌ Erro ao finalizar ritual: {str(e)}")

    # =========================================================
    # TAB 2: HISTÓRICO & LINHA DO TEMPO
    # =========================================================
    with tab_history:
        st.subheader("Linha do Tempo de Governança")
        rituals = container.get_history_use_case.execute_list(limit=20)
        if not rituals:
            st.info("Nenhum ritual semanal registado até ao momento.")
        else:
            for r in rituals:
                with st.expander(f"Ciclo {r.cycle_id} ({r.week_start.strftime('%d/%m/%Y')}) — {r.scenario.type.value}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**📊 Snapshots de Métricas**")
                        for s in r.snapshots:
                            if s.is_available:
                                dev = s.deviation_pct()
                                dev_str = f"({dev:+.1f}%)" if dev is not None else "(ref 0)"
                                st.write(f"- **{s.definition.name}:** {s.observed_value} {s.definition.unit} {dev_str} | *{s.status().value}*")
                            else:
                                st.write(f"- **{s.definition.name}:** Indisponível (`{s.unavailability_reason}`)")
                    with c2:
                        st.markdown("**🎯 Decisão Prioritária**")
                        st.write(f"- **Ação:** {r.decision.summary}")
                        st.write(f"- **Hipótese:** {r.decision.hypothesis}")
                        st.write(f"- **Critério:** {r.decision.success_criterion}")
                        st.write(f"- **Prazo:** {r.decision.evaluation_due_date.strftime('%d/%m/%Y')} ({r.decision.owner})")
                        if r.learning:
                            st.markdown("**💡 Aprendizado Auditado**")
                            st.write(f"- **Decisão Alvo (ID {r.learning.target_decision_id}):** {r.learning.target_decision_summary}")
                            st.write(f"- **Resultado:** {r.learning.outcome.value}")
                            st.write(f"- **Evidências:** {r.learning.evidence_notes}")

    # =========================================================
    # TAB 3: EXPORTAÇÃO MARKDOWN
    # =========================================================
    with tab_export:
        st.subheader("📄 Exportação do Relatório de Auditoria")
        rituals = container.get_history_use_case.execute_list(limit=20)
        if not rituals:
            st.caption("Finalize ao menos um ritual para gerar exportações.")
        else:
            selected_cycle = st.selectbox(
                "Selecione o ciclo para exportar:",
                options=[r.cycle_id for r in rituals]
            )
            if selected_cycle:
                md_text = container.export_ritual_use_case.execute_markdown(selected_cycle)
                st.text_area("Pré-visualização do Relatório:", md_text, height=300)
                st.download_button(
                    label="💾 Descarregar Relatório (.md)",
                    data=md_text,
                    file_name=f"cdms_relatorio_{selected_cycle}.md",
                    mime="text/markdown"
                )

    # =========================================================
    # TAB 4: CALIBRAÇÃO & CONFIGURAÇÕES
    # =========================================================
    with tab_config:
        st.subheader("⚙️ Configurações Operacionais de Referência")
        current_calibs = repo.get_active_calibrations()
        updated_calibs = render_calibration_editor(current_calibs)
        if st.button("Salvar Novas Calibrações"):
            for cal in updated_calibs.values():
                container.calibrate_metrics_use_case.execute_save(cal)
            st.success("✅ Calibrações salvas com sucesso! Novos rituais utilizarão estas faixas de referência.")
            st.rerun()