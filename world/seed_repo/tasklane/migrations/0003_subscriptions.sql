-- Local mirror of each account's PayGate subscription (see ADR-0003).

CREATE TABLE subscriptions (
    account_id               INTEGER PRIMARY KEY REFERENCES accounts(id),
    plan_id                  TEXT    NOT NULL,
    status                   TEXT    NOT NULL,
    provider_subscription_id TEXT    NOT NULL UNIQUE,
    provider_customer_id     TEXT    NOT NULL,
    current_period_end       TEXT    NOT NULL,
    created_at               TEXT    NOT NULL,
    updated_at               TEXT    NOT NULL
);
