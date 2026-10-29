"""Testes da interface real com banco temporário compartilhado por CDMS e CGS."""
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from cdms.config import container as container_module
from importlib import import_module
settings_module = import_module("cdms.config.settings")
from cgs.adapters.persistence.sqlite_growth_repo import SQLiteGrowthRepository

APP = Path(__file__).resolve().parents[2] / "app.py"


def widget(elements, label):
    return next(element for element in elements if element.label == label)


def assert_healthy(at):
    assert not at.exception, [e.message for e in at.exception]
    assert not at.error, [e.value for e in at.error]


def open_page(at, page):
    at.button(key=f"studio_page_{page}").click().run()
    assert_healthy(at)


def ritual_step(at, step):
    while at.session_state["_ritual_step"] != step:
        direction = "next" if at.session_state["_ritual_step"] < step else "previous"
        at.button(key=f"ritual_{direction}").click().run()
        assert_healthy(at)


@pytest.fixture
def ui(tmp_path, monkeypatch):
    config = replace(settings_module.settings, DATA_DIR=tmp_path, DB_PATH=tmp_path / "suite.db")
    monkeypatch.setattr(settings_module, "settings", config)
    monkeypatch.setattr(container_module, "settings", config)
    monkeypatch.setattr(container_module, "_container_instance", None)
    class FixedDate(date):
        @classmethod
        def today(cls):
            return date(2026, 11, 9)
    for module_name in (
        "cdms.adapters.ui.streamlit_app", "cgs.adapters.ui.growth_engine_page",
        "cdms.adapters.ui.components.decision_form",
    ):
        monkeypatch.setattr(import_module(module_name), "date", FixedDate)
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert_healthy(at)
    at.button(key="studio_nav_Governança").click().run()
    assert_healthy(at)
    return at, config.DB_PATH


@pytest.mark.parametrize("conversion_type", ["DIRECT_SALE", "LEAD"])
def test_navigation_and_calibrated_ritual(ui, conversion_type):
    at, db_path = ui
    open_page(at, "calibration")
    widget(at.button, "Salvar Novas Calibrações").click().run()
    assert_healthy(at)
    open_page(at, "ritual")
    ritual_step(at, 4)
    at.text_input(key="dec_summary").set_value("Testar CTA no início")
    at.text_area(key="dec_hypothesis").set_value("CTA cedo aumenta cliques")
    at.text_area(key="dec_criterion").set_value("CTR >= 4.5%")
    at.button(key="ritual_finish").click().run()
    assert_healthy(at)
    assert container_module.get_container().repository.list_rituals(limit=10)
    at.button(key="studio_nav_Experimentos").click().run()
    assert_healthy(at)
    assert not at.title
    assert any("Experimentos / Diagnóstico do funil" in item.value for item in at.markdown)
    open_page(at, "baseline")
    widget(at.selectbox, "Tipo de Conversão Comercial").set_value(conversion_type).run()
    assert_healthy(at)
    widget(at.button, "Salvar Baseline Ativa").click().run()
    assert_healthy(at)
    assert SQLiteGrowthRepository(str(db_path)).get_active_baseline() is not None
    open_page(at, "diagnosis")
    widget(at.button, "Executar Diagnóstico Financeiro").click().run()
    assert_healthy(at)
    assert len(SQLiteGrowthRepository(str(db_path)).list_funnel_audits()) == 1


@pytest.mark.parametrize("outcome, expected_status", [
    ("ACHIEVED", "COMPLETED"), ("NOT_ACHIEVED", "DISCARDED"),
])
def test_growth_proposal_ritual_and_audited_outcome(ui, outcome, expected_status):
    at, db_path = ui
    at.button(key="studio_nav_Experimentos").click().run()
    assert_healthy(at)
    open_page(at, "baseline")
    widget(at.button, "Salvar Baseline Ativa").click().run()
    assert_healthy(at)
    open_page(at, "diagnosis")
    widget(at.date_input, "Segunda-feira de Referência").set_value(date(2026, 11, 2))
    widget(at.button, "Executar Diagnóstico Financeiro").click().run()
    assert_healthy(at)
    open_page(at, "backlog")
    at.button(key="backlog_new_hypothesis").click().run()
    widget(at.text_input, "Ação Prática").set_value("Inserir CTA claro aos 5 segundos")
    widget(at.selectbox, "Variável Única").set_value("CTA")
    widget(at.button, "Adicionar ao Backlog").click().run()
    assert_healthy(at)
    growth = SQLiteGrowthRepository(str(db_path))
    hypothesis = growth.list_hypotheses()[0]
    at.date_input(key=f"growth_proposal_cycle_{hypothesis.id}").set_value(date(2026, 11, 2))
    at.button(key=f"btn_prop_{hypothesis.id}").click().run()
    assert_healthy(at)
    pending = growth.get_hypothesis_by_id(hypothesis.id)
    assert pending.status.value == "PENDING"
    assert pending.promoted_decision_id is None
    assert pending.target_cycle_id == "2026-11-02"

    at.button(key="studio_nav_Governança").click().run()
    assert_healthy(at)
    at.date_input(key="cycle_week_start").set_value(date(2026, 11, 2)).run()
    assert_healthy(at)
    ritual_step(at, 4)
    at.selectbox(key="ritual_proposal").set_value(hypothesis.id).run()
    assert_healthy(at)
    assert at.text_input(key="dec_summary").value == hypothesis.action_description
    at.button(key="ritual_finish").click().run()
    assert_healthy(at)
    active = growth.get_hypothesis_by_id(hypothesis.id)
    record = container_module.get_container().repository.get_ritual_by_cycle("2026-11-02")
    assert active.status.value == "ACTIVE"
    assert active.promoted_decision_id == record.decision.id
    assert record.decision.source_hypothesis_id == hypothesis.id

    at.date_input(key="cycle_week_start").set_value(date(2026, 11, 9)).run()
    assert_healthy(at)
    outcome_widget = widget(at.selectbox, "Resultado Observado:")
    outcome_widget.set_value((outcome, "✅ Meta Atingida" if outcome == "ACHIEVED" else "❌ Meta Não Atingida"))
    widget(at.text_area, "Evidências e Aprendizados Observados:").set_value("CTR medido na plataforma após sete dias")
    ritual_step(at, 4)
    at.text_input(key="dec_summary").set_value("Testar próximo gancho")
    at.text_area(key="dec_hypothesis").set_value("Gancho claro aumenta retenção")
    at.text_area(key="dec_criterion").set_value("Retenção >= 45%")
    at.button(key="ritual_finish").click().run()
    assert_healthy(at)
    assert growth.get_hypothesis_by_id(hypothesis.id).status.value == expected_status
    audited = container_module.get_container().repository.get_ritual_by_cycle("2026-11-09")
    assert audited.learning.target_decision_id == record.decision.id
    assert audited.learning.outcome.value == outcome
    at.button(key="studio_nav_Experimentos").click().run()
    assert_healthy(at)
    at.session_state["growth_backlog_tab"] = "Histórico"
    at.run()
    assert_healthy(at)
    assert any("Resultado auditado" in item.value for item in at.markdown)
    assert any("CTR medido na plataforma após sete dias" in item.value for item in at.markdown)
    open_page(at, "report")
    widget(at.selectbox, "Ciclo Alvo do Relatório").set_value("2026-11-02").run()
    assert_healthy(at)
    assert any(expected_status in element.value for element in at.markdown)


def test_ritual_validation_and_unavailable_metric(ui):
    at, db_path = ui
    ritual_step(at, 4)
    at.button(key="ritual_finish").click().run()
    assert not at.exception
    assert any("campos obrigatórios" in e.value for e in at.error)
    assert not container_module.get_container().repository.list_rituals()
    ritual_step(at, 2)
    at.checkbox(key="avail_ctr_pct").uncheck().run()
    assert_healthy(at)
    at.selectbox(key="reason_ctr_pct").set_value("TRACKING_ERROR")
    ritual_step(at, 4)
    at.text_input(key="dec_summary").set_value("Corrigir rastreamento")
    at.text_area(key="dec_hypothesis").set_value("Rastreamento correto permite medir cliques")
    at.text_area(key="dec_criterion").set_value("Eventos de clique validados")
    at.button(key="ritual_finish").click().run()
    assert_healthy(at)
    record = container_module.get_container().repository.list_rituals()[0]
    snapshot = next(s for s in record.snapshots if s.definition.key == "ctr_pct")
    assert not snapshot.is_available
    assert snapshot.unavailability_reason == "TRACKING_ERROR"
    assert record.scenario.type.value == "INCONCLUSIVE"


def test_four_high_cycles_render_drift_alert_and_all_metric_charts(ui):
    from cdms.adapters.ui.components.metric_inputs import CANONICAL_DEFINITIONS, DEFAULT_CALIBRATIONS
    from cdms.domain.entities.metric import MetricSnapshot
    at, _ = ui
    open_page(at, "calibration")
    widget(at.button, "Salvar Novas Calibrações").click().run()
    assert_healthy(at)
    snapshots = [
        MetricSnapshot(d, DEFAULT_CALIBRATIONS[d.key], DEFAULT_CALIBRATIONS[d.key].healthy_max + 1)
        for d in CANONICAL_DEFINITIONS
    ]
    for offset in range(4, 0, -1):
        start = date(2026, 11, 9) - timedelta(weeks=offset)
        container_module.get_container().run_weekly_ritual_use_case.execute(
            week_start=start, snapshots=snapshots, decision_summary="Testar novo gancho",
            decision_hypothesis="Gancho claro aumenta atenção", decision_success_criterion="Retenção >= 60%",
            decision_evaluation_due_date=start + timedelta(days=7),
        )
    open_page(at, "history")
    assert_healthy(at)
    assert any("Recalibração Assistida" in alert.value for alert in at.warning)
    assert len(at.get("vega_lite_chart")) == 4


def test_studio_preserves_ritual_draft_and_panel_toggles(ui):
    at, _ = ui
    ritual_step(at, 4)
    at.text_input(key="dec_summary").set_value("Rascunho do próximo teste").run()
    at.button(key="studio_nav_Cockpit").click().run()
    assert_healthy(at)
    assert any("Uma decisão de cada vez" in title.value for title in at.title)
    at.button(key="studio_toggle_explorer").click().run()
    at.button(key="studio_toggle_evidence").click().run()
    assert not at.session_state["studio_evidence"]
    at.button(key="studio_toggle_evidence").click().run()
    assert_healthy(at)
    assert not at.session_state["studio_explorer"]
    assert at.session_state["studio_evidence"]
    assert any("Evidências do ciclo" in item.value for item in at.subheader)
    at.button(key="studio_nav_Governança").click().run()
    assert_healthy(at)
    assert at.text_input(key="dec_summary").value == "Rascunho do próximo teste"


def test_contextual_sections_remember_selection_and_growth_draft(ui):
    at, _ = ui
    assert not at.tabs
    assert not any(button.label == "Salvar Novas Calibrações" for button in at.button)
    ritual_step(at, 4)
    at.text_input(key="dec_summary").set_value("Rascunho preservado").run()
    open_page(at, "calibration")
    assert not any(item.key == "dec_summary" for item in at.text_input)
    at.button(key="studio_nav_Experimentos").click().run()
    open_page(at, "backlog")
    at.button(key="backlog_new_hypothesis").click().run()
    widget(at.text_input, "Ação Prática").set_value("Hipótese ainda não enviada").run()
    at.button(key="studio_nav_Governança").click().run()
    assert at.session_state["studio_page_Governança"] == "calibration"
    assert any(button.label == "Salvar Novas Calibrações" for button in at.button)
    open_page(at, "ritual")
    assert at.text_input(key="dec_summary").value == "Rascunho preservado"
    at.button(key="studio_toggle_explorer").click().run()
    at.button(key="studio_nav_Experimentos").click().run()
    assert at.session_state["studio_explorer"]
    assert at.session_state["studio_page_Experimentos"] == "backlog"
    assert widget(at.text_input, "Ação Prática").value == "Hipótese ainda não enviada"
    assert not SQLiteGrowthRepository(str(ui[1])).list_hypotheses()


def test_cockpit_filters_saved_evidence_by_cycle(ui):
    from decimal import Decimal
    from cgs.domain.entities.funnel import FunnelOpportunityAudit, FunnelStage
    at, db_path = ui
    growth = SQLiteGrowthRepository(str(db_path))
    growth.save_funnel_audit(FunnelOpportunityAudit(
        source_cycle_id="2026-11-02", primary_bottleneck=FunnelStage.INTENTION,
        intention_opportunity_reais=Decimal("1234.56"),
        conversion_opportunity_reais=Decimal("0"),
        total_opportunity_reais=Decimal("1234.56"), diagnosis_summary="Evidência de novembro",
    ))
    at.button(key="studio_nav_Cockpit").click().run()
    at.date_input(key="studio_cycle").set_value(date(2026, 11, 2)).run()
    assert_healthy(at)
    assert at.metric[0].value == "R$ 1.234,56"
    at.date_input(key="studio_cycle").set_value(date(2026, 11, 9)).run()
    assert_healthy(at)
    assert not at.metric
    assert any("ainda não tem diagnóstico" in item.value for item in at.subheader)
    at.date_input(key="studio_cycle").set_value(date(2026, 11, 10)).run()
    assert not at.exception
    assert any("segunda-feira" in item.value for item in at.error)
    assert len(growth.list_funnel_audits()) == 1
    assert not container_module.get_container().repository.list_rituals()


def test_contextual_export_and_baseline_draft_do_not_save(ui):
    at, db_path = ui
    open_page(at, "export")
    assert any("Finalize ao menos um ritual" in item.value for item in at.caption)
    assert not at.tabs
    assert not any(item.key == "dec_summary" for item in at.text_input)
    at.button(key="studio_nav_Experimentos").click().run()
    open_page(at, "baseline")
    widget(at.number_input, "Ticket Médio do Produto Final (R$)").set_value(333.0).run()
    open_page(at, "diagnosis")
    open_page(at, "baseline")
    assert widget(at.number_input, "Ticket Médio do Produto Final (R$)").value == 333.0
    assert SQLiteGrowthRepository(str(db_path)).get_active_baseline() is None


def test_wizard_recalculates_diagnosis_and_isolates_cycle_drafts(ui):
    at, _ = ui
    assert at.session_state["_ritual_step"] == 1
    assert not any(item.key == "dec_summary" for item in at.text_input)
    ritual_step(at, 3)
    assert any("Equilíbrio Operacional" in item.value for item in at.markdown)
    ritual_step(at, 2)
    at.number_input(key="val_ctr_pct").set_value(0.1).run()
    ritual_step(at, 3)
    assert any("Sinais Mistos" in item.value for item in at.markdown)
    ritual_step(at, 4)
    at.text_input(key="dec_summary").set_value("Rascunho de novembro 9").run()
    at.date_input(key="cycle_week_start").set_value(date(2026, 11, 2)).run()
    assert_healthy(at)
    assert at.session_state["_ritual_step"] == 1
    ritual_step(at, 4)
    assert at.text_input(key="dec_summary").value == ""
    assert at.session_state["val_ctr_pct"] != 0.1
    at.text_input(key="dec_summary").set_value("Rascunho de novembro 2").run()
    at.date_input(key="cycle_week_start").set_value(date(2026, 11, 9)).run()
    assert_healthy(at)
    assert at.session_state["_ritual_step"] == 4
    assert at.text_input(key="dec_summary").value == "Rascunho de novembro 9"
    assert at.session_state["val_ctr_pct"] == 0.1
    at.date_input(key="cycle_week_start").set_value(date(2026, 11, 2)).run()
    assert at.text_input(key="dec_summary").value == "Rascunho de novembro 2"
    assert not container_module.get_container().repository.list_rituals()


def test_wizard_validates_hidden_steps_before_writing(ui):
    from cdms.adapters.ui.components.metric_inputs import CANONICAL_DEFINITIONS, DEFAULT_CALIBRATIONS
    from cdms.domain.entities.metric import MetricSnapshot
    at, _ = ui
    snapshots = [MetricSnapshot(item, DEFAULT_CALIBRATIONS[item.key],
                               DEFAULT_CALIBRATIONS[item.key].healthy_min)
                 for item in CANONICAL_DEFINITIONS]
    container_module.get_container().run_weekly_ritual_use_case.execute(
        week_start=date(2026, 11, 2), snapshots=snapshots,
        decision_summary="Decisão anterior", decision_hypothesis="Hipótese anterior",
        decision_success_criterion="CTR >= 4%", decision_evaluation_due_date=date(2026, 11, 9),
    )
    at.run()
    assert at.selectbox(key="ritual_learning_outcome").value is None
    at.button_group(key="ritual_step_selector").set_value(4).run()
    assert_healthy(at)
    at.text_input(key="dec_summary").set_value("Nova decisão")
    at.text_area(key="dec_hypothesis").set_value("Hipótese verificável")
    at.text_area(key="dec_criterion").set_value("CTR >= 5%")
    at.button(key="ritual_finish").click().run()
    assert any("métricas na etapa 2" in item.value for item in at.error)
    assert container_module.get_container().repository.get_ritual_by_cycle("2026-11-09") is None
    ritual_step(at, 2)
    ritual_step(at, 4)
    at.button(key="ritual_finish").click().run()
    assert any("resultado observado na etapa 1" in item.value for item in at.error)
    assert container_module.get_container().repository.get_ritual_by_cycle("2026-11-09") is None


@pytest.mark.parametrize("conversion_type", ["DIRECT_SALE", "LEAD"])
def test_funnel_tabs_preserve_inputs_and_saved_result(ui, conversion_type):
    at, db_path = ui
    at.button(key="studio_nav_Experimentos").click().run()
    open_page(at, "baseline")
    widget(at.selectbox, "Tipo de Conversão Comercial").set_value(conversion_type).run()
    widget(at.button, "Salvar Baseline Ativa").click().run()
    open_page(at, "diagnosis")
    assert [tab.label for tab in at.tabs] == ["Diagnóstico do ciclo", "Histórico e evolução"]
    at.number_input(key="growth_impressions").set_value(15000)
    at.number_input(key="growth_clicks").set_value(500)
    widget(at.button, "Executar Diagnóstico Financeiro").click().run()
    assert_healthy(at)
    saved_metrics = [(item.label, item.value) for item in at.metric]
    assert saved_metrics
    assert not at.dataframe
    # AppTest cannot click native tabs; set their documented keyed state.
    at.session_state["growth_diagnosis_tab"] = "Histórico e evolução"
    at.run()
    assert_healthy(at)
    assert not any(item.key == "growth_impressions" for item in at.number_input)
    assert widget(at.metric, "Ciclos Auditados").value == "1"
    assert len(at.dataframe[0].value) == 1
    at.session_state["growth_diagnosis_tab"] = "Diagnóstico do ciclo"
    at.run()
    assert_healthy(at)
    assert at.number_input(key="growth_impressions").value == 15000
    assert at.number_input(key="growth_clicks").value == 500
    assert [(item.label, item.value) for item in at.metric] == saved_metrics
    assert len(SQLiteGrowthRepository(str(db_path)).list_funnel_audits()) == 1


def test_funnel_history_is_accessible_without_baseline(ui):
    at, _ = ui
    at.button(key="studio_nav_Experimentos").click().run()
    at.session_state["growth_diagnosis_tab"] = "Histórico e evolução"
    at.run()
    assert_healthy(at)
    assert any("Nenhuma auditoria registrada" in item.value for item in at.info)
    assert not at.warning
    assert not any(button.label == "Executar Diagnóstico Financeiro" for button in at.button)


def test_backlog_tabs_creation_and_draft_preservation(ui):
    at, db_path = ui
    at.button(key="studio_nav_Experimentos").click().run()
    open_page(at, "backlog")
    assert [tab.label for tab in at.tabs] == ["Backlog", "Em teste", "Histórico"]
    assert not any(item.key == "growth_action" for item in at.text_input)
    at.button(key="backlog_new_hypothesis").click().run()
    at.text_input(key="growth_action").set_value("Rascunho de hipótese").run()
    at.session_state["growth_backlog_tab"] = "Em teste"
    at.run()
    assert_healthy(at)
    assert not any(item.key == "growth_action" for item in at.text_input)
    at.session_state["growth_backlog_tab"] = "Backlog"
    at.run()
    assert at.text_input(key="growth_action").value == "Rascunho de hipótese"
    at.button(key="backlog_new_hypothesis").click().run()
    assert not any(item.key == "growth_action" for item in at.text_input)
    at.button(key="backlog_new_hypothesis").click().run()
    assert at.text_input(key="growth_action").value == "Rascunho de hipótese"
    widget(at.button, "Adicionar ao Backlog").click().run()
    assert_healthy(at)
    assert len(SQLiteGrowthRepository(str(db_path)).list_hypotheses()) == 1
    assert not any(item.key == "growth_action" for item in at.text_input)
    at.button(key="backlog_new_hypothesis").click().run()
    assert at.text_input(key="growth_action").value == ""


def create_backlog_hypothesis(growth, action, variable="CTA", score=7, lower=False):
    from decimal import Decimal
    from cgs.application.use_cases.manage_hypotheses import ManageHypothesesUseCase
    from cgs.domain.entities.hypothesis import VariableType, MetricDirection
    return ManageHypothesesUseCase(growth).create_hypothesis(
        action_description=action, tested_variable=VariableType(variable),
        target_metric_key="ctr_pct", target_metric_unit="%",
        metric_direction=MetricDirection.LOWER_IS_BETTER if lower else MetricDirection.HIGHER_IS_BETTER,
        baseline_reference_value=Decimal("3"), success_metric_target=Decimal("2") if lower else Decimal("4.5"),
        invalidation_floor=Decimal("4") if lower else Decimal("2.5"),
        expected_impact_description="Hipótese verificável", impact_score=score,
        confidence_score=score, ease_score=score,
    )


def test_backlog_ranking_filters_and_per_card_proposal(ui):
    from cgs.application.use_cases.prepare_cdms_proposal import PrepareCDMSProposalUseCase
    at, db_path = ui
    growth = SQLiteGrowthRepository(str(db_path))
    first = create_backlog_hypothesis(growth, "Prioridade intermediária", score=7)
    reserved = create_backlog_hypothesis(growth, "Gancho reservado", variable="HOOK", score=4)
    high = create_backlog_hypothesis(growth, "Maior prioridade", score=9)
    PrepareCDMSProposalUseCase(growth_repository=growth).execute(
        hypothesis_id=reserved.id, target_cycle_start=date(2026, 11, 2),
    )
    at.button(key="studio_nav_Experimentos").click().run()
    open_page(at, "backlog")
    actions = [item.value for item in at.markdown if item.value in {
        "**Maior prioridade**", "**Prioridade intermediária**", "**Gancho reservado**",
    }]
    assert actions == ["**Maior prioridade**", "**Prioridade intermediária**", "**Gancho reservado**"]
    at.selectbox(key="growth_backlog_variable").set_value("HOOK").run()
    assert not any(item.key == f"btn_prop_{high.id}" for item in at.button)
    assert at.button(key=f"btn_prop_{reserved.id}")
    at.selectbox(key="growth_backlog_cycle").set_value("unassigned").run()
    assert any("Nenhuma hipótese corresponde" in item.value for item in at.info)
    at.selectbox(key="growth_backlog_variable").set_value(None).run()
    assert at.button(key=f"btn_prop_{first.id}")
    at.date_input(key=f"growth_proposal_cycle_{high.id}").set_value(date(2026, 11, 10))
    at.button(key=f"btn_prop_{high.id}").click().run()
    assert not at.exception
    assert at.error
    assert growth.get_hypothesis_by_id(high.id).target_cycle_id is None
    at.date_input(key=f"growth_proposal_cycle_{high.id}").set_value(date(2026, 11, 9)).run()
    at.button(key=f"btn_prop_{high.id}").click().run()
    assert_healthy(at)
    proposal = growth.get_hypothesis_by_id(high.id)
    assert proposal.status.value == "PENDING"
    assert proposal.promoted_decision_id is None
    assert proposal.target_cycle_id == "2026-11-09"


def test_active_and_manual_history_do_not_claim_audited_result(ui):
    from cgs.application.use_cases.manage_hypotheses import ManageHypothesesUseCase
    at, db_path = ui
    growth = SQLiteGrowthRepository(str(db_path))
    hypothesis = create_backlog_hypothesis(growth, "Reduzir custo", lower=True)
    ManageHypothesesUseCase(growth).activate_hypothesis(hypothesis.id, target_cycle_id="2026-11-02")
    at.button(key="studio_nav_Experimentos").click().run()
    open_page(at, "backlog")
    at.session_state["growth_backlog_tab"] = "Em teste"
    at.run()
    assert_healthy(at)
    assert any("≤ 2" in item.value for item in at.markdown)
    assert any("09/11/2026" in item.value for item in at.caption)
    at.button(key=f"btn_comp_{hypothesis.id}").click().run()
    at.session_state["growth_backlog_tab"] = "Histórico"
    at.run()
    assert_healthy(at)
    assert any("Sem aprendizado auditado vinculado" in item.value for item in at.caption)
    assert not any("Resultado auditado" in item.value for item in at.markdown)
