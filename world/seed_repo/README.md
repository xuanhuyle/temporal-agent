# Tasklane

Tasklane is task tracking for small teams: accounts hold projects, projects
hold tasks, and team members share an account.

Accounts are on one of three plans:

| Plan | Price      | Projects  | Seats |
|------|------------|-----------|-------|
| Free | $0         | 3         | 1     |
| Pro  | $12/month  | Unlimited | 5     |
| Team | $29/month  | Unlimited | 50    |

Paid plans are billed through PayGate. Plan definitions live in
`tasklane/plans.py`.

## Layout

| Path | Contents |
|------|----------|
| `tasklane/config.py` | Settings loader and validation (`config/settings.json`) |
| `tasklane/db.py` | SQLite connections, migrations, timestamp encoding |
| `tasklane/migrations/` | Schema migrations, applied in filename order |
| `tasklane/auth.py` | Password hashing, registration, login, sessions |
| `tasklane/plans.py` | Plan catalogue |
| `tasklane/billing.py` | Subscriptions and entitlements |
| `tasklane/projects.py` | Accounts, projects, tasks; plan limits |
| `tasklane/jobs.py` | SQLite-backed job queue and subscription reconciliation |
| `tasklane/providers/` | Payment provider interface and the PayGate adapter |
| `vendor/` | Vendored third-party code (PayGate SDK) |
| `config/settings.json` | Application settings |
| `infra/platform.json` | Hosting configuration |
| `docs/adr/` | Architecture decision records |
| `tests/` | Test suite |

## Development

Tasklane needs Python 3.11 or newer and has no runtime dependencies outside
the standard library. The test suite needs pytest:

```
pip install -r requirements-dev.txt
python -m pytest
```

Tests use in-memory databases and the PayGate sandbox; they need no network
access and leave no files behind.

All library functions that depend on the current time take an explicit `now`
(an aware UTC datetime) instead of reading the clock.

## Working agreements

- **Decisions** with lasting impact are recorded as ADRs in `docs/adr/`.
- **Tickets** are referenced as `TCK-NNNN` in commit messages, branch names and
  code comments.
- **Third-party code** is vendored under `vendor/`, because our build and deploy
  environments have no package index access. See `vendor/README.md`.
- **Hosting facts** (platform, tier, resources, managed services) are kept in
  `infra/platform.json`. Keep it in sync with the Fleetline configuration.
- **Settings** live in `config/settings.json`. Every key is required and
  unknown keys are rejected, so add new settings to `tasklane/config.py` and the
  JSON file together.
