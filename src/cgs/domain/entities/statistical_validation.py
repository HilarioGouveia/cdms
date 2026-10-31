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
    lift_pct: Decimal | None              # Indefinido quando controle tem zero conversões
    verdict: StatisticalSignificanceVerdict
    sample_adequacy_ratio: Decimal        # amostra observada / amostra mínima exigida
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    cycle_id: str | None = None
    method: str = 'beta-binomial-mc-v1'
    difference_low_pp: Decimal | None = None
    difference_high_pp: Decimal | None = None
    sample_minimum: int = 100
    significance_threshold_pct: Decimal = Decimal('95')
    event_definition: str = 'Conversão binária por unidade exposta'
