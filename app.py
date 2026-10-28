import sys
import os

# Garante a resolução dos pacotes 'cdms' e 'cgs' em 'src'
sys.path.insert(0, os.path.abspath("src"))

import streamlit as st
from cdms.adapters.ui.streamlit_app import run_app as render_cdms
from cgs.adapters.ui.growth_engine_page import render_growth_engine
from cdms.config.settings import settings


def main():
    # Seletor na barra lateral
    st.sidebar.title("Creator Suite")
    modulo = st.sidebar.radio(
        "Navegação",
        ["🎯 CDMS (Governança e Ritual)", "🚀 CGS (Growth e Funil)"],
        index=0,
    )

    if modulo == "🎯 CDMS (Governança e Ritual)":
        render_cdms()
    else:
        render_growth_engine(db_path=str(settings.DB_PATH))


if __name__ == "__main__":
    main()