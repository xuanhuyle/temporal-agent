# Temporal Agent Benchmark

A controlled experiment to test whether making time an **addressable dimension of agent state** creates a measurable advantage over strong conventional memory.

This repository is intentionally a **benchmark first**. The Tesseract implementation is a contestant, not the benchmark designer.

> **Status (2026-10-03, Milestone 2.5 research reset): disposition A, Stop.**
> A review of 2025-2026 prior work found prior art for every NORTH_STAR
> concept and component mechanism; what remains is integration and untested
> effects. No residual hypothesis on the thesis was both distinct and cheap
> to test. The temporal-architecture program (Tesseract,
> new scenario families) has stopped on value-of-information grounds.
>
> This is **not** an EXPERIMENT.md §13 kill: §13 was never run. See
> [docs/m2.5-decision-record.md](docs/m2.5-decision-record.md) and
> [docs/residual-hypotheses.md](docs/residual-hypotheses.md).

## Fresh research branch: temporal multiplicity

A new, deliberately separate experiment now tests a smaller primitive: explicit agent state as a copyable and executable object.

The v0 kernel implements snapshot, fork, run and compare. Its first model-backed test compares strong full-history prompting against mechanically enforced epistemic isolation on hindsight-sensitive historical decisions.

Product framing: this is a **model-agnostic cognitive capability** injected into an agent runtime. The LLM provides reasoning; the capability provides operations over executable versions of agent state.

See [docs/temporal-multiplicity-kernel-v0.md](docs/temporal-multiplicity-kernel-v0.md). This does not reverse the Milestone 2.5 stop decision on the earlier Tesseract architecture.

## Core question

> When a new event changes the significance of an earlier decision, can an agent autonomously identify the affected historical decision, reconstruct what it knew at the time, reconsider it, and return to the present with a better action?

No prompt tells the agent which past decision to inspect.

## Contestants

1. **Baseline** — same model and tools, with checkpoints + strong RAG memory.
2. **Temporal** — same model and tools, plus Chronicle / Historian / Tesseract temporal navigation (stopped under M2.5 disposition A; never implemented).

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

See [EXPERIMENT.md](EXPERIMENT.md) for the frozen protocol and [docs/protocol-amendments.md](docs/protocol-amendments.md) for the amendments in force (protocol v0.2).

See [NORTH_STAR.md](NORTH_STAR.md) for the broader conceptual model of temporal agency that guides future research without changing the frozen benchmark.

## Repository layout

```
src/
  contestant_runtime/  # shared LLM agent loop used by every model-backed contestant
  baseline/       # strong conventional contestant: event log, checkpoints, hybrid RAG, summaries
  tesseract/      # temporal contestant stub; not implemented, deprecated under M2.5 disposition A
  harness/        # event runner, agent interface, tools, world history, commands,
                  # model gateway (fake / claude-cli / anthropic / replay), contestant processes, replay, CLI
  evaluation/     # ground truth, scorer, remediation checks, oracle, validation
world/
  seed_repo/      # software world under management
  events/         # chronological event stream
  ground_truth/   # evaluator-only labels
scenarios/
  smoke/          # smoke_v1: frozen 10-event machinery check (not held out)
  simple/ long_history/ high_noise/ deep_causality/   # planned families, deprecated (M2.5)
runs/             # generated experiment outputs (not source of truth)
results/          # archived runs referenced by reports (milestone-2: fake-model machinery checks only)
tests/
prompts/
```

## Quickstart

Requirements: Python ≥ 3.11 and `pytest` (the only dependency).

```bash
pip install pytest                      # or: pip install -e '.[dev]'
python -m pytest                        # full test suite
PYTHONPATH=src python -m harness smoke  # run the frozen 10-event smoke scenario with the dummy agent
```

The smoke command prints the run id and headline scores, and writes
`runs/<run_id>/` with `metadata.json`, `events.jsonl`, `actions.jsonl`,
`scores.json`, `trace.jsonl` (plus `evaluation.jsonl`, `process.jsonl`, `blobs/`,
`final_state/`, `MANIFEST.sha256`).

After `pip install -e .`, `tab-bench` is equivalent to `PYTHONPATH=src python -m harness`.

### Baseline smoke runs (Milestone 2)

There are two different commands. They are not interchangeable.

```bash
# 1. Machinery check. A deterministic fake model drives every baseline preset.
#    This proves the harness works. Its scores say NOTHING about baseline quality. CI runs it.
PYTHONPATH=src python -m harness smoke-baseline-fake

# 2. Real model run through the Claude Code CLI and your existing Claude login
#    (e.g. a Max subscription; no API key needed). Run it from a normal terminal,
#    not from inside a Claude Code session.
PYTHONPATH=src python -m harness claude-cli-check --model claude-opus-5-5     # one tiny call first
PYTHONPATH=src python -m harness smoke-baseline-claude --model claude-opus-5-5 --effort high
```

`smoke-baseline-claude` runs `baseline-k8`, `baseline-k32`, `baseline-k64` and
`baseline-full` in lockstep, under one model configuration. Add
`--agent baseline-k32` to run a single preset. Every model call is one
`claude -p` process and counts against your plan's usage limits. If the login
or the usage limit fails mid-run, the run stops and is marked failed, with its
outputs preserved. `--model-provider anthropic --model MODEL` (with
`ANTHROPIC_API_KEY`) remains available for later API-based runs.
Summarize any run with `PYTHONPATH=src python -m harness report runs/<run_id> --markdown`.

Archived Milestone 2 runs (fake model only, non-scientific) are in
[results/milestone-2/](results/milestone-2/README.md).

Other commands (all via `PYTHONPATH=src python -m harness ...`):

| Command | Purpose |
|---|---|
| `run --scenario PATH --agent dummy [--agent baseline-k32] [--model-provider fake\|claude-cli\|anthropic --model M]` | run agents in lockstep under one model configuration |
| `smoke-baseline-fake` / `smoke-baseline-claude --model M` | baseline presets on `smoke_v1`: machinery check / real model via the Claude CLI |
| `claude-cli-check --model M` | one tiny Claude CLI call (CLI, login, model) |
| `report runs/<run_id> [--markdown]` | scores, metered usage and tool calls of a run |
| `replay runs/<run_id>` | re-execute a recorded run and verify it reproduces exactly |
| `validate [--scenario PATH] [--static-only]` | lint, integrity, canary, world-suite and oracle solvability checks |
| `freeze --scenario PATH` | validate and freeze a draft scenario (refuses to re-freeze changed content) |

Design and file formats: [docs/milestone-1-design.md](docs/milestone-1-design.md) (world, harness, evaluator) and [docs/milestone-2-design.md](docs/milestone-2-design.md) (history, commands, model gateway, contestant processes, shared runtime, baseline).
Benchmark changes are logged in [BENCHMARK_CHANGELOG.md](BENCHMARK_CHANGELOG.md).

## Principle

**Do not improve Tesseract to fit a failing benchmark case.** Freeze a benchmark version, run both contestants, record the result, then decide whether a new experiment is warranted.
