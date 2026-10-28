"""Entidades de domínio para Alocação Adaptativa e Multi-Armed Bandits (CGS Fase 3)."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional


class ExplorationStrategy(str, Enum):
    THOMPSON_SAMPLING = "THOMPSON_SAMPLING"
    EPSILON_GREEDY = "EPSILON_GREEDY"
    UPPER_CONFIDENCE_BOUND = "UPPER_CONFIDENCE_BOUND"


class AutoRollbackTrigger(str, Enum):
    CPA_SPIKE = "CPA_SPIKE"                    # CPA explodiu acima do teto estipulado
    CONVERSION_COLLAPSE = "CONVERSION_COLLAPSE"  # Taxa caiu mais de 40% em relação ao controle
    NEGATIVE_REVENUE_IMPACT = "NEGATIVE_REVENUE_IMPACT"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"


@dataclass(frozen=True)
class VariantArm:
    """Braço experimental em teste com parâmetros de distribuição Beta."""
    arm_id: str
    variable_name: str
    alpha_prior: int = 1   # Sucessos acumulados + 1
    beta_prior: int = 1    # Falhas acumuladas + 1
    total_impressions: int = 0
    total_conversions: int = 0
    traffic_weight_pct: Decimal = Decimal("50.00")

    @property
    def empirical_cr_pct(self) -> Decimal:
        if self.total_impressions == 0:
            return Decimal("0.00")
        return ((Decimal(self.total_conversions) / Decimal(self.total_impressions)) * Decimal("100")).quantize(Decimal("0.01"))


@dataclass(frozen=True)
class BanditOptimizationResult:
    """Decisão do motor adaptativo de redistribuição dinâmica de tráfego."""
    hypothesis_id: int
    cycle_id: str
    strategy: ExplorationStrategy
    arm_weights: Dict[str, Decimal]  # arm_id -> novo percentual de tráfego
    leading_arm_id: str
    is_converged: bool
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class CircuitBreakerStatus:
    """Estado do disjuntor de segurança operacional para rollback automático."""
    hypothesis_id: int
    cycle_id: str
    is_tripped: bool
    trigger_reason: Optional[AutoRollbackTrigger] = None
    observed_metric_value: Optional[Decimal] = None
    threshold_limit_value: Optional[Decimal] = None
    tripped_at: Optional[datetime] = None