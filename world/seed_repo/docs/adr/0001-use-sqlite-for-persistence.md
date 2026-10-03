# ADR-0001: Use SQLite for persistence

- Status: Accepted
- Date: 2025-09-02

## Context

Tasklane runs as a single instance on Fleetline PaaS with a 5 GB persistent
volume (see `infra/platform.json`). Our Fleetline plan does not include managed
Postgres, and we do not want to operate a database server ourselves for an
application of this size.

Write volume is low: fewer than 5 writes per second at peak (sign-ups, task
edits, and the periodic background jobs).

We also need somewhere to keep background jobs. A separate broker (such as
Redis) is not available on our plan either.

## Decision

Use SQLite, stored on the persistent volume, as the only database.

- Connections enable WAL journaling and foreign-key enforcement
  (`tasklane/db.py`).
- Schema changes are plain SQL files in `tasklane/migrations/`, named
  `NNNN_description.sql` and applied in filename order. Applied migrations are
  recorded in `schema_migrations`.
- The background job queue is a table in the same database
  (`tasklane/jobs.py`).

## Consequences

- No database server to operate, back up separately, or pay for. Backups are a
  copy of the database file.
- SQLite allows a single writer at a time. That is fine at our write volume,
  but long write transactions must be avoided.
- The database lives on one instance's volume, so scaling past one instance
  would need a different database.
- Jobs and application data share transactions and backups.
