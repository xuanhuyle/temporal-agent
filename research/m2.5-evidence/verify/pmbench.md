# Verification of PM-Bench analysis (adversarial pass, 2026-10-03)

Repo: scratchpad/lit/repos/genglinliu_PMBench (commit e1093c470c8981daf522d4ef047a7c3a71e077d7, 2026-07-13), re-read independently.
Paper body: NOT readable. WebSearch returned "this session has used its web search budget (200 of 200)"; arxiv.org blocked.
Abstract re-checked verbatim at scratchpad/lit/repos/csq_daily/15-Jul-2026/AI/README.md:300-306 and papers.jsonl:34.

## Independently re-verified facts
- Scenario counts (python over data/synthetic_week_v9.json): 7 days, 80 steps, 83 tasks (event 57 / time 26), cross_day 7,
  11 updates (reschedule 6, override 3, cancel 2), time_visible_by_default False.
- Rescore: `pm_bench.py score --scenario data/synthetic_week_v9.json --log runs/all_results_v9/gpt-54/heartbeat-proactive-.../...jsonl`
  -> "Set micro: TP 55 | FP 3 | FN 26", "set_f1 79.1%". Matches analyst.
- apply_task_update (pm_bench.py:346-383): `if state["completed"]: return`; overrides/reschedules overwrite state["current"][...] in place.
- resolve_state_query_items (pm_bench.py:117-153): clock/snapshot = current value; delta = events from last_query_step+1 to now. No t argument.
- run_llm baseline: `messages` created at 1749 and only `.append`ed afterwards (grep shows no other assignment/del). Append-only transcript confirmed.
- Ground-truth fallback (pm_bench.py:1944-1953): `fallback_task_ids = sorted(due_now)[:MAX_ACTION_TASK_IDS]`; mapper accepts raw ids (2154-2157). Confirmed.
- Prompt log per step (1925-1930) writes full `messages` each step (not released).
- make_run_metadata (214-236): mode, timestamps, duration, entry_count, model, backend only.
- TODO ledger (run_todo_ledger.py:38-56): MAX_LEDGER_ITEMS=5; when = time | "cue: X" | "unknown"; "keep the 5 most urgent/likely"; _prune_messages 318-335.
- Subagent schema (run_hierarchical_agent_union_query.py:458-520): focus, state_query_suggestions{channel,reason}, tasks_might_be_due{task_handle,evidence,pending_state_queries}, optional tasks_should_not_select. Header 1-10: "Subagent memory persisted as JSON files on disk (one latest version each). No rolling chat history."
- UI: storage.ts saves whole SessionRuntime to localStorage key pm_bench_frontend_autosave_v1; rewindRuntimeToStep (engine.ts:2186-2217) rebuilds from log_entries.slice(0,n); App.tsx:317-326 handleStepBack replaces runtime (gated by allow_backtrack_debug).
- replay_union_votes.py:245-255: new run metadata with `source_union_run_dir` and mode label; original run untouched.
- Menu (pm_bench.py:658-661 docstring): "Canceled tasks remain visible ... completed tasks are hidden."
- Heartbeat channel hint (1581-1595) computed from privileged simulator task_states.
- Keyword grep (predict|forecast|counterfactual|branch|fork|checkpoint|rollback|confiden|probab|uncertain) over sim/*.py + webapp/frontend/src:
  only run_hierarchical_agent.py:86 "Prefer precision over guessing when uncertain." No forecasting/branching machinery.

## Ratings: no changes
All 20 ratings are supported by the code. Borderline calls I considered and rejected:
- historical_epistemic_state partial: generous. Basis = unreleased per-step prompt logs (cutoff by construction) + released .ledger.jsonl snapshots. These are passive researcher logs; kept partial but weak.
- cross_time_state_querying no: delta channels give a since-last-query diff of external channels; t1 not addressable, current-time only. Kept no (closest analogue noted).
- branch_provenance no: replay-derived runs carry a parent pointer + mode label but are post-hoc re-scorings of logged votes, not state branches. Kept no.
- backward_requirements no: the closest analogue is deriving "query channel now" from a stored intention's trigger (pending_state_queries); trigger conditions are user-given, not derived from a desired/feared future. Kept no.
- uncertainty_representation partial: only 'unknown' and pending_state_queries; no confidence. Kept partial (weak).

## Minor corrections / additions to the analysis
- sim/run_eval.py:22-29 SETUP_CHOICES also includes `multi_baseline` (sim/run_hierarchical_agent.py, markdown notebooks, "one latest version each"), not among the 8 reported setups. The analyst did not mention this 9th runner. It makes no difference to ratings.
- Released run logs store resolved task ids (e.g. "task_ids": ["antibiotic_breakfast"]), not menu handles.
