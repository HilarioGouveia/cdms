from datetime import date
from typing import Tuple
import streamlit as st


def render_decision_form(default_due_date: date) -> Tuple[str, str, str, date, str]:
    """Renderiza a trava da decisão única com critério e prazo verificáveis."""
    st.markdown("#### 🎯 Trava da Decisão Única do Ciclo")
    st.caption("A governança do CDMS exige exatamente uma decisão prioritária para garantir a causalidade experimental.")

    # Proteção contra StreamlitValueBelowMinError:
    # Garante que min_value nunca seja estritamente maior que o valor default inicial
    today = date.today()
    safe_min_value = min(default_due_date, today) if default_due_date else today

    col1, col2 = st.columns(2)
    with col1:
        summary = st.text_input(
            "Ação Operacional (O Que Fazer)",
            placeholder="Ex: Padronizar miniaturas e títulos com gancho focado em dor",
            key="dec_summary"
        )
        hypothesis = st.text_area(
            "Hipótese Causal (Porquê / Racional)",
            placeholder="Ex: Ao usar gancho de dor, aumentamos o CTR de link e geramos cliques mais qualificados",
            key="dec_hypothesis"
        )
    with col2:
        criterion = st.text_area(
            "Critério de Sucesso Verificável",
            placeholder="Ex: Atingido: CTR >= 3.5%; Parcial: CTR entre 2.5% e 3.4%; Não atingido: CTR < 2.5%",
            key="dec_criterion"
        )
        due_date = st.date_input(
            "Prazo de Avaliação (Data Limite)",
            value=default_due_date,
            min_value=safe_min_value,
            key="dec_due_date"
        )
        owner = st.text_input("Responsável pela Execução", value="Creator", key="dec_owner")

    return summary, hypothesis, criterion, due_date, owner