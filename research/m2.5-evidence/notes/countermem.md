# COUNTERMEM: World-Model Verified Counter-Factual Memory for Language Agents (arXiv:2609.31874)

Analyst notes, 2026-10-03. Lane: single-system deep read for the temporal-agency novelty assessment.

## 0. Read this first: what evidence exists

**The paper body was not available to me. Every claim below about COUNTERMEM is taken from the arXiv abstract and metadata only.**

- WebSearch was unavailable. The first call returned: "Web search was not performed: this session has used its web search budget (200 of 200 WebSearch calls)." No arXiv HTML extracts were obtained.
- The orchestrator reports that arxiv.org, export.arxiv.org, alphaxiv.org, semanticscholar.org and openreview.net are blocked. I did not retry them.
- **No official code exists.** The abstract says: "Code will be released upon acceptance." See section 4 for the repo search.
- Instead, I found the arXiv abstract mirrored verbatim in 4 independent GitHub-hosted feeds, using GitHub code search through the GitHub MCP. I fetched each file through raw.githubusercontent.com at a pinned commit.
  - After normalizing whitespace, all 4 copies are byte-identical: 1768 chars, sha256 prefix `ce35b64d5d4d8d19`.
  - I treat this text as the primary source.
- **Rating convention used below:**
  - "no (abstract-level)": the abstract describes the whole pipeline (trigger, alternative evaluation, storage, reuse, evaluation), and nothing in it provides the capability. The full text could still revise this.
  - "unclear": the abstract hints at something related, but the details needed to rate it are not there.
- Do not read the ratings as verified against the paper body or code. Neither was available.

## 1. Sources and how they were obtained

| # | Source | How obtained | What it gives |
|---|---|---|---|
| S1 | https://arxiv.org/abs/2609.31874 (canonical) | Not fetched (host blocked). Cited by all mirrors. | n/a |
| S2 | raw.githubusercontent.com/xiaoqixiaowei/daily-arxiv-ai/14963ab30b567e039c656dea1ce2e39a39f9a0a7/data/2026-09-29.jsonl, line 14 | GitHub code search for "2609.31874", then curl raw at pinned commit | Verbatim abstract plus arXiv metadata fields (authors, categories, comment) |
| S3 | raw.githubusercontent.com/angelababyhuang/013-ai-knowledge-base/ca7bf149523c308a7d67f38548b8838dbd1ac3fe/knowledge/raw/rss-2026-09-29.json | same | arXiv cs.AI RSS item `oai:arXiv.org:2609.31874v1`, verbatim abstract (`summary_raw`), published "Tue, 29 Sep 2026" |
| S4 | raw.githubusercontent.com/xiaoqianran/web-001-Blog/8809ac57053ae41e01dd0bec533febdf30c5b2e8/content/data/rss-feeds/2026-09-29.json | same | Same RSS item, verbatim abstract |
| S5 | raw.githubusercontent.com/flybfree/AI-Wiki/HEAD/raw/papers/2026-09-25_18-12-38Z_COUNTERMEM_World_ModelVerifiedCounter_FactualMemor.md | GitHub code search "verified counterfactual memory", then curl raw | Verbatim abstract; `published: 2026-09-25T18:12:38Z`; url `http://arxiv.org/abs/2609.31874v1` |
| S6 | raw.githubusercontent.com/IAAR-Shanghai/Awesome-AI-Memory/13ac6e97cc829854cc15fc17e665134be8e034e8/screening/2026-09-30-review.json | GitHub code search | Curated-list screening record. `"reading_scope": "abstract"`, so the curators also read only the abstract. |
| S7 | raw.githubusercontent.com/waitfor-night/textworld-social-simulation-research/5655014a90dcdb128207059dfe807888faab70b7/papers/2609.31874.md | GitHub code search | Third-party paper card (Chinese). States "代码 / 数据：未确认公开仓库" (no confirmed public repo). Its "limitations" line is the card author's inference, not a paper quote. |
| S8 | raw.githubusercontent.com/flybfree/AI-Wiki/HEAD/raw/summaries/SUMMARY_PAPER_2026-09-28_COUNTERMEM__... | GitHub code search | LLM (qwen3.6-35b-a3b) summary of the abstract. It adds nothing. |
| S9 | raw.githubusercontent.com/wdndev/wdndev.github.io/4506878506b87c3d412ebc621068c00091cd33f7/daily/domain/202609/2026-09-30/index.html | GitHub code search | Abstract only. The full-text "LLM Analysis" failed: "Kimi内容未就绪或抓取失败: 2609.31874 (HTTP 429)". |
| S10 | git clone https://github.com/DeltaLabTLV/CounterMem.git (commit 1b338c0c, 2026-08-26) | git clone into repos/DeltaLabTLV_CounterMem | **Name collision, not this paper.** See section 4. |
| S11 | Local copy of IAAR-Shanghai Awesome-AI-Memory list (verify/awesome/IAAR-Shanghai_Awesome-AI-Memory.md, around line 2618; verify/awesome/iaar.tsv:168) | Already in scratchpad | Listing date 2026-09-25, Chinese one-line summary |

Local copies of S2 to S9 are in /tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/lit/countermem/.

## 2. Metadata (from S2 and S5)

- Title: "COUNTERMEM: World-Model Verified Counter-Factual Memory for Language Agents"
- Authors: Hongji Pu, Ruixiang Tang, Yongfeng Zhang (S2 `"authors"`, S3 `"author"`, S5 `authors:`)
- Submitted: 2026-09-25T18:12:38Z (S5 `published:`). Announced 2026-09-29 (S3 RSS `"published": "Tue, 29 Sep 2026 00:00:00 -0400"`). v1.
- Category: cs.AI (S2 `"categories": ["cs.AI"]`)
- arXiv comment (S2): `"comment": "25 Pages, 8 Figures, ICLR 2027"`.
  - Acceptance status is **unclear**. Read together with "Code will be released upon acceptance", the comment probably marks a submission, not an acceptance. That is an inference.
- Author affiliations: not in any source I obtained. **Unclear.**

## 3. Verbatim abstract (identical in S2, S3, S4, S5)

> Existing agent memory frameworks mainly create memory through an agent's interaction with the factual world, e.g., remembering feedback from actions taken to improve performance on future tasks. However, these frameworks seldom ask the "what if" question during memory construction: what if a different action had been taken, would the feedback have changed, and how could this feedback become useful memory? Obtaining such feedback directly in an active environment can be expensive and can alter the state needed for comparison. In this work, we introduce COUNTERMEM, a reinforcement-learning framework for constructing and using verified counterfactual memory across tasks. After a failed action, COUNTERMEM evaluates local alternatives from a copy or reset of the original state using executable world models, such as tests, proof checkers, and solvers. It stores improvements with the original and corrected actions, checked outcomes, and conditions for reuse. A learned memory-use policy selects a retrieved record or skips memory to balance task success and interaction cost, while the base LLM remains fixed. Both memory and policy are frozen during held-out evaluation. We evaluate COUNTERMEM on 12 benchmark settings across six domains. With gpt-oss-120b, COUNTERMEM improves both ReAct and Reflexion on all 12 benchmarks across six domains, averaging a gain of 12.6 percentage points over their unaugmented versions. In the four-domain comparison across two backbones, task-run tokens decrease by 7.7-42.0%, excluding offline selector-training costs. Further analyses show that removing verification or persistent storage weakens the gains, while applying verified corrections to unsuitable decisions can reverse them. Code will be released upon acceptance.

### 3.1 Claim-by-claim mapping (all claims from the abstract; "PAPER CLAIM" = stated, "INFERENCE" = mine)

| Question | Abstract evidence (verbatim) | Status |
|---|---|---|
| Trigger | "After a failed action" | PAPER CLAIM. Triggered by the agent's own failed action. |
| How prior states are copied or reset | "evaluates local alternatives from a copy or reset of the original state" | PAPER CLAIM, but the mechanism is unknown. Snapshot vs. environment reset vs. re-execution, and what "original state" contains (environment only, or agent context too), are **unclear**. |
| Why copy or reset at all | "Obtaining such feedback directly in an active environment can be expensive and can alter the state needed for comparison." | PAPER CLAIM. They explicitly preserve the original state for comparison, which is fork semantics. |
| How alternatives are generated | "local alternatives" | **Unclear.** No generator is described (LLM-proposed, enumerated, or mutation-based). "Local" suggests the change is confined to the failed step or its neighborhood (INFERENCE). |
| What the "world model" is | "executable world models, such as tests, proof checkers, and solvers" | PAPER CLAIM. The "world model" is an executable verifier or oracle, **not** a learned or LLM-imagined dynamics model. |
| How verification works | "verified counterfactual memory"; "checked outcomes"; "stores improvements" | Partly stated. Outcomes are checked by executing the verifier. A record is kept only if it is an improvement. The improvement criterion (pass/fail vs. score), number of alternatives, and depth are **unclear**. |
| What is persisted | "It stores improvements with the original and corrected actions, checked outcomes, and conditions for reuse." | PAPER CLAIM. Record = (original action, corrected action, checked outcome(s), reuse conditions). It is unstated whether non-improving alternatives, the state or observation, an episode/task id, or a timestamp are stored. **Unclear**, but "stores improvements" suggests failed alternatives are dropped (INFERENCE). |
| Reuse | "A learned memory-use policy selects a retrieved record or skips memory to balance task success and interaction cost, while the base LLM remains fixed." | PAPER CLAIM. Retrieval method, how a record is injected (prompt vs. action override), and the policy's input features are **unclear**. |
| What is RL-trained | "a reinforcement-learning framework"; "offline selector-training costs" | PAPER CLAIM that the framework is RL and that a "selector" is trained offline. The base LLM is fixed. INFERENCE: RL trains the memory-use policy (the selector). |
| Train/test protocol | "Both memory and policy are frozen during held-out evaluation." | PAPER CLAIM. No memory writes during test. Whether the world model or verifier is called at test time is **unclear**. |
| Scale of eval | "12 benchmark settings across six domains" | PAPER CLAIM. Which benchmarks and domains is **unclear**. INFERENCE from "tests, proof checkers, and solvers": code, formal proofs, and solver tasks are likely among them. |
| Main number | "With gpt-oss-120b, COUNTERMEM improves both ReAct and Reflexion on all 12 benchmarks ... averaging a gain of 12.6 percentage points over their unaugmented versions." | PAPER CLAIM. Baselines named are ReAct and Reflexion (unaugmented). Whether other memory baselines (e.g. ExpeL/AWM-style experience memory) were compared is **unclear**. |
| Cost | "In the four-domain comparison across two backbones, task-run tokens decrease by 7.7-42.0%, excluding offline selector-training costs." | PAPER CLAIM. The second backbone is unnamed. Offline construction and verification cost is excluded. |
| Ablations | "removing verification or persistent storage weakens the gains, while applying verified corrections to unsuitable decisions can reverse them." | PAPER CLAIM. Verification and persistence matter. Misapplied corrections are harmful, which motivates the learned skip. |
| Code | "Code will be released upon acceptance." | PAPER CLAIM. No public code. |

### 3.2 Factual vs. counterfactual memory, and provenance

- The paper frames itself against factual memory: "Existing agent memory frameworks mainly create memory through an agent's interaction with the factual world ... these frameworks seldom ask the 'what if' question".
- **At the record level, factual and counterfactual are separated by field:**
  - the "original ... action" is the factual action that failed;
  - the "corrected action" with "checked outcomes" is the verified counterfactual.
- **At the store level, separation is unclear.** The abstract does not say whether factual (Reflexion-style) memories share a store with counterfactual records, or whether records carry a type label.
- **Provenance of a counterfactual branch is partial.** The record keeps the original action, the corrected action, and the outcome. It does not mention:
  - a parent state id, divergence time, or episode/task id;
  - the generating reason;
  - failed alternatives. Only "improvements" are stored, so the non-improving branches are apparently not kept (inference from wording).

## 4. Code search (none found for this paper)

- **Name collision, a different paper:** GitHub code search "COUNTERMEM" found `DeltaLabTLV/CounterMem`. I cloned it to repos/DeltaLabTLV_CounterMem.
  - README.md:3 says "Code release for the paper (Findings of EMNLP 2026):"
  - README.md:5 says "**CounterMem: Counterfactual Evaluation of Non-Parametric Memory Use in Retrieval-Augmented Generation**"
  - README.md:8 says "Mikhail Baklanov, Oren Barkan, Noam Koenigstein"
  - README.md:12 says "CounterMem keeps the RAG system fixed, edits only the retrieved context at three pipeline points"
  - grep for "2609", "world model" and "gpt-oss" in the repo returned nothing.
  - **This is a RAG-evaluation protocol, not arXiv:2609.31874. Do not cite it as COUNTERMEM code.**
- `git ls-remote https://github.com/agiresearch/{CounterMem,COUNTERMEM,countermem}.git` returned "could not read Username" for all three, meaning no public repo exists under those names.
  - I guessed this org from the author list. That the org belongs to an author lab is an assumption.
- `mcp__github__search_repositories "countermem"` failed twice with a 502 from api.github.com.
- S7 (third-party card) independently states "代码 / 数据：未确认公开仓库".

## 5. Capability ratings (abstract-level; see the convention in section 0)

| # | Capability | Rating | Evidence and what is missing |
|---|---|---|---|
| 1 | immutable_historical_observations | unclear | No mention of raw trajectory/observation logging. The persisted memory is a selective, derived record ("stores improvements ..."), not an append-only observation log. |
| 2 | historical_world_state | partial | "from a copy or reset of the original state": the environment state at the failed decision point is restored. Missing: arbitrary as-of-t reconstruction, cross-episode history, and how the reset is done. |
| 3 | historical_epistemic_state | no (abstract-level) | Nothing reconstructs what the agent knew or believed at t. Construction deliberately uses after-the-fact verifier outcomes (hindsight is the point). The stored "original ... action" is behavior, not belief. |
| 4 | historical_policy_objective_state | no (abstract-level) | "the base LLM remains fixed"; "Both memory and policy are frozen during held-out evaluation". Training changes the selector, but no versioned record of policy or objective is described. |
| 5 | execution_checkpoints | partial | Environment state is copied or reset in order to evaluate alternatives. Missing: whether the agent's runtime/context state is snapshotted and restorable; the checkpoint format. |
| 6 | replay | partial | Alternatives are re-executed from the restored point (local re-execution). Missing: replay of the original trajectory, determinism guarantees, and replay beyond the local step. |
| 7 | fork_from_historical_state | partial | Copying the original state preserves it while alternatives run: "can alter the state needed for comparison" is the stated motive. Missing: forks are local, ephemeral, one decision point, within one episode, and not a general primitive. The "reset" variant may not preserve the live original. |
| 8 | counterfactual_action_branches | yes | "evaluates local alternatives from a copy or reset of the original state using executable world models", run off the active trajectory. How alternatives are generated is unclear. |
| 9 | branch_provenance | partial | Record holds "original and corrected actions, checked outcomes, and conditions for reuse". Missing: parent state id, divergence time, episode id, reason. Non-improving branches are apparently not stored. |
| 10 | explicit_current_belief_state | no (abstract-level) | The memory is a library of correction records. No maintained beliefs, assumptions, or requirements structure. |
| 11 | uncertainty_representation | unclear | Reuse "conditions" and the learned skip handle applicability. No explicit confidence or unresolved-item fields are mentioned. |
| 12 | future_state_rollout | partial | Action-conditioned outcomes are computed by executing tests, solvers, or proof checkers on a copied state. Missing: this is retrospective verification after a failure, not forward imagination of the agent's future. There is no learned predictive model, and test-time use of the world model is unclear. |
| 13 | multiple_prospective_branches | partial | Several "local alternatives" are evaluated and compared from one state. Missing: they are retrospective, only improvements are kept, and no set of futures is maintained. |
| 14 | probability_over_futures | no (abstract-level) | Outcomes are "checked" (executed). No likelihoods are assigned. |
| 15 | backward_requirements | no (abstract-level) | Not described. "conditions for reuse" are applicability preconditions for a correction. That is a weak analog, not regression from a desired or feared future. |
| 16 | intervention_aware_forecasting | no (abstract-level) | No forecasting is described. |
| 17 | prevented_futures_preserved | no (abstract-level) | No forecasts exist. Non-improving alternatives are apparently not stored. |
| 18 | predicted_vs_realized | no (abstract-level) | It compares the factual outcome with a verified counterfactual outcome, not a prediction with a realization. The RL selector learns from task success and cost, which is not calibration of forecasts. |
| 19 | cross_time_state_querying | no (abstract-level) | Reuse is retrieve-and-select over records. No state_at(t), diff, or as-of queries. |
| 20 | unified_temporal_abstraction | no (abstract-level) | No single abstraction spans historical, actual, counterfactual, and prospective states. |

## 6. Relation to the temporal-agency thesis and smoke_v1

**Overlap (real prior art):**
- It asks "what if a different action had been taken" at an earlier decision point.
- It evaluates the alternative off the live state, by copy or reset, so the original is preserved for comparison.
- It uses executable checks; tests are an obvious fit for software.
- It persists the factual action and the verified counterfactual as a reusable record with applicability conditions.
- Ablations show verification and persistence matter, and misapplication hurts.
- This pre-empts any claim that "verified counterfactual re-evaluation of past actions, stored as memory" is novel.

**Non-overlap:**
- The trigger is the agent's own immediate failed action. It is not a later event that changes the significance of an earlier world-authored decision.
- It has no epistemic cutoff and no "known then vs. known now". It is hindsight by design.
- It does not track identity, objective, or policy over time.
- It has no prospective forecasts, so it cannot have prevented futures, predicted-vs-realized comparison, or backward requirements.
- It has no as-of queries and no general branch DAG.
- Memory is frozen at test time and reuse is cross-task, rather than reopening a specific historical artifact.

**smoke_v1 relevance:**
- A COUNTERMEM-style component (verified correction memory, keyed by reuse conditions, with tests as the verifier) could be a legitimate strengthening of the checkpoint+RAG baseline.
- It would need agent-visible tests only. It must never use the benchmark's hidden tests or ground truth (CLAUDE.md rule 3).
- It would not, by itself, address smoke_v1's core demand: notice that a later event reframes an earlier ADR or ticket, then state what was true then, known then, and known now.

## 7. Could not verify

- Any content of the paper body: method section, algorithms, record schema, retrieval method, selector architecture and RL objective, reward definition, alternative generator, number and depth of alternatives, improvement criterion.
- How "copy" vs. "reset" is implemented per domain, and whether agent context is part of the "original state".
- Whether non-improving alternatives are stored, and whether records carry state, episode, or time ids.
- Whether the world model or verifier is used at test time, and whether test-time failures trigger new counterfactual construction. The abstract says memory and policy are frozen.
- The 12 benchmark settings and 6 domains by name, the second backbone, per-benchmark numbers, variance or CIs, and whether stronger memory baselines (beyond ReAct and Reflexion) were compared.
- The exact ablation magnitudes ("weakens the gains", "can reverse them").
- Affiliations, venue status ("ICLR 2027" in the arXiv comment), and the limitations section.
- Code: none public. The "upon acceptance" release has not happened as of 2026-10-03, as far as GitHub code search shows.
