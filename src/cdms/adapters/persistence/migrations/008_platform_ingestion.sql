-- Armazenamento local ao workspace; a identidade permanece no banco central.
CREATE TABLE IF NOT EXISTS ingestion_connections (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    account_id TEXT NOT NULL,
    encrypted_credentials TEXT NOT NULL,
    created_by TEXT NOT NULL,
    automatic_sync INTEGER NOT NULL DEFAULT 0,
    api_version TEXT NOT NULL,
    conversion_action_type TEXT NOT NULL,
    timezone_name TEXT NOT NULL,
    currency TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_synced_at TEXT,
    UNIQUE(platform, account_id)
);
CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id TEXT PRIMARY KEY,
    connection_id TEXT NOT NULL REFERENCES ingestion_connections(id),
    connection_revision INTEGER NOT NULL,
    cycle_id TEXT NOT NULL,
    generation INTEGER NOT NULL DEFAULT 1,
    requested_by TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PENDING','RUNNING','SUCCESS','FAILED')),
    attempts INTEGER NOT NULL DEFAULT 0,
    run_token TEXT,
    lease_until TEXT,
    error_code TEXT,
    created_at TEXT NOT NULL,
    finished_at TEXT,
    UNIQUE(connection_id, connection_revision, cycle_id, generation)
);
CREATE TABLE IF NOT EXISTS ingestion_batches (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL UNIQUE REFERENCES ingestion_jobs(id),
    payload_json TEXT NOT NULL,
    ingested_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ingestion_dispatch ON ingestion_jobs(status, lease_until);
