"""Testes unitários para o serviço puro FunnelOpportunityAnalyzer do CGS."""

from decimal import Decimal
import pytest

from cgs.domain.entities.funnel import (
    ConversionType,
    FunnelBaseline,
    FunnelOpportunityAudit,
    FunnelStage,
)
from cgs.domain.services.funnel_analyzer import FunnelOpportunityAnalyzer


@pytest.fixture
def standard_baseline():
    """Baseline comercial padrão para venda direta."""
    return FunnelBaseline(
        ticket_price=Decimal("120.00"),
        expected_ctr_pct=Decimal("5.0"),
        expected_conversion_rate_pct=Decimal("10.0"),
        conversion_type=ConversionType.DIRECT_SALE,
    )


@pytest.fixture
def lead_baseline():
    """Baseline configurada para captação de leads com taxa lead -> venda."""
    return FunnelBaseline(
        ticket_price=Decimal("200.00"),
        expected_ctr_pct=Decimal("4.0"),
        expected_conversion_rate_pct=Decimal("20.0"),  # 20% taxa de lead
        conversion_type=ConversionType.LEAD,
        lead_to_sale_rate_pct=Decimal("25.0"),          # 25% dos leads viram venda
    )


def test_funnel_analyzer_detects_intention_bottleneck(standard_baseline):
    """Testa detecção de gargalo quando a maior oportunidade está na perda de cliques (Intenção)."""
    audit = FunnelOpportunityAnalyzer.calculate_opportunity(
        source_cycle_id="2026-10-26",
        impressions=10000,
        clicks=200,
        conversions=20,
        baseline=standard_baseline,
    )

    assert audit.primary_bottleneck == FunnelStage.INTENTION
    assert audit.intention_opportunity_reais > Decimal("0")
    assert audit.conversion_opportunity_reais == Decimal("0.00")
    assert audit.intention_opportunity_reais == Decimal("3600.00")
    assert audit.total_opportunity_reais == Decimal("3600.00")
    assert "INTENÇÃO" in audit.diagnosis_summary


def test_funnel_analyzer_detects_conversion_bottleneck(standard_baseline):
    """Testa detecção de gargalo quando a maior oportunidade está no checkout/vendas."""
    audit = FunnelOpportunityAnalyzer.calculate_opportunity(
        source_cycle_id="2026-10-26",
        impressions=10000,
        clicks=500,
        conversions=10,
        baseline=standard_baseline,
    )

    assert audit.primary_bottleneck == FunnelStage.CONVERSION
    assert audit.intention_opportunity_reais == Decimal("0.00")
    assert audit.conversion_opportunity_reais > Decimal("0")
    assert audit.conversion_opportunity_reais == Decimal("4800.00")
    assert audit.total_opportunity_reais == Decimal("4800.00")
    assert "CONVERSÃO" in audit.diagnosis_summary


def test_funnel_analyzer_stable_tie_breaking(standard_baseline):
    """Garante política de desempate estável priorizando CONVERSION em caso de valores idênticos."""
    audit = FunnelOpportunityAnalyzer.calculate_opportunity(
        source_cycle_id="2026-10-26",
        impressions=5000,
        clicks=200,
        conversions=15,
        baseline=standard_baseline,
    )

    assert audit.intention_opportunity_reais == Decimal("600.00")
    assert audit.conversion_opportunity_reais == Decimal("600.00")
    assert audit.primary_bottleneck == FunnelStage.CONVERSION


def test_funnel_analyzer_healthy_funnel_returns_stage_none(standard_baseline):
    """Testa cenário onde as métricas reais superam a baseline (sem gargalos)."""
    audit = FunnelOpportunityAnalyzer.calculate_opportunity(
        source_cycle_id="2026-10-26",
        impressions=10000,
        clicks=600,
        conversions=72,
        baseline=standard_baseline,
    )

    assert audit.primary_bottleneck == FunnelStage.NONE
    assert audit.intention_opportunity_reais == Decimal("0.00")
    assert audit.conversion_opportunity_reais == Decimal("0.00")
    assert audit.total_opportunity_reais == Decimal("0.00")
    assert "dentro ou acima" in audit.diagnosis_summary


def test_funnel_analyzer_zero_impressions_attention_stage(standard_baseline):
    """Testa tratamento para ausência total de impressões (sem divisão por zero)."""
    audit = FunnelOpportunityAnalyzer.calculate_opportunity(
        source_cycle_id="2026-10-26",
        impressions=0,
        clicks=0,
        conversions=0,
        baseline=standard_baseline,
    )

    assert audit.primary_bottleneck == FunnelStage.ATTENTION
    assert audit.total_opportunity_reais == Decimal("0.00")
    assert "0 impressões" in audit.diagnosis_summary


def test_funnel_analyzer_zero_clicks_safe_division(standard_baseline):
    """Testa tratamento quando há impressões mas zero cliques registrados."""
    audit = FunnelOpportunityAnalyzer.calculate_opportunity(
        source_cycle_id="2026-10-26",
        impressions=1000,
        clicks=0,
        conversions=0,
        baseline=standard_baseline,
    )

    assert audit.primary_bottleneck == FunnelStage.INTENTION
    assert audit.intention_opportunity_reais == Decimal("600.00")
    assert audit.conversion_opportunity_reais == Decimal("0.00")


def test_funnel_analyzer_lead_generation_mode(lead_baseline):
    """Testa cálculo aplicando multiplicador de conversão lead -> venda."""
    audit = FunnelOpportunityAnalyzer.calculate_opportunity(
        source_cycle_id="2026-10-26",
        impressions=10000,
        clicks=400,
        conversions=40,
        baseline=lead_baseline,
    )

    assert audit.primary_bottleneck == FunnelStage.CONVERSION
    assert audit.conversion_opportunity_reais == Decimal("2000.00")
    assert audit.total_opportunity_reais == Decimal("2000.00")


@pytest.mark.parametrize(
    "impressions,clicks,conversions",
    [
        (-1, 10, 2),
        (100, -5, 1),
        (100, 10, -3),
        (500, 600, 10),
    ],
)
def test_funnel_analyzer_input_validation(standard_baseline, impressions, clicks, conversions):
    """Valida rejeição de contagens negativas ou cliques superiores a impressões."""
    with pytest.raises(ValueError):
        FunnelOpportunityAnalyzer.calculate_opportunity(
            source_cycle_id="2026-10-26",
            impressions=impressions,
            clicks=clicks,
            conversions=conversions,
            baseline=standard_baseline,
        )