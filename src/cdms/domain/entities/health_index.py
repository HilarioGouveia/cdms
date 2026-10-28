"""Entidade do Creator Health Index (Score Composto Ponderado de 0 a 100)."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum


class HealthTier(str, Enum):
    EXCELLENT = "EXCELLENT"  # >= 80
    HEALTHY = "HEALTHY"      # >= 60 e < 80
    VULNERABLE = "VULNERABLE" # >= 40 e < 60
    CRITICAL = "CRITICAL"    # < 40


@dataclass(frozen=True)
class CreatorHealthIndex:
    """Score unificado ponderado refletindo saúde operacional e financeira do criador."""
    workspace_id: str
    cycle_id: str
    reach_score: Decimal          # Peso 20%
    retention_score: Decimal      # Peso 25%
    ctr_score: Decimal            # Peso 25%
    conversion_score: Decimal     # Peso 30%
    composite_score: Decimal
    tier: HealthTier
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        for score, name in [
            (self.reach_score, "reach_score"),
            (self.retention_score, "retention_score"),
            (self.ctr_score, "ctr_score"),
            (self.conversion_score, "conversion_score"),
            (self.composite_score, "composite_score"),
        ]:
            if not isinstance(score, Decimal):
                raise TypeError(f"{name} deve ser um Decimal.")
            if not (Decimal("0.0") <= score <= Decimal("100.0")):
                raise ValueError(f"{name} deve estar contido entre 0 e 100.")