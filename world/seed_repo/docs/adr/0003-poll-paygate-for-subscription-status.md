# ADR-0003: Poll PayGate for subscription status

- Status: Accepted
- Date: 2025-11-20

## Context

Paid plans are billed through PayGate. Tasklane needs a local view of each
account's subscription status to decide what the account is entitled to.

Our PayGate account is on the Starter plan, which does not include webhook
delivery (webhooks are available on the Growth plan and above), so PayGate
cannot notify us when a subscription changes.

New subscriptions start in `incomplete` status until the first payment is
confirmed, which usually takes a few seconds but can take longer.

## Decision

- A background job, `reconcile_subscriptions` (`tasklane/jobs.py`), polls
  PayGate every 15 minutes (`reconcile_interval_minutes`) and updates the local
  `subscriptions` table when status, plan or period end have changed. Each run
  schedules the next one, and failed runs are retried with backoff. Every
  worker pass also checks that a run is queued (`ensure_reconcile_scheduled`)
  and enqueues one if not, so polling resumes by itself after a run has used
  up its retries.
- To avoid locking out customers who have just checked out, a subscription in
  `incomplete` status is entitled to its plan for `checkout_grace_minutes`
  (30) after creation (`tasklane/billing.py`).

## Consequences

- Entitlement changes can lag PayGate by up to 15 minutes, plus retry delays
  if PayGate is unavailable.
- The extra API calls (one per subscription every 15 minutes) are well within
  PayGate's rate limits at our customer count.
- The integration only depends on read endpoints of the PayGate API.
