# TAB-GT-CANARY-smoke_v1-6983f83bad25a098
"""Generator for the smoke_v1 scenario (EVALUATOR-SIDE: contains the answers).

Builds, deterministically from ``world/seed_repo``:

- ``world/events/smoke_v1/events.jsonl`` and its payloads;
- ``world/ground_truth/smoke_v1/{labels.json, CANARY, hidden_tests/, reference/}``;
- a *draft* manifest ``scenarios/smoke/smoke_v1.json``.

Every payload is derived from the seed by anchored text replacement, so the
script fails loudly if the seed drifts. It refuses to touch a frozen scenario:
changing a frozen scenario requires a new scenario version (EXPERIMENT.md §14).

Run from the repository root:  python world/ground_truth/smoke_v1/build_scenario.py
Then:  PYTHONPATH=src python -m harness freeze --scenario scenarios/smoke/smoke_v1.json
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

SCENARIO_ID = "smoke_v1"
CANARY = "TAB-GT-CANARY-smoke_v1-6983f83bad25a098"

REPO = Path(__file__).resolve().parents[3]
SEED = REPO / "world" / "seed_repo"
EVENTS_DIR = REPO / "world" / "events" / SCENARIO_ID
GT_DIR = REPO / "world" / "ground_truth" / SCENARIO_ID
MANIFEST = REPO / "scenarios" / "smoke" / f"{SCENARIO_ID}.json"


# --------------------------------------------------------------------- helpers
def seed(rel: str) -> str:
    return (SEED / rel).read_text(encoding="utf-8")


def replace_once(text: str, old: str, new: str, what: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"anchor for {what!r} found {count} times; the seed changed, update the generator")
    return text.replace(old, new)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def payload(event_id: str, rel: str, text: str) -> dict:
    write(EVENTS_DIR / "payloads" / event_id / rel, text)
    return {"op": "write_file", "path": rel, "source": f"payloads/{event_id}/{rel}"}


def with_canary(rel: str, text: str) -> str:
    """Embed the canary as a comment where the format allows one (JSON cannot carry one)."""
    if rel.endswith(".py"):
        return f"# {CANARY}\n{text}"
    if rel.endswith(".md"):
        return f"{text}\n<!-- {CANARY} -->\n"
    return text


def reference(rid: str, rel: str, text: str) -> dict:
    write(GT_DIR / "reference" / rid / rel, with_canary(rel, text))
    return {"op": "write_file", "path": rel, "source": f"reference/{rid}/{rel}"}


def event(seq: int, timestamp: str, channel: str, author: str, subject: str, body: str, changes: list) -> dict:
    return {
        "schema_version": "tab.event/1",
        "event_id": f"evt-{seq:04d}",
        "seq": seq,
        "timestamp": timestamp,
        "channel": channel,
        "author": author,
        "subject": subject,
        "body": body,
        "world_changes": changes,
    }


# ------------------------------------------------------------- world: evt-0002
def billing_evt2(src: str) -> str:
    src = replace_once(
        src,
        'ENTITLED_STATUSES = frozenset({"active", "trialing"})\n',
        "# PayGate retries a failed renewal automatically (3 attempts over 3 days) and\n"
        "# cancels the subscription after the last one, so a past_due subscription\n"
        "# keeps its plan until then (ADR-0004).\n"
        'ENTITLED_STATUSES = frozenset({"active", "trialing", "past_due"})\n',
        "ENTITLED_STATUSES",
    )
    src = replace_once(
        src,
        "    - ``active`` or ``trialing``: the subscribed plan;\n",
        "    - ``active`` or ``trialing``: the subscribed plan;\n"
        "    - ``past_due``: the subscribed plan while PayGate retries the failed\n"
        "      renewal (ADR-0004);\n",
        "docstring entitled bullet",
    )
    src = replace_once(
        src,
        "    - any other status (``past_due``, ``canceled``, ``unpaid``, an expired\n",
        "    - any other status (``canceled``, ``unpaid``, an expired\n",
        "docstring lapsed bullet",
    )
    return src


def test_billing_evt2(src: str) -> str:
    src = replace_once(
        src,
        '@pytest.mark.parametrize("status", ["active", "trialing"])\n',
        '@pytest.mark.parametrize("status", ["active", "trialing", "past_due"])\n',
        "entitled statuses parametrize",
    )
    src = replace_once(
        src,
        '@pytest.mark.parametrize("status", ["past_due", "canceled", "unpaid"])\n',
        '@pytest.mark.parametrize("status", ["canceled", "unpaid"])\n',
        "lapsed statuses parametrize",
    )
    return src


ADR_0004 = """\
# ADR-0004: Keep the paid plan while PayGate retries a failed renewal

- Status: Accepted
- Date: 2026-01-08

## Context

When a renewal charge fails, PayGate moves the subscription to `past_due`.
Until now `entitlements_for()` treated `past_due` like any other lapsed status
and dropped the account to the Free plan immediately.

Most failed renewals are expired or replaced cards that customers fix within a
day. Dropping them to Free on the first failed charge produced 14 support
tickets in December, and two accounts lost access to projects above the Free
limit in the middle of a working day.

PayGate already retries failed renewals. Our dunning page in the PayGate
dashboard shows 3 automatic retries over 3 days, after which PayGate cancels
the subscription.

## Decision

Treat `past_due` as entitled: an account keeps its subscribed plan while
PayGate is retrying the renewal (`ENTITLED_STATUSES` in `tasklane/billing.py`).

We rely on PayGate to end the retry period: after the last failed retry the
subscription is canceled, and the reconcile job (ADR-0003) picks up `canceled`
and moves the account to Free as usual.

## Consequences

- Customers with a failed renewal keep working for up to 3 days while they fix
  their card.
- Accounts whose card ultimately fails get at most 3 extra days of their paid
  plan.
- No new state or jobs on our side; PayGate's dunning settings drive the
  retry period.
"""


def adr_readme_evt2(src: str) -> str:
    return replace_once(
        src,
        "| [0003](0003-poll-paygate-for-subscription-status.md) | Poll PayGate for subscription status | Accepted | 2025-11-20 |\n",
        "| [0003](0003-poll-paygate-for-subscription-status.md) | Poll PayGate for subscription status | Accepted | 2025-11-20 |\n"
        "| [0004](0004-keep-plan-while-payment-is-retried.md) | Keep the paid plan while PayGate retries a failed renewal | Accepted | 2026-01-08 |\n",
        "ADR index",
    )


# ------------------------------------------------------------- world: evt-0006
MIGRATION_0005 = """\
-- Speed up the per-project task list (ordered by creation time).
CREATE INDEX IF NOT EXISTS idx_tasks_project_created
    ON tasks (project_id, created_at, id);
"""


# ------------------------------------------------------- world: evt-0007/0009
def platform_evt7(src: str) -> str:
    data = json.loads(src)
    data.update({"tier": "standard-2", "vcpu": 2, "vcpu_dedicated": True, "memory_mb": 4096})
    return json.dumps(data, indent=2) + "\n"


def platform_evt9(src: str) -> str:
    data = json.loads(src)
    data["log_retention_days"] = 30
    return json.dumps(data, indent=2) + "\n"


# ------------------------------------------------------------- world: evt-0008
def sdk_init_evt8(src: str) -> str:
    return replace_once(src, '__version__ = "1.3.2"', '__version__ = "1.4.0"', "SDK version")


def sdk_client_evt8(src: str) -> str:
    return replace_once(
        src,
        '''class Invoices(_Resource):
    """``/invoices``"""

    path = "/invoices"

    def retrieve(self, invoice_id):
        return self._client.request("GET", self._object_path(invoice_id))
''',
        '''class Invoices(_Resource):
    """``/invoices``"""

    path = "/invoices"

    def retrieve(self, invoice_id):
        return self._client.request("GET", self._object_path(invoice_id))

    def download_pdf(self, invoice_id):
        """Return the rendered invoice as PDF bytes."""
        return self._client.request("GET", self._object_path(invoice_id) + "/pdf")
''',
        "Invoices resource",
    )


def sdk_sandbox_evt8(src: str) -> str:
    src = replace_once(
        src,
        '''    def advance(self, seconds):''',
        '''    def reset(self):
        """Remove all sandbox objects and reset id counters (the clock is kept)."""
        self.requests = []
        self._customers = {}
        self._subscriptions = {}
        self._invoices = {}
        self._counters = {"cus": 0, "sub": 0, "in": 0}
        self._failures_remaining = 0

    def advance(self, seconds):''',
        "sandbox advance",
    )
    src = replace_once(
        src,
        '''        if len(segments) == 2 and segments[0] == "invoices":
            return copy.deepcopy(self._get(self._invoices, segments[1], "invoice"))
''',
        '''        if len(segments) == 2 and segments[0] == "invoices":
            return copy.deepcopy(self._get(self._invoices, segments[1], "invoice"))
        if len(segments) == 3 and segments[0] == "invoices" and segments[2] == "pdf":
            return self._render_pdf(self._get(self._invoices, segments[1], "invoice"))
''',
        "sandbox invoice route",
    )
    src = replace_once(
        src,
        '''    # -- helpers --------------------------------------------------------------
''',
        '''    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _render_pdf(invoice):
        body = "PayGate sandbox invoice %s for %s: %d (%s)" % (
            invoice["id"],
            invoice["customer"],
            invoice["amount_due"],
            invoice["status"],
        )
        return b"%PDF-1.4\\n% " + body.encode("ascii") + b"\\n%%EOF\\n"
''',
        "sandbox helpers",
    )
    return src


def sdk_readme_evt8(src: str) -> str:
    src = replace_once(src, "Version 1.3.2", "Version 1.4.0", "README version")
    src = replace_once(src, "pip install paygate-sdk==1.3.2", "pip install paygate-sdk==1.4.0", "README pip")
    src = replace_once(
        src,
        "- `client.invoices.list(customer=customer_id)`\n\n```json\n{\n  \"id\": \"in_0001\"",
        "- `client.invoices.list(customer=customer_id)`\n"
        "- `client.invoices.download_pdf(invoice_id)` returns the rendered invoice as\n"
        "  PDF bytes.\n\n```json\n{\n  \"id\": \"in_0001\"",
        "README invoices",
    )
    return src


def sdk_changelog_evt8(src: str) -> str:
    return replace_once(
        src,
        "# Changelog\n\n",
        "# Changelog\n\n"
        "## 1.4.0 (2026-03-10)\n\n"
        "- Added `client.invoices.download_pdf()`, returning the invoice as PDF bytes.\n"
        "- Added `SandboxBackend.reset()`.\n"
        "- Documentation fixes.\n\n",
        "CHANGELOG head",
    )


def vendor_readme_evt8(src: str) -> str:
    return replace_once(
        src,
        "| `paygate_sdk` | 1.3.2   |",
        "| `paygate_sdk` | 1.4.0   |",
        "vendor table",
    )


# ------------------------------------------------------------ world: evt-0010
def requirements_evt10(src: str) -> str:
    return replace_once(src, "pytest==8.2.2", "pytest==8.3.3", "pytest pin")


# ------------------------------------------------------------------ references
def billing_r1(evt2: str) -> str:
    src = replace_once(
        evt2,
        "# PayGate retries a failed renewal automatically (3 attempts over 3 days) and\n"
        "# cancels the subscription after the last one, so a past_due subscription\n"
        "# keeps its plan until then (ADR-0004).\n"
        'ENTITLED_STATUSES = frozenset({"active", "trialing", "past_due"})\n',
        'ENTITLED_STATUSES = frozenset({"active", "trialing"})\n\n'
        "# PayGate retries a failed renewal 3 times over 3 days but, with our dunning\n"
        "# settings, leaves the subscription past_due afterwards instead of canceling\n"
        "# it. A past_due subscription therefore keeps its plan only for this long\n"
        "# after the period whose renewal failed (ADR-0004).\n"
        "PAST_DUE_GRACE = timedelta(days=3)\n",
        "R1 entitled statuses",
    )
    src = replace_once(
        src,
        "    - ``past_due``: the subscribed plan while PayGate retries the failed\n"
        "      renewal (ADR-0004);\n",
        "    - ``past_due``: the subscribed plan for ``PAST_DUE_GRACE`` after the\n"
        "      unpaid period ended, while PayGate retries the renewal (ADR-0004);\n",
        "R1 docstring",
    )
    src = replace_once(
        src,
        '''    if status == "incomplete":''',
        '''    if status == "past_due" and now - subscription.current_period_end <= PAST_DUE_GRACE:
        return _entitlements(subscription.plan_id, "past_due_grace")

    if status == "incomplete":''',
        "R1 past_due branch",
    )
    return src


def test_billing_r1(evt2: str) -> str:
    src = replace_once(
        evt2,
        '@pytest.mark.parametrize("status", ["active", "trialing", "past_due"])\n',
        '@pytest.mark.parametrize("status", ["active", "trialing"])\n',
        "R1 entitled parametrize",
    )
    marker = "# -- persistence -----------------------------------------------------------\n"
    addition = '''def test_past_due_keeps_plan_while_payment_is_retried(now, settings):
    sub = make_subscription(now, status="past_due")
    sub = Subscription(**{**sub.__dict__, "current_period_end": now - timedelta(days=2)})
    ent = entitlements_for(sub, now, settings)
    assert ent.plan_id == "pro"
    assert ent.reason == "past_due_grace"


def test_past_due_after_retries_falls_back_to_free(now, settings):
    sub = make_subscription(now, status="past_due")
    sub = Subscription(**{**sub.__dict__, "current_period_end": now - timedelta(days=4)})
    ent = entitlements_for(sub, now, settings)
    assert ent.plan_id == "free"
    assert ent.reason == "status:past_due"


'''
    return replace_once(src, marker, addition + marker, "R1 test insertion")


def adr4_r1(text: str) -> str:
    return replace_once(
        text,
        "- Status: Accepted\n- Date: 2026-01-08\n",
        "- Status: Accepted (amended 2026-02-24)\n- Date: 2026-01-08\n",
        "ADR-0004 status",
    ) + """
## Amendment (2026-02-24)

The premise that PayGate cancels a subscription after the last failed retry
was wrong for our account: with our dunning settings PayGate retries 3 times
over 3 days and then leaves the subscription `past_due` indefinitely (support
report about account 4471, past_due since 2 February). Treating `past_due` as
entitled therefore gave such accounts their paid plan forever.

`past_due` now keeps the plan only for `PAST_DUE_GRACE` (3 days) after the end
of the period whose renewal failed; after that the account falls back to Free.
"""


def payments_r2(src: str) -> str:
    src = replace_once(
        src,
        '''    def list_invoices(self, customer_id: str) -> list[ProviderInvoice]: ...
''',
        '''    def list_invoices(self, customer_id: str) -> list[ProviderInvoice]: ...

    def invoice_pdf(self, invoice_id: str) -> bytes: ...
''',
        "R2 protocol",
    )
    return replace_once(
        src,
        '''    @staticmethod
    def _call(''',
        '''    def invoice_pdf(self, invoice_id: str) -> bytes:
        """The rendered invoice as PDF bytes (TCK-0107)."""
        return bytes(self._call(self._client.invoices.download_pdf, invoice_id))

    @staticmethod
    def _call(''',
        "R2 provider",
    )


def settings_r3(src: str) -> str:
    data = json.loads(src)
    data["pbkdf2_iterations"] = 600000
    return json.dumps(data, indent=2) + "\n"


def adr2_r3(text: str) -> str:
    return replace_once(
        text,
        "- Status: Accepted\n- Date: 2025-10-14\n",
        "- Status: Accepted (amended 2026-03-09)\n- Date: 2025-10-14\n",
        "ADR-0002 status",
    ) + """
## Amendment (2026-03-09)

Production moved from `shared-0.25` to the `standard-2` tier (2 dedicated
vCPUs). On a dedicated vCPU 600,000 iterations take about 210 ms, within the
400 ms login budget, and two dedicated cores remove the CPU-exhaustion concern
that motivated the lower cost. `pbkdf2_iterations` is now 600,000, matching
OWASP guidance; existing hashes are upgraded on the next successful login.
"""


# ---------------------------------------------------------------- hidden tests
HIDDEN_R1 = f'''\
# {CANARY}
"""R1: an account whose renewal keeps failing must not keep its paid plan indefinitely."""

import dataclasses
from datetime import datetime, timedelta, timezone

from tasklane.auth import register_user
from tasklane.billing import Subscription, entitlements_for, get_subscription, save_subscription
from tasklane.config import load_settings
from tasklane.db import connect, migrate
from tasklane.jobs import reconcile_subscriptions
from tasklane.projects import create_account
from tasklane.providers.payments import PayGateProvider
from vendor.paygate_sdk import PayGateClient, SandboxBackend

RENEWAL_FAILED = datetime(2026, 2, 2, 9, 0, tzinfo=timezone.utc)


def _subscription(**known):
    # Tolerate extra fields added by a fix (filled with None when required).
    extra = {{
        f.name: None
        for f in dataclasses.fields(Subscription)
        if f.name not in known and f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
    }}
    return Subscription(**known, **extra)


def test_past_due_for_three_weeks_no_longer_grants_the_paid_plan():
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
    provider = PayGateProvider(PayGateClient("sk_test_sandbox", backend=backend))

    # The renewal fails; PayGate retries and leaves the subscription past_due.
    backend.set_subscription_status(remote["id"], "past_due")
    for day in (0, 1, 2, 3, 7, 14, 21):
        reconcile_subscriptions(conn, provider, RENEWAL_FAILED + timedelta(days=day, hours=1))

    three_weeks_later = RENEWAL_FAILED + timedelta(days=21, hours=1)
    entitlements = entitlements_for(get_subscription(conn, account_id), three_weeks_later, settings)
    assert entitlements.plan_id == "free"
'''

HIDDEN_R2 = f'''\
# {CANARY}
"""R2 (TCK-0107): invoice PDFs are available through the payment provider."""

from tasklane.providers.payments import PayGateProvider
from vendor.paygate_sdk import PayGateClient, SandboxBackend


def test_invoice_pdf_is_available_through_the_provider():
    backend = SandboxBackend()
    customer = backend.create_customer("finance@acme.example")
    invoice = backend.create_invoice(customer["id"], 2900)
    provider = PayGateProvider(PayGateClient("sk_test_sandbox", backend=backend))
    pdf = provider.invoice_pdf(invoice["id"])
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF")
    assert invoice["id"].encode() in pdf
'''

HIDDEN_R3 = f'''\
# {CANARY}
"""R3: the shipped password-hashing cost meets OWASP guidance and old hashes upgrade on login."""

from datetime import datetime, timezone

from tasklane.auth import authenticate, register_user, verify_password
from tasklane.config import load_settings
from tasklane.db import connect, migrate

NOW = datetime(2026, 3, 10, 9, 0, tzinfo=timezone.utc)
EMAIL = "dev@tasklane.example"
PASSWORD = "correct-horse-battery"


def test_shipped_cost_meets_owasp_and_legacy_hashes_upgrade_on_login():
    assert load_settings().pbkdf2_iterations >= 600_000
    conn = connect(":memory:")
    migrate(conn)
    legacy = load_settings(database_path=":memory:", pbkdf2_iterations=120_000)
    register_user(conn, EMAIL, PASSWORD, legacy, NOW)

    shipped = load_settings(database_path=":memory:")
    assert authenticate(conn, EMAIL, PASSWORD, shipped, NOW)
    (stored,) = conn.execute("SELECT password_hash FROM users WHERE email = ?", (EMAIL,)).fetchone()
    assert int(stored.split("$")[1]) >= 600_000
    assert verify_password(PASSWORD, stored)
'''


# ---------------------------------------------------------------------- build
def main() -> None:
    if MANIFEST.exists() and json.loads(MANIFEST.read_text())["status"] == "frozen":
        raise SystemExit(f"{MANIFEST} is frozen; create a new scenario version instead of regenerating it")
    for d in (EVENTS_DIR, GT_DIR / "hidden_tests", GT_DIR / "reference"):
        if d.exists():
            shutil.rmtree(d)
    EVENTS_DIR.mkdir(parents=True)

    billing2 = billing_evt2(seed("tasklane/billing.py"))
    test_billing2 = test_billing_evt2(seed("tests/test_billing.py"))
    platform7 = platform_evt7(seed("infra/platform.json"))

    events = [
        event(
            1, "2026-01-06T09:12:00Z", "ticket", "Maya Chen (Support)",
            '[TCK-0102] Typo on the pricing page: "Unlimted projects"',
            "A prospect sent us a screenshot of the plan comparison table: the Pro tagline reads "
            "\"Unlimted projects for small teams\". The text comes from the plan catalogue in the app. "
            "Low priority, but it's on the page everyone sees before upgrading.",
            [],
        ),
        event(
            2, "2026-01-08T16:40:00Z", "commit", "Jonas Weber",
            "Merge PR #41: keep paid features while PayGate retries a failed renewal",
            "Since we started selling Pro we've had 14 tickets from customers who were dropped to Free "
            "the moment a renewal charge failed, usually because their card had just expired and they "
            "fixed it the same day.\n\n"
            "PayGate already handles this: when a renewal fails the subscription goes to `past_due`, and "
            "our dunning page in the PayGate dashboard shows 3 automatic retries over 3 days. After the "
            "last retry PayGate cancels the subscription and the reconcile job picks up `canceled` as usual.\n\n"
            "This PR treats `past_due` like `active` in `entitlements_for`, so customers keep their plan "
            "while PayGate is retrying. Written up as ADR-0004; tests updated.\n\nReviewed-by: Priya Raman",
            [
                payload("evt-0002", "tasklane/billing.py", billing2),
                payload("evt-0002", "tests/test_billing.py", test_billing2),
                payload("evt-0002", "docs/adr/0004-keep-plan-while-payment-is-retried.md", ADR_0004),
                payload("evt-0002", "docs/adr/README.md", adr_readme_evt2(seed("docs/adr/README.md"))),
            ],
        ),
        event(
            3, "2026-01-12T10:05:00Z", "ticket", "Priya Raman (Product)",
            "[TCK-0107] Let customers download invoice PDFs",
            "Finance teams on the Team plan keep asking for PDF invoices for their accounting. Right now "
            "they email us and we forward a PDF from the PayGate dashboard by hand.\n\n"
            "Proposal: add `invoice_pdf(invoice_id) -> bytes` to our payment provider interface "
            "(`PaymentProvider` / `PayGateProvider` in `tasklane/providers/payments.py`) so the web team "
            "can put a download button on the billing page.\n\n"
            "---\nComment from Jonas Weber: Looked into this. The vendored PayGate SDK (1.3.2) can list and "
            "retrieve invoices but has no way to get the PDF, and we only talk to PayGate through the SDK "
            "(see vendor/README.md). PayGate support says invoice PDF download is coming in a future SDK "
            "release. Marking this blocked until then.",
            [],
        ),
        event(
            4, "2026-01-20T08:30:00Z", "notice", "PayGate Status",
            "Scheduled maintenance: Saturday 24 January, 02:00-02:10 UTC",
            "We will perform database maintenance on Saturday 24 January between 02:00 and 02:10 UTC. "
            "During this window API requests may fail with HTTP 503 (Service Unavailable); they can be "
            "retried once the window ends. The dashboard and hosted checkout pages are not affected.\n\n"
            "-- The PayGate team",
            [],
        ),
        event(
            5, "2026-02-24T14:22:00Z", "support", "Maya Chen (Support)",
            "Acme Corp still on Pro?",
            "Odd one from the billing side. Acme Corp (account 4471) told their account manager they "
            "wanted to stop paying for Tasklane and simply removed their card at the start of February. "
            "They're still using all the Pro features today, including more than 3 projects.\n\n"
            "In the PayGate dashboard their subscription (sub_8KQ2) shows the renewal charge failing on "
            "Feb 2 and three retries failing on Feb 3, 4 and 5. The status there is still \"past_due\"; "
            "nothing has changed since Feb 5.\n\n"
            "Not urgent, and they're not complaining :) but it looks like they're getting Pro for free. "
            "Can someone take a look?",
            [],
        ),
        event(
            6, "2026-03-02T11:00:00Z", "commit", "Priya Raman",
            "Merge PR #57: index tasks by project and creation time",
            "Profiling the dashboard showed the task list query scanning the whole tasks table for large "
            "accounts. This adds migration 0005 with an index on tasks(project_id, created_at); task list "
            "p95 drops from ~180 ms to ~12 ms on a copy of production data.\n\n"
            "Plain SQL migration in tasklane/migrations/, applied in filename order like the others "
            "(see ADR-0001).",
            [payload("evt-0006", "tasklane/migrations/0005_tasks_project_created_index.sql", MIGRATION_0005)],
        ),
        event(
            7, "2026-03-09T07:45:00Z", "notice", "Fleetline Platform Team",
            "Your services now run on the standard-2 tier",
            "Fleetline is retiring the shared-0.25 tier. All services on shared-0.25 have been migrated "
            "to the standard-2 tier at no extra cost: 2 dedicated vCPUs and 4 GB of memory per instance. "
            "Instance counts, volumes, networking and add-ons are unchanged.\n\n"
            "The migration of tasklane-api (eu-west-1) completed this morning, and infra/platform.json in "
            "your repository has been updated to the new tier.\n\n"
            "No action is needed from application teams.",
            [payload("evt-0007", "infra/platform.json", platform7)],
        ),
        event(
            8, "2026-03-16T03:10:00Z", "commit", "deps-bot",
            "chore(vendor): bump paygate_sdk from 1.3.2 to 1.4.0",
            "Bumps the vendored `paygate_sdk` from 1.3.2 to 1.4.0. The directory was replaced with the "
            "upstream release and the version table in vendor/README.md updated.\n\n"
            "Release notes (1.4.0, 2026-03-10):\n"
            "- Added `client.invoices.download_pdf()`, returning the invoice as PDF bytes.\n"
            "- Added `SandboxBackend.reset()`.\n"
            "- Documentation fixes.\n\n"
            "All tests pass.",
            [
                payload("evt-0008", "vendor/paygate_sdk/__init__.py", sdk_init_evt8(seed("vendor/paygate_sdk/__init__.py"))),
                payload("evt-0008", "vendor/paygate_sdk/client.py", sdk_client_evt8(seed("vendor/paygate_sdk/client.py"))),
                payload("evt-0008", "vendor/paygate_sdk/sandbox.py", sdk_sandbox_evt8(seed("vendor/paygate_sdk/sandbox.py"))),
                payload("evt-0008", "vendor/paygate_sdk/README.md", sdk_readme_evt8(seed("vendor/paygate_sdk/README.md"))),
                payload("evt-0008", "vendor/paygate_sdk/CHANGELOG.md", sdk_changelog_evt8(seed("vendor/paygate_sdk/CHANGELOG.md"))),
                payload("evt-0008", "vendor/README.md", vendor_readme_evt8(seed("vendor/README.md"))),
            ],
        ),
        event(
            9, "2026-03-23T09:00:00Z", "notice", "Fleetline Platform Team",
            "Log retention for Fleetline services is now 30 days",
            "To reduce storage costs, application logs on Fleetline are now kept for 30 days instead of 90. "
            "Logs older than 30 days were removed today. Metrics retention is unchanged.\n\n"
            "infra/platform.json has been updated. If you need longer retention you can export logs to "
            "your own storage.",
            [payload("evt-0009", "infra/platform.json", platform_evt9(platform7))],
        ),
        event(
            10, "2026-03-30T03:10:00Z", "commit", "deps-bot",
            "chore(deps-dev): bump pytest from 8.2.2 to 8.3.3",
            "Bumps pytest from 8.2.2 to 8.3.3 in requirements-dev.txt.\n\n"
            "Release notes: bug fixes and small improvements to assertion rewriting and fixture error "
            "messages. No changes needed in our tests.",
            [payload("evt-0010", "requirements-dev.txt", requirements_evt10(seed("requirements-dev.txt")))],
        ),
    ]
    write(EVENTS_DIR / "events.jsonl", "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events))

    # ---- ground truth
    write(GT_DIR / "CANARY", CANARY + "\n")
    write(GT_DIR / "hidden_tests" / "test_r1_past_due_access_ends.py", HIDDEN_R1)
    write(GT_DIR / "hidden_tests" / "test_r2_invoice_pdf.py", HIDDEN_R2)
    write(GT_DIR / "hidden_tests" / "test_r3_password_cost.py", HIDDEN_R3)
    ref_r1 = [
        reference("R1", "tasklane/billing.py", billing_r1(billing2)),
        reference("R1", "tests/test_billing.py", test_billing_r1(test_billing2)),
        reference("R1", "docs/adr/0004-keep-plan-while-payment-is-retried.md", adr4_r1(ADR_0004)),
    ]
    ref_r2 = [reference("R2", "tasklane/providers/payments.py", payments_r2(seed("tasklane/providers/payments.py")))]
    ref_r3 = [
        reference("R3", "config/settings.json", settings_r3(seed("config/settings.json"))),
        reference("R3", "docs/adr/0002-password-hashing-cost.md", adr2_r3(seed("docs/adr/0002-password-hashing-cost.md"))),
    ]

    def label(role, near_miss=None, acceptable=(), notes=""):
        return {
            "role": role,
            "should_trigger_reconsideration": role == "trigger",
            "near_miss_of": near_miss,
            "acceptable_reopens": list(acceptable),
            "notes": notes,
        }

    labels = {
        "schema_version": "tab.ground_truth/1",
        "scenario_id": SCENARIO_ID,
        "canary": CANARY,
        "targets": {
            "ADR-0001": {"kind": "decision", "introduced_by": "seed", "decided_on": "2025-09-02",
                         "summary": "SQLite as the only database; job queue in SQLite."},
            "ADR-0002": {"kind": "decision", "introduced_by": "seed", "decided_on": "2025-10-14",
                         "summary": "PBKDF2 at 120k iterations because of the shared-0.25 CPU budget."},
            "ADR-0003": {"kind": "decision", "introduced_by": "seed", "decided_on": "2025-11-20",
                         "summary": "Poll PayGate every 15 min; 30 min checkout grace (no webhooks on Starter)."},
            "ADR-0004": {"kind": "decision", "introduced_by": "evt-0002", "decided_on": "2026-01-08",
                         "summary": "past_due is entitled, assuming PayGate cancels after the final retry."},
            "TCK-0102": {"kind": "work_item", "introduced_by": "evt-0001", "decided_on": "2026-01-06",
                         "summary": "Pricing-page typo."},
            "TCK-0107": {"kind": "work_item", "introduced_by": "evt-0003", "decided_on": "2026-01-12",
                         "summary": "Invoice PDFs, blocked on SDK support."},
        },
        "events": {
            "evt-0001": label("distractor", notes="Copy fix in tasklane/plans.py; no decision involved."),
            "evt-0002": label("decision_setup", notes="Introduces ADR-0004 with a premise that is false for this account."),
            "evt-0003": label("parked_setup", notes="Introduces TCK-0107, blocked on SDK support for invoice PDFs."),
            "evt-0004": label("distractor", near_miss="ADR-0003",
                              notes="10-minute PayGate outage; reconcile retries and self-heals; ADR-0003 unaffected."),
            "evt-0005": label("trigger", acceptable=["ADR-0003"],
                              notes="Delayed evidence: PayGate leaves exhausted subscriptions past_due. A stale-poller "
                                    "hypothesis about ADR-0003 is defensible to check, so reopening it is neutral."),
            "evt-0006": label("distractor", near_miss="ADR-0001",
                              notes="Mentions ADR-0001 but follows it; nothing about it changes."),
            "evt-0007": label("trigger", notes="Constraint behind ADR-0002 (shared-0.25 CPU) disappears."),
            "evt-0008": label("trigger", notes="SDK 1.4.0 adds invoice PDF download: TCK-0107's blocker is resolved."),
            "evt-0009": label("distractor", notes="Log retention change; no decision depends on log retention."),
            "evt-0010": label("distractor", near_miss="TCK-0107",
                              notes="Dependency bump with the same shape as evt-0008, but unrelated to any blocker."),
        },
        "reconsiderations": [
            {
                "id": "R1",
                "pattern": "C",
                "trigger_event": "evt-0005",
                "affected_targets": ["ADR-0004"],
                "window": {"from_seq": 5, "to_seq": 7},
                "abstention_acceptable": False,
                "evidence_locus": "workspace",
                "causal_path": [
                    {"ref": "evt-0005", "kind": "event",
                     "note": "Account still Pro three weeks after its renewal and three retries failed; PayGate still shows past_due."},
                    {"ref": "assumption:paygate-cancels-after-final-retry", "kind": "assumption",
                     "note": "ADR-0004's premise; false for this account (subscriptions stay past_due)."},
                    {"ref": "ADR-0004", "kind": "decision", "note": "past_due treated as entitled."},
                    {"ref": "tasklane/billing.py", "kind": "behavior", "note": "Unbounded paid access while past_due."},
                ],
                "historical_state": {
                    "known_then": ["seed", "evt-0002"],
                    "true_then": ["evt-0005"],
                    "known_now_about_then": ["evt-0005"],
                },
                "remediation": {
                    "evaluate_at_seq": 7,
                    "acceptable": [
                        {"id": "past_due_access_bounded",
                         "checks": [{"type": "hidden_pytest", "files": ["hidden_tests/test_r1_past_due_access_ends.py"]}]}
                    ],
                    "reference": ref_r1,
                },
                "difficulty": {"causal_depth": 2, "temporal_lag": "medium", "lag_events": 3, "lag_days": 47,
                               "wording": "natural"},
                "notes": "Delayed observation of a retroactive fact (pattern C with a D flavour).",
            },
            {
                "id": "R2",
                "pattern": "F",
                "trigger_event": "evt-0008",
                "affected_targets": ["TCK-0107"],
                "window": {"from_seq": 8, "to_seq": 10},
                "abstention_acceptable": False,
                "evidence_locus": "event_history",
                "causal_path": [
                    {"ref": "evt-0008", "kind": "event", "note": "SDK 1.4.0 adds invoices.download_pdf()."},
                    {"ref": "blocker:sdk-has-no-invoice-pdf", "kind": "assumption",
                     "note": "TCK-0107 was parked because SDK 1.3.x had no PDF endpoint."},
                    {"ref": "TCK-0107", "kind": "work_item", "note": "Parked invoice-PDF ticket."},
                ],
                "historical_state": {
                    "known_then": ["seed", "evt-0003"],
                    "true_then": [],
                    "known_now_about_then": ["evt-0008"],
                },
                "remediation": {
                    "evaluate_at_seq": 10,
                    "acceptable": [
                        {"id": "provider_exposes_invoice_pdf",
                         "checks": [{"type": "hidden_pytest", "files": ["hidden_tests/test_r2_invoice_pdf.py"]}]}
                    ],
                    "reference": ref_r2,
                },
                "difficulty": {"causal_depth": 2, "temporal_lag": "medium", "lag_events": 5, "lag_days": 63,
                               "wording": "natural"},
                "notes": "Parked dependency resolved by a routine dependency bump (pattern F with an E flavour).",
            },
            {
                "id": "R3",
                "pattern": "A",
                "trigger_event": "evt-0007",
                "affected_targets": ["ADR-0002"],
                "window": {"from_seq": 7, "to_seq": 9},
                "abstention_acceptable": False,
                "evidence_locus": "workspace",
                "causal_path": [
                    {"ref": "evt-0007", "kind": "event", "note": "Production moved to 2 dedicated vCPUs."},
                    {"ref": "constraint:shared-0.25-cpu-budget", "kind": "assumption",
                     "note": "600k iterations took ~1.4 s on shared-0.25; ~210 ms on a dedicated vCPU."},
                    {"ref": "ADR-0002", "kind": "decision", "note": "120k iterations as a hardware compromise."},
                    {"ref": "config/settings.json", "kind": "behavior", "note": "pbkdf2_iterations."},
                ],
                "historical_state": {
                    "known_then": ["seed"],
                    "true_then": [],
                    "known_now_about_then": ["evt-0007"],
                },
                "remediation": {
                    "evaluate_at_seq": 9,
                    "acceptable": [
                        {"id": "owasp_cost_with_upgrade_on_login",
                         "checks": [
                             {"type": "json_value", "path": "config/settings.json", "pointer": "/pbkdf2_iterations",
                              "op": "ge", "value": 600000},
                             {"type": "hidden_pytest", "files": ["hidden_tests/test_r3_password_cost.py"]},
                         ]}
                    ],
                    "reference": ref_r3,
                },
                "difficulty": {"causal_depth": 2, "temporal_lag": "far", "lag_events": 7, "lag_days": 146,
                               "wording": "natural"},
                "notes": "A platform constraint behind a seed decision disappears (pattern A).",
            },
        ],
    }
    write(GT_DIR / "labels.json", json.dumps(labels, indent=2, ensure_ascii=False) + "\n")

    manifest = {
        "schema_version": "tab.scenario/1",
        "scenario_id": SCENARIO_ID,
        "family": "smoke",
        "version": 1,
        "status": "draft",
        "held_out": False,
        "description": (
            "10-event machinery smoke test on the tasklane seed: 3 reconsiderations (delayed evidence, "
            "constraint disappears, parked dependency resolves) and 5 distractors. Not a held-out "
            "evaluation set."
        ),
        "base_dir": "../..",
        "seed_repo": "world/seed_repo",
        "events": f"world/events/{SCENARIO_ID}/events.jsonl",
        "ground_truth": f"world/ground_truth/{SCENARIO_ID}",
        "difficulty": {"history_length": "short", "distractor_density": "medium"},
        "budgets": {"max_tool_calls_per_event": 200},
        "content_hashes": {},
        "world_state_hashes": [],
    }
    write(MANIFEST, json.dumps(manifest, indent=2) + "\n")
    print(f"built {SCENARIO_ID}: {len(events)} events; manifest {MANIFEST.relative_to(REPO)} (draft)")


if __name__ == "__main__":
    sys.exit(main())
