# Deep read: DeepRewind: Predicting and Repairing Premature Commitments in Deep Research Agents

Abaskohi, Dabiriaghdam, Wang, West, Carenini. arXiv 2609.36344 (v1 published 2026-09-28T22:27:33Z per the arXiv RSS
mirror). The README BibTeX names the venue: REALM@EMNLP 2026, "Second Workshop for Research on Agent Language Models",
https://openreview.net/forum?id=LGVrhRguSJ. Code: https://github.com/AmirAbaskohi/DeepRewind (MIT), built on
langchain-ai/open_deep_research.

Date: 2026-10-03. Lanes: exec-state, backward-optionality.

## What was read, and how
- **Paper full text: NOT read.** arxiv.org, openreview.net and alphaxiv are blocked for curl and WebFetch, and this
  session's WebSearch budget (200/200) was already used up. I had only the abstract, from three independent mirrors:
  - `CSQianDong/Awesome-arXiv-Daily-Reporter`, 30-Sep-2026 NLP `papers.jsonl` (already cloned at `scratchpad/lit/repos/csq_daily`);
  - https://raw.githubusercontent.com/flybfree/AI-Wiki/master/raw/papers/2026-09-28_22-27-33Z_DeepRewind_PredictingandRepairingPrematureCommitme.md
    (gives the publish timestamp, arXiv v1);
  - https://raw.githubusercontent.com/qhduan/cn-chat-arxiv/master/papers/26/09/2609.36344.json (abstract is truncated).
  - I found the repo with GitHub code search for "DeepRewind" (MCP search_code). It returned `AmirAbaskohi/DeepRewind`
    (README.md, scripts/run_research.py).
- **Code: cloned** to `scratchpad/lit/repos/deeprewind` (HEAD `9282f0f2800aca31fdf5227a75fe8e382986ca9d`, 2026-10-01
  "Update README.md"). The only other commit is `b107198` (2026-09-13, "Added files."). Read in full:
  `epistemic_graph.py`, `world_model.py`, `world_model_scoring.py`, `world_model_monitor.py`, `world_model_rollback.py`,
  `experiments/{config,switching,seed_initial_condition,hooks,analyze}.py`, and the commit, monitor and rollback sections
  of `deep_researcher.py` (lines 860-1440, 1990-2080). Also read: the reconciliation prompt in `prompts.py`,
  `DeepRewind-method.png`, the README and parts of `scripts/`.
- **Executed probe**: `scratchpad/lit/deeprewind_raw/probe.py` imports the repo's pure-Python graph, scoring, monitor and
  rollback modules, using the repo's default thresholds. Results are below.

## Abstract (verbatim, from the mirrors)
"Deep-research agents conduct long-horizon investigations through iterative search, evidence evaluation, belief revision,
and synthesis. However, they may commit to claims before sufficient evidence is available, causing later reasoning to
reinforce an incorrect interpretation. We introduce DeepRewind, an additive control layer for reversible deep research
that represents the agent's evolving epistemic state as a typed graph of sources, evidence, claims, hypotheses,
assumptions, commitments, plans, and drafts. Before accepting an intermediate conclusion, a prompt-based world model
predicts its impact and estimates reversibility based on hypothesis narrowing, information loss, recovery cost, and
contradiction-trigger coverage. A binary controller blocks risky commitments, while a consistency monitor performs
dependency-aware rollback when later evidence invalidates them. Across DRBench and LiveDRBench, DeepRewind improves
insight recall by 3.6 percentage points and reduces premature commitments by 59.1% relative to Open Deep Research."

## Method figure (DeepRewind-method.png, verbatim text)
- Panels: "1 Research-state graph", "2 Reversibility prediction", "3 Binary commit gate", "4 Rollback monitor",
  "5 Dependency-aware reduced rollback".
- "Observed only: Source, Evidence. Predicted: Claims, Hypotheses, Commitment, Draft"
- Gate: "Risk score q_t = IRR(a_t)(1 - TC(a_t))", "q_t <= tau?", "COMMIT: Safe & reversible enough", "NOT-COMMIT (high
  risk or contested belief): Continue exploring before committing"
- Rollback steps: "Identify minimal affected subgraph", "Retract commitments in the subgraph", "Retain unaffected
  supported findings", "Local replanning & continuation", "Improved final report"
- "Append-only ledger: every transition, decision, and rollback is recorded for auditability."
- "Instead of only storing memory, the model tracks transitions and reversibility, enabling targeted recovery from
  premature commitments."

## Verbatim code evidence, by mechanism

### Epistemic graph (append-only JSONL plus a mutable in-memory mirror)
- `epistemic_graph.py:31-37`: "Because every node and edge is appended as its own event, the graph is append-friendly and
  preserves history: beliefs are never silently overwritten. When later information changes an earlier belief we add a
  ``revises``/``invalidates`` edge to a *new* node instead of mutating the old one."
- `NODE_TYPES` = Source, Evidence, Claim, Hypothesis, Assumption, Commitment, DraftFragment, PlanStep. `EDGE_TYPES` =
  supports, contradicts, locks_in, depends_on, compresses, used_in, derived_from, cites, revises, invalidates.
- Every node and edge event carries `"ts": _now_iso()`. The node metadata from deep_researcher carries `iteration`.
- `epistemic_graph.py:316`: "In-memory mirror used by the world-model encoder. This does not alter the append-only JSONL
  schema; it only adds read access to current run state."
- Status changes are append-only events, but they mutate the mirror in place:
  `mark_contested` -> `node["data"]["status"] = "contested"` plus a `{"event": "contested", ...}` line; likewise
  `retract_node` ("retracted"), `retract_edge`, `mark_stale` ("stale") and `rollback_record` (`"event": "rollback"`).
- Text is truncated (`_truncate(value, limit=4000)`), so the log is not a complete raw record of observations.
- README: "Invalidated artifacts are marked contested/stale/retracted rather than deleted, preserving the full research
  history."
- There is no API for state as of t. `scripts/visualize_epistemic_graph.py::build_graph` rebuilds only the full
  end-of-run graph, from `node` and `edge` events. It ignores the `contested`, `retraction` and `stale` events.

### World model, gate, and one-step prospective evaluation
- `world_model.py` SYSTEM_PREDICTION_PROMPT: "You are a world model of a deep-research agent's epistemic state. You are
  given the current research-state graph and one candidate COMMIT action. Predict how the graph will change if the action
  is taken, and estimate the reversibility of that change." / "You MUST NOT invent, rewrite, or predict Source or Evidence
  nodes. Their content is determined by the internet, not by the agent." / "optional trigger_coverage in [0,1] if you can
  estimate how likely future probes would catch contradictions for the committed claim."
- `world_model_scoring.py:247` `apply_commit_to_snapshot`: "Return post-commit simulated snapshot without mutating the
  input graph". It adds `config.wm_commit_lockin_strength` to the target hypothesis. This models the reflexive lock-in
  effect of committing.
- `compute_kappa`: "(entropy(p_t) - entropy(p_t1)) / log k". This is the drop in entropy of the hypothesis-plausibility
  softmax between the pre-commit snapshot and the simulated post-commit snapshot.
- `compute_lambda`: contradiction mass divided by total stance mass for the claim. `compute_gamma`: the number of
  transitive dependents times the retract+regen cost, divided by the budget. `compute_irr` = alpha-weighted sum.
- `compute_tc`: "count active PlanStep probes linked to the committed claim ... More probes imply better chance a future
  contradiction will be detected."
- `decide`: "if contested: return 'not_commit'". Threshold mode: `irr * (1 - tc) <= wm_tau_commit`. Utility mode:
  `U = V - eta*IRR*(1-TC)`.
- `deep_researcher.py:1320-1335`: a blocked commit becomes a PlanStep "Retain as contested for: {topic}" with
  `"status": "retain_as_contested", "reason": "world_model_not_commit"`, and then `continue` (keep researching).
- Only ONE candidate action is evaluated: commit to this iteration's claim, or do not. No alternative branches are
  generated or kept.

### Uncertainty
- `compute_belief`: "Compute claim belief beta(c) via logistic aggregation", summing ±edge_weight × source reliability over
  Evidence edges. `compute_plausibility`: "Compute hypothesis plausibility softmax". `is_contested`: belief within a band
  around 0.5, with enough contradiction mass.
- The sufficiency decision node records `"missing_information"`.

### Consistency monitor and "rollback" (graph retraction, not state restoration)
- `world_model_monitor.py:79` `_is_new_since_step(edge, step)`: counts only contradicting edges whose `iteration` is
  greater than the commitment step. This is a narrow "since t" query.
- `consistency_violated`: a trigger qualifies only if the contradicting endpoint is `Evidence`
  (`if other_node.get("type") != "Evidence": continue`), with `rho >= rho_star` and `weight >= w_star`, AND
  `beta_now < wm_beta_star`. It returns `"beta_before": commitment_record.get("beta_at_commit")` and `"beta_now"`.
- `world_model_rollback.py` `reduced_repair`: "Build a deterministic reduced rollback repair plan for one stranded
  commitment". It returns contested_claims, retract_nodes (the commitment plus its unique justifications),
  retract_edges, regenerate_nodes (dependent DraftFragment/Hypothesis), preserved_nodes (nodes with another active
  commitment or an outside consumer), and reopen_claims.
- `apply_repair`: "Apply repair via append-only ledger/status helpers without deletion."
- `deep_researcher.py:1223-1229`: for each reopened claim, its topic goes into `pending_reopen_topics`. Line 972 feeds
  these as `seed_topics` to the next proposal iteration, and line 1258 keeps the loop running while any are pending.
  This is the reopen-and-remediate behaviour: the agent re-researches forward. It does NOT restore an earlier execution
  state.
- `deep_researcher.py:1426-1430`: the consolidated findings passed to the report writer are
  `for topic, compressed in all_compressed_results`. They are NOT filtered by retraction status. `_record_draft_fragments`
  (line 2044) links `egraph.all_claim_ids()` (also unfiltered) `used_in` the final report. So in the released code, the
  text of retracted findings still reaches the report writer. The "repair" is: graph flags, plus re-research, plus
  whatever the report LLM does with both versions.

### How contradictions are detected (organic path)
- `deep_researcher.py:1144-1171`: `reconcile_epistemic_state` is an LLM call. It compares this iteration's findings
  against ALL prior claims and hypotheses (`existing_items=prior_epistemic_items`, the full list with no retrieval). It
  emits supports/contradicts/revises/invalidates edges FROM the new Claim TO the existing item.
- Prompt (`prompts.py:254`): "'invalidates' - the new findings show the existing item is wrong and should no longer be
  relied upon."
- **Probe result (my execution, default config: beta0=0.0, default reliability 0.5, rho_star 0.7, w_star 0.6,
  beta_star 0.5)**:
  - case 1, organic path (new Claim -contradicts-> and -invalidates-> committed Claim): belief stays 0.622, monitor fired 0.
  - case 2, Evidence -contradicts-> Claim from an unrated source (reliability 0.5): belief 0.5, fired 0.
  - case 3, synthetic switch injection (reliability 0.95, weight 0.95, as in `experiments/hooks.py:165-203`): belief 0.401,
    fired 1. The repair plan retracts `cmt1` and `hyp1`, contests and reopens `clm1`.
  - Grep: the only `contradicts` edges from Evidence in the whole package are created by `experiments/hooks.py:76,197`
    (synthetic seed and switch injection). No organic code sets source `reliability`.
- **Implication (code-level, may differ from the paper):** in the released code, the dependency-aware rollback is
  effectively reachable only in the synthetic switching experiment. Organic contradictions that the LLM reconciler finds
  do not change belief or fire triggers. Organic gains would therefore come from the commit gate (not_commit means
  "continue researching"), not from rollback. I cannot check whether the paper's DRBench/LiveDRBench numbers came from
  this code path.

### Experiments (the closest analogue to the project's benchmark)
- `experiments/config.py`: families "initial_condition" (neutral/counter/distract/support) and "switching"
  (noswitch/switch). Arms: base, wm_shadow (predict-only), wm_gate, wm_rollback, ablate_norollback.
- `experiments/switching.py`: the preamble makes alternative A "the leading hypothesis". There is a synthetic
  "Preliminary indications favor alternative A" prior. After the first commitment, switch evidence is injected:
  "New high-confidence contradiction against alternative A" with `"attach_to_commitment_claim": True`, plus
  "New high-confidence support for alternative B".
- `experiments/hooks.py:165`: "Explicitly add high-confidence contradiction to the actual commitment claim so
  monitor/rollback can fire on that exact target." This means that in the switching study the link between the new
  evidence and the earlier commitment is GIVEN by construction. The agent does not have to infer which earlier decision
  is affected.
- `experiments/analyze.py`: `recovered_to_b` (an LLM judge checks that the final answer aligns with alternative B),
  divergence across initial conditions, a "Seeding Susceptibility" flip fraction, and a "Calibration table: correlation
  between LLM self-estimates and grounded" κ/λ/γ. That last one compares the LLM against a structural formula at
  prediction time. It does NOT compare predictions with realized outcomes.
- `scripts/run_live_research_bench.py` targets `Salesforce/LiveResearchBench` and "performs **no evaluation**". The
  abstract names DRBench and LiveDRBench. I found no code for "insight recall" or the "premature commitment" metric
  (grep for premature, insight, DRBench and LiveDRBench hit only the README title and BibTeX).

## Ratings (what the work itself provides)
| # | capability | rating | basis |
|---|---|---|---|
| 1 | immutable_historical_observations | yes | Append-only JSONL of typed nodes and edges with ts; retractions are events, not deletions. Caveats: 4000-char truncation; the live in-memory mirror is mutated |
| 2 | historical_world_state | no | No reconstruction of the world as of t. Source/Evidence are recorded, but no as-of view exists |
| 3 | historical_epistemic_state | partial | The log prefix could rebuild beliefs at t; `beta_at_commit` is stored; the monitor filters contradictions newer than the commit step. No API and no cutoff enforcement |
| 4 | historical_policy_objective_state | no | A one-time config snapshot in the world-model log; the question is recorded once. No tracking of goal or policy change |
| 5 | execution_checkpoints | no | "Rollback" is status retraction in the graph plus forward re-research. LangGraph MemorySaver is only the framework default in the runners and is not used by the method |
| 6 | replay | no | None |
| 7 | fork_from_historical_state | no | None |
| 8 | counterfactual_action_branches | partial | One hypothetical commit is simulated on a deep-copied snapshot without committing. A single action only; no alternative branches |
| 9 | branch_provenance | partial | The research log records available/chosen/rejected actions with rationale; rollback events record commitment, offending evidence, beta before/after and the plan; revises edges. There are no forks to attribute |
| 10 | explicit_current_belief_state | yes | Typed Hypothesis/Assumption/Claim/Commitment nodes with contested/retracted/stale status |
| 11 | uncertainty_representation | yes | Claim belief beta, hypothesis plausibility softmax and entropy, contested band, retain_as_contested, missing_information |
| 12 | future_state_rollout | partial | A one-step, action-conditioned prediction of the epistemic graph delta, and a post-commit plausibility. Not multi-step, not external |
| 13 | multiple_prospective_branches | no | One candidate action per gate |
| 14 | probability_over_futures | no | Plausibility is over current hypotheses, not over futures; TC is one scalar for detecting a future contradiction |
| 15 | backward_requirements | partial | A feared future (irreversible lock-in) drives present obligations: do not commit and keep exploring, register a rollback trigger θ, count probes (TC). A fixed formula, not derived from a stated future |
| 16 | intervention_aware_forecasting | partial | The prediction is conditioned on the agent's own commit and models a reflexive lock-in term; κ contrasts pre- and post-commit. No passive/policy/reflexive taxonomy; no external forecasts |
| 17 | prevented_futures_preserved | partial | Predictions for blocked commits stay in the append-only log with decision=not_commit and enforced=true, and shadow arms log unenforced predictions. Incidental only: no forecast-scoring semantics |
| 18 | predicted_vs_realized | no | The "calibration" compares LLM κ/λ/γ with structural κ/λ/γ at prediction time. Predicted graph deltas are never compared with the later realized graph |
| 19 | cross_time_state_querying | partial | Narrow and hard-coded: `_is_new_since_step` gives contradicting edges added after the commit iteration; beta_at_commit vs beta_now. No state_at or diff API |
| 20 | unified_temporal_abstraction | no | The GraphSnapshot type is shared by the current and simulated post-commit state, but nothing makes time addressable and history is not queryable as states |

Disagreements with the work-item card: the card lists execution_checkpoints, replay and backward_requirements as
covered. From the code, execution_checkpoints and replay are NOT provided; "rewind" here means truth-maintenance-style
retraction. backward_requirements is only partial.

## Threat to the project
**High for the benchmark behaviour and for the "dependency tracking alone suffices" alternative hypothesis. Low to
medium for the temporal-navigation mechanism itself.**

1. DeepRewind already implements the project's target behaviour and evaluates it in a controlled ablation. The behaviour:
   an earlier commitment is later invalidated by new evidence, the agent notices, retracts it, reopens it and
   re-researches. The ablation: base / shadow / gate / rollback / no-rollback, with a "switch" condition injected after the
   first commitment and a recovered-to-B outcome metric. Its mechanism is a typed dependency graph with
   justification-based retraction. That is LLM-era truth maintenance (Doyle 1979 TMS lineage, confirmed in an earlier
   sweep: https://en.wikipedia.org/wiki/Reason_maintenance). It is not temporal navigation. So the claim "noticing that a
   later event changes the significance of an earlier decision needs time as an addressable dimension" now faces published
   prior art that gets the behaviour without addressable time.
2. The commit gate (irreversibility risk × (1 − trigger coverage), "continue exploring before committing") is published
   prior art for "option-preserving actions derived from a feared future". It is narrower (one fixed formula), but it is
   measured.
3. Methodological consequence: the project needs a third contestant, a DeepRewind-style dependency/justification-graph
   agent (decision records with depends_on edges, plus a monitor that retracts and reopens), alongside checkpoint+RAG.
   Without it, a win for the temporal contestant cannot be attributed to temporal navigation rather than to dependency
   tracking. CLAUDE.md rule 4 (strong baseline) points the same way.
4. Reusable design: the switching protocol (seeded prior, commitment, injected contradiction, recovery judged against
   alternative B), the shadow arm (predict but do not act), and the no-rollback ablation map almost directly onto the
   project's trigger protocol and metrics.

## What it does NOT cover (residual space for the project)
- No reconstruction of past world or epistemic state with a strict cutoff. There is no "what did I know at t" query and
  no hindsight-leakage control: the reconciler sees all prior items together with the new findings.
- No execution checkpoints, replay or forks. Nothing is restored; alternatives are not kept as branches.
- Single-step, single-action prospection over the agent's own epistemic graph only. There are no external world
  futures, no multiple futures, no probabilities over futures, no prevented-forecast accounting, and no comparison of
  predictions with outcomes.
- Commitments are epistemic (claims in a report), not actions with external side effects (repo or task state). Its
  "remediation" is re-research. The project's "present remediation success" in a software world has no analogue.
- Detection of "which earlier decision is affected" is not tested. In the switching study the contradiction is wired
  directly to the committed claim (`attach_to_commitment_claim`). In organic runs, detection is an exhaustive LLM
  comparison against all prior items. That works for one short research run but does not address long-lived agents where
  the affected decision is far back, implicit, or causally indirect. The project's no-hint trigger protocol, its
  reopening precision/recall over decisions, and long-horizon scaling are untested by DeepRewind.
- No tracking of identity, objective or policy change.
- Code-level weakness (not necessarily the paper's): organic contradictions never fire the rollback monitor (see the
  probe), and retracted findings still reach the report writer. The headline numbers may therefore reflect the gate
  (extra research iterations) more than dependency-aware repair. I could not check whether research budgets were matched
  across arms.

## Could not verify
- Full paper text: the definitions of "premature commitment" and "insight recall", the 59.1% and 3.6 pp figures, the
  models, the number of questions and seeds, budget matching, the DRBench/LiveDRBench protocol, and whether the paper's
  rollback path differs from the released code.
- The OpenReview page (LGVrhRguSJ) and the workshop acceptance: these come from the README BibTeX only.
- Whether the abstract's "LiveDRBench" and the repo's LiveResearchBench script are the same benchmark.
