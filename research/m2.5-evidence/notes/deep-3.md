# Deep read 3: FutureSim — Replaying World Events to Evaluate Adaptive Agents (arXiv 2605.15188, 2026)

Authors (from the digest corpus): Shashwat Goel, Nikhil Chandak, Arvindh Arun, Ameya Prabhu, Steffen Staab, Moritz Hardt,
Maksym Andriushchenko, Jonas Geiping. The paper is dated 2026-05-14.

## Sources and evidence tiers

- **[ABS]** The arXiv abstract, verbatim, from the CSQianDong/Awesome-arXiv-Daily-Reporter digest
  (`repos/pf/daily/15-May-2026/AI/README.md`, line 934). The digest links to the PDF at https://arxiv.org/pdf/2605.15188.
  arxiv.org itself was blocked, and the WebSearch budget for this session was already exhausted (200/200), so no further
  queries could be run.
- **[REPO]** https://github.com/OpenForecaster/futuresim, cloned at `908322f` (2026-06-25) into
  `scratchpad/lit/repos/OpenForecaster_futuresim`. The first commit is dated 2026-01-11 and there are 152 commits.
  I read these files line by line:
  - `environment/scoring/base.py`, `environment/scoring/__init__.py`
  - `environment/env.py`, `environment/replay.py`, `environment/updater.py`, `environment/scorekeeping.py`
  - `environment/article_corpus.py`, `environment/data_loader.py`
  - `agents/minimalHarnessAgent/{agent.py, state.py, mcp_server.py}`
  - `agents/minimalHarnessAgent/prompts/{prompt.py, prompt_active_memory2.py}`
  - `agents/basicAgent/feedback.py`, `agents/search_tools/{handler.py, lancedb/store.py}`
  - `scripts/run_forecast_sim.py` (restart logic)
  - the `configs/minimalHarness/{badWarmup, goodWarmup, no_memory}` configs
- **[NOTE-3P]** Two third-party summaries, cached in `scratchpad/lit/pf_raw/`. Neither is used alone for any numeric claim.
  - InMatrix/ai-papers-reader `docs/2026-05-15/2605.15188.md`
  - emptymalei/swarm-notes-ts
- **Not read:** the full paper text and the blogpost (https://openforecaster.github.io/futuresim/; `*.github.io` is
  blocked).

## What it is ([ABS], verbatim)

> "we propose building grounded simulations that replay real-world events in the order they occurred. We build FutureSim,
> where agents forecast world events beyond their knowledge cutoff while interacting with a chronological replay of the
> world: real news articles arriving and questions resolving over the simulated period. We evaluate frontier agents in their
> native harness, testing their ability to predict world events over a three-month period from January to March 2026.
> FutureSim reveals a clear separation in their capabilities, with the best agent's accuracy being 25%, and many having worse
> Brier skill score than making no prediction at all. Through careful ablations, we show how FutureSim offers a realistic
> setting to study emerging research directions like long-horizon test-time adaptation, search, memory, and reasoning about
> uncertainty."

The README ([REPO]) describes the design:

> "It advances a dated question market, exposes only the information available at each simulated date, records agent
> forecasts, and scores them over time."
> "The environment owns dates, visible questions, visible article files, forecast ingestion, answer matching, and scoring.
> Agents own their retrieval strategy."

## Mechanisms in the code ([REPO])

### 1. Strict date gating of the external world

**Search cap.** `agents/search_tools/handler.py` computes
`allowed_max_date = current_date - timedelta(days=self._search_cutoff_days)` and caps any requested `to_date`. It tells the
agent: `"Note: maximum allowed search date is ... Your requested to-date ... was capped."`

**LanceDB filter.** `agents/search_tools/lancedb/store.py`:

```python
# Build date filter - max_date prevents future leakage
f"date <= timestamp '{max_ts}' AND (date_publish IS NULL OR date_publish <= timestamp '{max_ts}')"
```

**Article staging.** `environment/article_corpus.py` stages only the `articles/YYYY/MM/DD/` directories up to
`effective_max_date`, as symlinks. In freeze mode, `_copy_filtered_jsonl` drops articles whose
`article_date > cutoff_iso` or `publish_date > cutoff_iso`.

**Hidden ground truth.** `env.py::_get_safe_active_questions` returns
`[replace(q, ground_truth_answer="") for q in active_questions]`.

**Sandboxing.** The harness runs in a bwrap sandbox with `network_isolation: true` and an egress proxy, so the CLI agent
cannot browse the live web. The README says: "Sandboxes block general internet by default to avoid future leakage."

### 2. Append-only forecast history with as-of queries

`environment/scoring/base.py`:

```python
@dataclass
class PredictionHistory:
    """Track all predictions for a question."""
    # agent_id -> list of predictions (one per day they predicted)
    predictions: Dict[str, List[DailyPrediction]] = field(default_factory=dict)
    def add_prediction(self, pred: DailyPrediction): ... self.predictions[pred.agent_id].append(pred)
    def get_prediction_as_of(self, agent_id: str, target_date: date) -> Optional[DailyPrediction]:
        """
        Get agent's active prediction as of target_date (carry-forward).
        Returns None if agent hadn't predicted by target_date.
        """
```

`scoring/__init__.py::_get_snapshot_at(history, target_date)` builds an all-agent snapshot as of a date.
`resolve_question` integrates scores over the "change points" in that history, which gives a time-weighted Brier skill score.

Caveats:
- **The in-memory history is deleted when the question resolves.** `env.py::_resolve_question` ends with
  `# Clean up  del self.prediction_histories[q.qid]`. Only the final snapshot survives, in `resolved_agent_predictions`.
- **The durable record is the log file.** It is `actions.jsonl`, an append-only JSONL log (`SimLogger.log_prediction`,
  `log_resolution`). `replay.rescore` "Rebuilds prediction histories from actions.jsonl and replays all resolutions."
- **The as-of API is not exposed to the agent.**
  - The agent sees only its latest `my_prediction` / `my_prediction_date` columns in `market.csv`.
  - In the OpenReward integration it also gets read-only per-day files (`predictions/YYYY-MM-DD.json`, `chmod 444`).
  - The prompt text: "predictions/ — Read-only record of your past submissions, one file per day as
    `predictions/YYYY-MM-DD.json`."
  - I could not find where the local MinimalHarness path writes these per-day files. The OpenReward env writes them in
    `_upload_prediction_snapshot`.

### 3. Predicted-vs-realized feedback used for self-calibration

`agents/minimalHarnessAgent/mcp_server.py::_build_feedback_recap` renders the feedback:

```
## RESULTS SINCE YOUR LAST SESSION (...)
- "<title>"
  Your prediction distribution: {..} | Truth: <gt>
  Brier: +x.xx | TW-Score: +y.yy
## YOUR CUMULATIVE PERFORMANCE TILL TODAY
```

The prompt (`prompt.py:38`, `prompt_no_memory.py:33`) says:

> "Call `mcp__forecast__next_day` when done. You'll receive resolution feedback with your Brier score per question — use
> this to learn from mistakes and improve calibration."

The `active_memory2` end-of-day memory phase (`prompt_active_memory2.py::build_memory_update_prompt`) says:

> "### STEP 1: Extract lessons from resolved questions — If any questions resolved since your last session, create or update
> meta-insight lesson entries capturing what happened, why you were right or wrong, and the reusable rule you want future-you
> to apply."
> "### STEP 4: Cleanup — Delete stale per-question notes and stale meta-insights that future-you should no longer rely on."
> "If a prior meta-insight is now stale or contradicted, revise it with `mcp__forecast__memory_update` or remove it"

### 4. Daily read-only snapshots of the agent's memory (a partial historical epistemic state)

`mcp_server.py::_save_active_memory_for_today`:

> "Persist mem.csv + meta.yaml for the current sim date and chmod read-only."

It writes `workspace/memory/{date}/{mem.csv,meta.yaml}`, then runs `os.chmod(f, 0o444)` on the files and
`os.chmod(date_dir, 0o555)` on the directory.

The `mem_df` columns are `qid, question, last_updated, memory, category`, described as "per-question notes (reasoning,
evidence, calibration)". There is also a meta-insights layer of "reusable cross-question patterns, lessons, and calibration
rules".

The agent is told to read the previous day's memory: "Your prior `mem_df` is saved at `memory/{prev_iso}/mem.csv`
(read-only)". The other dated directories stay in the workspace.

### 5. Resume, restart-from-day, and bootstrap (experimenter-level checkpoint and fork)

**Resume.** `replay.restore_state` restores from the log:

> "Restore simulation state from actions.jsonl in the resume directory. Rebuilds: prediction_histories (active),
> agent_scores (resolved), resolved_questions list, q_pool (mark questions as processed), current_date (set to
> last_seen_date + timegap_days)"

**Restart from a day.** `scripts/run_forecast_sim.py::prepare_restart_directory` builds a new run directory:

> "Prepare a new output directory for restarting a simulation from a specific day. Copies: actions.jsonl entries with
> sim_date < restart_day; Memory snapshots with date < restart_day; Matcher cache"

- It creates a new directory, `create_output_dir(args.sim_name + "_restart", ...)`, so the original run is preserved.
- It records provenance with `save_config(output_dir, args, {'restart_source': args.restart_from, 'restart_from_day':
  args.restart_from_day})` and copies the parent config as `source_config.json`.
- README: `python scripts/run_forecast_sim.py --restart_from /path/to/original/run --restart_from_day 2025-04-05`.

**Bootstrap.** `agents/minimalHarnessAgent/state.py::_apply_bootstrap` seeds a new run from a fixed Day-0 state: it copies
`mem.csv` and `meta.yaml` and injects `prediction.json` into the env histories. The configs use this for controlled
counterfactual comparisons from an identical starting state.

From `configs/minimalHarness/no_memory/..._nomemory_from_activemem2_day1.yaml`:

> "Purpose: compare active_memory2 vs no_memory with the same starting point."

From `configs/minimalHarness/badWarmup/*`:

> "bootstrapped from the qwen3.6-plus AllQ warmup output"

From `configs/minimalHarness/goodWarmup/*`:

> "goodWarmup was built from the Codex GPT-5.5 active_memory2 run's Day 0 artifacts"

[NOTE-3P] (InMatrix) describes the matching paper experiment:

> "the researchers intentionally gave models a bad initial prediction—one made by a weaker model—to see if they could correct
> it. They found that even when the agents were presented with overwhelming evidence that the initial guess was wrong, they
> struggled to move their 'Brier Skill Score' ... back into positive territory ... 'anchored' to their first thought."

This summary is third-party and I could not verify it against the paper text.

### 6. Revision pressure and a revision metric

The handholding v2/v3 text in `mcp_server.py::next_day` says:

> "N question(s) are still active. Re-read market.csv, scan today's news, and resubmit any forecast where new evidence has
> shifted your view before calling next_day again. A forecast is never "done" while its question is still active."

The v3 text adds:

> "**IMPORTANT**: N question(s) resolve tomorrow ... stale forecasts might hurt your performance."

The metric `avg_submission_tv_to_prev` (in `scorekeeping.build_metrics_list`) is the total-variation distance between an
agent's consecutive forecasts on a question. It measures how much a belief was revised.

## Capability ratings (only what FutureSim itself provides)

| # | Capability | Rating | Evidence |
|---|---|---|---|
| 1 | immutable_historical_observations | yes | Dated article corpus staged read-only by date. `actions.jsonl` is an append-only log of predictions and resolutions. Daily memory snapshots are chmod 0o444. Immutability is by convention and file permissions, not cryptography. |
| 2 | historical_world_state | yes | At sim date t the agent sees exactly the articles ≤ t (search capped, files staged ≤ t), the active questions and the resolutions ≤ t. The world is the information set, not a mutable world model. |
| 3 | historical_epistemic_state | partial | `get_prediction_as_of` reconstructs the agent's forecast at t (scorer side). Per-date read-only `memory/{date}/` snapshots and per-day `predictions/` files preserve notes and forecasts. Restart truncates memory to < t. There is no agent-facing "what did I believe at t, and why" interrogation and no known-then vs known-now distinction. |
| 4 | historical_policy_objective_state | partial (weak) | The run config is frozen in `config.json`, and on restart `source_config.json` is kept. The agent-authored "calibration rules" (meta-insights) are versioned per day in `meta.yaml`. There is no model of goals or instructions changing over time. |
| 5 | execution_checkpoints | partial | `--resume` rebuilds env state from `actions.jsonl` plus memory directories, at day granularity. The CLI session can be resumed (`codex_resume`, `claude_code_resume`). The agent's in-context state is not snapshotted. |
| 6 | replay | yes | The core design is a chronological world replay. `replay.rescore` replays all resolutions from the log. `--restart_from_day` re-runs from a past day. |
| 7 | fork_from_historical_state | yes | `prepare_restart_directory` creates a new `_restart` directory from the state before day D and leaves the original intact. `bootstrap_dir` forks several configs from one Day-0 state. |
| 8 | counterfactual_action_branches | partial | Only at experimenter level: the same starting state is run with different memory or prompt modes, or with good vs bad warmup predictions. The agent cannot branch its own actions without committing. |
| 9 | branch_provenance | partial | `config.json` gets `restart_source` and `restart_from_day`, and `source_config.json` is copied. Bootstrap configs name the `bootstrap_dir`. There is no structured lineage or recorded reason beyond YAML comments. |
| 10 | explicit_current_belief_state | partial | Current per-question probability distributions (`my_prediction`, `my_prediction_date`) plus `mem_df` per-question notes with `last_updated` and meta-insights. There is no assumption or requirement layer. |
| 11 | uncertainty_representation | yes | Each forecast is `{outcome: prob}` over at most 5 outcomes, with sum ≤ 1, scored by a proper Brier rule. |
| 12 | future_state_rollout | no | Agents forecast outcomes. They do not simulate future states conditioned on their own actions. |
| 13 | multiple_prospective_branches | partial | Up to 5 mutually exclusive outcomes per question are held at once. These are outcome alternatives, not world-state branches. |
| 14 | probability_over_futures | yes | Probabilities over future resolutions, scored over time (time-weighted Brier skill). |
| 15 | backward_requirements | no | Nothing derives present obligations from desired or feared futures. |
| 16 | intervention_aware_forecasting | no | The replay is fixed real history and agents cannot affect outcomes, so forecasting is purely passive. |
| 17 | prevented_futures_preserved | no | There are no interventions. Every forecast is scored against the realized truth. |
| 18 | predicted_vs_realized | yes | Per-resolution feedback ("Your prediction distribution: {..} \| Truth: .. Brier ..") plus the prompt "use this to learn from mistakes and improve calibration", and a lesson-extraction memory step. |
| 19 | cross_time_state_querying | partial | `get_prediction_as_of(agent_id, target_date)`, `_get_snapshot_at`, and a TV-distance diff between consecutive forecasts. These cover forecasts only, are used by the scorer and not exposed to the agent, and the in-memory history is deleted on resolution (the log keeps it). There is no general `state_at(t)` or `diff(t1,t2)`. |
| 20 | unified_temporal_abstraction | no | Separate mechanisms for each concern: article date-gating, PredictionHistory, memory directories and restart directories. There are no counterfactual or prospective states in a shared abstraction. |

## How this threatens the project's novelty

1. **Strict epistemic cutoff is ordinary benchmark plumbing.** FutureSim enforces "no hindsight" for the world state through
   four mechanisms: date-capped search, date-staged files, hidden ground truth and a network-isolated sandbox. The project
   cannot claim "replay with a strict epistemic cutoff" as new infrastructure. It is FutureSim's core design, published with
   code (and preceded by ForecastBench-style pastcasting).
2. **The as-of forecast ledger and predicted-vs-realized loop already exist.** FutureSim has an append-only per-agent
   forecast history, an as-of query, time-weighted scoring over change points, and per-resolution "distribution vs truth +
   Brier" feedback that the agent is told to use for self-calibration. It also has a lesson-extraction step that asks "why you
   were right or wrong". So "compare predicted vs realized futures and learn from it" is not novel, at least in forecasting.
3. **Fork and replay from a historical day is implemented** (`--restart_from --restart_from_day`), with minimal provenance
   (`restart_source`, `restart_from_day`) and the original run preserved. The project's "never overwrite time, fork it"
   principle is matched at experimenter level.
4. **The badWarmup/goodWarmup bootstrap is the closest analog to the project's benchmark construct.** The agent inherits
   earlier (bad) commitments and has to notice that incoming evidence makes them wrong, then revise. The prompt pushes this
   explicitly: "A forecast is never 'done' while its question is still active". The revision metric
   (`avg_submission_tv_to_prev`) measures it. The third-party summary says agents anchor and fail to recover. This is
   empirical evidence on a "reopen and remediate an earlier decision" task, in forecasting form. A reviewer could argue that
   the project's benchmark is FutureSim's anchoring test moved to a software-world setting.
5. **It is a ready, strong baseline harness.** FutureSim compares memory modes (no_memory, active_memory, active_memory2)
   from the same starting state. "Strong memory + daily feedback" is therefore an existing, tested contestant design. The
   project's temporal contestant would need to beat this kind of baseline, not a weak one.

## What FutureSim does not cover

- **Agency over the world.** The world is fixed history and the agent cannot intervene. So it has no
  intervention-aware or policy-conditioned forecasting, no reflexive forecasts, and no prevented-futures bookkeeping
  (capabilities 15–17 are all "no").
- **Prospective simulation.** It has no rollout of future states conditioned on actions, no imagined branches beyond
  outcome distributions, and no backward requirements.
- **Agent-facing temporal interrogation.** The as-of API is used by the scorer, not offered to the agent as a tool. The
  agent reads its latest prediction and its memory directories. It is never asked to separate "what I knew then" from "what I
  know now" when judging a past decision.
- **Significance shift of past decisions.** FutureSim questions are independent forecasts. Nothing tests whether a later
  event changes the meaning of an earlier, already-executed action with lasting consequences (a remediation obligation). The
  task is "update an open forecast", not "reopen a closed decision and remediate side effects".
- **Identity, objective or policy drift tracking.** None, beyond per-run config and daily meta-insight snapshots.
- **A unified temporal state abstraction.** It does not unify historical, actual, counterfactual and prospective states.
  Each mechanism is purpose-built.
- **Truly immutable history in memory.** The in-memory history is deleted on resolution, and the immutable record is a JSONL
  log.

## Could not verify

- The full paper text: per-model numbers beyond the abstract (25% best accuracy; "many having worse Brier skill score than
  making no prediction"), the exact ablations, and whether the badWarmup anchoring result appears in the paper as InMatrix
  describes it.
- The model names (GPT-5.5, Claude Opus 4.6, DeepSeek V4 Pro) come from the third-party summary and from repo config file
  names, not from the paper.
- Whether the local MinimalHarness path writes the per-day `predictions/YYYY-MM-DD.json` files. The prompt advertises them
  and the OpenReward path writes them; I did not find a local writer.
- The blogpost (openforecaster.github.io/futuresim) was not readable.
