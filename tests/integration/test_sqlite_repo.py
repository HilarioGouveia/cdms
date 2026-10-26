import unittest
from pathlib import Path
from datetime import date, timedelta
import sqlite3

from cdms.domain.entities.metric import MetricDefinition, MetricCalibration, MetricSnapshot
from cdms.domain.entities.scenario import Scenario, ScenarioType
from cdms.domain.entities.decision import Decision
from cdms.domain.entities.learning import Learning, HypothesisOutcome
from cdms.domain.entities.weekly_ritual import WeeklyRitualRecord
from cdms.adapters.persistence.sqlite_repo import SQLiteRepository

class TestSQLiteRepository(unittest.TestCase):
    def setUp(self):
        self.db_path = Path("data/test_integration.db")
        if self.db_path.exists():
            self.db_path.unlink()
        self.repo = SQLiteRepository(self.db_path)

    def tearDown(self):
        if self.db_path.exists():
            self.db_path.unlink()

    def _get_snapshots(self):
        m_def = MetricDefinition("reach", "Alcance", "un", "desc")
        m_cal = MetricCalibration("reach", 1000.0, 5000.0)
        return [MetricSnapshot(m_def, m_cal, 2000.0)]

    def test_atomic_persistence_and_rollback(self):
        # 1. Salvar ritual válido
        dec = Decision(
            id=None,
            cycle_id="2026-10-19",
            summary="Ação Integrada",
            hypothesis="Hipótese Integrada",
            success_criterion="Critério Integrado",
            evaluation_due_date=date(2026, 10, 26)
        )
        scen = Scenario(ScenarioType.STABILITY, "Equilíbrio", "Manter", ["reach"])
        ritual = WeeklyRitualRecord(
            id=None,
            cycle_id="2026-10-19",
            week_start=date(2026, 10, 19),
            snapshots=self._get_snapshots(),
            scenario=scen,
            decision=dec,
            rules_version="2.3.1"
        )
        saved = self.repo.save_ritual_atomic(ritual)
        self.assertIsNotNone(saved.id)

        # 2. Testar violação de unicidade de cycle_id -> rollback atômico
        dup_dec = Decision(
            id=None,
            cycle_id="2026-10-19",
            summary="Ação Duplicada",
            hypothesis="Hipótese Duplicada",
            success_criterion="Critério",
            evaluation_due_date=date(2026, 10, 26)
        )
        dup_ritual = WeeklyRitualRecord(
            id=None,
            cycle_id="2026-10-19",
            week_start=date(2026, 10, 19),
            snapshots=self._get_snapshots(),
            scenario=scen,
            decision=dup_dec,
            rules_version="2.3.1"
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.save_ritual_atomic(dup_ritual)

        # Confirmar que a base continua íntegra com apenas 1 registro
        all_rituals = self.repo.list_rituals()
        self.assertEqual(len(all_rituals), 1)

    def test_calibration_upsert_flow(self):
        cal1 = MetricCalibration("reach", 1000.0, 5000.0)
        self.repo.save_metric_calibration(cal1)
        
        # Atualizar mesma chave (upsert)
        cal2 = MetricCalibration("reach", 1500.0, 6000.0)
        self.repo.save_metric_calibration(cal2)

        active = self.repo.get_active_calibrations()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].healthy_min, 1500.0)
        self.assertEqual(active[0].healthy_max, 6000.0)