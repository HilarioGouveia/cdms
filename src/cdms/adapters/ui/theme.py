"""Resolve local Streamlit theme profiles for custom shell and chart tokens."""
from pathlib import Path
import tomllib

import streamlit as st


def theme_tokens():
    selected = st.session_state.get('_theme_profile')
    if selected in {'dark-premium', 'soft-light'}:
        path = Path(__file__).resolve().parents[4] / '.streamlit' / 'themes' / f'{selected}.toml'
        with path.open('rb') as source:
            profile = tomllib.load(source)['theme']
        keys = dict(background='backgroundColor', surface='secondaryBackgroundColor',
                    text='textColor', primary='primaryColor', card='dataframeHeaderBackgroundColor',
                    mint='greenTextColor', amber='yellowTextColor', coral='redTextColor',
                    violet='violetTextColor', cobalt='blueTextColor', border='borderColor', muted='grayTextColor')
        return {'dark': profile['base'] == 'dark', **{token: profile[key] for token, key in keys.items()}}
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
    if st.session_state.get('_theme_profile') in {'dark-premium', 'soft-light'}:
        scheme = 'dark' if tokens['dark'] else 'light'
        st.html('''<style>
        .stApp {color-scheme: SCHEME; background:var(--studio-background); color:var(--studio-text);}
        .stApp [data-testid="stHeader"] {background:var(--studio-background);}
        .stApp :is(h1,h2,h3,h4,h5,h6,p,label,[data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"]) {color:inherit;}
        .stApp [data-testid="stCaptionContainer"] {color:var(--studio-muted);}
        .stApp :is(button,input,textarea,[data-baseweb="select"] > div,[data-baseweb="input"], [data-baseweb="base-input"]) {
            background-color:var(--studio-surface); color:var(--studio-text); border-color:var(--studio-border);
        }
        .stApp input::placeholder, .stApp textarea::placeholder {color:var(--studio-muted);}
        .stApp button[kind="primary"], .stApp button[kind="primaryFormSubmit"] {background:var(--studio-primary); color:white;}
        .stApp :is([data-testid="stForm"], [data-testid="stVerticalBlockBorderWrapper"]) {border-color:var(--studio-border);}
        .stApp [data-testid="stMetricValue"] {color:var(--studio-text);}
        .stApp a {color:var(--studio-cobalt);}
        body:has(.stApp) [data-baseweb="popover"] {color-scheme:SCHEME;}
        body:has(.stApp) [data-baseweb="popover"] :is(ul,li,[role="listbox"],[data-testid="stPopoverBody"]) {
            background:var(--studio-surface, SURFACE); color:var(--studio-text, TEXT);
        }
        </style>'''.replace('SCHEME', scheme).replace('SURFACE', tokens['surface']).replace('TEXT', tokens['text']))
