from datetime import timedelta

import pytest

from tasklane.auth import register_user
from tasklane.billing import Subscription, entitlements_for, get_subscription, save_subscription
from tasklane.config import load_settings
from tasklane.plans import PLANS, get_plan
from tasklane.projects import create_account


def make_subscription(now, status="active", plan_id="pro", created_at=None, account_id=1):
    return Subscription(
        account_id=account_id,
        plan_id=plan_id,
        status=status,
        provider_subscription_id=f"sub_{account_id:04d}",
        provider_customer_id=f"cus_{account_id:04d}",
        current_period_end=now + timedelta(days=30),
        created_at=created_at if created_at is not None else now - timedelta(days=3),
    )


# -- plans -----------------------------------------------------------------


def test_plan_catalogue():
    assert set(PLANS) == {"free", "pro", "team"}
    for plan_id, plan in PLANS.items():
        assert plan.plan_id == plan_id
        assert get_plan(plan_id) is plan
    assert PLANS["free"].monthly_price_cents == 0
    assert PLANS["free"].max_projects == 3
    assert PLANS["free"].max_seats == 1
    assert PLANS["pro"].monthly_price_cents == 1200
    assert PLANS["pro"].max_projects is None
    assert PLANS["team"].max_seats == 50


def test_unknown_plan():
    with pytest.raises(ValueError, match="unknown plan"):
        get_plan("enterprise")


# -- entitlements ----------------------------------------------------------


def test_no_subscription_is_free(now, settings):
    ent = entitlements_for(None, now, settings)
    assert ent.plan_id == "free"
    assert ent.max_projects == 3
    assert ent.max_seats == 1
    assert ent.reason == "no_subscription"


@pytest.mark.parametrize("status", ["active", "trialing", "past_due"])
def test_entitled_statuses_grant_plan(now, settings, status):
    ent = entitlements_for(make_subscription(now, status=status, plan_id="team"), now, settings)
    assert ent.plan_id == "team"
    assert ent.max_projects is None
    assert ent.max_seats == 50
    assert ent.reason == f"status:{status}"


@pytest.mark.parametrize("age_minutes", [0, 10, 30])
def test_incomplete_within_checkout_grace_grants_plan(now, settings, age_minutes):
    created_at = now - timedelta(minutes=age_minutes)
    sub = make_subscription(now, status="incomplete", created_at=created_at)
    ent = entitlements_for(sub, now, settings)
    assert ent.plan_id == "pro"
    assert ent.reason == "checkout_grace"


def test_incomplete_after_checkout_grace_is_free(now, settings):
    sub = make_subscription(now, status="incomplete", created_at=now - timedelta(minutes=31))
    ent = entitlements_for(sub, now, settings)
    assert ent.plan_id == "free"
    assert ent.reason == "status:incomplete"


def test_checkout_grace_follows_settings(now, settings):
    short_grace = load_settings(checkout_grace_minutes=5, pbkdf2_iterations=1_000)
    sub = make_subscription(now, status="incomplete", created_at=now - timedelta(minutes=10))
    assert entitlements_for(sub, now, settings).plan_id == "pro"
    assert entitlements_for(sub, now, short_grace).plan_id == "free"


def test_default_settings_are_used_when_none_given(now):
    within = make_subscription(now, status="incomplete", created_at=now - timedelta(minutes=30))
    after = make_subscription(now, status="incomplete", created_at=now - timedelta(minutes=31))
    assert entitlements_for(within, now).reason == "checkout_grace"
    assert entitlements_for(after, now).reason == "status:incomplete"


@pytest.mark.parametrize("status", ["canceled", "unpaid"])
def test_lapsed_statuses_fall_back_to_free(now, settings, status):
    ent = entitlements_for(make_subscription(now, status=status), now, settings)
    assert ent.plan_id == "free"
    assert ent.max_projects == 3
    assert ent.reason == f"status:{status}"


# -- persistence -----------------------------------------------------------


@pytest.fixture
def account_id(conn, settings, now):
    user_id = register_user(conn, "owner@example.com", "s3cret-pass", settings, now)
    return create_account(conn, "Acme", user_id, now)


def test_save_and_get_subscription(conn, now, account_id):
    sub = make_subscription(now, account_id=account_id)
    save_subscription(conn, sub, now)
    assert get_subscription(conn, account_id) == sub


def test_save_subscription_upserts(conn, now, account_id):
    save_subscription(conn, make_subscription(now, account_id=account_id), now)
    later = now + timedelta(hours=1)
    changed = make_subscription(now, account_id=account_id, status="past_due", plan_id="team")
    save_subscription(conn, changed, later)

    assert get_subscription(conn, account_id) == changed
    row = conn.execute("SELECT COUNT(*) AS n, MAX(updated_at) AS u FROM subscriptions").fetchone()
    assert row["n"] == 1
    assert row["u"] == "2026-01-05T13:00:00+00:00"


def test_save_subscription_rejects_unknown_plan(conn, now, account_id):
    with pytest.raises(ValueError, match="unknown plan"):
        save_subscription(conn, make_subscription(now, account_id=account_id, plan_id="gold"), now)
    assert get_subscription(conn, account_id) is None


def test_get_missing_subscription(conn):
    assert get_subscription(conn, 12345) is None
