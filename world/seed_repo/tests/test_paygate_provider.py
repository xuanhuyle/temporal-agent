from datetime import datetime, timezone

import pytest

from tasklane.providers import (
    PayGateProvider,
    ProviderError,
    ProviderInvoice,
    ProviderSubscription,
    ProviderUnavailable,
)
from vendor.paygate_sdk import NotFound, PayGateClient, PayGateError, ServiceUnavailable


def test_get_subscription_maps_fields(provider, sandbox):
    customer = sandbox.create_customer("ada@example.com")
    remote = sandbox.create_subscription(
        customer["id"], "team", status="trialing", current_period_end=1769904000
    )

    sub = provider.get_subscription(remote["id"])
    assert sub == ProviderSubscription(
        id="sub_0001",
        customer_id="cus_0001",
        plan_id="team",
        status="trialing",
        current_period_end=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )


def test_list_invoices_maps_fields(provider, sandbox):
    customer = sandbox.create_customer("ada@example.com")
    other = sandbox.create_customer("bob@example.com")
    sandbox.create_invoice(customer["id"], 1200, created=1767225600)
    sandbox.create_invoice(other["id"], 2900)
    sandbox.create_invoice(customer["id"], 1200, status="open", created=1769904000)

    jan_1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    feb_1 = datetime(2026, 2, 1, tzinfo=timezone.utc)
    assert provider.list_invoices(customer["id"]) == [
        ProviderInvoice("in_0001", "cus_0001", 1200, "paid", jan_1),
        ProviderInvoice("in_0003", "cus_0001", 1200, "open", feb_1),
    ]
    assert provider.list_invoices("cus_9999") == []


def test_service_unavailable_becomes_provider_unavailable(provider, sandbox):
    customer = sandbox.create_customer("ada@example.com")
    remote = sandbox.create_subscription(customer["id"], "pro")
    sandbox.fail_next(2)

    for _ in range(2):
        with pytest.raises(ProviderUnavailable) as excinfo:
            provider.get_subscription(remote["id"])
        assert isinstance(excinfo.value.__cause__, ServiceUnavailable)
    assert provider.get_subscription(remote["id"]).status == "active"

    sandbox.fail_next(1)
    with pytest.raises(ProviderUnavailable):
        provider.list_invoices(customer["id"])


def test_other_sdk_errors_become_provider_error(provider):
    with pytest.raises(ProviderError) as excinfo:
        provider.get_subscription("sub_9999")
    assert not isinstance(excinfo.value, ProviderUnavailable)
    assert isinstance(excinfo.value.__cause__, NotFound)


def test_client_without_transport_becomes_provider_error():
    with pytest.raises(ProviderError) as excinfo:
        PayGateProvider(PayGateClient("sk_test_x")).get_subscription("sub_0001")
    assert type(excinfo.value.__cause__) is PayGateError
