"""SQLite connection handling, schema migrations and timestamp encoding.

Tasklane persists everything in a single SQLite database (ADR-0001). Schema
changes are plain ``.sql`` files in ``tasklane/migrations`` named
``NNNN_description.sql``; :func:`migrate` applies the ones not yet recorded in
``schema_migrations`` in filename order, each inside its own transaction
(so migration files must not contain their own ``BEGIN``/``COMMIT``).

Timestamps are stored as ISO-8601 strings in UTC with second precision
(``2026-01-05T12:00:00+00:00``). Because every stored value uses the same
format, string comparison in SQL matches chronological order.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

_MEMORY = ":memory:"


def connect(path: str | Path) -> sqlite3.Connection:
    """Open a connection configured the way the application expects.

    ``":memory:"`` opens a private in-memory database. For file databases the
    parent directory is created if needed and WAL journaling is enabled.
    """
    if str(path) == _MEMORY:
        conn = sqlite3.connect(_MEMORY)
    else:
        db_path = Path(path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def migrate(conn: sqlite3.Connection, now: datetime | None = None) -> list[str]:
    """Apply pending migrations in filename order and return their names.

    Running it again is a no-op. Each migration and its ``schema_migrations``
    row are committed together, so a failing migration leaves no trace and
    can be retried after it is fixed. ``now``, if given, is recorded as the
    ``applied_at`` time of the migrations applied by this call.
    """
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " name TEXT PRIMARY KEY,"
        " applied_at TEXT)"
    )
    conn.commit()
    applied = {row[0] for row in conn.execute("SELECT name FROM schema_migrations")}
    applied_at = "NULL" if now is None else _sql_literal(format_timestamp(now))

    newly_applied: list[str] = []
    for script in sorted(MIGRATIONS_DIR.glob("*.sql"), key=lambda p: p.name):
        if script.name in applied:
            continue
        body = script.read_text(encoding="utf-8")
        try:
            conn.executescript(
                "BEGIN;\n"
                f"{body}\n;\n"
                "INSERT INTO schema_migrations (name, applied_at) VALUES ("
                f"{_sql_literal(script.name)}, {applied_at});\n"
                "COMMIT;"
            )
        except sqlite3.Error:
            if conn.in_transaction:
                conn.rollback()
            raise
        newly_applied.append(script.name)
    return newly_applied


def format_timestamp(value: datetime) -> str:
    """Encode an aware datetime for storage (UTC, second precision)."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("naive datetimes are not allowed; pass an aware UTC datetime")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_timestamp(value: str) -> datetime:
    """Decode a stored timestamp into an aware UTC datetime."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"stored timestamp has no UTC offset: {value!r}")
    return parsed.astimezone(timezone.utc)
