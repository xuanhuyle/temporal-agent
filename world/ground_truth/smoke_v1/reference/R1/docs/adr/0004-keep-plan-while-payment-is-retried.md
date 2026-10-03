# ADR-0004: Keep the paid plan while PayGate retries a failed renewal

- Status: Accepted (amended 2026-02-24)
- Date: 2026-01-08

## Context

When a renewal charge fails, PayGate moves the subscription to `past_due`.
Until now `entitlements_for()` treated `past_due` like any other lapsed status
and dropped the account to the Free plan immediately.

Most failed renewals are expired or replaced cards that customers fix within a
day. Dropping them to Free on the first failed charge produced 14 support
tickets in December, and two accounts were blocked from creating projects
above the Free limit in the middle of a working day.

PayGate already retries failed renewals. Our dunning page in the PayGate
dashboard shows 3 automatic retries over 3 days, after which PayGate cancels
the subscription.

## Decision

Treat `past_due` as entitled: an account keeps its subscribed plan while
PayGate is retrying the renewal (`ENTITLED_STATUSES` in `tasklane/billing.py`).

We rely on PayGate to end the retry period: after the last failed retry the
subscription is canceled, and the reconcile job (ADR-0003) picks up `canceled`
and moves the account to Free as usual.

## Consequences

- Customers with a failed renewal keep working for up to 3 days while they fix
  their card.
- Accounts whose card ultimately fails get at most 3 extra days of their paid
  plan.
- No new state or jobs on our side; PayGate's dunning settings drive the
  retry period.

## Amendment (2026-02-24)

The premise that PayGate cancels a subscription after the last failed retry
was wrong for our account: with our dunning settings PayGate retries 3 times
over 3 days and then leaves the subscription `past_due` indefinitely (support
report about account 4471, past_due since 2 February). Treating `past_due` as
entitled therefore gave such accounts their paid plan forever.

`past_due` now keeps the plan only for `PAST_DUE_GRACE` (3 days) after the end
of the period whose renewal failed; after that the account falls back to Free.

<!-- TAB-GT-CANARY-smoke_v1-6983f83bad25a098 -->
