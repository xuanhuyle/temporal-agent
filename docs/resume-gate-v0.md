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


## LangGraph integration (v0.1)

Install the optional integration:

```bash
pip install -e '.[langgraph]'
```

`GuardedLangGraph` wraps an already-compiled LangGraph. It does not replace the
checkpointer. When a graph pauses at an interrupt, the wrapper stores a separate
Resume Gate manifest keyed to the persisted thread. Before any later
`Command(resume=...)`, it materializes the current manifest and runs the unchanged
v0 validator.

Any non-`SAFE` verdict fails closed before LangGraph executes the resume.

Run the stale-authority demonstration:

```bash
PYTHONPATH=src python examples/resume_gate/langgraph_refund_demo.py
```

The demo:

1. starts a refund workflow;
2. pauses it at a LangGraph `interrupt()`;
3. revokes the `refund_customer` tool while the thread sleeps;
4. attempts `Command(resume=True)`;
5. receives `BLOCK` before the refund node executes.

### Integration contract

The application supplies two small functions:

- `checkpoint_manifest(snapshot, config)`: captures what made execution valid when
  the graph paused;
- `current_manifest(snapshot, config)`: obtains the authoritative state at resume.

Resume Gate intentionally does not guess how an application obtains live policy,
tool, credential or dependency state. That boundary is application-specific.

The manifest store should be at least as durable as the LangGraph checkpointer in
production. v0.1 ships an in-memory store for tests and local examples only.


## Automatic LangGraph capture (v0.2)

For the common case, applications no longer need to supply separate
`checkpoint_manifest` and `current_manifest` callbacks.

Use:

```python
guarded = GuardedLangGraph.auto(
    compiled_graph,
    store=JsonDirectoryManifestStore(".resume-gate"),
)
```

With no application annotations, Resume Gate automatically fingerprints:

- LangGraph package version;
- graph topology;
- input/output/state schema shape;
- registered `ToolNode` tools and their argument schemas.

Those values are sampled when the graph pauses and again immediately before
`Command(resume=...)`.

This catches, without application-specific rules:

- tool removal between deployments → `BLOCK`;
- tool schema/description change → `REVALIDATE`;
- state-schema drift → `MIGRATE`;
- graph/framework/runtime drift → `REVALIDATE`.

The automatic schema capture has a non-Pydantic fallback so it does not require
applications to change otherwise executable Python 3.11 `TypedDict` graphs
merely to make Resume Gate work.

### Optional live context

LangGraph cannot infer external business authority generically. A single
optional provider can add current policy, approvals and dependencies:

```python
def live_context(snapshot, config):
    return {
        "policy_version": policy_store.current_version(),
        "authorities": approval_store.for_thread(config),
        "dependencies": dependency_store.current_readings(),
    }

guarded = GuardedLangGraph.auto(
    compiled_graph,
    context_provider=live_context,
    store=JsonDirectoryManifestStore(".resume-gate"),
)
```

The same provider is called at pause time and resume time. Resume Gate preserves
the pause-time result in the manifest, so the developer does not maintain two
parallel representations of "then" and "now".

### Persistence

`JsonDirectoryManifestStore` is a small single-host persistent store. It writes
one JSON document per LangGraph thread/namespace using atomic replacement.

It is appropriate for local prototypes and single-host deployments. A
distributed production deployment should implement the small `ManifestStore`
interface on the same durability tier as its LangGraph checkpointer.

### Verified deployment scenario

The LangGraph integration CI now exercises a real cross-deployment case:

1. Deployment A registers `refund_customer`.
2. A persisted thread pauses at an interrupt.
3. Resume Gate automatically records the tool surface.
4. Deployment B is compiled without `refund_customer`.
5. The same persisted thread is resumed.
6. Resume Gate discovers the removed tool from the new graph and returns
   `BLOCK` before LangGraph executes the next node.

No checkpoint/current manifest callbacks are supplied in that test.
