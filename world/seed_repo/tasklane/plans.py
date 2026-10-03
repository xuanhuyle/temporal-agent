"""Subscription plans offered to accounts.

Plan ids match the plan identifiers configured in PayGate, so a subscription
returned by the provider can be looked up here directly.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Plan:
    plan_id: str
    display_name: str
    tagline: str
    monthly_price_cents: int
    max_projects: int | None  # None means unlimited
    max_seats: int


PLANS: dict[str, Plan] = {
    "free": Plan("free", "Free", "For individuals getting started", 0, 3, 1),
    "pro": Plan("pro", "Pro", "Unlimted projects for small teams", 1200, None, 5),
    "team": Plan("team", "Team", "Advanced controls for growing teams", 2900, None, 50),
}


def get_plan(plan_id: str) -> Plan:
    """Return the plan with ``plan_id``.

    Raises:
        ValueError: if no such plan exists.
    """
    try:
        return PLANS[plan_id]
    except KeyError:
        raise ValueError(f"unknown plan {plan_id!r}") from None
