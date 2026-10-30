"""Gerador de visualizações gráficas no padrão visual Decision Cockpit."""

from decimal import Decimal
import plotly.graph_objects as go
from cdms.adapters.ui.theme import theme_tokens


def create_funnel_cockpit_chart(
    impressions: int,
    clicks: int,
    leads: int,
    conversions: int,
    p90_reference_conversions: float = None,
    p10_reference_conversions: float = None,
) -> go.Figure:
    """Renderiza funil com gradiente esmeralda, superfícies escuras e linhas P10/P90."""
    palette = theme_tokens()
    label_color = palette["background"] if palette["dark"] else palette["surface"]
    stages = ["1. Impressões", "2. Cliques (CTR)", "3. Leads (Opt-in)", "4. Vendas"]
    values = [impressions, clicks, leads, conversions]

    fig = go.Figure(
        go.Funnel(
            y=stages,
            x=values,
            textinfo="value+percent previous",
            textposition="inside",
            textfont=dict(family="JetBrains Mono, monospace", size=13, color=[palette["text"], label_color, label_color, label_color]),
            marker=dict(
                color=[palette["card"], palette["cobalt"], palette["mint"], palette["mint"]],
                line=dict(width=1, color=palette["border"]),
            ),
            connector=dict(line=dict(color=palette["border"], width=1)),
        )
    )

    fig.update_layout(
        template="plotly_dark" if palette["dark"] else "plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=25, b=25),
        height=320,
        font=dict(family="Inter, sans-serif", color=palette["text"]),
        showlegend=False,
    )

    if p90_reference_conversions is not None:
        fig.add_hline(
            y=3,
            line_dash="dot",
            line_color=palette["mint"],
            line_width=1.5,
            annotation_text=f"P90 Meta ({p90_reference_conversions:,.0f})",
            annotation_position="bottom right",
            annotation_font=dict(family="JetBrains Mono", size=10, color=palette["mint"]),
        )

    if p10_reference_conversions is not None:
        fig.add_hline(
            y=3,
            line_dash="dot",
            line_color=palette["coral"],
            line_width=1.5,
            annotation_text=f"P10 Piso ({p10_reference_conversions:,.0f})",
            annotation_position="bottom left",
            annotation_font=dict(family="JetBrains Mono", size=10, color=palette["coral"]),
        )

    return fig