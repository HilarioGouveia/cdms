import unittest
import math
from cdms.domain.entities.metric import (
    MetricStatus,
    MetricDefinition,
    MetricCalibration,
    MetricSnapshot,
)

class TestMetrics(unittest.TestCase):
    def setUp(self):
        self.def_reach = MetricDefinition("reach", "Alcance Semanal", "un", "Total de contas únicas alcançadas")
        self.def_ret = MetricDefinition("avg_retention_pct", "Retenção Média", "%", "Média ponderada da retenção")
        self.cal_reach = MetricCalibration("reach", 1000.0, 5000.0)
        self.cal_ret = MetricCalibration("avg_retention_pct", 30.0, 60.0)

    def test_calibration_validations(self):
        # Validação de min > max
        with self.assertRaises(ValueError):
            MetricCalibration("reach", 6000.0, 5000.0)

        # Validação de valores negativos
        with self.assertRaises(ValueError):
            MetricCalibration("reach", -100.0, 5000.0)

        # Validação de NaN e Infinito
        with self.assertRaises(ValueError):
            MetricCalibration("reach", float("nan"), 5000.0)
        with self.assertRaises(ValueError):
            MetricCalibration("reach", 1000.0, float("inf"))

        # Validação de tipo booleano
        with self.assertRaises(ValueError):
            MetricCalibration("reach", True, 5000.0)

    def test_snapshot_status_and_deviation(self):
        # Snapshot Saudável
        snap_h = MetricSnapshot(self.def_reach, self.cal_reach, 3000.0)
        self.assertEqual(snap_h.status(), MetricStatus.HEALTHY)
        self.assertEqual(snap_h.deviation_pct(), 0.0)

        # Snapshot Abaixo (BELOW)
        snap_b = MetricSnapshot(self.def_reach, self.cal_reach, 800.0)
        self.assertEqual(snap_b.status(), MetricStatus.BELOW)
        self.assertEqual(snap_b.deviation_pct(), -20.0)

        # Snapshot Acima (ABOVE)
        snap_a = MetricSnapshot(self.def_reach, self.cal_reach, 6000.0)
        self.assertEqual(snap_a.status(), MetricStatus.ABOVE)
        self.assertEqual(snap_a.deviation_pct(), 20.0)

    def test_snapshot_integer_counts_constraint(self):
        # Métricas reach e conversions exigem valores inteiros
        with self.assertRaises(ValueError):
            MetricSnapshot(self.def_reach, self.cal_reach, 1500.5)

        # Retenção aceita float decimal normalmente
        snap_ret = MetricSnapshot(self.def_ret, self.cal_ret, 42.5)
        self.assertEqual(snap_ret.status(), MetricStatus.HEALTHY)

    def test_snapshot_unavailability(self):
        # Métrica indisponível exige valor None e motivo preenchido
        snap_unavail = MetricSnapshot(
            self.def_reach,
            self.cal_reach,
            None,
            is_available=False,
            unavailability_reason="NO_EXPOSURE"
        )
        self.assertFalse(snap_unavail.is_available)
        self.assertIsNone(snap_unavail.status())
        self.assertIsNone(snap_unavail.deviation_pct())

        # Violação: indisponível com valor preenchido
        with self.assertRaises(ValueError):
            MetricSnapshot(self.def_reach, self.cal_reach, 2000.0, is_available=False, unavailability_reason="NO_EXPOSURE")

        # Violação: indisponível sem motivo
        with self.assertRaises(ValueError):
            MetricSnapshot(self.def_reach, self.cal_reach, None, is_available=False, unavailability_reason=None)

    def test_snapshot_zero_reference_deviation(self):
        # Quando o limite é zero, desvio percentual deve retornar None (indisponível)
        cal_zero = MetricCalibration("reach", 0.0, 0.0)
        snap_zero = MetricSnapshot(self.def_reach, cal_zero, 50.0)
        self.assertEqual(snap_zero.status(), MetricStatus.ABOVE)
        self.assertIsNone(snap_zero.deviation_pct())

    def test_snapshot_key_mismatch(self):
        cal_wrong = MetricCalibration("other_key", 10.0, 50.0)
        with self.assertRaises(ValueError):
            MetricSnapshot(self.def_reach, cal_wrong, 25.0)