"""Entidades de domínio para Governança Orçamentária e Alocação de Capital no CGS (Fase 2)."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional


class ExperimentRiskTier(str, Enum):
    LOW = "LOW"          # Iterações cosméticas (ex: CTA, Hero text)
    MEDIUM = "MEDIUM"    # Ajustes estruturais de LP ou formato de vídeo
    HIGH = "HIGH"        # Mudança radical de oferta, precificação ou modelo


@dataclass(frozen=True)
class BudgetAllocation:
    """Alocação estrita de orçamento por hipótese, evitando sobre-alocação ou risco excessivo."""
    hypothesis_id: int
    cycle_id: str
    allocated_amount_cents: int
    spent_amount_cents: int = 0
    risk_tier: ExperimentRiskTier = ExperimentRiskTier.LOW
    max_cpa_target_cents: Optional[int] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if self.allocated_amount_cents <= 0:
            raise ValueError("allocated_amount_cents deve ser estritamente positivo.")
        if self.spent_amount_cents < 0:
            raise ValueError("spent_amount_cents não pode ser negativo.")
        if self.spent_amount_cents > self.allocated_amount_cents:
            raise ValueError("Gasto executado não pode exceder o teto alocado da hipótese.")

    @property
    def allocated_reais(self) -> Decimal:
        return (Decimal(self.allocated_amount_cents) / Decimal("100")).quantize(Decimal("0.01"))

    @property
    def spent_reais(self) -> Decimal:
        return (Decimal(self.spent_amount_cents) / Decimal("100")).quantize(Decimal("0.01"))

    @property
    def burn_rate_pct(self) -> Decimal:
        if self.allocated_amount_cents == 0:
            return Decimal("0.00")
        return ((Decimal(self.spent_amount_cents) / Decimal(self.allocated_amount_cents)) * Decimal("100")).quantize(Decimal("0.01"))