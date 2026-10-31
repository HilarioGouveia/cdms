"""Studio com sessão autenticada por workspace e modo local explícito."""
from datetime import date, timedelta
from html import escape
from pathlib import Path

import streamlit as st

from cdms.adapters.ui.studio_workspaces import (
    LOCAL, DEMO, initialize_workspace, switch_workspace, workspace_container,
)
from cgs.adapters.persistence.sqlite_growth_repo import SQLiteGrowthRepository
from cgs.domain.entities.hypothesis import HypothesisStatus
from cdms.adapters.ui.components.identity import money, render_tag as cockpit_tag


SECTIONS = {
    "Cockpit": "space_dashboard",
    "Governança": "fact_check",
    "Experimentos": "science",
}

PAGES = {
    "Configurações": {
        "users": ("Gerenciar usuários", "manage_accounts"),
        "integrations": ("Integrações", "hub"),
    },
    "Governança": {
        "ritual": ("Ritual semanal", "fact_check"),
        "history": ("Histórico e tendências", "monitoring"),
        "export": ("Exportar resumo", "description"),
        "calibration": ("Calibrações", "tune"),
    },
    "Experimentos": {
        "diagnosis": ("Diagnóstico do funil", "analytics"),
        "backlog": ("Backlog e hipóteses", "science"),
        "budget": ("Orçamento dos testes", "account_balance_wallet"),
        "ab_evaluation": ("Avaliação A/B", "compare_arrows"),
        "baseline": ("Baseline do funil", "tune"),
        "report": ("Relatório executivo", "description"),
    },
    "Demonstração": {
        "demo_data": ("Dados de demonstração", "database"),
        "demo_catalog": ("Catálogo de cenários", "grid_view"),
    },
}

PAGE_DESCRIPTIONS = {
    "integrations": "Conecte contas Meta Ads e configure a coleta semanal de métricas.",
    "budget": "Defina o limite do ciclo, aloque recursos e acompanhe os gastos por hipótese.",
    "ab_evaluation": "Compare controle e tratamento com probabilidade de ganho e incerteza.",
    "users": "Cadastre pessoas e gerencie perfis e acessos ao workspace.",
    "demo_data": "Prepare um ambiente simulado para apresentar os fluxos do CDMS.",
    "demo_catalog": "Explore as combinações heurísticas sem alterar dados.",
    "ritual": "Uma decisão prioritária, com hipótese, critério e prazo.",
    "history": "Acompanhe a evolução das métricas e os aprendizados de cada ciclo.",
    "export": "Exporte o registro da decisão e suas evidências.",
    "calibration": "Defina as faixas de referência para classificar as métricas.",
    "diagnosis": "Identifique o gargalo do funil e estime a oportunidade recuperável.",
    "backlog": "Priorize hipóteses e acompanhe os experimentos por variável.",
    "baseline": "Defina as referências comerciais para o diagnóstico do funil.",
    "report": "Consolide diagnósticos, experimentos e decisões do ciclo.",
}


def navigate(section, page=None):
    st.session_state.studio_section = section
    st.session_state.studio_explorer = True
    if page is not None:
        st.session_state[f"studio_page_{section}"] = page
        if section == "Experimentos" and page == "diagnosis":
            st.session_state["growth_diagnosis_tab"] = "Diagnóstico do ciclo"


def open_cycle_story(cycle):
    st.session_state["growth_selected_cycle"] = cycle
    st.session_state["growth_report_tab"] = "Storytelling"
    navigate("Experimentos", "report")


def select_page(section, page):
    st.session_state[f"studio_page_{section}"] = page


def toggle(key):
    st.session_state[key] = not st.session_state[key]


def sync_cycle(source, target):
    st.session_state[target] = st.session_state[source]


def render_context_controls(session, *, mobile=False):
    if session:
        from cdms.adapters.ui.studio_auth import render_workspace_selector
        render_workspace_selector(session, 'mobile_account_workspace' if mobile else 'account_workspace')
    elif not mobile:
        st.selectbox('Workspace', [LOCAL, DEMO], key='studio_workspace', on_change=switch_workspace)
    else:
        st.selectbox('Workspace', [LOCAL, DEMO], index=[LOCAL, DEMO].index(st.session_state.studio_workspace),
                     key='mobile_workspace', on_change=sync_local_workspace)
    key, other = ('mobile_studio_cycle', 'studio_cycle') if mobile else ('studio_cycle', 'mobile_studio_cycle')
    st.session_state.setdefault(key, st.session_state['studio_cycle'])
    st.date_input('Ciclo de referência do Cockpit', key=key, on_change=sync_cycle, args=(key, other))


def sync_local_workspace():
    st.session_state['studio_workspace'] = st.session_state['mobile_workspace']
    switch_workspace()


def render_statusbar(is_demo, cycle, rules_version, session=None):
    """Report only known local state; no inferred API/telemetry health."""
    context = session.workspace_name if session else ("DEMO · DADOS SIMULADOS" if is_demo else "Local")
    connection = "● Sessão autenticada" if session else "● Modo local"
    with st.container(key="studio_statusbar"):
        st.html(
            '<div class="studio-status" role="status" aria-live="polite">'
            '<span class="studio-status-connections">'
            f'<span>{connection}</span><span class="studio-status-telemetry"> · Telemetria não configurada</span></span>'
            '<span class="studio-status-execution">Painel carregado</span>'
            f'<span class="studio-status-context">{escape(context)}'
            f'<span class="studio-status-cycle"> · Ciclo {cycle:%d/%m/%Y}</span>'
            f' · Regras v{escape(str(rules_version))}</span></div>'
        )




def render_cockpit(core, growth, cycle):
    audit = growth.get_funnel_audit(cycle)
    ritual = core.repository.get_ritual_by_cycle(cycle)
    backlog = growth.list_hypotheses(status=HypothesisStatus.PENDING, limit=3)
    bottlenecks = {
        "NONE": "Nenhum gargalo crítico", "ATTENTION": "Atenção · exposição",
        "INTENTION": "Intenção · CTR", "CONVERSION": "Conversão · venda",
        "LEAD_CAPTURE": "Captura de leads", "LEAD_CLOSING": "Fechamento comercial",
    }
    scenarios = {
        "PRE_DROP": ("Risco de queda", "amber"), "ANOMALY": ("Assimetria crítica", "coral"),
        "SCALE": ("Potencial de escala", "mint"), "STABILITY": ("Estabilidade", "cobalt"),
        "INCONCLUSIVE": ("Inconclusivo", "violet"),
    }
    with st.container(key="cockpit_overview"):
        st.caption("CDMS / INTELIGÊNCIA DE DECISÃO")
        st.title("Decision Cockpit")
        st.write("Uma decisão de cada vez. Evidência, hipótese e critério no mesmo ciclo.")
        with st.container(horizontal=True, key="cockpit_context"):
            cockpit_tag(f"Ciclo {date.fromisoformat(cycle):%d/%m/%Y}")
            cockpit_tag("Diagnóstico salvo" if audit else "Diagnóstico pendente", "mint" if audit else "neutral")
            cockpit_tag("Ritual registrado" if ritual else "Ritual pendente", "cobalt" if ritual else "neutral")

        with st.container(key="studio_opportunity"):
            st.caption("01 / DIAGNÓSTICO FINANCEIRO")
            if audit:
                st.metric("Oportunidade recuperável estimada", money(audit.total_opportunity_reais))
                st.caption("Estimativa do diagnóstico salvo; não representa receita realizada.")
                cockpit_tag(bottlenecks.get(audit.primary_bottleneck.value, audit.primary_bottleneck.value),
                            "mint" if audit.primary_bottleneck.value == "NONE" else "amber")
            else:
                st.subheader("O ciclo ainda não tem diagnóstico")
                st.write("Registre o funil para identificar o gargalo e estimar a oportunidade recuperável.")
            st.button("Abrir diagnóstico", icon=":material/analytics:",
                      on_click=navigate, args=("Experimentos", "diagnosis"), key="studio_open_growth")

        with st.container(key="cockpit_decision"):
            st.caption("02 / GOVERNANÇA DA DECISÃO")
            if ritual:
                label, tone = scenarios[ritual.scenario.type.value]
                cockpit_tag(label, tone)
                st.subheader(ritual.decision.summary)
                st.write(ritual.decision.hypothesis)
                with st.container(key="cockpit_criterion"):
                    st.caption("CRITÉRIO DE SUCESSO")
                    st.write(ritual.decision.success_criterion)
                    st.caption(f"Avaliação em {ritual.decision.evaluation_due_date:%d/%m/%Y} · Responsável: {ritual.decision.owner}")
            else:
                st.subheader("Defina o próximo movimento")
                st.write("Consolide as evidências e registre uma decisão com hipótese, critério e prazo.")
            st.button("Abrir ritual", on_click=navigate, args=("Governança", "ritual"),
                      key="studio_open_ritual", icon=":material/fact_check:")

        st.button("Ver narrativa do ciclo", icon=":material/auto_stories:",
                  key="cockpit_open_story", on_click=open_cycle_story, args=(cycle,))

        with st.container(key="cockpit_backlog"):
            st.caption("03 / EXPERIMENTAÇÃO")
            st.subheader("Hipóteses priorizadas")
            st.caption("Até três pendências do workspace, ordenadas por ICE. A promoção depende do ritual.")
            if not backlog:
                st.write("Nenhuma hipótese pendente. Crie a primeira em Experimentos.")
            for hypothesis in backlog:
                with st.container(key=f"cockpit_hypothesis_{hypothesis.id}"):
                    with st.container(horizontal=True):
                        tone = {"HOOK": "violet", "OFFER": "amber", "CTA": "cobalt"}.get(hypothesis.tested_variable.value, "neutral")
                        cockpit_tag(hypothesis.tested_variable.value.replace("_", " "), tone)
                        cockpit_tag(f"ICE {hypothesis.ice_score}")
                    st.write(hypothesis.action_description)
                    st.caption(f"Proposta para {hypothesis.target_cycle_id} · aguarda ritual" if hypothesis.target_cycle_id
                               else "Sem ciclo reservado · aguarda priorização")
            st.button("Explorar backlog", icon=":material/science:", on_click=navigate,
                      args=("Experimentos", "backlog"), key="cockpit_open_backlog")


def run_studio():
    st.set_page_config(page_title="CDMS Studio · Decision Cockpit",
                       page_icon=":material/space_dashboard:", layout="wide")
    from cdms.adapters.ui.theme import apply_shell_theme
    apply_shell_theme()
    st.html(Path(__file__).parent / "styles" / "studio.css")
    from cdms.adapters.ui.studio_auth import require_session, render_account, session_container
    from cdms.domain.entities.tenant import UserRole
    session = require_session()
    if session:
        apply_shell_theme()
    else:
        initialize_workspace()
    defaults = {"studio_section": "Cockpit", "studio_explorer": True,
                "studio_evidence": False, "studio_page_Governança": "ritual",
                "studio_page_Experimentos": "diagnosis", "studio_page_Demonstração": "demo_data"}
    defaults['studio_page_Configurações'] = 'users'
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    # Retain draft widgets when their module is not rendered. Do not retain
    # ephemeral buttons, uploads, or external credentials.
    draft_prefixes = (
        "dec_", "val_", "avail_", "reason_", "custom_reason_", "cal_",
        "growth_", "ritual_learning_",
        "experiment_draft_",
    )
    for key in list(st.session_state):
        if key.startswith(draft_prefixes) or key in (
            "cycle_week_start", "proposal_cycle", "ritual_proposal",
        ):
            st.session_state[key] = st.session_state[key]

    core = session_container(session) if session else workspace_container()
    is_demo = session is None and st.session_state.studio_workspace == DEMO
    pages={section:dict(items) for section,items in PAGES.items()}
    if is_demo:
        pages['Configurações']={'integrations':PAGES['Configurações']['integrations']}
        st.session_state['studio_page_Configurações']='integrations'
    read_only = session is not None and session.tenant.role == UserRole.VIEWER
    sections = {**SECTIONS, "Demonstração": "science"} if is_demo else SECTIONS
    if is_demo or (session and session.tenant.role in (UserRole.OWNER, UserRole.ADMIN)):
        sections = {**sections, 'Configurações': 'settings'}
    growth = SQLiteGrowthRepository(str(core.settings.DB_PATH))
    today = date.today()
    st.session_state.setdefault('studio_cycle', today - timedelta(days=today.weekday()))
    # Keep the chosen cycle when the desktop explorer is collapsed.
    st.session_state['studio_cycle'] = st.session_state['studio_cycle']
    cycle = st.session_state['studio_cycle']
    st.session_state['mobile_studio_cycle'] = cycle
    if not session:
        st.session_state['studio_workspace'] = st.session_state['studio_workspace']
        st.session_state['mobile_workspace'] = st.session_state['studio_workspace']
    with st.container(key="studio_titlebar", horizontal=True):
        st.markdown(":material/space_dashboard: **CDMS STUDIO · DADOS SIMULADOS**" if is_demo else ":material/space_dashboard: **CDMS STUDIO**")
        st.caption(session.workspace_name if session else ("Workspace CDMS Demo" if is_demo else "Workspace local / Decision Cockpit"))
        st.space("stretch")
        st.button("Evidências", icon=":material/right_panel_close:" if st.session_state.studio_evidence else ":material/right_panel_open:",
                  type='primary' if st.session_state.studio_evidence else 'secondary',
                  key="studio_toggle_evidence", on_click=toggle, args=("studio_evidence",))

        # Small-screen ritual uses popovers rather than stacking the side panes.
        with st.container(key="studio_mobile_tools", horizontal=True, width="content"):
            with st.popover("Seções", icon=":material/menu:"):
                render_context_controls(session, mobile=True)
                active_section = st.session_state.studio_section
                for target_page, (label, icon) in pages.get(active_section, {}).items():
                    st.button(label, icon=f":material/{icon}:", key=f"mobile_page_{target_page}",
                              on_click=select_page, args=(active_section, target_page), width="stretch")
            st.button('Evidências',icon=':material/article:',key='mobile_evidence',
                      on_click=toggle,args=('studio_evidence',))

        if session:
            render_account(session)

    if session and st.session_state.get('_account_page'):
        from cdms.adapters.ui.studio_auth import auth_service
        from cdms.adapters.ui.studio_users import password_form
        with st.container(key='studio_editor'):
            if st.button('Voltar ao painel', key='account_back'):
                st.session_state.pop('_account_page', None)
                st.rerun()
            password_form(auth_service(), session)
        st.stop()

    weights = [0.5] + ([2.15] if st.session_state.studio_explorer else []) + [6]
    with st.container(key="studio_workbench", gap=None):
        panels = iter(st.columns(weights, gap=None))
    dock = next(panels)
    explorer = next(panels) if st.session_state.studio_explorer else None
    editor = next(panels)
    with dock, st.container(key="studio_dock"):
        st.button("Navegação", icon=":material/left_panel_close:" if st.session_state.studio_explorer else ":material/left_panel_open:",
                  help="Recolher navegação" if st.session_state.studio_explorer else "Expandir navegação",
                  key="studio_toggle_explorer", on_click=toggle, args=("studio_explorer",), width="stretch")
        for section, icon in sections.items():
            st.button(section, icon=f":material/{icon}:", help=section,
                      type="primary" if st.session_state.studio_section == section else "secondary",
                      key=f"studio_nav_{section}", on_click=navigate, args=(section,), width="stretch")
    if explorer is not None:
        with explorer, st.container(key="studio_explorer_panel"):
            render_context_controls(session)
            st.divider()
            section = st.session_state.studio_section
            st.caption(section.upper() if section in pages else "ESPAÇO DE TRABALHO")
            with st.container(border=True):
                if section in pages:
                    for page, (label, icon) in pages[section].items():
                        st.button(label, icon=f":material/{icon}:",
                                  type="primary" if st.session_state[f"studio_page_{section}"] == page else "tertiary",
                                  key=f"studio_page_{page}", on_click=select_page,
                                  args=(section, page), width="stretch")
                else:
                    st.markdown(":material/space_dashboard: **Visão do ciclo**")
            descriptions = {
                "Demonstração": "Pacotes simulados e catálogo de cenários para apresentação.",
                "Cockpit": "Visão do ciclo, oportunidade estimada e próximas decisões.",
                "Governança": "Ritual semanal, histórico, exportação e calibrações.",
                "Experimentos": "Diagnóstico do funil, backlog ICE, baseline e relatório.",
                "Configurações": "Usuários, perfis e permissões do workspace.",
            }
            st.write(descriptions[st.session_state.studio_section])
    with editor, st.container(key="studio_editor"):
        if cycle.weekday() != 0:
            st.error('Selecione uma segunda-feira para o ciclo do Cockpit.')
            return
        section = st.session_state.studio_section
        if section in pages:
            page = st.session_state[f"studio_page_{section}"]
            with st.container(key="studio_page_heading"):
                st.caption(f"CDMS / {section.upper()}")
                st.subheader(pages[section][page][0])
                st.caption(PAGE_DESCRIPTIONS[page])
        if read_only and ((section == "Governança" and page in {"ritual", "calibration"})
                          or (section == "Experimentos" and page in {"diagnosis", "baseline"})):
            st.info("Seu perfil permite somente leitura. Consulte o Cockpit, histórico, backlog e relatórios.")
        elif read_only and section == "Experimentos" and page == "backlog":
            st.info("Acesso somente de leitura.")
            hypotheses = growth.list_hypotheses(limit=500)
            if not hypotheses:
                st.write("Nenhuma hipótese registrada neste workspace.")
            for hypothesis in hypotheses:
                with st.container(border=True):
                    st.write(hypothesis.action_description)
                    st.caption(f"{hypothesis.status.value} · {hypothesis.tested_variable.value} · ICE {hypothesis.ice_score}")
                    from cdms.adapters.ui.evidence_panel import inspect_hypothesis
                    st.button('Ver evidências',key=f'viewer_evidence_{hypothesis.id}',
                              on_click=inspect_hypothesis,args=(hypothesis.id,))
        elif section == 'Configurações':
            if session or is_demo:
                if page == 'integrations':
                    from cdms.adapters.ui.platform_ingestion_page import render_integrations
                    render_integrations(core,session)
                else:
                    from cdms.adapters.ui.studio_auth import auth_service
                    from cdms.adapters.ui.studio_users import render_users
                    render_users(auth_service(), session)
            else:
                st.info('Entre com uma conta para gerenciar usuários.')
        elif section == "Cockpit":
            render_cockpit(core, growth, cycle.isoformat())
            from cgs.adapters.persistence.sqlite_cgs_fase2_repo import SQLiteCGSPhase2Repository
            finance=SQLiteCGSPhase2Repository(core.settings.DB_PATH)
            budgets=finance.list_budgets_by_cycle(cycle.isoformat())
            with st.container(border=True):
                st.subheader('Investimento em experimentos')
                allocated=sum(b.allocated_amount_cents for b in budgets)/100
                spent=sum(b.spent_amount_cents for b in budgets)/100
                st.write(f'Comprometido: R$ {allocated:,.2f} · Gasto: R$ {spent:,.2f} · Teto: R$ {finance.get_cycle_limit(cycle.isoformat())/100:,.2f}')
                if spent > allocated:
                    st.warning('Gasto acima do orçamento alocado.')
                st.button('Abrir orçamento',on_click=navigate,args=('Experimentos','budget'),key='cockpit_budget')
                evaluations=finance.cycle_evaluations(cycle.isoformat())
                if evaluations:
                    st.write('Últimas avaliações A/B do ciclo')
                    st.dataframe([{'Hipótese':e.hypothesis_id,'Probabilidade de ganho (%)':float(e.probability_to_beat_control),
                                   'Amostra suficiente':e.verdict.value!='INCONCLUSIVE_INSUFFICIENT_SAMPLE',
                                   'Data':e.evaluated_at.isoformat()} for e in evaluations],hide_index=True)
                    st.button('Revisar avaliações A/B',on_click=navigate,args=('Experimentos','ab_evaluation'),key='cockpit_ab')
            from cdms.adapters.ui.platform_ingestion_page import render_imports
            render_imports(core,session,cycle.isoformat())
        elif section == "Governança":
            from cdms.adapters.ui.streamlit_app import run_app
            run_app(embedded=True, section=page, container=core)
        elif section == "Demonstração":
            from cdms.adapters.ui.demo_page import render_demo_data, render_demo_catalog
            with st.container(key="studio_demo"):
                if page == "demo_catalog":
                    render_demo_catalog()
                else:
                    render_demo_data()
        elif section == 'Experimentos' and page in {'budget','ab_evaluation'}:
            from cgs.adapters.ui.experiment_finance_page import render_experiment_finance
            render_experiment_finance(core,growth,cycle.isoformat(),page,session)
        else:
            from cgs.adapters.ui.growth_engine_page import render_growth_engine
            render_growth_engine(db_path=str(core.settings.DB_PATH), section=page)
    if st.session_state.studio_evidence:
        from cdms.adapters.ui.evidence_panel import render_evidence
        with st.container(key='studio_evidence_panel'):
            render_evidence(core,growth,cycle.isoformat(),session)
    render_statusbar(is_demo, cycle, core.settings.RULES_VERSION, session)
