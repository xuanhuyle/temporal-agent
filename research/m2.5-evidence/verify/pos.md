# Adversarial verification: PoS (arXiv:2610.01415), 2026-10-03

## Access
- WebSearch: budget exhausted (200/200) on first call, so the paper body could NOT be read by me either.
  Paper evidence limited to scrapes already in scratchpad/lit/pos_src (abstract via recynie/research-pipeline,
  section headers + Fig 1/2 captions via averkij/top_papers JSON of arxiv.org/html/2610.01415v1).
- Primary code: repos/luoyu100_PoS @ 6818cfa6434dbc91fcf67f0b3eb12a91db47433f (2026-10-02). Re-read all cited files myself.
- Re-ran analyst probe: `python3 pos_src/probe_pos.py repos/luoyu100_PoS`.

## Rating changes
None. All 20 ratings survive re-check against code. Borderline items noted below.

## Claim corrections (verbatim evidence)
1. Probe claim "the step-0 entry in belief_update_history still holds 'dirty'" is mislabelled.
   probe_pos.py prints `res["belief_update_history"][0]` (list index 0), and the output is:
     HISTORY steps/status: [(-1, 'validated'), (0, 'validated')]
     HISTORY[0] final s1: Mug 1 is dirty.
   So the 'dirty' record lives in the step -1 (initialization) entry, not the step-0 entry. Substance
   (earlier committed beliefs survive in the export log while the live belief is overwritten) is unchanged.
2. "Global audit every 8th update" is config-dependent, not universal:
     configs/alfworld/pos.yaml:52   global_audit_every_steps: 8
     configs/rca100/pos.yaml:51     global_audit_every_steps: 8
     configs/clindiag/pos.yaml:69   global_audit_every_steps: 8
     configs/loca/pos.yaml:59       global_audit_every_steps: 32
3. events.jsonl is append-only only within one case run: utils/logger.py:18
     self.file = path.open("w", encoding="utf-8")
   main.py:655 creates `Logger(case_path / "events.jsonl")` for every case not skipped, so a re-run of a case
   (skip_existing false, or a crashed case restarted by run_until_complete) truncates the earlier log.
   raw_trajectory (belief/manager.py:161-170, 237-247) is append-only in memory per episode; reset() replaces it.

## Confirmed (spot checks)
- Belief schema: belief/beliefStates.py:1-3 "Structured belief is the source of truth"; :15 "Fixed goal G";
  :22-36 EpistemicGap / AchievementGap docstrings; worldStates.py:60-82 State/Relation fields
  (state_id, entity_id, description, probability, reason, source_type) -- no time/validity fields (probe output).
- Policy context has no history: prompts/react_prompt.py:500-518 (observation, Belief Text, Goal+Active-Gap
  subgraph, Active Gap, FRONTIER_ACTION_SELECTION_CONTRACT, recovery, action schemas). Raw baseline's
  build_prompt has "Previous steps:" (react_prompt.py:457-458); PoS prompt does not.
- Update prompt: prompt_generation.py:13 "Keep only goal-relevant facts"; :150-151 "remove a State or Relation
  only when the observation invalidates it"; :82-84 "replace contradicted facts, remove only the Gaps resolved".
- Candidate on deepcopy, reject -> keep base: manager.py:557-585, 408-508.
- Sentinel judges changed records only: beliefSentinel_prompt.py:9-10 "Report an issue only when a changed
  State, Relation, or Gap ..."; verbatim-quote filter beliefSentinel.py:466-478.
- Trapping: trappingDetection.py:233-323 (K window of verified transitions, H = 1 - max(P)*max(S,R),
  projections onto current active_gap at :274-276). Cycle recovery inserts world_before/world_after
  snapshots: manager.py:912-950.
- grep for predict|forecast|simulat|lookahead|imagin|rollout|counterfact|fork|branch|rollback|restore|replay|as_of
  over belief/ prompts/ baselines/ contexts/ main.py docs/ utils/ scripts/: no prospective/branching mechanism
  (only snapshot = trapping-window bookkeeping, and test-harness snapshots in scripts/).
- Table 1 numbers match docs/results.md; 22.68% (88.81/72.39) and 37.89% (38.83/28.16) recomputed OK;
  ablations lower than full PoS in all 12 settings (checked all three tables).
- Compute: docs/results.md:73-75 "5.06x total method tokens"; project page _pages/...project.html:126
  "Fewer unproductive actions should not be read as lower total compute."
- docs/method.md:77 "approximation, not a learned semantic equivalence guarantee."

## Borderline ratings (kept)
- cross_time_state_querying = partial: internally snapshots_by_step[step] (trappingDetection.py:262-264) is a
  state_at(step) lookup and _world_distance/_projection_distance are pairwise diffs, but none is exposed to the
  policy/agent as a query. Could defensibly be "no" under a strict "first-class" reading.
- backward_requirements = partial: achievement gaps = "unresolved difference between the current and desired
  world" (beliefStates.py:30-31); single-level, LLM-regenerated each update, no feared futures.
- historical_policy_objective_state = partial: frontier_history (manager.py:653-673) and recovery_history are
  step-stamped; goal is fixed; no model/instruction versioning in agent state.

## Not verifiable here
Paper body (§3 equations, Appendix G, Tables 2-9) -- no arXiv access and no WebSearch budget.
