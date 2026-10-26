import unittest
from itertools import product
from cdms.domain.entities.metric import (
    MetricDefinition,
    MetricCalibration,
    MetricSnapshot,
)
from cdms.domain.entities.scenario import (
    ScenarioType,
    InconclusiveReason,
)
from cdms.domain.services.scenario_classifier import ScenarioClassifier

class TestDiagnoseScenario(unittest.TestCase):
    def setUp(self):
        self.classifier = ScenarioClassifier()
        self.keys = ["reach", "avg_retention_pct", "ctr_pct", "conversions"]

    def _make_snapshot(self, key: str, status_target: str) -> MetricSnapshot:
        m_def = MetricDefinition(key, key, "un", "desc")
        m_cal = MetricCalibration(key, 100.0, 200.0)
        
        if status_target == "BELOW":
            val = 50.0
        elif status_target == "ABOVE":
            val = 250.0
        else: # HEALTHY
            val = 150.0

        if key in {"reach", "conversions"}:
            val = float(int(val))

        return MetricSnapshot(m_def, m_cal, val)

    def test_all_81_combinations_coverage(self):
        """Valida que o motor em cascata resolve as 81 combinações teóricas conforme a tabela de precedência."""
        states = ["BELOW", "HEALTHY", "ABOVE"]
        all_combinations = list(product(states, repeat=4))
        self.assertEqual(len(all_combinations), 81)

        counts = {
            ScenarioType.PRE_DROP: 0,
            ScenarioType.ANOMALY: 0,
            ScenarioType.SCALE: 0,
            ScenarioType.STABILITY: 0,
            ScenarioType.INCONCLUSIVE: 0,
        }

        for comb in all_combinations:
            snaps = [self._make_snapshot(k, s) for k, s in zip(self.keys, comb)]
            scenario = self.classifier.classify(snaps)
            counts[scenario.type] += 1
            
            # Nas 4 combinações inconclusivas das 81 (1 BELOW e 3 HEALTHY), motivo deve ser MIXED_SIGNALS
            if scenario.type == ScenarioType.INCONCLUSIVE:
                self.assertEqual(scenario.inconclusive_reason, InconclusiveReason.MIXED_SIGNALS)

        # Validação estrita das frequências teóricas da SDD v2.3.1
        self.assertEqual(counts[ScenarioType.PRE_DROP], 33)
        self.assertEqual(counts[ScenarioType.ANOMALY], 28)
        self.assertEqual(counts[ScenarioType.SCALE], 11)
        self.assertEqual(counts[ScenarioType.STABILITY], 5)
        self.assertEqual(counts[ScenarioType.INCONCLUSIVE], 4)

    def test_guard_missing_data(self):
        # 1. Menos de 4 métricas
        snaps_missing = [self._make_snapshot("reach", "HEALTHY")]
        scen = self.classifier.classify(snaps_missing)
        self.assertEqual(scen.type, ScenarioType.INCONCLUSIVE)
        self.assertEqual(scen.inconclusive_reason, InconclusiveReason.MISSING_DATA)

        # 2. Métricas duplicadas
        snaps_dup = [
            self._make_snapshot("reach", "HEALTHY"),
            self._make_snapshot("reach", "HEALTHY"),
            self._make_snapshot("avg_retention_pct", "HEALTHY"),
            self._make_snapshot("ctr_pct", "HEALTHY"),
        ]
        scen_dup = self.classifier.classify(snaps_dup)
        self.assertEqual(scen_dup.type, ScenarioType.INCONCLUSIVE)
        self.assertEqual(scen_dup.inconclusive_reason, InconclusiveReason.MISSING_DATA)

    def test_guard_unavailable_metric(self):
        # Métrica indisponível no ciclo conduz imediatamente a MISSING_DATA
        snap_unavail = MetricSnapshot(
            MetricDefinition("reach", "reach", "un", "desc"),
            MetricCalibration("reach", 100.0, 200.0),
            None,
            is_available=False,
            unavailability_reason="ZERO_IMPRESSIONS"
        )
        snaps = [snap_unavail] + [self._make_snapshot(k, "HEALTHY") for k in ["avg_retention_pct", "ctr_pct", "conversions"]]
        scen = self.classifier.classify(snaps)
        self.assertEqual(scen.type, ScenarioType.INCONCLUSIVE)
        self.assertEqual(scen.inconclusive_reason, InconclusiveReason.MISSING_DATA)
        self.assertIn("reach", scen.evidence_metric_keys)