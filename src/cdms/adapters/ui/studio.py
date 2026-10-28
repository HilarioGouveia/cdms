"""Studio local: navegação e evidências ao redor dos fluxos CDMS/CGS existentes.

O workspace local não representa um tenant autenticado. Somente a futura
interface de API poderá selecionar organizações e permissões de usuários.
"""
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

from cdms.config.container import get_container
from cgs.adapters.persistence.sqlite_growth_repo import SQLiteGrowthRepository
from cgs.domain.entities.hypothesis import HypothesisStatus


SECTIONS = {
    "Cockpit": "space_dashboard",
    "Governança": "fact_check",
    "Experimentos": "science",
}

PAGES = {
    "Governança": {
        "ritual": ("Ritual semanal", "fact_check"),
        "history": ("Histórico e tendências", "monitoring"),
        "export": ("Exportar resumo", "description"),
        "calibration": ("Calibrações", "tune"),
    },
    "Experimentos": {
        "diagnosis": ("Diagnóstico do funil", "analytics"),
        "backlog": ("Backlog e hipóteses", "science"),
        "baseline": ("Baseline do funil", "tune"),
        "report": ("Relatório executivo", "description"),
    },
}


def navigate(section, page=None):
    st.session_state.studio_section = section
    st.session_state.studio_explorer = True
    if page is not None:
        st.session_state[f"studio_page_{section}"] = page


def select_page(section, page):
    st.session_state[f"studio_page_{section}"] = page


def toggle(key):
    st.session_state[key] = not st.session_state[key]


def money(value):
    return "R$ " + f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def render_cockpit(core, growth, cycle):
    st.caption("DECISION COCKPIT / VISÃO DO CICLO")
    st.title("Uma decisão de cada vez")
    st.write("Diagnóstico, experimentação e governança no mesmo espaço de trabalho.")
    audit = growth.get_funnel_audit(cycle)
    ritual = core.repository.get_ritual_by_cycle(cycle)
    with st.container(border=True, key="studio_opportunity"):
        st.caption("OPORTUNIDADE ESTIMADA")
        if audit:
            st.metric("Potencial recuperável", money(audit.total_opportunity_reais))
            st.write(f"Gargalo primário: **{audit.primary_bottleneck.value}**")
            st.caption("Estimativa do diagnóstico salvo; não representa receita realizada.")
        else:
            st.subheader("O ciclo ainda não tem diagnóstico")
            st.write("Configure a baseline e registre o funil em Experimentos.")
        st.button("Abrir diagnóstico", icon=":material/analytics:",
                  on_click=navigate, args=("Experimentos", "diagnosis"), key="studio_open_growth")
    left, right = st.columns(2)
    with left, st.container(border=True):
        st.subheader("Governança semanal")
        if ritual:
            st.write(f"Ritual registrado · **{ritual.scenario.type.value}**")
            st.write(ritual.decision.summary)
        else:
            st.write("Ritual ainda não registrado para este ciclo.")
        st.button("Abrir ritual", on_click=navigate, args=("Governança", "ritual"),
                  key="studio_open_ritual", icon=":material/fact_check:")
    with right, st.container(border=True):
        st.subheader("Backlog priorizado")
        st.caption("Pendências do workspace · ordenadas por ICE")
        backlog = growth.list_hypotheses(status=HypothesisStatus.PENDING, limit=3)
        if not backlog:
            st.write("Nenhuma hipótese pendente. Crie a primeira em Experimentos.")
        for hypothesis in backlog:
            st.write(f"**{hypothesis.tested_variable.value} · ICE {hypothesis.ice_score}**")
            st.write(hypothesis.action_description)
            if hypothesis.target_cycle_id:
                st.caption(f"Proposta para {hypothesis.target_cycle_id} · aguarda ritual")


def run_studio():
    st.set_page_config(page_title="CDMS Studio · Decision Cockpit",
                       page_icon=":material/space_dashboard:", layout="wide")
    st.html(Path(__file__).parent / "styles" / "studio.css")
    defaults = {"studio_section": "Cockpit", "studio_explorer": True,
                "studio_evidence": True, "studio_page_Governança": "ritual",
                "studio_page_Experimentos": "diagnosis"}
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    # Retain draft widgets when their module is not rendered. Do not retain
    # ephemeral buttons, uploads, or external credentials.
    draft_prefixes = (
        "dec_", "val_", "avail_", "reason_", "custom_reason_", "cal_",
        "growth_", "ritual_learning_",
    )
    for key in list(st.session_state):
        if key.startswith(draft_prefixes) or key in (
            "cycle_week_start", "proposal_cycle", "ritual_proposal",
        ):
            st.session_state[key] = st.session_state[key]

    core = get_container()
    growth = SQLiteGrowthRepository(str(core.settings.DB_PATH))
    with st.container(key="studio_titlebar", horizontal=True):
        st.markdown(":material/space_dashboard: **CDMS STUDIO**")
        st.caption("Workspace local / Decision Cockpit")
        st.space("stretch")
        st.button("Navegação", icon=":material/left_panel_close:",
                  key="studio_toggle_explorer", on_click=toggle, args=("studio_explorer",))
        st.button("Evidências", icon=":material/right_panel_close:",
                  key="studio_toggle_evidence", on_click=toggle, args=("studio_evidence",))

        with st.popover("Workspace e ciclo", icon=":material/workspaces:"):
            st.selectbox("Workspace", ["Local · CDMS"], disabled=True,
                         help="Banco local existente. A seleção de organizações pela API será integrada em outra etapa.")
            today = date.today()
            cycle = st.date_input("Ciclo de referência do Cockpit",
                                 value=today - timedelta(days=today.weekday()), key="studio_cycle")
            st.caption("Modo local · sem autenticação · dados deste ambiente")
    if cycle.weekday() != 0:
        st.error("Selecione uma segunda-feira para o ciclo do Cockpit.")
        return
    weights = [0.5] + ([2.15] if st.session_state.studio_explorer else []) + [6]
    if st.session_state.studio_evidence:
        weights.append(3.2)
    with st.container(key="studio_workspace", gap=None):
        panels = iter(st.columns(weights, gap=None))
    dock = next(panels)
    explorer = next(panels) if st.session_state.studio_explorer else None
    editor = next(panels)
    evidence = next(panels) if st.session_state.studio_evidence else None
    with dock, st.container(key="studio_dock"):
        for section, icon in SECTIONS.items():
            st.button(section, icon=f":material/{icon}:", help=section,
                      type="primary" if st.session_state.studio_section == section else "secondary",
                      key=f"studio_nav_{section}", on_click=navigate, args=(section,), width="stretch")
    if explorer is not None:
        with explorer, st.container(key="studio_explorer_panel"):
            section = st.session_state.studio_section
            st.caption(section.upper() if section in PAGES else "ESPAÇO DE TRABALHO")
            with st.container(border=True):
                st.markdown(":material/folder_open: **Local · CDMS**")
                st.divider()
                if section in PAGES:
                    for page, (label, icon) in PAGES[section].items():
                        st.button(label, icon=f":material/{icon}:",
                                  type="primary" if st.session_state[f"studio_page_{section}"] == page else "tertiary",
                                  key=f"studio_page_{page}", on_click=select_page,
                                  args=(section, page), width="stretch")
                else:
                    st.markdown(":material/space_dashboard: **Visão do ciclo**")
            st.caption(f"Ciclo de referência · {cycle:%d/%m/%Y}")
            descriptions = {
                "Cockpit": "Visão do ciclo, oportunidade estimada e próximas decisões.",
                "Governança": "Ritual semanal, histórico, exportação e calibrações.",
                "Experimentos": "Diagnóstico do funil, backlog ICE, baseline e relatório.",
            }
            st.write(descriptions[st.session_state.studio_section])
    with editor, st.container(key="studio_editor"):
        section = st.session_state.studio_section
        if section in PAGES:
            page = st.session_state[f"studio_page_{section}"]
            st.caption(f"{section} / {PAGES[section][page][0]}")
        if section == "Cockpit":
            render_cockpit(core, growth, cycle.isoformat())
        elif section == "Governança":
            from cdms.adapters.ui.streamlit_app import run_app
            run_app(embedded=True, section=page)
        else:
            from cgs.adapters.ui.growth_engine_page import render_growth_engine
            render_growth_engine(db_path=str(core.settings.DB_PATH), section=page)
    if evidence is not None:
        with evidence, st.container(key="studio_evidence_panel"):
            st.subheader("Evidências do ciclo")
            st.caption(cycle.isoformat())
            audit = growth.get_funnel_audit(cycle.isoformat())
            if audit:
                st.write(audit.diagnosis_summary)
                st.caption(f"Cálculo v{audit.calculation_version}")
            else:
                st.write("Nenhum diagnóstico salvo para este ciclo.")
            st.divider()
            st.caption("Assistente ainda não conectado. Este painel exibe evidências persistidas.")
    with st.container(key="studio_statusbar", horizontal=True):
        st.caption(f"Local · Regras v{core.settings.RULES_VERSION}")
        st.caption("Integração Meta Ads disponível pela API · leitura de métricas")
