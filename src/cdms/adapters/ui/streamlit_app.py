"""Módulo de Interface Streamlit do Creator Data Marketing System (CDMS)."""

from datetime import date
from pathlib import Path
import streamlit as st

from cdms.config.container import get_container
from cdms.domain.services.baseline_drift_detector import BaselineDriftDetector
from cdms.adapters.ui.components.metric_inputs import (
    render_calibration_editor,
)
from cdms.adapters.ui.components.trend_charts import render_metric_trends


def load_css():
    css_path = Path(__file__).parent / "styles" / "main.css"
    if css_path.exists():
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def run_app(*, embedded=False, section="ritual"):
    if section not in {"ritual", "history", "export", "calibration"}:
        raise ValueError("Seção de governança desconhecida.")
    if not embedded:
        st.set_page_config(
            page_title="Creator Data Marketing System (CDMS)",
            page_icon="🎯",
            layout="wide",
        )
    load_css()

    container = get_container()
    repo = container.repository

    # Persistência de Calibrações na Sessão
    if (
        "active_calibs" not in st.session_state
        or st.session_state.get("reload_calibs", False)
    ):
        active_list = repo.get_active_calibrations()
        st.session_state["active_calibs"] = {c.metric_key: c for c in active_list}
        st.session_state["active_calibs_list"] = active_list
        st.session_state["reload_calibs"] = False

    # Detetor de Deriva de Baseline (Recalibração Assistida)
    history_rituals = container.get_history_use_case.execute_list(limit=8)
    drift_alerts = BaselineDriftDetector.audit_drift(history_rituals, min_consecutive_cycles=4)

    if drift_alerts:
        for alert in drift_alerts:
            st.warning(
                f"⚡ **Recalibração Assistida Sugerida:** {alert.message}\n\n"
                f"Considere atualizar a meta de referência ($P_{{50}}$) para **{alert.suggested_new_p50}** em 'Calibrações' na navegação lateral."
            )

    # =========================================================
    # TAB 1: RITUAL SEMANAL (4 Passos Canónicos)
    # =========================================================
    if section == "ritual":
        from cdms.adapters.ui.ritual_wizard import render_ritual_wizard
        with st.container(key="ritual_screen"):
            render_ritual_wizard(container, date.today())

    if section == "history":
        st.subheader("Linha do Tempo de Governança")
        rituals = container.get_history_use_case.execute_list(limit=20)
        if not rituals:
            st.info("Nenhum ritual semanal registado até ao momento.")
        else:
            # Gráficos com faixas saudáveis P10 e P90
            render_metric_trends(rituals, st.session_state["active_calibs"])
            st.markdown("---")

            st.markdown("#### 📂 Histórico de Rituais Gravados")
            for r in rituals:
                with st.expander(
                    f"Ciclo {r.cycle_id} ({r.week_start.strftime('%d/%m/%Y')}) — {r.scenario.type.value}"
                ):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**📊 Snapshots de Métricas**")
                        for s in r.snapshots:
                            if s.is_available:
                                dev = s.deviation_pct()
                                dev_str = (
                                    f"({dev:+.1f}%)"
                                    if dev is not None
                                    else "(ref 0)"
                                )
                                st.write(
                                    f"- **{s.definition.name}:** {s.observed_value} {s.definition.unit} {dev_str} | *{s.status().value}*"
                                )
                            else:
                                st.write(
                                    f"- **{s.definition.name}:** Indisponível (`{s.unavailability_reason}`)"
                                )
                    with c2:
                        st.markdown("**🎯 Decisão Prioritária**")
                        st.write(f"- **Ação:** {r.decision.summary}")
                        st.write(f"- **Hipótese:** {r.decision.hypothesis}")
                        st.write(f"- **Critério:** {r.decision.success_criterion}")
                        st.write(
                            f"- **Prazo:** {r.decision.evaluation_due_date.strftime('%d/%m/%Y')} ({r.decision.owner})"
                        )
                        if r.learning:
                            st.markdown("**💡 Aprendizado Auditado**")
                            st.write(
                                f"- **Decisão Alvo (ID {r.learning.target_decision_id}):** {r.learning.target_decision_summary}"
                            )
                            st.write(
                                f"- **Resultado:** {r.learning.outcome.value}"
                            )
                            st.write(
                                f"- **Evidências:** {r.learning.evidence_notes}"
                            )

    # =========================================================
    # TAB 3: EXPORTAÇÃO MARKDOWN
    # =========================================================
    if section == "export":
        st.subheader("📄 Exportação do Relatório de Auditoria")
        rituals = container.get_history_use_case.execute_list(limit=20)
        if not rituals:
            st.caption("Finalize ao menos um ritual para gerar exportações.")
        else:
            selected_cycle = st.selectbox(
                "Selecione o ciclo para exportar:",
                options=[r.cycle_id for r in rituals],
            )
            if selected_cycle:
                md_text = (
                    container.export_ritual_use_case.execute_markdown(
                        selected_cycle
                    )
                )
                st.text_area(
                    "Pré-visualização do Relatório:", md_text, height=300
                )
                st.download_button(
                    label="💾 Descarregar Relatório (.md)",
                    data=md_text,
                    file_name=f"cdms_relatorio_{selected_cycle}.md",
                    mime="text/markdown",
                )

    # =========================================================
    # TAB 4: CALIBRAÇÃO & CONFIGURAÇÕES
    # =========================================================
    if section == "calibration":
        st.subheader("⚙️ Configurações Operacionais de Referência")
        current_calibs = st.session_state["active_calibs_list"]
        updated_calibs = render_calibration_editor(current_calibs)

        if st.button("Salvar Novas Calibrações"):
            for cal in updated_calibs.values():
                container.calibrate_metrics_use_case.execute_save(cal)
            st.session_state["reload_calibs"] = True
            st.toast("✅ Novas calibrações salvas com sucesso!")
            st.rerun()
