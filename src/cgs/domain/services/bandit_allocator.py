"""Serviço puro de alocação probabilística com Thompson Sampling."""

from decimal import Decimal, ROUND_HALF_UP
import random
from typing import Dict, List
from cgs.domain.entities.bandit_policy import (
    BanditOptimizationResult,
    ExplorationStrategy,
    VariantArm,
)


class ThompsonSamplingBanditAllocator:
    """Implementação pura de Thompson Sampling para teste adaptativo contínuo."""

    @classmethod
    def rebalance_weights(
        cls,
        hypothesis_id: int,
        cycle_id: str,
        arms: List[VariantArm],
        simulations_count: int = 10000,
        min_exploration_pct: Decimal = Decimal("10.00"),
    ) -> BanditOptimizationResult:
        if len(arms) < 2:
            raise ValueError("Otimização adaptativa exige pelo menos 2 braços concorrentes.")

        wins: Dict[str, int] = {arm.arm_id: 0 for arm in arms}

        # Simulação Monte Carlo sobre a posterior Beta(alpha, beta)
        for _ in range(simulations_count):
            samples = {
                arm.arm_id: random.betavariate(
                    arm.alpha_prior + arm.total_conversions,
                    arm.beta_prior + max(0, arm.total_impressions - arm.total_conversions),
                )
                for arm in arms
            }
            winner = max(samples, key=samples.get)
            wins[winner] += 1

        total_sims = Decimal(str(simulations_count))
        raw_weights = {
            arm_id: ((Decimal(win_count) / total_sims) * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            for arm_id, win_count in wins.items()
        }

        # Aplicação de piso mínimo de exploração (evita sufocamento precoce de variantes)
        floor_applied_weights: Dict[str, Decimal] = {}
        for arm_id, w in raw_weights.items():
            floor_applied_weights[arm_id] = max(min_exploration_pct, w)

        total_adjusted = sum(floor_applied_weights.values())
        final_weights = {
            arm_id: ((w / total_adjusted) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            for arm_id, w in floor_applied_weights.items()
        }

        leading_arm = max(final_weights, key=final_weights.get)
        is_converged = final_weights[leading_arm] >= Decimal("85.00")

        return BanditOptimizationResult(
            hypothesis_id=hypothesis_id,
            cycle_id=cycle_id,
            strategy=ExplorationStrategy.THOMPSON_SAMPLING,
            arm_weights=final_weights,
            leading_arm_id=leading_arm,
            is_converged=is_converged,
        )