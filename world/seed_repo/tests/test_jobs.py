from datetime import timedelta

import pytest

from tasklane.auth import register_user
from tasklane.billing import Subscription, get_subscription, save_subscription
from tasklane.db import format_timestamp
from tasklane.jobs import (
    MAX_ATTEMPTS,
    RECONCILE_JOB,
    ReconcileResult,
    claim_due,
    complete,
    enqueue,
    ensure_reconcile_scheduled,
    fail,
    make_reconcile_handler,
    reconcile_subscriptions,
    run_due_jobs,
    run_worker_pass,
    schedule_next_reconcile,
)
from tasklane.projects import create_account
from tasklane.providers import ProviderError, ProviderUnavailable


def job_row(conn, job_id):
    return conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()


# -- queue -----------------------------------------------------------------


def test_enqueue_claim_complete(conn, now):
    job_id = enqueue(conn, "send_digest", {"account_id": 7}, now, now)
    job = claim_due(conn, now)
    assert job is not None
    assert job.id == job_id
    assert job.kind == "send_digest"
    assert job.payload == {"account_id": 7}
    assert job.status == "running"
    assert job.attempts == 1
    assert job.run_at == now
    assert claim_due(conn, now) is None  # already claimed

    complete(conn, job_id, now)
    assert job_row(conn, job_id)["status"] == "done"
    assert claim_due(conn, now + timedelta(days=1)) is None


def test_claim_order_is_run_at_then_id(conn, now):
    later = enqueue(conn, "k", {"n": "later"}, now - timedelta(minutes=1), now)
    first_tie = enqueue(conn, "k", {"n": "tie-1"}, now - timedelta(minutes=5), now)
    second_tie = enqueue(conn, "k", {"n": "tie-2"}, now - timedelta(minutes=5), now)
    not_yet_due = enqueue(conn, "k", {"n": "not yet due"}, now + timedelta(seconds=1), now)

    claimed = []
    while (job := claim_due(conn, now)) is not None:
        claimed.append(job.id)
    assert claimed == [first_tie, second_tie, later]
    assert job_row(conn, not_yet_due)["status"] == "pending"


def test_retry_backoff(conn, now):
    job_id = enqueue(conn, "k", {}, now, now)

    claim_due(conn, now)
    fail(conn, job_id, "boom", now)
    row = job_row(conn, job_id)
    assert row["status"] == "pending"
    assert row["attempts"] == 1
    assert row["last_error"] == "boom"
    assert row["run_at"] == "2026-01-05T12:02:00+00:00"  # 2 ** 1 minutes

    assert claim_due(conn, now + timedelta(minutes=1)) is None
    t2 = now + timedelta(minutes=2)
    assert claim_due(conn, t2).attempts == 2
    fail(conn, job_id, "boom again", t2)
    assert job_row(conn, job_id)["run_at"] == "2026-01-05T12:06:00+00:00"  # t2 + 2 ** 2 minutes


def test_job_is_dead_after_max_attempts(conn, now):
    job_id = enqueue(conn, "k", {}, now, now)
    t = now
    for attempt in range(1, MAX_ATTEMPTS + 1):
        job = claim_due(conn, t)
        assert job is not None and job.attempts == attempt
        fail(conn, job_id, f"failure {attempt}", t)
        t += timedelta(days=1)

    row = job_row(conn, job_id)
    assert row["status"] == "dead"
    assert row["attempts"] == MAX_ATTEMPTS
    assert row["last_error"] == f"failure {MAX_ATTEMPTS}"
    assert claim_due(conn, t + timedelta(days=365)) is None


def test_fail_unknown_job(conn, now):
    with pytest.raises(ValueError):
        fail(conn, 999, "boom", now)


def test_run_due_jobs(conn, now):
    calls = []

    def ok(c, payload, at):
        calls.append((payload, at))

    def broken(c, payload, at):
        raise RuntimeError("handler exploded")

    ok_id = enqueue(conn, "ok", {"x": 1}, now, now)
    broken_id = enqueue(conn, "broken", {}, now, now)
    orphan_id = enqueue(conn, "orphan", {}, now, now)
    not_due_id = enqueue(conn, "ok", {"x": 2}, now + timedelta(hours=1), now)

    assert run_due_jobs(conn, {"ok": ok, "broken": broken}, now) == 3
    assert calls == [({"x": 1}, now)]
    assert job_row(conn, ok_id)["status"] == "done"
    assert job_row(conn, broken_id)["status"] == "pending"
    assert job_row(conn, broken_id)["last_error"] == "RuntimeError: handler exploded"
    assert "no handler" in job_row(conn, orphan_id)["last_error"]
    assert job_row(conn, not_due_id)["status"] == "pending"
    assert run_due_jobs(conn, {"ok": ok}, now) == 0


def test_failed_handler_uncommitted_changes_are_rolled_back(conn, now):
    def half_done(c, payload, at):
        c.execute(
            "INSERT INTO users (email, password_hash, created_at)"
            " VALUES ('x@example.com', 'h', '2026-01-05T12:00:00+00:00')"
        )
        raise RuntimeError("failed midway")

    enqueue(conn, "half", {}, now, now)
    run_due_jobs(conn, {"half": half_done}, now)
    (count,) = conn.execute("SELECT COUNT(*) FROM users").fetchone()
    assert count == 0


# -- subscription reconciliation ---------------------------------------------


def subscribe_account(conn, settings, now, sandbox, email, remote_plan="pro"):
    """Create an account with an active Pro subscription mirrored locally."""
    user_id = register_user(conn, email, "s3cret-pass", settings, now)
    account_id = create_account(conn, "Acme", user_id, now)
    customer = sandbox.create_customer(email)
    remote = sandbox.create_subscription(customer["id"], remote_plan, status="active")
    save_subscription(
        conn,
        Subscription(
            account_id=account_id,
            plan_id="pro",
            status="active",
            provider_subscription_id=remote["id"],
            provider_customer_id=customer["id"],
            current_period_end=now + timedelta(days=30),
            created_at=now,
        ),
        now,
    )
    return account_id, remote["id"]


@pytest.fixture
def subscribed_account(conn, settings, now, sandbox):
    return subscribe_account(conn, settings, now, sandbox, "owner@example.com")


def test_reconcile_without_changes(conn, settings, provider, sandbox, now):
    assert reconcile_subscriptions(conn, provider, now) == ReconcileResult(0, 0, 0)
    subscribe_account(conn, settings, now, sandbox, "owner@example.com")
    assert reconcile_subscriptions(conn, provider, now) == ReconcileResult(1, 0, 0)


def test_reconcile_updates_changed_status(conn, provider, sandbox, now, subscribed_account):
    account_id, subscription_id = subscribed_account
    sandbox.set_subscription_status(subscription_id, "past_due")

    later = now + timedelta(minutes=15)
    assert reconcile_subscriptions(conn, provider, later) == ReconcileResult(1, 1, 0)

    local = get_subscription(conn, account_id)
    assert local.status == "past_due"
    assert local.plan_id == "pro"
    assert local.created_at == now
    updated_at = conn.execute(
        "SELECT updated_at FROM subscriptions WHERE account_id = ?", (account_id,)
    ).fetchone()[0]
    assert updated_at == "2026-01-05T12:15:00+00:00"

    assert reconcile_subscriptions(conn, provider, later).changed == 0


def test_reconcile_propagates_provider_unavailable(
    conn, provider, sandbox, now, subscribed_account
):
    sandbox.fail_next(1)
    with pytest.raises(ProviderUnavailable):
        reconcile_subscriptions(conn, provider, now)


def test_reconcile_continues_past_a_failing_subscription(
    conn, settings, provider, sandbox, now, caplog
):
    missing, _ = subscribe_account(conn, settings, now, sandbox, "a@example.com")
    canceled, canceled_sub = subscribe_account(
        conn, settings, now, sandbox, "b@example.com", remote_plan="pro_annual"
    )
    sandbox.set_subscription_status(canceled_sub, "canceled")
    sandbox.fail_next(1, error="not_found")  # PayGate no longer knows the first subscription

    assert reconcile_subscriptions(conn, provider, now) == ReconcileResult(1, 1, 1)
    assert get_subscription(conn, missing).status == "active"
    # An unknown remote plan keeps the local plan but still applies the status change.
    assert get_subscription(conn, canceled).status == "canceled"
    assert get_subscription(conn, canceled).plan_id == "pro"
    assert len([r for r in caplog.records if r.levelname == "WARNING"]) == 2


def test_reconcile_fails_when_no_subscription_could_be_refreshed(
    conn, settings, provider, sandbox, now
):
    subscribe_account(conn, settings, now, sandbox, "a@example.com")
    sandbox.fail_next(1, error="api_error")
    with pytest.raises(ProviderError, match="could not reconcile any"):
        reconcile_subscriptions(conn, provider, now)


def test_schedule_next_reconcile(conn, settings, now):
    job_id = schedule_next_reconcile(conn, now, settings)
    row = job_row(conn, job_id)
    assert row["kind"] == RECONCILE_JOB
    assert row["status"] == "pending"
    assert row["run_at"] == "2026-01-05T12:15:00+00:00"


def test_reconcile_job_retries_when_provider_unavailable(
    conn, settings, provider, sandbox, now, subscribed_account
):
    account_id, subscription_id = subscribed_account
    handlers = {RECONCILE_JOB: make_reconcile_handler(provider, settings)}
    job_id = schedule_next_reconcile(conn, now, settings)
    sandbox.set_subscription_status(subscription_id, "canceled")
    sandbox.fail_next(1)

    t1 = now + timedelta(minutes=15)
    assert run_due_jobs(conn, handlers, t1) == 1
    row = job_row(conn, job_id)
    assert row["status"] == "pending"
    assert row["attempts"] == 1
    assert row["run_at"] == "2026-01-05T12:17:00+00:00"
    assert row["last_error"].startswith("ProviderUnavailable")
    assert get_subscription(conn, account_id).status == "active"

    t2 = t1 + timedelta(minutes=2)
    assert run_due_jobs(conn, handlers, t2) == 1
    assert job_row(conn, job_id)["status"] == "done"
    assert get_subscription(conn, account_id).status == "canceled"

    pending = conn.execute(
        "SELECT run_at FROM jobs WHERE kind = ? AND status = 'pending'", (RECONCILE_JOB,)
    ).fetchall()
    assert [r["run_at"] for r in pending] == ["2026-01-05T12:32:00+00:00"]


def test_polling_resumes_after_reconcile_job_dies(
    conn, settings, provider, sandbox, now, subscribed_account
):
    account_id, subscription_id = subscribed_account
    handlers = {RECONCILE_JOB: make_reconcile_handler(provider, settings)}
    assert run_worker_pass(conn, handlers, now, settings) == 0  # schedules the first run
    (first,) = conn.execute("SELECT id FROM jobs WHERE kind = ?", (RECONCILE_JOB,)).fetchone()
    assert ensure_reconcile_scheduled(conn, now, settings) is None  # already pending

    sandbox.set_subscription_status(subscription_id, "canceled")
    sandbox.fail_next(MAX_ATTEMPTS)  # PayGate is down for every attempt of the first run
    for minute in range(1, 120):
        run_worker_pass(conn, handlers, now + timedelta(minutes=minute), settings)
        if job_row(conn, first)["status"] == "dead":
            break
    assert minute == 15 + 2 + 4 + 8 + 16
    assert get_subscription(conn, account_id).status == "active"

    # PayGate is back: the next pass enqueues a fresh run instead of polling stopping for good.
    t = now + timedelta(minutes=minute + 1)
    run_worker_pass(conn, handlers, t, settings)
    pending = conn.execute(
        "SELECT run_at FROM jobs WHERE kind = ? AND status = 'pending'", (RECONCILE_JOB,)
    ).fetchall()
    assert [r["run_at"] for r in pending] == [format_timestamp(t + timedelta(minutes=15))]

    assert run_worker_pass(conn, handlers, t + timedelta(minutes=15), settings) == 1
    assert get_subscription(conn, account_id).status == "canceled"
