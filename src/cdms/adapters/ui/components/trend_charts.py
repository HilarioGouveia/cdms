"""Componente de visualização de histórico de tendências temporais e limites canónicos."""
from typing import List, Dict
import pandas as pd
import streamlit as st
from cdms.adapters.ui.theme import theme_tokens


def render_metric_trends(rituals: List, active_calibs: Dict):
    """Renderiza gráficos de linhas com faixas saudáveis (P10 e P90) das últimas semanas."""
    if not rituals:
        st.info("Nenhum histórico registado para exibir tendências.")
        return

    palette = theme_tokens()
    ordered_rituals = sorted(rituals, key=lambda r: r.week_start)

    data = []
    for r in ordered_rituals:
        row = {"Semana": r.week_start.strftime("%d/%m/%Y")}
        for snap in r.snapshots:
            if snap.is_available:
                row[snap.definition.key.value if hasattr(snap.definition.key, "value") else str(snap.definition.key)] = float(snap.observed_value)
        data.append(row)

    df_hist = pd.DataFrame(data).set_index("Semana")

    st.markdown("#### 📈 Evolução Histórica das Métricas Canónicas")
    tab_names = ["Alcance Semanal", "Retenção (%)", "CTR (%)", "Conversões"]
    tabs = st.tabs(tab_names)

    mapping = [
        ("reach", 0),
        ("avg_retention_pct", 1),
        ("ctr_pct", 2),
        ("conversions", 3),
    ]

    for key_str, tab_idx in mapping:
        with tabs[tab_idx]:
            if key_str in df_hist.columns:
                calib = active_calibs.get(key_str)
                chart_df = pd.DataFrame(index=df_hist.index)
                chart_df["Observado"] = df_hist[key_str]

                if calib:
                    chart_df["P10 (Mín. Saudável)"] = float(calib.healthy_min)
                    chart_df["P90 (Máx. Saudável)"] = float(calib.healthy_max)

                st.line_chart(
                    chart_df,
                    color=[palette["cobalt"], palette["amber"], palette["mint"]] if calib else [palette["cobalt"]],
                    height=280
                )
            else:
                st.caption(f"Sem dados observados para {tab_names[tab_idx]}.")