"""Página demonstrativa e homologação visual do Decision Cockpit."""

from decimal import Decimal
import streamlit as st

from cdms.adapters.ui.components.cockpit_ui import (
    load_cockpit_css,
    render_circuit_breaker_status,
    render_kpi_hero,
)
from cdms.adapters.ui.components.cockpit_charts import create_funnel_cockpit_chart

st.set_page_config(page_title="Decision Cockpit | CDMS + CGS", layout="wide")
load_cockpit_css()

st.title("🎯 The Decision Cockpit")
st.caption("Visão integrada de Governança Semanal, Diagnóstico Financeiro e Backlog de Hipóteses.")

col_left, col_right = st.columns([0.62, 0.38], gap="medium")

with col_left:
    st.subheader("Diagnóstico Financeiro de Funil")
    render_kpi_hero(opportunity_reais=Decimal("12450.00"), bottleneck_label="Intenção (CTR)")

    st.markdown("##### Performance do Funil em 2 Passos")
    fig = create_funnel_cockpit_chart(
        impressions=125000,
        clicks=4200,
        leads=840,
        conversions=68,
        p90_reference_conversions=95,
        p10_reference_conversions=45,
    )
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader("Backlog & Governança ICE")

    st.markdown(
        """
        <div class="ice-card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.35rem;">
                <span class="badge-tag badge-hook">HOOK</span>
                <span class="ice-score-pill">ICE 8.4</span>
            </div>
            <div style="font-weight:600; font-size:0.88rem; color:#F1F5F9; margin-bottom:0.25rem;">
                Gancho interrogativo nos primeiros 3s
            </div>
            <div style="font-size:0.78rem; color:#94A3B8;">
                Meta: Elevar CTR de 3.3% para 4.2% | Invalidação: &lt; 2.8%
            </div>
        </div>

        <div class="ice-card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.35rem;">
                <span class="badge-tag badge-offer">OFFER</span>
                <span class="ice-score-pill">ICE 7.2</span>
            </div>
            <div style="font-weight:600; font-size:0.88rem; color:#F1F5F9; margin-bottom:0.25rem;">
                Bônus de onboarding no fechamento
            </div>
            <div style="font-size:0.78rem; color:#94A3B8;">
                Meta: Subir taxa lead-venda de 8% para 11%
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_circuit_breaker_status(
        is_active=True, note="Monitorando variação de CPA e queda de conversão"
    )

    if st.button("🚀 Promover Hipótese Prioritária para Ritual CDMS", use_container_width=True):
        st.success("Variável HOOK promovida para a próxima segunda-feira! Trava causal ativada.")