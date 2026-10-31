"""Inferência Beta-Binomial com prior Beta(1,1) e Monte Carlo reproduzível."""
from decimal import Decimal
from functools import lru_cache
import random
from cgs.domain.entities.statistical_validation import BayesianExperimentEvaluation, StatisticalSignificanceVerdict as Verdict

@lru_cache(maxsize=128)
def posterior(c, n, t, m):
    rng = random.Random(1729)
    differences = sorted((rng.betavariate(t+1, m-t+1) - rng.betavariate(c+1, n-c+1)) * 100 for _ in range(30000))
    return (Decimal(str(round(sum(d > 0 for d in differences)/len(differences)*100, 2))),
            Decimal(str(round(differences[749], 4))), Decimal(str(round(differences[29249], 4))))

class BayesianExperimentAnalyzer:
    @classmethod
    def evaluate(cls, hypothesis_id, control_conversions, control_sample, treatment_conversions,
                 treatment_sample, sample_minimum=100, significance_threshold_pct=Decimal('95'), cycle_id=None,
                 event_definition='Conversão binária por unidade exposta'):
        if not isinstance(event_definition,str) or not event_definition.strip() or len(event_definition)>500:
            raise ValueError('Descreva o evento binário de conversão em até 500 caracteres.')
        for conversions, sample in ((control_conversions, control_sample), (treatment_conversions, treatment_sample)):
            if type(sample) is not int or type(conversions) is not int or sample <= 0 or not 0 <= conversions <= sample:
                raise ValueError('Informe amostras positivas e conversões inteiras entre zero e a amostra.')
        if type(sample_minimum) is not int or sample_minimum <= 0:
            raise ValueError('A amostra mínima deve ser um inteiro positivo.')
        threshold = Decimal(str(significance_threshold_pct))
        if not threshold.is_finite() or not 50 < threshold < 100:
            raise ValueError('O limiar deve estar entre 50 e 100%.')
        c, t = Decimal(control_conversions)/control_sample, Decimal(treatment_conversions)/treatment_sample
        lift = ((t-c)/c*100).quantize(Decimal('.01')) if c else None
        raw_adequacy = Decimal(min(control_sample,treatment_sample))/sample_minimum
        adequacy = raw_adequacy.quantize(Decimal('.01'))
        probability, low, high = posterior(control_conversions,control_sample,treatment_conversions,treatment_sample)
        if raw_adequacy < Decimal('.5'):
            verdict = Verdict.INCONCLUSIVE_INSUFFICIENT_SAMPLE
        elif lift is not None and lift < -30 and probability <= 100-threshold:
            verdict = Verdict.EARLY_STOPPED_HIGH_LOSS
        elif raw_adequacy < 1:
            verdict = Verdict.INCONCLUSIVE_INSUFFICIENT_SAMPLE
        elif probability >= threshold:
            verdict = Verdict.STATISTICALLY_SIGNIFICANT
        else:
            verdict = Verdict.NO_EFFECT_DETECTED
        return BayesianExperimentEvaluation(hypothesis_id, control_conversions, control_sample,
            treatment_conversions, treatment_sample, probability, lift, verdict, adequacy,
            cycle_id=cycle_id, difference_low_pp=low, difference_high_pp=high,
            sample_minimum=sample_minimum, significance_threshold_pct=threshold,event_definition=event_definition.strip())
