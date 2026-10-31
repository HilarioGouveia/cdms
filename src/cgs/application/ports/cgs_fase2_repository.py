"""Porta dirigida para operações orçamentárias e validações estatísticas da Fase 2."""

from abc import ABC, abstractmethod
from typing import List, Optional
from cgs.domain.entities.budget_allocation import BudgetAllocation
from cgs.domain.entities.statistical_validation import BayesianExperimentEvaluation


class CGSPhase2RepositoryPort(ABC):
    @abstractmethod
    def save_budget_allocation(self, allocation: BudgetAllocation, max_cycle_budget_cents=500000, actor=None) -> BudgetAllocation:
        pass

    @abstractmethod
    def get_budget_by_hypothesis(self, hypothesis_id: int, cycle_id=None) -> Optional[BudgetAllocation]:
        pass

    @abstractmethod
    def list_budgets_by_cycle(self, cycle_id: str) -> List[BudgetAllocation]:
        pass

    @abstractmethod
    def save_statistical_evaluation(self, evaluation: BayesianExperimentEvaluation, actor=None) -> None:
        pass

    @abstractmethod
    def get_evaluation_by_hypothesis(self, hypothesis_id: int, cycle_id=None) -> Optional[BayesianExperimentEvaluation]:
        pass
