"""Exceptions raised by the PayGate SDK."""


class PayGateError(Exception):
    """Base class for all PayGate errors.

    ``code`` is the machine-readable error code returned by the API, when
    there is one. ``http_status`` is the HTTP status of the failed request.
    """

    default_code = "api_error"
    default_http_status = 500

    def __init__(self, message, code=None, http_status=None):
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.http_status = http_status or self.default_http_status


class InvalidRequest(PayGateError):
    """The request was malformed or had invalid parameters (HTTP 400)."""

    default_code = "invalid_request"
    default_http_status = 400


class NotFound(PayGateError):
    """The requested object does not exist (HTTP 404)."""

    default_code = "resource_missing"
    default_http_status = 404


class ServiceUnavailable(PayGateError):
    """PayGate is temporarily unable to handle the request (HTTP 503).

    Safe to retry with backoff.
    """

    default_code = "service_unavailable"
    default_http_status = 503
