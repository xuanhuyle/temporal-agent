# Temporal Agent Benchmark

A controlled experiment to test whether making time an **addressable dimension of agent state** creates a measurable advantage over strong conventional memory.

This repository is intentionally a **benchmark first**. The Tesseract implementation is a contestant, not the benchmark designer.

## Core question

> When a new event changes the significance of an earlier decision, can an agent autonomously identify the affected historical decision, reconstruct what it knew at the time, reconsider it, and return to the present with a better action?

No prompt tells the agent which past decision to inspect.

## Contestants

1. **Baseline** — same model and tools, with checkpoints + strong RAG memory.
2. **Temporal** — same model and tools, plus Chronicle / Historian / Tesseract temporal navigation.

The model, task stream, tool access, and evaluation conditions must otherwise be identical.

## Primary metrics

- Correct decision reopenings / decisions that should be reopened
- False reopenings
- Successful present-day remediation
- Historical-state reconstruction accuracy
- Context tokens / inference cost
- Latency
- False-memory / false-topology rate

## Kill criterion

If the strong baseline reaches statistically similar temporal-governance performance at comparable total inference cost, the distinctive Tesseract thesis is not supported.

See [EXPERIMENT.md](EXPERIMENT.md) for the frozen protocol.

## Repository layout

```
src/
  baseline/       # checkpoint + RAG contestant
  tesseract/      # temporal contestant (import only after protocol freeze)
  harness/        # event runner and common agent interface
  evaluation/     # scorer and metrics
world/
  seed_repo/      # software world under management
  events/         # chronological event stream
  ground_truth/   # evaluator-only labels
scenarios/
  simple/
  long_history/
  high_noise/
  deep_causality/
runs/             # generated experiment outputs (not source of truth)
tests/
prompts/
```

## Principle

**Do not improve Tesseract to fit a failing benchmark case.** Freeze a benchmark version, run both contestants, record the result, then decide whether a new experiment is warranted.
