# ADR-0002: Password hashing cost

- Status: Accepted
- Date: 2025-10-14

## Context

Passwords are hashed with PBKDF2-HMAC-SHA256 from the Python standard library.
OWASP's current guidance for PBKDF2-HMAC-SHA256 is 600,000 iterations.

Production runs on Fleetline's `shared-0.25` tier: a quarter of a burstable
vCPU (see `infra/platform.json`). Measured in production:

| Iterations | Time per hash |
|-----------:|--------------:|
| 600,000    | ≈ 1.4 s       |
| 120,000    | ≈ 280 ms      |

For comparison, 600,000 iterations take ≈ 210 ms on a dedicated vCPU (our CI
runners). The difference is CPU throttling on the shared tier.

Our login latency budget is p95 ≤ 400 ms. A slow hash also makes the login
endpoint an easy CPU-exhaustion target on an instance this small: a handful of
concurrent login attempts at 600,000 iterations would saturate it.

## Decision

Use 120,000 iterations, configured via `pbkdf2_iterations` in
`config/settings.json`.

Each stored hash embeds its iteration count
(`pbkdf2_sha256$<iterations>$<salt>$<hash>`), and verification uses the
embedded count. `authenticate()` transparently re-hashes the password on a
successful login when the configured count differs from the stored one, so the
cost can be changed without a data migration.

## Consequences

- Login stays within the latency budget (≈ 280 ms per hash).
- The cost is below OWASP guidance. This is a hardware-driven compromise, not a
  security target.
- Changing the cost is a configuration change; existing users move to the new
  cost as they log in.
