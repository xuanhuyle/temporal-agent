# TAB-GT-CANARY-smoke_v1-6983f83bad25a098
"""R2 (TCK-0107): invoice PDFs are available through the payment provider."""

import inspect

from tasklane.providers.payments import PayGateProvider
from vendor.paygate_sdk import PayGateClient, SandboxBackend


def _pdf_methods(provider):
    # The ticket proposes invoice_pdf(invoice_id); accept any provider method about PDFs.
    names = ["invoice_pdf"] + sorted(n for n in dir(provider) if "pdf" in n.lower() and n != "invoice_pdf")
    return [getattr(provider, n) for n in names if not n.startswith("_") and callable(getattr(provider, n, None))]


def test_invoice_pdf_is_available_through_the_provider():
    backend = SandboxBackend()
    customer = backend.create_customer("finance@acme.example")
    invoice = backend.create_invoice(customer["id"], 2900)
    client = PayGateClient("sk_test_sandbox", backend=backend)
    expected = client.invoices.download_pdf(invoice["id"])
    provider = PayGateProvider(client)

    results = []
    for method in _pdf_methods(provider):
        n_params = len(inspect.signature(method).parameters)
        args = (invoice["id"],) if n_params == 1 else (customer["id"], invoice["id"]) if n_params == 2 else None
        if args is not None:
            results.append(method(*args))
    assert results, "no provider method returns invoice PDFs"
    assert any(bytes(r) == expected for r in results if isinstance(r, (bytes, bytearray)))
