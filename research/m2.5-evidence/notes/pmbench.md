# PM-Bench (arXiv:2607.12385) — primary-source notes

Paper: "PM-Bench: Evaluating Prospective Memory in LLM Agents", Genglin Liu, Saadia Gabriel (arXiv:2607.12385, listed in the 15-Jul-2026 arXiv digest).
Analyst date: 2026-10-03.

## IMPORTANT access caveat

The paper body (arXiv HTML/PDF) could NOT be read in this session:
- arxiv.org / alphaxiv / semanticscholar are blocked by egress policy.
- The session's WebSearch budget was already exhausted (tool returned "this session has used its web search budget (200 of 200)"),
  so no search-extract of the arXiv HTML page could be obtained.
- Probed GitHub-hosted paper-digest mirrors (InMatrix/ai-papers-reader, memgrafter/research-digests,
  emptymalei/swarm-notes-ts raw_papers) — none contain 2607.12385.

What follows is therefore based on:
(a) the ABSTRACT, taken verbatim from a GitHub-hosted arXiv daily digest (git clone);
(b) the AUTHORS' RELEASED CODE + DATA + 64 RUN LOGS (github.com/genglinliu/PMBench, git clone) — this is the primary
    artifact and everything about task structure, scoring, configurations and results below is code/data-verified;
(c) abstracts of two follow-up papers that use PM-Bench (secondary).
Anything that only the paper body would establish (exact definitions in prose, related-work positioning, paper tables,
human-study results, stated limitations) is marked UNVERIFIED.

## Sources and how obtained

| # | Source | How obtained |
|---|---|---|
| S1 | https://github.com/CSQianDong/Awesome-arXiv-Daily-Reporter — file `15-Jul-2026/AI/README.md` lines 300-306 and `15-Jul-2026/AI/papers.jsonl` line 34 (commit 4d0c5775b7379a8b913468c4c14e661bd7928258) | `git clone --depth 1 --filter=blob:none --sparse`, sparse-checkout `15-Jul-2026`. Local: `scratchpad/lit/repos/csq_daily/` (an older unversioned copy also in `scratchpad/lit/repos/pf/daily/15-Jul-2026/AI/README.md:300-306`) |
| S2 | https://github.com/genglinliu/PMBench (commit e1093c470c8981daf522d4ef047a7c3a71e077d7, 2026-07-13) | Found by `git ls-remote` on candidate names (genglinliu/PMBench and genglinliu/pmbench resolve; PM-Bench/pm-bench do not), then `git clone --depth 1`. Local: `scratchpad/lit/repos/genglinliu_PMBench/`. README line 1 "# PM-Bench" and line 8-10 say it contains "the deterministic v9 scenario used in the paper, all eight evaluated agent configurations, the 64 reported runs". Linking repo<->paper is by README content + author name; the arXiv page's code link itself was not seen. |
| S3 | arXiv:2609.01272 "Making Prospective Memory SLM-Shaped: Typed Intention Stores for Small-Model Agents" (Zhao, Wu) abstract | Same digest repo, `2-Sep-2026/AI/README.md:139-145` (sparse checkout) |
| S4 | arXiv:2609.37125 "When Should Agents Check External State? Budgeting Observations for Stored Intentions" (Di et al.) abstract | Same digest repo, `30-Sep-2026/AI/README.md:779-785` |
| S5 | IAAR-Shanghai/Awesome-AI-Memory list entry (Chinese one-line summary) | previously cached at `scratchpad/lit/verify/awesome/iaar.tsv:856` |

## Verbatim: abstract (S1, 15-Jul-2026/AI/README.md:306)

> "A significant challenge in agentic AI is prospective memory: the ability to execute an intention at a specific future
> cue or state while other activities are ongoing. We introduce PM-Bench, a text-based benchmark for measuring prospective
> memory capabilities in modern LLM agents. Inspired by the Virtual Week paradigm from cognitive science, PM-Bench evaluates
> how well LLM agents maintain user intentions, execute delayed intentions, and monitor latent environment changes. Over the
> course of a simulated seven-day week, agents must continue an ongoing activity while deciding whether any deferred task is
> due. We compare eight state-of-the-art LLMs on PM-Bench under eight different agent configurations. PM-Bench proves
> challenging across all settings: the best method, a GPT-5.4 agent, reaches only 65.1\% F1 score under our evaluation.
> Furthermore, no single strategy for improving prospective memory dominates across models. We release PM-Bench as a
> controlled testbed for diagnosing these failures and developing training or inference-time interventions that support
> reliable prospective behavior."

Definition of prospective memory used (abstract): "the ability to execute an intention at a specific future cue or state
while other activities are ongoing." Code system prompt (S2 `sim/pm_bench.py:1282-1295`):

> "You are taking a prospective memory evaluation that assess how you remember to do things later. ... Your goal is to
> remember to perform tasks at the correct time or event without reminders.
> You must voluntarily remember to perform tasks at the right moment. If you are unsure, you may still act; that is
> allowed. No reminders will be given for missed tasks.
> Some cues will cancel, override, or reschedule tasks. Always follow the most recent instruction for any task."

and (`sim/pm_bench.py:1304-1310`):
> "Some tasks are triggered by state cues that are NOT shown in the vignette. You can only observe these cues by
> proactively querying state channels. ... No reminders will be given about when to query state; you must decide when to check."

## Repo README (S2, README.md:3-10)

> "PM-Bench is a text-based benchmark for prospective memory in LLM agents. It places an agent in a seven-day simulated
> week where the agent must continue an ongoing activity while remembering delayed intentions, reacting to updates, and
> deciding when to query hidden state channels.
> This release contains the benchmark and scoring runtime, the deterministic v9 scenario used in the paper, all eight
> evaluated agent configurations, the 64 reported runs, and the frontend-only human evaluation interface."

Note: README:25 and :129 refer to `runs/March_ALL_results_v9/`, but the released directory is `runs/all_results_v9/`.

## Task structure — verified from data/synthetic_week_v9.json (S2) with a python count script

- One scenario only: `scenario_name "synthetic_week_v9"`, 7 days (Mon-Sun), **80 steps** total (13,13,10,11,12,10,11).
- **83 intention instances**: type `event` 57, type `time` 26 (no `time_check` in v9).
  - event cue channel: `narrative` 42; hidden state channels 15 (appointment_portal 3, library_hold 3, calendar 3,
    email 2, bank_balance 2, course_portal 1, shipment_status 1).
  - `regular` 28 (= daily antibiotic at breakfast/dinner + asthma meds 11:00/21:00 × 7 days; header at
    `pm_bench.py:430-434`), irregular 55.
  - `cross_day` 7 with `cross_day_offset` 1-3 days; `depends_on` 0 (dependency logic exists in code, unused in v9).
  - encoding: `start` 71 (listed in the day's start_instructions or carried from an earlier day), `step` 12 (introduced mid-day).
- **11 updates**: reschedule 6, override 3, cancel 2; cross-day updates 0 (all target the same day).
- Ground truth: 51 steps with ≥1 due task, 81 due actions (83 − 2 canceled).
- Time is hidden by default: `"time_visible_by_default": false`, all `state_visibility` false → all 26 time-based
  intentions require `check_time`/`query_state clock` to time correctly.
- Scorer's monitoring split (from rescoring a run): "no-proactive" (narrative cue) total 42; "proactive-required" total 39
  (= 24 clock + 15 non-clock hidden channels).
- Distractors: per-day lure catalog of 10-12 irrelevant actions (`week_builder_v9.py:1171-1172`), 3 sampled into each
  step menu (`STEP_LURE_DISPLAY_COUNT = 3`, `pm_bench.py:437`); after an override the OLD cue still appears later
  (e.g. Monday `hardware_counter_d1`: override at step 1, old cue at step 5, new-cue due at step 6).
- Ongoing activity: each step offers options A/B/C; the choice is required to advance but is NOT scored
  (score_day, `pm_bench.py:2266-2583`, never reads `action["choice"]`).
- Delays: within-day (cue/time later in the same day) and cross-day (1-3 days, encoded as a narrative note on an earlier
  day: `week_builder_v9.py:1615-1627` "You leave yourself a note: On {target_day}, {label}").

Example cross-day encoding in data (Wednesday d3_s2 text): "You leave yourself a note: On Friday, Carry the laundry soap when you notice the laundry room cart."

### Agent interface per step (pm_bench.py run_llm, 1697-2203)
- Prompt per step = vignette text + A/B/C options + "Step action menu" (`pm_bench.py:1906-1914`).
- The step menu shows **all active, non-completed tasks (including canceled ones) + 3 lures**, shuffled, under
  anonymous per-day handles `task_N` (`build_step_action_menu`, `pm_bench.py:649-695`; docstring at 657-661):
  > "Canceled tasks remain visible so selecting them can be scored as a cancellation memory failure; completed tasks are hidden."
  Consequence (my inference from code): the agent does not have to free-recall WHAT intentions exist — the menu lists
  them; the burden is recognizing WHEN each is due (cue/time), monitoring hidden channels, and applying updates.
- Actions: `choose` (A/B/C + task_ids), `query_state` (channel), `check_time`, optionally `set_heartbeat`.
- State channels: `snapshot` mode returns current value; `delta` mode returns events since the last query of that
  channel (`resolve_state_query_items`, `pm_bench.py:117-153`).

### Updates (the "later event changes an earlier commitment" mechanism) — `apply_task_update`, pm_bench.py:346-383
```
346 def apply_task_update(state, update, task_states=None, by_type=None, by_regular=None, metrics=None):
347     if state["completed"]:
348         return
349     action = update.get("action")
350     if action not in ("cancel", "reschedule", "override"):
351         return
```
- cancel → `mark_task_canceled` (+ cascade to `depends_on` dependents, `cancel_dependents` 325-344);
- override → new cue_id/label/action_text, resets cue_seen; reschedule → new target_time.
- `state["current"]` is overwritten in place; the original spec stays in `state["task"]`; intermediate versions are not kept.
- Updates to already-completed intentions are ignored (line 347-348) → the benchmark never asks the agent to reopen
  something already done.

All 11 updates in v9 (verified by script) arrive BEFORE the original due time/cue, and every update notice is explicit in
the vignette text, e.g. Tuesday d2_s6: "A short follow-up changes the timing for check in with your manager. The timing
shifts a little: check in with your manager moves to 15:55."; Wednesday d3_s4: "A quick message clears it: you do not
need to worry about calling the insurance desk today."; Friday d5_s2: "A later message changes what you should watch for
before you collect the dry cleaning. You should wait for the confirmation email before you collect the dry cleaning."

### Scoring — score_day, pm_bench.py:2266-2583; score_log 2586-2652
Docstring (2267-2273): "false_alarm: performed a task when no task was due or the task was inactive. commission: repeated
a task after it was already completed. wrong_content: performed a task when a different task was due."
Primary metric Set-F1 (micro over steps):
```
2422        # Exact-set diagnostic: +1 only when chosen set exactly matches due set, else -1.
2423        chosen_set = set(chosen_task_ids)
...
2430        metrics["set_tp"] += len(chosen_set & due_now)
2431        metrics["set_fp"] += len(chosen_set - due_now)
2432        metrics["set_fn"] += len(due_now - chosen_set)
```
Also: hit / late (event: within 1 step after cue, `EVENT_LATE_WINDOW_STEPS = 1`; time: within 60 min,
`TIME_LATE_WINDOW_MINUTES = 60`, lines 428-429) / miss; update_hit/late/miss/violation/canceled; cross_day hit/late/miss;
proactive-monitoring hit by channel; exact-set match; state-query counts. Selecting a canceled task → false_alarm +
update_violation (2458-2463). Ground truth is recomputed deterministically by re-simulating the scenario
(`compute_groundtruth_for_day`, 698-795) and checked against stored labels (`validate_groundtruth_labels`, 4051).

Reproducibility check I ran: `python3 sim/pm_bench.py validate --scenario data/synthetic_week_v9.json` → "Scenario OK";
`python3 sim/pm_bench.py score ... heartbeat-proactive-gpt-54-...jsonl` → "Set micro: TP 55 | FP 3 | FN 26 ... set_f1 79.1%"
(matches the released report).

### Agent configurations (S2 run_eval.py:22-29, report "Setup Definitions")
| Setup | What it is (code-verified) |
|---|---|
| single-baseline | `pm_bench.run_llm`; full chat history appended for the whole week (`messages` only appended, never pruned, 1749ff) |
| single-todo-ledger | `run_todo_ledger.py`: model must return a ledger each step (task_id, when, status pending/done/canceled, notes), ≤5 items (`MAX_LEDGER_ITEMS = 5`, line 38), re-injected each step; done items pruned; older messages pruned above est. 32k tokens (`_prune_messages` 315-333; `--max-context-tokens` default 32000) |
| heartbeat-proactive | run_llm with optional `set_heartbeat` (30/60 virtual min) |
| heartbeat-auto-60m / -30m | heartbeat auto-enabled each day |
| hier-union-query | coordinator + 3 subagents (event_watcher, status_watcher, update_watcher; `run_hierarchical_agent_union_query.py:47-60`); union of subagent-suggested state queries executed; header 1-10: "Subagent memory persisted as JSON files on disk (one latest version each). No rolling chat history." |
| hier-majority-vote / hier-unanimous-vote | OFFLINE replay: task selection recomputed from logged subagent votes (`replay_union_votes.py`); metadata records `source_union_run_dir` (line 254) |

TODO-ledger instructions verbatim (run_todo_ledger.py:40-56): "You must maintain a compact TODO ledger that tracks tasks to
do later. ... - when: string (exact time like \"11:00\", a cue like \"cue: breakfast\", or \"unknown\") - status:
\"pending\", \"done\", or \"canceled\" ... Hard limit: ledger must contain at most 5 items. ... Keep only tasks that still
matter; remove completed items immediately."

Heartbeat nudge content (channel_query mode, default) is computed from the simulator's internal task states
(pm_bench.py:1581-1595):
```
1581 def pending_proactive_channels_for_heartbeat(task_states, state_visibility):
1582     """Return sorted proactive channels for active, incomplete tasks."""
...
1587         if state.get("completed") or state.get("canceled"):
1588             continue
```
→ the heartbeat tells the agent which channels currently have pending, non-canceled monitored tasks (privileged env state,
though not exact cue timing). `task_reminder` mode (not default) gives action text + target times.

### Models (report Scope, runs/all_results_v9/experiment_output_comparison_report.md:6-7)
"Runs covered: 64 total (8 models x 8 setups). Models covered: GPT-5.3-Codex, GPT-5.4, Llama 3.3 70B Instruct, Mistral
Large 2512, Mistral Small 3.2 24B Instruct, Qwen3-14B, Qwen3-32B, Qwen3-8B." One run per (model, setup); no repeats.

### Results (report, setup-level table lines 27-35 and conclusions 420-428)
| Setup | Macro Set-F1 | Micro Set-F1 | Best model |
|---|---|---|---|
| single-baseline | 60.0% | 59.4% | GPT-5.3-Codex (78.9%) |
| single-todo-ledger | 62.8% | 62.8% | GPT-5.3-Codex (74.8%) |
| heartbeat-proactive | 65.1% | 65.0% | GPT-5.4 (79.1%) |
| heartbeat-auto-60m | 56.6% | 52.2% | GPT-5.3-Codex (74.8%) |
| heartbeat-auto-30m | 57.8% | 51.5% | Mistral Large 2512 (74.7%) |
| hier-union-query | 45.2% | 45.9% | Mistral Large 2512 (58.1%) |
| hier-majority-vote (replay) | 37.2% | 38.3% | Llama 3.3 70B (49.4%) |
| hier-unanimous-vote (replay) | 35.3% | 39.6% | Mistral Large 2512 (53.3%) |

Report conclusions verbatim (420-428): "1. Best overall Set-F1 in this V9 batch is `heartbeat-proactive` (macro Set-F1
65.1%)." ... "6. Clock monitoring remains far easier than non-clock monitoring. Even the best non-clock macro hit rate is
only 16.7%, far below the best clock macro hit rate of 67.7%."
Per-model best setups differ (GPT-5.4 heartbeat-proactive 79.1%; GPT-5.3-Codex single-baseline 78.9%; Llama
single-todo-ledger 72.5%; Mistral Large single-baseline 75.3%; Qwen3-8B heartbeat-proactive 71.9%; Qwen3-14B
single-todo-ledger 52.3%) — consistent with abstract's "no single strategy ... dominates across models".
Update metrics example (report "Cross-Day and Update Metrics"): GPT-5.4 single-baseline update hit/late/miss/canceled/total
= 5/1/3/2/11, violations 2; GPT-5.4 hier-union-query 1/0/8/2/11.

DISCREPANCY (unresolved): abstract says "the best method, a GPT-5.4 agent, reaches only 65.1% F1". In the released
report, 65.1% is the MACRO Set-F1 of heartbeat-proactive averaged over 8 models; the GPT-5.4 heartbeat-proactive run
itself scores 79.1% Set-F1 (re-verified by rescoring). The follow-up S3 abstract phrases it as "the best published
PM-Bench scaffold reaches only 65.1% Set-F1", consistent with the macro reading. Whether the paper's own table differs
from the released report could not be checked.

### Benchmark-integrity observations from code (my findings, not claims of the paper)
1. Ground-truth fallback in run_llm (used by single-baseline and heartbeat setups), pm_bench.py:1944-1953:
```
1944                except InvalidModelResponseError as exc:
1945                    # Keep long sweeps running even when a provider repeatedly
1946                    # returns empty/truncated structured outputs.
1947                    fallback_task_ids = sorted(due_now)[:MAX_ACTION_TASK_IDS]
```
   and the mapper accepts raw task IDs (2154-2157: `elif token in step_handle_to_id.values(): mapped_id = token`),
   so a step where the model fails all retries is credited with exactly the ground-truth due set. How often this fired
   in the released runs is unknowable from the release (prompt logs with FALLBACK_ACTION lines are not released).
2. Heartbeat (channel_query) hints derive from internal simulator state (see above).
3. Menu lists all active intentions → recognition, not recall, of intention content.
4. Majority/unanimous ablations cannot be re-derived from the release (their source `.debug.jsonl` files are not included;
   union-query run dirs contain only `.jsonl` and `.score.md`).
5. Single synthetic scenario, single run per cell, no variance estimates.

### Other repo features relevant to the 20-capability rubric
- Human-eval UI autosave/resume: `webapp/frontend/src/storage.ts:3-32` stores the whole `SessionRuntime` in
  localStorage (`pm_bench_frontend_autosave_v1`); App.tsx:102-107 saves after every change.
- UI debug "Back One Step": `rewindRuntimeToStep` (`engine.ts:2186-2217`) rebuilds runtime by replaying
  `log_entries.slice(0, boundedCount)`; App.tsx:317-326 replaces the runtime with it (the dropped step is discarded, not
  kept as a branch). Gated by "Allow stepping backward for debugging" (App.tsx:430).
- Per-step logs: run JSONL records per step only {day, step_id, choice, task_ids, check_time, state_queries, heartbeat
  flags} + a run_metadata header (model, backend, timestamps, duration) — no token/cost fields, no observations.
  TODO-ledger runs additionally write `.ledger.jsonl` with the ledger snapshot at every step (e.g. GPT-5.4 run line 1:
  `"ledger": [{"task_id": "task_14", "when": "11:00", "status": "pending", "notes": "asthma med"}, ...]`).
- `grep -i "predict|forecast|counterfactual|branch|fork|checkpoint|rollback|confidence|probab|uncertain"` over sim/*.py and
  webapp src: only hit is run_hierarchical_agent.py:86 "Prefer precision over guessing when uncertain." No forecasting,
  simulation, branching or probability machinery exists.

### Follow-up papers using PM-Bench (secondary; abstracts only)
S3 (2609.01272): "frontier LLMs still struggle: the best published PM-Bench scaffold reaches only 65.1% Set-F1. We argue
that this loop is schema-constrained state tracking rather than open-ended reasoning ... We propose the Prospective
Intention Store (PIS) that puts lifecycle logic in code ... On PM-Bench, DeepSeek-Chat with PIS reaches 82.9% Set-F1. On
Gemma-E2B, Set-F1 is only 4.2% without a store and at most 6.6% under seven retrospective memories, while PIS reaches 66.2%."
S4 (2609.37125): "Prospective memory allows an agent to retain an intention tied to a future condition, but the stored
intention does not reveal whether that condition currently holds. ... On PM-Bench, its Logistic scorer ... retains
99.9--100% of unconstrained quality with 42--54% fewer observations."

## Remembering a future intention vs predicting/simulating a future
PM-Bench is strictly about the former: holding a user-given intention ("do X when cue Y / at time T"), monitoring for
the cue (including hidden channels), applying explicit updates, and executing at the right step. Nothing in the
code or data asks the agent to predict what the world will look like, simulate consequences of actions, assign
likelihoods to futures, or derive requirements from a desired/feared future. "Future" in PM-Bench = a scheduled
trigger, not a modeled state. (Whether the paper discusses this distinction in prose: UNVERIFIED.)

## Does any task test noticing that a later event changes an earlier commitment?
Yes, in a narrow form: 11 explicit update notices (6 reschedule, 3 override, 2 cancel) change PENDING user intentions
later in the same day; scored via update_hit/miss/violation, with canceled tasks left in the menu as traps and old cues
still appearing after overrides. Not tested: implicit invalidation (the agent must infer that an event undermines an
earlier commitment without being told), changes to already-executed actions/decisions (updates to completed intentions
are ignored, pm_bench.py:347-348), reopening with evidence, or reasoning about what was known then vs now. No cross-day updates.

## Could not verify
- Anything in the paper body: the prose definition/taxonomy of prospective memory, how "Virtual Week" is adapted,
  related-work positioning, the paper's own results tables, the human evaluation (participants, scores), stated
  limitations and future work, whether the paper distinguishes prospective memory from forecasting.
- The source of the "GPT-5.4 agent ... 65.1% F1" phrasing in the abstract vs the repo (79.1% per-run, 65.1% macro).
- That the released repo is byte-identical to what the paper used (README claims so).
- Whether the ground-truth fallback (pm_bench.py:1947) fired in any released run.
- Which heartbeat message mode the released heartbeat runs used (run metadata does not record it; the launcher
  `run_all_setups.sh` sets no `--heartbeat-message-mode`, so default `channel_query` is likely).
- Author affiliation (not present in the digest metadata; not inferred).
