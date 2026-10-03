import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from tasklane import db
from tasklane.db import connect, format_timestamp, migrate, parse_timestamp

FIRST_MIGRATIONS = [
    "0001_users_sessions.sql",
    "0002_accounts_projects_tasks.sql",
    "0003_subscriptions.sql",
    "0004_jobs.sql",
]


def shipped_migrations():
    return sorted(path.name for path in db.MIGRATIONS_DIR.glob("*.sql"))


def tables(conn):
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {row["name"] for row in rows}


def test_migrate_applies_all_migrations_in_order(now):
    expected = shipped_migrations()
    assert expected[: len(FIRST_MIGRATIONS)] == FIRST_MIGRATIONS
    conn = connect(":memory:")
    assert migrate(conn, now) == expected
    rows = conn.execute("SELECT name, applied_at FROM schema_migrations ORDER BY rowid").fetchall()
    assert [row["name"] for row in rows] == expected
    assert {row["applied_at"] for row in rows} == {"2026-01-05T12:00:00+00:00"}
    assert {"users", "sessions", "accounts", "memberships"} <= tables(conn)
    assert {"projects", "tasks", "subscriptions", "jobs"} <= tables(conn)


def test_migrate_is_idempotent(conn):
    assert migrate(conn) == []
    assert migrate(conn) == []
    (count,) = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()
    assert count == len(shipped_migrations())


def test_migrations_are_applied_by_filename_order(tmp_path, monkeypatch):
    # Created out of order on purpose; 0002 depends on 0001 and 0010 on both.
    (tmp_path / "0010_c.sql").write_text("CREATE TABLE c (b_id INTEGER REFERENCES b(id));")
    (tmp_path / "0002_b.sql").write_text(
        "CREATE TABLE b (id INTEGER PRIMARY KEY, a_id INTEGER);\n"
        "INSERT INTO b (a_id) SELECT id FROM a;"
    )
    (tmp_path / "0001_a.sql").write_text(
        "CREATE TABLE a (id INTEGER PRIMARY KEY);\nINSERT INTO a DEFAULT VALUES;"
    )
    (tmp_path / "notes.txt").write_text("not a migration")
    monkeypatch.setattr(db, "MIGRATIONS_DIR", tmp_path)

    conn = connect(":memory:")
    assert migrate(conn) == ["0001_a.sql", "0002_b.sql", "0010_c.sql"]
    assert conn.execute("SELECT a_id FROM b").fetchone()["a_id"] == 1


def test_new_migration_file_is_picked_up(tmp_path, monkeypatch):
    (tmp_path / "0001_a.sql").write_text("CREATE TABLE a (id INTEGER PRIMARY KEY);")
    monkeypatch.setattr(db, "MIGRATIONS_DIR", tmp_path)
    conn = connect(":memory:")
    assert migrate(conn) == ["0001_a.sql"]

    (tmp_path / "0002_add_name.sql").write_text("ALTER TABLE a ADD COLUMN name TEXT;")
    assert migrate(conn) == ["0002_add_name.sql"]
    assert migrate(conn) == []


def test_failed_migration_is_rolled_back(tmp_path, monkeypatch):
    (tmp_path / "0001_ok.sql").write_text("CREATE TABLE a (id INTEGER PRIMARY KEY);")
    (tmp_path / "0002_broken.sql").write_text("CREATE TABLE b (id INTEGER);\nTHIS IS NOT SQL;")
    monkeypatch.setattr(db, "MIGRATIONS_DIR", tmp_path)
    conn = connect(":memory:")

    with pytest.raises(sqlite3.Error):
        migrate(conn)

    assert "a" in tables(conn)
    assert "b" not in tables(conn)
    recorded = [row["name"] for row in conn.execute("SELECT name FROM schema_migrations")]
    assert recorded == ["0001_ok.sql"]


def test_connection_settings(conn):
    assert conn.row_factory is sqlite3.Row
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO sessions (token_sha256, user_id, created_at, expires_at)"
            " VALUES ('x', 999, '2026-01-01T00:00:00+00:00', '2026-01-02T00:00:00+00:00')"
        )


def test_file_database_creates_directory_and_uses_wal(tmp_path):
    path = tmp_path / "nested" / "dir" / "tasklane.sqlite3"
    conn = connect(path)
    try:
        assert path.parent.is_dir()
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert migrate(conn) == shipped_migrations()
    finally:
        conn.close()


def test_timestamp_roundtrip_normalizes_to_utc():
    value = datetime(2026, 1, 5, 12, 30, 15, tzinfo=timezone.utc)
    text = format_timestamp(value)
    assert text == "2026-01-05T12:30:15+00:00"
    assert parse_timestamp(text) == value
    plus_one = datetime(2026, 1, 5, 13, 30, tzinfo=timezone(timedelta(hours=1)))
    assert format_timestamp(plus_one) == "2026-01-05T12:30:00+00:00"


def test_naive_timestamps_rejected():
    with pytest.raises(ValueError):
        format_timestamp(datetime(2026, 1, 5, 12, 0))
    with pytest.raises(ValueError):
        parse_timestamp("2026-01-05T12:00:00")
