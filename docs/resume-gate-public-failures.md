# Resume Gate v0 — Public failure coverage

Date: 2026-10-03

## Question

Without changing Resume Gate v0's rules, how much of the public checkpoint/resume failure surface does its existing manifest comparison catch?

This is a **coverage probe**, not a prevalence study.

The corpus was assembled from public issue reports in LangGraph, LangGraph.js, Microsoft Agent Governance Toolkit, and OpenAI Agents SDK. The before/after manifests are our normalization of those reports; they were not supplied by the issue authors.

Source data: `examples/resume_gate/public_cases.json`.

## Result

16 public failure reports were normalized.

| classification | cases | interpretation |
|---|---:|---|
| **caught** | 4 | v0 directly returns the safety action appropriate to the reported risk |
| **partial** | 4 | v0 surfaces enough drift/uncertainty to prevent blind resume, but does not identify the framework's exact failure |
| **not caught** | 7 | the current manifests look safe even though the underlying runtime can resume incorrectly |
| **out of scope** | 1 | no checkpoint exists, so a resume validator has nothing to inspect |

Among the 15 cases where a checkpoint exists:

- direct coverage: **4 / 15 (26.7%)**;
- direct + partial safety signal: **8 / 15 (53.3%)**;
- missed: **7 / 15 (46.7%)**.

Do **not** interpret these percentages as incident prevalence. The corpus is deliberately heterogeneous and was selected to pressure-test the product boundary.

## Directly caught

### 1. Microsoft Agent Governance Toolkit #2641 — stale authorization

Source: https://github.com/microsoft/agent-governance-toolkit/issues/2641

A tool permission can be serialized into LangGraph checkpoint state and survive until a later resume even if the tool has since been removed from the allowed set.

**v0:** `BLOCK`.

Why: the checkpoint's tool/permission contract no longer matches the current environment.

This is the cleanest example of the product thesis:

> durable state can be mechanically restorable while no longer being authorized to execute.

### 2. LangGraph #9001 — state key removed across deploy

Source: https://github.com/langchain-ai/langgraph/issues/9001

Removing a graph state key can leave existing threads in an infinite approval/re-interrupt loop after deployment.

**v0:** `MIGRATE`.

Why: the issue itself treats state-key removal as a breaking change; when the state schema is versioned in the manifest, v0 prevents normal resume across the schema boundary.

### 3. LangGraph #9006 — ambiguous tool timeout

Source: https://github.com/langchain-ai/langgraph/issues/9006

After a tool timeout or worker death, the runtime may not know whether the external side effect occurred and whether replay is safe.

**v0:** `BLOCK` for a non-idempotent uncertain effect; `REVALIDATE` if a durable idempotency key exists.

Why: automatic replay is unsafe until the external effect is reconciled.

### 4. OpenAI Agents SDK #4646 — tool completed, persistence ambiguous

Source: https://github.com/openai/openai-agents-python/issues/4646

A tool and its guardrails can complete before Session persistence fails, leaving resumable state that may continue despite an ambiguous publication boundary.

**v0:** `BLOCK` when represented as an uncertain non-idempotent side effect.

Why: completion in local process state is not sufficient evidence that retrying is safe.

## Partially caught

These cases trigger a conservative gate, but v0 does not understand the framework-specific invariant that failed.

### LangGraph #7066 — unknown type silently deserializes as a dict

Source: https://github.com/langchain-ai/langgraph/issues/7066

v0 can flag a declared runtime/agent version change, but it does not inspect serialized payload types. It therefore says `REVALIDATE`, not "checkpoint payload corrupted."

### LangGraph.js #2667 — completed subgraph task re-executes

Source: https://github.com/langchain-ai/langgraphjs/issues/2667

If the task crossed an external side-effect boundary and that effect is declared, v0 can require receipt/idempotency verification. It does not understand subgraph checkpoint namespaces or detect duplicate execution of pure tasks.

### OpenAI Agents SDK #4685 — handoff plus Session append failure

Source: https://github.com/openai/openai-agents-python/issues/4685

v0 can stop blind continuation when an external effect is left uncertain, but it cannot prove that Session history and handoff state agree.

### OpenAI Agents SDK #4690 — terminal tool output not durably appended

Source: https://github.com/openai/openai-agents-python/issues/4690

Same boundary: v0 can gate an ambiguous external effect but does not reconcile the framework's Session ledger.

## Not caught

### LangGraph #8234 — inconsistent checkpoint/write ordering

Source: https://github.com/langchain-ai/langgraph/issues/8234

The environment has not drifted; the checkpoint itself may be internally inconsistent. v0 has no checkpoint integrity proof.

### LangGraph #8837 — stale resume payload re-used

Source: https://github.com/langchain-ai/langgraph/issues/8837

v0 does not model interrupt payload identity or whether a resume value has already been consumed.

### LangGraph #8579 — multiple interrupts misrouted

Source: https://github.com/langchain-ai/langgraph/issues/8579

v0 has no pending-interrupt set or resume-value routing invariant.

### LangGraph #6792 — nested checkpoint scope causes rerun

Source: https://github.com/langchain-ai/langgraph/issues/6792

Without an explicitly declared external side effect, v0 does not model checkpoint namespace ancestry or task-completion identity.

### LangGraph #8358 — historical replay vs live run boundary

Source: https://github.com/langchain-ai/langgraph/issues/8358

v0 validates whether a checkpoint may execute; it does not label event-stream provenance.

### OpenAI Agents SDK #4323 — pending-input ordering and exactly-once admission

Source: https://github.com/openai/openai-agents-python/issues/4323

v0 does not model pending input, ownership, ordering or consumption.

### LangGraph #6938 — malformed checkpoint schema reaches load path

Source: https://github.com/langchain-ai/langgraph/issues/6938

v0 compares declared schema versions but does not validate the checkpoint payload against a schema definition.

## Out of scope

### LangGraph #8764 — run dies before first durable checkpoint

Source: https://github.com/langchain-ai/langgraph/issues/8764

There is no checkpoint to inspect. This is a durable admission / run-ledger problem, not resume validity.

## What this says about the product

The useful boundary is narrower than "make resume reliable."

Resume Gate v0 is strongest at:

> **Is the checkpoint still entitled and compatible to continue in the current environment?**

It is not currently a solution for:

- checkpoint corruption;
- framework checkpoint ordering;
- interrupt routing;
- pending-input exactly-once semantics;
- event-stream provenance;
- durable run admission.

Those are workflow-engine/runtime concerns.

This is a positive boundary if the product remains a small layer that can sit **in front of** different durable runtimes rather than trying to replace them.

## Temporal-agency connection

The original temporal-agency intuition survives here in a concrete form:

```text
valid state at t1
      +
world / policy / authority changes
      ↓
the same persisted state at t2
may no longer be safe to execute
```

The relevant temporal distinction is not "past self" versus "present self."

It is:

> **state validity is time-dependent.**

The system must distinguish:

- what the checkpoint said then;
- what is authoritative now;
- which assumptions must be revalidated before the past state can act in the present.

That is a narrow operational expression of the broader thesis, without requiring a bespoke temporal-agent architecture.

## Decision for the next iteration

Do not add an LLM yet.

The next most informative product question is:

> Can we integrate this gate into one real resumable agent framework with minimal developer effort and catch one of these failures before execution?

The strongest first integration target is LangGraph because:
- most public cases in this corpus are there;
- checkpoint/resume is a first-class abstraction;
- the stale-authorization case in Microsoft AGT explicitly proposes resume-time validation around LangGraph.

A good v0.1 would be a LangGraph adapter that:
1. captures the manifest fields at checkpoint time;
2. re-materializes current state at resume;
3. runs the unchanged validator before the next node/tool executes;
4. blocks or pauses on a non-SAFE verdict.

Do not broaden the validator until that integration is proven.
