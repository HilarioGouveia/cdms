import sqlite3
import json
from pathlib import Path
from datetime import datetime, date, timezone
from typing import List, Optional

from cdms.application.ports.repository import RepositoryPort
from cdms.domain.entities.metric import MetricDefinition, MetricCalibration, MetricSnapshot
from cdms.domain.entities.scenario import Scenario, ScenarioType, InconclusiveReason
from cdms.domain.entities.decision import Decision
from cdms.domain.entities.learning import Learning, HypothesisOutcome
from cdms.domain.entities.weekly_ritual import WeeklyRitualRecord

class SQLiteRepository(RepositoryPort):
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def save_ritual_atomic(self, ritual: WeeklyRitualRecord) -> WeeklyRitualRecord:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
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

            cursor.execute("""
                INSERT INTO decisions (
                    ritual_id, cycle_id, summary, hypothesis, success_criterion,
                    evaluation_due_date, owner, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ritual_id,
                ritual.decision.cycle_id,
                ritual.decision.summary,
                ritual.decision.hypothesis,
                ritual.decision.success_criterion,
                ritual.decision.evaluation_due_date.isoformat(),
                ritual.decision.owner,
                ritual.decision.recorded_at.isoformat()
            ))
            ritual.decision.id = cursor.lastrowid

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

            conn.commit()
            return ritual
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_pending_decision(self, before_week_start: date, evaluation_as_of: date) -> Optional[Decision]:
        with self._get_connection() as conn:
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
                recorded_at=datetime.fromisoformat(row["recorded_at"])
            )
    # ... outros métodos get_ritual_by_cycle, list_rituals e calibrações