-- Migração 007: Multi-Armed Bandits e Disjuntores de Proteção Operacional (Fase 3 CGS)
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS growth_bandit_allocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hypothesis_id INTEGER NOT NULL,
    cycle_id TEXT NOT NULL,
    strategy TEXT NOT NULL,
    weights_json TEXT NOT NULL,
    leading_arm_id TEXT NOT NULL,
    is_converged INTEGER NOT NULL DEFAULT 0,
    calculated_at TEXT NOT NULL,
    FOREIGN KEY (hypothesis_id) REFERENCES growth_hypotheses(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS growth_circuit_breaker_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hypothesis_id INTEGER NOT NULL,
    cycle_id TEXT NOT NULL,
    is_tripped INTEGER NOT NULL DEFAULT 1,
    trigger_reason TEXT NOT NULL,
    observed_metric_value TEXT,
    threshold_limit_value TEXT,
    tripped_at TEXT NOT NULL,
    FOREIGN KEY (hypothesis_id) REFERENCES growth_hypotheses(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_bandit_hypo ON growth_bandit_allocations(hypothesis_id, cycle_id);
CREATE INDEX IF NOT EXISTS idx_breaker_hypo ON growth_circuit_breaker_events(hypothesis_id);