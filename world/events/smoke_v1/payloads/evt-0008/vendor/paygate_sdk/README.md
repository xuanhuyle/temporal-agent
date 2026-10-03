# PayGate Python SDK

Version 1.4.0

A small client for the PayGate payments API. Responses are returned as plain
Python dicts and lists, decoded from the API's JSON.

## Installation

```
pip install paygate-sdk==1.4.0
```

## Usage

```python
from paygate_sdk import PayGateClient

client = PayGateClient("sk_test_...", backend=my_transport)

subscription = client.subscriptions.retrieve("sub_0001")
invoices = client.invoices.list(customer="cus_0001")
```

`backend` is the transport that performs requests: any object with a
`request(method, path, params)` method returning the decoded JSON body. The SDK
does not bundle an HTTP transport.

## Sandbox

`SandboxBackend` is an in-memory implementation of the API for development and
tests. Object ids are sequential (`cus_0001`, `sub_0001`, `in_0001`, ...) and
timestamps come from the sandbox clock (`backend.now`), so results are
reproducible.

```python
from paygate_sdk import PayGateClient, SandboxBackend

backend = SandboxBackend()
customer = backend.create_customer("ada@example.com")
backend.create_subscription(customer["id"], "pro", status="trialing")
client = PayGateClient("sk_test_sandbox", backend=backend)
```

`backend.fail_next(n)` makes the next `n` API calls raise `ServiceUnavailable`,
which is useful for testing retry logic.

## Resources

### Subscriptions

- `client.subscriptions.retrieve(subscription_id)`
- `client.subscriptions.list(customer=customer_id)`

```json
{
  "id": "sub_0001",
  "object": "subscription",
  "customer": "cus_0001",
  "plan": "pro",
  "status": "active",
  "current_period_end": 1738281600,
  "created": 1735689600
}
```

Timestamps are Unix epoch seconds (UTC).

### Invoices

Invoices can be listed and retrieved:

- `client.invoices.retrieve(invoice_id)`
- `client.invoices.list(customer=customer_id)`
- `client.invoices.download_pdf(invoice_id)` returns the rendered invoice as
  PDF bytes.

```json
{
  "id": "in_0001",
  "object": "invoice",
  "customer": "cus_0001",
  "amount_due": 1200,
  "status": "paid",
  "created": 1735689600
}
```

Invoice statuses: `draft`, `open`, `paid`, `uncollectible`, `void`.

## Subscription statuses

| Status       | Meaning |
|--------------|---------|
| `incomplete` | The subscription was created but the first payment is still pending. |
| `trialing`   | The subscription is in its trial period. |
| `active`     | The subscription is paid and in good standing. |
| `past_due`   | A renewal payment failed; PayGate retries the charge according to the dunning settings of your PayGate account. While a subscription is `past_due`, `current_period_end` stays at the end of the period whose renewal failed. |
| `canceled`   | The subscription has been canceled. |
| `unpaid`     | The subscription has outstanding unpaid invoices. |

## Webhooks

Webhook delivery is available on the Growth plan and above.

## Errors

All errors derive from `PayGateError`, which carries `code` and `http_status`.

| Exception            | HTTP | When |
|----------------------|------|------|
| `InvalidRequest`     | 400  | Missing or invalid parameters. |
| `NotFound`           | 404  | The object does not exist. |
| `ServiceUnavailable` | 503  | PayGate is temporarily unavailable. Retry with backoff. |
| `PayGateError`       | 5xx  | Any other API error. |
