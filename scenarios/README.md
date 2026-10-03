# Scenarios

Scenario families vary one main difficulty axis at a time:

- `simple/`
- `long_history/`
- `high_noise/`
- `deep_causality/`

A scenario is frozen once used to evaluate a contestant version. Any post-run modification creates a new scenario version.

## Scenarios

| Scenario | Status | Held out | Purpose |
|---|---|---|---|
| `smoke/smoke_v1.json` | frozen | no | 10-event machinery check: 3 reconsiderations (delayed evidence, constraint disappears, parked dependency resolves), 5 distractors |

Validate with `PYTHONPATH=src python -m harness validate --scenario <manifest>`.
