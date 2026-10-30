"""Shared Decision Cockpit presentation primitives; no business state."""
from html import escape

import streamlit as st


def render_tag(label, tone="neutral"):
    # Tones are internal design tokens; all displayed data stays escaped.
    tone = tone if tone in {"neutral", "mint", "amber", "coral", "cobalt", "violet"} else "neutral"
    st.html(f'<span class="cockpit-tag cockpit-tag-{tone}">{escape(str(label))}</span>', width="content")


def money(value):
    return "R$ " + f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
