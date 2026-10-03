# Resume Gate v0

Resume Gate answers one question before a long-running agent resumes from a persisted checkpoint:

> **Is this checkpoint still valid to execute against the world as it exists now?**

It does not provide durable execution. It assumes a checkpoint already exists and checks whether objective facts that made the checkpoint safe are still true.

## v0 scope

The first iteration is deliberately deterministic and model-free. It compares two JSON manifests:

- the assumptions captured with the checkpoint;
- the current execution environment.

It returns one of four verdicts:

- `SAFE` — no declared incompatibility was detected;
- `REVALIDATE` — something changed and must be checked before continuing;
- `MIGRATE` — checkpoint state is structurally incompatible with the current runtime;
- `BLOCK` — continuing automatically would violate current authority or replay-safety constraints.

## Checks

v0 checks:

1. state schema drift;
2. agent/model version drift;
3. tool removal, version drift, or permission-contract changes;
4. stale, revoked, missing, expired, or policy-mismatched authorities;
5. changed or stale declared dependencies;
6. uncertain side effects and idempotency/receipt safety.

The key rule is:

> **Persisted memory is evidence, not current authority.**

An approval, permission or tool capability saved inside a checkpoint never authorizes an action by itself. Resume Gate re-checks it against the current manifest.

## Usage

After `pip install -e .`:

```bash
resume-gate validate examples/resume_gate/checkpoint.json examples/resume_gate/current.json
```

Machine-readable output:

```bash
resume-gate validate examples/resume_gate/checkpoint.json examples/resume_gate/current.json --json
```

The example returns `BLOCK` because the saved approval is no longer active, while also surfacing policy/runtime/dependency drift.

## Exit codes

| verdict | exit code |
|---|---:|
| SAFE | 0 |
| invalid input / runtime error | 1 |
| REVALIDATE | 2 |
| MIGRATE | 3 |
| BLOCK | 4 |

## What v0 intentionally does not do

- infer undeclared dependencies;
- use an LLM to decide resume safety;
- migrate checkpoints;
- refresh credentials or approvals;
- call external systems;
- guarantee sandboxing or exactly-once execution;
- replace a durable workflow engine.

Those are later questions only if this simple gate captures a meaningful fraction of real resume failures.

## First falsification target

The next iteration should be driven by externally observed failure cases, not new architecture. Take public checkpoint/resume failures from real agent frameworks and encode their before/after state as manifests.

The v0 is useful only if the same small set of rules catches several independent real failures without case-specific logic.
