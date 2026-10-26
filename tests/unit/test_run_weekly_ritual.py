import unittest
from datetime import date, timedelta
from typing import List, Optional

from cdms.config.settings import Settings
from cdms.application.ports.repository import RepositoryPort
from cdms.domain.services.scenario_classifier import ScenarioClassifier
from cdms.domain.entities.metric import MetricDefinition, MetricCalibration, MetricSnapshot
from cdms.domain.entities.decision import Decision
from cdms.domain.entities.learning import HypothesisOutcome
from cdms.domain.entities.weekly_ritual import WeeklyRitualRecord
from cdms.application.use_cases.run_weekly_ritual import (
    RunWeeklyRitualUseCase,
    CycleAlreadyClosedError,
    InvalidCycleDateError,
)

class InMemoryRepoStub(RepositoryPort):
    def __init__(self):
        self.rituals = {}
        self.calibrations = {}

    def save_ritual_atomic(self, ritual: WeeklyRitualRecord) -> WeeklyRitualRecord:
        ritual.id = len(self.rituals) + 1
        ritual.decision.id = ritual.id
        self.rituals[ritual.cycle_id] = ritual
        return ritual

    def get_ritual_by_cycle(self, cycle_id: str) -> Optional[WeeklyRitualRecord]:
        return self.rituals.get(cycle_id)

    def get_pending_decision(self, before_week_start: date, evaluation_as_of: date) -> Optional[Decision]:
        for r in reversed(list(self.rituals.values())):
            d = r.decision
            if r.week_start < before_week_start and d.evaluation_due_date <= evaluation_as_of:
                evaluated = any(
                    rec.learning and rec.learning.target_decision_id == d.id
                    for rec in self.rituals.values()
                )
                if not evaluated:
                    return d
        return None

    def list_rituals(self, limit: int = 20) -> List[WeeklyRitualRecord]:
        return list(self.rituals.values())[:limit]

    def save_metric_calibration(self, calibration: MetricCalibration) -> None:
        self.calibrations[calibration.metric_key] = calibration

    def get_active_calibrations(self) -> List[MetricCalibration]:
        return list(self.calibrations.values())

class TestRunWeeklyRitual(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryRepoStub()
        self.classifier = ScenarioClassifier()
        self.settings = Settings()
        self.use_case = RunWeeklyRitualUseCase(self.repo, self.classifier, self.settings)
        self.monday = date(2026, 10, 19)

    def _get_valid_snapshots(self):
        return [
            MetricSnapshot(MetricDefinition("reach", "Alcance", "un", ""), MetricCalibration("reach", 1000, 5000), 2500.0),
            MetricSnapshot(MetricDefinition("avg_retention_pct", "Retenção", "%", ""), MetricCalibration("avg_retention_pct", 30, 60), 45.0),
            MetricSnapshot(MetricDefinition("ctr_pct", "CTR", "%", ""), MetricCalibration("ctr_pct", 2, 5), 3.5),
            MetricSnapshot(MetricDefinition("conversions", "Conversões", "un", ""), MetricCalibration("conversions", 10, 30), 20.0),
        ]

    def test_run_ritual_flow_and_idempotency(self):
        snaps = self._get_valid_snapshots()
        
        # 1. Finalização com sucesso
        record1 = self.use_case.execute(
            week_start=self.monday,
            snapshots=snaps,
            decision_summary="Testar gancho",
            decision_hypothesis="Aumentar CTR",
            decision_success_criterion="CTR >= 3.5%",
            decision_evaluation_due_date=self.monday + timedelta(days=7)
        )
        self.assertEqual(record1.cycle_id, "2026-10-19")
        self.assertEqual(record1.rules_version, "2.3.1")

        # 2. Reenvio idempotente idêntico -> retorna mesmo registro
        record1_dup = self.use_case.execute(
            week_start=self.monday,
            snapshots=snaps,
            decision_summary="Testar gancho",
            decision_hypothesis="Aumentar CTR",
            decision_success_criterion="CTR >= 3.5%",
            decision_evaluation_due_date=self.monday + timedelta(days=7)
        )
        self.assertEqual(record1.id, record1_dup.id)

        # 3. Reenvio com payload divergente -> lança CycleAlreadyClosedError
        with self.assertRaises(CycleAlreadyClosedError):
            self.use_case.execute(
                week_start=self.monday,
                snapshots=snaps,
                decision_summary="Decisão alterada",
                decision_hypothesis="Nova hipótese",
                decision_success_criterion="CTR >= 5.0%",
                decision_evaluation_due_date=self.monday + timedelta(days=7)
            )

    def test_reject_non_monday_cycle(self):
        wednesday = date(2026, 10, 21)
        with self.assertRaises(InvalidCycleDateError):
            self.use_case.execute(
                week_start=wednesday,
                snapshots=self._get_valid_snapshots(),
                decision_summary="Ação",
                decision_hypothesis="Hipótese",
                decision_success_criterion="Critério",
                decision_evaluation_due_date=wednesday + timedelta(days=7)
            )

    def test_retroactive_decision_auditing_flow(self):
        snaps = self._get_valid_snapshots()
        # Semana 1
        rec1 = self.use_case.execute(
            week_start=self.monday,
            snapshots=snaps,
            decision_summary="Ação W1",
            decision_hypothesis="Hipótese W1",
            decision_success_criterion="Critério W1",
            decision_evaluation_due_date=self.monday + timedelta(days=7)
        )

        # Semana 2 (Segunda seguinte)
        next_monday = self.monday + timedelta(days=7)
        rec2 = self.use_case.execute(
            week_start=next_monday,
            snapshots=snaps,
            decision_summary="Ação W2",
            decision_hypothesis="Hipótese W2",
            decision_success_criterion="Critério W2",
            decision_evaluation_due_date=next_monday + timedelta(days=7),
            target_decision_id=rec1.decision.id,
            learning_outcome=HypothesisOutcome.ACHIEVED,
            learning_evidence_notes="Meta batida com folga",
            evaluation_as_of=next_monday
        )
        self.assertIsNotNone(rec2.learning)
        self.assertEqual(rec2.learning.target_decision_id, rec1.decision.id)
        self.assertEqual(rec2.learning.outcome, HypothesisOutcome.ACHIEVED)