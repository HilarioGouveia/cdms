-- Migração 002: Esquema Relacional do Creator Growth System (CGS)
PRAGMA foreign_keys = ON;

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
    calculated_at TEXT NOT NULL,
    FOREIGN KEY (source_cycle_id) REFERENCES rituals(cycle_id) ON DELETE CASCADE
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
    created_at TEXT NOT NULL,
    FOREIGN KEY (source_cycle_id) REFERENCES rituals(cycle_id) ON DELETE SET NULL,
    FOREIGN KEY (target_cycle_id) REFERENCES rituals(cycle_id) ON DELETE SET NULL,
    FOREIGN KEY (promoted_decision_id) REFERENCES decisions(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_cgs_hypotheses_ranking ON growth_hypotheses(status, ice_score DESC, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_cgs_audits_source_cycle ON funnel_opportunity_audits(source_cycle_id);
CREATE INDEX IF NOT EXISTS idx_cgs_baselines_active ON growth_baselines(is_active);