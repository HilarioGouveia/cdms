"""Testes unitários para Multi-Armed Bandits e Disjuntores de Segurança do CGS (Fase 3)."""

from decimal import Decimal
import os
import tempfile
import pytest

from cgs.adapters.persistence.sqlite_cgs_fase3_repo import SQLiteCGSPhase3Repository
from cgs.application.use_cases.optimize_variant_allocation import OptimizeVariantAllocationUseCase
from cgs.domain.entities.bandit_policy import AutoRollbackTrigger, VariantArm
from cgs.domain.services.auto_circuit_breaker import ExperimentCircuitBreaker
from cgs.domain.services.bandit_allocator import ThompsonSamplingBanditAllocator


@pytest.fixture
def temp_cgs3_repo():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    repo = SQLiteCGSPhase3Repository(path)
    yield repo
    if os.path.exists(path):
        os.remove(path)


def test_thompson_sampling_favors_high_converting_arm():
    arms = [
        VariantArm(arm_id="control", variable_name="CTA Original", total_impressions=1000, total_conversions=20),    # 2.0%
        VariantArm(arm_id="treatment", variable_name="CTA Urgente", total_impressions=1000, total_conversions=60),   # 6.0%
    ]

    res = ThompsonSamplingBanditAllocator.rebalance_weights(
        hypothesis_id=1,
        cycle_id="2026-10-26",
        arms=arms,
        simulations_count=5000,
    )

    assert res.leading_arm_id == "treatment"
    assert res.arm_weights["treatment"] > res.arm_weights["control"]
    assert res.arm_weights["treatment"] >= Decimal("80.00")


def test_circuit_breaker_trips_on_cpa_spike():
    breaker = ExperimentCircuitBreaker.evaluate(
        hypothesis_id=2,
        cycle_id="2026-10-26",
        current_cpa_reais=Decimal("180.00"),
        max_allowed_cpa_reais=Decimal("100.00"),  # Limite de R$ 100,00 (180 > 150)
        control_cr_pct=Decimal("3.0"),
        treatment_cr_pct=Decimal("2.8"),
        current_spend_reais=Decimal("300.00"),
        max_budget_reais=Decimal("1000.00"),
    )

    assert breaker.is_tripped is True
    assert breaker.trigger_reason == AutoRollbackTrigger.CPA_SPIKE
    assert breaker.observed_metric_value == Decimal("180.00")


def test_circuit_breaker_trips_on_conversion_collapse():
    breaker = ExperimentCircuitBreaker.evaluate(
        hypothesis_id=3,
        cycle_id="2026-10-26",
        current_cpa_reais=Decimal("50.00"),
        max_allowed_cpa_reais=Decimal("60.00"),
        control_cr_pct=Decimal("5.0"),
        treatment_cr_pct=Decimal("1.5"),  # Queda de 70% frente ao controle
        current_spend_reais=Decimal("250.00"),
        max_budget_reais=Decimal("1000.00"),
    )

    assert breaker.is_tripped is True
    assert breaker.trigger_reason == AutoRollbackTrigger.CONVERSION_COLLAPSE


def test_optimize_allocation_use_case_disarms_on_spike(temp_cgs3_repo):
    uc = OptimizeVariantAllocationUseCase(temp_cgs3_repo)
    arms = [
        VariantArm(arm_id="ctrl", variable_name="Hero A", total_impressions=500, total_conversions=15),
        VariantArm(arm_id="treat", variable_name="Hero B", total_impressions=500, total_conversions=2),
    ]

    result = uc.execute(
        hypothesis_id=10,
        cycle_id="2026-10-26",
        arms=arms,
        current_cpa_reais=Decimal("250.00"),
        max_allowed_cpa_reais=Decimal("100.00"),  # Dispara disjuntor
        current_spend_reais=Decimal("400.00"),
        max_budget_reais=Decimal("1000.00"),
    )

    assert result.circuit_breaker.is_tripped is True
    assert "DISJUNTOR ACIONADO" in result.action_taken
    assert result.bandit_decision is None