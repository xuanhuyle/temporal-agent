"""Background jobs.

The job queue is a table in the application's SQLite database (ADR-0001), so
there is no separate broker to run. The worker repeatedly calls
:func:`run_worker_pass`; a failed job goes back to ``pending`` with
exponential backoff and is marked ``dead`` after :data:`MAX_ATTEMPTS`
attempts.

Subscription state is pulled from the payment provider by polling (ADR-0003):
the :data:`RECONCILE_JOB` job runs :func:`reconcile_subscriptions` and then
schedules its next run ``reconcile_interval_minutes`` later. Each worker pass
also calls :func:`ensure_reconcile_scheduled` before running due jobs, so
polling resumes on its own even after a run has used up its retries.
"""

import json
import logging
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from tasklane.billing import list_subscriptions, save_subscription
from tasklane.config import Settings
from tasklane.db import format_timestamp, parse_timestamp
from tasklane.plans import PLANS
from tasklane.providers.payments import PaymentProvider, ProviderError, ProviderUnavailable

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
RECONCILE_JOB = "reconcile_subscriptions"

Handler = Callable[[sqlite3.Connection, dict, datetime], None]


@dataclass(frozen=True)
class Job:
    id: int
    kind: str
    payload: dict
    status: str
    attempts: int
    run_at: datetime


def enqueue(
    conn: sqlite3.Connection,
    kind: str,
    payload: dict,
    run_at: datetime,
    now: datetime,
) -> int:
    """Add a job that becomes due at ``run_at`` and return its id."""
    stamp = format_timestamp(now)
    with conn:
        cursor = conn.execute(
            "INSERT INTO jobs (kind, payload, status, attempts, run_at, created_at, updated_at)"
            " VALUES (?, ?, 'pending', 0, ?, ?, ?)",
            (kind, json.dumps(payload, sort_keys=True), format_timestamp(run_at), stamp, stamp),
        )
    return int(cursor.lastrowid)


def claim_due(conn: sqlite3.Connection, now: datetime) -> Job | None:
    """Claim the oldest due pending job, marking it running.

    Jobs are taken in ``run_at`` order, ties broken by id. Returns None when
    nothing is due.
    """
    stamp = format_timestamp(now)
    while True:
        row = conn.execute(
            "SELECT id FROM jobs WHERE status = 'pending' AND run_at <= ?"
            " ORDER BY run_at, id LIMIT 1",
            (stamp,),
        ).fetchone()
        if row is None:
            return None
        with conn:
            # The status check makes the claim atomic: if another worker took
            # the job since the SELECT, nothing is updated and we look again.
            cursor = conn.execute(
                "UPDATE jobs SET status = 'running', attempts = attempts + 1, updated_at = ?"
                " WHERE id = ? AND status = 'pending'",
                (stamp, row["id"]),
            )
        if cursor.rowcount == 1:
            break
    claimed = conn.execute(
        "SELECT id, kind, payload, status, attempts, run_at FROM jobs WHERE id = ?",
        (row["id"],),
    ).fetchone()
    return Job(
        id=int(claimed["id"]),
        kind=claimed["kind"],
        payload=json.loads(claimed["payload"]),
        status=claimed["status"],
        attempts=int(claimed["attempts"]),
        run_at=parse_timestamp(claimed["run_at"]),
    )


def complete(conn: sqlite3.Connection, job_id: int, now: datetime) -> None:
    with conn:
        conn.execute(
            "UPDATE jobs SET status = 'done', updated_at = ? WHERE id = ?",
            (format_timestamp(now), job_id),
        )


def fail(conn: sqlite3.Connection, job_id: int, error: str, now: datetime) -> None:
    """Record a failed attempt.

    The job is retried after ``2 ** attempts`` minutes (2, 4, 8, 16), or
    marked ``dead`` once it has been attempted :data:`MAX_ATTEMPTS` times.
    """
    row = conn.execute("SELECT attempts FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        raise ValueError(f"no such job: {job_id}")
    attempts = int(row["attempts"])
    stamp = format_timestamp(now)
    with conn:
        if attempts >= MAX_ATTEMPTS:
            conn.execute(
                "UPDATE jobs SET status = 'dead', last_error = ?, updated_at = ? WHERE id = ?",
                (error, stamp, job_id),
            )
        else:
            retry_at = now + timedelta(minutes=2**attempts)
            conn.execute(
                "UPDATE jobs SET status = 'pending', run_at = ?, last_error = ?, updated_at = ?"
                " WHERE id = ?",
                (format_timestamp(retry_at), error, stamp, job_id),
            )


def run_due_jobs(
    conn: sqlite3.Connection,
    handlers: dict[str, Handler],
    now: datetime,
) -> int:
    """Run every job due at ``now`` and return how many were processed.

    A handler that raises causes the job to be retried later (see
    :func:`fail`) and its uncommitted writes are rolled back; anything it
    already committed stays. A job whose kind has no handler fails the same
    way.
    """
    processed = 0
    while (job := claim_due(conn, now)) is not None:
        processed += 1
        handler = handlers.get(job.kind)
        if handler is None:
            fail(conn, job.id, f"no handler registered for job kind {job.kind!r}", now)
            continue
        try:
            handler(conn, job.payload, now)
        except Exception as exc:  # noqa: BLE001 - any handler error means "retry later"
            conn.rollback()
            fail(conn, job.id, f"{type(exc).__name__}: {exc}", now)
        else:
            complete(conn, job.id, now)
    return processed


@dataclass(frozen=True)
class ReconcileResult:
    """Outcome of one reconciliation run.

    ``checked`` subscriptions were refreshed from the provider, ``changed`` of
    them had a local update, and ``failed`` could not be fetched this run.
    """

    checked: int
    changed: int
    failed: int = 0


def reconcile_subscriptions(
    conn: sqlite3.Connection,
    provider: PaymentProvider,
    now: datetime,
) -> ReconcileResult:
    """Refresh every local subscription from the payment provider.

    Status, plan and current period end are updated when they differ from the
    provider's view. :class:`~tasklane.providers.ProviderUnavailable`
    propagates so that the job is retried with backoff. If the provider
    rejects the request for a single subscription, that is logged and counted
    in ``failed``, and the remaining subscriptions are still refreshed. A plan
    we do not know is logged and the local plan is kept, but status and period
    end are still updated so that a cancellation is never missed.
    """
    checked = changed = failed = 0
    for local in list_subscriptions(conn):
        try:
            remote = provider.get_subscription(local.provider_subscription_id)
        except ProviderUnavailable:
            raise
        except ProviderError as exc:
            failed += 1
            logger.warning(
                "could not reconcile subscription %s (account %s): %s",
                local.provider_subscription_id,
                local.account_id,
                exc,
            )
            continue
        plan_id = remote.plan_id
        if plan_id not in PLANS:
            logger.warning(
                "subscription %s (account %s) is on unknown plan %r; keeping plan %r",
                local.provider_subscription_id,
                local.account_id,
                plan_id,
                local.plan_id,
            )
            plan_id = local.plan_id
        checked += 1
        updated = replace(
            local,
            status=remote.status,
            plan_id=plan_id,
            current_period_end=remote.current_period_end,
        )
        if updated != local:
            save_subscription(conn, updated, now)
            changed += 1
    if failed and not checked:
        # Nothing could be refreshed: fail the run so it is retried and visible
        # in the job's last_error instead of silently reporting success.
        raise ProviderError(f"could not reconcile any of {failed} subscriptions")
    return ReconcileResult(checked=checked, changed=changed, failed=failed)


def schedule_next_reconcile(conn: sqlite3.Connection, now: datetime, settings: Settings) -> int:
    """Enqueue the next reconciliation ``reconcile_interval_minutes`` from now."""
    run_at = now + timedelta(minutes=settings.reconcile_interval_minutes)
    return enqueue(conn, RECONCILE_JOB, {}, run_at, now)


def ensure_reconcile_scheduled(
    conn: sqlite3.Connection,
    now: datetime,
    settings: Settings,
) -> int | None:
    """Enqueue a reconciliation unless one is already pending.

    Returns the id of the newly enqueued job, or None if a pending one
    (including one waiting for a retry) already exists. Running jobs are not
    counted: when called from the reconcile handler, the running job is the
    current run, which is about to finish.
    """
    pending = conn.execute(
        "SELECT 1 FROM jobs WHERE kind = ? AND status = 'pending' LIMIT 1",
        (RECONCILE_JOB,),
    ).fetchone()
    if pending is not None:
        return None
    return schedule_next_reconcile(conn, now, settings)


def make_reconcile_handler(provider: PaymentProvider, settings: Settings) -> Handler:
    """Build the handler for :data:`RECONCILE_JOB`.

    It reconciles all subscriptions and, on success, schedules the next run.
    """

    def handle(conn: sqlite3.Connection, payload: dict, now: datetime) -> None:
        reconcile_subscriptions(conn, provider, now)
        ensure_reconcile_scheduled(conn, now, settings)

    return handle


def run_worker_pass(
    conn: sqlite3.Connection,
    handlers: dict[str, Handler],
    now: datetime,
    settings: Settings,
) -> int:
    """One pass of the background worker; returns the number of jobs processed.

    Makes sure subscription polling is scheduled (a reconcile job that died
    after :data:`MAX_ATTEMPTS` is replaced by a fresh one), then runs every
    due job.
    """
    ensure_reconcile_scheduled(conn, now, settings)
    return run_due_jobs(conn, handlers, now)
