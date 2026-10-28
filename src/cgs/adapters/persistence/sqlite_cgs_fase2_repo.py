"""Implementação SQLite do repositório da Fase 2 do CGS."""

import sqlite3
from contextlib import contextmanager
from typing import Iterator
from typing import List, Optional
from cgs.application.ports.cgs_fase2_repository import CGSPhase2RepositoryPort
from cgs.domain.entities.budget_allocation import BudgetAllocation, ExperimentRiskTier
from cgs.domain.entities.statistical_validation import BayesianExperimentEvaluation, StatisticalSignificanceVerdict
from decimal import Decimal


class SQLiteCGSPhase2Repository(CGSPhase2RepositoryPort):
    def __init__(self, db_path: str = "data/cdms_dev.db"):
        self.db_path = db_path
        self._init_schema()

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """Finaliza a transação e fecha a conexão mesmo quando a operação falha."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS growth_budget_allocations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hypothesis_id INTEGER NOT NULL UNIQUE,
                    cycle_id TEXT NOT NULL,
                    allocated_amount_cents INTEGER NOT NULL,
                    spent_amount_cents INTEGER NOT NULL DEFAULT 0,
                    risk_tier TEXT NOT NULL DEFAULT 'LOW',
                    max_cpa_target_cents INTEGER,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS growth_statistical_evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hypothesis_id INTEGER NOT NULL UNIQUE,
                    control_conversions INTEGER NOT NULL,
                    control_sample INTEGER NOT NULL,
                    treatment_conversions INTEGER NOT NULL,
                    treatment_sample INTEGER NOT NULL,
                    probability_to_beat_control TEXT NOT NULL,
                    lift_pct TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    sample_adequacy_ratio TEXT NOT NULL,
                    evaluated_at TEXT NOT NULL
                );
                """
            )

    def save_budget_allocation(self, allocation: BudgetAllocation) -> BudgetAllocation:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO growth_budget_allocations (
                    hypothesis_id, cycle_id, allocated_amount_cents, spent_amount_cents, risk_tier, max_cpa_target_cents, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(hypothesis_id) DO UPDATE SET
                    allocated_amount_cents = excluded.allocated_amount_cents,
                    spent_amount_cents = excluded.spent_amount_cents,
                    risk_tier = excluded.risk_tier,
                    max_cpa_target_cents = excluded.max_cpa_target_cents;
                """,
                (
                    allocation.hypothesis_id,
                    allocation.cycle_id,
                    allocation.allocated_amount_cents,
                    allocation.spent_amount_cents,
                    allocation.risk_tier.value,
                    allocation.max_cpa_target_cents,
                    allocation.created_at.isoformat(),
                ),
            )
            conn.commit()
            return allocation

    def get_budget_by_hypothesis(self, hypothesis_id: int) -> Optional[BudgetAllocation]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM growth_budget_allocations WHERE hypothesis_id = ?;", (hypothesis_id,)
            ).fetchone()
            if not row:
                return None
            return BudgetAllocation(
                hypothesis_id=row["hypothesis_id"],
                cycle_id=row["cycle_id"],
                allocated_amount_cents=row["allocated_amount_cents"],
                spent_amount_cents=row["spent_amount_cents"],
                risk_tier=ExperimentRiskTier(row["risk_tier"]),
                max_cpa_target_cents=row["max_cpa_target_cents"],
            )

    def list_budgets_by_cycle(self, cycle_id: str) -> List[BudgetAllocation]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM growth_budget_allocations WHERE cycle_id = ?;", (cycle_id,)
            ).fetchall()
            return [
                BudgetAllocation(
                    hypothesis_id=r["hypothesis_id"],
                    cycle_id=r["cycle_id"],
                    allocated_amount_cents=r["allocated_amount_cents"],
                    spent_amount_cents=r["spent_amount_cents"],
                    risk_tier=ExperimentRiskTier(r["risk_tier"]),
                    max_cpa_target_cents=r["max_cpa_target_cents"],
                )
                for r in rows
            ]

    def save_statistical_evaluation(self, evaluation: BayesianExperimentEvaluation) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO growth_statistical_evaluations (
                    hypothesis_id, control_conversions, control_sample, treatment_conversions, treatment_sample,
                    probability_to_beat_control, lift_pct, verdict, sample_adequacy_ratio, evaluated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(hypothesis_id) DO UPDATE SET
                    probability_to_beat_control = excluded.probability_to_beat_control,
                    lift_pct = excluded.lift_pct,
                    verdict = excluded.verdict,
                    sample_adequacy_ratio = excluded.sample_adequacy_ratio;
                """,
                (
                    evaluation.hypothesis_id,
                    evaluation.control_conversions,
                    evaluation.control_sample,
                    evaluation.treatment_conversions,
                    evaluation.treatment_sample,
                    str(evaluation.probability_to_beat_control),
                    str(evaluation.lift_pct),
                    evaluation.verdict.value,
                    str(evaluation.sample_adequacy_ratio),
                    evaluation.evaluated_at.isoformat(),
                ),
            )
            conn.commit()

    def get_evaluation_by_hypothesis(self, hypothesis_id: int) -> Optional[BayesianExperimentEvaluation]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM growth_statistical_evaluations WHERE hypothesis_id = ?;", (hypothesis_id,)
            ).fetchone()
            if not row:
                return None
            return BayesianExperimentEvaluation(
                hypothesis_id=row["hypothesis_id"],
                control_conversions=row["control_conversions"],
                control_sample=row["control_sample"],
                treatment_conversions=row["treatment_conversions"],
                treatment_sample=row["treatment_sample"],
                probability_to_beat_control=Decimal(row["probability_to_beat_control"]),
                lift_pct=Decimal(row["lift_pct"]),
                verdict=StatisticalSignificanceVerdict(row["verdict"]),
                sample_adequacy_ratio=Decimal(row["sample_adequacy_ratio"]),
            )