"""Testes de integração para o SQLiteGrowthRepository do CGS."""

from datetime import datetime, timezone
from decimal import Decimal
import os
import sqlite3
import pytest

from cgs.adapters.persistence.sqlite_growth_repo import SQLiteGrowthRepository
from cgs.domain.entities.funnel import (
    ConversionType,
    FunnelBaseline,
    FunnelOpportunityAudit,
    FunnelStage,
)
from cgs.domain.entities.hypothesis import (
    GrowthHypothesis,
    HypothesisStatus,
    MetricDirection,
    VariableType,
)


@pytest.fixture
def temp_db_path(tmp_path):
    """Cria uma base de dados SQLite limpa e isolada por teste."""
    db_file = tmp_path / "test_cgs_integration.db"
    return str(db_file)


@pytest.fixture
def repo(temp_db_path):
    """Instancia o repositório SQLite garantindo migrações executadas."""
    return SQLiteGrowthRepository(temp_db_path)


def test_schema_migration_002_applied_successfully(temp_db_path, repo):
    """Garante que a migração 002 cria as tabelas e índices corretos e atualiza a tabela schema_version."""
    with sqlite3.connect(temp_db_path) as conn:
        cursor = conn.execute("SELECT version FROM schema_version WHERE version = 2;")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == 2

        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            ).fetchall()
        ]
        assert "growth_baselines" in tables
        assert "funnel_opportunity_audits" in tables
        assert "growth_hypotheses" in tables


def test_save_and_retrieve_active_baseline(repo):
    """Testa a persistência da baseline de funil e a política de manter apenas uma ativa."""
    base1 = FunnelBaseline(
        ticket_price=Decimal("120.00"),
        expected_ctr_pct=Decimal("5.0"),
        expected_conversion_rate_pct=Decimal("10.0"),
        conversion_type=ConversionType.DIRECT_SALE,
    )
    repo.save_baseline(base1)

    active = repo.get_active_baseline()
    assert active is not None
    assert active.ticket_price == Decimal("120.00")
    assert active.expected_ctr_pct == Decimal("5.0")
    assert active.expected_conversion_rate_pct == Decimal("10.0")
    assert active.conversion_type == ConversionType.DIRECT_SALE
    assert active.lead_to_sale_rate_pct is None

    base2 = FunnelBaseline(
        ticket_price=Decimal("250.50"),
        expected_ctr_pct=Decimal("3.5"),
        expected_conversion_rate_pct=Decimal("15.0"),
        conversion_type=ConversionType.LEAD,
        lead_to_sale_rate_pct=Decimal("20.0"),
    )
    repo.save_baseline(base2)

    active_updated = repo.get_active_baseline()
    assert active_updated is not None
    assert active_updated.ticket_price == Decimal("250.50")
    assert active_updated.conversion_type == ConversionType.LEAD
    assert active_updated.lead_to_sale_rate_pct == Decimal("20.0")


def test_save_and_retrieve_funnel_audit(repo):
    """Testa gravação e recuperação de diagnóstico de oportunidade de funil por ciclo."""
    audit = FunnelOpportunityAudit(
        source_cycle_id="2026-10-26",
        primary_bottleneck=FunnelStage.INTENTION,
        intention_opportunity_reais=Decimal("3600.00"),
        conversion_opportunity_reais=Decimal("0.00"),
        total_opportunity_reais=Decimal("3600.00"),
        diagnosis_summary="Gargalo primário identificado em INTENÇÃO.",
        calculation_version="1.1.0",
    )
    repo.save_funnel_audit(audit)

    retrieved = repo.get_funnel_audit("2026-10-26")
    assert retrieved is not None
    assert retrieved.source_cycle_id == "2026-10-26"
    assert retrieved.primary_bottleneck == FunnelStage.INTENTION
    assert retrieved.intention_opportunity_reais == Decimal("3600.00")
    assert retrieved.conversion_opportunity_reais == Decimal("0.00")
    assert retrieved.total_opportunity_reais == Decimal("3600.00")
    assert retrieved.diagnosis_summary == "Gargalo primário identificado em INTENÇÃO."
    assert retrieved.calculation_version == "1.1.0"


def test_save_and_retrieve_hypothesis(repo):
    """Testa persistência de uma hipótese com precisão exata em Decimal e atributos completos."""
    hypo = GrowthHypothesis(
        id=None,
        source_cycle_id="2026-10-26",
        target_cycle_id=None,
        promoted_decision_id=None,
        action_description="Ajustar primeiros 3 segundos do Reels",
        tested_variable=VariableType.HOOK,
        target_metric_key="reach",
        target_metric_unit="un",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        baseline_reference_value=Decimal("5000"),
        success_metric_target=Decimal("8000"),
        invalidation_floor=Decimal("4500"),
        expected_impact_description="Aumentar retenção inicial e distribuição orgânica",
        impact_score=8,
        confidence_score=7,
        ease_score=9,
        sample_exposure_minimum=500,
        window_days=7,
        status=HypothesisStatus.BACKLOG,
    )
    saved = repo.save_hypothesis(hypo)
    assert saved.id is not None
    assert saved.ice_score == Decimal("50.40")

    retrieved = repo.get_hypothesis_by_id(saved.id)
    assert retrieved is not None
    assert retrieved.id == saved.id
    assert retrieved.action_description == "Ajustar primeiros 3 segundos do Reels"
    assert retrieved.tested_variable == VariableType.HOOK
    assert retrieved.ice_score == Decimal("50.40")
    assert retrieved.baseline_reference_value == Decimal("5000")
    assert retrieved.success_metric_target == Decimal("8000")
    assert retrieved.invalidation_floor == Decimal("4500")
    assert retrieved.status == HypothesisStatus.BACKLOG


def test_list_hypotheses_sorted_by_ice_score(repo):
    """Testa listagem com ordenação decrescente estável por ICE score."""
    hypo_a = GrowthHypothesis(
        id=None,
        source_cycle_id=None,
        target_cycle_id=None,
        promoted_decision_id=None,
        action_description="Hipótese A",
        tested_variable=VariableType.CTA,
        target_metric_key="ctr_pct",
        target_metric_unit="%",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        baseline_reference_value=Decimal("3.0"),
        success_metric_target=Decimal("4.5"),
        invalidation_floor=Decimal("2.5"),
        expected_impact_description="A",
        impact_score=8,
        confidence_score=7,
        ease_score=9,
    )
    hypo_b = GrowthHypothesis(
        id=None,
        source_cycle_id=None,
        target_cycle_id=None,
        promoted_decision_id=None,
        action_description="Hipótese B (Top)",
        tested_variable=VariableType.CREATIVE,
        target_metric_key="ctr_pct",
        target_metric_unit="%",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        baseline_reference_value=Decimal("3.0"),
        success_metric_target=Decimal("5.0"),
        invalidation_floor=Decimal("2.0"),
        expected_impact_description="B",
        impact_score=9,
        confidence_score=9,
        ease_score=9,
    )
    hypo_c = GrowthHypothesis(
        id=None,
        source_cycle_id=None,
        target_cycle_id=None,
        promoted_decision_id=None,
        action_description="Hipótese C (Baixa)",
        tested_variable=VariableType.OFFER,
        target_metric_key="conversions",
        target_metric_unit="un",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        baseline_reference_value=Decimal("10"),
        success_metric_target=Decimal("15"),
        invalidation_floor=Decimal("8"),
        expected_impact_description="C",
        impact_score=5,
        confidence_score=5,
        ease_score=5,
    )

    repo.save_hypothesis(hypo_a)
    repo.save_hypothesis(hypo_b)
    repo.save_hypothesis(hypo_c)

    ranked = repo.list_hypotheses(status=HypothesisStatus.BACKLOG)
    assert len(ranked) == 3
    assert ranked[0].action_description == "Hipótese B (Top)"
    assert ranked[0].ice_score == Decimal("72.90")
    assert ranked[1].action_description == "Hipótese A"
    assert ranked[1].ice_score == Decimal("50.40")
    assert ranked[2].action_description == "Hipótese C (Baixa)"
    assert ranked[2].ice_score == Decimal("12.50")


def test_update_hypothesis_status_lifecycle(repo):
    """Testa transição de status: BACKLOG -> PROPOSED -> ACTIVE com vinculação de ciclo e decisão."""
    hypo = GrowthHypothesis(
        id=None,
        source_cycle_id="2026-10-26",
        target_cycle_id=None,
        promoted_decision_id=None,
        action_description="CTA direto no fechamento",
        tested_variable=VariableType.CTA,
        target_metric_key="ctr_pct",
        target_metric_unit="%",
        metric_direction=MetricDirection.HIGHER_IS_BETTER,
        baseline_reference_value=Decimal("3.0"),
        success_metric_target=Decimal("4.5"),
        invalidation_floor=Decimal("2.5"),
        expected_impact_description="Aumentar cliques",
        impact_score=8,
        confidence_score=7,
        ease_score=9,
    )
    saved = repo.save_hypothesis(hypo)

    proposed = repo.update_hypothesis_status(
        hypothesis_id=saved.id,
        status=HypothesisStatus.PROPOSED,
        target_cycle_id="2026-11-02",
    )
    assert proposed.status == HypothesisStatus.PROPOSED
    assert proposed.target_cycle_id == "2026-11-02"
    assert proposed.promoted_decision_id is None

    active = repo.update_hypothesis_status(
        hypothesis_id=saved.id,
        status=HypothesisStatus.ACTIVE,
        promoted_decision_id=99,
    )
    assert active.status == HypothesisStatus.ACTIVE
    assert active.target_cycle_id == "2026-11-02"
    assert active.promoted_decision_id == 99


def test_update_nonexistent_hypothesis_raises_error(repo):
    """Garante lançamento de erro ao tentar atualizar hipótese inexistente."""
    with pytest.raises(ValueError, match="não encontrada"):
        repo.update_hypothesis_status(
            hypothesis_id=9999,
            status=HypothesisStatus.ACTIVE,
        )