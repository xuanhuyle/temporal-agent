"""PayGate Python SDK.

Usage::

    from paygate_sdk import PayGateClient, SandboxBackend

    client = PayGateClient("sk_test_...", backend=SandboxBackend())
    subscriptions = client.subscriptions.list(customer="cus_0001")

The SDK does not bundle an HTTP transport; pass your own ``backend`` for
live requests (see :class:`PayGateClient`).
"""

from .client import DEFAULT_API_BASE, PayGateClient
from .errors import InvalidRequest, NotFound, PayGateError, ServiceUnavailable
from .sandbox import SandboxBackend

__version__ = "1.4.0"

__all__ = [
    "DEFAULT_API_BASE",
    "InvalidRequest",
    "NotFound",
    "PayGateClient",
    "PayGateError",
    "SandboxBackend",
    "ServiceUnavailable",
    "__version__",
]
