import sys
import os

# Adiciona o diretório 'src' ao sys.path para garantir discovery de módulos
sys.path.insert(0, os.path.abspath("src"))

from cdms.adapters.ui.streamlit_app import run_app

if __name__ == "__main__":
    run_app()