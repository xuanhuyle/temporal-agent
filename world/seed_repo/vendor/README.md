# Vendored dependencies

Our CI runners and the production build on Fleetline have no access to a
package index, so third-party runtime code is vendored here instead of being
installed with pip.

Policy:

- Each package lives in its own directory under `vendor/` and is imported as
  `vendor.<package>`.
- Vendored code is copied verbatim from an upstream release. Do not edit it in
  place; if a fix is needed, upgrade to a newer upstream release or wrap the
  behaviour in our own code (see `tasklane/providers/`).
- Keep the upstream `README.md` and `CHANGELOG.md` next to the code so the
  vendored version and its documented behaviour are easy to check.
- Upgrading means replacing the whole directory with the new release and
  running the full test suite.

| Package       | Version | Used by                          |
|---------------|---------|----------------------------------|
| `paygate_sdk` | 1.3.2   | `tasklane/providers/payments.py` |
