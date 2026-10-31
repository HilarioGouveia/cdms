from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from cgs.adapters.persistence.sqlite_cgs_fase2_repo import SQLiteCGSPhase2Repository
from cgs.domain.entities.budget_allocation import BudgetAllocation
from cgs.domain.services.bayesian_analyzer import BayesianExperimentAnalyzer


def test_budget_cycle_isolation_edit_preserves_spend_and_history(tmp_path):
    repo=SQLiteCGSPhase2Repository(tmp_path/'finance.db')
    repo.set_cycle_limit('2026-10-19',10000)
    repo.save_budget_allocation(BudgetAllocation(1,'2026-10-19',8000))
    repo.record_spend(1,'2026-10-19',9000,'user')
    repo.save_budget_allocation(BudgetAllocation(1,'2026-10-19',9500))
    repo.save_budget_allocation(BudgetAllocation(1,'2026-10-26',5000))
    assert repo.get_budget_by_hypothesis(1,'2026-10-19').spent_amount_cents == 9000
    assert repo.get_budget_by_hypothesis(1,'2026-10-26').spent_amount_cents == 0
    with pytest.raises(ValueError):
        repo.record_spend(1,'2026-10-19',8000)
    with pytest.raises(ValueError):
        repo.set_cycle_limit('2026-10-19',9000)
    assert len(repo.budget_history('2026-10-19'))==4


def test_concurrent_allocations_cannot_exceed_cycle_limit(tmp_path):
    repo=SQLiteCGSPhase2Repository(tmp_path/'finance.db')
    repo.set_cycle_limit('2026-10-19',10000)
    def allocate(uid):
        try:
            repo.save_budget_allocation(BudgetAllocation(uid,'2026-10-19',7000))
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(allocate,[1,2]))==[False,True]
    assert sum(b.allocated_amount_cents for b in repo.list_budgets_by_cycle('2026-10-19'))==7000


@pytest.mark.parametrize('values',[(101,100,1,100,100),(-1,100,1,100,100),(0,100,1,100,0),(True,100,1,100,100),(1,0,1,100,100)])
def test_invalid_ab_inputs_are_rejected(values):
    with pytest.raises(ValueError):
        BayesianExperimentAnalyzer.evaluate(1,*values)


def test_beta_posterior_zero_control_and_immutable_evaluation_history(tmp_path):
    repo=SQLiteCGSPhase2Repository(tmp_path/'finance.db')
    first=BayesianExperimentAnalyzer.evaluate(1,0,100,20,100,cycle_id='2026-10-19')
    second=BayesianExperimentAnalyzer.evaluate(1,20,100,40,100,cycle_id='2026-10-19')
    assert first.lift_pct is None
    assert first.probability_to_beat_control > 99
    assert first.difference_low_pp > 0
    repeat=BayesianExperimentAnalyzer.evaluate(1,0,100,20,100,cycle_id='2026-10-19')
    assert first.probability_to_beat_control==repeat.probability_to_beat_control
    repo.save_statistical_evaluation(first,'owner')
    repo.save_statistical_evaluation(second,'owner')
    history=repo.evaluation_history(1,'2026-10-19')
    assert history==[second,first]
    assert history[0].control_conversions==20
    assert history[1].control_conversions==0
    assert history[0].evaluated_at==second.evaluated_at
    assert repo.cycle_evaluations('2026-10-19')==[second]
    insufficient=BayesianExperimentAnalyzer.evaluate(1,1,5,80,100,100)
    assert insufficient.verdict.value=='INCONCLUSIVE_INSUFFICIENT_SAMPLE'
    rounded=BayesianExperimentAnalyzer.evaluate(1,1,999,900,1000,1000)
    assert rounded.verdict.value=='INCONCLUSIVE_INSUFFICIENT_SAMPLE'
