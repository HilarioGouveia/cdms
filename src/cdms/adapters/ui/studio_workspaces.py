"""Dois contextos locais, sem confundir demonstração com tenants da API."""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import streamlit as st

from cdms.application.demo_data import create_demo_bundle, demo_settings, new_demo_path
from cdms.config.container import Container, get_container
from cgs.adapters.persistence.sqlite_growth_repo import SQLiteGrowthRepository
from cgs.domain.entities.funnel import ConversionType, FunnelBaseline


LOCAL = "Local · CDMS"
DEMO = "CDMS Demo"
SCOPED_PREFIXES = ("dec_", "val_", "avail_", "reason_", "custom_reason_", "cal_", "growth_",
                   "ritual_learning_", "_ritual_")
SCOPED_KEYS = {"cycle_week_start", "ritual_proposal", "ritual_step_selector", "_decision_form_source",
               "parsed_metrics_dto", "active_calibs", "active_calibs_list", "reload_calibs",
               "studio_cycle", "studio_section", "studio_page_Governança",
               "studio_page_Experimentos", "studio_page_Demonstração"}


def scoped_keys():
    return [key for key in st.session_state if key.startswith(SCOPED_PREFIXES) or key in SCOPED_KEYS]


def initialize_workspace():
    st.session_state.setdefault("studio_workspace", LOCAL)
    st.session_state.setdefault("_studio_active_workspace", st.session_state.studio_workspace)


def switch_workspace():
    target = st.session_state.studio_workspace
    previous = st.session_state["_studio_active_workspace"]
    if target not in (LOCAL, DEMO):
        raise ValueError("Workspace local desconhecido.")
    if target == previous:
        return
    banks = st.session_state.setdefault("_studio_workspace_drafts", {})
    keys = scoped_keys()
    banks[previous] = deepcopy({key: st.session_state[key] for key in keys})
    for key in keys:
        del st.session_state[key]
    st.session_state.update(deepcopy(banks.get(target, {})))
    st.session_state["_studio_active_workspace"] = target
    if target == DEMO and target not in banks:
        st.session_state["studio_section"] = "Demonstração"
        st.session_state["studio_page_Demonstração"] = "demo_data"


def workspace_container():
    if st.session_state.studio_workspace not in (LOCAL, DEMO):
        raise ValueError("Workspace local desconhecido.")
    local = get_container()
    if st.session_state.studio_workspace == LOCAL:
        st.session_state["_studio_upload_scope"] = "local"
        return local
    st.session_state.setdefault("_demo_session_id", uuid4().hex)
    if "_demo_container" not in st.session_state:
        path = new_demo_path(local.settings, st.session_state["_demo_session_id"])
        st.session_state["_demo_container"] = Container(app_settings=demo_settings(local.settings, path))
    demo = st.session_state["_demo_container"]
    st.session_state["_studio_upload_scope"] = demo.settings.DB_PATH.stem
    return demo


def present_cycle(row):
    if st.session_state.studio_workspace != DEMO:
        raise ValueError("Os exemplos só podem ser aplicados ao CDMS Demo.")
    core = workspace_container()
    baseline = row["baseline"]
    is_lead = row["funnel"] == "LEAD"
    SQLiteGrowthRepository(str(core.settings.DB_PATH)).save_baseline(FunnelBaseline(
        ticket_price=Decimal(baseline["ticket"]), expected_ctr_pct=Decimal(baseline["ctr"]),
        expected_conversion_rate_pct=Decimal(baseline["conversion"]),
        conversion_type=ConversionType(row["funnel"]),
        lead_to_sale_rate_pct=Decimal(baseline["lead_to_sale"]) if is_lead else None,
    ))
    st.session_state.update({
        "studio_cycle": date.fromisoformat(row["cycle"]), "studio_section": "Cockpit",
        "growth_source_cycle": date.fromisoformat(row["cycle"]),
        "growth_impressions": row["inputs"]["impressions"], "growth_clicks": row["inputs"]["clicks"],
        "growth_conversions": row["inputs"]["conversions"], "growth_conversions_2": row["inputs"]["conversions"],
        "growth_leads": row["inputs"]["leads"] or 0, "growth_selected_type": row["funnel"],
        "growth_t_price": float(baseline["ticket"]), "growth_e_ctr": float(baseline["ctr"]),
        "growth_e_conv": float(baseline["conversion"]), "growth_e_conv_2": float(baseline["conversion"]),
        "growth_e_lead_sale": float(baseline["lead_to_sale"] or "10"),
        "growth_selected_cycle": row["cycle"], "growth_diagnosis_tab": "Diagnóstico do ciclo",
    })


def load_demo(restore=False):
    if st.session_state.studio_workspace != DEMO:
        return
    previous = st.session_state.get("_demo_manifest")
    today = date.today()
    anchor = date.fromisoformat(previous["anchor"]) if restore and previous else today - timedelta(days=today.weekday())
    package = previous["package"] if restore and previous else st.session_state["demo_package"]
    try:
        bundle = create_demo_bundle(get_container().settings, st.session_state["_demo_session_id"], anchor, package)
        st.session_state.pop("_demo_error", None)
        for key in scoped_keys():
            del st.session_state[key]
        st.session_state.get("_studio_workspace_drafts", {}).pop(DEMO, None)
        st.session_state["_demo_manifest"] = bundle.manifest
        st.session_state["_demo_container"] = Container(app_settings=demo_settings(get_container().settings, bundle.db_path))
        st.session_state["demo_package"] = package
        present_cycle(bundle.manifest["cycles"][-1])
        st.session_state.update({"studio_section": "Demonstração", "studio_page_Demonstração": "demo_catalog" if package == "Cobertura completa" else "demo_data",
                                 "cycle_week_start": anchor, "_demo_notice": "Pacote inicial restaurado." if restore else "Pacote de demonstração carregado."})
    except Exception as error:
        st.session_state["_demo_error"] = str(error)
