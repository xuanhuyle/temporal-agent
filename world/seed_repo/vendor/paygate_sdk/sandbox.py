"""In-memory sandbox backend for local development and tests.

``SandboxBackend`` implements the subset of the PayGate REST API that the SDK
calls, entirely in memory. Object ids are sequential (``cus_0001``,
``sub_0001``, ``in_0001``, ...) and timestamps come from the sandbox clock
(``backend.now``, epoch seconds), so runs are fully reproducible.

Pass it to the client to use it instead of the network::

    backend = SandboxBackend()
    customer = backend.create_customer("ada@example.com")
    backend.create_subscription(customer["id"], "pro")
    client = PayGateClient("sk_test_sandbox", backend=backend)

The ``create_*`` and ``set_*`` helpers configure sandbox state directly and
are not API calls; only :meth:`SandboxBackend.request` is.
"""

import copy

from .errors import InvalidRequest, NotFound, PayGateError, ServiceUnavailable

SUBSCRIPTION_STATUSES = (
    "incomplete",
    "trialing",
    "active",
    "past_due",
    "canceled",
    "unpaid",
)

INVOICE_STATUSES = ("draft", "open", "paid", "uncollectible", "void")

DEFAULT_PERIOD_SECONDS = 30 * 24 * 60 * 60

# 2025-01-01T00:00:00Z
DEFAULT_SANDBOX_TIME = 1735689600

_INJECTABLE_ERRORS = {
    "service_unavailable": ServiceUnavailable,
    "invalid_request": InvalidRequest,
    "not_found": NotFound,
    "api_error": PayGateError,
}


class SandboxBackend:
    """Deterministic in-memory stand-in for the PayGate API."""

    def __init__(self, now=DEFAULT_SANDBOX_TIME):
        self.now = int(now)
        self.requests = []
        self._customers = {}
        self._subscriptions = {}
        self._invoices = {}
        self._counters = {"cus": 0, "sub": 0, "in": 0}
        self._failures_remaining = 0
        self._failure_error = "service_unavailable"

    # -- sandbox configuration ------------------------------------------------

    def advance(self, seconds):
        """Move the sandbox clock forward."""
        self.now += int(seconds)

    def fail_next(self, n, error="service_unavailable"):
        """Make the next ``n`` API calls fail with ``error``."""
        if error not in _INJECTABLE_ERRORS:
            raise ValueError("unknown sandbox error: %r" % (error,))
        self._failures_remaining = int(n)
        self._failure_error = error

    def create_customer(self, email):
        customer = {
            "id": self._next_id("cus"),
            "object": "customer",
            "email": email,
        }
        self._customers[customer["id"]] = customer
        return copy.deepcopy(customer)

    def create_subscription(
        self,
        customer_id,
        plan,
        status="active",
        current_period_end=None,
        created=None,
    ):
        self._require_customer(customer_id)
        self._require_status(status)
        created = self.now if created is None else int(created)
        if current_period_end is None:
            current_period_end = created + DEFAULT_PERIOD_SECONDS
        subscription = {
            "id": self._next_id("sub"),
            "object": "subscription",
            "customer": customer_id,
            "plan": plan,
            "status": status,
            "current_period_end": int(current_period_end),
            "created": created,
        }
        self._subscriptions[subscription["id"]] = subscription
        return copy.deepcopy(subscription)

    def set_subscription_status(self, subscription_id, status):
        self._require_status(status)
        subscription = self._get(self._subscriptions, subscription_id, "subscription")
        subscription["status"] = status
        return copy.deepcopy(subscription)

    def create_invoice(self, customer_id, amount_cents, status="paid", created=None):
        self._require_customer(customer_id)
        if status not in INVOICE_STATUSES:
            raise InvalidRequest("invalid invoice status: %r" % (status,))
        invoice = {
            "id": self._next_id("in"),
            "object": "invoice",
            "customer": customer_id,
            "amount_due": int(amount_cents),
            "status": status,
            "created": self.now if created is None else int(created),
        }
        self._invoices[invoice["id"]] = invoice
        return copy.deepcopy(invoice)

    # -- API ------------------------------------------------------------------

    def request(self, method, path, params=None):
        """Handle one API request and return the decoded JSON body."""
        params = dict(params or {})
        self.requests.append((method, path, params))

        if self._failures_remaining > 0:
            self._failures_remaining -= 1
            error_cls = _INJECTABLE_ERRORS[self._failure_error]
            raise error_cls("sandbox: injected %s" % self._failure_error)

        if method != "GET":
            raise InvalidRequest("unsupported method: %s %s" % (method, path))

        segments = [s for s in path.split("/") if s]
        if segments == ["subscriptions"]:
            return self._list(self._subscriptions, params)
        if len(segments) == 2 and segments[0] == "subscriptions":
            return copy.deepcopy(self._get(self._subscriptions, segments[1], "subscription"))
        if segments == ["invoices"]:
            return self._list(self._invoices, params)
        if len(segments) == 2 and segments[0] == "invoices":
            return copy.deepcopy(self._get(self._invoices, segments[1], "invoice"))
        raise NotFound("unrecognized request URL: %s %s" % (method, path))

    # -- helpers --------------------------------------------------------------

    def _next_id(self, prefix):
        self._counters[prefix] += 1
        return "%s_%04d" % (prefix, self._counters[prefix])

    def _require_customer(self, customer_id):
        self._get(self._customers, customer_id, "customer")

    def _require_status(self, status):
        if status not in SUBSCRIPTION_STATUSES:
            raise InvalidRequest("invalid subscription status: %r" % (status,))

    @staticmethod
    def _get(store, object_id, kind):
        try:
            return store[object_id]
        except KeyError:
            raise NotFound("no such %s: %s" % (kind, object_id)) from None

    @staticmethod
    def _list(store, params):
        customer = params.get("customer")
        if not customer:
            raise InvalidRequest("missing required parameter: customer")
        return [
            copy.deepcopy(obj)
            for _, obj in sorted(store.items())
            if obj["customer"] == customer
        ]
