"""Serviço puro de cálculo do Creator Health Index."""

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict
from cdms.domain.entities.health_index import CreatorHealthIndex, HealthTier
from cdms.domain.entities.weekly_ritual import WeeklyRitualRecord


class HealthIndexCalculator:
    """Calcula score unificado a partir das 4 métricas canônicas versus calibrações vigentes."""

    # Pesos do algoritmo de governança
    WEIGHTS = {
        "reach": Decimal("0.20"),
        "avg_retention_pct": Decimal("0.25"),
        "ctr_pct": Decimal("0.25"),
        "conversions": Decimal("0.30"),
    }

    @classmethod
    def calculate(cls, workspace_id: str, ritual: WeeklyRitualRecord) -> CreatorHealthIndex:
        scores: Dict[str, Decimal] = {}

        for snap in ritual.snapshots:
            key = snap.definition.key
            if not snap.is_available or snap.observed_value is None:
                scores[key] = Decimal("0.0")
                continue

            obs = Decimal(str(snap.observed_value))
            p10 = Decimal(str(snap.calibration.healthy_min))
            p90 = Decimal(str(snap.calibration.healthy_max))

            if p90 <= p10:
                score = Decimal("100.0") if obs >= p10 else Decimal("0.0")
            elif obs < p10:
                # Abaixo do piso: interpola de 0 a 50
                ratio = max(Decimal("0.0"), obs / p10) if p10 > Decimal("0") else Decimal("0.0")
                score = (ratio * Decimal("50.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            elif obs <= p90:
                # Dentro da faixa saudável: pontuação entre 60 e 90
                ratio = (obs - p10) / (p90 - p10)
                score = (Decimal("60.0") + ratio * Decimal("30.0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                # Acima do teto saudável: alavancagem de 90 a 100
                score = Decimal("100.0")

            scores[key] = min(Decimal("100.0"), max(Decimal("0.0"), score))

        composite = (
            scores["reach"] * cls.WEIGHTS["reach"]
            + scores["avg_retention_pct"] * cls.WEIGHTS["avg_retention_pct"]
            + scores["ctr_pct"] * cls.WEIGHTS["ctr_pct"]
            + scores["conversions"] * cls.WEIGHTS["conversions"]
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if composite >= Decimal("80.0"):
            tier = HealthTier.EXCELLENT
        elif composite >= Decimal("60.0"):
            tier = HealthTier.HEALTHY
        elif composite >= Decimal("40.0"):
            tier = HealthTier.VULNERABLE
        else:
            tier = HealthTier.CRITICAL

        return CreatorHealthIndex(
            workspace_id=workspace_id,
            cycle_id=ritual.cycle_id,
            reach_score=scores["reach"],
            retention_score=scores["avg_retention_pct"],
            ctr_score=scores["ctr_pct"],
            conversion_score=scores["conversions"],
            composite_score=composite,
            tier=tier,
        )