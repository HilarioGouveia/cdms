PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metric_calibrations (
    metric_key TEXT PRIMARY KEY,
    healthy_min REAL NOT NULL,
    healthy_max REAL NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS weekly_rituals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_id TEXT NOT NULL UNIQUE,          -- Formato canónico: YYYY-MM-DD
    week_start TEXT NOT NULL,
    scenario_type TEXT NOT NULL,
    scenario_description TEXT NOT NULL,
    scenario_recommendation TEXT NOT NULL,
    scenario_evidence_keys TEXT NOT NULL,   -- JSON array
    scenario_inconclusive_reason TEXT,
    rules_version TEXT NOT NULL,
    completed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ritual_id INTEGER NOT NULL UNIQUE,
    cycle_id TEXT NOT NULL,
    summary TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    success_criterion TEXT NOT NULL,
    evaluation_due_date TEXT NOT NULL,
    owner TEXT NOT NULL DEFAULT 'Creator',
    recorded_at TEXT NOT NULL,
    FOREIGN KEY(ritual_id) REFERENCES weekly_rituals(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS metric_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ritual_id INTEGER NOT NULL,
    metric_key TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    unit TEXT NOT NULL,
    description TEXT,
    healthy_min REAL NOT NULL,
    healthy_max REAL NOT NULL,
    observed_value REAL,
    is_available INTEGER NOT NULL DEFAULT 1,
    unavailability_reason TEXT,
    FOREIGN KEY(ritual_id) REFERENCES weekly_rituals(id) ON DELETE CASCADE,
    UNIQUE(ritual_id, metric_key)
);

CREATE TABLE IF NOT EXISTS learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ritual_id INTEGER NOT NULL UNIQUE,
    target_decision_id INTEGER NOT NULL UNIQUE,
    target_decision_summary TEXT NOT NULL,
    outcome TEXT NOT NULL,                  -- ACHIEVED, PARTIAL, NOT_ACHIEVED, INCONCLUSIVE
    evidence_notes TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    FOREIGN KEY(ritual_id) REFERENCES weekly_rituals(id) ON DELETE CASCADE,
    FOREIGN KEY(target_decision_id) REFERENCES decisions(id)
);

CREATE INDEX IF NOT EXISTS idx_rituals_week_start ON weekly_rituals(week_start DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_cycle_id ON decisions(cycle_id);
CREATE INDEX IF NOT EXISTS idx_decisions_due_date ON decisions(evaluation_due_date);