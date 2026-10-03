# Verification notes: COUNTERMEM (arXiv:2609.31874v1)

Verifier, 2026-10-03. Adversarial re-check of the analyst's ratings in notes/countermem.md.

## Evidence obtained

- WebSearch is again unavailable. My call (query "COUNTERMEM ... 2609.31874 method record schema copy reset state", allowed_domains arxiv.org) returned: "Web search was not performed: this session has used its web search budget (200 of 200 WebSearch calls)." No arXiv HTML extract exists, so the paper body is unread by both analyst and verifier.
- Abstract re-fetched by curl:
  - from raw.githubusercontent.com/xiaoqixiaowei/daily-arxiv-ai/14963ab30b567e039c656dea1ce2e39a39f9a0a7/data/2026-09-29.jsonl, line 14;
  - metadata: authors [Hongji Pu, Ruixiang Tang, Yongfeng Zhang], categories [cs.AI], comment "25 Pages, 8 Figures, ICLR 2027".
- I recomputed the mirror identity on local copies in lit/countermem/ (xiaoqixiaowei, angelababy RSS, xiaoqianran RSS, flybfree raw). After whitespace normalization, all 4 are 1768 chars with sha256 prefix ce35b64d5d4d8d19. CONFIRMED.
- flybfree_raw.md:3 reads `published: 2026-09-25T18:12:38Z`. CONFIRMED.
- repos/DeltaLabTLV_CounterMem/README.md:3-8 is the unrelated EMNLP 2026 Findings RAG-evaluation paper (Baklanov, Barkan, Koenigstein). CONFIRMED name collision.
- GitHub code search, run by me:
  - `"2609.31874"` returned 41 hits;
  - `COUNTERMEM "memory-use policy"` returned 1 hit;
  - `"counterfactual memory" "proof checkers" "solvers"` returned 5 hits.
  - Every hit is an abstract copy, an RSS item, an LLM summary, or a seen-id list. Examples: hretheum/exocortex-public radar 2026-W39.md:93 only extracts "The code for COUNTERMEM will be released upon acceptance."; angelababyhuang knowledge/articles/...countermem...json is a Chinese abstract summary.
  - No body text, PDF mirror, or code was found.
- Housekeeping: lit/countermem/lightrain_iclr_idea_factory.py is NOT about COUNTERMEM.
  - It is an unrelated idea-generator script.
  - Its line 522-531 is an idea "Irreversible-Action Counterfactuals" containing the phrase "Verified counterfactual memory should reduce irreversible errors".
  - Do not cite it as COUNTERMEM evidence.

Verbatim abstract sentences used below:
- A1: "Obtaining such feedback directly in an active environment can be expensive and can alter the state needed for comparison."
- A2: "After a failed action, COUNTERMEM evaluates local alternatives from a copy or reset of the original state using executable world models, such as tests, proof checkers, and solvers."
- A3: "It stores improvements with the original and corrected actions, checked outcomes, and conditions for reuse."
- A4: "A learned memory-use policy selects a retrieved record or skips memory to balance task success and interaction cost, while the base LLM remains fixed."
- A5: "Both memory and policy are frozen during held-out evaluation."
- A6: "Further analyses show that removing verification or persistent storage weakens the gains, while applying verified corrections to unsuitable decisions can reverse them."

## Rating-by-rating verdict

No rating changed. Every rating rests on the abstract only.

| # | Capability | Analyst | Verified | Note |
|---|---|---|---|---|
| 1 | immutable_historical_observations | unclear | unclear | A3 describes derived, selective records. Trajectory logging is neither affirmed nor denied. |
| 2 | historical_world_state | partial | partial | A2 restores "the original state" at one failure point. "Before the failed action" is a reading of "original state", not a quote. |
| 3 | historical_epistemic_state | no | no | Hindsight by design (A2: alternatives come after the failure; A3: improvements are judged by checked outcomes). Caveat: if "original state" includes the agent's context, the at-t context is restored implicitly, but nothing describes a cutoff or belief reconstruction. "No" holds at abstract level. |
| 4 | historical_policy_objective_state | no | no | A4 and A5. |
| 5 | execution_checkpoints | partial | partial | A2 copies or resets the environment state. Agent runtime state is unknown. |
| 6 | replay | partial | partial | A2 is local re-execution of alternatives, not a replay of the original. |
| 7 | fork_from_historical_state | partial | partial | A2 plus A1: the copy preserves the original "for comparison". It is ephemeral and local. |
| 8 | counterfactual_action_branches | yes | yes | A2 is the paper's core. |
| 9 | branch_provenance | partial | partial | A3 keeps the original and corrected action plus outcomes. There are no ids, times, or reasons. |
| 10 | explicit_current_belief_state | no | no | |
| 11 | uncertainty_representation | unclear | unclear | The reuse conditions and the skip option (A4) carry no explicit confidence. |
| 12 | future_state_rollout | partial | partial | Executable world models compute action-conditioned outcomes (A2). This is retrospective, and test-time use is unknown (A5 freezes memory and policy). |
| 13 | multiple_prospective_branches | partial | partial (weak) | It rests on the same sentence as #8 and #12: plural "local alternatives" compared with the original. Nothing prospective-from-present is described and no set is maintained (A3 keeps improvements only). Do not count it as independent prior art. |
| 14-20 | probability, backward requirements, intervention-aware forecasts, prevented futures, predicted-vs-realized, as-of queries, unified abstraction | no | no | The abstract describes the full pipeline (A2-A5), and none of these appear. Each "no" is abstract-level. |

## Claims corrected or qualified

- Summary: "it restores the state before that action". The abstract says "the original state" (A2). That it is the pre-action state is a plausible inference, not a quote.
- "RL trains the selector" is an inference from "reinforcement-learning framework" plus "offline selector-training costs". The analyst marked it as an inference.
- The source list omits several local files, all abstract-level or summary-only, so they add nothing: cgdeep, lodestar, tmokmss, zemyblue, innerca, angelababy_enriched. lightrain_iclr_idea_factory.py is unrelated (see above).

## Strongest threat to the temporal-agency project

COUNTERMEM is direct prior art for this loop:
1. go back to an earlier decision point;
2. fork the state instead of overwriting it, preserving it "for comparison" (A1, A2);
3. try alternatives;
4. verify them with executable tests (A2);
5. persist the factual and counterfactual pair as reusable memory (A3).

The abstract reports +12.6 pp over ReAct and Reflexion on all 12 settings, and A6 says verification and persistence each matter.

In smoke_v1, remediation is test-checkable. A baseline with a COUNTERMEM-style verifier loop could therefore plausibly do the "reopen and remediate" half without any temporal navigation:
- agent-visible tests fail after the later event;
- the agent then retries alternatives on a copy and keeps the verified fix.

That would leave the project's distinct claim resting mainly on the epistemic-cutoff statements (true then, known then, known now) and on the prospective, prevented-future, and as-of pillars, none of which COUNTERMEM touches.
