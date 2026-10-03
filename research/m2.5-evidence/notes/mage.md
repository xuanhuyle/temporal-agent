# MAGE (Memory as Agent-Guided Exploration): primary-source notes

Paper: "Beyond Semantic Organization: Memory as Execution State Management for Long-Horizon Agents", arXiv:2606.06090 (v1), Microsoft Research.
Analyst date: 2026-10-03.

## 0. How sources were obtained (and how much to trust each)

| # | Source | How obtained | Trust level |
|---|--------|--------------|-------------|
| S1 | https://www.microsoft.com/en-us/research/publication/beyond-semantic-organization-memory-as-execution-state-management-for-long-horizon-agents/ | `curl` (HTTP 200), HTML parsed locally. Saved: `scratchpad/lit/msr_pub.html`, abstract text in `scratchpad/lit/mage_msr_abstract.txt` | **Verbatim primary text** (abstract + metadata only) |
| S2 | https://arxiv.org/html/2606.06090 and https://arxiv.org/html/2606.06090v1 (also /abs/, /pdf/) | arxiv.org is blocked for curl/WebFetch. Content obtained **only through WebSearch summaries** (server-side) that cite these URLs. | **Search extract**: a summarizer model's restatement of the page. Often near-verbatim, but not guaranteed. Several extracts mixed in material from *other* papers (flagged below). |
| S3 | https://github.com/microsoft/MAGE (commit 76bec2bb3818863f470de7e867c2dc7f1d0bfd83, 2026-08-10) | `git clone --depth 1` into `scratchpad/lit/repos/microsoft_MAGE` | Verbatim, but **UNRELATED**: it is the "Mage" multimodal model family (Mage-VL, Mage-Flow). Not the memory paper. |
| S4 | https://arxiv.org/html/2602.16313v1 (MemoryArena benchmark paper) | WebSearch extract | Search extract; used only to describe the benchmark domains. |

No code repository for the MAGE memory system was found:
- S1 (MSR page) links only to `https://arxiv.org/abs/2606.06090` (grep of `href` for github/arxiv/pdf/uploads returned only that link).
- Multiple WebSearch queries ("MAGE Memory as Agent-Guided Exploration github code", "... MemoryArena code release") returned no repository; summarizer explicitly said none found.
- `git ls-remote` probes: `microsoft/MAGE` exists but is unrelated (S3); `microsoft/MAGE-Memory`, `microsoft/mage-memory`, `microsoft/MemoryArena`, `YaoqiChen/MAGE` do not exist / not public.
- Therefore **nothing below is verified in code**. Everything about mechanism is "paper claims" (via S1 verbatim abstract or S2 search extracts).

The session's WebSearch budget (200 calls, shared) was exhausted before all follow-ups could be asked; remaining gaps are listed in section 9.

## 1. Metadata (S1, verbatim from HTML meta tags)

```
citation_title" content="Beyond Semantic Organization: Memory as Execution State Management for Long-Horizon Agents"
citation_author: Yaoqi Chen, Haibin Lai, Yuru Feng, Chuyu Han, Qianxi Zhang, Baotong Lu, Menghao Li, Xinjiang Wang, Zilong Wang, Shusen Xu, Zengzhong Li, Zewen Jin, Hao Wu, Cheng Li, Qi Chen
citation_publication_date" content="2026/06/04"
datePublished":"2026-06-08T22:07:21+00:00"
```
Discrepancy: a WebSearch extract of the arXiv listing gave the 10th author as "Zhirui Wang"; MSR page says "Zilong Wang". Unresolved.
MSR page lists venue as "arXiv", research area "Artificial intelligence".

## 2. Abstract (S1, VERBATIM)

> LLM-based agents increasingly tackle long-horizon tasks with interdependent decisions, where each action reshapes future constraints and intermediate errors can cascade. Existing RAG and agent memory systems organize histories by semantic similarity, retrieving content-relevant entries at decision time. We argue that this design mismatches execution-state dependencies: it fragments decision trajectories and mixes valid and erroneous traces, hindering coherent state reconstruction and error isolation. We propose MAGE (Memory as Agent-Guided Exploration), an active execution-state manager that stores interactions in a hierarchical state tree. The agent derives its state from the active root-to-current path, combining subgoal summaries, recent traces, and hints from prior branches. Four coupled operations maintain the tree: Grow records new traces, Compress summarizes completed subgoals, Maintain validates summaries, and Revise restores a target boundary and resumes on a new branch. This design bounds context growth while preserving state integrity and isolating flawed segments from the active path. Experiments on MemoryArena show that MAGE improves the average task success rate by 7.8–20.4 pp over baselines, while reducing token consumption by 55.1%.

## 3. State abstraction: the two-layer hierarchical state tree (S2 search extracts)

Extract (cites arxiv.org/html/2606.06090v1):
> "MAGE organizes the agent's history as a persistent two-layer hierarchical state tree, where the bottom layer records the step-by-step action-observation trace, while the top layer stores summaries generated at subgoal or decision boundaries. This boundary-aware compression reduces context without interrupting an active trace or breaking execution-state integrity."

Extract (cites arxiv.org/html/2606.06090):
> "Mage represents the agent's execution history as a two-layer hierarchical state tree, where the bottom layer records raw action-observation nodes in execution order, preserving fine-grained state dependencies, and the top layer stores summary nodes that cover completed bottom-layer segments, progressively chunking long local traces into compact subgoal-level states."

Node definition extract (cites arxiv.org/html/2606.06090):
> "The node structure includes fields for: id (unique identifier), content (action-observation pair for bottom layer or compressed summary for top layer), parent (pointer to parent node), children (set of child node pointers), cover_nodes (ordered bottom-node pointers covered by this summary for top layer only), and note (diagnostic feedback for top layer only)."

Agent-facing execution state S = (C, R, H) (cites arxiv.org/html/2606.06090):
> "the agent's execution state S is composed of three parts: (1) compressed state C, consisting of top-layer summaries along the root-to-p_t path, each annotated by its step id, allowing the agent to revise failed subgoals from the corresponding boundary upon detecting errors; (2) raw state R, the bottom-layer nodes accumulated since the last compression that provide fine-grained recent context; and (3) execution hint H."
> "The agent-facing execution state consists of compressed summaries, recent raw trace, and execution hints from previously explored branches and diagnostic notes."
> "The current execution state is read from the active tree path instead of being assembled from semantically similar entries, combining compressed state, recent raw state, and execution hints from sibling branches."

Notes:
- `p_t` = pointer to the current node at step t (notation appears in the extract "root-to-p_t path").
- No timestamps other than step ids are mentioned. No belief/assumption/uncertainty fields are mentioned in the node schema.
- Bottom-layer nodes appear to be **retained** after Compress: top-layer nodes hold `cover_nodes` = "ordered bottom-node pointers covered by this summary", and Maintain "examines the compressed subtree" (see §4). This is my inference from the schema; no extract says "bottom nodes are never deleted".

## 4. Operations (S2 search extracts)

### Grow
> "When the agent executes an action and receives an observation, Mage automatically invokes Grow to update the bottom layer."
Trigger: automatic, every action-observation step. Decider: MAGE (system), not the agent.

### Compress
> "Compress bounds context growth by replacing a completed bottom-layer segment with a top-layer summary node, freeing space while preserving the decision boundary needed for later recovery. It is invoked when the agent marks a subgoal complete with summary content provided as an argument, or by Mage as a fallback when the raw state R exceeds a length threshold."
Trigger: (a) the agent (LLM) marks a subgoal complete and supplies the summary text as an argument; (b) fallback by MAGE when R exceeds a length threshold. The threshold value was not obtained.

### Maintain
> "Maintain validates the just-completed subgoal before the new summary becomes a trusted part of memory. This check protects the execution state from incorrect memory writes, allowing Mage to detect missing information, unsatisfied task requirements, or broken dependencies before such errors accumulate."
> "Immediately after compression, Maintain validates ... An LLM examines the compressed subtree together with the summary content and task instruction."
> "If validation fails, Maintain records the diagnostic feedback in the note field and returns a failure signal with the revision target."
> (another extract) "When Maintain fails, it records the diagnostic feedback in the note field and returns a failure signal with the revision target step ID."
Trigger: immediately after each Compress. Decider: an auxiliary LLM call (which model is not established). Output: pass, or fail + note + revision target step id.

### Revise
> "Revise is triggered by a Maintain failure or invoked proactively by the agent upon detecting an error, restoring the active path to the target step, which is either returned by Maintain or selected from exposed compressed-state boundaries. Subsequent actions branch from this restored point as sibling paths, achieving error isolation without discarding valid progress on other branches."
> "Revise restores the active path to the target step ... The compressed state and raw state are reverted to these positions, while the execution hint is updated with diagnostic feedback and alternatives from the restored nodes."
> "If an error is detected, Revise restores the execution state to the target boundary and resumes execution as a new branch. The erroneous segment is therefore excluded from the active path, while the valid progress before the target boundary is preserved, isolating the error from subsequent decisions."
> "The execution hint (H) is updated with diagnostic feedback and alternatives from restored nodes, providing extra guidance that helps avoid repeating the same error."
> (Figure-2 related extract) "Mage maintains a coherent current state, reuses historical exploration to avoid recurring errors, and quarantines flawed segments into inactive branches."
> (contributions extract) "a closed-loop state-management cycle that isolates errors into separate branches and keeps the active execution state free from erroneous traces."

Trigger: Maintain failure (target = step id returned by Maintain) OR agent-initiated on detecting an error (target = one of the step-id-annotated boundaries exposed in C).
Effect: C and R are reverted to the target; H receives diagnostic feedback + "alternatives from the restored nodes"; new actions become a sibling branch; the old segment becomes an inactive branch (kept, "quarantined").

### Cost claim
> "Unlike traditional memory systems that require continuous, token-heavy auxiliary LLM calls to extract entities or generate queries, Mage maintains the tree structure deterministically and invokes auxiliary LLMs only during Compress and Maintain at natural subgoal boundaries."

## 5. Branching semantics: kept? queryable? environment restored?

- Kept: yes, per "quarantines flawed segments into inactive branches" and "sibling paths ... without discarding valid progress on other branches".
- Queryable: only indirectly. Inactive branches influence the agent through H ("execution hints from previously explored branches and diagnostic notes"; "hints from sibling branches"). No extract describes an agent-facing tool to browse/search/diff inactive branches. The only agent-addressable past points are "exposed compressed-state boundaries" (step ids on C) used as Revise targets.
- "Hints from prior branches" contain: diagnostic feedback (Maintain's `note`) and "alternatives from the restored nodes". Exact format not obtained.
- **Environment restoration: not described.** Every extract describes Revise as reverting C and R (agent-facing memory) and updating H. No extract mentions snapshotting, resetting or re-executing the external environment. One WebSearch answer claimed "Read-only/deterministic tools are re-executed from the environment snapshot ... consequential tools are shadow-executed during replay with call-ID deduplication" — this was **mixed in from a different paper** in the same result set (likely "Forgetting Without Restarting" / "Revisable by Design" / AgentRewind); it does not match any MAGE terminology and is NOT attributed to MAGE. Another answer stated Revise operates "on the agent's internal memory context ... rather than resetting external environment states" but explicitly as the summarizer's inference. Conclusion: as described, Revise is a memory/context rewind; whether MemoryArena environments are reset is **unclear**.

## 6. Evaluation (S2 search extracts)

Benchmark: MemoryArena (arXiv:2602.16313; S4 extract):
> "MemoryArena is instantiated across four domains: (1) bundled web shopping, (2) preference-constrained group travel planning, (3) progressive information searching, and (4) sequential formal reasoning over math and physical problems."
> "Each task spans long horizons (with an average of 57 action steps) and produces extended reasoning traces with more than 40k tokens."
MAGE paper describes it as (extract): "an interdependent long-horizon benchmark where agents operate in a continuous Memory-Agent-Environment loop for up to hundreds of steps."

Setup (extract, cites arxiv.org/html/2606.06090v1):
> "All methods use Qwen3.6-27B (Qwen, 2026a) as the backbone LLM with ReAct (Yao et al., 2023) for agent exploration."

Baselines (extract, cites arxiv.org/html/2606.06090):
> "The RAG baselines include HippoRAG2, which builds a knowledge graph and applies Personalized PageRank for multi-hop retrieval, and MemoRAG, which uses a lightweight memory model to generate retrieval clues. The agent memory baselines include Mem0, which extracts and consolidates facts into graph-based memory, and MemoryOS, which maintains hierarchical storage layers with dynamic cross-level updating."
Plus Long Context ("retains full interaction history"). So: Long Context, HippoRAG2, MemoRAG, Mem0, MemoryOS (completeness of this list not verified).
Metrics: "Table 3 presents main results on MemoryArena, with SR (Task Success Rate %) and PS (Task Progress Score %) ... along with average token consumption per task."

Headline numbers (extracts):
> "MAGE improves the average task success rate by 7.8–20.4 pp over baselines, while reducing token consumption by 55.1%" (S1 verbatim as well).
> "Mage outperforms the long-context approach by average margins of 7.8 pp in SR and 8.7 pp in PS."
> "On tasks with complex state dependencies like Web Shopping, RAG and memory-based baselines underperform the long-context approach, with success rate drops of 12.7–22.0 pp on Web Shopping and 6.3–18.1 pp on Web Search."
> "Systems like HippoRAG2 and Mem0 end up consuming 12.6–14.7% more tokens than the long-context approach on Web Shopping ... MAGE consistently reduces token usage by 32.9-71.4% across all domains."
> "HippoRAG2 achieves good results on Travel Planning because local constraints are anchored by stable entities ... its PS advantage does not translate into higher SR than Mage."
> "In Formal Reasoning, baselines perform comparably or slightly better than the long-context approach because mathematical dependencies are explicit and sparse, enabling precise lemma retrieval."
Other backbones (extract): "MAGE was evaluated on Qwen3.6-35B-A3B and Gemma4-31B on the Bundled Web Shopping domain, with MAGE consistently improving SR over baselines by gains of 8.0–18.7 pp on Qwen3.6-35B-A3B and 6.7–22.7 pp on Gemma4-31B." and "MAGE reduces token consumption relative to the long-context approach by 33.2% on Qwen3.6-35B-A3B."

LOW-CONFIDENCE numbers (one extract; may be mixed from another MemoryArena paper such as "MemoryLake on MemoryArena" which appeared in the same result set):
> "On the Web Shopping task, Mage (Full) achieves a success rate (SR) of 0.3933 (39.33%) ... Long Context achieves 0.2800 (28.00%), MemoRAG achieves 0.1342 (13.42%), and MemoryOS achieves 0.1200 (12.00%)."
(These are internally consistent with the 12.7–22.0 pp drop range, but I could not confirm they are from Table 3 of 2606.06090.)

Case study (extract): baseline failure on a shopping task where "HippoRAG retrieve[s] only Product 2 information while MemoryOS retrieves Product 4 exploration traces but not the final purchased item, both missing that Product 4 contains gold and choosing an incompatible unicorn-themed option. In contrast, MAGE preserves the execution state and selects the compatible wedding option."

## 7. Ablations (S2 extract, cites arxiv.org/html/2606.06090v1)

> "Removing Compress consistently hurts task completion, reducing SR by 7.3 pp on Web Shopping and 6.7 pp on Travel Planning, while increasing token consumption to 2.4× and 1.8× that of the full model."
> "Removing Maintain reduces token usage by avoiding boundary-level verification, but SR drops by 5.2–6.7 pp on two domains."
> "Removing Revise lowers SR by 4.0-5.2 pp on two domains, showing that error detection alone is insufficient; after a failed boundary is identified, the agent must restore the corresponding state, branch away from the flawed segment, and continue from the preserved valid prefix."
> "these weakened variants remain competitive with or superior to the baselines, suggesting that organizing memory around the execution path mitigates state fragmentation"
Ablations reported on two domains only (Web Shopping, Travel Planning per the Compress sentence). No ablation of H (hints) was found.

## 8. Limitations

No extract surfaced a "Limitations" section or explicit limitation statements. One WebSearch answer listed "reliance on LLM verifier accuracy" as a limitation but this was the summarizer's own inference, not quoted text. Treat stated limitations as **not obtained**.

Analyst-observed (my inferences, not paper claims):
- Scope appears to be a single long-horizon task episode (benchmark is per-task; no extract describes cross-task persistence).
- Revise is a memory rewind; no environment rollback described, so any external side effects of the abandoned branch presumably persist.
- H deliberately injects post-hoc (hindsight) information into the restored state: the opposite of a strict epistemic cutoff.
- Rewind targets are limited to compression boundaries (step-id-annotated summaries).

## 9. Could not verify

1. Any code: no public repository found; `microsoft/MAGE` is an unrelated multimodal model repo.
2. Full Table 3 numbers per domain (only ranges and one low-confidence Web Shopping row).
3. Length threshold for fallback Compress; number of revisions allowed; which LLM performs Maintain/Compress (same backbone or not); prompts.
4. Whether Revise (or MemoryArena) resets/restores the external environment. Not described in any extract.
5. Exact format/content of the execution hint H beyond "diagnostic feedback and alternatives from the restored nodes" / "hints from sibling branches".
6. Whether the agent can inspect inactive branches directly (no tool described).
7. Whether bottom-layer nodes are physically retained after Compress (inferred from `cover_nodes`, not stated).
8. Stated limitations section.
9. Author name discrepancy (Zilong Wang on MSR page vs Zhirui Wang in a search extract).
10. Whether the tree persists across tasks (only "persistent" within the task is stated).

## 10. Capability ratings summary (see structured output for evidence)

| # | Capability | Rating |
|---|---|---|
| 1 | immutable_historical_observations | partial |
| 2 | historical_world_state | no |
| 3 | historical_epistemic_state | partial |
| 4 | historical_policy_objective_state | no |
| 5 | execution_checkpoints | partial |
| 6 | replay | no |
| 7 | fork_from_historical_state | partial |
| 8 | counterfactual_action_branches | no |
| 9 | branch_provenance | partial |
| 10 | explicit_current_belief_state | partial |
| 11 | uncertainty_representation | no |
| 12 | future_state_rollout | no |
| 13 | multiple_prospective_branches | no |
| 14 | probability_over_futures | no |
| 15 | backward_requirements | no |
| 16 | intervention_aware_forecasting | no |
| 17 | prevented_futures_preserved | no |
| 18 | predicted_vs_realized | no |
| 19 | cross_time_state_querying | no |
| 20 | unified_temporal_abstraction | partial |
