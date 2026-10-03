"""Payment provider abstraction.

The rest of Tasklane talks to :class:`PaymentProvider`, never to the PayGate
SDK directly. :class:`PayGateProvider` adapts the vendored SDK
(``vendor/paygate_sdk``): it converts SDK dicts into typed records and SDK
exceptions into :class:`ProviderError` / :class:`ProviderUnavailable`.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from vendor.paygate_sdk import PayGateClient, PayGateError, ServiceUnavailable


class ProviderError(Exception):
    """The payment provider rejected a request or returned an error."""


class ProviderUnavailable(ProviderError):
    """The payment provider is temporarily unreachable; retrying may succeed."""


@dataclass(frozen=True)
class ProviderSubscription:
    id: str
    customer_id: str
    plan_id: str
    status: str
    current_period_end: datetime


@dataclass(frozen=True)
class ProviderInvoice:
    id: str
    customer_id: str
    amount_cents: int
    status: str
    created_at: datetime


class PaymentProvider(Protocol):
    def get_subscription(self, subscription_id: str) -> ProviderSubscription: ...

    def list_invoices(self, customer_id: str) -> list[ProviderInvoice]: ...


def _from_epoch(value: int) -> datetime:
    return datetime.fromtimestamp(value, tz=timezone.utc)


class PayGateProvider:
    """PaymentProvider backed by the vendored PayGate SDK."""

    def __init__(self, client: PayGateClient) -> None:
        self._client = client

    def get_subscription(self, subscription_id: str) -> ProviderSubscription:
        data = self._call(self._client.subscriptions.retrieve, subscription_id)
        return ProviderSubscription(
            id=data["id"],
            customer_id=data["customer"],
            plan_id=data["plan"],
            status=data["status"],
            current_period_end=_from_epoch(data["current_period_end"]),
        )

    def list_invoices(self, customer_id: str) -> list[ProviderInvoice]:
        items = self._call(self._client.invoices.list, customer=customer_id)
        return [
            ProviderInvoice(
                id=item["id"],
                customer_id=item["customer"],
                amount_cents=int(item["amount_due"]),
                status=item["status"],
                created_at=_from_epoch(item["created"]),
            )
            for item in items
        ]

    @staticmethod
    def _call(method: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        try:
            return method(*args, **kwargs)
        except ServiceUnavailable as exc:
            raise ProviderUnavailable(str(exc)) from exc
        except PayGateError as exc:
            raise ProviderError(str(exc)) from exc
