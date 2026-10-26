import streamlit as st
from cdms.domain.entities.scenario import Scenario, ScenarioType, InconclusiveReason

BADGE_STYLES = {
    ScenarioType.PRE_DROP: ("🔴 Risco de Queda", "badge-pre-drop"),
    ScenarioType.ANOMALY: ("🟠 Assimetria Crítica", "badge-anomaly"),
    ScenarioType.SCALE: ("🚀 Alavancagem de Escala", "badge-scale"),
    ScenarioType.STABILITY: ("🟢 Equilíbrio Operacional", "badge-stability"),
    ScenarioType.INCONCLUSIVE: ("⚪ Diagnóstico Inconclusivo", "badge-inconclusive"),
}

def render_scenario_card(scenario: Scenario) -> None:
    """Renderiza o card de diagnóstico heurístico e evidências."""
    label, css_class = BADGE_STYLES.get(scenario.type, (scenario.type.value, "badge-inconclusive"))
    
    st.markdown(f'<div class="scenario-badge {css_class}">{label}</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(f"**Diagnóstico:** {scenario.description}")
        st.markdown(f"**Diretriz Tática:** {scenario.recommendation}")
    with col2:
        if scenario.evidence_metric_keys:
            st.markdown(f"**Métricas Envolvidas:** `{', '.join(scenario.evidence_metric_keys)}`")
        if scenario.inconclusive_reason:
            st.caption(f"**Motivo de Inconclusão:** `{scenario.inconclusive_reason.value}`")