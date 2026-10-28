"""Entidades de significância e inferência experimental (Frequentista / Bayesiana)."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum


class StatisticalSignificanceVerdict(str, Enum):
    STATISTICALLY_SIGNIFICANT = "STATISTICALLY_SIGNIFICANT"
    INCONCLUSIVE_INSUFFICIENT_SAMPLE = "INCONCLUSIVE_INSUFFICIENT_SAMPLE"
    NO_EFFECT_DETECTED = "NO_EFFECT_DETECTED"
    EARLY_STOPPED_HIGH_LOSS = "EARLY_STOPPED_HIGH_LOSS"


@dataclass(frozen=True)
class BayesianExperimentEvaluation:
    """Resultado da validação inferencial sobre o ciclo de 7 dias."""
    hypothesis_id: int
    control_conversions: int
    control_sample: int
    treatment_conversions: int
    treatment_sample: int
    probability_to_beat_control: Decimal  # 0.00 a 100.00%
    lift_pct: Decimal                     # Percentual de elevação estimada
    verdict: StatisticalSignificanceVerdict
    sample_adequacy_ratio: Decimal        # amostra observada / amostra mínima exigida
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))