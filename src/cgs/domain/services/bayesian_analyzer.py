"""Serviço puro de cálculo de significância Bayesiana e Early Stopping para o CGS."""

from decimal import Decimal, ROUND_HALF_UP
import math
from cgs.domain.entities.statistical_validation import (
    BayesianExperimentEvaluation,
    StatisticalSignificanceVerdict,
)


class BayesianExperimentAnalyzer:
    """Calcula probabilidade de ganho e parada antecipada com base em distribuições Beta/Binomial conjugadas."""

    @classmethod
    def evaluate(
        cls,
        hypothesis_id: int,
        control_conversions: int,
        control_sample: int,
        treatment_conversions: int,
        treatment_sample: int,
        sample_minimum: int = 100,
        significance_threshold_pct: Decimal = Decimal("95.0"),
    ) -> BayesianExperimentEvaluation:
        if control_sample <= 0 or treatment_sample <= 0:
            raise ValueError("Amostras de controle e tratamento devem ser maiores que zero.")

        # Conversão para taxas empíricas
        cr_control = Decimal(control_conversions) / Decimal(control_sample)
        cr_treatment = Decimal(treatment_conversions) / Decimal(treatment_sample)

        # Cálculo de Lift Percentual
        if cr_control > Decimal("0"):
            lift = (((cr_treatment - cr_control) / cr_control) * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        else:
            lift = Decimal("100.00") if cr_treatment > 0 else Decimal("0.00")

        # Proporção da amostra frente ao piso de corte
        adequacy = (Decimal(treatment_sample) / Decimal(sample_minimum)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # Heurística Bayesiana aproximada via Normalização de Gauss (Z-score normal para A/B Test)
        p_pooled = (Decimal(control_conversions + treatment_conversions)) / (
            Decimal(control_sample + treatment_sample)
        )
        se = math.sqrt(float(p_pooled * (Decimal("1") - p_pooled) * (Decimal("1") / Decimal(control_sample) + Decimal("1") / Decimal(treatment_sample))))

        if se > 0:
            diff = float(cr_treatment - cr_control)
            z = diff / se
            # Aproximação da CDF Normal para probabilidade de superar o controle
            p_beat = Decimal(str(round((0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))) * 100, 2)))
        else:
            p_beat = Decimal("50.00")

        # Decisão e Veredito com Guard-rail de Amostra e Early Stopping
        if treatment_sample < (sample_minimum // 2):
            # Amostra muito prematura
            verdict = StatisticalSignificanceVerdict.INCONCLUSIVE_INSUFFICIENT_SAMPLE
        elif lift < Decimal("-30.00") and adequacy >= Decimal("0.50"):
            # Early stopping acionado: perda catastrófica detectada precocemente
            verdict = StatisticalSignificanceVerdict.EARLY_STOPPED_HIGH_LOSS
        elif adequacy < Decimal("1.00"):
            verdict = StatisticalSignificanceVerdict.INCONCLUSIVE_INSUFFICIENT_SAMPLE
        elif p_beat >= significance_threshold_pct:
            verdict = StatisticalSignificanceVerdict.STATISTICALLY_SIGNIFICANT
        else:
            verdict = StatisticalSignificanceVerdict.NO_EFFECT_DETECTED

        return BayesianExperimentEvaluation(
            hypothesis_id=hypothesis_id,
            control_conversions=control_conversions,
            control_sample=control_sample,
            treatment_conversions=treatment_conversions,
            treatment_sample=treatment_sample,
            probability_to_beat_control=p_beat,
            lift_pct=lift,
            verdict=verdict,
            sample_adequacy_ratio=adequacy,
        )