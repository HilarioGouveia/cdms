"""
Camada de Adaptadores (Adapters) do CDMS.

Contém os adaptadores conduzidos (Driven Adapters, como persistência em SQLite)
e adaptadores condutores (Driving Adapters, como a interface de utilizador Streamlit).
"""

from cdms.adapters.persistence.sqlite_repo import SQLiteRepository
from cdms.adapters.ui.streamlit_app import run_app

__all__ = [
    "SQLiteRepository",
    "run_app",
]