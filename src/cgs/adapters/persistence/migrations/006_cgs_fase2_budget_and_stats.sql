-- Migração 006: Governança Orçamentária e Validação Estatística Bayesiana (Fase 2 CGS)
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS growth_budget_allocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hypothesis_id INTEGER NOT NULL UNIQUE,
    cycle_id TEXT NOT NULL,
    allocated_amount_cents INTEGER NOT NULL,
    spent_amount_cents INTEGER NOT NULL DEFAULT 0,
    risk_tier TEXT NOT NULL DEFAULT 'LOW',
    max_cpa_target_cents INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (hypothesis_id) REFERENCES growth_hypotheses(id) ON DELETE CASCADE
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
    evaluated_at TEXT NOT NULL,
    FOREIGN KEY (hypothesis_id) REFERENCES growth_hypotheses(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_budget_cycle ON growth_budget_allocations(cycle_id);