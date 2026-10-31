"""Caso de uso: Alocar e validar orçamento de teste operacional respeitando o limite do ciclo."""

from decimal import Decimal
from cgs.application.ports.cgs_fase2_repository import CGSPhase2RepositoryPort
from cgs.domain.entities.budget_allocation import BudgetAllocation, ExperimentRiskTier


class AllocateExperimentBudgetUseCase:
    def __init__(self, repository: CGSPhase2RepositoryPort, max_cycle_budget_cents: int = 500000):
        self.repository = repository
        self.max_cycle_budget_cents = max_cycle_budget_cents  # Padrão: R$ 5.000,00 por ciclo

    def execute(
        self,
        hypothesis_id: int,
        cycle_id: str,
        amount_reais: Decimal,
        risk_tier: ExperimentRiskTier = ExperimentRiskTier.LOW,
        max_cpa_target_reais: Decimal = None,
        actor: str = None,
    ) -> BudgetAllocation:
        if not amount_reais.is_finite() or amount_reais <= 0 or amount_reais != amount_reais.quantize(Decimal('.01')):
            raise ValueError('Informe um valor positivo com até duas casas decimais.')
        if max_cpa_target_reais is not None and (not max_cpa_target_reais.is_finite() or max_cpa_target_reais <= 0):
            raise ValueError('CPA deve ser positivo.')
        allocated_cents = int((amount_reais * Decimal("100")).to_integral_value())

        max_cpa_cents = int((max_cpa_target_reais * Decimal("100")).to_integral_value()) if max_cpa_target_reais else None

        allocation = BudgetAllocation(
            hypothesis_id=hypothesis_id,
            cycle_id=cycle_id,
            allocated_amount_cents=allocated_cents,
            risk_tier=risk_tier,
            max_cpa_target_cents=max_cpa_cents,
        )
        return self.repository.save_budget_allocation(allocation, max_cycle_budget_cents=self.max_cycle_budget_cents, actor=actor)
