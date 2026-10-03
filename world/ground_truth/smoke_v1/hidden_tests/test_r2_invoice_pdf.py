# TAB-GT-CANARY-smoke_v1-6983f83bad25a098
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
