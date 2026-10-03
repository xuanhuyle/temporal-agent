from datetime import timedelta

import pytest

from tasklane.auth import register_user
from tasklane.billing import Subscription, save_subscription
from tasklane.projects import (
    EntitlementError,
    add_task,
    create_account,
    create_project,
    list_tasks,
)


@pytest.fixture
def owner_id(conn, settings, now):
    return register_user(conn, "owner@example.com", "s3cret-pass", settings, now)


@pytest.fixture
def account_id(conn, owner_id, now):
    return create_account(conn, "Acme", owner_id, now)


def subscribe(conn, account_id, now, status="active", plan_id="pro"):
    save_subscription(
        conn,
        Subscription(
            account_id=account_id,
            plan_id=plan_id,
            status=status,
            provider_subscription_id="sub_0001",
            provider_customer_id="cus_0001",
            current_period_end=now + timedelta(days=30),
            created_at=now - timedelta(days=1),
        ),
        now,
    )


def test_create_account_adds_owner_membership(conn, owner_id, account_id):
    row = conn.execute("SELECT * FROM memberships WHERE account_id = ?", (account_id,)).fetchone()
    assert row["user_id"] == owner_id
    assert row["role"] == "owner"


def test_free_plan_project_limit(conn, settings, now, account_id):
    for i in range(3):
        create_project(conn, account_id, f"Project {i}", now, settings)
    with pytest.raises(EntitlementError, match="at most 3 projects"):
        create_project(conn, account_id, "One too many", now, settings)
    (count,) = conn.execute("SELECT COUNT(*) FROM projects").fetchone()
    assert count == 3


def test_paid_plan_has_no_project_limit(conn, settings, now, account_id):
    subscribe(conn, account_id, now)
    for i in range(6):
        create_project(conn, account_id, f"Project {i}", now, settings)


def test_canceled_subscription_gets_free_limits(conn, settings, now, account_id):
    subscribe(conn, account_id, now, status="canceled")
    for i in range(3):
        create_project(conn, account_id, f"Project {i}", now, settings)
    with pytest.raises(EntitlementError):
        create_project(conn, account_id, "Project 3", now, settings)


def test_project_limits_are_per_account(conn, settings, now, owner_id, account_id):
    other = create_account(conn, "Other", owner_id, now)
    for i in range(3):
        create_project(conn, account_id, f"Project {i}", now, settings)
    assert create_project(conn, other, "Project 0", now, settings)


def test_names_must_not_be_blank(conn, settings, now, owner_id, account_id):
    with pytest.raises(ValueError):
        create_account(conn, "  ", owner_id, now)
    with pytest.raises(ValueError):
        create_project(conn, account_id, "", now, settings)
    project_id = create_project(conn, account_id, "Roadmap", now, settings)
    with pytest.raises(ValueError):
        add_task(conn, project_id, "   ", now)


def test_tasks_are_listed_in_creation_order(conn, settings, now, account_id):
    project_id = create_project(conn, account_id, "Roadmap", now, settings)
    later = add_task(conn, project_id, "Ship it", now + timedelta(minutes=5))
    first = add_task(conn, project_id, "Write spec", now)
    same_time = add_task(conn, project_id, "Review spec", now)

    tasks = list_tasks(conn, project_id)
    assert [t["id"] for t in tasks] == [first, same_time, later]
    assert tasks[0] == {
        "id": first,
        "project_id": project_id,
        "title": "Write spec",
        "done": False,
        "created_at": "2026-01-05T12:00:00+00:00",
    }
    assert list_tasks(conn, create_project(conn, account_id, "Other", now, settings)) == []
