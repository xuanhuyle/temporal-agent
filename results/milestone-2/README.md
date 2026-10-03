# Milestone 2 smoke runs (machinery checks, not results)

> **These are not measurements of the baseline.** Every run here used the
> deterministic `fake` model backend (`fake-v1`). That test double picks its
> tool calls and reopens by hashing event ids (`docs/milestone-2-design.md`
> §7), not by reading anything. Its scores show only that the harness,
> runtime, baseline, evaluator and replay work end to end. They say nothing
> about how good the baseline is, and they must not be compared with any
> real-model run.
>
> Dense retrieval used lexical hash embeddings (`hash-ngram-v1`; protocol
> deviation D1), not a semantic embedding model.

No real-model contestant run has been made. The Claude CLI backend was used
during development only for one-call preflight and probe calls, never for a
benchmark run (see "Backends exercised" below).

## Contents

| directory | what | code |
|---|---|---|
| `final/` | Final run on the Milestone 2 code: all four baseline presets on `smoke_v1`. Includes its replay. | harness 0.3.1, evaluator 0.3.1 |
| `pre-review-trial/` | First trial run, made before the adversarial-review fixes. Kept because every run is preserved (CLAUDE.md rule 8). Superseded. | harness 0.3.0, evaluator 0.3.0 |

Each directory has:

- `run.tar.gz`: the complete run directory (trace, actions, events,
  evaluation, scores, metadata, blobs, final state, manifest). `final/` also
  has the replay run.
- `report.md`: `python -m harness report <run_dir> --markdown`.
- `cli_output.json`: what the command printed.

`final/` also has `replay_report.json` and the output of a second, fresh run
(`cli_output_second_fresh_run.json`).

## Commands

```bash
PYTHONPATH=src python -m harness smoke-baseline-fake            # writes runs/<run_id>/
PYTHONPATH=src python -m harness replay runs/<run_id>
PYTHONPATH=src python -m harness report runs/<run_id> --markdown

# Replay an archived run:
mkdir -p /tmp/m2 && tar -xzf results/milestone-2/final/run.tar.gz -C /tmp/m2
PYTHONPATH=src python -m harness replay "/tmp/m2/smoke_v1__baseline-k8+baseline-k32+baseline-k64+baseline-full__aba07cb294" --runs-dir /tmp/m2/replays
```

## Final run

Run id `smoke_v1__baseline-k8+baseline-k32+baseline-k64+baseline-full__aba07cb294`,
fingerprint `da8378699d053a471335c5b8b39a1da984308c620b8c847b3036fc610cfbbd02`,
status `completed`, protocol v0.2, about 20 s wall clock.

Reproducibility:

- A second fresh run in an empty directory gave the same run id,
  fingerprint and scores.
- Replay matched with no mismatches. The replay fingerprint
  (`f5e64f72…`), which leaves out the agents' private state tree, is equal
  for the original and the replay.
- Replaying the run extracted from `run.tar.gz` matches too.

Scores (fake model; **meaningless as evidence**):

| agent | recall | precision | FIR | fidelity | remediation | steps |
|---|---|---|---|---|---|---|
| baseline-k8 | 0.333 (1/3) | 0.2 (1/5) | 0.286 (2/7) | 0 | 0 (0/3) | ok: 10 |
| baseline-k32 | 0.333 (1/3) | 0.167 (1/6) | 0.429 (3/7) | 0 | 0 (0/3) | ok: 10 |
| baseline-k64 | 0.667 (2/3) | 0.286 (2/7) | 0.429 (3/7) | 0 | 0 (0/3) | ok: 10 |
| baseline-full | 0.333 (1/3) | 0.167 (1/6) | 0.429 (3/7) | 0 | 0 (0/3) | ok: 10 |

The presets differ only because the fake model reopens ids that happen to
appear in its context, and larger top-k shows it more ids. That is a
property of the test double, not of retrieval quality.

Measured usage (harness-metered; tokens use the fake backend's documented
estimate, `ceil(utf8_bytes / 4)` plus 4 per message; cost is 0 by
definition):

| agent | model calls | input tokens | output tokens | retrieval tokens (attributed) | embedding tokens | tool calls | commands |
|---|---|---|---|---|---|---|---|
| baseline-k8 | 59 | 174,527 | 1,706 | 92,446 | 36,903 | 72 | 2 |
| baseline-k32 | 59 | 429,831 | 1,772 | 347,894 | 36,928 | 72 | 2 |
| baseline-k64 | 59 | 736,854 | 1,823 | 654,943 | 36,953 | 72 | 2 |
| baseline-full | 49 | 252,247 | 1,551 | 173,458 | 35,640 | 72 | 2 |

Tool calls by tool, the same for every preset: `read_file` 53, `history`
10, `diff` 6, `run_command` 2, `list_files` 1. `embed` was called 24 times.
`baseline-full` makes 10 fewer model calls because it has no query
expansion.

What these numbers do show, and what a real run would also show:

- Context size scales with top-k as configured: k64 sends about 4.2 times
  the input tokens of k8.
- Every step finished `ok`, within budget.
- Every model, embedding, history and command call was metered and
  replayable.

## Pre-review trial run

Run id `smoke_v1__baseline-k8+baseline-k32+baseline-k64+baseline-full__2930382443`
(harness 0.3.0, evaluator 0.3.0), made at 2026-10-03T08:14Z, before the
adversarial-review fixes.

- Scores and call counts are identical to the final run.
- Input tokens are 2,769 lower per agent. The runtime's system prompt
  changed afterwards (the `read_lines` tool line and the revised guidance
  text).
- `uncached_cost_usd` did not exist yet.

## Backends exercised during development

| backend | used for | benchmark runs |
|---|---|---|
| `fake` | CI, these smoke runs, tests | yes (these, non-scientific) |
| `recorded` | every replay | yes (replays) |
| `claude-cli` | one-call preflights (`claude-cli-check`) and protocol probes, run by the developer session | none |
| `anthropic` | unit tests with a stubbed SDK client only | none; never called |
| `hash` embeddings | these runs and tests | yes |

The first real-model run is for the operator to make from a normal terminal
(see the top-level README):

```bash
PYTHONPATH=src python -m harness claude-cli-check --model claude-opus-5-5
PYTHONPATH=src python -m harness smoke-baseline-claude --model claude-opus-5-5 --effort high
```
