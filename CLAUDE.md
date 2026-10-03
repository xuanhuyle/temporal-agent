# Claude Code Instructions

You are working in an experimental benchmark repository.

## Objective

Test, rather than assume, whether explicit temporal navigation gives long-lived agents an advantage over strong checkpoint + RAG memory.

Read `EXPERIMENT.md` before changing code.

## Critical rules

1. **Do not implement Tesseract until the world, harness, and evaluator are frozen.**
2. **Do not optimize the benchmark for the temporal contestant.**
3. Ground-truth labels must never be exposed through contestant interfaces.
4. Baseline must be strong and configurable, not intentionally weak.
5. Both contestants must use the same model, tools, events, and task budgets.
6. Never silently change a frozen scenario after observing contestant performance.
7. When fixing benchmark bugs, distinguish benchmark fixes from contestant improvements in commits and reports.
8. Preserve all failed runs and traces.
9. Prefer deterministic infrastructure where possible.
10. Add tests for leakage, isolation, ordering, scoring, and reproducibility.

## Current milestone

Build only:

- seed software world;
- chronological event format;
- event application engine;
- common Agent interface;
- dummy/no-memory agent;
- evaluator;
- replay traces;
- 10-event smoke scenario.

Do not import prior Tesseract code in this milestone.

## Definition of done

`pytest` passes and one command can run the smoke scenario end-to-end and write:

- run metadata;
- per-event agent actions;
- scoring output;
- token/cost placeholders;
- replayable trace.

Before coding, write a short implementation plan in the response. After coding, run tests and summarize any assumptions or deviations from `EXPERIMENT.md`.
