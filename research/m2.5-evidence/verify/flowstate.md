# FlowState (arXiv:2609.34565): adversarial verification notes

Verifier notes, 2026-10-03.

## 0. What could be accessed

### Not accessible
- **WebSearch:** budget exhausted. The first call returned "this session has used its web search budget (200 of 200 WebSearch calls)". So I could **not** re-query the arXiv HTML.
- **curl:** blocked (proxy 403 connect_rejected) for export.arxiv.org, api.openalex.org, api.crossref.org, web.archive.org and grep.app. Probed 2026-10-03.
- **Consequence:** I could not independently re-read any method-level text (M_k, G_k, S_k,t, ISU/PSA rules, node types, relations, ablation). For those claims my verification is limited to:
  - internal consistency;
  - whether the quoted extracts in notes/flowstate.md support each rating.

### Accessible primary or near-primary sources (raw.githubusercontent.com, files found via GitHub MCP code search)
Saved under verify/flowstate_src/.

**V1. flybfree/AI-Wiki @ master** — raw/papers/2026-09-28_08-18-03Z_FlowState_ExecutionStateasMemoryforLong_HorizonLLM.md
- An arXiv-API dump: `url: http://arxiv.org/abs/2609.34565v1`, `published: 2026-09-28T08:18:03Z`.
- Full author list: Minghao Li, Bangyan Li, Zifan Wang, Yulong Li, Hu Xu, Gan Zhang, Jingtong Wu, Wenqiang Xu.
- Full abstract, verbatim. Key sentences:
  > "we propose FlowState, which treats execution state as memory that can be retained and revisited across requests, unifying current decision-making with the reuse of historical information. FlowState preserves semantically typed state nodes, their relations, and references to raw tool observations, separating persistent retention from on-demand access. Within a single execution loop, Incremental State Update (ISU) maintains the current state based on new inputs and feedback, while Progressive State Access (PSA) progressively reveals historical states and supporting evidence as needed during reasoning. Together, these mechanisms enable agents to reassess prior decisions in light of new information and guide subsequent actions. Compared with a full-context baseline using the same DeepSeek-V4-Flash model, FlowState improves the average success rate on MemoryArena and the average pass rate on $τ^3$-Bench by 4.55 and 13.95 percentage points, respectively, while reducing total token consumption by 43.2% and 40.6%."

**V2. isaacveg/mas-daily @ main** — daily/2026-10-02.md, entry 11
- `| FlowState ... | Ant Group | T1 | llm agent | v1 / Mon, 28 Sep 2026 |`
- "机构（T1）：Ant Group ｜ 主要作者：Minghao Li（共 8 人）"
- Category cs.AI. The English abstract is identical to V1.

**V3. waitfor-night/textworld-social-simulation-research** — papers/2609.34565.md
- Third-party card: "代码 / 数据：未确认公开仓库" (no confirmed public repository).
- Read at abstract level only.

**V4. Dannyzen/eliezer-weekly-roundup-public @ master** — AgenticAI/2026-09-29/reasoning.md
- A blog paraphrase of the abstract.
- **Caution:** its "Practical method" bullet ("Define typed nodes for goals, decisions, dependencies, unresolved questions, effects, and evidence references") is the blogger's recommendation, **not** the paper's node taxonomy. Do not cite it as evidence of uncertainty or unresolved-item nodes.

**GitHub code search**
- `"Incremental State Update" "Progressive State Access"`: 6 hits, all digests or cards (V1–V4, plus an unrelated candidates.json).
- `"Historical State Index"`: only go-ethereum and other unrelated hits.
- No official code repository found. This is consistent with the analyst's finding.

## 1. Key claims checked against V1–V3

| Claim | Status |
|---|---|
| Title and full author list | CONFIRMED (V1) |
| Submitted 2026-09-28 | CONFIRMED (V1 published 2026-09-28T08:18:03Z; V2 "v1 / Mon, 28 Sep 2026") |
| Affiliation is Ant Group | CONFIRMED at institution level (V2) |
| "all of Ant International, Ant Group" | Not independently confirmed (V2 says only "Ant Group") |
| Abstract quotes: retained and revisited across requests; typed state nodes, relations, references to raw tool observations; ISU/PSA; "reassess prior decisions in light of new information"; +4.55 / +13.95 pp; −43.2% / −40.6% tokens | CONFIRMED verbatim (V1) |
| No public code | CONSISTENT (V3 plus GitHub code search). The "release at an appropriate time" quote itself is not re-verified. |

**Not independently re-verifiable** (rest only on the analyst's WebSearch extracts):
- every method-level quote;
- the hotel D7/D8 example;
- node and relation types;
- the validation rules;
- Table 3 numbers;
- "beats ZipAct+BM25 on all nine metrics";
- related-work statements on MAGE and ZipAct.

The analyst's extracts are internally consistent: relations were confirmed by two independent returns, and the 20.0/7.9 per-domain gains average to the abstract's 13.95. But they are summaries, not verbatim text.

## 2. Claims corrected

**C1. "It improves exactly this behaviour [notice/reopen an earlier decision with evidence] over full context, ZipAct+BM25, Mem0, BM25 and ReasoningBank."**
- This overreaches.
- The evaluated benchmarks are MemoryArena (information reuse across interdependent subtasks) and τ³-Bench (policy-constrained tool use). They report aggregate success, pass rate, PS and tokens.
- The hotel D7→D8 reassessment is a motivating example. Nothing retrieved shows it was itself evaluated, or that the gains were attributed to decision reassessment.
- The abstract says the mechanisms "enable agents to reassess prior decisions". That is a design claim, not a measured, isolated effect.
- Corrected reading: FlowState improves aggregate long-horizon task metrics. The decision-reassessment behaviour is claimed and illustrated, not isolated in evaluation (as far as retrieved).

**C2. The V4 blog's "unresolved questions" node type is not paper content.**
- The analyst did not use it, but downstream readers might.

## 3. Rating review (per capability)

The ratings rest on the analyst's extracts. Below, "kept" means the quoted extract supports the rating and I found nothing contradicting it.

1. **immutable_historical_observations: partial — kept.**
   - Supported: "historical states retain their original source requests and cannot be deleted"; Update/Remove are limited to the current request.
   - Gaps: raw results are kept only "if referenced"; within-request edits are made in place.
2. **historical_world_state: no — kept.**
   - knowledge/attribute nodes give observed-then, which is epistemic, not true-then. Nothing separates world truth from agent observation.
   - Arguable as "partial-as-observed", but the capability asks for world reconstruction. Under smoke_v1's true-then vs known-then split, FlowState offers only known-then.
3. **historical_epistemic_state: partial — kept.**
   - Request-tagged, non-deletable judgement nodes. No cutoff operator.
4. **historical_policy_objective_state: partial — kept (generous).**
   - User preferences/requirements and agent "task objectives, plans" are request-tagged nodes.
   - The agent's own system policy and model are not tracked.
   - Use of 'supersedes' across requests is structurally possible: refs only need to resolve to valid ids. Actual use is unverified.
5. **execution_checkpoints: no — kept.** Semantic memory with no restore.
6. **replay: no — kept.**
7. **fork_from_historical_state: no — kept.** The paper contrasts itself with MAGE's branching Revise (extract).
8. **counterfactual_action_branches: no — kept.**
9. **branch_provenance: no — kept.** Has dependency provenance, not branch provenance.
10. **explicit_current_belief_state: yes — kept.**
    - The abstract (V1, verbatim) confirms "ISU maintains the current state based on new inputs and feedback" and "semantically typed state nodes".
11. **uncertainty_representation: CHANGED no → partial.** Reasoning:
    - The capability definition includes "explicit ... unresolved items in state".
    - The analyst's own extracts (two phrasings) say the typed agent-side category records risks:
      > "agent-side *judgements* record the agent's assessments of task objectives, plans, decisions, and risks"
      > "Agent-side judgements record agent assessments of task goals, plans, intermediate decisions, and execution risks."
    - Risks are explicit, typed (judgement) state items about what may go wrong, i.e. represented uncertainty. The hotel example also stores an open conditional ("planning to reconsider if B becomes cheaper"), which is an unresolved item that later gets re-evaluated.
    - There is **no** confidence or probability attribute: the documented node fields are source request, semantic id, category and content.
    - Table 6 and the Appendix B.3 prompts were not read, so a richer status field cannot be ruled out.
    - So: partial. Unresolved and risk items exist as typed content; there is no calibrated uncertainty.
    - Evidence source: the analyst's WebSearch extracts of https://arxiv.org/html/2609.34565, quoted in notes/flowstate.md §4.3 and §3. I could not re-query them (budget exhausted).
12–18. **no — kept.**
    - No rollout, prospective branches, probabilities, goal regression, forecasts, prevented-future labels or calibration appear in any extract or in the abstract (V1).
    - These are absence-of-evidence judgements.
19. **cross_time_state_querying: partial — kept (weak).**
    - The per-request index plus disclose-by-id gives a crude "what was created in request k" lookup.
    - There is no state_at, diff or as-of operator.
20. **unified_temporal_abstraction: partial — kept.**
    - Abstract (V1): "unifying current decision-making with the reuse of historical information".
    - The extract says historical states are expanded "through the same representation used for current states".
    - No counterfactual or prospective states.

## 4. Strongest threat to the project

FlowState (Ant Group, 2026-09-28) is public prior art for smoke_v1's core behaviour: a later observation changes the meaning of an earlier decision, and the agent revisits that decision and its linked evidence, then forms a new decision without overwriting the old one.

It does this with:
- typed, request-tagged, non-deletable state nodes;
- supports/derives/follows/supersedes edges.

It reports wins over full context and over retrieval memories (BM25, Mem0, ReasoningBank) at about 40% fewer tokens. That is roughly the class of baseline smoke_v1 uses.

Two consequences follow:

1. **A structured-state baseline is the fair control.** A temporal-agent win over the current smoke_v1 baseline could come from structured decision/evidence state rather than from time navigation, so a FlowState-style variant is needed.
2. **The "known then" cutoff may be nearly free in FlowState.** Because every node carries an immutable source request, filtering to nodes with source_request ≤ k is a trivial add-on. The project must show that cutoff-correct reconstruction changes outcomes, not only that it can be stated.

What remains distinctive:
- world-truth-at-t as distinct from observed-at-t;
- forward-looking forecasting and intervention semantics;
- branching.

smoke_v1 does not yet exercise most of these.
