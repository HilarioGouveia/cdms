"""Resolve local Streamlit theme profiles for custom shell and chart tokens."""
from pathlib import Path
import tomllib

import streamlit as st


def theme_tokens():
    base = st.get_option("theme.base") or "dark"
    profile = {}
    if base not in ("dark", "light"):
        # theme.base is server configuration, never a widget or uploaded path.
        with Path(base).open("rb") as source:
            profile = tomllib.load(source)["theme"]
    dark = profile.get("base", base) == "dark"
    fallback = {
        "backgroundColor": "#20242C" if dark else "#F2F3F1",
        "secondaryBackgroundColor": "#292E38" if dark else "#FAFAF8",
        "textColor": "#E7E9EC" if dark else "#252B33",
        "primaryColor": "#526B8E" if dark else "#405D87",
        "dataframeHeaderBackgroundColor": "#323844" if dark else "#E8EBE8",
        "greenTextColor": "#91CDB5" if dark else "#246B54",
        "yellowTextColor": "#D6B477" if dark else "#805C24",
        "redTextColor": "#E49A8C" if dark else "#A94738",
        "violetTextColor": "#B9A8CE" if dark else "#6C5283",
        "blueTextColor": "#8EA8D0" if dark else "#405D87",
        "borderColor": "#454C58" if dark else "#C8CECA",
        "grayTextColor": "#B9BEC6" if dark else "#59635F",
    }
    keys = dict(background="backgroundColor", surface="secondaryBackgroundColor",
                text="textColor", primary="primaryColor", card="dataframeHeaderBackgroundColor",
                mint="greenTextColor", amber="yellowTextColor", coral="redTextColor",
                violet="violetTextColor", cobalt="blueTextColor", border="borderColor", muted="grayTextColor")
    return {"dark": dark, **{
        token: st.get_option(f"theme.{key}") or profile.get(key) or fallback[key]
        for token, key in keys.items()
    }}


def apply_shell_theme():
    tokens = theme_tokens()
    css = ";".join(f"--studio-{key}: {value}" for key, value in tokens.items() if key != "dark")
    st.html(f"<style>.stApp {{{css}}}</style>")
