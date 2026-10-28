"""Testes unitários para Conectores, Health Index e Gerador de Hipóteses com IA."""

from decimal import Decimal
import pytest
from cdms.adapters.connectors.mock_connectors import MockMetaAdsConnector, MockYouTubeStudioConnector
from cdms.domain.entities.funnel import FunnelOpportunityAudit, FunnelStage
from cdms.domain.entities.health_index import HealthTier
from cdms.domain.services.ai_hypothesis_generator import AIHypothesisGenerator


def test_meta_ads_connector():
    connector = MockMetaAdsConnector()
    assert connector.validate_connection("act_1234567") is True
    assert connector.validate_connection("invalid_acc") is False

    metrics = connector.fetch_weekly_metrics("act_1234567", "2026-10-26")
    assert metrics["reach"] == 18450
    assert metrics["clicks"] == 860
    assert metrics["platform"] == "META_ADS"


def test_youtube_studio_connector():
    connector = MockYouTubeStudioConnector()
    assert connector.validate_connection("channel_999") is True
    metrics = connector.fetch_weekly_metrics("channel_999", "2026-10-26")
    assert metrics["reach"] == 14200
    assert metrics["avg_retention_pct"] == 42.5


def test_ai_hypothesis_generation_for_intention_bottleneck():
    audit = FunnelOpportunityAudit(
        id=1,
        source_cycle_id="2026-10-26",
        primary_bottleneck=FunnelStage.INTENTION,
        intention_opportunity_reais=Decimal("3500.00"),
        conversion_opportunity_reais=Decimal("500.00"),
        total_opportunity_reais=Decimal("4000.00"),
        diagnosis_summary="Gargalo primário em Intenção.",
        calculation_version="2.0.0",
    )

    suggestions = AIHypothesisGenerator.generate_suggestions(audit=audit, current_ctr_pct=Decimal("2.8"))
    assert len(suggestions) >= 2
    assert any(s.tested_variable.value in ("HOOK", "CTA") for s in suggestions)
    assert all(s.suggested_target > s.invalidation_floor for s in suggestions)


def test_ai_hypothesis_generation_for_conversion_bottleneck():
    audit = FunnelOpportunityAudit(
        id=2,
        source_cycle_id="2026-10-26",
        primary_bottleneck=FunnelStage.CONVERSION,
        intention_opportunity_reais=Decimal("400.00"),
        conversion_opportunity_reais=Decimal("4200.00"),
        total_opportunity_reais=Decimal("4600.00"),
        diagnosis_summary="Gargalo primário em Conversão.",
        calculation_version="2.0.0",
    )

    suggestions = AIHypothesisGenerator.generate_suggestions(audit=audit, current_conv_rate_pct=Decimal("3.2"))
    assert len(suggestions) >= 2
    assert any(s.tested_variable.value in ("OFFER", "LANDING_PAGE") for s in suggestions)