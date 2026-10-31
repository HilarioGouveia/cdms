"""Identidade central; dados operacionais ficam em bancos distintos por workspace."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4

from cdms.domain.entities.tenant import TenantContext, UserRole


class SQLiteIdentityRepository:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        migration = Path(__file__).parent / "migrations" / "004_multitenant_schema.sql"
        with self.connection() as conn:
            conn.executescript(migration.read_text(encoding="utf-8"))
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
            if "token_version" not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0")
            if "must_change_password" not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")
            if "theme_preference" not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN theme_preference TEXT NOT NULL DEFAULT 'dark-premium'")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_normalized ON users(lower(email))")

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            with conn:
                yield conn
        finally:
            conn.close()

    def create_user(self, email: str, hashed_password: str, full_name: str):
        user_id = str(uuid4())
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO users (id,email,hashed_password,full_name,created_at) VALUES (?,?,?,?,?)",
                (user_id, email.strip().casefold(), hashed_password, full_name,
                 datetime.now(timezone.utc).isoformat()),
            )
        return self.get_user(user_id)

    def get_user(self, user_id: str):
        with self.connection() as conn:
            return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    def set_theme_preference(self, user_id, profile):
        if profile not in {'dark-premium', 'soft-light'}:
            raise ValueError('Tema inválido.')
        with self.connection() as conn:
            conn.execute('UPDATE users SET theme_preference = ? WHERE id = ?', (profile, user_id))

    def get_user_by_email(self, email: str):
        with self.connection() as conn:
            return conn.execute("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email.strip().casefold(),)).fetchone()

    def create_workspace(self, name: str, slug: str, owner_id: str):
        workspace_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            conn.execute("INSERT INTO workspaces (id,name,slug,owner_id,created_at) VALUES (?,?,?,?,?)",
                         (workspace_id, name, slug, owner_id, now))
            conn.execute("INSERT INTO workspace_members (workspace_id,user_id,role,joined_at) VALUES (?,?,?,?)",
                         (workspace_id, owner_id, UserRole.OWNER.value, now))
        return workspace_id

    def get_tenant(self, user_id: str, workspace_id: str):
        with self.connection() as conn:
            row = conn.execute(
                """SELECT m.role FROM workspace_members m JOIN users u ON u.id = m.user_id
                   JOIN workspaces w ON w.id = m.workspace_id
                   WHERE m.user_id = ? AND m.workspace_id = ? AND u.is_active = 1""",
                (user_id, workspace_id),
            ).fetchone()
        return TenantContext(workspace_id, user_id, UserRole(row["role"])) if row else None

    def list_workspaces(self, user_id: str):
        with self.connection() as conn:
            return [dict(row) for row in conn.execute(
                """SELECT w.id,w.name,w.slug,w.owner_id,m.role FROM workspaces w
                   JOIN workspace_members m ON m.workspace_id = w.id WHERE m.user_id = ? ORDER BY w.name""",
                (user_id,),
            )]

    def list_members(self, workspace_id: str):
        with self.connection() as conn:
            return [dict(row) for row in conn.execute(
                """SELECT u.id,u.email,u.full_name,m.role FROM workspace_members m
                   JOIN users u ON u.id = m.user_id WHERE m.workspace_id = ? ORDER BY u.email""",
                (workspace_id,),
            )]

    def set_member(self, workspace_id: str, user_id: str, role: UserRole):
        with self.connection() as conn:
            conn.execute(
                """INSERT INTO workspace_members (workspace_id,user_id,role,joined_at) VALUES (?,?,?,?)
                   ON CONFLICT(workspace_id,user_id) DO UPDATE SET role = excluded.role""",
                (workspace_id, user_id, role.value, datetime.now(timezone.utc).isoformat()),
            )

    def remove_member(self, workspace_id: str, user_id: str):
        with self.connection() as conn:
            conn.execute("DELETE FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
                         (workspace_id, user_id))

    def revoke_tokens(self, user_id: str):
        with self.connection() as conn:
            conn.execute("UPDATE users SET token_version = token_version + 1 WHERE id = ?", (user_id,))

    def change_password(self, user_id: str, hashed_password: str, *, temporary=False):
        with self.connection() as conn:
            conn.execute(
                "UPDATE users SET hashed_password = ?, must_change_password = ?, token_version = token_version + 1 WHERE id = ?",
                (hashed_password, int(temporary), user_id),
            )

    def get_member_role(self, workspace_id: str, user_id: str):
        with self.connection() as conn:
            row = conn.execute("SELECT role FROM workspace_members WHERE workspace_id = ? AND user_id = ?",
                               (workspace_id, user_id)).fetchone()
        return UserRole(row["role"]) if row else None

    def workspace_exists(self, workspace_id):
        with self.connection() as conn:
            return conn.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone() is not None

    def workspace_ids(self):
        with self.connection() as conn:
            return [row["id"] for row in conn.execute("SELECT id FROM workspaces ORDER BY id")]
