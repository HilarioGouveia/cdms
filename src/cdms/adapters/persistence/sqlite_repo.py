import sqlite3
import json
from pathlib import Path
from datetime import datetime, date, timezone
from typing import List, Optional, Generator
from contextlib import contextmanager

from cdms.application.ports.repository import RepositoryPort
from cdms.domain.entities.metric import (
    MetricDefinition,
    MetricCalibration,
    MetricSnapshot,
)
from cdms.domain.entities.scenario import (
    Scenario,
    ScenarioType,
    InconclusiveReason,
)
from cdms.domain.entities.decision import Decision
from cdms.domain.entities.learning import Learning, HypothesisOutcome
from cdms.domain.entities.weekly_ritual import WeeklyRitualRecord


class SQLiteRepository(RepositoryPort):
    """
    Implementação concreta do Repositório SQLite utilizando a biblioteca padrão (Fase 1 - MVP).
    Garante integridade referencial (PRAGMA foreign_keys = ON), controlo transacional
    atómico com fecho determinístico de descritores e isolamento de ciclo.
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Garante a abertura, configuração e fecho determinístico da ligação."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Executa a criação do esquema base caso não exista."""
        schema_path = Path(__file__).parent / "schema.sql"
        if not schema_path.exists():
            raise FileNotFoundError(f"Ficheiro de esquema não encontrado em {schema_path}")

        with open(schema_path, "r", encoding="utf-8") as f:
            ddl = f.read()

        with self._connection() as conn:
            conn.executescript(ddl)
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(decisions)")}
            if "cgs_hypothesis_id" not in columns:
                conn.execute("ALTER TABLE decisions ADD COLUMN cgs_hypothesis_id INTEGER")
            cursor = conn.cursor()
            cursor.execute("SELECT version FROM schema_migrations WHERE version = 1")
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (1, "001_initial_schema", datetime.now(timezone.utc).isoformat())
                )
            conn.commit()

    def save_metric_calibration(self, calibration: MetricCalibration) -> None:
        with self._connection() as conn:
            conn.execute("""
                INSERT INTO metric_calibrations (metric_key, healthy_min, healthy_max, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(metric_key) DO UPDATE SET
                    healthy_min = excluded.healthy_min,
                    healthy_max = excluded.healthy_max,
                    updated_at = excluded.updated_at
            """, (
                calibration.metric_key,
                float(calibration.healthy_min),
                float(calibration.healthy_max),
                datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()

    def get_active_calibrations(self) -> List[MetricCalibration]:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT metric_key, healthy_min, healthy_max FROM metric_calibrations")
            return [
                MetricCalibration(
                    metric_key=r["metric_key"],
                    healthy_min=float(r["healthy_min"]),
                    healthy_max=float(r["healthy_max"])
                )
                for r in cursor.fetchall()
            ]

    def save_ritual_atomic(self, ritual: WeeklyRitualRecord) -> WeeklyRitualRecord:
        """
        Persiste atomicamente todo o agregado em transação única.
        Aplica ROLLBACK automático em caso de exceção.
        """
        with self._connection() as conn:
            try:
                cursor = conn.cursor()
                cursor.execute("BEGIN IMMEDIATE")

                # 1. Inserir ritual agregador
                evidence_json = json.dumps(ritual.scenario.evidence_metric_keys)
                cursor.execute("""
                    INSERT INTO weekly_rituals (
                        cycle_id, week_start, scenario_type, scenario_description,
                        scenario_recommendation, scenario_evidence_keys,
                        scenario_inconclusive_reason, rules_version, completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ritual.cycle_id,
                    ritual.week_start.isoformat(),
                    ritual.scenario.type.value,
                    ritual.scenario.description,
                    ritual.scenario.recommendation,
                    evidence_json,
                    ritual.scenario.inconclusive_reason.value if ritual.scenario.inconclusive_reason else None,
                    ritual.rules_version,
                    ritual.completed_at.isoformat()
                ))
                ritual_id = cursor.lastrowid
                ritual.id = ritual_id

                # 2. Inserir decisão associada
                cursor.execute("""
                    INSERT INTO decisions (
                        ritual_id, cycle_id, summary, hypothesis, success_criterion,
                        evaluation_due_date, owner, recorded_at, cgs_hypothesis_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ritual_id,
                    ritual.decision.cycle_id,
                    ritual.decision.summary,
                    ritual.decision.hypothesis,
                    ritual.decision.success_criterion,
                    ritual.decision.evaluation_due_date.isoformat(),
                    ritual.decision.owner,
                    ritual.decision.recorded_at.isoformat(),
                    ritual.decision.source_hypothesis_id,
                ))
                ritual.decision.id = cursor.lastrowid

                if ritual.decision.source_hypothesis_id is not None:
                    hypothesis_id = ritual.decision.source_hypothesis_id
                    conflict = conn.execute(
                        """SELECT active.id FROM growth_hypotheses active
                           JOIN growth_hypotheses candidate ON candidate.id = ?
                           WHERE active.status = 'ACTIVE' AND active.id != candidate.id
                             AND active.tested_variable = candidate.tested_variable
                             AND (active.target_cycle_id = ? OR active.target_cycle_id IS NULL)
                           LIMIT 1""", (hypothesis_id, ritual.cycle_id),
                    ).fetchone()
                    if conflict:
                        raise ValueError("Já existe hipótese ativa para esta variável no ciclo.")
                    cursor.execute(
                        """UPDATE growth_hypotheses
                           SET status = 'ACTIVE', target_cycle_id = ?, promoted_decision_id = ?
                           WHERE id = ? AND status IN ('PENDING', 'BACKLOG')
                             AND target_cycle_id = ? AND promoted_decision_id IS NULL""",
                        (ritual.cycle_id, ritual.decision.id, hypothesis_id, ritual.cycle_id),
                    )
                    if cursor.rowcount != 1:
                        raise ValueError("A proposta CGS não está pendente para este ciclo. Prepare-a novamente.")

                # 3. Inserir snapshots de métricas
                for s in ritual.snapshots:
                    cursor.execute("""
                        INSERT INTO metric_snapshots (
                            ritual_id, metric_key, metric_name, unit, description,
                            healthy_min, healthy_max, observed_value, is_available, unavailability_reason
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        ritual_id,
                        s.definition.key,
                        s.definition.name,
                        s.definition.unit,
                        s.definition.description,
                        float(s.calibration.healthy_min),
                        float(s.calibration.healthy_max),
                        float(s.observed_value) if s.observed_value is not None else None,
                        1 if s.is_available else 0,
                        s.unavailability_reason
                    ))

                # 4. Inserir aprendizagem auditada (se existir)
                if ritual.learning:
                    cursor.execute("""
                        INSERT INTO learnings (
                            ritual_id, target_decision_id, target_decision_summary,
                            outcome, evidence_notes, recorded_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        ritual_id,
                        ritual.learning.target_decision_id,
                        ritual.learning.target_decision_summary,
                        ritual.learning.outcome.value,
                        ritual.learning.evidence_notes,
                        ritual.learning.recorded_at.isoformat()
                    ))
                    ritual.learning.id = cursor.lastrowid
                    has_growth = conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'growth_hypotheses'"
                    ).fetchone()
                    if has_growth:
                        next_status = {
                            "ACHIEVED": "COMPLETED", "PARTIAL": "COMPLETED",
                            "NOT_ACHIEVED": "DISCARDED",
                        }.get(ritual.learning.outcome.value)
                        if next_status:
                            cursor.execute(
                                """UPDATE growth_hypotheses SET status = ?
                                   WHERE promoted_decision_id = ? AND status = 'ACTIVE'""",
                                (next_status, ritual.learning.target_decision_id),
                            )

                conn.commit()
                return ritual
            except Exception:
                conn.rollback()
                raise

    def _row_to_entity(self, conn: sqlite3.Connection, r_row: sqlite3.Row) -> WeeklyRitualRecord:
        ritual_id = r_row["id"]
        cursor = conn.cursor()

        # Carregar Snapshots
        cursor.execute(
            "SELECT * FROM metric_snapshots WHERE ritual_id = ? ORDER BY metric_key ASC",
            (ritual_id,)
        )
        snapshots = [
            MetricSnapshot(
                definition=MetricDefinition(
                    key=sr["metric_key"],
                    name=sr["metric_name"],
                    unit=sr["unit"],
                    description=sr["description"] or ""
                ),
                calibration=MetricCalibration(
                    metric_key=sr["metric_key"],
                    healthy_min=float(sr["healthy_min"]),
                    healthy_max=float(sr["healthy_max"])
                ),
                observed_value=float(sr["observed_value"]) if sr["observed_value"] is not None else None,
                is_available=bool(sr["is_available"]),
                unavailability_reason=sr["unavailability_reason"]
            )
            for sr in cursor.fetchall()
        ]

        # Carregar Cenário
        try:
            evidences = json.loads(r_row["scenario_evidence_keys"])
        except (ValueError, TypeError):
            evidences = []

        inconc_reason = (
            InconclusiveReason(r_row["scenario_inconclusive_reason"])
            if r_row["scenario_inconclusive_reason"]
            else None
        )

        scenario = Scenario(
            type=ScenarioType(r_row["scenario_type"]),
            description=r_row["scenario_description"],
            recommendation=r_row["scenario_recommendation"],
            evidence_metric_keys=evidences,
            inconclusive_reason=inconc_reason
        )

        # Carregar Decisão
        cursor.execute("SELECT * FROM decisions WHERE ritual_id = ?", (ritual_id,))
        d_row = cursor.fetchone()
        if not d_row:
            raise ValueError(f"Corrupção de integridade: ritual {ritual_id} sem registo de decisão.")

        decision = Decision(
            id=d_row["id"],
            cycle_id=d_row["cycle_id"],
            summary=d_row["summary"],
            hypothesis=d_row["hypothesis"],
            success_criterion=d_row["success_criterion"],
            evaluation_due_date=date.fromisoformat(d_row["evaluation_due_date"]),
            owner=d_row["owner"],
            source_hypothesis_id=d_row["cgs_hypothesis_id"],
            recorded_at=datetime.fromisoformat(d_row["recorded_at"])
        )

        # Carregar Aprendizagem (se houver)
        cursor.execute("SELECT * FROM learnings WHERE ritual_id = ?", (ritual_id,))
        l_row = cursor.fetchone()
        learning = None
        if l_row:
            learning = Learning(
                id=l_row["id"],
                target_decision_id=l_row["target_decision_id"],
                target_decision_summary=l_row["target_decision_summary"],
                outcome=HypothesisOutcome(l_row["outcome"]),
                evidence_notes=l_row["evidence_notes"],
                recorded_at=datetime.fromisoformat(l_row["recorded_at"])
            )

        return WeeklyRitualRecord(
            id=r_row["id"],
            cycle_id=r_row["cycle_id"],
            week_start=date.fromisoformat(r_row["week_start"]),
            snapshots=snapshots,
            scenario=scenario,
            decision=decision,
            learning=learning,
            rules_version=r_row["rules_version"],
            completed_at=datetime.fromisoformat(r_row["completed_at"])
        )

    def get_ritual_by_cycle(self, cycle_id: str) -> Optional[WeeklyRitualRecord]:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM weekly_rituals WHERE cycle_id = ?", (cycle_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_entity(conn, row)

    def get_pending_decision(self, before_week_start: date, evaluation_as_of: date) -> Optional[Decision]:
        """
        Recupera a decisão mais recente anterior a before_week_start sem Learning vinculado
        e cujo prazo (evaluation_due_date) seja menor ou igual a evaluation_as_of.
        """
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT d.* FROM decisions d
                JOIN weekly_rituals r ON d.ritual_id = r.id
                LEFT JOIN learnings l ON d.id = l.target_decision_id
                WHERE r.week_start < ?
                  AND d.evaluation_due_date <= ?
                  AND l.id IS NULL
                ORDER BY r.week_start DESC, d.id DESC
                LIMIT 1
            """, (before_week_start.isoformat(), evaluation_as_of.isoformat()))
            row = cursor.fetchone()
            if not row:
                return None
            return Decision(
                id=row["id"],
                cycle_id=row["cycle_id"],
                summary=row["summary"],
                hypothesis=row["hypothesis"],
                success_criterion=row["success_criterion"],
                evaluation_due_date=date.fromisoformat(row["evaluation_due_date"]),
                owner=row["owner"],
                source_hypothesis_id=row["cgs_hypothesis_id"],
                recorded_at=datetime.fromisoformat(row["recorded_at"])
            )

    def list_rituals(self, limit: int = 20) -> List[WeeklyRitualRecord]:
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM weekly_rituals ORDER BY week_start DESC, id DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            return [self._row_to_entity(conn, r) for r in rows]