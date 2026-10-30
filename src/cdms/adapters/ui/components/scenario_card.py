import streamlit as st
from cdms.adapters.ui.components.identity import render_tag
from cdms.domain.entities.scenario import Scenario, ScenarioType

def render_scenario_card(scenario: Scenario) -> None:
    """Renderiza o card de diagnóstico heurístico e evidências."""
    
    tones = {ScenarioType.PRE_DROP: ("Risco de queda", "amber"),
             ScenarioType.ANOMALY: ("Assimetria crítica", "coral"),
             ScenarioType.SCALE: ("Potencial de escala", "mint"),
             ScenarioType.STABILITY: ("Estabilidade", "cobalt"),
             ScenarioType.INCONCLUSIVE: ("Inconclusivo", "violet")}
    render_tag(*tones.get(scenario.type, (scenario.type.value, "neutral")))
    
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(f"**Diagnóstico:** {scenario.description}")
        st.markdown(f"**Diretriz Tática:** {scenario.recommendation}")
    with col2:
        if scenario.evidence_metric_keys:
            st.markdown(f"**Métricas Envolvidas:** `{', '.join(scenario.evidence_metric_keys)}`")
        if scenario.inconclusive_reason:
            st.caption(f"**Motivo de Inconclusão:** `{scenario.inconclusive_reason.value}`")
