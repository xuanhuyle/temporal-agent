"""Subscriptions and the entitlements they grant.

PayGate is the source of truth for subscription state. Tasklane keeps a local
copy per account in the ``subscriptions`` table, refreshed by the
``reconcile_subscriptions`` background job (ADR-0003). Feature limits are
always derived from that local copy via :func:`entitlements_for`.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from tasklane.config import Settings, load_settings
from tasklane.db import format_timestamp, parse_timestamp
from tasklane.plans import get_plan

# PayGate retries a failed renewal automatically (3 attempts over 3 days) and
# cancels the subscription after the last one, so a past_due subscription
# keeps its plan until then (ADR-0004).
ENTITLED_STATUSES = frozenset({"active", "trialing", "past_due"})

FREE_PLAN_ID = "free"


@dataclass(frozen=True)
class Subscription:
    account_id: int
    plan_id: str
    status: str  # PayGate status: incomplete|trialing|active|past_due|canceled|unpaid
    provider_subscription_id: str
    provider_customer_id: str
    current_period_end: datetime
    created_at: datetime


@dataclass(frozen=True)
class Entitlements:
    plan_id: str
    max_projects: int | None
    max_seats: int
    reason: str  # why this plan applies, e.g. "status:active" or "checkout_grace"


def _entitlements(plan_id: str, reason: str) -> Entitlements:
    plan = get_plan(plan_id)
    return Entitlements(
        plan_id=plan.plan_id,
        max_projects=plan.max_projects,
        max_seats=plan.max_seats,
        reason=reason,
    )


def entitlements_for(
    subscription: Subscription | None,
    now: datetime,
    settings: Settings | None = None,
) -> Entitlements:
    """Return what an account may use, given its subscription (if any).

    - no subscription: Free plan;
    - ``active`` or ``trialing``: the subscribed plan;
    - ``past_due``: the subscribed plan while PayGate retries the failed
      renewal (ADR-0004);
    - ``incomplete`` within ``checkout_grace_minutes`` of creation: the
      subscribed plan, so customers are not locked out while the first payment
      is confirmed (ADR-0003);
    - any other status (``canceled``, ``unpaid``, an expired
      ``incomplete``): Free plan.
    """
    if subscription is None:
        return _entitlements(FREE_PLAN_ID, "no_subscription")
    if settings is None:
        settings = load_settings()

    status = subscription.status
    if status in ENTITLED_STATUSES:
        return _entitlements(subscription.plan_id, f"status:{status}")

    if status == "incomplete":
        grace = timedelta(minutes=settings.checkout_grace_minutes)
        if now - subscription.created_at <= grace:
            return _entitlements(subscription.plan_id, "checkout_grace")

    return _entitlements(FREE_PLAN_ID, f"status:{status}")


def save_subscription(conn: sqlite3.Connection, subscription: Subscription, now: datetime) -> None:
    """Insert or replace the subscription for ``subscription.account_id``."""
    get_plan(subscription.plan_id)  # reject unknown plans before they reach the table
    with conn:
        conn.execute(
            """
            INSERT INTO subscriptions (
                account_id, plan_id, status, provider_subscription_id,
                provider_customer_id, current_period_end, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (account_id) DO UPDATE SET
                plan_id = excluded.plan_id,
                status = excluded.status,
                provider_subscription_id = excluded.provider_subscription_id,
                provider_customer_id = excluded.provider_customer_id,
                current_period_end = excluded.current_period_end,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at
            """,
            (
                subscription.account_id,
                subscription.plan_id,
                subscription.status,
                subscription.provider_subscription_id,
                subscription.provider_customer_id,
                format_timestamp(subscription.current_period_end),
                format_timestamp(subscription.created_at),
                format_timestamp(now),
            ),
        )


def _from_row(row: sqlite3.Row) -> Subscription:
    return Subscription(
        account_id=int(row["account_id"]),
        plan_id=row["plan_id"],
        status=row["status"],
        provider_subscription_id=row["provider_subscription_id"],
        provider_customer_id=row["provider_customer_id"],
        current_period_end=parse_timestamp(row["current_period_end"]),
        created_at=parse_timestamp(row["created_at"]),
    )


def get_subscription(conn: sqlite3.Connection, account_id: int) -> Subscription | None:
    row = conn.execute(
        "SELECT * FROM subscriptions WHERE account_id = ?", (account_id,)
    ).fetchone()
    return None if row is None else _from_row(row)


def list_subscriptions(conn: sqlite3.Connection) -> list[Subscription]:
    """All locally known subscriptions, ordered by account id."""
    rows = conn.execute("SELECT * FROM subscriptions ORDER BY account_id").fetchall()
    return [_from_row(row) for row in rows]
