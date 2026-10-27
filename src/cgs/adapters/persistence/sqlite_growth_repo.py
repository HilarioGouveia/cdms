"""Implementação do repositório SQLite para o Creator Growth System (CGS)."""

import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from cgs.application.ports.growth_repository import GrowthRepositoryPort
from cgs.domain.entities.funnel import (
    ConversionType,
    FunnelBaseline,
    FunnelOpportunityAudit,
    FunnelStage,
)
from cgs.domain.entities.hypothesis import (
    GrowthHypothesis,
    HypothesisStatus,
    MetricDirection,
    VariableType,
)


class SQLiteGrowthRepository(GrowthRepositoryPort):
    """Adaptador de persistência SQLite com armazenamento exato em Decimal e isolamento transacional."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        """Aplica as migrações necessárias para assegurar a existência das tabelas CGS."""
        with self._get_connection() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT);"
            )
            cursor = conn.execute("SELECT version FROM schema_version WHERE version = 2;")
            if not cursor.fetchone():
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS growth_baselines (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ticket_price TEXT NOT NULL,
                        expected_ctr_pct TEXT NOT NULL,
                        expected_conversion_rate_pct TEXT NOT NULL,
                        conversion_type TEXT NOT NULL DEFAULT 'DIRECT_SALE',
                        lead_to_sale_rate_pct TEXT,
                        is_active INTEGER NOT NULL DEFAULT 1,
                        created_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS funnel_opportunity_audits (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_cycle_id TEXT NOT NULL,
                        primary_bottleneck TEXT NOT NULL,
                        intention_opportunity_reais TEXT NOT NULL,
                        conversion_opportunity_reais TEXT NOT NULL,
                        total_opportunity_reais TEXT NOT NULL,
                        diagnosis_summary TEXT NOT NULL,
                        calculation_version TEXT NOT NULL,
                        calculated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS growth_hypotheses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_cycle_id TEXT,
                        target_cycle_id TEXT,
                        promoted_decision_id INTEGER,
                        action_description TEXT NOT NULL,
                        tested_variable TEXT NOT NULL,
                        target_metric_key TEXT NOT NULL,
                        target_metric_unit TEXT NOT NULL,
                        metric_direction TEXT NOT NULL,
                        baseline_reference_value TEXT NOT NULL,
                        success_metric_target TEXT NOT NULL,
                        invalidation_floor TEXT NOT NULL,
                        expected_impact_description TEXT NOT NULL,
                        impact_score INTEGER NOT NULL,
                        confidence_score INTEGER NOT NULL,
                        ease_score INTEGER NOT NULL,
                        ice_score TEXT NOT NULL,
                        sample_exposure_minimum INTEGER NOT NULL DEFAULT 100,
                        window_days INTEGER NOT NULL DEFAULT 7,
                        status TEXT NOT NULL DEFAULT 'BACKLOG',
                        created_at TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_cgs_hypotheses_ranking ON growth_hypotheses(status, ice_score DESC, created_at ASC);
                    CREATE INDEX IF NOT EXISTS idx_cgs_audits_source_cycle ON funnel_opportunity_audits(source_cycle_id);
                    CREATE INDEX IF NOT EXISTS idx_cgs_baselines_active ON growth_baselines(is_active);
                    """
                )
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (2, ?);",
                    (datetime.now(timezone.utc).isoformat(),),
                )
                conn.commit()

    def save_baseline(self, baseline: FunnelBaseline) -> FunnelBaseline:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE growth_baselines SET is_active = 0 WHERE is_active = 1;")
            cursor.execute(
                """
                INSERT INTO growth_baselines (
                    ticket_price, expected_ctr_pct, expected_conversion_rate_pct,
                    conversion_type, lead_to_sale_rate_pct, is_active, created_at
                ) VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    str(baseline.ticket_price),
                    str(baseline.expected_ctr_pct),
                    str(baseline.expected_conversion_rate_pct),
                    baseline.conversion_type.value,
                    str(baseline.lead_to_sale_rate_pct) if baseline.lead_to_sale_rate_pct is not None else None,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
            return baseline

    def get_active_baseline(self) -> Optional[FunnelBaseline]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT ticket_price, expected_ctr_pct, expected_conversion_rate_pct,
                       conversion_type, lead_to_sale_rate_pct
                FROM growth_baselines
                WHERE is_active = 1
                ORDER BY id DESC LIMIT 1
                """
            )
            row = cursor.fetchone()
            if not row:
                return None
            return FunnelBaseline(
                ticket_price=Decimal(row["ticket_price"]),
                expected_ctr_pct=Decimal(row["expected_ctr_pct"]),
                expected_conversion_rate_pct=Decimal(row["expected_conversion_rate_pct"]),
                conversion_type=ConversionType(row["conversion_type"]),
                lead_to_sale_rate_pct=Decimal(row["lead_to_sale_rate_pct"]) if row["lead_to_sale_rate_pct"] else None,
            )

    def save_funnel_audit(self, audit: FunnelOpportunityAudit) -> FunnelOpportunityAudit:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO funnel_opportunity_audits (
                    source_cycle_id, primary_bottleneck, intention_opportunity_reais,
                    conversion_opportunity_reais, total_opportunity_reais,
                    diagnosis_summary, calculation_version, calculated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit.source_cycle_id,
                    audit.primary_bottleneck.value,
                    str(audit.intention_opportunity_reais),
                    str(audit.conversion_opportunity_reais),
                    str(audit.total_opportunity_reais),
                    audit.diagnosis_summary,
                    audit.calculation_version,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
            return audit

    def get_funnel_audit(self, source_cycle_id: str) -> Optional[FunnelOpportunityAudit]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT source_cycle_id, primary_bottleneck, intention_opportunity_reais,
                       conversion_opportunity_reais, total_opportunity_reais,
                       diagnosis_summary, calculation_version
                FROM funnel_opportunity_audits
                WHERE source_cycle_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (source_cycle_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return FunnelOpportunityAudit(
                source_cycle_id=row["source_cycle_id"],
                primary_bottleneck=FunnelStage(row["primary_bottleneck"]),
                intention_opportunity_reais=Decimal(row["intention_opportunity_reais"]),
                conversion_opportunity_reais=Decimal(row["conversion_opportunity_reais"]),
                total_opportunity_reais=Decimal(row["total_opportunity_reais"]),
                diagnosis_summary=row["diagnosis_summary"],
                calculation_version=row["calculation_version"],
            )

    def save_hypothesis(self, hypothesis: GrowthHypothesis) -> GrowthHypothesis:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now_iso = datetime.now(timezone.utc).isoformat()
            if hypothesis.id is None:
                cursor.execute(
                    """
                    INSERT INTO growth_hypotheses (
                        source_cycle_id, target_cycle_id, promoted_decision_id,
                        action_description, tested_variable, target_metric_key,
                        target_metric_unit, metric_direction, baseline_reference_value,
                        success_metric_target, invalidation_floor, expected_impact_description,
                        impact_score, confidence_score, ease_score, ice_score,
                        sample_exposure_minimum, window_days, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        hypothesis.source_cycle_id,
                        hypothesis.target_cycle_id,
                        hypothesis.promoted_decision_id,
                        hypothesis.action_description,
                        hypothesis.tested_variable.value,
                        hypothesis.target_metric_key,
                        hypothesis.target_metric_unit,
                        hypothesis.metric_direction.value,
                        str(hypothesis.baseline_reference_value),
                        str(hypothesis.success_metric_target),
                        str(hypothesis.invalidation_floor),
                        hypothesis.expected_impact_description,
                        hypothesis.impact_score,
                        hypothesis.confidence_score,
                        hypothesis.ease_score,
                        str(hypothesis.ice_score),
                        hypothesis.sample_exposure_minimum,
                        hypothesis.window_days,
                        hypothesis.status.value,
                        now_iso,
                    ),
                )
                hypothesis.id = cursor.lastrowid
            else:
                cursor.execute(
                    """
                    UPDATE growth_hypotheses SET
                        source_cycle_id = ?, target_cycle_id = ?, promoted_decision_id = ?,
                        action_description = ?, tested_variable = ?, target_metric_key = ?,
                        target_metric_unit = ?, metric_direction = ?, baseline_reference_value = ?,
                        success_metric_target = ?, invalidation_floor = ?, expected_impact_description = ?,
                        impact_score = ?, confidence_score = ?, ease_score = ?, ice_score = ?,
                        sample_exposure_minimum = ?, window_days = ?, status = ?
                    WHERE id = ?
                    """,
                    (
                        hypothesis.source_cycle_id,
                        hypothesis.target_cycle_id,
                        hypothesis.promoted_decision_id,
                        hypothesis.action_description,
                        hypothesis.tested_variable.value,
                        hypothesis.target_metric_key,
                        hypothesis.target_metric_unit,
                        hypothesis.metric_direction.value,
                        str(hypothesis.baseline_reference_value),
                        str(hypothesis.success_metric_target),
                        str(hypothesis.invalidation_floor),
                        hypothesis.expected_impact_description,
                        hypothesis.impact_score,
                        hypothesis.confidence_score,
                        hypothesis.ease_score,
                        str(hypothesis.ice_score),
                        hypothesis.sample_exposure_minimum,
                        hypothesis.window_days,
                        hypothesis.status.value,
                        hypothesis.id,
                    ),
                )
            conn.commit()
            return hypothesis

    def get_hypothesis_by_id(self, hypothesis_id: int) -> Optional[GrowthHypothesis]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM growth_hypotheses WHERE id = ?", (hypothesis_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_hypothesis(row)

    def list_hypotheses(
        self,
        status: Optional[HypothesisStatus] = None,
        limit: int = 50,
    ) -> List[GrowthHypothesis]:
        with self._get_connection() as conn:
            if status:
                query = "SELECT * FROM growth_hypotheses WHERE status = ? ORDER BY CAST(ice_score AS REAL) DESC, created_at ASC, id ASC LIMIT ?"
                params = (status.value, limit)
            else:
                query = "SELECT * FROM growth_hypotheses ORDER BY CAST(ice_score AS REAL) DESC, created_at ASC, id ASC LIMIT ?"
                params = (limit,)
            cursor = conn.execute(query, params)
            return [self._row_to_hypothesis(row) for row in cursor.fetchall()]

    def update_hypothesis_status(
        self,
        hypothesis_id: int,
        status: HypothesisStatus,
        target_cycle_id: Optional[str] = None,
        promoted_decision_id: Optional[int] = None,
    ) -> GrowthHypothesis:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            updates = ["status = ?"]
            params = [status.value]
            if target_cycle_id is not None:
                updates.append("target_cycle_id = ?")
                params.append(target_cycle_id)
            if promoted_decision_id is not None:
                updates.append("promoted_decision_id = ?")
                params.append(promoted_decision_id)
            params.append(hypothesis_id)

            cursor.execute(
                f"UPDATE growth_hypotheses SET {', '.join(updates)} WHERE id = ?",
                tuple(params),
            )
            conn.commit()

        hypo = self.get_hypothesis_by_id(hypothesis_id)
        if not hypo:
            raise ValueError(f"Hipótese {hypothesis_id} não encontrada após atualização.")
        return hypo

    def _row_to_hypothesis(self, row: sqlite3.Row) -> GrowthHypothesis:
        return GrowthHypothesis(
            id=row["id"],
            source_cycle_id=row["source_cycle_id"],
            target_cycle_id=row["target_cycle_id"],
            promoted_decision_id=row["promoted_decision_id"],
            action_description=row["action_description"],
            tested_variable=VariableType(row["tested_variable"]),
            target_metric_key=row["target_metric_key"],
            target_metric_unit=row["target_metric_unit"],
            metric_direction=MetricDirection(row["metric_direction"]),
            baseline_reference_value=Decimal(row["baseline_reference_value"]),
            success_metric_target=Decimal(row["success_metric_target"]),
            invalidation_floor=Decimal(row["invalidation_floor"]),
            expected_impact_description=row["expected_impact_description"],
            impact_score=row["impact_score"],
            confidence_score=row["confidence_score"],
            ease_score=row["ease_score"],
            sample_exposure_minimum=row["sample_exposure_minimum"],
            window_days=row["window_days"],
            status=HypothesisStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )