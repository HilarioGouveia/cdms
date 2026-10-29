"""Conexões cifradas, outbox durável e ingestões imutáveis no banco do workspace."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

MAX_ATTEMPTS = 3
LEASE_SECONDS = 300


def now_utc():
    return datetime.now(timezone.utc)


class SQLiteIngestionRepository:
    def __init__(self, db_path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.executescript((Path(__file__).parent / "migrations" / "008_platform_ingestion.sql").read_text(encoding="utf-8"))

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            with conn:
                yield conn
        finally:
            conn.close()

    def get_connection(self, connection_id):
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM ingestion_connections WHERE id = ?", (connection_id,)).fetchone()
            return dict(row) if row else None

    def save_connection(self, *, account_id, encrypted_credentials, api_version, conversion_action_type, timezone_name, currency, created_by, automatic_sync=False):
        connection_id = str(uuid4())
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT id FROM ingestion_connections WHERE platform = 'META_ADS' AND account_id = ?", (account_id,)).fetchone()
            if existing:
                connection_id = existing["id"]
                conn.execute("""UPDATE ingestion_connections SET encrypted_credentials = ?, api_version = ?,
                    conversion_action_type = ?, timezone_name = ?, currency = ?, created_by = ?, automatic_sync = ?, is_active = 1, revision = revision + 1
                    WHERE id = ?""", (encrypted_credentials, api_version, conversion_action_type, timezone_name, currency, created_by, int(automatic_sync), connection_id))
            else:
                conn.execute("""INSERT INTO ingestion_connections
                    (id,platform,account_id,encrypted_credentials,api_version,conversion_action_type,timezone_name,currency,created_by,automatic_sync,created_at)
                    VALUES (?,'META_ADS',?,?,?,?,?,?,?,?,?)""",
                    (connection_id, account_id, encrypted_credentials, api_version, conversion_action_type, timezone_name, currency, created_by, int(automatic_sync), now_utc().isoformat()))
        return self.get_connection(connection_id)

    def list_connections(self):
        with self.connection() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM ingestion_connections ORDER BY created_at")]

    def deactivate(self, connection_id):
        with self.connection() as conn:
            result = conn.execute("UPDATE ingestion_connections SET is_active = 0, revision = revision + 1 WHERE id = ?", (connection_id,))
            return result.rowcount == 1

    def enqueue(self, connection_id, cycle_id, user_id, *, retry_failed=False, force_refresh=False):
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            connection = conn.execute("SELECT * FROM ingestion_connections WHERE id = ? AND is_active = 1", (connection_id,)).fetchone()
            if connection is None:
                raise ValueError("Conexão inativa ou inexistente neste workspace.")
            row = conn.execute("SELECT * FROM ingestion_jobs WHERE connection_id = ? AND connection_revision = ? AND cycle_id = ? ORDER BY generation DESC LIMIT 1",
                               (connection_id, connection["revision"], cycle_id)).fetchone()
            generation = row["generation"] if row else 1
            if row and force_refresh and row["status"] in ('SUCCESS', 'FAILED'):
                generation += 1
                row = None
            if row:
                if retry_failed and row["status"] == "FAILED":
                    conn.execute("""UPDATE ingestion_jobs SET status = 'PENDING', attempts = 0, error_code = NULL,
                        finished_at = NULL, requested_by = ? WHERE id = ?""", (user_id, row["id"]))
                    job_id, changed = row["id"], True
                else:
                    return dict(row), False
            else:
                job_id, changed = str(uuid4()), True
                conn.execute("""INSERT INTO ingestion_jobs
                    (id,connection_id,connection_revision,cycle_id,generation,requested_by,status,created_at)
                    VALUES (?,?,?,?,?,?,'PENDING',?)""",
                    (job_id, connection_id, connection["revision"], cycle_id, generation, user_id, now_utc().isoformat()))
        return self.get_job(job_id), changed

    def get_job(self, job_id):
        with self.connection() as conn:
            row = conn.execute("SELECT * FROM ingestion_jobs WHERE id = ?", (job_id,)).fetchone()
            return dict(row) if row else None

    def list_jobs(self):
        with self.connection() as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM ingestion_jobs ORDER BY created_at DESC LIMIT 100")]

    def claim(self, job_id, *, now=None):
        now = now or now_utc()
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM ingestion_jobs WHERE id = ?", (job_id,)).fetchone()
            if not row or row["status"] in ('SUCCESS', 'FAILED'):
                return None
            if row["status"] == 'RUNNING' and row["lease_until"] > now.isoformat():
                return None
            if row["attempts"] >= MAX_ATTEMPTS:
                conn.execute("UPDATE ingestion_jobs SET status = 'FAILED', error_code = 'RETRY_EXHAUSTED', finished_at = ? WHERE id = ?",
                             (now.isoformat(), job_id))
                return None
            token = str(uuid4())
            conn.execute("""UPDATE ingestion_jobs SET status = 'RUNNING', attempts = attempts + 1,
                run_token = ?, lease_until = ?, error_code = NULL WHERE id = ?""",
                (token, (now + timedelta(seconds=LEASE_SECONDS)).isoformat(), job_id))
        return self.get_job(job_id)

    def fail(self, job, code, *, retryable=False):
        status = 'PENDING' if retryable and job["attempts"] < MAX_ATTEMPTS else 'FAILED'
        with self.connection() as conn:
            conn.execute("""UPDATE ingestion_jobs SET status = ?, error_code = ?, lease_until = NULL,
                run_token = NULL, finished_at = ? WHERE id = ? AND status = 'RUNNING' AND run_token = ?""",
                (status, code, now_utc().isoformat() if status == 'FAILED' else None, job["id"], job["run_token"]))
        return self.get_job(job["id"])

    def finish(self, job, payload):
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute("SELECT * FROM ingestion_jobs WHERE id = ?", (job["id"],)).fetchone()
            if current["status"] != 'RUNNING' or current["run_token"] != job["run_token"]:
                return False
            active = conn.execute("SELECT 1 FROM ingestion_connections WHERE id = ? AND is_active = 1 AND revision = ?",
                                  (job["connection_id"], job["connection_revision"])).fetchone()
            if not active:
                raise ValueError("CONNECTION_CHANGED")
            now = now_utc().isoformat()
            conn.execute("INSERT INTO ingestion_batches (id,job_id,payload_json,ingested_at) VALUES (?,?,?,?)",
                         (str(uuid4()), job["id"], json.dumps(payload, allow_nan=False), now))
            conn.execute("UPDATE ingestion_jobs SET status = 'SUCCESS', run_token = NULL, lease_until = NULL, finished_at = ? WHERE id = ?",
                         (now, job["id"]))
            conn.execute("UPDATE ingestion_connections SET last_synced_at = ? WHERE id = ?", (now, job["connection_id"]))
        return True

    def get_batch(self, job_id):
        with self.connection() as conn:
            row = conn.execute("SELECT payload_json FROM ingestion_batches WHERE job_id = ?", (job_id,)).fetchone()
            return json.loads(row["payload_json"]) if row else None

    def dispatchable_jobs(self, *, limit=25):
        with self.connection() as conn:
            return [row["id"] for row in conn.execute("""SELECT id FROM ingestion_jobs
                WHERE status = 'PENDING' OR (status = 'RUNNING' AND lease_until <= ?)
                ORDER BY created_at LIMIT ?""", (now_utc().isoformat(), limit))]
