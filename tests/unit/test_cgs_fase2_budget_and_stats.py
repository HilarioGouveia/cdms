"""Testes unitários para Governança Orçamentária e Significância Estatística do CGS."""

from decimal import Decimal
import os
import tempfile
import pytest

from cgs.adapters.persistence.sqlite_cgs_fase2_repo import SQLiteCGSPhase2Repository
from cgs.application.use_cases.allocate_experiment_budget import AllocateExperimentBudgetUseCase
from cgs.domain.entities.budget_allocation import BudgetAllocation, ExperimentRiskTier
from cgs.domain.entities.statistical_validation import StatisticalSignificanceVerdict
from cgs.domain.services.bayesian_analyzer import BayesianExperimentAnalyzer


@pytest.fixture
def temp_cgs2_repo():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    repo = SQLiteCGSPhase2Repository(path)
    yield repo
    if os.path.exists(path):
        os.remove(path)


def test_budget_allocation_within_limit(temp_cgs2_repo):
    uc = AllocateExperimentBudgetUseCase(temp_cgs2_repo, max_cycle_budget_cents=100000)  # R$ 1.000,00
    alloc = uc.execute(
        hypothesis_id=1,
        cycle_id="2026-10-26",
        amount_reais=Decimal("450.00"),
        risk_tier=ExperimentRiskTier.LOW,
    )
    assert alloc.allocated_amount_cents == 45000
    assert alloc.allocated_reais == Decimal("450.00")
    assert alloc.risk_tier == ExperimentRiskTier.LOW


def test_budget_allocation_exceeds_cycle_limit_raises_error(temp_cgs2_repo):
    uc = AllocateExperimentBudgetUseCase(temp_cgs2_repo, max_cycle_budget_cents=50000)  # R$ 500,00
    uc.execute(hypothesis_id=1, cycle_id="2026-10-26", amount_reais=Decimal("350.00"))

    with pytest.raises(ValueError, match="Teto orçamentário do ciclo '2026-10-26' excedido"):
        uc.execute(hypothesis_id=2, cycle_id="2026-10-26", amount_reais=Decimal("200.00"))


def test_bayesian_significance_conclusive_winner():
    res = BayesianExperimentAnalyzer.evaluate(
        hypothesis_id=10,
        control_conversions=20,
        control_sample=1000,  # 2.0%
        treatment_conversions=45,
        treatment_sample=1000,  # 4.5%
        sample_minimum=500,
    )
    assert res.lift_pct > Decimal("100.0")
    assert res.probability_to_beat_control >= Decimal("95.0")
    assert res.verdict == StatisticalSignificanceVerdict.STATISTICALLY_SIGNIFICANT


def test_bayesian_early_stopping_triggered_on_loss():
    # Perda severa observada com amostra parcial
    res = BayesianExperimentAnalyzer.evaluate(
        hypothesis_id=11,
        control_conversions=50,
        control_sample=1000,  # 5.0%
        treatment_conversions=15,
        treatment_sample=600,   # 2.5% (-50% lift)
        sample_minimum=1000,
    )
    assert res.lift_pct <= Decimal("-30.0")
    assert res.verdict == StatisticalSignificanceVerdict.EARLY_STOPPED_HIGH_LOSS