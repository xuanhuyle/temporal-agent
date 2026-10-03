"""Accounts, projects and tasks."""

import sqlite3
from datetime import datetime
from typing import Any

from tasklane.billing import entitlements_for, get_subscription
from tasklane.config import Settings
from tasklane.db import format_timestamp


class EntitlementError(Exception):
    """The account's current plan does not allow the requested action."""


def _require_text(value: str, field: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field} must not be empty")
    return cleaned


def create_account(conn: sqlite3.Connection, name: str, owner_user_id: int, now: datetime) -> int:
    """Create an account owned by ``owner_user_id`` and return its id."""
    name = _require_text(name, "account name")
    with conn:
        cursor = conn.execute(
            "INSERT INTO accounts (name, owner_user_id, created_at) VALUES (?, ?, ?)",
            (name, owner_user_id, format_timestamp(now)),
        )
        account_id = int(cursor.lastrowid)
        conn.execute(
            "INSERT INTO memberships (account_id, user_id, role) VALUES (?, ?, 'owner')",
            (account_id, owner_user_id),
        )
    return account_id


def create_project(
    conn: sqlite3.Connection,
    account_id: int,
    name: str,
    now: datetime,
    settings: Settings | None = None,
) -> int:
    """Create a project in ``account_id`` and return its id.

    Raises:
        EntitlementError: if the account already has as many projects as its
            plan allows.
    """
    name = _require_text(name, "project name")
    entitlements = entitlements_for(get_subscription(conn, account_id), now, settings)
    if entitlements.max_projects is not None:
        (count,) = conn.execute(
            "SELECT COUNT(*) FROM projects WHERE account_id = ?", (account_id,)
        ).fetchone()
        if count >= entitlements.max_projects:
            raise EntitlementError(
                f"the {entitlements.plan_id} plan allows at most "
                f"{entitlements.max_projects} projects"
            )
    with conn:
        cursor = conn.execute(
            "INSERT INTO projects (account_id, name, created_at) VALUES (?, ?, ?)",
            (account_id, name, format_timestamp(now)),
        )
    return int(cursor.lastrowid)


def add_task(conn: sqlite3.Connection, project_id: int, title: str, now: datetime) -> int:
    """Add a task to ``project_id`` and return its id."""
    title = _require_text(title, "task title")
    with conn:
        cursor = conn.execute(
            "INSERT INTO tasks (project_id, title, created_at) VALUES (?, ?, ?)",
            (project_id, title, format_timestamp(now)),
        )
    return int(cursor.lastrowid)


def list_tasks(conn: sqlite3.Connection, project_id: int) -> list[dict[str, Any]]:
    """Tasks of ``project_id`` in creation order."""
    rows = conn.execute(
        "SELECT id, project_id, title, done, created_at FROM tasks"
        " WHERE project_id = ? ORDER BY created_at, id",
        (project_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "project_id": row["project_id"],
            "title": row["title"],
            "done": bool(row["done"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]
