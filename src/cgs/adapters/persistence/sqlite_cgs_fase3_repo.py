"""Implementação do repositório SQLite para a Fase 3 do CGS."""

import json
import sqlite3
from typing import Optional
from cgs.application.ports.cgs_fase3_repository import CGSPhase3RepositoryPort
from cgs.domain.entities.bandit_policy import (
    AutoRollbackTrigger,
    BanditOptimizationResult,
    CircuitBreakerStatus,
    ExplorationStrategy,
)
from decimal import Decimal


class SQLiteCGSPhase3Repository(CGSPhase3RepositoryPort):
    def __init__(self, db_path: str = "data/cdms_dev.db"):
        self.db_path = db_path
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _init_schema(self) -> None:
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS growth_bandit_allocations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hypothesis_id INTEGER NOT NULL,
                    cycle_id TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    weights_json TEXT NOT NULL,
                    leading_arm_id TEXT NOT NULL,
                    is_converged INTEGER NOT NULL DEFAULT 0,
                    calculated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS growth_circuit_breaker_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hypothesis_id INTEGER NOT NULL,
                    cycle_id TEXT NOT NULL,
                    is_tripped INTEGER NOT NULL DEFAULT 1,
                    trigger_reason TEXT NOT NULL,
                    observed_metric_value TEXT,
                    threshold_limit_value TEXT,
                    tripped_at TEXT NOT NULL
                );
                """
            )

    def save_bandit_decision(self, result: BanditOptimizationResult) -> None:
        serialized_weights = {k: str(v) for k, v in result.arm_weights.items()}
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO growth_bandit_allocations (
                    hypothesis_id, cycle_id, strategy, weights_json, leading_arm_id, is_converged, calculated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    result.hypothesis_id,
                    result.cycle_id,
                    result.strategy.value,
                    json.dumps(serialized_weights),
                    result.leading_arm_id,
                    1 if result.is_converged else 0,
                    result.calculated_at.isoformat(),
                ),
            )
            conn.commit()

    def get_latest_bandit_decision(self, hypothesis_id: int) -> Optional[BanditOptimizationResult]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM growth_bandit_allocations WHERE hypothesis_id = ? ORDER BY id DESC LIMIT 1;",
                (hypothesis_id,),
            ).fetchone()
            if not row:
                return None
            weights_raw = json.loads(row["weights_json"])
            weights = {k: Decimal(v) for k, v in weights_raw.items()}
            return BanditOptimizationResult(
                hypothesis_id=row["hypothesis_id"],
                cycle_id=row["cycle_id"],
                strategy=ExplorationStrategy(row["strategy"]),
                arm_weights=weights,
                leading_arm_id=row["leading_arm_id"],
                is_converged=bool(row["is_converged"]),
            )

    def record_circuit_breaker_event(self, status: CircuitBreakerStatus) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO growth_circuit_breaker_events (
                    hypothesis_id, cycle_id, is_tripped, trigger_reason, observed_metric_value, threshold_limit_value, tripped_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    status.hypothesis_id,
                    status.cycle_id,
                    1 if status.is_tripped else 0,
                    status.trigger_reason.value if status.trigger_reason else "UNKNOWN",
                    str(status.observed_metric_value) if status.observed_metric_value else None,
                    str(status.threshold_limit_value) if status.threshold_limit_value else None,
                    status.tripped_at.isoformat() if status.tripped_at else None,
                ),
            )
            conn.commit()

    def get_active_circuit_breaker(self, hypothesis_id: int) -> Optional[CircuitBreakerStatus]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM growth_circuit_breaker_events WHERE hypothesis_id = ? AND is_tripped = 1 ORDER BY id DESC LIMIT 1;",
                (hypothesis_id,),
            ).fetchone()
            if not row:
                return None
            return CircuitBreakerStatus(
                hypothesis_id=row["hypothesis_id"],
                cycle_id=row["cycle_id"],
                is_tripped=bool(row["is_tripped"]),
                trigger_reason=AutoRollbackTrigger(row["trigger_reason"]),
                observed_metric_value=Decimal(row["observed_metric_value"]) if row["observed_metric_value"] else None,
                threshold_limit_value=Decimal(row["threshold_limit_value"]) if row["threshold_limit_value"] else None,
            )