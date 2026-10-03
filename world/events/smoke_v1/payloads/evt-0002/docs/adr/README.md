# Architecture Decision Records

Significant technical decisions are recorded here, one file per decision.

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [0001](0001-use-sqlite-for-persistence.md) | Use SQLite for persistence | Accepted | 2025-09-02 |
| [0002](0002-password-hashing-cost.md) | Password hashing cost | Accepted | 2025-10-14 |
| [0003](0003-poll-paygate-for-subscription-status.md) | Poll PayGate for subscription status | Accepted | 2025-11-20 |
| [0004](0004-keep-plan-while-payment-is-retried.md) | Keep the paid plan while PayGate retries a failed renewal | Accepted | 2026-01-08 |

## Writing a new ADR

New ADRs take the next number (`NNNN-short-title.md`) and use the same
sections as the existing ones: Title, Status, Date, Context, Decision,
Consequences.
