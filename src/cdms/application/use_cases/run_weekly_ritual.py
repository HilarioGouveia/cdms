from datetime import date, datetime, timezone
from typing import List, Optional
import math

from cdms.config.settings import Settings
from cdms.application.ports.repository import RepositoryPort
from cdms.domain.services.scenario_classifier import ScenarioClassifier
from cdms.domain.entities.metric import MetricSnapshot
from cdms.domain.entities.scenario import Scenario
from cdms.domain.entities.decision import Decision
from cdms.domain.entities.learning import Learning, HypothesisOutcome
from cdms.domain.entities.weekly_ritual import WeeklyRitualRecord

class CycleAlreadyClosedError(Exception):
    pass

class InvalidCycleDateError(Exception):
    pass

class RunWeeklyRitualUseCase:
    def __init__(self, repo: RepositoryPort, classifier: ScenarioClassifier, settings: Settings):
        self.repo = repo
        self.classifier = classifier
        self.settings = settings

    def _is_equivalent_payload(
        self,
        existing: WeeklyRitualRecord,
        snapshots: List[MetricSnapshot],
        decision_summary: str,
        decision_hypothesis: str,
        decision_success_criterion: str,
        decision_evaluation_due_date: date,
        decision_owner: str,
        target_decision_id: Optional[int],
        learning_outcome: Optional[HypothesisOutcome],
        learning_evidence_notes: Optional[str]
    ) -> bool:
        # Comparação normalizada de textos, calibrações, valores float e aprendizado
        ...

    def execute(
        self,
        week_start: date,
        snapshots: List[MetricSnapshot],
        decision_summary: str,
        decision_hypothesis: str,
        decision_success_criterion: str,
        decision_evaluation_due_date: date,
        decision_owner: str = "Creator",
        target_decision_id: Optional[int] = None,
        learning_outcome: Optional[HypothesisOutcome] = None,
        learning_evidence_notes: Optional[str] = None,
        evaluation_as_of: Optional[date] = None
    ) -> WeeklyRitualRecord:
        if week_start.weekday() != 0:
            raise InvalidCycleDateError(f"A data {week_start.isoformat()} não é uma segunda-feira.")

        cycle_id = week_start.isoformat()

        existing_ritual = self.repo.get_ritual_by_cycle(cycle_id)
        if existing_ritual:
            if self._is_equivalent_payload(...):
                return existing_ritual
            raise CycleAlreadyClosedError(f"O ciclo {cycle_id} já foi encerrado com conteúdo diferente.")

        learning = None
        if target_decision_id is not None:
            if learning_outcome is None:
                raise ValueError("Um aprendizado exige o preenchimento de HypothesisOutcome.")
            as_of_date = evaluation_as_of or week_start
            pending_decision = self.repo.get_pending_decision(before_week_start=week_start, evaluation_as_of=as_of_date)
            if not pending_decision or pending_decision.id != target_decision_id:
                raise ValueError(f"A decisão {target_decision_id} não é elegível para avaliação no ciclo {cycle_id}.")
            
            learning = Learning(
                id=None,
                target_decision_id=pending_decision.id,
                target_decision_summary=pending_decision.summary,
                outcome=learning_outcome,
                evidence_notes=(learning_evidence_notes or "").strip()
            )

        scenario = self.classifier.classify(snapshots)

        decision = Decision(
            id=None,
            cycle_id=cycle_id,
            summary=decision_summary.strip(),
            hypothesis=decision_hypothesis.strip(),
            success_criterion=decision_success_criterion.strip(),
            evaluation_due_date=decision_evaluation_due_date,
            owner=decision_owner.strip()
        )

        record = WeeklyRitualRecord(
            id=None,
            cycle_id=cycle_id,
            week_start=week_start,
            snapshots=snapshots,
            scenario=scenario,
            decision=decision,
            learning=learning,
            rules_version=self.settings.RULES_VERSION,
            completed_at=datetime.now(timezone.utc)
        )

        return self.repo.save_ritual_atomic(record)