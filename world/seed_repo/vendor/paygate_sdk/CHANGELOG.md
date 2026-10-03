# Changelog

## 1.3.2 (2025-08-19)

- Fixed `InvalidRequest` being raised without an error code when the API
  response omitted one.
- `SandboxBackend.fail_next()` now validates the error name.

## 1.3.1 (2025-07-08)

- Fixed sandbox list endpoints returning objects in insertion order instead of
  id order.

## 1.3.0 (2025-05-27)

- Added `SandboxBackend.advance()` for moving the sandbox clock.
- Added `created` to subscription objects.
- Errors now expose `http_status`.

## 1.2.0 (2025-04-02)

- Added `client.invoices.retrieve()`.
- Added `SandboxBackend.fail_next()` for simulating outages.

## 1.1.0 (2025-02-11)

- Added `client.invoices.list()`.
- Added the `trialing` subscription status.

## 1.0.0 (2025-01-14)

- First stable release: `client.subscriptions.retrieve()` and
  `client.subscriptions.list()`, `SandboxBackend`, and the `PayGateError`
  hierarchy.
