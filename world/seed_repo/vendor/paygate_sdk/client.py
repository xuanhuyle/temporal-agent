"""PayGate API client."""

from .errors import InvalidRequest, PayGateError

DEFAULT_API_BASE = "https://api.paygate.example/v1"


class PayGateClient:
    """Client for the PayGate REST API.

    :param api_key: secret API key (``sk_live_...`` or ``sk_test_...``).
    :param backend: transport used to perform requests: any object with a
        ``request(method, path, params)`` method returning the decoded JSON
        body. Pass a :class:`~paygate_sdk.sandbox.SandboxBackend` to use the
        in-memory sandbox. The SDK does not bundle an HTTP transport; without a
        backend every request raises :class:`~paygate_sdk.errors.PayGateError`.
    :param api_base: base URL of the API, available to transports as
        ``client.api_base``.
    """

    def __init__(self, api_key, backend=None, api_base=DEFAULT_API_BASE):
        if not api_key:
            raise InvalidRequest("an API key is required")
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self._backend = backend
        self.subscriptions = Subscriptions(self)
        self.invoices = Invoices(self)

    def request(self, method, path, params=None):
        if self._backend is not None:
            return self._backend.request(method, path, params)
        return self._send_http(method, path, params)

    def _send_http(self, method, path, params):
        raise PayGateError("network transport not configured")


class _Resource:
    path = ""

    def __init__(self, client):
        self._client = client

    def _object_path(self, object_id):
        if not object_id or "/" in object_id:
            raise InvalidRequest("invalid id: %r" % (object_id,))
        return "%s/%s" % (self.path, object_id)


class Subscriptions(_Resource):
    """``/subscriptions``"""

    path = "/subscriptions"

    def retrieve(self, subscription_id):
        return self._client.request("GET", self._object_path(subscription_id))

    def list(self, customer):
        return self._client.request("GET", self.path, {"customer": customer})


class Invoices(_Resource):
    """``/invoices``"""

    path = "/invoices"

    def retrieve(self, invoice_id):
        return self._client.request("GET", self._object_path(invoice_id))

    def list(self, customer):
        return self._client.request("GET", self.path, {"customer": customer})
