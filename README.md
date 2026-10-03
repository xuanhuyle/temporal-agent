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

See [EXPERIMENT.md](EXPERIMENT.md) for the frozen protocol.\n\nSee [NORTH_STAR.md](NORTH_STAR.md) for the broader conceptual model of temporal agency that guides future research without changing the frozen benchmark.

## Repository layout

```
src/
  baseline/       # checkpoint + RAG contestant (not implemented yet)
  tesseract/      # temporal contestant (import only after protocol freeze)
  harness/        # event runner, common agent interface, tools, replay, CLI
  evaluation/     # ground truth, scorer, remediation checks, oracle, validation
world/
  seed_repo/      # software world under management
  events/         # chronological event stream
  ground_truth/   # evaluator-only labels
scenarios/
  smoke/          # smoke_v1: frozen 10-event machinery check (not held out)
  simple/ long_history/ high_noise/ deep_causality/   # planned families
runs/             # generated experiment outputs (not source of truth)
tests/
prompts/
```

## Quickstart (Milestone 1)

Requirements: Python ≥ 3.11 and `pytest` (the only dependency).

```bash
pip install pytest                      # or: pip install -e '.[dev]'
python -m pytest                        # full test suite
PYTHONPATH=src python -m harness smoke  # run the frozen 10-event smoke scenario with the dummy agent
```

The smoke command prints the run id and headline scores, and writes
`runs/<run_id>/` with `metadata.json`, `events.jsonl`, `actions.jsonl`,
`scores.json`, `trace.jsonl` (plus `evaluation.jsonl`, `blobs/`,
`final_state/`, `MANIFEST.sha256`).

After `pip install -e .`, `tab-bench` is equivalent to `PYTHONPATH=src python -m harness`.

Other commands (all via `PYTHONPATH=src python -m harness ...`):

| Command | Purpose |
|---|---|
| `run --scenario PATH --agent dummy [--agent keyword:kw2] [--seed N]` | run reference agents in lockstep |
| `replay runs/<run_id>` | re-execute a recorded run and verify it reproduces exactly |
| `validate [--scenario PATH] [--static-only]` | lint, integrity, canary, world-suite and oracle solvability checks |
| `freeze --scenario PATH` | validate and freeze a draft scenario (refuses to re-freeze changed content) |

Design and file formats: [docs/milestone-1-design.md](docs/milestone-1-design.md).
Benchmark changes are logged in [BENCHMARK_CHANGELOG.md](BENCHMARK_CHANGELOG.md).

## Principle

**Do not improve Tesseract to fit a failing benchmark case.** Freeze a benchmark version, run both contestants, record the result, then decide whether a new experiment is warranted.
