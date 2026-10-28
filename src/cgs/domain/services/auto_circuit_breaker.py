"""Serviço de disjuntor de segurança e rollback operacional automatizado."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from cgs.domain.entities.bandit_policy import AutoRollbackTrigger, CircuitBreakerStatus


class ExperimentCircuitBreaker:
    """Avalia integridade em tempo real e desarma testes operacionais que gerem perda catastrófica."""

    @classmethod
    def evaluate(
        cls,
        hypothesis_id: int,
        cycle_id: str,
        current_cpa_reais: Decimal,
        max_allowed_cpa_reais: Optional[Decimal],
        control_cr_pct: Decimal,
        treatment_cr_pct: Decimal,
        current_spend_reais: Decimal,
        max_budget_reais: Decimal,
    ) -> CircuitBreakerStatus:
        # 1. Checagem de explosão de CPA
        if max_allowed_cpa_reais is not None and current_cpa_reais > (max_allowed_cpa_reais * Decimal("1.50")):
            return CircuitBreakerStatus(
                hypothesis_id=hypothesis_id,
                cycle_id=cycle_id,
                is_tripped=True,
                trigger_reason=AutoRollbackTrigger.CPA_SPIKE,
                observed_metric_value=current_cpa_reais,
                threshold_limit_value=max_allowed_cpa_reais,
                tripped_at=datetime.now(timezone.utc),
            )

        # 2. Checagem de colapso de conversão frente ao controle
        if control_cr_pct > Decimal("0"):
            relative_loss = (control_cr_pct - treatment_cr_pct) / control_cr_pct
            if relative_loss >= Decimal("0.40") and current_spend_reais >= (max_budget_reais * Decimal("0.20")):
                return CircuitBreakerStatus(
                    hypothesis_id=hypothesis_id,
                    cycle_id=cycle_id,
                    is_tripped=True,
                    trigger_reason=AutoRollbackTrigger.CONVERSION_COLLAPSE,
                    observed_metric_value=treatment_cr_pct,
                    threshold_limit_value=control_cr_pct * Decimal("0.60"),
                    tripped_at=datetime.now(timezone.utc),
                )

        return CircuitBreakerStatus(
            hypothesis_id=hypothesis_id,
            cycle_id=cycle_id,
            is_tripped=False,
        )