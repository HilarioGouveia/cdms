-- Migração 005: Conectores de APIs, Tarefas Assíncronas e Health Index (Fase 3 CDMS)
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS platform_connections (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    account_id TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    encrypted_credentials TEXT,
    last_synced_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS creator_health_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    reach_score TEXT NOT NULL,
    retention_score TEXT NOT NULL,
    ctr_score TEXT NOT NULL,
    conversion_score TEXT NOT NULL,
    composite_score TEXT NOT NULL,
    tier TEXT NOT NULL,
    calculated_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ai_hypothesis_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    action_description TEXT NOT NULL,
    tested_variable TEXT NOT NULL,
    target_metric_key TEXT NOT NULL,
    suggested_target TEXT NOT NULL,
    invalidation_floor TEXT NOT NULL,
    rational_explanation TEXT NOT NULL,
    ice_score TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'SUGGESTED',
    created_at TEXT NOT NULL,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_health_workspace_cycle ON creator_health_history(workspace_id, cycle_id);
CREATE INDEX IF NOT EXISTS idx_connections_workspace ON platform_connections(workspace_id);