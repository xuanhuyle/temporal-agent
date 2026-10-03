# MAGE (arXiv:2606.06090): adversarial verification notes

Verifier date: 2026-10-03.

## Access attempted during verification
- WebSearch: refused, because the session budget is exhausted ("this session has used its web search budget (200 of 200 WebSearch calls)"). I therefore could NOT re-obtain any arXiv HTML extract myself.
- curl probes all returned 000 (blocked): web.archive.org (arxiv html snapshot), api.openalex.org, r.jina.ai, scholar.archive.org, api.crossref.org, alphaxiv.org, paperswithcode.com, duckduckgo.com.
- git ls-remote probes, none of which exist: microsoft/MAGE-Agent, microsoft/mage-agent, microsoft/MAGE_memory, microsoft/AgentMemory, microsoft/ExecutionStateMemory, chenyaoqi/MAGE, yaoqichen/MAGE, Yaoqi-Chen/MAGE, microsoft/MemoryArena-MAGE, qi-chen/MAGE. No code found, which confirms the analyst.
- Awesome-list mirror at scratchpad/lit/verify/awesome/IAAR-Shanghai_Awesome-AI-Memory.md:7348-7363. It links only the arXiv abstract (no code badge). Its Chinese summary: "提出 MAGE 层次执行状态树，通过 grow、compress、maintain、revise 维护任务状态" and "通过保留有效路径、隔离错误分支提升任务成功率并降低 token 消耗" ("improves task success and reduces tokens by preserving valid paths and isolating erroneous branches").
- arXiv daily digest mirror at scratchpad/lit/repos/pf/daily/5-Jun-2026/AI/README.md:300-306. It gives the arXiv-listed authors, with "Zhirui Wang" as the 10th author and listing day 5-Jun-2026. MSR page (msr_pub.html:130) says `citation_author content="Zilong Wang"`. Two sources now give the arXiv spelling as Zhirui and the MSR page alone says Zilong. Which spelling is correct remains unresolved.

Primary verbatim text available to me: the MSR abstract (scratchpad/lit/mage_msr_abstract.txt), which is identical to the arXiv abstract in the digest mirror. Everything else rests on the analyst's recorded WebSearch extracts (notes/mage.md §3-§7). I cannot re-verify them, so I judge whether the ratings FOLLOW from them plus the abstract.

Key verbatim abstract sentences:
> "The agent derives its state from the active root-to-current path, combining subgoal summaries, recent traces, and hints from prior branches. Four coupled operations maintain the tree: Grow records new traces, Compress summarizes completed subgoals, Maintain validates summaries, and Revise restores a target boundary and resumes on a new branch. This design bounds context growth while preserving state integrity and isolating flawed segments from the active path."
> "Experiments on MemoryArena show that MAGE improves the average task success rate by 7.8–20.4 pp over baselines, while reducing token consumption by 55.1%."

## Changed ratings

### replay: no -> partial
Definition: "re-run execution from a historical point".
Evidence:
- Abstract (verbatim): "Revise restores a target boundary and resumes on a new branch".
- Analyst extract (notes §4): "If an error is detected, Revise restores the execution state to the target boundary and resumes execution as a new branch."
This IS re-running execution from a historical point for the agent's execution state. It matches LangGraph-style "replay from checkpoint", where execution resumes from a checkpoint and later steps are re-generated. The analyst's "no" applied a stricter, deterministic-trace-replay reading that the definition does not require.
Partial, not yes, because:
- The environment is not described as restored.
- Recorded steps are not reproduced deterministically.
- It runs only on error recovery and only at compression boundaries.

### fork_from_historical_state: partial -> yes (agent-state scope)
Definition: "start a new branch from an earlier state while preserving the original".
- Abstract (verbatim): "Revise restores a target boundary and resumes on a new branch"; "isolating flawed segments from the active path".
- Analyst extracts (notes §4): "Subsequent actions branch from this restored point as sibling paths, achieving error isolation without discarding valid progress on other branches"; "quarantines flawed segments into inactive branches".
- Independent awesome-list summary: "隔离错误分支" ("isolating erroneous branches").
This is MAGE's defining operation and meets both parts of the definition: a new branch from an earlier state, and the original kept as an inactive sibling.
The analyst's caveats limit scope; they do not show the capability is missing:
- The external environment is not forked.
- It forks only at compression boundaries.
- It is reactive.
- Only one branch is active at a time.
Comparable checkpoint systems such as LangGraph also fork agent state only, not the world. Rating it partial understates prior art.

### uncertainty_representation: no -> partial (weak)
Definition explicitly includes "unresolved items in state".
Analyst extracts (notes §4):
- Maintain detects "missing information, unsatisfied task requirements, or broken dependencies".
- "records the diagnostic feedback in the note field".
- On Revise, "the execution hint is updated with diagnostic feedback".
So explicit, state-resident records of unresolved problems (an unmet requirement, missing information) exist. They sit in the top-node `note` field and in H, which the agent sees.
Limits:
- There are no confidence or probability values.
- Notes appear only after a validation failure.
- Their exact format is unknown, and that they contain unresolved-item content is inferred from what Maintain detects.
So the rating is weak partial, not yes.

## Unchanged ratings (re-checked)
| Capability | Rating | Re-check |
|---|---|---|
| immutable_historical_observations | partial | Raw nodes plus kept inactive branches, but there is no immutability claim. The Compress extract says it is "replacing a completed bottom-layer segment with a top-layer summary node, freeing space". That is ambiguous: "freeing space" most likely means context, given that cover_nodes point to the bottom nodes, but it could mean deletion. Partial at most. |
| historical_world_state | no | Only the agent's observation trace exists. No environment snapshot or as-of reconstruction is described anywhere (abstract or extracts). |
| historical_epistemic_state | partial | Generous but defensible. The C/R pair at a boundary is the agent's memory as of that boundary. However, it is materialized only to resume, and H then injects later-branch diagnostics, so there is no cutoff in the agent-facing result. |
| historical_policy_objective_state | no | There is a single fixed task instruction and no recorded policy or goal changes. |
| execution_checkpoints | partial | For an LLM agent, context is most of the runtime state, so restoring C/R is close to a checkpoint restore. It is derived from the tree path rather than snapshotted, and tool or environment state is absent. Partial holds; "yes" is arguable. |
| counterfactual_action_branches | no | Branches are committed real executions after an error. Nothing is explored without commitment. |
| branch_provenance | partial | Parent and child pointers give the divergence point. The note gives the reason only for Maintain-triggered branches. |
| explicit_current_belief_state | partial | C is validated "trusted" summaries, but it holds task progress, not typed beliefs. |
| future_state_rollout, multiple_prospective_branches, probability_over_futures, intervention_aware_forecasting, prevented_futures_preserved, predicted_vs_realized | no | No forecasting or simulation component appears in the abstract or any recorded extract. Inactive branches are past, realized failures. |
| backward_requirements | no | Maintain checks a completed subgoal against the task instruction ("unsatisfied task requirements"). That is retrospective conformance to the goal, not derivation of present obligations from a future state. Borderline but no. |
| cross_time_state_querying | no | Step ids are exposed on C only as Revise targets, which are mutations. No as-of query or diff exists. |
| unified_temporal_abstraction | partial | One tree holds past steps, the current path and abandoned realized alternatives. It has no prospective or simulated states. |

## Claim corrections
1. "55.1% fewer tokens than long-context": the abstract says only "reducing token consumption by 55.1%" with no comparator, and no recorded extract ties 55.1% to long-context. The comparator is unverified. The extract that does mention long-context gives per-domain reductions of 32.9-71.4%.
2. Author discrepancy: no longer just one search extract against MSR. An independent arXiv-listing mirror (the digest README) also reads "Zhirui Wang". The MSR page reads "Zilong Wang".
3. All mechanism-level claims rest on search extracts that neither the analyst nor I could check against the page itself. I could not re-run them, because the budget is exhausted. The analysis already says this; it is restated here because the confidence ceiling is the extracts, not the paper.
