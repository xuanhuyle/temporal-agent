# PoS (Progression of States): "Beyond Memory: Harnessing Long-Horizon Agents with Explicit Belief States" (arXiv:2610.01415)

Analyst notes, written 2026-10-03. Scope: one system. Evidence standard: every non-obvious claim carries a source tag.

## 0. Read this first: access constraints and how much to trust each source

- **I could not read the paper itself.** The session's WebSearch budget was used up before this task started: the first call returned
  "this session has used its web search budget (200 of 200 WebSearch calls)". arxiv.org, alphaxiv, huggingface and
  *.github.io are blocked for curl/WebFetch (orchestrator rule), so I did not try them.
- What I used instead, from most to least authoritative:
  - **[CODE]** The authors' official code repository, `https://github.com/luoyu100/PoS`, cloned with `git clone --depth 1` to
    `scratchpad/lit/repos/luoyu100_PoS`. HEAD is `6818cfa6434dbc91fcf67f0b3eb12a91db47433f`, 2026-10-02 10:08 +0800,
    "Add arXiv paper links and citation metadata". The repo is MIT-licensed and includes README, docs, code, configs and
    offline tests. I read the code and ran the offline tests myself (see section 9).
  - **[PROJ]** Source of the authors' project page (`https://luoyu100.github.io/projects/progression-of-states/project/`),
    taken from the Pages repo `https://github.com/luoyu100/luoyu100.github.io`, cloned to
    `scratchpad/lit/repos/luoyu100.github.io`. HEAD is `04a4757c7ae10f46bdf659cad65d154a1777555f`, 2026-10-03.
    Relevant files: `_pages/progression-of-states-project.html`, `_data/pos_project.yml`, `_data/pos_experience.yml` and
    `_includes/pos-*.html`. The authors wrote this page, so it is primary for claims and numbers, but it is not the paper text.
  - **[ABS]** The arXiv abstract, copied verbatim by three independent arXiv scrapers on GitHub. I fetched them with
    raw.githubusercontent.com after finding them through the GitHub MCP code search for "2610.01415". All three copies match
    each other and match `abstract:` in [PROJ] `_data/pos_project.yml:18-19`.
    - `qhduan/cn-chat-arxiv` `papers/26/10/2610.01415.json` (truncated copy)
    - `recynie/research-pipeline` `_papers/2610.01415.md` (full copy; authors; published_date 2026-10-01)
    - `kzinmr/ai-topics` `wiki/raw/articles/arxiv-2610.01415-explicit-belief-states-long-horizon-agents.md` (full copy;
      full author list; "submitted 2026-10-01")
  - **[FIGCAP]** Section headers and figure captions scraped from the arXiv HTML page by `averkij/top_papers`
    (`assets/img_data/2610.01415.json`). The captions are verbatim from the arXiv HTML; image URLs point to
    `https://arxiv.org/html/2610.01415/2610.01415v1/...`.
  - **[SEC-V]** A third-party LLM-written summary: `vollero/hf-daily-paper-summaries`
    `summaries/2026/10/2026-10-02/2610.01415.md`. It cites paper sections and tables. Treat it as secondary. I use it only
    for paper-only content: Appendix G limitations, section numbering, and the baseline-adaptation notes.
  - **[SEC-K]** A third-party Korean summary: `gbdata365/daily_papers` `papers/2610.01415_new.html`. It is secondary. It is
    my only source for the Figure 3 trapping-pattern percentages. It also gave me the project-page link that led to [CODE].
  - `daiwk/auto-research` `docs/agent-research/2610.01415-belief-state-pos/README.md` says no official code had been found
    as of 2026-10-03. **The luoyu100/PoS repo contradicts this**, so that statement is stale.

## 1. Identity

- **What PoS stands for: "Progression of States".**
  - [CODE] `README.md:7`: `# PoS · Progression of States`
  - [CODE] `CITATION.cff`: `title: "PoS: Progression of States"`
  - [PROJ] `_pages/progression-of-states-project.html:3`: `title: "Progression of States | Beyond Memory"`
  - [PROJ] `_includes/pos-intro.html:4`: `Progression <br>of States`
  - The abstract does not expand the acronym. I could not check whether the paper body does.
- **Authors** ([ABS] kzinmr copy; [PROJ] `_data/pos_project.yml:5-17`): Yu Luo, Jiamin Jiang, Yimin Zuo, Xidao Wen,
  Rongchen Gao, Yongqian Sun (corresponding), Shenglin Zhang, Guiyang Liu, Cheng Zhang, Fang Situ, Qi Zhou, Dan Pei.
- **Affiliations** ([PROJ] `progression-of-states-project.html:33`): "<sup>1</sup>Nankai University
  <sup>2</sup>Alibaba Group <sup>3</sup>Tsinghua University".
- **Date and category:** arXiv v1, submitted 2026-10-01 ([ABS] recynie/kzinmr), cs.AI.
- [CODE] `README.md:193`: "This work was carried out during an internship at Alibaba Group."
- **Lineage** ([PROJ] `progression-of-states-project.html:49`): "Graph of States grounds abductive search in a causal graph
  and a state machine. PoS maintains a task-conditioned belief for both diagnosis and execution, assesses how that belief
  evolves, and intervenes when progress stalls."

## 2. Abstract (verbatim, [ABS])

> Large language model (LLM) agents can now undertake increasingly complex tasks, but the way they organize interaction
> history into memory does not ensure a coherent understanding of the current world. We introduce PoS, an inference-time
> framework that constructs and continually maintains explicit belief states as the agent's decision context. Each belief
> combines an estimate of the current world state with unresolved task requirements, making explicit what the agent still
> needs to learn and accomplish. To keep this belief reliable and actionable, PoS validates its consistency and monitors
> task progress to detect Belief Trapping, where the agent continues to act without making meaningful progress toward the
> goal. Recovery is then tailored to both the trapping pattern and the type of unresolved task requirement. Experiments on
> four benchmarks spanning execution and diagnosis show that PoS achieves the highest overall performance on every
> benchmark with all three LLM backbones. Ablations demonstrate the importance of consistency validation and recovery,
> while context-scaling experiments show resilience to context growth. Together, these results support belief
> construction and continual maintenance as a foundation for long-horizon context management beyond history retention and
> compression.

Figure 2 caption, verbatim ([FIGCAP]):

> Overview of PoS. Belief Modeling constructs and incrementally updates a task-conditioned Belief from interaction evidence
> (Section 3.1). Belief-Guided Interaction conditions each action on the current Belief and an Active Gap, while the Belief
> Sentinel validates consistency and records task-relevant progress (Section 3.2). Trapping-Aware Recovery estimates Belief
> health, diagnoses heterogeneous trapping conditions, and composes recovery constraints to restore progress (Section 3.3).

Paper outline ([FIGCAP] headers): 1 Introduction; 2 Related Work; 3 Methodology; 4 Experiments; 5 Conclusion. Appendices:
A Notation; B Supplementary Method Details; C Benchmark Details and Evaluation Protocols; D Implementation and
Reproducibility Details; E Fine-Grained Main Results; F Case Study; G Limitations and Future Directions.

## 3. The belief state: schema

- **Formal definition** ([CODE] `docs/method.md:19-21`):
  "PoS maintains the structured belief \(B_t=(W_t,G,\Delta_t^E,\Delta_t^A)\). The world uses Entities, States, and
  Relations. The Active Gap identifies the current focus, while health and recovery are runtime bookkeeping."
- [CODE] `belief/beliefStates.py:1-3`: `"""PoS runtime representation B_t = (W_t, G, Delta_E, Delta_A).` /
  `Structured belief is the source of truth; belief text is a derived decision view."""`
- **Records** ([CODE] `belief/worldStates.py`):
  - `Entity(entity_id, entity_type, name, attributes)` (lines 43-57). Attributes must be scalar and fit a 4096-char budget.
  - `State(state_id, entity_id, description, probability=1.0, reason=None, source_type: Literal["observed","inferred"])`
    (lines 60-69).
  - `Relation(relation_id, source_id, target_id, description, probability=0.5, reason, source_type)` (lines 72-82).
  - `WorldState` holds dicts of entities, states and relations. Methods: `upsert_*`, `remove_state` (which also removes
    relations that reference the state), `remove_relation` (lines 90-174).
  - Observed records are forced to probability 1 with no reason (`upsert_state` lines 117-119; `upsert_relation` 130-132).
- **Goal, gaps and pointers** ([CODE] `belief/beliefStates.py`):
  - `Goal(user_input, specification)`. Docstring at line 15: `"""Fixed goal G: the user request and its interpreted specification."""`
  - `EpistemicGap(target, reason)`: "Task-relevant information that remains unknown or unverified."
  - `AchievementGap(target, reason)`: "An unresolved difference between the current and desired world."
  - `GapFrontier(gap_type, target)`: "Pointer to the single gap currently prioritized". This is the paper's Active Gap.
  - `BeliefHealth(...)`: persistence_e/a, stagnation, recurrence, recurrence_period, health_score, threshold, gap_dimension,
    trapping_pattern, persistent gap ids.
  - `RecoveryDirective(...)`: recovery_frontier, trigger_frontier, gap_dimension, trapping_pattern, started_at_step,
    applies_from_step, recovery_action_steps, low_progress_transitions, instruction.
  - `BeliefState(world, goal, epistemic_gaps, achievement_gaps, frontier, health, belief_text, step)`.
- **How the authors describe the components** ([PROJ] `_includes/pos-method.html:4`):
  - "WORLD STATE / What holds now / Entities, their states, and their relations, with provenance, confidence, and evidence
    when available."
  - "EPISTEMIC GAP / What needs to be learned / A question that remains unresolved, such as distinguishing database waiting
    from JVM-side processing."
  - "ACHIEVEMENT GAP / What needs to change / A difference between the current world and the goal, such as making a mug hot
    before putting it away."
- **Mapping the user's questions to fields:**
  - "Open questions" are epistemic gaps.
  - "Unresolved requirements" are achievement gaps.
  - "Assumptions" are records with `source_type: "inferred"`, a `probability` below 1, and a `reason`. The prompt says so
    in [CODE] `prompts/prompt_generation.py:8-14`: "Observed State/Relation has probability 1 and no reason; inferred
    content has probability below 1 and a reason. Keep only goal-relevant facts and never invent evidence."
- **Confidence semantics** ([CODE] `docs/examples.md:43`): "`probability` is the runtime field for a record's confidence.
  Inferred State/Relation confidences are independent and are not normalized into a categorical distribution. Observed
  records have unit confidence. The structured world is the source of truth; `belief_text` is a derived policy-facing view."
- **Provenance in code is thin.** The project page promises "provenance". In code, a record carries only `source_type`
  (observed or inferred) and a free-text `reason`. No world record points to an evidence step and none has a timestamp.
  `grep -i "provenance|timestamp|valid_from|observed_at"` over belief/, prompts/, baselines/, contexts/ and main.py finds
  nothing. The only `evidence_step` field is on Sentinel issues (`belief/beliefSentinel.py:29`). The project-page
  illustration tracks "sources" per fact (`_data/pos_experience.yml`), but that is a UI illustration.

## 4. How the belief is updated

- **Initialization** ([CODE] `belief/manager.py:157-229`, `reset`): an LLM call (`build_initial_belief_prompt`) takes the
  task and first observation. It returns `goal_specification`, entities, states, relations, both gap lists and the
  frontier. The result is validated and recorded at step -1.
- **Per-step update** ([CODE] `manager.py:231-360`, `update` and `_update_belief`):
  1. Append (step, action, observation, done, success, score, available_actions) to `self.raw_trajectory` (lines 237-247).
  2. Deep-copy the committed belief (line 268).
  3. The LLM returns a **delta**: `remove_state_ids`, `remove_relation_ids`, `upsert_entities/states/relations`, plus the
     **complete** current gap lists and the frontier. The schema is in `prompts/prompt_generation.py:65-79`. The prompt
     text at lines 150-153 reads: "Produce one incremental candidate update. Omitted World records remain unchanged; remove a
     State or Relation only when the observation invalidates it. Return the complete current Gap lists. Keep the existing
     Frontier while its Gap remains, otherwise select an exact target from the new Gap lists."
  4. The execution example at lines 82-84 says: "when new evidence directly establishes a task-relevant state change,
     replace contradicted facts, remove only the Gaps resolved by that evidence, and preserve every other unresolved Gap."
     The diagnostic example at lines 87-89 says: "a new negative test may lower an inferred diagnosis probability while
     adding the observed test State. This is a valid belief revision; preserve competing hypotheses not addressed by the
     test."
  5. `_build_candidate` (lines 557-585): "Apply a delta to a deep copy without mutating the committed belief". Gap targets
     are stabilized against equivalent earlier gaps, and the frontier is selected.
  6. `_validate_candidate` runs the Sentinel (section 5). Then `_record_belief_update` and the commit
     (`self.belief_state = final`, line 306).
  7. `_record_snapshot` (lines 741-762), Sentinel progress scoring, health/recovery update, and an LLM call that refreshes
     `belief_text`.
- **The committed belief is overwritten in place.** It does not version records. `_apply_world_update` (lines 613-626)
  deletes and upserts records by ID. The project page shows this as "Replace an outdated state … Closed was true before.
  Open is the supported state now." ([PROJ] `_data/pos_experience.yml`, perception frame 3), and "The earlier location
  stays in the history. The current relation changes." (frame 2).
- **The policy sees no history.** [CODE] `prompts/react_prompt.py:469-522` (`build_belief_prompt`) builds the policy input
  from four things only:
  - "Current observation"
  - "Belief Text"
  - "Goal and Active-Gap structured subgraph"
  - "Active Gap", plus `FRONTIER_ACTION_SELECTION_CONTRACT` and an optional "Recovery constraint C_t"

  It includes no past observations or trajectory. The raw baseline is different: [CODE] `baselines/react.py:196-203` sends
  the full trajectory when `context["type"] == "raw"`.

## 5. How consistency is checked (the Belief Sentinel)

- [CODE] `docs/method.md:26-29`: "The synchronous Sentinel validates internal and evidence consistency. A detected issue
  permits one repair and re-audit. A rejected candidate does not replace the committed belief."
- **System prompt** ([CODE] `prompts/beliefSentinel_prompt.py:8-12`): "Validate one candidate Belief transition. Report an
  issue only when a changed State, Relation, or Gap is internally inconsistent or contradicts the supplied raw trajectory.
  Absence from a partial observation is not contradiction. Return at most one evidence-grounded issue and do not propose
  environment actions."
- **Issue schema** (lines 36-40): `targets`, `issue_type: "internal or external"`, `problem`, `evidence_step`,
  `evidence_quote: "verbatim evidence"`, `evidence`, `suggestion`.
- **Mechanical grounding filter** ([CODE] `belief/beliefSentinel.py:466-478`, `_valid_issue`): "Require a valid belief
  target and verbatim evidence from the cited step". The issue's targets must be existing IDs or gap targets, and the quote
  must appear verbatim, after normalization, in the cited step's action and observation. Only the first issue is considered
  (`raw_issues[:1]`, line 164).
- **Evidence window** ([CODE] `manager.py:510-525`, `_audit_scope`):
  - At init: local audit over the whole trajectory.
  - Every `global_audit_every_steps` (8 in the configs): global audit over the full `raw_trajectory`.
  - Otherwise: local audit over the last `recent_transition_count` (4) transitions.
  - Both modes use the same prompt (`build_global_audit_prompt` simply returns `build_local_audit_prompt`, lines 47-50).
    They differ only in the evidence window. Even the global audit is told to judge only **changed** records.
- **Outcome** ([CODE] `manager.py:408-508`):
  - No issues: the candidate is committed ("validated").
  - Issues: one repair LLM call, then a re-audit. If it passes, "repaired". If not, or if the audit errors, "rejected" and
    the previous committed belief is kept. Remaining issues are added to `pending_issues`.
- **Ablation config** ([CODE] diff of `configs/alfworld/pos.yaml` vs `pos_no_consistency.yaml`): only
  `consistency_enabled: false` changes. Progress scoring stays on.

## 6. Progress, Belief Trapping and recovery (the only cross-time mechanism)

- **Progress label u_t:**
  - Diagnostic tasks ([CODE] `belief/progressScoring.py:9-36`): computed in Python as
    `d_diag = 0.5 * sum(|c_t(x) - c_{t-1}(x)|)` over inferred records, with u = 1 if above 0.3.
  - Execution tasks: an LLM judge (`PROGRESS_SYSTEM_PROMPT`, `beliefSentinel_prompt.py:15-19`): "progress=1 only when it
    reduced the Gap, acquired evidence needed for it, or established a State/Relation on a plausible path to the Goal. A
    repeated failure or irrelevant change is 0."
- **Health** ([CODE] `docs/method.md:63-92`; code at `belief/trappingDetection.py:233-323`, formula at line 282):
  `H = 1 - max(P_E,P_A) * max(S,R)`, over the last K=8 transitions with verified progress. The signals are:
  - Persistence P_X: the fraction of the window's initial gaps that persist through the whole window.
  - Stagnation S = 1 - mean(u).
  - Recurrence R: the maximum over lags 1-4 of the rate at which **historical belief snapshots**, projected onto the
    **current** Active Gap, come within Jaccard distance 0.15 of each other.
  - Trapping is declared when H <= 0.25.
- [CODE] `docs/method.md:73-77`: "All historical worlds are projected onto the same current Active Gap using text matching
  and existing relations. … Text matching is an implementation approximation, not a learned semantic equivalence
  guarantee."
- **Pattern diagnosis** ([CODE] `docs/method.md:97-102`), tested in order:
  - Static: the last two full worlds are within epsilon.
  - Cycle: R >= 0.75 with dominant lag > 1.
  - Drift: the last two Active-Gap projections are within epsilon.
  - Otherwise: generic recovery.
- **Recovery** ([CODE] `belief/recoveryPlanning.py:9-65`): `C = C_pattern ∪ C_gap`, composed as text with no extra LLM
  call. Examples:
  - Static: "Do not repeat the latest ineffective action under the unchanged belief condition".
  - Cycle: "Avoid the transition that re-enters the detected {period}-step cycle; …".
  - Drift: "Reject off-gap actions and re-anchor the next decision to the Active Gap."
  - Epistemic: "Acquire new discriminative evidence that can resolve or narrow …"
  - Achievement: "Cause a task-relevant world-state change that reduces …"
- [CODE] `docs/method.md:114-117`: "Recovery never replaces the Active Gap or executes an action directly. After each scored
  nonterminal transition, release constraints if health exceeds the threshold; otherwise refresh them from the current
  diagnosis."

## 7. History, versioning, and whether the belief at an earlier time can be recovered

- **Kept (per episode, in memory, exported):** see [CODE] `manager.py:141-155` and `get_result` at 371-400.
  - `raw_trajectory`: append-only list of every action and observation.
  - `belief_update_history`: `{step, status, candidate_belief, final_belief}` for every update (`_record_belief_update`
    lines 587-611). This is a full serialized belief per step.
  - `belief_snapshots`: `{step, world, epistemic_gap_ids, achievement_gap_ids, frontier}` per committed step (lines
    741-762). Docstring: "Store a validated belief snapshot for the health window."
  - `frontier_history`, `health_transitions`, `health_history`, `recovery_history`, and Sentinel `audit_history` /
    `progress_history`.
  - All of these are written to `result.json`. Every model input and output and every lifecycle event goes to
    `events.jsonl`; [CODE] `utils/logger.py:1` describes it as "Append-only structured event logging".
- [CODE] `docs/method.md:131-133`: "Events and results retain raw observations, candidate and committed beliefs, progress,
  health components, the Active Gap, and recovery constraints."
- **Not provided:**
  - No API to query the belief at step t, no diff API, no as-of semantics. `BeliefManager`'s public surface is `reset`,
    `update`, `get_context`, `get_result` and `close` (probe output in section 9).
  - Records have no time fields.
  - History is cleared on `reset` for each case (lines 157-182), so nothing persists across episodes.
  - The policy never sees past beliefs.
  - Internally, past snapshots are read only by the trapping detector and `_cycle_transitions` (lines 912-950), which puts
    matched `world_before`/`world_after` snapshots into the Cycle recovery instruction.
- **Verdict:** the belief at an earlier step **can be recovered after the fact** from the exported logs. It was recorded
  when committed, so it carries no hindsight. But this is logging for analysis and health monitoring. It is not a
  versioned, queryable epistemic store.

## 8. Evaluation (numbers from [CODE] `docs/results.md` and [PROJ] `_data/pos_project.yml:20-65`; both are author-transcribed Table 1/2)

**Benchmarks and protocol** ([CODE] `docs/reproduction.md` "Evaluation protocol"):

| Benchmark | Cases | Metric | Budget |
|---|---|---|---|
| ALFWorld | 134 valid-unseen | task success | 50 actions |
| LOCA-Bench | 525 = 15 families × 5 seeds × 7 lengths (8K-256K) | pooled success | 100 MCP tool calls |
| RCA-100 | 103 cases | joint fault-type + root-cause-entity accuracy | 50 turns × up to 3 actions |
| ClinDiag | fixed balanced 604-case subset (Emergency excluded) | diagnosis accuracy | 30 tool calls |

**Backbones:** Qwen3.7-Plus, Kimi-K3, GLM-5.3. The same backbone is used for the policy, belief and Sentinel roles. The
ClinDiag provider and judge are fixed to Qwen3.7-Plus.

**Baselines:** Raw Trajectory (ReAct), ACON, PACE, HiAgent, LongHorizon-Harness.

Table 1, Qwen3.7-Plus (ALFWorld / LOCA / RCA-100 / ClinDiag, %):

| Method | ALFWorld | LOCA | RCA-100 | ClinDiag |
|---|---|---|---|---|
| Raw Trajectory | 62.69 | 43.62 | 24.27 | 38.91 |
| ACON | 66.42 | 49.90 | 27.18 | 39.74 |
| PACE | 67.91 | 17.33 | 28.16 | 41.89 |
| HiAgent | 66.42 | 24.57 | 28.16 | 40.07 |
| LongHorizon-Harness | 72.39 | 52.57 | 26.21 | 40.56 |
| **PoS** | **88.81** | **56.38** | **38.83** | **45.03** |
| w/o consistency validation | 73.88 | 44.57 | 31.07 | 44.54 |
| w/o trapping diagnosis & recovery | 73.13 | 48.19 | 33.98 | 42.38 |

PoS on the other backbones:
- Kimi-K3: PoS 94.03 / 74.29 / 51.46 / 54.80. Best baselines: 91.79 (LH-Harness) / 70.86 (ACON) / 41.75 (HiAgent) /
  51.82 (LH-Harness).
- GLM-5.3: PoS 97.01 / 70.86 / 49.51 / 52.15. Best baselines: 95.52 / 65.90 / 40.78 / 46.85.

Headline claims:
- [CODE] `README.md:49`: "Relative gains over the strongest evaluated baseline with the same backbone reach **22.68% on
  ALFWorld** and **37.89% on RCA-100**."
- **Compute** ([CODE] `docs/results.md:67-75`, Table 2, RCA-100/Qwen3.7-Plus, mean per episode over 103 cases):
  - Raw Trajectory: 355.70K Task Agent tokens, 355.70K total.
  - PoS: 281.20K Task Agent tokens, **1,800.13K total (5.06×)**.
  - Accuracy: 24.27 to 38.83.
- **Generic vs factorized recovery** ([PROJ] `pos_project.yml:20-24`, Figure 3 right, Qwen3.7-Plus):
  ALFWorld 76.87 vs 88.81; LOCA 49.33 vs 56.38; RCA 31.07 vs 38.83; ClinDiag 42.22 vs 45.03. The page says at line 120:
  "These are final outcomes over all evaluated cases, not trap-recovery success rates."
- **Context scaling** ([PROJ] `progression-of-states-project.html:123`): "At 256K context, PoS exceeds the strongest tested
  baseline by 10.67-16.00 percentage points across the three backbones. The experiment varies LOCA-Bench
  environment-description length."
- **Trapping-pattern distribution** ([SEC-K] only, unverified): ALFWorld is mostly Cycle; LOCA-Bench and RCA-100 are mostly
  Drift (55.93%); ClinDiag is mostly Static (78.25%).

Release and reproducibility caveats (author-stated):
- [CODE] `docs/reproduction.md` "Release scope": "The manuscript also evaluates ACON, PACE, HiAgent, and
  LongHorizon-Harness. Their implementations and configurations are **not included in this release**."
- Also from `docs/reproduction.md`: "No historical experiment outputs are bundled."
- [CODE] `docs/results.md:81`: "The manuscript used live API models without fixed snapshots".
- [CODE] `docs/development.md:47`: "No paid model or complete benchmark evaluations were performed as part of the
  source-package or documentation checks."
- [CODE] `docs/development.md:52`: "it does not establish that the public templates have independently reproduced those
  results."

## 9. My own verification in code (run 2026-10-03)

- I installed `openai==2.46.0 PyYAML==6.0.3 tqdm==4.68.4` into `scratchpad/venv-pos`.
  - `scripts/check_behavior_equivalence.py --self-test` printed "Passed: Raw, full PoS, both ablations, and diagnostic PoS."
  - `scripts/check_method.py` ran 28 tests, all OK.
  - Both make no API calls and use fixed responses and a mock environment.
- **Probe** `scratchpad/lit/pos_src/probe_pos.py`. It drives `BeliefManager` with scripted model replies:
  - Initial belief: s1 = "Mug 1 is dirty.", plus one epistemic and one achievement gap.
  - Update at step 0: upsert s1 = "Mug 1 is clean." and empty gap lists.
  - Output:

```
CURRENT s1: Mug 1 is clean.
CURRENT gaps: [] []
HISTORY steps/status: [(-1, 'validated'), (0, 'validated')]
HISTORY[0] final s1: Mug 1 is dirty.
HISTORY[0] final gaps: [{'target': 'Mug 1 must be clean', 'reason': 'Mug 1 is dirty.'}]
SNAPSHOT keys: ['step', 'world', 'epistemic_gap_ids', 'achievement_gap_ids', 'frontier']
SNAPSHOT steps: [-1, 0]
State record fields: ['state_id', 'entity_id', 'description', 'probability', 'reason', 'source_type']
Public methods: [... 'get_context', 'get_result', 'reset', 'update', 'close', + attribute lists ...]
raw_trajectory steps: [-1, 0]
result keys: ['active_recovery', 'belief_health', 'belief_health_history', 'belief_state', 'belief_update_history', 'frontier_history', 'health_transitions', 'raw_trajectory', 'recovery_history']
```

  - **Interpretation:**
    - The current belief overwrites "dirty" with "clean" in place, and resolved gaps disappear from the current belief.
    - The step-indexed log still holds the earlier belief.
    - Records carry no time fields.
    - There is no state_at(t) accessor.

## 10. Limitations

- **Author-stated in the repo [CODE]:**
  - The extra inference cost (5.06× total tokens).
  - Text matching for gap and recurrence identity is "an implementation approximation".
  - No fixed API snapshots.
  - Four baselines are not released.
  - The ClinDiag PoS template is untested with a real model in the release validation.
  - ALFWorld build issues on the release check host.
- **Author-stated in paper Appendix G, from [SEC-V] only (secondary, unverified):**
  - "Belief maintenance adds computation; repeated natural-language updates may omit information or distort meaning."
  - "Internally consistent beliefs can still contain incorrect judgments when backbone knowledge is inadequate. PoS lacks
    systematic external domain-knowledge retrieval."
  - [SEC-K] also says the authors name the token overhead as the main limitation.
- **Analyst-noted by [SEC-V]:**
  - Comparisons match action budgets but not compute.
  - Detector precision and recall are not measured.
  - No uncertainty intervals or repeated runs.
  - Confidence values are uncalibrated.
- **My own inferences from code:**
  - Everything is episode-local. `reset` clears all history for each case, so there is no cross-episode memory.
  - The belief prompt says "Keep only goal-relevant facts", so information judged irrelevant to the current goal is
    dropped from the decision context. The policy then cannot recover it, because raw history is not shown to the policy.
  - The goal is fixed for the episode.
  - Consistency audits judge only changed records. A stale unchanged record contradicted by older evidence is not
    re-examined unless an update touches it.

## 11. Capability ratings with evidence (summary; details in StructuredOutput)

| # | Capability | Rating | Key evidence |
|---|---|---|---|
| 1 | immutable_historical_observations | yes (episode-scoped) | `raw_trajectory` append-only, `manager.py:161-170,237-247`; `events.jsonl` append-only |
| 2 | historical_world_state | no | No environment snapshots; W_t snapshots are belief estimates, not world state |
| 3 | historical_epistemic_state | partial | `belief_update_history` / `belief_snapshots` per step (`manager.py:587-611,741-762`); offline logs, no query API, no time fields, policy never sees them |
| 4 | historical_policy_objective_state | partial | `frontier_history` and `recovery_history` log Active Gap and constraint changes per step; Goal fixed (`beliefStates.py:15`); no model/policy versioning |
| 5 | execution_checkpoints | no | Only case-level `skip_existing`/`run_until_complete`; candidate deep copy and reject-to-previous is a transactional commit, not a restorable checkpoint |
| 6 | replay | no | Fixed-response self-test is a regression harness, not replay from a historical point |
| 7 | fork_from_historical_state | no | none |
| 8 | counterfactual_action_branches | no | Actions run in the real environment; only candidate *belief* updates are uncommitted |
| 9 | branch_provenance | no | none |
| 10 | explicit_current_belief_state | yes | B_t = (W_t, G, Δ^E, Δ^A), `beliefStates.py`, `worldStates.py` |
| 11 | uncertainty_representation | yes | probability, observed/inferred, reason; epistemic gaps; pending Sentinel issues |
| 12 | future_state_rollout | no | none |
| 13 | multiple_prospective_branches | no | Competing *diagnostic hypotheses* are about the present, not futures |
| 14 | probability_over_futures | no | Probabilities are on current records |
| 15 | backward_requirements | partial | Achievement gaps = goal-vs-current discrepancies; frontier contract allows prerequisite actions; no regression chain, no feared futures |
| 16 | intervention_aware_forecasting | no | none |
| 17 | prevented_futures_preserved | no | none |
| 18 | predicted_vs_realized | no | No predictions recorded; the Sentinel checks belief vs observations, not forecast vs outcome |
| 19 | cross_time_state_querying | partial | Internal Jaccard diffs between belief snapshots (lags 1-4, K=8) and gap persistence; no general state_at/diff API |
| 20 | unified_temporal_abstraction | no | Present-centric |

## 12. Things I could not verify

1. The paper's own text: section 3 equations, Algorithm 1, the related-work positioning (§2.2), Appendix B-G, and Tables 3-9.
   The numbers above are the authors' transcriptions in [CODE] and [PROJ]. They agree with each other and with [SEC-V], but I
   did not see the PDF or HTML.
2. Whether the paper body expands "PoS" as "Progression of States". README, CITATION.cff and the project page do; the
   abstract does not.
3. Paper Appendix G limitations verbatim. I have only the [SEC-V] paraphrase.
4. The Figure 3 trapping-pattern percentages (Drift 55.93%, Static 78.25%). I have only the [SEC-K] summary.
5. Whether the released code is byte-identical to the code used for the paper's runs. The repo itself says no historical
   outputs are bundled and no paid or benchmark runs were done for release validation.
6. The exact versions and availability of the backbones (Qwen3.7-Plus, Kimi-K3, GLM-5.3) and of the baseline adaptations
   (ACON, PACE, HiAgent, LongHorizon-Harness). The baselines were not released.
7. Whether the paper discusses belief versioning or as-of querying anywhere. The code and docs give no sign of it.
