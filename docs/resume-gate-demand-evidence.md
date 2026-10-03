# Resume Gate — Public demand / product-boundary evidence

Date: 2026-10-03

## Question

We already know Resume Gate can detect some resume-time drift.

The next product question is different:

> Is "old agent state is mechanically resumable but no longer valid to execute" a repeated operational problem across independent agent ecosystems, or just a handful of LangGraph bugs?

This document uses public framework issues and current framework documentation as revealed-demand evidence. It is not a prevalence study and it is not a substitute for customer interviews.

## Bottom line

**Continue one more product iteration, but narrow the thesis.**

The evidence supports a repeated problem class across multiple ecosystems:

> persistence/resumption preserves execution state, but authority, tool surface, code/schema, session history, or approval semantics can change before or during resume.

However, framework vendors are actively fixing checkpoint/session consistency themselves. Resume Gate should **not** compete as a generic durable-execution or checkpoint-correctness layer.

The independent product hypothesis is now:

> **Cross-framework resume-time validity:** before persisted agent state is allowed to act again, revalidate that its executable assumptions and authority still hold in the current environment.

This is strongest where correctness depends on information *outside* the framework checkpoint:

- current tool/capability surface;
- current policy;
- current approval/authority;
- current external dependency state;
- deployment/schema compatibility.

## Evidence by ecosystem

### 1. LangGraph

Public issues show several distinct ways persisted threads can become invalid or behave incorrectly when resumed.

Examples already in the Resume Gate corpus include:

- #9001 — removing a state key across a deployment can make an old thread re-interrupt forever after approval;
- #8837 — a consumed resume value can be re-used for a later interrupt;
- #8579 — resume values can be associated with the wrong pending interrupt;
- #7066 — code/type drift can cause restored custom state to deserialize incorrectly;
- #8234 / #8039 — crash recovery and checkpoint/write ordering can cause replay/re-execution ambiguity.

Interpretation:

- **real resume pain:** yes;
- **Resume Gate product fit:** strongest for deployment/schema/tool drift;
- **not our product:** checkpoint ordering, interrupt routing and exactly-once runtime internals belong to LangGraph.

### 2. Microsoft Agent Governance Toolkit

Issue #2641 is unusually close to the product thesis.

The issue states that LangGraph checkpointing can carry a tool permission from step N to step N+K even if the tool is removed from `allowed_tools` in between. It proposes checkpoint-time snapshots and resume-time revalidation.

This is direct revealed demand for:

> persisted state must not silently preserve execution authority across time.

Interpretation:

- **real resume-validity pain:** yes;
- **product fit:** direct;
- **competitive warning:** Microsoft governance tooling may absorb this natively.

### 3. OpenAI Agents SDK

The Agents SDK now has a first-class serializable `RunState` for approval/HITL pause and resume, plus Sessions for durable history.

Recent public failures include:

- #4827 — an approval resume can leave a durable session with an orphaned function output, making later runs unusable;
- related approval/session issues (#4611, #4615, #4630, #4685, #4690) deal with ownership, retries and persistence boundaries around resumed tool work.

Current OpenAI documentation has already become much stricter about resume invariants:

- resumed state must use the original Session backend/session identity;
- pending writes are reconciled before further model work;
- independently restored snapshots should not resume concurrently;
- changed or ambiguous history requires application repair;
- some terminal states are explicitly marked unrecoverable rather than replayed.

Interpretation:

- **real resume pain:** yes;
- **vendor absorption:** high — OpenAI is actively moving persistence/replay safety into the SDK;
- **remaining external gap:** the SDK cannot generically know whether an approval, policy, capability, account state or external dependency is still valid *now*.

### 4. Google ADK

Recent public bugs show that HITL/resume correctness can cross an authorization boundary:

- #7303 — after an interrupted upward transfer, resume could skip a later confirmation gate and execute the privileged successor;
- #7148 — a custom tool could execute after the user clicked Decline because the framework did not centrally enforce the confirmation verdict;
- #7245 — nested agent tooling could lose a pending HITL pause;
- resumable workflow issues also show replay/session consistency failures.

A separate public request (#6099) asks for a persistent decision ledger carrying authority, policy outcome and confirmation semantics, motivated by recurring questions from production teams.

Interpretation:

- **real authority/resume pain:** yes;
- **product fit:** current authority and approval semantics are relevant;
- **competitive warning:** ADK can fix framework-local confirmation enforcement itself.

### 5. CrewAI

The ecosystem has public requests for:

- a standardized pre-tool authorization provider (#4877);
- a runtime release-control mediation layer before agent/tool execution (#6025);
- durable idempotency protection against repeated external side effects on retry (#5802).

These are not all resume-time problems, but they show demand for a cross-cutting execution gate *before* tools run.

Interpretation:

- **governance pain:** real;
- **Resume Gate fit:** partial;
- **warning:** generic policy/guardrail products are a broader and more crowded market than our current wedge.

## What is repeated vs what is not

### Repeated across frameworks

1. **Human approval / interruption creates a durable execution boundary.**
2. **Resume can occur in a different process or deployment.**
3. **The resumed state may carry assumptions from the earlier execution context.**
4. **Bad resume behavior is often delayed:** the checkpoint loads successfully and failure or unsafe action appears later.
5. **Frameworks increasingly add fail-closed rules around ambiguous replay.**
6. **External authority is not equivalent to persisted state.**

### Mostly framework-internal

- checkpoint/write ordering;
- event ordering;
- interrupt ID routing;
- session append atomicity;
- serialization implementation bugs;
- exactly-once task execution.

Resume Gate should not become a workflow engine in order to chase these.

## Is the problem frequent enough?

Public evidence supports **recurrence**, not frequency.

We can now point to independent concrete failures or feature requests in LangGraph, Microsoft governance tooling, OpenAI Agents SDK, Google ADK and CrewAI. That is enough to reject the hypothesis that the problem is unique to one framework.

It is **not** enough to claim:

- a high incident rate in production;
- a large budget;
- enterprise willingness to buy;
- that resume drift is among the top agent-platform pains.

Without interviews or telemetry, those remain unknown.

## Is the problem costly enough?

The public failure modes include credible high-cost consequences:

- privileged action proceeds after an expected confirmation gate is skipped;
- revoked/removed capability remains represented in persisted state;
- external side effects can be replayed or duplicated;
- a durable conversation/session can become permanently unusable;
- deployment/schema changes can strand existing long-lived threads.

These establish **severity potential**, not economic frequency.

## Are vendors already solving it?

### Yes, for framework-local correctness

OpenAI's current RunState/Session semantics increasingly encode explicit recovery and unrecoverable-state rules.

LangGraph, Google ADK and other frameworks continue to fix checkpoint, replay and HITL bugs in-core.

This means a product whose pitch is merely:

> "make agent resume reliable"

is likely to be absorbed by the runtimes.

### Not completely, for external validity

A framework can restore its own state, but it cannot generically decide whether:

- the approver still has authority;
- the approval has expired or been revoked;
- a tool is still permitted by current organizational policy;
- the external resource still has the same status;
- an old thread created under deployment A should execute under deployment B;
- a cross-framework agent handoff preserves the same authority semantics.

That is the residual product boundary.

## Product thesis after this evidence

Do **not** position Resume Gate as:

- durable execution;
- checkpoint repair;
- exactly-once execution;
- generic agent guardrails;
- agent observability.

Position the hypothesis as:

> **A pre-execution compatibility and authority check for persisted agent state.**

Or more concretely:

> **Before a long-running agent resumes, verify that the checkpoint is still compatible with current code, tools, policy and authority.**

## Competitive implication

The biggest strategic risk is **native absorption**.

If every runtime independently adds the equivalent of:

- deployment fingerprints;
- approval expiry/revalidation;
- current tool-policy checks;
- external dependency freshness;
- fail-closed resume hooks,

then an independent Resume Gate has little value.

The independent product earns its place only if a common validity contract can work across runtimes and external policy/identity systems better than each framework's local implementation.

## Next falsifiable milestone

**Do not add new validator rules.**

Build exactly one second framework adapter using the unchanged validity model.

Recommended target: **OpenAI Agents SDK**.

Why:

1. it has a first-class serializable `RunState` resume boundary;
2. its current docs explicitly distinguish durable state from application-owned repair/identity responsibilities;
3. recent approval/session bugs demonstrate the same broad lifecycle;
4. it is architecturally different enough from LangGraph to test whether Resume Gate is really cross-framework;
5. vendor-native recovery is improving quickly, so a successful adapter must demonstrate value specifically in **external current validity**, not duplicate OpenAI's own session reconciliation.

### Milestone question

> Can the same Resume Gate model, with no new verdicts or case-specific rules, prevent an OpenAI Agents SDK `RunState` from executing an approved tool after current tool/policy/authority state has changed?

### Pass

- same validator;
- same manifest vocabulary;
- thin OpenAI adapter;
- real serialized pause/resume test;
- authority/tool drift blocked before tool execution;
- integration remains small enough to be plausibly adopted.

### Kill / narrow further

If the adapter requires OpenAI-specific semantic rules in the core validator, or if the SDK already exposes an equivalent native current-validity gate that covers external authority cleanly, the cross-framework product thesis weakens materially.

## Decision

**Proceed to the OpenAI Agents SDK adapter as the next and only implementation milestone.**

This is no longer justified by novelty.

It is justified by a narrower empirical question:

> Is resume-time validity a reusable cross-framework layer, or merely a collection of framework-specific bugs and policies?
