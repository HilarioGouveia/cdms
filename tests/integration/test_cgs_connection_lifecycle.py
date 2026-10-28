"""Regressões de transação e liberação de conexões dos adaptadores CGS."""

import sqlite3

import pytest

from cgs.adapters.persistence.sqlite_growth_repo import SQLiteGrowthRepository
from cgs.adapters.persistence.sqlite_cgs_fase2_repo import SQLiteCGSPhase2Repository
from cgs.adapters.persistence.sqlite_cgs_fase3_repo import SQLiteCGSPhase3Repository


@pytest.mark.parametrize("repository_type", [
    SQLiteGrowthRepository, SQLiteCGSPhase2Repository, SQLiteCGSPhase3Repository,
])
def test_transaction_commit_rollback_and_connection_release(tmp_path, repository_type):
    db_path = tmp_path / "transaction.db"
    repo = repository_type(str(db_path))

    with repo._get_connection() as conn:
        conn.execute("CREATE TABLE connection_probe (value INTEGER)")
        conn.execute("INSERT INTO connection_probe VALUES (1)")
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")

    with pytest.raises(RuntimeError, match="abort transaction"):
        with repo._get_connection() as failed_conn:
            failed_conn.execute("INSERT INTO connection_probe VALUES (2)")
            raise RuntimeError("abort transaction")
    with pytest.raises(sqlite3.ProgrammingError):
        failed_conn.execute("SELECT 1")

    with repo._get_connection() as read_conn:
        assert [row[0] for row in read_conn.execute("SELECT value FROM connection_probe")] == [1]
    db_path.unlink()
    assert not db_path.exists()
