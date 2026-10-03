# TAB-GT-CANARY-smoke_v1-6983f83bad25a098
"""R1: past_due keeps the plan while PayGate retries, but not indefinitely."""

import dataclasses
from datetime import datetime, timedelta, timezone

from tasklane.auth import register_user
from tasklane.billing import Subscription, entitlements_for, get_subscription, save_subscription
from tasklane.config import load_settings
from tasklane.db import connect, migrate
from tasklane.jobs import make_reconcile_handler
from tasklane.projects import create_account
from tasklane.providers.payments import PayGateProvider
from vendor.paygate_sdk import PayGateClient, SandboxBackend

RENEWAL_FAILED = datetime(2026, 2, 2, 9, 0, tzinfo=timezone.utc)


def _subscription(**known):
    # Tolerate extra fields added by a fix (filled with None when required).
    extra = {
        f.name: None
        for f in dataclasses.fields(Subscription)
        if f.name not in known and f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
    }
    return Subscription(**known, **extra)


def test_past_due_keeps_plan_during_retries_but_not_for_three_weeks():
    settings = load_settings(pbkdf2_iterations=1_000, database_path=":memory:")
    conn = connect(":memory:")
    migrate(conn)
    start = RENEWAL_FAILED - timedelta(days=30)
    user_id = register_user(conn, "finance@acme.example", "correct-horse-1", settings, start)
    account_id = create_account(conn, "Acme Corp", user_id, start)

    backend = SandboxBackend(now=int(start.timestamp()))
    customer = backend.create_customer("finance@acme.example")
    remote = backend.create_subscription(
        customer["id"], "pro", status="active", current_period_end=int(RENEWAL_FAILED.timestamp())
    )
    save_subscription(
        conn,
        _subscription(
            account_id=account_id,
            plan_id="pro",
            status="active",
            provider_subscription_id=remote["id"],
            provider_customer_id=customer["id"],
            current_period_end=RENEWAL_FAILED,
            created_at=start,
        ),
        start,
    )
    reconcile = make_reconcile_handler(PayGateProvider(PayGateClient("sk_test_sandbox", backend=backend)), settings)

    # The renewal fails; PayGate retries and leaves the subscription past_due.
    backend.set_subscription_status(remote["id"], "past_due")
    reconcile(conn, {}, RENEWAL_FAILED + timedelta(hours=1))
    during_retries = RENEWAL_FAILED + timedelta(hours=2)
    assert entitlements_for(get_subscription(conn, account_id), during_retries, settings).plan_id == "pro"

    for day in (1, 2, 3, 7, 14, 21):
        reconcile(conn, {}, RENEWAL_FAILED + timedelta(days=day, hours=1))
    three_weeks_later = RENEWAL_FAILED + timedelta(days=21, hours=2)
    assert entitlements_for(get_subscription(conn, account_id), three_weeks_later, settings).plan_id == "free"
