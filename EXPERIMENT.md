# Experiment: Temporal Navigation vs Strong RAG

Status: **Protocol v0.1 — freeze before contestant implementation**

## 1. Hypothesis

A long-lived agent operating in a changing environment benefits from an explicit temporal-causal state space when later information changes the significance of earlier decisions.

The proposed capability is not simple recall.

The temporal agent should be able to:

1. **detect variance** — recognize that a new event may affect prior reasoning;
2. **traverse** — address and reconstruct the relevant past state;
3. **trace causality** — identify the assumption(s) and decision(s) affected;
4. **reconsider** — re-evaluate the historical decision using the correct historical information state plus newly arrived evidence;
5. **return to now** — apply the revised conclusion to the current system.

## 2. Null hypothesis

A strong checkpoint + RAG agent with the same model and tools can reproduce this behavior at comparable reliability and inference cost.

If the null survives, Tesseract should not be treated as a distinct agent architecture.

## 3. World

Use a small but realistic Python SaaS/backend repository with:

- authentication;
- database/persistence;
- billing or entitlements;
- external API integration;
- background jobs;
- tests;
- architecture decision records generated naturally during work.

The world evolves through **30–50 sequential tasks/events**.

No event should say "revisit decision X."

## 4. Event classes

The stream must contain both causal events and distractors.

Required causal patterns:

### A. Constraint disappears
An architecture choice is made because capability X is unavailable. Later X becomes available.

### B. Requirement changes
A later customer/product requirement invalidates an earlier design premise.

### C. Delayed evidence
A bug report or external fact arrives long after the decision it bears on.

### D. Retroactive fact
The agent learns at time T2 that the world changed at T1 < T2.

### E. Dependency evolution
A library/API limitation that caused a workaround is removed or changes semantics.

### F. Parked work
A task is blocked, becomes dormant, then a later event satisfies the dependency.

### G. Deep causal chain
New fact -> invalidates assumption -> affects decision -> affects workaround -> affects current behavior.

At least 50% of events should be irrelevant to any historical reconsideration.

## 5. Difficulty axes

Evaluate independently across:

- **History length:** short / medium / long
- **Distractor density:** low / medium / high
- **Causal depth:** 1 / 2 / 3+ edges
- **Temporal lag:** near / medium / far
- **Wording:** explicit / natural prose / indirect evidence

## 6. Agent equality constraints

Both contestants must use:

- the same foundation model;
- the same model settings;
- the same coding tools;
- the same current task/event;
- the same underlying repository state;
- the same wall-clock or step budget;
- the same permission to inspect their own persistent memory system.

Only the memory/runtime differs.

## 7. Baseline

The baseline must be deliberately strong, not a straw man.

Minimum:

- append-only raw event log;
- checkpointed current state;
- embeddings/vector retrieval;
- metadata filters for time/entity/file when available;
- configurable top-k retrieval;
- optional summary memory;
- decision records retrievable by semantic search.

Baseline configurations should include at least:
- RAG top-8;
- RAG top-32;
- RAG top-64;
- a long-context/replay condition where feasible.

## 8. Temporal contestant

The temporal contestant may use:

- immutable Chronicle;
- Historian proposals;
- deterministic verification;
- bitemporal facts;
- decision provenance;
- addressable historical states;
- causal edges;
- dormant/wake relationships;
- temporal traversal.

It may **not** consume evaluator ground truth.

## 9. Trigger protocol

After every event:

1. Apply event to both isolated worlds.
2. Give each agent the event.
3. Allow normal processing.
4. Ask no temporal hint.
5. Record any autonomous decision-reconsideration action.
6. Allow remediation if the agent chooses to reopen something.
7. Score only after both contestants have completed the step.

## 10. Ground truth

Evaluator-only ground truth records:

- whether an event should trigger reconsideration;
- which prior decision(s) are affected;
- causal path;
- historical facts available at decision time;
- later facts unavailable at decision time;
- acceptable remediation outcomes;
- whether abstention is acceptable.

Ground truth must live outside both agents' accessible context.

## 11. Primary metrics

### Temporal governance recall
```
correct affected decisions reopened
-----------------------------------
all decisions that should be reopened
```

### Reopening precision
```
correct affected decisions reopened
-----------------------------------
all decisions reopened
```

### False intervention rate
Negative-control events that cause an unnecessary historical intervention.

### Historical-state fidelity
Does the agent distinguish:
- what was true then;
- what it knew then;
- what it knows now about then?

### Present remediation success
Did revisiting history cause the current repo/task to be fixed correctly?

### Efficiency
- model input tokens;
- model output tokens;
- retrieval tokens;
- model calls;
- wall-clock latency.

### Topology integrity (temporal contestant)
- false fact edges;
- false entity links;
- false supersession edges;
- false decision dependencies;
- unsupported backdating.

## 12. Required reporting

Report results by:
- contestant;
- scenario;
- history length;
- distractor density;
- causal depth;
- temporal lag.

Do not report only averages.

Every failure should retain a replayable trace.

## 13. Kill / continue rules

### Kill distinctive-architecture thesis if
A strong baseline is statistically similar on:
- temporal governance recall;
- reopening precision;
- remediation success;

and has comparable total inference cost as histories scale.

### Continue if
The temporal contestant shows a persistent advantage that grows with at least one of:
- history length;
- causal depth;
- distractor density;
- temporal lag;

without a material increase in false-memory/topology rate.

## 14. Anti-overfitting rules

- Freeze scenario and ground truth before running contestants.
- Never patch a contestant and rerun the same test as if it were held out.
- New patches require a new held-out scenario set.
- Keep benchmark generation and contestant implementation separate.
- Do not let Tesseract-specific vocabulary appear in event text unless naturally justified.

## 15. First milestone

Build the **world + event runner + evaluator only**.

Do **not** implement or import Tesseract yet.

The milestone passes when:
- the seed software world runs;
- 10 initial events can be applied deterministically;
- evaluator-only ground truth is hidden from contestant interfaces;
- a dummy agent can complete a full run;
- metrics and replay traces are emitted.
