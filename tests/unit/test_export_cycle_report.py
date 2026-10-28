"""Testes Unitários: Exportador de Relatório Consolidado de Ciclo em Markdown."""

from decimal import Decimal
import pytest

from cgs.application.use_cases.export_cycle_report import ExportCycleReportUseCase
from cgs.domain.entities.funnel import FunnelOpportunityAudit, FunnelStage
from cgs.domain.entities.hypothesis import (
    GrowthHypothesis,
    HypothesisStatus,
    MetricDirection,
    VariableType,
)


class FakeGrowthRepo:
    def __init__(self, audit=None, previous_audit=None, hypotheses=None):
        self._audit = audit
        self._previous_audit = previous_audit
        self._hypotheses = hypotheses or []

    def get_funnel_audit(self, source_cycle_id: str):
        if self._audit and self._audit.source_cycle_id == source_cycle_id:
            return self._audit
        return None

    def list_funnel_audits(self, limit: int = 50):
        audits = []
        if self._audit:
            audits.append(self._audit)
        if self._previous_audit:
            audits.append(self._previous_audit)
        return audits

    def list_hypotheses(self, status=None, limit: int = 50):
        return self._hypotheses


def test_export_report_with_complete_audit_and_roi_delta():
    audit_current = FunnelOpportunityAudit(
        source_cycle_id="2026-10-26",
        primary_bottleneck=FunnelStage.INTENTION,
        intention_opportunity_reais=Decimal("1200.00"),
        conversion_opportunity_reais=Decimal("800.00"),
        total_opportunity_reais=Decimal("2000.00"),
        diagnosis_summary="Gargalo crítico no CTR (Intenção).",
        calculation_version="2.0.0",
        leads_opportunity_reais=Decimal("500.00"),
        closing_opportunity_reais=Decimal("300.00"),
    )
    audit_prev = FunnelOpportunityAudit(
        source_cycle_id="2026-10-19",
        primary_bottleneck=FunnelStage.INTENTION,
        intention_opportunity_reais=Decimal("3000.00"),
        conversion_opportunity_reais=Decimal("1500.00"),
        total_opportunity_reais=Decimal("4500.00"),
        diagnosis_summary="Gargalo crítico grave no CTR.",
        calculation_version="2.0.0",
    )
    hypo = GrowthHypothesis(
        id=42,
        source_cycle_id="2026-10-26",
        target_cycle_id="2026-10-26",
        promoted_decision_id=10,
        action_description="Inserir CTA claro no segundo 5",
        tested_variable=VariableType.CTA,
        target_metric_key="ctr_pct",
        target_metric_unit="%",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        baseline_reference_value=Decimal("2.5"),
        success_metric_target=Decimal("4.5"),
        invalidation_floor=Decimal("1.8"),
        expected_impact_description="Aumentar cliques",
        impact_score=8,
        confidence_score=7,
        ease_score=9,
        status=HypothesisStatus.ACTIVE,
    )

    fake_repo = FakeGrowthRepo(
        audit=audit_current,
        previous_audit=audit_prev,
        hypotheses=[hypo],
    )
    use_case = ExportCycleReportUseCase(fake_repo)

    result = use_case.execute("2026-10-26")

    assert result.cycle_id == "2026-10-26"
    assert result.has_funnel_audit is True
    assert result.hypotheses_count == 1
    assert "# 📊 Relatório Executivo Semanal — Ciclo `2026-10-26`" in result.markdown_content
    assert "\n\n## 1." in result.markdown_content
    assert "\\n" not in result.markdown_content
    assert "INTENTION" in result.markdown_content
    assert "R$ 2,000.00" in result.markdown_content
    assert "**ROI de Governança Positivo:** Redução de **R$ 2,500.00**" in result.markdown_content
    assert "| #42 | 🔵 ACTIVE | `CTA` | `ctr_pct` |" in result.markdown_content
    assert "#10" in result.markdown_content


def test_export_report_without_funnel_audit_handles_cleanly():
    fake_repo = FakeGrowthRepo(audit=None, hypotheses=[])
    use_case = ExportCycleReportUseCase(fake_repo)

    result = use_case.execute("2026-11-02")

    assert result.has_funnel_audit is False
    assert result.hypotheses_count == 0
    assert "_Nenhuma auditoria quantitativa de funil foi registrada para este ciclo._" in result.markdown_content
    assert "_Nenhum experimento ou hipótese de crescimento foi vinculado explicitamente a este ciclo._" in result.markdown_content