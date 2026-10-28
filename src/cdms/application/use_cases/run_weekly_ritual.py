import math
from datetime import date, datetime, timezone
from typing import Any, List, Optional

from cdms.application.ports.repository import RepositoryPort
from cdms.domain.entities.decision import Decision
from cdms.domain.entities.learning import HypothesisOutcome, Learning
from cdms.domain.entities.metric import MetricSnapshot
from cdms.domain.entities.scenario import Scenario
from cdms.domain.entities.weekly_ritual import WeeklyRitualRecord
from cdms.domain.services.scenario_classifier import ScenarioClassifier


class CycleAlreadyClosedError(Exception):
    """Lançado quando se tenta submeter conteúdo divergente para um ciclo já finalizado."""
    pass


class InvalidCycleDateError(Exception):
    """Lançado quando a data do ciclo não corresponde a uma segunda-feira."""
    pass


class RunWeeklyRitualUseCase:
    """
    Orquestra o fecho do ritual semanal de decisão única:
    - Validação de invariantes temporais (segunda-feira canónica).
    - Verificação de idempotência estrita (mesmo payload reutiliza; divergente bloqueia).
    - Validação e vínculo auditado de hipótese prévia (Learning).
    - Diagnóstico determinístico em cascata via ScenarioClassifier.
    - Persistência transacional atómica via RepositoryPort.
    """

    def __init__(
        self,
        repo: RepositoryPort,
        classifier: ScenarioClassifier,
        rules_version_or_settings: Any = "2.3.1",
        rules_version: Optional[str] = None,
        settings: Optional[Any] = None,
    ):
        self.repo = repo
        self.classifier = classifier

        # Resolução polimórfica da versão de regras sem acoplar fortemente à classe Settings
        source = settings if settings is not None else rules_version_or_settings
        if hasattr(source, "RULES_VERSION"):
            self.rules_version = getattr(source, "RULES_VERSION")
        elif rules_version is not None:
            self.rules_version = rules_version
        elif isinstance(source, str):
            self.rules_version = source
        else:
            self.rules_version = "2.3.1"

    def _validate_cycle_date(self, week_start: date) -> None:
        """Garante que a semana canónica inicia obrigatoriamente numa segunda-feira."""
        if week_start.weekday() != 0:
            raise InvalidCycleDateError(
                f"A data {week_start.isoformat()} não é uma segunda-feira (weekday {week_start.weekday()})."
            )

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
        learning_evidence_notes: Optional[str],
    ) -> bool:
        """Compara o conteúdo de negócio submetido com o registo previamente gravado."""
        # 1. Comparar atributos da decisão
        d = existing.decision
        if d.summary.strip() != decision_summary.strip():
            return False
        if d.hypothesis.strip() != decision_hypothesis.strip():
            return False
        if d.success_criterion.strip() != decision_success_criterion.strip():
            return False
        if d.evaluation_due_date != decision_evaluation_due_date:
            return False
        if d.owner.strip() != decision_owner.strip():
            return False

        # 2. Comparar snapshots ordenados deterministicamente por chave
        cur_snaps = sorted(snapshots, key=lambda s: s.definition.key)
        ex_snaps = sorted(existing.snapshots, key=lambda s: s.definition.key)
        if len(cur_snaps) != len(ex_snaps):
            return False

        for s_cur, s_ex in zip(cur_snaps, ex_snaps):
            if s_cur.definition.key != s_ex.definition.key:
                return False
            if s_cur.is_available != s_ex.is_available:
                return False
            if s_cur.is_available:
                if not math.isclose(s_cur.observed_value, s_ex.observed_value, rel_tol=1e-9):
                    return False
            else:
                if (s_cur.unavailability_reason or "").strip() != (s_ex.unavailability_reason or "").strip():
                    return False
            if not math.isclose(s_cur.calibration.healthy_min, s_ex.calibration.healthy_min, rel_tol=1e-9):
                return False
            if not math.isclose(s_cur.calibration.healthy_max, s_ex.calibration.healthy_max, rel_tol=1e-9):
                return False

        # 3. Comparar eventual aprendizado (Learning)
        if existing.learning is None and target_decision_id is None:
            return True
        if existing.learning is not None and target_decision_id is not None:
            l = existing.learning
            if l.target_decision_id != target_decision_id:
                return False
            if l.outcome != learning_outcome:
                return False
            if (l.evidence_notes or "").strip() != (learning_evidence_notes or "").strip():
                return False
            return True

        return False

    def _resolve_learning(
        self,
        week_start: date,
        cycle_id: str,
        target_decision_id: Optional[int],
        learning_outcome: Optional[HypothesisOutcome],
        learning_evidence_notes: Optional[str],
        evaluation_as_of: Optional[date],
    ) -> Optional[Learning]:
        """Valida e vincula a decisão anterior a ser auditada neste ciclo."""
        if target_decision_id is None:
            return None

        if learning_outcome is None:
            raise ValueError("Um aprendizado exige o preenchimento de HypothesisOutcome.")

        as_of_date = evaluation_as_of or week_start
        pending_decision = self.repo.get_pending_decision(
            before_week_start=week_start, evaluation_as_of=as_of_date
        )

        if not pending_decision or pending_decision.id != target_decision_id:
            raise ValueError(
                f"A decisão de ID {target_decision_id} não é uma pendência elegível para avaliação no ciclo {cycle_id}."
            )

        return Learning(
            id=None,
            target_decision_id=pending_decision.id,
            target_decision_summary=pending_decision.summary,
            outcome=learning_outcome,
            evidence_notes=(learning_evidence_notes or "").strip(),
        )

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
        evaluation_as_of: Optional[date] = None,
        source_hypothesis_id: Optional[int] = None,
    ) -> WeeklyRitualRecord:
        # 1. Validação temporal invariante
        self._validate_cycle_date(week_start)
        cycle_id = week_start.isoformat()

        # 2. Verificação de idempotência / ciclo já encerrado
        existing_ritual = self.repo.get_ritual_by_cycle(cycle_id)
        if existing_ritual:
            if existing_ritual.decision.source_hypothesis_id != source_hypothesis_id:
                raise CycleAlreadyClosedError(f"O ciclo {cycle_id} já possui outra decisão vinculada.")
            if self._is_equivalent_payload(
                existing=existing_ritual,
                snapshots=snapshots,
                decision_summary=decision_summary,
                decision_hypothesis=decision_hypothesis,
                decision_success_criterion=decision_success_criterion,
                decision_evaluation_due_date=decision_evaluation_due_date,
                decision_owner=decision_owner,
                target_decision_id=target_decision_id,
                learning_outcome=learning_outcome,
                learning_evidence_notes=learning_evidence_notes,
            ):
                return existing_ritual
            raise CycleAlreadyClosedError(
                f"O ciclo {cycle_id} já foi encerrado com conteúdo diferente e não pode ser sobrescrito."
            )

        # 3. Resolução e auditoria de hipótese do ciclo anterior
        learning = self._resolve_learning(
            week_start=week_start,
            cycle_id=cycle_id,
            target_decision_id=target_decision_id,
            learning_outcome=learning_outcome,
            learning_evidence_notes=learning_evidence_notes,
            evaluation_as_of=evaluation_as_of,
        )

        # 4. Diagnóstico de domínio puro pelas 81 combinações
        scenario = self.classifier.classify(snapshots)

        # 5. Instanciação da decisão prioritária
        decision = Decision(
            id=None,
            cycle_id=cycle_id,
            summary=decision_summary.strip(),
            hypothesis=decision_hypothesis.strip(),
            success_criterion=decision_success_criterion.strip(),
            evaluation_due_date=decision_evaluation_due_date,
            owner=decision_owner.strip(),
            source_hypothesis_id=source_hypothesis_id,
        )

        # 6. Agregador com carimbo de versão de regras
        record = WeeklyRitualRecord(
            id=None,
            cycle_id=cycle_id,
            week_start=week_start,
            snapshots=snapshots,
            scenario=scenario,
            decision=decision,
            learning=learning,
            rules_version=self.rules_version,
            completed_at=datetime.now(timezone.utc),
        )

        # 7. Persistência transacional
        return self.repo.save_ritual_atomic(record)