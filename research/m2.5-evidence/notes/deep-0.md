# Deep read: "The Log is the Agent" / ActiveGraph (Nakajima, arXiv 2605.21997; github.com/yoheinakajima/activegraph)

Date: 2026-10-03. Analyst: deep-read subagent (lane exec-state).

## What was read, and how
- Code: clone at `scratchpad/lit/repos/activegraph` (HEAD `50d8405`, "Release prep: v1.12.0 changelog ..."). PyPI JSON
  (https://pypi.org/pypi/activegraph/json) confirms the current release is 1.12.0 under Apache-2.0.
- I read: `README.md`; `docs/concepts/{forking,replay,events,frames,views,patterns,behaviors}.md`;
  `docs/guides/fork-test-promote.md`; `docs/quickstart.md` (fork section); `docs/cookbook/common-patterns.md`;
  `CONTRACT.md` (v0.6 #8 and the fork-cache entries); `compaction-design.md`; `trial-isolation-design.md`; `FUTURE_IDEAS.md`;
  `ROADMAP.md`.
- Source files read: `activegraph/runtime/runtime.py` (`load`, `fork`, `diff`, `set_authority_ceiling`, `llm.requested` emission),
  `runtime/diff.py`, `runtime/promote.py` (`build_base_graph`), `runtime/context_reads.py`, `store/sqlite.py` (`fork_run`,
  `truncate_after`, the runs schema), `frame.py`, `policy.py`, `runtime/authority.py`, `trace/causal.py`,
  `packs/diligence/object_types.py`, and `tests/test_tool_replay.py`.
- **Executed probe**: `scratchpad/lit/repos/ag_probe.py`, run against the clone on Python 3.11 with pydantic 2.13. Results are below.
- **Paper text**: NOT fetched. arxiv.org is blocked, and this session's WebSearch budget (200) was already used up when this
  deep read started. The paper statements below are the search-engine extracts recorded by the earlier exec-state sweep
  (`notes/sweep-exec-state.md`), which cites https://arxiv.org/abs/2605.21997. They are marked [paper-extract] and may be lightly
  paraphrased.

## Paper claims ([paper-extract], via the earlier sweep's WebSearch of arxiv.org/abs/2605.21997)
- "The append-only event log is the source of truth; the working graph is a deterministic projection of that log"
- "deterministic replay of any run from its log, cheap forking that branches a run at any event without re-executing the shared
  prefix, and end-to-end lineage from a high-level goal down to the individual model call that produced each artifact."
- "a forking and structural-diff primitive that branches a run at any event and answers counterfactual 'what if I had done X
  differently' questions without re-executing the shared prefix."

## Verbatim evidence from the repo, by capability

### 1 immutable_historical_observations: YES (operator-side truncation exists)
- docs/concepts/events.md: "An event is an immutable record of something that happened in a run. Events are append-only — once
  an event lands in the store, nothing modifies it." / "The event log is the source of truth. Everything else — the graph, the
  trace, the audit history — is derived from it."
- docs/concepts/events.md: "Event values are detached. `emit` owns a canonical copy of the submitted payload ... mutating one
  cannot rewrite accepted history".
- Caveat in docs/concepts/events.md: "No edit, no delete, no truncate (except via the explicit `truncate_after` primitive, which is
  operator-side, not behavior-side)". The code, store/sqlite.py:337-340, really deletes:
  `DELETE FROM events WHERE run_id = ? AND seq > ?`.
- Compaction archives events and never deletes them. compaction-design.md: "Compaction therefore cannot mean "delete old events" —
  it means **moving the truth boundary** ... Nothing is ever deleted by the runtime."

### 2 historical_world_state: YES, for whatever the graph or log holds
- The README tagline is "The graph is the world." The fork docstring (runtime.py) says: "Copies events from the parent's log up to and including
  `at_event` into a fresh `run_id`, replays them into a new Graph".
- Probe A: the parent created `decision` at evt_003, then `finding` at evt_007. `fork(at_event='evt_003')` gives a graph holding
  only `decision`, a strict prefix.
- Limitation: there is no separate model of the external world. External observations exist only as logged `tool.responded`
  events. The world at t outside the log cannot be reconstructed (see 3 and Probe E).

### 3 historical_epistemic_state: PARTIAL
Strong static reconstruction:
- The graph at a strict event prefix is the agent's working knowledge: claims, evidence, risks.
- `llm.requested` stores the full prompt body. runtime.py ~1737: "Only include full prompt body on turn 0's first attempt;
  subsequent turns/retries can be reconstructed from messages plus the shared prompt hash."
  `requested_payload["prompt"] = prompt.to_hashable()`
- Opt-in `context.read` events record which objects each behavior read. context_reads.py: "the runtime emits ONE batched
  `context.read` event carrying the ordered, deduplicated list of object ids the execution read."

No hindsight guarantee when the past self is re-executed or questioned:
- CONTRACT.md v0.6 #8: "`runtime.fork(at_event, ..., replay_llm_cache=True)` — pre-populates from the **parent's** full event
  log (not the fork's, which only has events up to and including `at_event`)."
- runtime.py fork(): "Cache is populated from the PARENT's recorded llm.responded events ... A diverging fork that regenerates an
  identical prompt will hit the cache".
- The tool cache works the same way (`_ToolCache.from_events(self.graph.events)`).
- **Probe E (executed)**: a non-deterministic tool `read_world` reads an external dict. Steps:
  1. The parent called it after goal.created and recorded `{'value': 'breach_disclosed'}` at evt_009.
  2. The world dict was then set to "calm".
  3. The parent was forked at evt_001 (goal.created, before any tool call).
  - With `replay_tool_cache=True`, the fork's call returned `('evt_009', cache_hit=True, {'value': 'breach_disclosed'})`. That is the
    parent's POST-cutoff observation, served into the counterfactual branch.
  - With caches off, it returned `{'value': 'calm'}`, which is the live present world. That is also not the world at t.
- The repo's own test `tests/test_tool_replay.py::test_replay_serves_non_deterministic_tool_from_cache` asserts this exact
  behavior as the desired default (fork at goal.created, tool served from the parent's later response).
- Epistemic state is not separate from world state: one graph serves as both.

### 4 historical_policy_objective_state: PARTIAL
Logged and replayable:
- `goal.created` (goal text).
- `pack.loaded`. docs/concepts/events.md: "carries the pack name, version, settings, and prompt content hashes".
- `pack.settings_overridden`, `pack.disabled`.
- `authority.ceiling_changed`, with previous_ceiling, actor and reason. runtime.py: "The last accepted
  `authority.ceiling_changed` event decides ... Reading from the log ... means `load`, `fork`, and replay see the same ceiling".
- `dev.override`, `authority.decision`.
- Full prompts, including frame text stamped into prompts. frame.py: "constraints, success_criteria, and permissions are
  declarative lists stamped into assembled LLM prompts".

Not restored as of t:
- fork() passes `frame=self.frame, policy=self.policy` and reuses the parent's current behaviors.
- **Probe F**: I set the parent's frame to `G-revised-later` after the run, then forked at evt_001. The fork's frame goal was
  `G-revised-later`, not the original one.
- Behavior code is not in the log: "behaviors are code, not state — re-register them" (examples/resume_and_fork.py).
- policy.py: "v0 semantics stand: fields are recorded with the run for audit; the actively enforced gate today is approval
  routing".
- There is no "what objective or policy governed me at t" query, and no identity/objective-drift tracking.

### 5 execution_checkpoints: YES
- `Runtime.load` replays the log, re-queues unfired events and rebuilds pending approvals. runtime.py: "Behaviors that started
  but never completed still lose their in-progress work".
- Compaction adds `runtime.snapshot` events with a hashed state blob; `verify_snapshot` replays the archived prefix to prove
  equality.

### 6 replay: YES
- docs/concepts/replay.md: "Two replays of the same log produce byte-identical graph state."
- Strict mode "re-fires every behavior and fails on divergence" (ReplayDivergenceError, with prompt-hash check).
- Known limitation, from the load() docstring: "payload-only drift is not detected".

### 7 fork_from_historical_state: YES
- docs/concepts/forking.md: "A fork copies events from the parent run, in order, up to the `--at-event` cutoff. The cutoff is
  **inclusive**".
- Forks of forks work. The parent is untouched (tests/test_fork.py::test_parent_is_untouched_by_fork).
- Requires a SQLite store. A fork below a compaction horizon is refused.

### 8 counterfactual_action_branches: YES
- docs/concepts/forking.md: "Forking is what lets the framework answer "what would have happened if I'd done X differently?""
- docs/guides/fork-test-promote.md: "branch a run at an event, try a candidate change in the branch against replayed history,
  and — if it earns it — adopt the branch's results back into the parent."
- Promote is a three-way merge, fail-closed on conflicts.
- `run_forked_trial` runs the candidate in a separate process.

### 9 branch_provenance: YES (no first-class "reason")
- The runs table has `parent_run_id, forked_at_event_id, label, created_at, goal, frame_id` (store/sqlite.py:75-83).
- Probe D: `('01M40...ZKZ8W'... parent), ('01M40...M19', parent_run_id='01M40...8W', 'evt_003', 'probe-fork', 'evaluate')`.
- The divergence action is recorded as the fork's own first events (`pack.settings_overridden`, `pack.loaded`, injected objects).
- `promote.applied` marker: "source run, fork point, id lists, warnings". compaction-design.md: "promoted-from fork logs are
  retention-pinned".
- Goal-to-LLM-call lineage: trace/causal.py, "a single chain walk renders the full lineage from a claim back to the LLM call that
  produced it, to the document it was extracted from, to the goal that started the whole run."
- There is no structured "why we forked" field beyond the free-text label.

### 10 explicit_current_belief_state: PARTIAL
- The framework supplies a typed object/relation graph as current state.
- The bundled diligence pack defines Claim (confidence, status open|reviewed|retracted), Evidence, Contradiction (open|resolved),
  Question (open|answered|skipped) and Risk (severity). This is an example pack ontology, not a framework belief/assumption
  primitive. The README calls it "an example ontology, not framework base types".

### 11 uncertainty_representation: PARTIAL (pack-level only)
- In the diligence pack: `confidence: float = Field(ge=0.0, le=1.0)`, open Questions, and open Contradictions. The pack
  "does not auto-resolve ... the memo synthesizer surfaces these as open questions".
- The framework has no uncertainty concept of its own.

### 12 future_state_rollout: PARTIAL, weak (executed trial, not simulation)
- A fork from the tip, run under a candidate pack, executes a hypothetical continuation in isolation before adoption:
  `parent.fork(at_event=parent.trace.events()[-1].id ...)`, then `fork.load_pack(candidate_pack)`, then `fork.run_goal(...)`.
- `run_forked_trial` runs a scenario in a subprocess.
- This is real execution, with live or cached tools, of a candidate policy. There is no world model, no simulated external
  dynamics and no forecast of external events.

### 13 multiple_prospective_branches: PARTIAL, weak
- Several forks can be cut from the same tip, and frames give in-run "parallel hypothesis exploration". frames.md: "Parallel
  hypothesis exploration before fork is appropriate".
- Diff is pairwise (parent vs fork). There is no set-of-futures object.

### 14-18: NO
- No probabilities over futures and no backward requirements.
- No intervention-aware forecasts: there are no forecasts at all.
- No prevented-forecast bookkeeping. Rejected trial forks are archived via `retire`, never deleted, but nothing labels them as
  averted predictions.
- No predicted-vs-realized comparison in the runtime. Grep of the runtime repo docs for forecast|predict|calibrat finds only
  "confidence score (0.0-1.0) calibrated to evidence" in a diligence prompt.
- Context only, not rated: the sibling repo activegraph-packs (HEAD 6639a53) has a narrow predicted-vs-realized loop.
  packs/tool_gateway/standing_scopes.py: "predictions (recorded BEFORE verdicts, product-side) → per-scope accuracy ...
  → sustained accuracy → tool_policy CANDIDATE ... → degraded accuracy → DEMOTED, naming the missed predictions" and
  "**No backfilled predictions** — every evidence pair's prediction must precede its decision in the event log". It predicts
  owner approval verdicts only, not future world states.

### 19 cross_time_state_querying: PARTIAL
- state_at(e) is available two ways:
  - fork(at_event=e) without running it.
  - The internal helper `activegraph.runtime.promote.build_base_graph(parent, forked_at_event)`, documented as "Reconstruct the
    parent's state at the fork point".
- Probe B: state_at(evt_003) gives [decision]; state_at(evt_009) gives [decision, finding].
- Probe C: `compute_diff(build_base_graph(g,t1), build_base_graph(g,t2))` gives `['finding#2 only in fork']`. So diff(t1,t2)
  within one run is achievable, but only through internal APIs, with parent/fork naming.
- The public `rt.diff(other)` compares two runs' FINAL states: "structural only — divergent objects, divergent relations, and the
  event partition".
- Time is addressed by event id, not wall-clock.
- No as-of query language: views are "Not a query language". The README mentions pattern "temporal predicates", but none appear
  in the documented Cypher subset. The only temporal knob found is `activate_after=` (N events later).

### 20 unified_temporal_abstraction: PARTIAL
- One abstraction (log, deterministic projection, lineage-tracked forks) covers past (prefix), actual (main run) and counterfactual
  (forks, diff, promote) states.
- It has no prospective or forecast states, so it does not unify historical, actual, counterfactual AND prospective states.

## Threat to the project's novelty (precise)
1. "Never overwrite time, fork it" is already shipped, tested and documented as a production runtime (v1.12, Apache-2.0,
   pip-installable), with a paper. It has an append-only log, the projection as derived state, inclusive-cutoff forks with
   (parent_run_id, forked_at_event_id, label) lineage, strict replay with divergence detection, structural diff, three-way
   fail-closed promote, subprocess fork trials, and retention-pinned provenance. Any project claim that "keeping all branches with
   provenance" or "forking from historical state" is novel is dead.
2. As-of reconstruction of the agent's own working state is available: strict prefix, full logged prompts, opt-in context.read
   sets. The project's capabilities 1, 2, 5-9 and most of 19 are prior art. A benchmark contestant could be built on ActiveGraph
   directly.
3. The "agent tests a change against its own history before adopting it" loop (fork, test, promote) already covers the
   self-modification and counterfactual-policy-evaluation story. Its docs even frame it as "Hypothesis testing on an agentic
   system, without losing the parent run."

## What it does NOT cover (the residual space)
- **Strict epistemic cutoff under re-execution.** Forks pre-fill caches from the parent's FULL log by design (CONTRACT v0.6 #8).
  Probe E shows a fork cut before a tool call receiving the parent's post-cutoff observation. With caches off, tools read the
  live present world instead. There is no "world as known at t" boundary for questioning a past self, and no hindsight-leakage
  test. A "question your past self with no hindsight" claim still has room, but it must be stated as a property ActiveGraph lacks
  (cutoff-safe tool/LLM replay), not as "reconstruct past state".
- **Historical policy/objective restoration.** Forks inherit the parent's current frame, policy and behaviors (Probe F). Policy
  changes are partly logged (authority ceiling, pack loads and settings, goals), but there is no state_at(t) query for "what
  governed me", and no identity or objective drift tracking.
- **The prospective side.** Nothing provides imagined futures, probabilities over futures, backward requirements, forecasts
  conditioned on the agent's own interventions, prevented-forecast preservation, or a predicted-vs-realized ledger in the
  runtime. The sibling activegraph-packs approval-prediction loop is narrow but has a log-ordered no-backfill guard.
- **Belief-state semantics.** There is no separation between world truth and agent belief, and no assumption/requirement
  objects at the framework level. Diff is structural only ("Semantic comparison is a behavior's job, not the runtime's"), so
  "noticing that a later event changes the significance of an earlier decision" would be a behavior the user writes, not
  something the runtime provides.
- **No benchmark** of whether forking or replay helps an agent reopen earlier decisions. The repo is infrastructure; the
  quickstart diff counts (61 divergent objects, 49 divergent relations) are demos, not evaluations.

## Could not verify
- The paper's full text: arXiv blocked, WebSearch budget exhausted. That covers its evaluation section, any claims about
  epistemic cutoffs or prospective use, and author list details beyond "Nakajima, 2026" as given in the README.
- The Regimes follow-up (arXiv 2606.10241), which the README describes as "an autonomous evaluation-improvement loop ...
  promotes repairs only through static, sandbox, in-sample, and held-out gates". Not read.
- The docs site (docs.activegraph.ai) and activegraph.ai: both blocked. The repo docs/ folder is the source of the site.
