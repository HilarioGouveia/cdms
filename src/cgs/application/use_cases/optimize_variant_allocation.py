"""Caso de uso: Rebalancear tráfego operacional e verificar integridade com disjuntor."""

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional
from cgs.application.ports.cgs_fase3_repository import CGSPhase3RepositoryPort
from cgs.domain.entities.bandit_policy import BanditOptimizationResult, CircuitBreakerStatus, VariantArm
from cgs.domain.services.auto_circuit_breaker import ExperimentCircuitBreaker
from cgs.domain.services.bandit_allocator import ThompsonSamplingBanditAllocator


@dataclass(frozen=True)
class OptimizationExecutionResult:
    bandit_decision: Optional[BanditOptimizationResult]
    circuit_breaker: CircuitBreakerStatus
    action_taken: str


class OptimizeVariantAllocationUseCase:
    def __init__(self, repository: CGSPhase3RepositoryPort):
        self.repository = repository

    def execute(
        self,
        hypothesis_id: int,
        cycle_id: str,
        arms: List[VariantArm],
        current_cpa_reais: Decimal,
        max_allowed_cpa_reais: Optional[Decimal],
        current_spend_reais: Decimal,
        max_budget_reais: Decimal,
    ) -> OptimizationExecutionResult:
        control_arm = arms[0]
        treatment_arm = arms[1] if len(arms) > 1 else arms[0]

        # 1. Avalia o disjuntor de segurança antes de rebalancear
        breaker = ExperimentCircuitBreaker.evaluate(
            hypothesis_id=hypothesis_id,
            cycle_id=cycle_id,
            current_cpa_reais=current_cpa_reais,
            max_allowed_cpa_reais=max_allowed_cpa_reais,
            control_cr_pct=control_arm.empirical_cr_pct,
            treatment_cr_pct=treatment_arm.empirical_cr_pct,
            current_spend_reais=current_spend_reais,
            max_budget_reais=max_budget_reais,
        )

        if breaker.is_tripped:
            self.repository.record_circuit_breaker_event(breaker)
            return OptimizationExecutionResult(
                bandit_decision=None,
                circuit_breaker=breaker,
                action_taken=f"DISJUNTOR ACIONADO ({breaker.trigger_reason.value}). Teste desarmado e revertido para 100% controle.",
            )

        # 2. Executa alocação adaptativa via Thompson Sampling
        bandit_res = ThompsonSamplingBanditAllocator.rebalance_weights(
            hypothesis_id=hypothesis_id,
            cycle_id=cycle_id,
            arms=arms,
        )
        self.repository.save_bandit_decision(bandit_res)

        action = (
            f"Convergência atingida no braço '{bandit_res.leading_arm_id}'. Auto-scale ativado."
            if bandit_res.is_converged
            else "Pesos rebalanceados com sucesso."
        )

        return OptimizationExecutionResult(
            bandit_decision=bandit_res,
            circuit_breaker=breaker,
            action_taken=action,
        )