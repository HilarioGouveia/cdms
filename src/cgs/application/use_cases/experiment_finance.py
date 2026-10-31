"""Fluxos compartilhados por Studio e API para orçamento e avaliação A/B."""
from decimal import Decimal, InvalidOperation
from cgs.application.use_cases.allocate_experiment_budget import AllocateExperimentBudgetUseCase
from cgs.domain.services.bayesian_analyzer import BayesianExperimentAnalyzer
from cgs.domain.entities.budget_allocation import ExperimentRiskTier


def money_cents(value, *, allow_zero=False):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0 or number > Decimal('1000000000000') or (not allow_zero and number == 0) or number != number.quantize(Decimal('.01')):
            raise ValueError
        return int(number*100)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Informe um valor monetário válido, com até duas casas decimais.') from None


class ExperimentFinance:
    def __init__(self, repo, growth, *, actor=None):
        self.repo, self.growth, self.actor = repo, growth, actor

    def hypothesis(self, hypothesis_id, cycle_id):
        from datetime import date
        parsed=date.fromisoformat(cycle_id)
        if cycle_id != parsed.isoformat() or parsed.weekday() != 0:
            raise ValueError('O ciclo deve começar numa segunda-feira.')
        h = self.growth.get_hypothesis_by_id(hypothesis_id)
        if h is None:
            raise ValueError('Hipótese não encontrada neste workspace.')
        if h.target_cycle_id and h.target_cycle_id != cycle_id:
            raise ValueError('A hipótese pertence a outro ciclo.')
        return h

    def allocate(self, hypothesis_id, cycle_id, amount, risk='LOW', cpa=None):
        h=self.hypothesis(hypothesis_id, cycle_id)
        if h.status.value in {'COMPLETED','DISCARDED','CANCELLED','ARCHIVED'}:
            raise ValueError('A hipótese foi encerrada. Registre gastos realizados, sem criar nova alocação.')
        amount = Decimal(money_cents(amount))/100
        cpa = Decimal(money_cents(cpa))/100 if cpa is not None else None
        return AllocateExperimentBudgetUseCase(self.repo).execute(hypothesis_id,cycle_id,amount,
                    ExperimentRiskTier(risk),cpa,actor=self.actor)

    def spend(self, hypothesis_id, cycle_id, amount):
        self.hypothesis(hypothesis_id,cycle_id)
        self.repo.record_spend(hypothesis_id,cycle_id,money_cents(amount,allow_zero=True),self.actor)

    def evaluate(self, hypothesis_id, cycle_id, **inputs):
        self.hypothesis(hypothesis_id,cycle_id)
        result=BayesianExperimentAnalyzer.evaluate(hypothesis_id,cycle_id=cycle_id,**inputs)
        self.repo.save_statistical_evaluation(result,self.actor)
        return result
