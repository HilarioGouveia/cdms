"""Componentes reutilizáveis em Streamlit integrando o tema Decision Cockpit."""

import os
from decimal import Decimal
import streamlit as st


def load_cockpit_css():
    """Injeta a folha de estilos CSS personalizada no cabeçalho do Streamlit."""
    css_path = os.path.join(os.path.dirname(__file__), "../styles/cockpit_theme.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def render_kpi_hero(opportunity_reais: Decimal, bottleneck_label: str):
    """Renderiza o card de destaque de Oportunidade Financeira e Gargalo Primário."""
    st.markdown(
        f"""
        <div class="cockpit-card">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div class="kpi-container">
                    <span class="kpi-label">Oportunidade Estimada Recuperável</span>
                    <span class="kpi-value-emerald">R$ {opportunity_reais:,.2f}</span>
                </div>
                <div class="badge-bottleneck-amber">
                    ⚠️ Gargalo Primário: {bottleneck_label}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_circuit_breaker_status(is_active: bool, note: str = ""):
    """Renderiza a barra de segurança de Auto-Rollback / Circuit Breaker."""
    if is_active:
        st.markdown(
            f"""
            <div class="circuit-breaker-banner">
                <span>🛡️ CIRCUIT BREAKER ATIVO (Auto-Rollback Engatilhado)</span>
                <span style="font-size:0.75rem; opacity:0.85;">{note}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )