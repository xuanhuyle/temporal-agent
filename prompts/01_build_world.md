# Task 01 — Build the benchmark world, harness, and evaluator

Read `README.md`, `EXPERIMENT.md`, and `CLAUDE.md` first.

## Goal

Implement Milestone 1 only. Do not implement Tesseract and do not build the RAG baseline yet.

Create:

1. a small realistic Python SaaS/backend seed application;
2. a versioned event schema;
3. a deterministic event application engine;
4. a common agent interface;
5. a dummy/no-memory agent;
6. evaluator-only ground truth loading;
7. a 10-event smoke scenario;
8. replay traces and machine-readable result output;
9. tests for ordering, isolation, leakage, scoring, and reproducibility.

## Seed application

Keep it small enough to understand completely but rich enough for later architectural decisions. Include:

- user authentication;
- SQLite persistence;
- subscription/entitlement logic;
- one external-provider abstraction;
- a background job;
- tests.

Avoid frameworks or dependencies that make the benchmark itself hard to run.

## Smoke scenario

The 10 events should include:

- at least 2 causal events that eventually require reconsidering an earlier decision;
- at least 5 distractors;
- one delayed observation;
- one parked dependency that later resolves.

The dummy agent does not need to solve these. The purpose is to prove the event stream and scoring machinery.

## Leakage requirement

The contestant-facing API must make it impossible to read evaluator ground truth accidentally. Add an explicit test that would fail if a contestant tool/path can access `world/ground_truth`.

## Output

A run should produce a directory such as:

```
runs/<run_id>/
  metadata.json
  events.jsonl
  actions.jsonl
  scores.json
  trace.jsonl
```

Use deterministic run IDs or seeds where practical.

## Definition of done

Run the full test suite locally.

Then report:

- files created;
- command to run smoke benchmark;
- test results;
- assumptions;
- any deviation from `EXPERIMENT.md`.

Do not proceed to baseline or Tesseract implementation.
