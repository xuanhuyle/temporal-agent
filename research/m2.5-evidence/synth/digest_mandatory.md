# Mandatory prior work: verified digests

Ratings are the VERIFIED ratings (after an adversarial verifier). Capability keys: 1=immutable_historical_observations, 2=historical_world_state, 3=historical_epistemic_state, 4=historical_policy_objective_state, 5=execution_checkpoints, 6=replay, 7=fork_from_historical_state, 8=counterfactual_action_branches, 9=branch_provenance, 10=explicit_current_belief_state, 11=uncertainty_representation, 12=future_state_rollout, 13=multiple_prospective_branches, 14=probability_over_futures, 15=backward_requirements, 16=intervention_aware_forecasting, 17=prevented_futures_preserved, 18=predicted_vs_realized, 19=cross_time_state_querying, 20=unified_temporal_abstraction

## mage: Beyond Semantic Organization: Memory as Execution State Management for Long-Horizon Agents (arXiv:2606.06090v1)
Yaoqi Chen, Haibin Lai, Yuru Feng, Chuyu Han, Qianxi Zhang, Baotong Lu, Menghao Li, Xinjiang Wang, Zilong Wang (a search extract of arXiv gives "Zhirui Wang"; unresolved), Shusen Xu, Zengzhong Li, Zewen Jin, Hao Wu, Cheng Li, Qi Chen. Microsoft Research publication page; citation_publication_date 2026/06/04; page datePublished 2026-06-08. Venue: arXiv preprint.

Sources: https://www.microsoft.com/en-us/research/publication/beyond-semantic-organization-memory-as-execution-state-management-for-long-horizon-agents/ (curl (HTTP 200), HTML parsed locally; verbatim abstract and citation_* meta tags. Saved at scratchpad/lit/msr_pub.html a); https://arxiv.org/html/2606.06090 (arxiv.org is blocked, so this came only from WebSearch summaries (allowed_domains arxiv.org) that cite this URL. They ar); https://arxiv.org/html/2606.06090v1 (WebSearch summaries citing the v1 HTML: Revise semantics, the Figure-2 description ('quarantines flawed segments into in); https://arxiv.org/abs/2606.06090 (WebSearch result listing (authors, title). Not fetched directly (blocked).); https://arxiv.org/html/2602.16313v1 (WebSearch summary of the MemoryArena benchmark paper: the four domains, average of 57 action steps and more than 40k tok); https://github.com/microsoft/MAGE (git clone --depth 1 (commit 76bec2bb, 2026-08-10) into scratchpad/lit/repos/microsoft_MAGE. UNRELATED: it is the Mage-VL)

SUMMARY: MAGE is a within-task memory manager for long-horizon LLM agents. It replaces similarity-based retrieval (RAG, Mem0, MemoryOS) with an execution-state tree. The bottom layer stores raw action-observation nodes. The top layer stores subgoal summary nodes that point to the bottom nodes they cover (cover_nodes) and carry a diagnostic 'note'. The agent's prompt state is S=(C,R,H): C is the summaries along the active root-to-current path, each tagged with a step id. R is the raw nodes since the last compression. H is hints (diagnostic notes and 'alternatives') from previously explored sibling branches. Grow appends every step automatically. Compress runs when the agent marks a subgoal complete (supplying the summary text), or as a fallback when R exceeds a length threshold. Maintain is an auxiliary LLM check of the new summary against its subtree and the task instruction; on failure it writes a note and returns a revision-target step id. Revise is triggered by a Maintain failure or by the agent itself. It reverts C and R to the target boundary, adds feedback and alternatives to H, and continues on a new sibling branch; the flawed segment is kept as an inactive branch. On MemoryArena with Qwen3.6-27B and ReAct, the paper reports +7.8 to +20.4 pp average success rate over baselines and 55.1% fewer tokens than long-context. No code was found, so all mechanism claims come from the paper, read through the verbatim MSR abstract and WebSearch extracts of the arXiv HTML. In temporal terms, MAGE is a rewind-and-branch mechanism for the agent's own memory, used for error recovery. It has no world-state reconstruction, no epistemic cutoff (H deliberately injects hindsight), no queries over time and no prospective machinery.

CORE STATE: A persistent, per-task, two-layer hierarchical state tree. Node fields (search extract of arxiv.org/html/2606.06090): id; content (an action-observation pair at the bottom, a compressed summary at the top); parent; children; cover_nodes (top only: ordered pointers to the bottom nodes the summary covers); note (top only: diagnostic feedback). p_t points to the current node. The agent-facing state S=(C,R,H) is derived from the active root-to-p_t path. C = top-layer summaries on the path, each annotated with its step id. R = bottom nodes since the last compression. H = execution hints from previously explored or sibling branches and diagnostic notes. The only time index is the step id. There are no timestamps, belief fields or confidence fields.

BRANCHING/REVISIT: Branches arise only through Revise, i.e. after an error is detected. The abandoned segment stays in the tree as an inactive sibling branch ('quarantines flawed segments into inactive branches'; 'without discarding valid progress on other branches'). Only one branch is active at a time. Abandoned branches reach the agent only indirectly, through H: diagnostic notes plus 'alternatives from the restored nodes' ('hints from sibling branches'). No tool to browse, search or diff inactive branches is described. Revisit targets are limited to the summary boundaries exposed in C, by step id; arbitrary raw steps are not described as targets. Restoration covers C and R, the agent-facing memory. Restoring, snapshotting or re-executing the external environment is never mentioned, so environment restoration on Revise is UNCLEAR and, as described, absent. One search answer that described shadow-executed replay with environment snapshots was traced to other papers in the same result set and is not attributed to MAGE.

PRESERVED VS LOST: Preserved, per the paper's description:
- Raw action-observation nodes for the episode. Bottom nodes are referenced by cover_nodes after compression, so retention is inferred, not stated.
- Summary nodes with their Maintain notes.
- Inactive (abandoned) branches.
- Step ids as the only time index.

Lost or never recorded:
- External environment state snapshots.
- Timestamps.
- The exact prompt or context seen at each step, as distinct from the reconstructable path.
- Beliefs, confidence and assumptions.
- Goal or policy changes.
- Anything across task episodes. Scope appears to be per task; cross-task persistence is not described.

What the agent sees (S=(C,R,H)):
- Older raw detail behind summaries; the agent sees only summaries for completed subgoals.
- Abandoned branches, except as distilled hints in H.

BELIEF STATE: MAGE has no explicit belief or assumption state. The nearest thing is C: Maintain-validated free-text subgoal summaries forming the trusted current execution state, with Maintain's diagnostic notes held in H. There is no representation of what the agent believed at time t as distinct from what it knows now. Revise restores C and R to an earlier boundary but then injects diagnostic feedback and alternatives from the later, failed branch into H. That is intentional hindsight injection, the opposite of an epistemic cutoff. Nothing marks which knowledge was available at which step.

FUTURE: None. MAGE does not simulate, forecast or roll out future states, keep alternative futures, or assign probabilities. Its only forward-looking element is H: lessons from failed branches meant to 'avoid repeating the same error'. That is retrospective error memory, not prediction. Maintain checks a completed subgoal against the task instruction, a retrospective validity check; it does not derive future requirements.

EVALUATION: Benchmark: MemoryArena (arXiv:2602.16313), four domains:
- Bundled Web Shopping
- Group Travel Planning
- Progressive Web Search
- Sequential Formal Reasoning

MemoryArena tasks average 57 action steps and more than 40k tokens.

Setup: 'All methods use Qwen3.6-27B ... as the backbone LLM with ReAct.'

Baselines (search extract): Long Context (full history), HippoRAG2 and MemoRAG (RAG), Mem0 and MemoryOS (agent memory). Completeness of this list is unverified.

Metrics: SR (task success rate %), PS (task progress score %), average tokens per task (Table 3).

Headline results:
- +7.8 to +20.4 pp average SR over baselines.
- −55.1% tokens versus long-context; per domain, token use falls by 32.9–71.4%.
- Versus long-context, average margins of +7.8 pp SR and +8.7 pp PS.

Context from the baselines:
- On Web Shopping, RAG and memory baselines fall 12.7–22.0 pp below long-context; on Web Search, 6.3–18.1 pp below.
- HippoRAG2 and Mem0 use 12.6–14.7% more tokens than long-context on Web Shopping.
- HippoRAG2 is strong on Travel Planning PS but not on SR.
- In Formal Reasoning, baselines are comparable to or slightly better than long-context.

Other backbones, Web Shopping only:
- Qwen3.6-35B-A3B: SR gains of 8.0–18.7 pp; −33.2% tokens versus long-context.
- Gemma4-31B: SR gains of 6.7–22.7 pp.

One low-confidence Web Shopping row, possibly mixed in from another MemoryArena paper: MAGE 39.33, Long Context 28.00, MemoRAG 13.42, MemoryOS 12.00 SR.

Ablations, on two domains:
- −Compress: SR −7.3 pp (Web Shopping) and −6.7 pp (Travel Planning); tokens rise to 2.4× and 1.8×.
- −Maintain: SR −5.2 to −6.7 pp, with fewer tokens.
- −Revise: SR −4.0 to −5.2 pp.
- The ablated variants remain competitive with or better than the baselines.
- No ablation of H was found.

Case study: in a compatibility-constrained shopping task, HippoRAG and MemoryOS miss that an earlier purchased product contains gold; MAGE chooses the compatible option.

DOES NOT COVER: Not covered:
- **No strict epistemic cutoff.** H deliberately carries hindsight into restored states, and nothing separates known-then from known-now.
- **No reconstruction of external world state at t.** Environment rollback is not described.
- **No record of identity, objective or policy changes.**
- **No future-state simulation or forecasting.** Consequently there are also no alternative futures, no probabilities, no backward requirements from desired or feared futures, no intervention-aware forecasts, no preserved prevented futures and no predicted-vs-realized comparison.
- **No queries over time** (state_at, diff, as-of).
- **No counterfactual branches without commitment.** Branches are reactive error recovery, one active at a time, at compression boundaries only.
- **Within a single task episode only**, as far as described.
- **Historical decisions are the agent's own subgoal summaries**, not world-authored artifacts.

RELATION TO smoke_v1: smoke_v1 tests whether an agent notices that a later event changes the significance of an earlier world-authored decision (an ADR or ticket), reopens it with evidence, separates true-then / known-then / known-now-about-then, and fixes the code in the present.

MAGE overlaps only in spirit. Its Revise reopens an earlier boundary when something later shows it was wrong. The differences are:
1. **Trigger and target.** MAGE revises the agent's own subgoal summaries, prompted by an LLM validator or the agent itself. It has no notion of external, world-authored decision artifacts or of their significance changing.
2. **Direction of repair.** Revise rewinds the active memory to the past boundary and continues from there. smoke_v1 requires acting from the present, keeping the later evidence and fixing the code forward. Rewinding memory without rolling back the world (environment rollback is not described) could even drop the triggering later event from the active path; it would survive only as a hint in H.
3. **Hindsight.** H injects later diagnostics into the restored state. MAGE therefore cannot produce the true-then / known-then / known-now separation that smoke_v1 scores.

Implications:
- **Strong baseline.** MAGE-style path-structured memory with summaries and a validator is a credible, stronger alternative or extra arm next to the current baseline (event log, checkpoints, hybrid RAG, rolling summary). It is evidence that path- or tree-structured memory beats similarity retrieval on interdependent tasks, which the project should not claim as novel.
- **Not directly portable.** No code is available, and its per-task, error-recovery design does not map directly onto smoke_v1's cross-event, world-artifact reopening.

The paper does not weaken the project's distinct claims. It provides none of epistemic cutoff, world-state as-of, prospective or forecast machinery, or questioning world-authored history.

VERIFIER STRONGEST THREAT: MAGE already implements, and tests empirically, the core move of smoke_v1 and the project's 'never overwrite time, fork it' slogan for the agent's own state. A later check (Maintain, or the agent itself) finds that an earlier, already-committed decision boundary was wrong. The agent reopens it by step id, forks a new branch from the preserved valid prefix, and keeps the flawed branch as an inactive sibling while carrying its diagnosis forward. On interdependent long-horizon tasks, this path-structured, rewindable memory beats similarity retrieval (HippoRAG2, MemoRAG, Mem0, MemoryOS) and long-context by 7.8 to 20.4 pp SR. Revise alone is credited with 4.0 to 5.2 pp in ablation.

Two consequences follow.
1. The project's benchmark baseline (event log, checkpoints, hybrid RAG, rolling summary) has no MAGE-like path-structured arm. Any win by a 'temporal' contestant over checkpoint plus RAG is therefore confounded: MAGE already reports that structuring memory around the execution path, rather than by similarity, wins on interdependent tasks, without needing any temporal-agency apparatus.
2. Reopening a past decision when later evidence invalidates it, with forking and preserved branches, is prior art.

The project's distinct claim must therefore rest only on what MAGE lacks:
- world-authored artifacts rather than the agent's own summaries;
- a strict known-then vs known-now separation (MAGE deliberately injects hindsight);
- repair forward from the present rather than rewinding;
- prospective, intervention-aware forecasting and prevented-future bookkeeping.

The first three are thin: a MAGE-style agent with a repo-history tool might already do well on smoke_v1. The fourth is still unbenchmarked in smoke_v1.

VERIFIER CORRECTIONS: replay was rated 'no' under a stricter deterministic-trace-replay reading. Under the given definition ('re-run execution from a historical point'), Revise ('restores a target boundary and resumes on a new branch', verbatim abstract) qualifies as partial. | fork_from_historical_state was understated as 'partial'. A new branch from an earlier state with the original kept as an inactive sibling is MAGE's core operation, which meets the definition (yes, scoped to agent state, not the environment). | uncertainty_representation was rated 'no'. Maintain's diagnostic notes (missing information, unsatisfied requirements) are stored in the node note field and in H, so they are unresolved items held in agent-visible state: weak partial. | '55.1% fewer tokens than long-context': the verbatim abstract says only 'reducing token consumption by 55.1%' with no comparator, and no recorded extract ties 55.1% to long-context. The comparator is unverified. | Author discrepancy: an independent arXiv-listing mirror (scratchpad/lit/repos/pf/daily/5-Jun-2026/AI/README.md:302) also gives 'Zhirui Wang', and lists the paper on 5-Jun-2026. The MSR page meta (msr_pub.html:130) gives 'Zilong Wang'. Two sources give the arXiv spelling as Zhirui, against the MSR page alone. Still unresolved.

UNVERIFIED: I could not independently re-obtain any arXiv HTML content. WebSearch was refused because the session budget was exhausted (200/200). Every mirror host probed was blocked, including web.archive.org, openalex, crossref, alphaxiv, r.jina.ai and paperswithcode. My verification therefore rests on the verbatim abstract plus the analyst's recorded search extracts, which are a summarizer's restatement.

Still unknown:
- whether bottom nodes are physically retained after Compress ('freeing space' is ambiguous);
- whether the environment is reset on Revise;
- the exact content of H and of Maintain notes, which determines whether uncertainty_representation is really partial;
- whether the agent can browse inactive branches (if so, cross_time_state_querying could rise);
- the comparator for the 55.1% figure;
- full Table 3 and the stated limitations;
- the 10th author's name.

Verification notes: /tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/lit/verify/mage.md

VERIFIED RATINGS:
- 1 immutable_historical_observations: partial -- The bottom layer records raw action-observation nodes, and abandoned segments are kept as inactive branches. Nothing says storage is append-only or immutable. The Compress extract says it is 'replacing a completed bottom-layer segment with a top-layer summary node, freeing space'. Retention of the r
- 2 historical_world_state: no -- Only the agent's own observation trace is stored. Neither the abstract nor any recorded extract describes an environment snapshot, reset or as-of reconstruction of the world.
- 3 historical_epistemic_state: partial -- Generous but defensible. Revise restores C and R to a step-id boundary, which is the agent's memory as of that point. It is materialized only in order to resume, and H then injects diagnostics from the later branch. So no query exists, and there is no cutoff in the state the agent actually sees.
- 4 historical_policy_objective_state: no -- There is a single fixed task instruction per task. The node schema has no goal or policy fields, and changes to them are not tracked.
- 5 execution_checkpoints: partial -- Restoring C and R to a boundary is close to a checkpoint restore for an LLM agent, whose runtime state is mostly its context. However, the state is derived from the tree path rather than snapshotted, and no tool or environment state is restored. 'Yes' is arguable.
- 6 replay: partial -- The definition is 're-run execution from a historical point'. The abstract says verbatim: 'Revise restores a target boundary and resumes on a new branch'. A recorded extract says Revise 'restores the execution state to the target boundary and resumes execution as a new branch'. That is re-execution 
- 7 fork_from_historical_state: yes -- This is MAGE's defining operation and meets both parts of the definition. The abstract says verbatim: 'resumes on a new branch' and 'isolating flawed segments from the active path'. Extracts say 'Subsequent actions branch from this restored point as sibling paths ... without discarding valid progres
- 8 counterfactual_action_branches: no -- Branches are committed real executions created after an error. Alternatives are never explored in simulation, in copies or without committing.
- 9 branch_provenance: partial -- Parent and child pointers give the parent and the divergence point. The Maintain note records the reason, but only for Maintain-triggered branches. There is no explicit branch record, timestamp or lineage query.
- 10 explicit_current_belief_state: partial -- C is a validated set of 'trusted' subgoal summaries kept separate from the raw trace, but it records task progress, not typed beliefs or assumptions.
- 11 uncertainty_representation: partial -- The definition includes 'unresolved items in state'. Maintain detects 'missing information, unsatisfied task requirements, or broken dependencies' and 'records the diagnostic feedback in the note field'. On Revise, H 'is updated with diagnostic feedback', so explicit unresolved-problem records sit i
- 12 future_state_rollout: no -- No world model, imagination or rollout appears in the abstract or any extract. Every node is a past step or a summary of past steps.
- 13 multiple_prospective_branches: no -- There is one active path. Inactive branches are past realized failures, not alternative futures.
- 14 probability_over_futures: no -- No futures are imagined, so none are assigned likelihoods.
- 15 backward_requirements: no -- Borderline. Maintain checks a completed subgoal retrospectively against the task instruction ('unsatisfied task requirements'). It does not derive present obligations or preconditions from a desired or feared future.
- 16 intervention_aware_forecasting: no -- The system has no forecasts.
- 17 prevented_futures_preserved: no -- There are no forecasts. Abandoned branches are realized failed executions, not prevented forecasts.
- 18 predicted_vs_realized: no -- Maintain compares a summary with its own subtree and the task instruction, not an earlier prediction with the outcome. There is no calibration component.
- 19 cross_time_state_querying: no -- Step ids on C are exposed only as Revise targets, and Revise mutates the active path. No state_at, diff or as-of query is described.
- 20 unified_temporal_abstraction: partial -- One tree spans past steps, the current active path and abandoned realized alternatives, and the current state is derived as a path through it. It has no prospective, simulated or world-state dimension.

## flowstate: FlowState: Execution State as Memory for Long-Horizon LLM Agents (arXiv:2609.34565)
The authors are Minghao Li, Bangyan Li, Zifan Wang, Yulong Li, Hu Xu, Gan Zhang, Jingtong Wu and Wenqiang Xu, all of Ant International, Ant Group. The paper was submitted to arXiv on 2026-09-28. Source: a WebSearch extract of https://arxiv.org/abs/2609.34565.

Sources: https://arxiv.org/abs/2609.34565 (Read through server-side WebSearch summaries of the abs page (title, authors, date, abstract), because arxiv.org is bloc); https://arxiv.org/html/2609.34565 (Read through about 35 targeted WebSearch queries (allowed_domains arxiv.org), each returning a summary of the HTML full ); github.com (WebSearch restricted to this domain) (Searched for an official repository and found none. Only unrelated 'flowstate' projects came up (makasim/flowstate, agen)

SUMMARY: FlowState is an agent memory framework. It keeps the agent's working state as typed state nodes, linked by typed relations, and treats that state as memory that carries across user requests q_1..q_K.

**Within a request**, the system runs one loop of ReAct steps:
- **Incremental State Update (ISU).** The model proposes a state delta made of Add, Update and Remove operations on the Active State. The delta is validated before commit: Add needs an unused id, references must resolve, and Update or Remove may only target states created in the current request.
- **Progressive State Access (PSA).** The model sees a lightweight Historical State Index of ids plus concise summaries for all earlier requests. It asks for specific historical states by id, or by following relations of states already disclosed, and the system discloses their full content and relations. It can trace back to raw tool observations kept as knowledge nodes.

**At the end of a request**, Persist writes the new states and relations into the Persistent State Repository, together with any raw tool results those states reference. Historical states keep their source request and cannot be deleted.

**Results reported in the paper.** With DeepSeek-V4-Flash, FlowState beats a full-context baseline by +4.55 pp average success rate on MemoryArena and +13.95 pp pass rate on τ³-Bench (Airline +20.0, Retail +7.9), with 43.2% and 40.6% fewer tokens. It also beats ReasoningBank, BM25, Mem0, ZipAct and ZipAct+BM25 on several metrics.

**Motivating example.** A user books hotel A and plans to switch if hotel B gets cheaper. When B's price drops, PSA re-discloses decision D7 together with its linked cancellation terms (C2) and policy evidence (E4). ISU then forms a new decision, D8, to keep A.

**Code** has not been released. The paper says: "We will release the complete source code at an appropriate time."

CORE STATE: The core abstraction is a graph of semantically typed state nodes joined by typed directed relations. It is held in three stores.

**Persistent State Repository (M_k)**
- Holds prior user requests, state nodes and the relations between them.
- Each node records its source request, a semantic identifier, a category and its full content.
- A raw tool result is kept as an accessible node (a knowledge node) only if a newly created state references it.
- M_k is not placed in the model's context.

**Historical State Index (G_k)**
- Built at the start of each request and placed in the model's context.
- For each prior request it holds only each state's id and a concise summary.

**Active State (S_k,t)**
- Holds the states created in the current request, plus any historical states and relations disclosed so far.
- Undisclosed historical content is excluded.

**Five node types** ("Table 6"; this is the extract's defining sentence, not the table itself):
- user-side **preferences**: preferences, requirements, constraints;
- environment-side **knowledge**: tool observations;
- environment-side **attributes**: entity-level information distilled from observations;
- agent-side **judgements**: assessments of task objectives, plans, decisions and risks;
- agent-side **artifacts**: reusable outputs.

**Relation types:** supports, derives, follows, supersedes.
- Relations are declared through refs on the source node.
- Every edge points from the state being added or updated to the target state_id.
- Per-type semantics were not retrieved.

All of the above is from search extracts of https://arxiv.org/html/2609.34565.

BRANCHING/REVISIT: **Revisit.** Revisiting is non-destructive, by disclosure. Earlier states stay in M_k, cannot be deleted, and keep their source request. Within the current context they can be re-disclosed by id or by following relations.

**Revising an earlier decision.** History is never edited in place. Update and Remove apply only to current-request states, so revising an earlier-request decision means adding a new node. In the hotel example, D8 is created and D7 is preserved. A 'supersedes' relation type exists, but whether D8 is formally linked to D7 by it was not confirmed.

**No branching.** The extracts describe no branching, forking, rollback, restore or replay. The paper contrasts itself with concurrent work MAGE, which 'organizes execution history as a hierarchical state tree with active-path context and branching revision' (Revise 'restores a target boundary and resumes on a new branch'). FlowState is described as typed nodes individually addressable across requests, not a tree. Its history is a single linear sequence of requests.

Source: search extracts of https://arxiv.org/html/2609.34565.

PRESERVED VS LOST: **Preserved across requests:**
- prior user requests;
- all states and relations created in a request and 'retained' at its end;
- each node's source request, semantic id, category and full content;
- raw tool results that a new state references, kept as knowledge nodes.

Historical states cannot be deleted.

**Lost or uncertain:**
- **Unreferenced raw tool results.** The paper says results are retained *if referenced*. Two search summaries inferred that unreferenced ones are discarded. Whether a full trajectory log is kept elsewhere is unclear.
- **Intermediate edits within a request.** Update and Remove change current-request nodes in place before Persist. No version history of those edits is described.
- **The Active State's composition at each step** is not described as being saved.
- **Index summaries** are 'maintained'. Whether they change after their request ends is unclear.
- **Time granularity** is the request, not a timestamp.

Source: search extracts of https://arxiv.org/html/2609.34565.

BELIEF STATE: **Current beliefs.** The Active State is an explicit structured current-belief store. 'judgements' nodes hold the agent's assessments of objectives, plans, decisions and risks. 'preferences' hold the user's requirements and constraints. 'knowledge' and 'attributes' hold observed environment facts.

**Past beliefs.** Each node carries its source request and historical nodes are immutable after Persist. So the agent's judgements as of request k survive, as with D7 kept after D8.

**What is missing for epistemic cutoffs:**
- no as-of reconstruction operator;
- no cutoff that hides later information when reasoning about the past (disclosed historical states sit in the same Active State as current knowledge);
- no record of what was in context or known at each step;
- no confidence or uncertainty fields: the documented node fields are only source request, id, category and content.

Source: search extracts of https://arxiv.org/html/2609.34565.

FUTURE: None found. The only forward-looking content is that 'judgements' may record plans and risks as text, and the motivating example contains a conditional plan ('reconsider if B becomes cheaper') that is re-evaluated when the trigger occurs.

No world model, rollout, imagined futures, probabilities over futures, goal regression or forecast tracking appears in any of about 35 method-focused extracts. One extract explicitly stated that it found no counterfactual reasoning or future-state simulation. This is absence of evidence in the retrieved text, not an explicit denial by the paper.

EVALUATION: **Benchmarks**
- MemoryArena subset: Bundled Web Shopping, Group Travel Planning, Formal Reasoning (Math and Physics). These test information reuse across interdependent subtasks.
- τ³-Bench: Airline (50 base tasks) and Retail (114 base tasks). These test policy-constrained tool use against a simulated user.

**Baselines (all DeepSeek-V4-Flash)**
- Full Context;
- memory systems: ReasoningBank, BM25, Mem0;
- state tracking: ZipAct;
- hybrid: ZipAct+BM25.
- For the cross-model check, only Full Context and FlowState were also run with GPT-5.6-terra and Qwen3.5-397B-A17B.

**Headline results vs Full Context (DeepSeek-V4-Flash)**

| Benchmark | Gain | Token reduction |
|---|---|---|
| MemoryArena | +4.55 pp average SR | 43.2% |
| τ³-Bench | +13.95 pp average pass rate | 40.6% |

- τ³ detail: Airline +20.0 and Retail +7.9 pass rate; DB accuracy +7.5 and +5.3.
- MemoryArena PS: Web Shopping 42.89 (+11.78 over the strongest memory-system baseline); Group Travel 12.57 (+5.61).
- FlowState beats ZipAct+BM25 on all nine metrics.
- Physics token reduction of 51.69% comes from a single unconfirmed extract.

**Ablation (Table 3; Group Travel and Web Shopping)**

| Variant | Travel SR / PS / sPS / tokens | Shopping SR / PS / tokens |
|---|---|---|
| FlowState | 0.74 / 12.57 / 91.87 / 128.93M | 5.33 / 42.89 / 44.83M |
| w/o PSA | 0.37 / 9.36 / 87.18 / 160.27M | 3.33 / 44.67 / 115.37M |
| w/o ISU | 0.00 / 9.15 / 90.34 / 93.16M | 0.00 / 32.11 / 69.01M |

- Absolute SRs are very low.
- w/o PSA has a higher PS than FlowState on Shopping.
- w/o ISU uses fewer tokens on Travel.
- Seeds and variance were not retrieved.

Sources: search extracts of https://arxiv.org/html/2609.34565.

DOES NOT COVER: FlowState does not cover:
- **Strict epistemic cutoff.** There is no reconstruction of what was believed at t that excludes later information; disclosed past states sit next to current knowledge.
- **Past world state.** The external world state at t cannot be reconstructed.
- **Execution history.** No execution checkpoints, replay, forks or branches, and so no 'fork, never overwrite time' semantics.
- **Counterfactual actions.** None are explored.
- **Anything forward-looking.** No future-state simulation, multiple prospective branches, probabilities, backward requirements from desired or feared futures, intervention-aware forecasts, preserved prevented futures, or predicted-vs-realized calibration.
- **Agent policy, model or identity over time.** Not tracked.
- **Temporal queries.** No state_at, diff or as-of queries.
- **Raw observations.** They are retained only when referenced, so the observation log is not guaranteed to be complete.

RELATION TO smoke_v1: FlowState's motivating example is structurally the same as the smoke_v1 premise. A later event (B's price drop) changes the significance of an earlier decision (D7: book A, reconsider if B is cheaper). The agent must notice this, reopen the decision with its linked evidence (cancellation terms C2, policy evidence E4), and form a revised decision (D8).

**Consequences for smoke_v1:**
1. **The 'notice and reopen an earlier decision with evidence' skill is no longer distinctive.** FlowState is published prior art for structured, typed, request-tagged execution state with supersedes and evidence edges. It improves exactly this behaviour over full context, ZipAct+BM25, Mem0, BM25 and ReasoningBank, and costs fewer tokens.
2. **The smoke_v1 baseline (event log, checkpoints, hybrid RAG, rolling summary, read-only repo history) has no typed decision/evidence graph.** A FlowState-style variant would be a stronger, fairer baseline. Without one, a temporal-agent win could be credited to time navigation when it really comes from structured state. FlowState's code is not released, so this would have to be re-implemented from the paper.
3. **Where smoke_v1 still goes beyond FlowState:**
   - The smoke_v1 decision is world-authored (an ADR or ticket in the repo). FlowState's decisions are the agent's own judgements, and it would only 'remember' an ADR if the agent's ISU created a node referencing that observation.
   - smoke_v1 asks for an explicit separation of 'true then / known then / known now about then'. FlowState has no epistemic-cutoff reconstruction; it keeps D7 and D8 side by side and leaves the distinction to the LLM.
   - smoke_v1 also requires remediating code, which FlowState does not address.

Smoke_v1 as currently framed mostly tests a capability FlowState already claims. The parts that remain distinctive are the cutoff-based 'known then' reconstruction, world-state-at-t reconstruction, and the forward-looking and branching parts of the north star, which smoke_v1 does not yet exercise.

VERIFIER STRONGEST THREAT: FlowState is dated, public prior art (Ant Group, 2026-09-28) for the core behaviour smoke_v1 tests: a later observation changes the meaning of an earlier decision, and the agent reopens that decision together with its linked evidence, then records a new decision without overwriting the old one (D7 kept, D8 added, typed supersedes/supports edges, request-tagged non-deletable nodes). It reports gains over full context and over retrieval memories (BM25, Mem0, ReasoningBank) at about 40% fewer tokens, which is close to the class of baseline smoke_v1 uses (event log, checkpoints, hybrid RAG, summaries). Two consequences follow. (1) A temporal-agent win over the current smoke_v1 baseline is confounded: structured decision/evidence state may explain it rather than time navigation, so a FlowState-style structured-state baseline is needed before any temporal-agency claim. (2) Every FlowState node carries an immutable source request, so 'known then' reconstruction with a cutoff is roughly a trivial filter (source_request <= k) on top of FlowState. The project must show that cutoff-correct reconstruction changes outcomes, not merely that it can be stated. The parts that remain plausibly distinctive are world-truth-at-t versus observed-at-t, forward-looking forecasting with intervention and prevented-future semantics, and branching. smoke_v1 does not yet exercise most of these.

VERIFIER CORRECTIONS: Overreach in relation_to_smoke_v1: 'It improves exactly this behaviour [notice and reopen an earlier decision with evidence] over full context, ZipAct+BM25, Mem0, BM25 and ReasoningBank'. The evaluation reports aggregate MemoryArena SR/PS and τ³-Bench pass rate and DB accuracy. The hotel D7/D8 reassessment is a motivating example; nothing retrieved shows it was evaluated in isolation or that the gains come from it. The abstract's 'enable agents to reassess prior decisions' is a design claim, not an isolated measured effect. | uncertainty_representation was understated. By the analyst's own extracts, typed judgement nodes explicitly record 'risks'/'execution risks', and the example stores an open conditional plan, which counts as explicit unresolved items. Rating changed from no to partial (still no confidence or probability fields). | The affiliation 'all of Ant International, Ant Group' is only partly confirmed. An independent digest (isaacveg/mas-daily daily/2026-10-02.md) lists the institution as 'Ant Group'. 'Ant International' and 'all' were not independently confirmed. | Caution for downstream use: a third-party blog (Dannyzen/eliezer-weekly-roundup-public AgenticAI/2026-09-29/reasoning.md) lists node types including 'unresolved questions'. That is the blogger's recommendation, not the paper's taxonomy.

UNVERIFIED: I could not independently re-read any method-level text. The session WebSearch budget was exhausted (200 of 200), and arxiv, export.arxiv, openalex, crossref, web.archive and grep.app were all blocked by the proxy. Independent verification covers only the abstract, metadata, affiliation and code status, through GitHub-hosted arXiv API dumps and digests. Everything else rests solely on the analyst's WebSearch summaries of the arXiv HTML, which are not verbatim: the M_k/G_k/S_k,t definitions, ISU validation rules, the five node types and Table 6, the relation types, the hotel D7/D8 example, the ablation Table 3, 'beats ZipAct+BM25 on all nine metrics', and the MAGE contrast. All 'no' ratings for branching and forward-looking capabilities are absence-of-evidence judgements. The uncertainty_representation change (no to partial) depends on the extract wording about 'risks'. Table 6 and the Appendix B.3 prompts were not read by anyone. Verification notes: /tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/lit/verify/flowstate.md. Fetched sources: /tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/lit/verify/flowstate_src/.

VERIFIED RATINGS:
- 1 immutable_historical_observations: partial -- The analyst's extracts support this. Historical states 'retain their original source requests and cannot be deleted', and Update/Remove are limited to current-request nodes. Raw tool results are kept only 'if referenced by a state newly created by the model', and within-request edits happen in place
- 2 historical_world_state: no -- Request-tagged knowledge and attribute nodes record what the agent observed then (epistemic), not a reconstruction of world truth then. Nothing separates true-then from observed-then. One could argue for 'partial-as-observed', but the definition asks for world-state reconstruction, so 'no' holds.
- 3 historical_epistemic_state: partial -- Judgement nodes are request-tagged and cannot be deleted; D7 is kept after D8 is created. There is no as-of or cutoff operator, disclosed history sits next to current knowledge, and within-request edits are lost. All of this rests on the analyst's extracts; I could not re-query.
- 4 historical_policy_objective_state: partial -- This rating is generous but defensible. User preferences, requirements and constraints, and agent 'task objectives, plans', are typed request-tagged nodes. A supersedes edge from a new node to a historical id is structurally allowed, since refs must only resolve to valid ids, but actual use is unver
- 5 execution_checkpoints: no -- The persisted repository is semantic memory with no restore or resume operation. The summarizer's 'appears to support checkpoint restoration' was rightly rejected as inference.
- 6 replay: no -- Neither the abstract nor any extract describes re-execution from a historical point. History is only disclosed into the current context.
- 7 fork_from_historical_state: no -- The paper reportedly contrasts itself with MAGE's branching Revise ('restores a target boundary and resumes on a new branch'). FlowState history is a linear sequence of requests.
- 8 counterfactual_action_branches: no -- Each ReAct step is one model invocation acting on the real environment. No simulated or sandboxed alternatives are described.
- 9 branch_provenance: no -- There are no branches. Source-request tags and supports/derives/follows/supersedes edges are dependency provenance, not branch provenance.
- 10 explicit_current_belief_state: yes -- The verbatim abstract confirms: 'FlowState preserves semantically typed state nodes, their relations...' and 'Incremental State Update (ISU) maintains the current state based on new inputs and feedback'. The extracts add the typed Active State and validated Add/Update/Remove deltas.
- 11 uncertainty_representation: partial -- The definition includes 'explicit ... unresolved items in state'. The analyst's own extracts (two independent phrasings) say the typed agent-side judgement nodes record 'the agent's assessments of task objectives, plans, decisions, and risks' and 'execution risks'. The motivating example stores an o
- 12 future_state_rollout: no -- Neither the abstract nor any extract mentions a world model or imagined rollout. Plans are free-text judgements. This is an absence-of-evidence judgement.
- 13 multiple_prospective_branches: no -- No mechanism holds alternative futures.
- 14 probability_over_futures: no -- No likelihoods are attached to futures, and no node field for probability is documented.
- 15 backward_requirements: no -- Objectives and plans are LLM-written judgement text. No operator derives preconditions from a desired or feared future.
- 16 intervention_aware_forecasting: no -- No forecasts are described.
- 17 prevented_futures_preserved: no -- There are no forecasts, so none are labelled as prevented.
- 18 predicted_vs_realized: no -- The hotel example re-evaluates a conditional plan when it triggers. No earlier prediction is scored against the outcome for calibration.
- 19 cross_time_state_querying: partial -- This is a weak partial. The per-request Historical State Index plus disclose-by-id or by-relation gives a crude 'what was created in request k' lookup. There is no state_at(t), diff or as-of operator.
- 20 unified_temporal_abstraction: partial -- The verbatim abstract says 'unifying current decision-making with the reuse of historical information'. An extract says historical states are expanded 'through the same representation used for current states'. No counterfactual or prospective states are covered.

## langgraph: LangGraph (langchain-ai/langgraph, Python, version 1.2.12; langgraph-checkpoint 4.2.0): Persistence, Checkpointers and Time Travel
LangChain, Inc. (open-source repo langchain-ai/langgraph and docs repo langchain-ai/docs). Analyzed at langgraph commit 7dc9195e (2026-10-02) and docs commit 6d6080f5 (2026-10-03). There is no paper.

Sources: https://github.com/langchain-ai/langgraph (commit 7dc9195e4141c8fbd8118581b3dd61d158628aa8) (git clone --depth 1. Read libs/checkpoint/langgraph/checkpoint/base/__init__.py, libs/langgraph/langgraph/pregel/{main.p); https://github.com/langchain-ai/docs (commit 6d6080f536bb0c2885a7cfa44abf0933cdb85b4c) (git clone --depth 1. Read src/oss/langgraph/{use-time-travel,checkpointers,persistence,use-subgraphs,graph-api,functiona); local empirical probes: /tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/lit/verify/langgraph_probe{,2,3,4}.py (+ .out) (Editable pip install of the cloned libs into a venv, then ran scripts that count node executions, inspect raw Checkpoint)

SUMMARY: LangGraph saves a checkpoint of graph state at every super-step boundary, keyed by (thread_id, checkpoint_ns, checkpoint_id). It also stores per-task "pending writes" linked to the checkpoint each step started from.

Time travel has two operations:
(a) Replay: invoke(None, config_with_past_checkpoint_id). Nodes before the checkpoint are not re-run. Nodes after it re-execute, so LLM and tool calls run again and interrupts re-fire. The loop first writes a source="fork" checkpoint whose parent is the replayed checkpoint.
(b) Fork: update_state(past_config, values, as_node). This runs the chosen node's writers (and reducers) on the values and saves a new source="update" checkpoint whose parent is the source checkpoint. The original history stays, and the new checkpoint becomes the thread head.

Subgraphs store checkpoints under namespaces "node:task_id" (joined with "|"), with metadata.parents mapping each enclosing namespace to a checkpoint id. A checkpointer=True subgraph keeps one history per thread under a namespace without task ids.

This is a strong, well-tested execution-state versioning and debugging/HITL mechanism. It does not:
- version the world or the long-term Store;
- enforce an epistemic cutoff on replay;
- record code, policy or reasoning;
- provide anything prospective (forecasts, probabilities, goal regression).

CORE STATE: Checkpoint TypedDict {v, id (uuid6, monotonic), ts, channel_values, channel_versions, versions_seen, updated_channels} (checkpoint/base/__init__.py:93-124; built by pregel/_checkpoint.py:149-214).

CheckpointMetadata {source in input|loop|update|fork, step, parents (namespace->checkpoint_id of enclosing graphs), run_id, counters_since_delta_snapshot} (base/__init__.py:39-87). Primitive config.metadata and config.configurable keys are also copied in (base/__init__.py:758-776).

CheckpointTuple {config, checkpoint, metadata, parent_config, pending_writes: list[(task_id, channel, value)]} (base/__init__.py:140-147). Storage keeps parent_checkpoint_id per (thread, namespace), and a writes table keyed (thread, ns, checkpoint_id, task_id, idx).

User-facing view: StateSnapshot {values, next, config, metadata, created_at, parent_config, tasks, interrupts} (types.py:711-735).

The unit is the graph's channel state at a super-step boundary within one thread and namespace. It is not world state and not beliefs.

BRANCHING/REVISIT: Revisiting a checkpoint never rolls the thread back. Both replay and update_state append new checkpoints whose parent_checkpoint_id points at the revisited checkpoint:
- replay first writes a source='fork' checkpoint (_loop.py:928-947);
- update_state writes source='update' (main.py:2014-2021, _checkpoint.py:127-131);
- update_state with as_node='__copy__' writes a source='fork' sibling (main.py:1778-1803).

The newest checkpoint id becomes the thread head (probe 1: 'latest == fork: True'). Earlier branches remain reachable only by checkpoint_id or by walking parent_config. There is no branch id or name. get_state_history interleaves all branches by id (probe 1 listed nine checkpoints from three branches).

Docs: 'update_state does not roll back a thread. It creates a new checkpoint that branches from the specified point. The original execution history remains intact.' (use-time-travel.mdx:129-133). Server docs: 'resuming past execution produces a new fork in the history' (langsmith/human-in-the-loop-time-travel.mdx:6).

Granularity is the super-step. You cannot time-travel into the middle of a node, or between nodes of a default (per-invocation) subgraph (use-time-travel.mdx:358-360). A checkpointer=True subgraph has its own per-step history that can be forked through get_state(subgraphs=True).tasks[i].state.config (use-time-travel.mdx:436-475).

Interrupts always re-fire on time travel (use-time-travel.mdx:216; _loop.py:850-876; probe 1).

Forks execute for real in the same runtime. There is no simulation or sandbox, and side effects happen.

PRESERVED VS LOST: PRESERVED:
- Channel values per super-step, plus channel_versions and versions_seen, which determine the next nodes.
- Per-task writes, including errors, interrupts and resume values, linked to the checkpoint each step started from. Probe 1: the checkpoint before 'act' holds act's output as a pending write.
- ts, step and source, and the parent pointer.
- Subgraph checkpoints under their namespaces. Per-invocation subgraph checkpoints remained in storage after completion (probe 1), but get_state can only discover them while the subgraph is interrupted (use-subgraphs.mdx:1261).
- Original checkpoint values are unchanged after replay or fork (probe 1).
- Primitive configurable and metadata keys from the config, on loop checkpoints only (probe 4).

NOT PRESERVED or NOT CONTROLLED:
(1) External side effects. They are re-executed on replay or fork and never undone. Probe 1 shows duplicated 'file_written'; graph-api.mdx:772-774 says 'Code and side effects before the pause run again ... Use idempotency keys'.
(2) Nondeterministic LLM/tool outputs. They are not reused on time-travel replay (plan-609912 -> plan-32779 in probe 1; use-time-travel.mdx:20-24). The opt-in node cache is the exception. Resume, unlike time travel, does reuse completed task and successful-node writes (functional-api.mdx:793; checkpointers.mdx:29).
(3) World and environment state, including LangGraph's own long-term Store. The Store sits outside graph state and is overwritten in place (persistence.mdx:19; store/base/__init__.py:865). Probe 3: replaying an old checkpoint read the present store value v=2 and wrote v=3.
(4) Code, prompt and model version. Replay runs current node code, and nothing records graph or code versions.
(5) The reasoning or decision rationale, unless the developer put it in state. Fork metadata has no reason, actor or explicit as_node field (probe 4).
(6) Beliefs and uncertainty: no such notion exists.
(7) Strict immutability, for these reasons:
- update_state appends writes to the source checkpoint (probe 1: 1 -> 3 writes);
- special writes are upserted (Postgres base.py:146-153; memory/__init__.py:493-503);
- checkpoint rows are UPSERT by id (base.py:137-144);
- prune, delete_thread and delete_for_runs exist, and the docs recommend pruning (persistence.mdx:101-114);
- durability='exit' saves no intermediate checkpoints (checkpointers.mdx:603).
(8) The 'writes' metadata field that the docs still show (checkpointers.mdx:244, 293) is stripped by the code (base/__init__.py:784-785; probe 1).

BELIEF STATE: None as a first-class concept. 'State' is whatever TypedDict or Pydantic schema the developer defines, usually a messages list plus fields, with optional reducers (checkpointers.mdx:566).

A checkpoint does capture everything the graph held in state at step k, so get_state(checkpoint_id) gives a naturally cut-off view of the agent's in-graph context at that step. That is partial 'known then'. Nothing distinguishes beliefs from observations, records confidence, or represents assumptions or requirements.

No cutoff is enforced when re-running from the past. Replayed nodes call current tools and LLMs and read the current Store (probe 3), so hindsight can leak into a replay.

The long-term Store (cross-thread memory) is a mutable key-value store with created_at and updated_at but no versions (store/base/__init__.py Item, put).

FUTURE: None. LangGraph has no world model, rollout or imagination, no forecast objects, no probabilities, and no goal regression. 'Fork' and 'replay' produce real executions of the actual graph from a past state. They are retrospective what-if executions with real side effects, not simulated futures. StateSnapshot.next and tasks list only the nodes scheduled for the next super-step. That is control flow, not a forecast.

EVALUATION: No paper and no benchmark. The only validation is the repo's own unit tests, mainly libs/langgraph/tests/test_time_travel.py (3966 lines) and test_time_travel_async.py. Examples: test_replay_reruns_nodes_after_checkpoint (line 69), test_replay_from_final_checkpoint_is_noop (line 112), test_multiple_forks_from_same_checkpoint (line 182), test_replay_from_before_interrupt_refires (line 226), plus subgraph replay and fork tests (lines 685-1332). There is also a checkpointer conformance suite (libs/checkpoint-conformance).

My own probes (InMemorySaver) confirmed the following:
- Replay re-executes downstream nodes, re-produces side effects and does not reuse nondeterministic outputs.
- Replay creates a source=fork checkpoint.
- update_state creates a source=update child of the source checkpoint, which becomes the head, and appends writes to the source checkpoint.
- Interrupts re-fire.
- The Store is not rolled back.
- The opt-in node cache short-circuits replay.
- Subgraph checkpoints persist under 'node:task_id' with metadata.parents set to the parent checkpoint id.

No agent-performance evaluation of time travel exists.

DOES NOT COVER: Not covered:
- A strict epistemic cutoff. Replays see present-day tools, LLM and Store (probe 3).
- Separating what was true then (world), what was known then, and what is known now about then.
- Versioned world or environment state.
- Tracking identity, objective, policy or code changes. Replay uses current code, and configurable keys are only incidentally copied.
- Recording the reasoning or justification behind a decision or a fork.
- Explicit belief or uncertainty state.
- Anything prospective: future simulation, multiple imagined futures, probabilities, backward requirements from desired or feared futures, intervention-aware forecasts, preserving prevented forecasts, predicted-vs-realized comparison.
- Branch-aware querying, diffs and as-of queries.
- Time travel as an agent-facing cognitive operation. The docs position it for developers and humans: 'to replay prior graph executions to review and / or debug' (checkpointers.mdx:26).

RELATION TO smoke_v1: LangGraph checkpointing is close to, and somewhat richer than, the 'checkpoints' component of the smoke_v1 baseline: restorable execution state, replay and fork, with parent pointers. It does not address the core smoke_v1 task.

The ADR or ticket and the code are world-authored artifacts outside graph state. LangGraph neither versions nor rolls them back (the Store and the external world are not checkpointed; probe 3). So 'what was true then' cannot be answered from checkpoints. 'Known then' is available only for content the agent kept in its graph state at that super-step. 'Known now about then' would require the agent to compare an old snapshot with the head on its own; there is no diff.

Using replay to reconstruct the agent's earlier reasoning would re-execute LLM calls with present-day tools and Store, which risks hindsight leakage and duplicate side effects.

In short, a LangGraph-based agent with get_state_history is roughly the baseline's 'event log + checkpoints' plus fork. Adding LangGraph's mechanism to the baseline would not by itself supply the epistemic-cutoff, reopen-with-evidence or prospective capabilities the thesis targets. It is a reasonable substrate on which such tools could be built, and a strong baseline should arguably include a get_state_at(checkpoint) tool to be fair.

VERIFIER STRONGEST THREAT: LangGraph, the most widely deployed agent runtime, already implements the project's slogan 'never overwrite time, fork it' for agent execution state. It provides immutable-by-default per-step checkpoints, state_at(checkpoint) reads, replay, forks with parent pointers, user-attached fork reasons that can be filtered, per-checkpoint capture of config (model/prompt-version keys), and server-side versioned assistant configs. So the retrospective half of the thesis (reconstruct and question past versions of the agent's own state, branch with provenance, track policy/config changes) reduces largely to engineering on existing primitives.

If an agent keeps the ADR or ticket text it read in its messages state, get_state(old_checkpoint) already answers 'known then' with a natural cutoff. 'Known now about then' is a diff between that snapshot and the head, a thin tool away. A fair smoke_v1 baseline could therefore add get_state_at/diff tools over LangGraph-style checkpoints, and the advantage claimed for the temporal contestant would have to come from what LangGraph lacks:
- an enforced epistemic cutoff on world/Store reads;
- a versioned world state ('true then');
- the prospective machinery (forecasts conditioned on interventions, prevented-future preservation, predicted-vs-realized, backward requirements).

The project's distinct hypothesis survives only if its benchmark rewards those capabilities, not retrospective checkpoint inspection and forking.

VERIFIER CORRECTIONS: historical_policy_objective_state was understated as 'no'; corrected to 'partial'. Each checkpoint automatically copies primitive configurable/metadata keys into its metadata, and these are filterable. The Agent Server versions assistants (prompt/model/tools configs) with history and rollback (langsmith/assistants.mdx:39,115-120; /assistants/{id}/versions). Server checkpoint metadata includes graph_id, and per encryption.mdx:156, likely assistant_id and langgraph_version. | The claim that 'update_state forks do not carry those keys (probe 4)' is a probe artifact. Keys present in the config passed to update_state (config['metadata'] or configurable) ARE stored on the fork checkpoint (verifier probe C: {'source':'update',...,'why':'ADR-7 reopened','actor':'agent'}) and can be queried with get_state_history(filter=...) (probe F). | The positioning quote checkpointers.mdx:26 was truncated. The same passage adds that checkpointers 'make it possible to fork the graph state at arbitrary checkpoints to explore alternative trajectories', so the docs do frame forks as alternative-exploration, not only debugging. | Nuance on immutability: update_state appends writes to the source checkpoint's storage, but in the verifier probe the historical get_state(source) view (tasks/results/values) was unchanged. The mutation is additive storage, not a rewrite of the user-visible record. | Additional finding that strengthens 'no code/policy tracking': the LangGraph 1.x Runtime context= (the recommended replacement for configurable) is NOT recorded in checkpoint metadata (verifier probe A).

UNVERIFIED: - **Agent Server internals.** The server is closed source, so it is unclear whether its checkpoint metadata records the active assistant VERSION (not just assistant_id). The indirect evidence is the SKIP_FIELDS list and the get_state example; I did not observe it. It is also unclear what threads.copy preserves and how long server-side history is retained.
- **Postgres and SQLite savers** were not executed, only read.
- **The JS implementation** was not examined.
- **DeltaChannel (beta)** failure modes under prune or copy were not probed.
- **Probe coverage.** All probes used InMemorySaver on Python 3.11.
- **Judgement calls.** The #4 upgrade to partial depends on counting incidental config capture plus server assistant versioning as policy tracking; a stricter reader could keep it at 'no'. #20 partial is a judgement call: three of the four required state kinds are covered, and the prospective kind is absent.

VERIFIED RATINGS:
- 1 immutable_historical_observations: partial -- Confirmed. Each super-step appends a new checkpoint, and replay and fork leave original values unchanged (analyst probe 1; verifier probe D2). Storage is not strictly immutable: update_state appends writes to the SOURCE checkpoint (main.py:1980-1986; verifier probe E shows 3 writes on the source), c
- 2 historical_world_state: no -- The Store Item has only value/key/namespace/created_at/updated_at, and put is 'Store or update an item'. There is no version history. Analyst probe 3 output confirmed: replay saw store v=2 and wrote v=3. The external world is not versioned. World facts modelled inside graph state would be checkpoint
- 3 historical_epistemic_state: partial -- get_state(checkpoint_id) returns in-graph state as of that super-step, which is a natural cutoff for content held in state. No cutoff is enforced on re-execution: current tools, LLM and Store are used (probe 3). There is no belief/knowledge labelling.
- 4 historical_policy_objective_state: partial -- The analyst under-weighted two real mechanisms. (1) Every checkpoint automatically copies primitive config.metadata/config.configurable keys, such as model_name or system_prompt_version, into its metadata (base/__init__.py:766-775; analyst probe 4), and these keys can be queried with get_state_histo
- 5 execution_checkpoints: yes -- Confirmed: a Checkpoint per super-step plus per-task pending writes, with resume after an interrupt or failure that does not re-run successful nodes.
- 6 replay: yes -- Confirmed. is_replaying (_loop.py:316) disables the reapply of stored writes (662-665), so downstream nodes re-execute, and a source='fork' checkpoint is written (928-947). This is re-execution, not deterministic replay.
- 7 fork_from_historical_state: yes -- Confirmed. update_state creates a source='update' checkpoint whose parent is the source checkpoint, and the original is intact. '__copy__' creates a source='fork' sibling under the source's parent (verifier probe G).
- 8 counterfactual_action_branches: partial -- Docs frame forks as exploration: 'checkpointers make it possible to fork the graph state at arbitrary checkpoints to explore alternative trajectories' (checkpointers.mdx:26; the analyst truncated this quote). But branches execute for real: side effects happen, the Store is shared, and nothing is sim
- 9 branch_provenance: partial -- Parent pointer, source, step, ts and parents namespace map are confirmed. Verifier probe C/F: a reason/actor passed in config['metadata'] to update_state is stored on the fork checkpoint and is filterable. None of this is automatic, and there is no branch id and no recorded as_node.
- 10 explicit_current_belief_state: no -- State is a developer-defined channel schema, and the Store is a generic key-value store. There is no belief/assumption structure.
- 11 uncertainty_representation: no -- No confidence or unresolved field exists in Checkpoint, CheckpointMetadata or StateSnapshot. A docs grep for 'uncertaint|confidence score' in oss/langgraph found nothing relevant.
- 12 future_state_rollout: no -- There is no world model or simulation. A docs grep for forecast/world model/dry-run/what-if/counterfactual in oss/langgraph found only an unrelated error page.
- 13 multiple_prospective_branches: no -- Multiple executed forks can coexist, but they are realized executions, not imagined futures, and no compare API exists.
- 14 probability_over_futures: no -- No mechanism exists in the code or docs.
- 15 backward_requirements: no -- No goal regression exists.
- 16 intervention_aware_forecasting: no -- There are no forecasts.
- 17 prevented_futures_preserved: no -- There are no forecasts. Abandoned forks persist as unlabelled executed histories.
- 18 predicted_vs_realized: no -- There are no prediction objects and no comparison or calibration.
- 19 cross_time_state_querying: partial -- get_state(checkpoint_id) works as state_at. get_state_history supports before/limit/equality filter on metadata, including custom keys (probe F). A grep for def .*(diff|as_of|state_at|children|branch) found no diff, as-of or lineage API.
- 20 unified_temporal_abstraction: partial -- One checkpoint tree (thread, ns, id, parent) spans past, head and executed forks. Prospective states are absent, so partial is the ceiling.

## pos: Beyond Memory: Harnessing Long-Horizon Agents with Explicit Belief States (arXiv:2610.01415)
Authors: Yu Luo, Jiamin Jiang, Yimin Zuo, Xidao Wen, Rongchen Gao, Yongqian Sun (corresponding), Shenglin Zhang, Guiyang Liu, Cheng Zhang, Fang Situ, Qi Zhou, Dan Pei. Affiliations: Nankai University, Alibaba Group, Tsinghua University. arXiv v1 was submitted 2026-10-01 in cs.AI. The work was done during an internship at Alibaba (repo README:193).

What "PoS" stands for: "Progression of States". This comes from the official repo (README.md:7 "# PoS · Progression of States"; CITATION.cff title "PoS: Progression of States") and the project page title. The abstract itself does not expand the acronym.

Sources: https://github.com/luoyu100/PoS (Official code repo, linked from the authors' project page (pos_project.yml code_url). git clone --depth 1, HEAD 6818cfa6); https://luoyu100.github.io/projects/progression-of-states/project/ (Authors' project page. *.github.io is blocked, so I read its source by cloning https://github.com/luoyu100/luoyu100.gith); https://arxiv.org/abs/2610.01415 (Not accessed directly: arxiv is blocked and the WebSearch budget was already exhausted (200/200). I got the verbatim abs); https://arxiv.org/html/2610.01415v1 (Not accessed directly. Section headers and Figure 1/2 captions are verbatim from a scrape of this HTML page in averkij/t); https://raw.githubusercontent.com/vollero/hf-daily-paper-summaries/main/summaries/2026/10/2026-10-02/2610.01415.md (Third-party LLM summary citing paper sections and tables. Secondary. Used only for Appendix G limitations, baseline adap); https://raw.githubusercontent.com/gbdata365/daily_papers/main/papers/2610.01415_new.html (Third-party Korean summary. Secondary. Source of the project-page link and of the trapping-pattern percentages (unverifi)

SUMMARY: PoS is an inference-time context-management framework for long-horizon LLM agents. It replaces the raw interaction history in the policy's decision context with an explicit, LLM-maintained belief state B_t = (W_t, G, Δ^E_t, Δ^A_t):
- W_t: an Entity/State/Relation graph of the current world, with confidence and an observed/inferred tag.
- G: a fixed goal.
- Δ^E_t: epistemic gaps (what remains unknown).
- Δ^A_t: achievement gaps (what remains undone).
- One "Active Gap" (stored as `frontier`) focuses action selection.

Each step works as follows:
- An LLM proposes a delta update.
- A "Belief Sentinel" (another LLM call plus a mechanical verbatim-quote grounding filter) audits the changed records for internal contradictions and contradictions with the raw trajectory. A failed candidate gets one repair; if that also fails, the previous belief is kept.
- Progress is labelled per transition.

Over a window of K=8 verified transitions, PoS computes "belief health" H = 1 - max(P_E,P_A)·max(S,R) from gap persistence, progress stagnation, and recurrence of past belief snapshots. When H <= 0.25 it declares "Belief Trapping", classifies it as Static, Cycle or Drift, and adds textual recovery constraints C = C_pattern ∪ C_gap to the policy prompt.

Reported results (Table 1):
- PoS has the best overall metric in all 12 benchmark×backbone settings: ALFWorld, LOCA-Bench, RCA-100 and ClinDiag × Qwen3.7-Plus, Kimi-K3 and GLM-5.3.
- Example (Qwen3.7-Plus): ALFWorld 88.81 vs 72.39 for the best baseline; RCA-100 38.83 vs 28.16.
- The cost is about 5.06× total tokens on RCA-100.

The system is strongly present-centric. The belief is overwritten in place, with no time fields on its records. Past beliefs survive only as per-step logs, which are exported for analysis and read internally by the trapping detector. Nothing does forecasting, branching or replay.

CORE STATE: A task-conditioned structured belief, BeliefState(world, goal, epistemic_gaps, achievement_gaps, frontier, health, belief_text, step). Sources: belief/beliefStates.py:104; docs/method.md:19.

World records (belief/worldStates.py):
- Entity(entity_id, entity_type, name, scalar attributes).
- State(state_id, entity_id, description, probability, reason, source_type ∈ {observed, inferred}).
- Relation(relation_id, source_id, target_id, description, probability, reason, source_type).
- Observed records are forced to probability 1 with no reason. Inferred records carry a probability below 1 and a reason. Confidences are independent and not normalized (docs/examples.md:43).

Goal and gaps:
- Goal(user_input, specification) is "Fixed goal G" (beliefStates.py:15).
- EpistemicGap(target, reason) is "information that remains unknown or unverified".
- AchievementGap(target, reason) is "an unresolved difference between the current and desired world".
- GapFrontier(gap_type, target) points to the single prioritized gap, the paper's Active Gap.

Other parts:
- belief_text is an LLM-generated textual projection given to the policy. The structured world is "the source of truth" (beliefStates.py:3).
- Runtime bookkeeping includes BeliefHealth (persistence, stagnation, recurrence, health score, trapping pattern) and RecoveryDirective (temporary constraints with start step).

Records have no timestamps, validity intervals or evidence-step pointers. "Provenance" in code is only source_type plus a free-text reason.

BRANCHING/REVISIT: There is no branching.
- Actions are executed in the real benchmark environment.
- The only uncommitted alternatives are candidate belief updates. They are built on a deep copy and either committed or discarded (validated, repaired or rejected). This is a transactional single-timeline commit, not a fork.

"Revisiting" happens in only two ways.
- **Sentinel audits.** They re-read raw evidence: the last 4 transitions, or the full trajectory every 8th update. Even the global audit is told to judge only changed records.
- **The trapping detector.** It compares the last K=8 committed belief snapshots with each other. It projects them all onto the current Active Gap and computes recurrence at lags 1-4. For Cycle recovery, it inserts the matched world_before/world_after snapshots into the constraint text.

PoS has no way to reopen or revise an earlier belief as of its own time, to restore one, or to restart from one. History is per-episode and is cleared on reset.

PRESERVED VS LOST: **Preserved within an episode** (in memory, exported to result.json and events.jsonl):
- raw_trajectory: an append-only list of every action and observation.
- belief_update_history: the candidate and final serialized belief per step, with status.
- belief_snapshots: world, gap identities and frontier per committed step.
- frontier_history, health_transitions with progress labels and reasons, health_history, and recovery_history (start step, status, instruction).
- Sentinel audit_history and progress_history.
- Every model input and output.

I confirmed with a probe that after "Mug 1 is dirty" was replaced by "Mug 1 is clean", the step-0 entry in belief_update_history still holds "dirty". The current belief holds only "clean".

**Lost or overwritten:**
- The live belief is overwritten in place. Records are upserted or deleted by ID, have no time or validity fields, and resolved gaps simply disappear.
- The policy never sees raw history or past beliefs.
- The belief prompt says "Keep only goal-relevant facts", so information judged irrelevant to the current goal is dropped from the decision context.
- Raw observations shown to the Sentinel are truncated to 6000 characters in the audit copy; the stored list keeps them whole.
- Everything is cleared at reset, so nothing persists across episodes or tasks.

BELIEF STATE: This is the system's central contribution, and it is fully explicit and structured.

What the belief holds:
- The current world estimate (Entity/State/Relation), with per-record confidence (probability), observed/inferred status and reason.
- Open questions as epistemic gaps.
- Unresolved requirements as achievement gaps.
- A single prioritized Active Gap.
- Assumptions are inferred records, with probability below 1 and a reason.
- In diagnostic mode, competing hypotheses are kept as inferred records with independent confidences. The prompt says: "preserve competing hypotheses not addressed by the test".

How consistency is maintained: every candidate update is audited by the Sentinel for internal contradictions (for example, the microwave both open and closed) and for external contradictions with observations. An issue must quote verbatim evidence from a cited step. It gets one repair; if that fails, the update is rejected.

Limits:
- The epistemic state is strictly "now". It has no notion of when something became believed, no valid-time or transaction-time, and no as-of queries.
- Earlier beliefs can be reconstructed only after the fact, from the step-indexed exported logs.
- The goal is fixed per episode.
- Confidence calibration is not evaluated. The secondary summary notes this; I could not check it in the paper.

FUTURE: There is essentially none.
- PoS has no world model, rollout, imagined future states, forecasts, or probability over futures.

Forward-looking elements are limited to three things:
- **Achievement gaps.** They are the discrepancy between the goal specification and the current belief, which is the remaining work.
- **The action-selection contract.** "Choose an action that directly resolves or narrows the Active Gap; use a prerequisite action only when a required argument … is still unknown."
- **Recovery constraints.** They are reactive. They are derived from past stagnation and recurrence, not from simulating consequences.

Progress labels are retrospective judgments of realized transitions, not predictions.

EVALUATION: **Benchmarks** (repo docs/reproduction.md):
- ALFWorld: 134 valid-unseen tasks, task success, 50 actions.
- LOCA-Bench: 525 cases = 15 families × 5 seeds × 7 context lengths from 8K to 256K, pooled success, 100 MCP tool calls.
- RCA-100: 103 microservice root-cause cases, joint fault-type and entity accuracy, 50 turns × up to 3 actions.
- ClinDiag: a fixed balanced 604-case subset with Emergency excluded, diagnosis accuracy, 30 tool calls. Its environment provider and judge are fixed to Qwen3.7-Plus.

**Backbones:** Qwen3.7-Plus, Kimi-K3, GLM-5.3. The same backbone is used for the policy, belief and Sentinel roles. Temperature is 0, and no model snapshots are pinned.

**Baselines:** Raw Trajectory (ReAct), ACON, PACE, HiAgent, LongHorizon-Harness.

**Table 1, Qwen3.7-Plus**, as transcribed by the authors in repo docs/results.md and project page data. Order is ALFWorld / LOCA / RCA / ClinDiag:

| Method | ALFWorld | LOCA | RCA | ClinDiag |
|---|---|---|---|---|
| Raw | 62.69 | 43.62 | 24.27 | 38.91 |
| ACON | 66.42 | 49.90 | 27.18 | 39.74 |
| PACE | 67.91 | 17.33 | 28.16 | 41.89 |
| HiAgent | 66.42 | 24.57 | 28.16 | 40.07 |
| LH-Harness | 72.39 | 52.57 | 26.21 | 40.56 |
| **PoS** | **88.81** | **56.38** | **38.83** | **45.03** |
| w/o consistency | 73.88 | 44.57 | 31.07 | 44.54 |
| w/o trapping | 73.13 | 48.19 | 33.98 | 42.38 |

**Other backbones:**
- Kimi-K3: PoS 94.03 / 74.29 / 51.46 / 54.80.
- GLM-5.3: PoS 97.01 / 70.86 / 49.51 / 52.15.
- PoS is best in all 12 settings. The largest relative gains over the best baseline are 22.68% on ALFWorld and 37.89% on RCA-100.

**Ablations:** removing either consistency validation or trapping diagnosis lowers the overall metric in every setting.

**Generic vs factorized recovery** (Qwen3.7-Plus, final outcomes over all cases):

| Benchmark | Generic | Factorized |
|---|---|---|
| ALFWorld | 76.87 | 88.81 |
| LOCA | 49.33 | 56.38 |
| RCA | 31.07 | 38.83 |
| ClinDiag | 42.22 | 45.03 |

**Compute** (Table 2, RCA-100/Qwen3.7-Plus, mean per episode over 103 cases):
- Task-agent tokens: 281.20K for PoS vs 355.70K for Raw.
- Total tokens: 1,800.13K for PoS vs 355.70K for Raw (5.06×).

**Context scaling:** at 256K on LOCA, PoS is +10.67 to +16.00 points over the strongest baseline across the three backbones.

**Caveats:**
- Comparisons match action budgets, not compute.
- No variance or confidence intervals are reported (per the secondary summary).
- Only PoS, Raw and the two ablations are released, and no historical outputs are bundled.
- The repo states that the release validation ran no paid or benchmark runs.

I ran the offline tests myself (behavior self-test passed; check_method 28/28 OK). They use mock models, so they verify mechanics only, not results.

DOES NOT COVER: - **Time is not an addressable dimension of state.**
  - Beliefs are overwritten in place, with no valid-time or transaction-time.
  - There is no state_at(t), diff or as-of query for the agent.
  - Past beliefs are never shown to the policy.
  - History is per-episode and cleared on reset.
- **No strict epistemic-cutoff interrogation of past states.** The one internal use of history projects past worlds through the current Active Gap, which is a present-lens comparison.
- **No separation of "what was true then", "known then" and "known now about then".**
- **No forks, replay or execution checkpoints, and no "never overwrite time, fork it".**
- **No counterfactual action exploration.**
- **No future simulation**, including multiple prospective branches, probabilities over futures, and feared futures.
- **No intervention-aware forecasts, no preserved prevented forecasts, and no predicted-vs-realized calibration.**
- **No identity, objective or model change tracking.** The goal is fixed.

In thesis terms, PoS argues the opposite direction from the North Star. Its claim is that agents need a better present (a validated current belief) rather than better access to the past ("beyond history retention and compression").

RELATION TO smoke_v1: In smoke_v1, a later event changes the significance of an earlier world-authored decision (an ADR or ticket). The agent must notice this, reopen the decision with evidence, state what was true then, known then, and known now about then, and fix the code.

**What PoS mechanisms would plausibly help:**
- An explicit current belief with inferred facts, confidences and reasons, plus open questions (epistemic gaps) and outstanding work (achievement gaps). A later event that contradicts a current belief record should trigger "replace contradicted facts".
- The global Sentinel audit re-reads the full raw trajectory every 8 updates.

**What PoS does not provide for this task:**
- No first-class notion of past decisions as objects that can be reopened.
- No record of when or why a belief was adopted, beyond a free-text reason with no evidence pointer.
- No way to answer "known then" vs "known now about then". The step-indexed belief_update_history could support this after the fact, but the agent cannot query it.
- The belief prompt keeps "only goal-relevant facts". An ADR rationale that seems irrelevant when first ingested could be omitted from the belief, and the PoS policy never sees raw history to recover it (my inference from the code, not tested).
- Sentinel audits judge only changed records. An unchanged earlier belief would not be re-examined unless an update touches it (my inference from the prompt and code).
- PoS is episode-scoped and was evaluated on single-episode tasks (ALFWorld, LOCA, RCA, ClinDiag). There is no cross-session memory.
- Trapping detection targets "acting without progress", which smoke_v1 does not stress.

**Implications for smoke_v1:**
- **Stronger baseline.** PoS is a credible additional baseline component: an explicit belief plus gaps layered over the existing event log, RAG and checkpoints. It is evidence that a strong "present-belief" baseline can beat history-centric memory. If smoke_v1 does not include such an arm, a skeptic could attribute any temporal-contestant win to "having an explicit state" rather than "having time".
- **Overlap.** PoS does not overlap smoke_v1's core distinctive targets: historical epistemic reconstruction with cutoff, reopening past decisions, and then/now distinctions.

VERIFIER STRONGEST THREAT: PoS is strong, recent (2026-10) evidence that the main win for long-horizon agents comes from an explicit, validated PRESENT belief state, not from better access to the past. Its belief holds confidences, observed/inferred tags, explicit open questions and obligations, and evidence-grounded revision with a 'replace contradicted facts' rule plus a periodic global audit against the full raw trajectory. It beats history-centric memory (ACON, HiAgent, LongHorizon-Harness) in all 12 settings, by up to 16 points. This threatens the project in three ways. (1) Confound: if smoke_v1's baseline (event log + checkpoints + RAG + rolling summary) has no explicit structured belief arm, any temporal-contestant win can be attributed to 'having explicit state' rather than 'having time'. PoS supplies a ready-made, published alternative explanation for the result. (2) Thin increment: PoS already writes a no-hindsight, step-indexed log of every committed belief (belief_update_history, belief_snapshots), which is the raw material for 'what was known then'. It already computes cross-time comparisons over those snapshots to change policy (trapping detection, Cycle recovery). A skeptic can frame 'historical epistemic state with cutoff' as exposing an existing log through a state_at(t) tool, i.e. an engineering add-on to PoS, not a new hypothesis. (3) Mechanism overlap with smoke_v1's core task: a later event that contradicts an earlier belief is exactly what PoS's contradiction-replacement plus global audit handles. If smoke_v1 can be solved by 'notice the contradiction in the current belief and fix the code', without needing the then/now distinction, it does not isolate the temporal hypothesis. The project's remaining distinct ground is forecasting, interventions, prevented futures, forks with provenance, and agent-facing then/now queries. PoS covers none of these, but the project must show that smoke_v1 actually requires them.

VERIFIER CORRECTIONS: Probe claim 'the step-0 entry in belief_update_history still holds "dirty"' is mislabelled. The probe prints belief_update_history[0], which is the step -1 (initialization) entry: 'HISTORY steps/status: [(-1, validated), (0, validated)] / HISTORY[0] final s1: Mug 1 is dirty.' The substance (earlier beliefs survive in logs) holds. | 'Global audit every 8th update' is not universal. ALFWorld, RCA100 and ClinDiag use global_audit_every_steps: 8, but LOCA uses 32 (configs/loca/pos.yaml:59). | events.jsonl is append-only only within one case run. Logger opens the file with mode 'w' (utils/logger.py:18), and main.py:655 creates a new Logger for every non-skipped case, so a re-run truncates the prior log. | The analyst's 'Sentinel audits judge only changed records' is confirmed verbatim (beliefSentinel_prompt.py:9-10). No correction needed; listed here because it is load-bearing for the smoke_v1 analysis.

UNVERIFIED: Neither I nor the original analyst could read the paper body. arXiv is blocked, and the WebSearch budget was exhausted on my first call. §3 equations, Algorithm 1, Related Work, Appendix G limitations and Tables 2-9 remain unverified. The only verbatim paper sources are the abstract and the section headers and figure captions (pos_src scrapes). Table numbers are author transcriptions in the repo and project page, not checked against the PDF. Whether the released code matches the code behind the paper's runs is unknown: the repo states no paid or benchmark runs were done for release validation. Two ratings are borderline: cross_time_state_querying (partial vs no) and backward_requirements (partial). Verification notes: /tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/lit/verify/pos.md

VERIFIED RATINGS:
- 1 immutable_historical_observations: yes -- raw_trajectory is only appended to during an episode (manager.py:237-247) and exported. Scope caveat: reset() replaces it per episode (manager.py:161-170). events.jsonl is opened with mode 'w' (utils/logger.py:18), so re-running a case truncates the earlier log; it is append-only only within one run
- 2 historical_world_state: no -- Snapshots hold the agent's belief W_t, not the environment state. No environment snapshot or reconstruction exists. Raw observations are kept but are not a world-state reconstruction.
- 3 historical_epistemic_state: partial -- belief_update_history (manager.py:587-611) and belief_snapshots (741-762) are written at commit time, so they contain no hindsight. Re-running the probe confirmed an earlier belief ('Mug 1 is dirty') survives after the live belief changed. Correction: it survives in the step -1 (initialization) entr
- 4 historical_policy_objective_state: partial -- frontier_history records each Active Gap change with its step, and recovery_history records the constraint directives with started_at_step and applies_from_step. The goal is fixed ('Fixed goal G'), and there is no versioning of model or instructions in agent state.
- 5 execution_checkpoints: no -- skip_existing reuses completed case results only (main.py:620-640). Candidate deepcopy plus reject-to-base is commit control, not a restorable snapshot.
- 6 replay: no -- There is no re-run from a historical point. scripts/check_behavior_equivalence.py is a mock regression harness.
- 7 fork_from_historical_state: no -- There is one timeline per episode and the belief is replaced in place (manager.py:306). Grep finds no fork, branch or restore code.
- 8 counterfactual_action_branches: no -- Actions execute directly in the env (baselines/react.py:73-82). The only uncommitted alternatives are belief candidates.
- 9 branch_provenance: no -- There are no branches. Update status (validated/repaired/rejected) and Sentinel evidence_step/quote are update provenance only.
- 10 explicit_current_belief_state: yes -- B_t=(W_t,G,Delta_E,Delta_A), with 'Structured belief is the source of truth'. It is the only decision context: the policy prompt omits history.
- 11 uncertainty_representation: yes -- Records carry probability, reason and source_type (observed/inferred); epistemic gaps hold unknowns; pending_issues holds unresolved Sentinel issues. Calibration is not evaluated.
- 12 future_state_rollout: no -- Grep for predict, forecast, simulat, lookahead, imagin and rollout finds no mechanism. The progress judge's 'plausible path to the Goal' (beliefSentinel_prompt.py:17-18) is a retrospective label, not a rollout.
- 13 multiple_prospective_branches: no -- Competing diagnostic hypotheses (prompt_generation.py:87-89) are explanations of the present, not futures.
- 14 probability_over_futures: no -- Probabilities attach only to current State and Relation records.
- 15 backward_requirements: partial -- Achievement gaps are 'An unresolved difference between the current and desired world', derived from goal_specification. This is single-level and regenerated by the LLM at each update. There are no feared futures and no precondition chains. The rating is borderline but defensible.
- 16 intervention_aware_forecasting: no -- There are no forecasts.
- 17 prevented_futures_preserved: no -- There are no forecasts. Resolved gaps are removed from the live belief.
- 18 predicted_vs_realized: no -- The Sentinel checks beliefs against observations, and the progress judge labels realized transitions. No prior prediction is recorded or compared.
- 19 cross_time_state_querying: partial -- Internally, snapshots_by_step[step] is a state_at(step) lookup and _world_distance/_projection_distance are pairwise diffs that drive the trapping and Cycle-recovery logic. None is exposed as a query to the agent, and past worlds are projected through the current Active Gap. A strict reading of 'fir
- 20 unified_temporal_abstraction: no -- The system has a present belief plus step-indexed logs, and no counterfactual or prospective states.

## graphiti: Zep: A Temporal Knowledge Graph Architecture for Agent Memory (arXiv:2501.13956), and its open-source engine Graphiti (getzep/graphiti, v0.30.2, commit 3c427640, 2026-09-30)
Preston Rasmussen, Pavlo Paliychuk, Travis Beauvais, Jack Ryan and Daniel Chalef. Submitted 20 Jan 2025 (from the arXiv abstract-page screenshot shipped in the repo at images/arxiv-screenshot.png). The affiliation line in the paper was not seen. The code is "Copyright 2024, Zep Software, Inc." (license headers).

Sources: https://github.com/getzep/graphiti (git clone --depth 1 (HEAD 3c427640abf909f12f71f963fce15eb514a3c493, 2026-09-30, version 0.30.2). Read edges.py, nodes.py); https://arxiv.org/abs/2501.13956 (Abstract only, read verbatim from images/arxiv-screenshot.png in the cloned repo. The paper body was NOT obtained: the s); file:///tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/lit/graphiti_filter_probe.py (My own script. It executes graphiti_core/search/search_filters.py in isolation (stubbed imports) to show the Cypher it g)

SUMMARY: Graphiti is an LLM-driven pipeline that builds a temporal knowledge graph incrementally. Raw inputs ("episodes") are turned into entity nodes and fact edges, and each fact edge carries four timestamps:
- valid time: valid_at / invalid_at, extracted by an LLM relative to the episode's reference_time;
- transaction time: created_at / expired_at, stamped from the wall clock.

When a new fact contradicts an existing one (an LLM judges this over top-k hybrid-search candidates), the old edge is invalidated by setting invalid_at and expired_at on the same record. The edge is not deleted. Facts link back to the episode UUIDs that produced or re-mentioned them.

Edge search accepts DNF date filters on all four timestamps, so a bitemporal "as of t" filter on facts can be expressed. However:
- default retrieval applies no validity filter (invalidated facts are returned and the LLM is told to read the dates);
- nodes and episodes have no time filtering in search;
- rows are mutated in place (MERGE/SET), so there are no versioned revisions.

The schema has no agent beliefs, decisions, goals, uncertainty, branches, forecasts or execution state. It is a bitemporal-ish world-fact memory, not an agent-state time machine. Abstract claims (not verified in the paper body): 94.8% vs 93.4% for MemGPT on DMR, and up to 18.5% accuracy gain with 90% lower latency on LongMemEval.

CORE STATE: A property graph partitioned by group_id.
- EpisodicNode: raw content, source, created_at (ingest wall-clock), valid_at (= caller's reference_time), and the list of entity_edges it touched (nodes.py:318-331).
- EntityNode: name, embedding, a mutable summary, attributes and created_at; no validity fields (nodes.py:499-504).
- EntityEdge (a "fact"): name, fact text, embedding, episodes[] provenance list, created_at, expired_at, valid_at, invalid_at, reference_time and attributes (edges.py:263-285).
- Episodic MENTIONS edges, communities, and sagas (ordered episode chains with HAS_EPISODE / NEXT_EPISODE edges).
State is persisted by in-place upsert (MERGE ... SET e = $edge_data, edge_db_queries.py:69-70; SET n = $entity_data, node_db_queries.py:144-146).

BRANCHING/REVISIT: There is no branching. The graph is a single mutable timeline per group_id.
- driver.clone(database=...) only rebinds the connection (driver/driver.py:131-133), and no API copies or forks a partition.
- Revisiting is query-only: date filters on edge search, and retrieve_episodes(reference_time).
- Late-arriving or backdated episodes are reconciled on the valid-time axis: a new edge is expired immediately if the graph already holds a later contradicting fact (edge_operations.py:826-839).
- Re-processing an existing episode uuid re-runs extraction and overwrites its entity_edges list (graphiti.py:1160-1170, 748-749).

PRESERVED VS LOST: Preserved:
- Raw episode content by default (store_raw_episode_content=True, graphiti.py:146).
- Superseded facts, kept as edges with invalid_at/expired_at rather than deleted (README.md:119-120; graphiti.py:1215).
- Episode-level provenance lists on edges (edges.py:267-270).

Lost or overwritten:
- Edges are upserted in place, so each edge holds only its latest invalid_at and attributes. An earlier invalid_at can be overwritten by a later contradiction while expired_at keeps its first value (edge_operations.py:569-570). Attributes are replaced or cleared (edge_operations.py:800-809).
- Entity summaries and attributes are rewritten with no history (node_operations.py:873-881; node_db_queries.py:144-146).
- Communities are deleted and rebuilt (graphiti.py:1563).
- Episode content is blanked when store_raw_episode_content=False (graphiti.py:750-751).
- Hard deletes via remove_episode, delete_entity_edge and clear_graph.
- The mention-level support history on an edge (when each episode was appended) is not timestamped.
- Transaction times are wall-clock utc_now() and cannot be injected (datetime_utils.py:20-22; edge_operations.py:306,570,820).

BELIEF STATE: Only world facts as extracted triples, plus raw episodes. There is no type or field for agent beliefs, assumptions, decisions, plans, goals, confidence or uncertainty: greps for confidence/uncertain/belief/decision/forecast/predict find nothing relevant.

The agent's own utterances can be ingested as message episodes; the langgraph example ingests "SalesBot: <response>", examples/langgraph-agent/agent.ipynb cell 20. The speaker is then extracted as an entity (prompts/extract_nodes.py:130), so the agent's statements become generic facts, not marked as beliefs.

"What the graph contained at t" can be approximated for edges with created_at <= t AND (expired_at > t OR NULL), but:
- invalid_at values on returned rows reflect later knowledge (hindsight leakage unless the caller masks them);
- node summaries cannot be reconstructed as of t;
- the MCP surface exposes only valid-time filters, not created_at/expired_at.

FUTURE: None. No forecasting, rollout, simulation, imagined branches or goal regression. Future-dated valid_at values could be stored if an episode states them, but nothing treats them as predictions.

EVALUATION: Paper abstract only (verbatim from the repo screenshot):
- DMR: "Zep demonstrates superior performance (94.8% vs 93.4%)" against MemGPT.
- LongMemEval: "accuracy improvements of up to 18.5% while simultaneously reducing response latency by 90% compared to baseline implementations", with gains "particularly pronounced in ... cross-session information synthesis and long-term context maintenance".
- Paper is "12 pages, 3 tables".

Per-category tables, models, baselines and the evaluation protocol could not be verified because the paper body was not obtained. The repo has unit and integration tests for filters and dedup (for example tests/test_graphiti_mock.py:974-1013), but no temporal-reasoning benchmark of the as-of filters.

DOES NOT COVER: - The agent's own epistemic state, decisions and assumptions as first-class versioned state. A strict no-hindsight cutoff is not enforced: returned rows carry later-learned invalid_at, and nodes and summaries are unversioned.
- Identity, objective and policy tracking.
- Execution checkpoints, replay, forking and branches with provenance ("fork, don't overwrite"). Rows are upserted in place.
- Simulation of future states, multiple prospective branches, probabilities, and backward requirements from desired or feared futures.
- Intervention-aware forecasts, preservation of prevented forecasts, and predicted-vs-realized comparison.
- A unified abstraction over historical, actual, counterfactual and prospective states.
- Detecting that a later event changes the significance of an earlier decision that is still true. Invalidation triggers only on LLM-judged contradiction between facts with known valid_at.

RELATION TO smoke_v1: Graphiti is essentially "hybrid RAG + temporal fact graph". It is therefore relevant prior art for the baseline side, and arguably a stronger memory component than plain hybrid RAG for the smoke_v1 sub-question "state what was true then / known then / known now about then":
- valid-time filter on the current graph = "what was true then, as known now";
- created_at/expired_at filter = an approximation of "what was known then";
- episode provenance = evidence pointers.

It does not address the core smoke_v1 behavior. In smoke_v1 a later event changes the significance of an earlier world-authored decision (ADR or ticket) whose own facts stay true. Graphiti's only automatic temporal mechanism is contradiction-driven invalidation, so it would usually leave the ADR fact valid and flag nothing. It also has no notion of reopening a decision, remediation, or the agent's decision-time assumptions.

Practical caveats if Graphiti were used in the benchmark:
- Transaction timestamps are wall-clock and cannot be injected, so scenario-clock as-of queries need a mapping from event index to wall-clock time.
- Default search returns invalidated facts.
- Ingestion is LLM-driven and nondeterministic, which conflicts with the project's preference for deterministic infrastructure.

To keep the comparison fair (CLAUDE.md rule 4), a Graphiti-style bitemporal fact store, or its as-of filters, could be considered as an optional baseline-strengthening memory. The thesis remains distinct mainly on agent-state versioning, forks and the prospective/forecast parts, not on bitemporal world facts.

VERIFIER STRONGEST THREAT: Graphiti/Zep already ships, as a widely used open-source agent-memory product, the past-facing half of the thesis: 'invalidate, don't delete'; a two-axis (valid-time vs transaction-time) record that separates 'what was true then' from 'when the system learned it'; provenance from every derived fact back to raw episodes; valid-time reconciliation of backdated information; and typed, provenance-linked memory of the requirements and procedures that govern a coding agent, with agent rules to consult them before each task. smoke_v1's 'what was true then / known then / known now about then' sub-question can therefore largely be answered by a strong baseline built on bitemporal fact memory, so the project cannot claim that historical or epistemic time-addressability of facts is novel. If the baseline is not given a Graphiti-style bitemporal store, any win can be attributed to a weak baseline (violating CLAUDE.md rule 4).

The residual distinct hypothesis must rest on what Graphiti demonstrably lacks:
- versioned agent decision-time assumptions with a no-hindsight cutoff (Graphiti leaks later invalid_at values and does not version nodes);
- detecting that a still-true earlier decision has changed significance (Graphiti acts only on fact contradiction);
- forks and branches with provenance;
- prospective, intervention-aware forecasts, prevented futures, and predicted-vs-realized calibration.

VERIFIER CORRECTIONS: historical_policy_objective_state 'no' is deflated, corrected to partial. The shipped MCP server enables by default a Procedure entity type ('A Procedure informing the agent what actions to take', entity_types.py:46-47), plus Requirement and Preference (config.yaml:96-102). Its cursor_rules.md:5,22 tells the agent to search procedures before every task and follow them exactly. Instructions governing the agent are therefore stored as typed, provenance-linked memory with validity-windowed facts, not merely as 'generic facts'. | The claim that there is 'no type or field for agent beliefs, assumptions, decisions, plans, goals' is overstated. Requirements and procedures are typed entities in the MCP defaults. Saga summaries are prompted to capture 'Decisions and their outcomes' and 'Plans, next steps, and commitments' (prompts/summarize_sagas.py:87-89), though as overwritten prose (graphiti.py:559). The claim holds only for graphiti_core's built-in schema. | Minor addition, not a refutation: the REST server's retrieve endpoint hard-codes reference_time=datetime.now (server/graph_service/routers/retrieve.py:39), and MCP get_episodes has no time parameter. As-of access to episodes therefore exists only via the Python API.

UNVERIFIED: The Zep paper body is still unread. The WebSearch budget is exhausted (200/200) and arxiv is blocked, so these remain unverified: whether the paper formalises the T/T' bitemporal timelines; whether it describes as-of retrieval; the LongMemEval per-category results (notably temporal-reasoning and knowledge-update categories), models and baselines; and the stated limitations. Managed Zep (proprietary) may offer versioning or transaction-time as-of queries beyond OSS Graphiti, and this cannot be checked. Runtime behavior was not exercised against a real graph DB; only the pure filter constructor was executed. It is also unverified whether the shared search-config limit mutation affects ingestion in practice.

VERIFIED RATINGS:
- 1 immutable_historical_observations: partial -- Confirmed. Raw episodes are stored and superseded facts are invalidated rather than deleted. But every write is MERGE+SET upsert, remove_episode hard-deletes, and store_raw_episode_content=False blanks content.
- 2 historical_world_state: partial -- Confirmed. A valid-time as-of filter on edges is expressible: the re-executed probe on the real search_filters.py emits valid_at<=t AND (invalid_at>t OR NULL). retrieve_episodes(reference_time) gives a valid-time cutoff on episodes. There is no materialized state_at(t), and entity summaries and attr
- 3 historical_epistemic_state: partial -- Confirmed. created_at/expired_at come from the wall clock (utc_now) and give an approximate 'what the graph held at t'. Hindsight leaks because invalid_at is overwritten in place (edge_operations.py:569-570). Nodes are unversioned. Ingestion extraction context is cut off by reference_time, but dedup
- 4 historical_policy_objective_state: partial -- Deflated by the analyst. The shipped MCP server enables, by default, typed entities for instructions governing the agent: Procedure ("A Procedure informing the agent what actions to take or how to perform in certain scenarios"), Requirement and Preference. Its agent rules tell the agent to search th
- 5 execution_checkpoints: no -- Confirmed. It is a memory store with no snapshot or restore of agent runtime.
- 6 replay: no -- Confirmed. There is no replay API, only manual re-ingestion.
- 7 fork_from_historical_state: no -- Confirmed. driver.clone returns self in the base class ('Clone the driver with a different database or graph name. return self'). There is no partition copy.
- 8 counterfactual_action_branches: no -- Confirmed. No sandbox or hypothetical writes.
- 9 branch_provenance: no -- Confirmed. Only fact-to-episode provenance (EntityEdge.episodes) exists, and there are no branches.
- 10 explicit_current_belief_state: partial -- Rating holds but the evidence is corrected. It is not only world facts: the MCP defaults type Requirement, Preference and Procedure entities, and saga summaries are prompted to capture 'Decisions and their outcomes' and 'Plans, next steps, and commitments'. Still partial: those summaries are overwri
- 11 uncertainty_representation: no -- Confirmed. The only hits are the GLiNER2 extraction-confidence option, Gemini safety probabilities and name-entropy dedup helpers. None is an uncertainty representation in memory state. A null valid_at renders as 'date unknown'.
- 12 future_state_rollout: no -- Confirmed. No simulation component.
- 13 multiple_prospective_branches: no -- Confirmed.
- 14 probability_over_futures: no -- Confirmed.
- 15 backward_requirements: no -- Confirmed. Requirement entities are extracted from text, not derived from future states.
- 16 intervention_aware_forecasting: no -- Confirmed. No forecasting.
- 17 prevented_futures_preserved: no -- Confirmed. Invalidated edges are superseded past facts, not prevented forecasts.
- 18 predicted_vs_realized: no -- Confirmed.
- 19 cross_time_state_querying: partial -- Confirmed. DNF date filters cover all four edge timestamps; the probe re-executed. There is no state_at or diff primitive, and node and episode search are not time-filtered. The OR-group parameter collision is confirmed: params are keyed by inner index j only. The MCP surface offers valid-time range
- 20 unified_temporal_abstraction: no -- Confirmed. The bitemporal edge spans only historical and current facts.

## countermem: COUNTERMEM: World-Model Verified Counter-Factual Memory for Language Agents (arXiv:2609.31874v1)
Hongji Pu, Ruixiang Tang, Yongfeng Zhang. Affiliations are not in any source I obtained (unclear). Submitted 2026-09-25T18:12:38Z and announced 2026-09-29, v1, category cs.AI. The arXiv comment reads "25 Pages, 8 Figures, ICLR 2027". Acceptance status is unclear; the abstract says "Code will be released upon acceptance".

Sources: https://arxiv.org/abs/2609.31874 (Canonical page, cited by every mirror. Not fetched: the host is blocked. WebSearch was also unavailable; the first call ); https://raw.githubusercontent.com/xiaoqixiaowei/daily-arxiv-ai/14963ab30b567e039c656dea1ce2e39a39f9a0a7/data/2026-09-29.jsonl (Found by GitHub MCP code search for "2609.31874", then curl at a pinned commit. Line 14 holds the verbatim abstract plus); https://raw.githubusercontent.com/angelababyhuang/013-ai-knowledge-base/ca7bf149523c308a7d67f38548b8838dbd1ac3fe/knowledge/raw/rss-2026-09-29.json (GitHub code search, then curl. An arXiv cs.AI RSS item oai:arXiv.org:2609.31874v1 with the verbatim abstract in summary_); https://raw.githubusercontent.com/xiaoqianran/web-001-Blog/8809ac57053ae41e01dd0bec533febdf30c5b2e8/content/data/rss-feeds/2026-09-29.json (GitHub code search, then curl. The same RSS item with the verbatim abstract. After whitespace normalization, all 4 mirro); https://raw.githubusercontent.com/flybfree/AI-Wiki/HEAD/raw/papers/2026-09-25_18-12-38Z_COUNTERMEM_World_ModelVerifiedCounter_FactualMemor.md (GitHub code search for "verified counterfactual memory", then curl. An arXiv-API-derived copy: verbatim abstract, publis); https://raw.githubusercontent.com/IAAR-Shanghai/Awesome-AI-Memory/13ac6e97cc829854cc15fc17e665134be8e034e8/screening/2026-09-30-review.json (GitHub code search, then curl. A curated-list screening record with reading_scope "abstract", so the curators also read ); https://raw.githubusercontent.com/waitfor-night/textworld-social-simulation-research/5655014a90dcdb128207059dfe807888faab70b7/papers/2609.31874.md (GitHub code search, then curl. A third-party paper card. It states no confirmed public repo; its limitations line is the); https://raw.githubusercontent.com/wdndev/wdndev.github.io/4506878506b87c3d412ebc621068c00091cd33f7/daily/domain/202609/2026-09-30/index.html (GitHub code search, then curl. Abstract only; its full-text LLM analysis failed (Kimi HTTP 429).); https://github.com/DeltaLabTLV/CounterMem (git clone (commit 1b338c0c). This is a name collision and an unrelated paper: README.md:3-8 is 'CounterMem: Counterfactu)

SUMMARY: COUNTERMEM is an RL-trained memory framework for language agents. After one of the agent's actions fails, it restores the state before that action, by copy or reset, and tries local alternative actions there. Each alternative is checked by an "executable world model", meaning tests, proof checkers, or solvers. Only alternatives that improve on the original are stored, each as a record of the original action, the corrected action, the checked outcomes, and conditions for reuse.

A learned memory-use policy, also called the selector, is trained offline. For a new task it picks one retrieved record or skips memory, trading task success against interaction cost. The base LLM stays fixed, and memory and policy are frozen for held-out evaluation.

The paper reports, with gpt-oss-120b, gains for both ReAct and Reflexion on all 12 benchmark settings across 6 domains, averaging +12.6 percentage points over the unaugmented versions. In a four-domain comparison across two backbones, task-run tokens fall by 7.7-42.0%, excluding offline selector-training cost. Removing verification or persistent storage weakens the gains, and applying verified corrections to unsuitable decisions can reverse them.

Important caveat: all of this comes from the verbatim arXiv abstract, obtained from 4 identical GitHub-hosted mirrors. The paper body could not be accessed, and no code is public.

CORE STATE: The unit of memory is a verified counterfactual correction record: (original action, corrected action, checked outcomes, conditions for reuse). Abstract: "It stores improvements with the original and corrected actions, checked outcomes, and conditions for reuse."

Environment state matters only transiently, as "the original state" that is copied or reset so alternatives can be evaluated. The "world model" is an executable verifier (tests, proof checkers, solvers), not a learned or imagined dynamics model.

What the abstract leaves open:
- the record schema in detail, including whether state, observations, episode/task ids, or timestamps are stored;
- the retrieval index;
- whether factual and counterfactual memories share a store.

BRANCHING/REVISIT: Revisiting is local and retrospective. The only revisit point is the state just before a failed action. It is restored by copy (which preserves the original, giving fork semantics) or by reset (which may not preserve the live original; unclear). From there, local alternatives are evaluated off the active trajectory and checked by executable verifiers. The stated motive is to avoid altering "the state needed for comparison".

Branches are ephemeral evaluation sandboxes. Only improving alternatives survive as memory records, and the abstract describes no branch DAG or continuation of a branch.

Provenance is partial:
- Each record keeps the original action (factual) and the corrected action (counterfactual) with checked outcomes and reuse conditions.
- The abstract does not mention a parent state id, divergence time, episode id, or reason.
- Failed alternatives are apparently discarded.

Factual vs. counterfactual is distinguished by field inside a record. Whether there is a type label at store level is unclear.

PRESERVED VS LOST: Preserved, per the abstract:
- verified improvements as records: the original action, the corrected action, the checked outcomes, and the reuse conditions;
- the original state, preserved during evaluation when the copy mode is used;
- the learned selector policy.

Apparently lost or not described:
- non-improving or failed alternatives (only "improvements" are stored);
- raw trajectories and observations (no logging is mentioned);
- the full state at the decision point, which is not listed as stored;
- what the agent believed or knew at the time;
- any timestamps or lineage beyond the action pair.

Memory and policy are frozen at evaluation, so nothing new is preserved at test time.

The ablation "removing ... persistent storage weakens the gains" shows that cross-task persistence matters. The details of that ablation are unclear.

BELIEF STATE: The abstract describes no explicit belief or epistemic state. Memory is a library of correction records, not a maintained model of beliefs, assumptions, or requirements. Reuse "conditions" and the learned skip option handle applicability: when a past correction applies. That is not a represented belief or uncertainty.

Construction is explicitly hindsight-based: verifier outcomes are obtained after the failure. There is no mechanism for reconstructing what the agent knew at the time of the original action, and no knowledge cutoff.

FUTURE: There is no prospective forecasting in the abstract. The "world model" executes tests, proof checkers, or solvers on a copied or reset state to check what an alternative action would have produced. This is action-conditioned outcome computation, but it is retrospective (after a failure) and local. It is not imagination of the agent's own future trajectory, and it assigns no probabilities.

At test time, the frozen memory is retrieved and a record is selected or skipped. Whether verifiers or world models are queried at test time is unclear.

The abstract mentions no forecasts, no prevented futures, no predicted-vs-realized comparison, and no backward requirements.

EVALUATION: Claims from the abstract only:
- 12 benchmark settings across six domains, none of them named;
- base model gpt-oss-120b (a second backbone is used in the four-domain cost comparison and is not named);
- baselines are ReAct and Reflexion in their unaugmented versions, with COUNTERMEM added on top of each;
- result: improves both on all 12 benchmarks, averaging +12.6 percentage points;
- cost: task-run tokens fall 7.7-42.0% in the four-domain, two-backbone comparison, excluding offline selector-training costs (and, presumably, offline counterfactual construction);
- ablations: removing verification or persistent storage weakens the gains, and applying verified corrections to unsuitable decisions can reverse them;
- protocol: memory and policy are frozen during held-out evaluation.

Not available:
- per-benchmark numbers, variance or CIs;
- comparisons with other experience-memory methods;
- the domain list (code, proofs, and solvers are a plausible guess, inferred only from the verifier examples).

DOES NOT COVER: COUNTERMEM does not cover these parts of the thesis:
- Reconstructing what the agent believed or knew at t under a strict epistemic cutoff. Its construction is hindsight-based by design.
- Tracking identity, objective, policy, or model changes over time. The LLM is fixed, and memory and policy are frozen at evaluation.
- An explicit current belief or assumption state.
- Prospective simulation of the agent's own futures, multiple maintained futures, or probabilities over them.
- Backward requirements from desired or feared futures.
- Intervention-aware forecasting, preservation of prevented futures, and predicted-vs-realized calibration.
- First-class as-of or diff queries.
- A general branch DAG with full provenance (parent state, time, reason). Non-improving branches are apparently discarded.
- A unified temporal abstraction.
- Triggers other than the agent's own immediate failure. In particular, it does not handle a later external event changing the significance of an earlier decision.

RELATION TO smoke_v1: smoke_v1 asks the agent to notice that a later event reframes an earlier world-authored ADR or ticket, reopen it with evidence, state what was true then, known then, and known now, and remediate the code. COUNTERMEM is not designed for that.
- Its trigger is the agent's own failed action, flagged by an executable check at that moment, not a later event.
- It has no "known then vs. known now" representation.
- Memory is frozen at test time and reused across tasks, rather than reopening a specific historical artifact.

It is still relevant in two ways:
1. A COUNTERMEM-style component (verified correction records keyed by reuse conditions, with agent-visible tests as the "world model") is a legitimate way to strengthen the checkpoint+RAG baseline. That would keep the comparison honest (CLAUDE.md rule 4). It must use only tests visible to the agent, never the benchmark's hidden tests or ground truth (rule 3).
2. Its ablation, where corrections applied to unsuitable decisions reverse the gains, parallels smoke_v1's risk that an agent "remediates" a past decision that was sound given what was known then.

Threat level:
- moderate for the "counterfactual action branches with executable verification, persisted as memory" pillar;
- low for the epistemic-cutoff, prospective, prevented-future, and as-of pillars.

VERIFIER STRONGEST THREAT: COUNTERMEM is published prior art, with positive results, for a central temporal-agency move. The loop is:
1. Go back to an earlier decision point.
2. Fork the state rather than overwrite it, explicitly to avoid altering "the state needed for comparison".
3. Try alternative actions.
4. Verify them with executable tests.
5. Persist the factual and counterfactual pair as reusable memory.

The abstract reports +12.6 pp over ReAct and Reflexion on all 12 settings, with ablations showing that verification and persistence matter.

Remediation in smoke_v1 is test-checkable. A checkpoint+RAG baseline with a COUNTERMEM-style verifier loop could plausibly do the "reopen and remediate" half without explicit temporal navigation: the agent's own tests fail after the later event, then it retries alternatives on a copy and keeps the verified fix. That would shrink the project's distinct contribution to two things COUNTERMEM does not touch:
- the epistemic-cutoff statements (true then, known then, known now);
- the prospective, prevented-future, predicted-vs-realized, and as-of pillars.

The cleanest framing of "never overwrite time, fork it" for counterfactual repair is therefore not novel.

VERIFIER CORRECTIONS: The summary's "restores the state before that action" is an inference. The abstract says only "a copy or reset of the original state". | "RL trains the selector" is an inference from "reinforcement-learning framework" plus "offline selector-training costs". The analyst flagged it as such, correctly. | The source list omits several local files in lit/countermem/ (cgdeep, lodestar, tmokmss, zemyblue, innerca, angelababy_enriched). All are abstract-level or summary-only and add no method detail. | lit/countermem/lightrain_iclr_idea_factory.py is an unrelated idea-generator script. Its lines 522-531 hold an idea called 'Irreversible-Action Counterfactuals' that uses the phrase 'Verified counterfactual memory'. It must not be cited as COUNTERMEM evidence. | multiple_prospective_branches (partial) and future_state_rollout (partial) rest on the same sentence as counterfactual_action_branches. They should not be counted as independent prior art for the prospective pillar.

UNVERIFIED: All ratings rest on the 1768-char abstract only. WebSearch is exhausted (200/200), arxiv.org and alphaxiv are blocked, and no body text, PDF mirror, or code was found on GitHub. The following cannot be checked:
- whether "original state" includes the agent's context;
- whether non-improving alternatives or trajectory logs are stored;
- whether records carry ids or timestamps;
- whether verifiers or world models run at test time;
- the alternative generator, the record schema, and the RL details;
- the benchmark names and stronger memory baselines;
- venue status ("ICLR 2027" probably means a submission, not an acceptance).

Several "no" ratings (epistemic state, uncertainty, provenance depth) could move once the full text is read.

Verifier notes: /tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/lit/verify/countermem.md

VERIFIED RATINGS:
- 1 immutable_historical_observations: unclear -- A3: "It stores improvements with the original and corrected actions, checked outcomes, and conditions for reuse." These are derived, selective records. The abstract neither affirms nor denies an append-only trajectory log, and the paper body could not be read.
- 2 historical_world_state: partial -- A2: "evaluates local alternatives from a copy or reset of the original state". This restores the environment at one failure point, not arbitrary as-of-t. That "original state" means the state before the failed action is an inference, not a quote.
- 3 historical_epistemic_state: no -- Construction uses hindsight by design: alternatives are evaluated after the failure, and only verified improvements are kept. No belief reconstruction or knowledge cutoff is described. Caveat: if "original state" includes agent context, the context at t is restored implicitly, but no cutoff is state
- 4 historical_policy_objective_state: no -- "the base LLM remains fixed"; "Both memory and policy are frozen during held-out evaluation." No versioned record of policy or objectives is described.
- 5 execution_checkpoints: partial -- The environment state is copied or reset (A2) so as not to "alter the state needed for comparison" (A1). Whether the agent's runtime state is checkpointed is unknown.
- 6 replay: partial -- Alternatives are re-executed from the restored point. Nothing says the original trajectory is replayed or that runs are deterministic.
- 7 fork_from_historical_state: partial -- Running on a "copy ... of the original state" preserves the original "for comparison", which is fork semantics. The forks are ephemeral, local, and limited to one failure point. A reset may not preserve the live original.
- 8 counterfactual_action_branches: yes -- A2 states the paper's core directly: "After a failed action, COUNTERMEM evaluates local alternatives from a copy or reset of the original state using executable world models, such as tests, proof checkers, and solvers."
- 9 branch_provenance: partial -- A record keeps the original action, the corrected action, the checked outcomes, and the reuse conditions. No parent-state id, divergence time, episode id, or reason is described. Only improvements are stored.
- 10 explicit_current_belief_state: no -- Memory is a library of correction records chosen by a learned selector. No maintained structure of beliefs, assumptions, or requirements is described.
- 11 uncertainty_representation: unclear -- Reuse conditions and the learned option to "skip memory" handle applicability. No explicit confidence fields are mentioned, and the record schema is unread.
- 12 future_state_rollout: partial -- Executable world models compute action-conditioned outcomes on a copied state. This is retrospective verification, not forward imagination from the present. Whether it is used at test time is unknown, since memory and policy are frozen.
- 13 multiple_prospective_branches: partial -- Kept as a weak partial: several "local alternatives" from one state are compared with the original. It rests on the same sentence as #8 and #12, so it is not independent evidence. Nothing prospective from the present is described, and no set of alternatives is maintained (only improvements are store
- 14 probability_over_futures: no -- Outcomes are "checked" by execution. No likelihoods are mentioned anywhere in the pipeline description.
- 15 backward_requirements: no -- There is no goal regression. "conditions for reuse" are only applicability preconditions for a stored correction.
- 16 intervention_aware_forecasting: no -- No forecasts are described. Outcomes are conditioned on alternative actions but checked retrospectively, and there is no passive vs. policy-conditioned distinction.
- 17 prevented_futures_preserved: no -- There are no forecasts. Only improvements are stored.
- 18 predicted_vs_realized: no -- The system compares a factual outcome with a verified counterfactual outcome, not a prediction with a realization. The selector optimizes task success and cost.
- 19 cross_time_state_querying: no -- Reuse is "selects a retrieved record or skips memory". No as-of or diff queries are described.
- 20 unified_temporal_abstraction: no -- There is one record type for factual-plus-counterfactual action pairs. Nothing spans historical, actual, and prospective states.

## itp: Imagine-then-Plan: Agent Learning from Adaptive Lookahead with World Models (arXiv:2601.08955)
Authors: Youwei Liu, Jian Wang (corresponding, marked with a dagger), Hanlin Wang, Beichen Guo, Wenjie Li. These come from the README and CITATION.cff of github.com/loyiv/ITP and from the HF-papers JSON mirror. The affiliation is probably The Hong Kong Polytechnic University; I inferred that only from Wenjie Li's www4.comp.polyu.edu.hk homepage link, because the paper header could not be read. Dates: v1 published 2026-01-13 per HF metadata. The README says the paper was released on 2026-01-15 and the code on 2026-01-18. v3 was announced around 2026-09-04/05 as 'replace-cross' per arXiv RSS mirrors. Repo HEAD d1b55ed5 is dated 2026-09-29.

Sources: https://github.com/loyiv/ITP (Found with the GitHub MCP search_code query "Imagine-then-Plan". Cloned with git clone (HEAD d1b55ed5950901c3a0816e8a56e); https://github.com/loyiv/ITP/blob/main/figures/main_table.png (Image of the paper's Table 1 in the repo, viewed with the Read tool. I transcribed the numbers by hand.); https://github.com/loyiv/ITP/blob/main/figures/workflow.png (Image of the paper's method figure in the repo, viewed with the Read tool. It shows WM training on D_exp and D_roll, the); https://arxiv.org/abs/2601.08955 (NOT accessed directly: arxiv.org is blocked and the WebSearch budget was exhausted (200/200) on the first query. The v3 ); https://raw.githubusercontent.com/R1M1N/research_paper_explainer/main/zenith_output/papers/hf_2601.08955_Imagine-then-Plan__Agent_Learn.json (HF-papers metadata mirror fetched with curl: abstract, authors, published_at 2026-01-13.); https://raw.githubusercontent.com/memgrafter/research-digests/main/ml_research_analysis_2026/2601.08955_imagine-then-plan-agent-learning-from-adaptive-lookahead-with-world-models_20260210_090438.md (An LLM-generated secondary digest fetched with curl. Low trust. I used it only where the code or figures corroborate it )

SUMMARY: ITP gives an LLM agent a learned textual world model (WM). Before each real action, the agent imagines a K-step future, choosing K adaptively, and then acts on the current state plus that imagined future. The paper calls this a POIMDP: a 'partially observable and imaginable MDP'.

How the parts work in the released code:
- **World model:** an LLM fine-tuned (LoRA) on (state, action) → next_state text pairs taken from expert ALFWorld/ScienceWorld trajectories. The figure also shows policy-rollout data (D_roll), but no code in the repo generates it.
- **ITP-I (no training):** the policy LLM is prompted to output an integer K in [0, Kmax]. The WM then writes a single greedy K-step 'foresight' text, and the policy writes Reflection/Thought/Action with that text pasted into its prompt.
- **ITP-R (trained):** adds a linear K-head and a value head on the policy backbone. Training has three stages:
  1. Pseudo-label K for each expert step as argmax_k [log p(expert action | state, imagined obs at k) − λ·k]. The imagined observations are one-step WM predictions made from the expert's own future states, so the labels use hindsight from the expert trajectory.
  2. Warm-up SFT on the action plus the K label.
  3. Online A2C in ALFWorld with reward = r_env + success bonus − λ_K·K − step cost.

  During RL the rollout alternates the policy's greedy action and a WM step, k times. Only the final imagined observation ('Obs@K') goes into the action prompt.

**How imagination affects the action:** in both variants it is prompt injection of a single imagined trajectory. Nothing scores, ranks or selects among imagined trajectories, and imagined states get no value estimate. The value head is a critic on real states only.

**What happens to imagined futures:** they are written to per-step evaluation JSON logs next to the realized next observation. They are dropped from the agent's context and never compared with reality. There is no backward or goal-regression reasoning.

**Reported results (Table 1):**
- ALFWorld Overall: ITP-I reaches 35.71 / 41.43 / 37.86 on Qwen2.5-7B / Qwen3-8B / Llama-3.1-8B, against RAP at 27.86 / 28.57 / 22.86. ITP-R reaches 85.07 / 88.57 / 87.14, against the best trained baseline (IWM) at 82.80 / 82.14 / 85.90.
- On ScienceWorld and WebShop, ITP-R's margins over the best trained baseline are about 1.3–7 points.

**Concerns with the released code and README:**
- The ALFWorld evaluation's action-parsing regexes are double-escaped. I executed the exact source lines and they never match, so the runner would always fall back to the first admissible action.
- The runner overrides actions in pick-two tasks using task metadata parsed from the gamefile path.
- The README's example RL command trains online on valid_seen, the same split the README evaluates on.
- The Qwen2.5 ITP-R row of Table 1 is internally inconsistent: the COOL and LOOK columns look swapped, and the overall is off by 0.07.

The paper body itself could not be read.

CORE STATE: There are only textual states, rebuilt each step from the environment. There is no persistent structured state.

- **Real state:**
  - In the ALFWorld eval runner, by default (use_history=0) the state is just 'Observation: <current obs>\nInventory: <inferred>' (runner.py:45-48, 356-370).
  - With use_history=1 it is a growing tagged string of Thought, Action and Obs per step (runner.py:262-268).
  - In ITP-R training it is 'Mission/Observation/History' with the history cut to the last 6 (action, obs) pairs (train_adaptive_k.py:43-51, 1313-1329).
- **Imagined state:**
  - In ITP-I, a free-text '<foresight>' block with numbered steps (prompts/imagine.txt).
  - In ITP-R, the text of the final imagined observation 'Obs@K' (train_adaptive_k.py:55-68, 929-963).
- **POIMDP:** the formal pairing of the 'observable stream' (task + history, 'the present') with the 'imaginable stream' (K-step foresight, 'the future') (docs/poimdp.md:9-10). The policy conditions on both, i.e. π(a | s_t, τ̂_t^(K_t)) (workflow figure; README:16).

The WM's own representation is text in, text out: STATE + ACTION → NEXT STATE (observation, inventory, brief outcome) (data_utils.py:28-41).

BRANCHING/REVISIT: There is no branching or revisiting of real or historical states.

- **One imagined continuation per step.** Each step produces a single greedy foresight, and the action is chosen by conditioning on it. Imagined alternatives are not enumerated or compared, and nothing backtracks.
- **Labeling uses prefixes, not branches.** The only multiplicity is in ITP-R pseudo-labeling, where k ∈ {0..Kmax} are prefixes of one teacher-forced imagined trajectory, scored by expert-action likelihood. These are horizon choices, not alternative futures.
- **Imagination is never revisited.** It is discarded from context after acting: the history update excludes the foresight (runner.py:262-271), and in ScienceWorld the foresight goes into a copied message list (runner_sciworld.py:292-303, 333-334).
- **No checkpoint, fork or replay of agent state.** The environment is reset per task, and the eval only resumes by skipping task JSONs already written (runner.py:738-752).
- **Branching exists only in the baseline.** The RAP baseline in the repo does MCTS over alternative actions with WM rollouts and UCT (rap.py:224-323). That is the comparison method, not ITP.

PRESERVED VS LOST: **Preserved** (as evaluation output files, not agent memory):
- The per-episode dialogue history and success/reward (runner.py:345-405).
- The per-step k, raw K output, foresight text, WM raw output, reflection, thought, action, next observation and info (runner.py:245-259, 828-832; runner_sciworld.py:317-331, 350-359; itp_i_driver.py:30-40).
- ITP-R: model and head checkpoints per epoch (train_adaptive_k.py:491-507, 835-849, 1406-1407), and the pseudo-label JSONL with obs_list per expert step (688-697).

**Lost:**
- The foresight is dropped from the agent's context after each step.
- With the default use_history=0, all past observations are dropped from the agent context. The agent and WM see only the current observation and inferred inventory.
- ITP-R's imagined Obs@K is never stored.
- Logs can be overwritten with --override (runner.py:646, 692).

Nothing links a logged foresight to the outcome that later happened.

BELIEF STATE: There is no explicit belief or epistemic state.

- **Reflection and Thought are free text** generated per step. They persist only when use_history=1, and only the Thought persists (runner.py:263-268).
- **No structured beliefs, assumptions, uncertainty or confidence.** The WM decodes greedily and outputs no probabilities. The K-head's categorical is a distribution over lookahead horizons, not over world states.
- **The only structured 'progress' state is a harness heuristic.** It is the eval runner's hand-coded Pick2Progress tracker (placed objects, source hint), built from task metadata parsed out of the ALFWorld gamefile path (runner.py:94-155). It overrides policy actions in pick-two tasks (157-190). This is evaluation-harness logic using privileged metadata, not an agent belief state.
- **Nothing represents what the agent knew at an earlier time**, and no epistemic cutoff exists.

FUTURE: This is the core of the system: a learned, action-conditioned textual world model used for K-step lookahead before each real action.

- **ITP-R rollout:** the policy proposes an action, the WM predicts the next state, and this repeats K times (train_adaptive_k.py:929-963).
- **ITP-I:** the WM is asked once to 'predict the next k steps' as a numbered plan (world_model.py:51-71).
- **Adaptive horizon:**
  - ITP-I: the LLM chooses K from a prompt.
  - ITP-R: a learned K-head, supervised with hindsight pseudo-labels (the K maximizing expert-action likelihood minus λK), then optimized by A2C with a −λ_K·K cost.
- **How the future is used:** only as extra context in the action prompt. ITP-I injects the full foresight text; ITP-R injects K and the final imagined observation.

**What the future mechanism does not do:**
- It does not produce multiple futures or probabilities over futures.
- It does not score imagined trajectories for selection.
- It does not forecast what happens without the agent's action, so there is no intervention-aware comparison.
- It does not reason backward from a goal state.
- Forecasts are not stored for later comparison, and the WM is not updated from forecast errors (it is frozen in ITP-R, train_adaptive_k.py:299-301).

The abstract describes the horizon as 'trading off the ultimate goal and task progress', but in code that is only the K choice.

EVALUATION: **Setup:**
- Benchmarks: ALFWorld (PICK/CLEAN/HEAT/COOL/LOOK/PICK2/Overall), ScienceWorld (Seen/Unseen) and WebShop. Metric: task success rate %.
- Backbones: Qwen2.5-7B, Qwen3-8B, Llama-3.1-8B-Instruct.
- Baselines: prompting (CoT, ReAct, RAP) and training (SFT, WKM, IWM).
- Source: the Table 1 image in the repo.

**ALFWorld Overall:**

| Backbone | ITP-I | RAP | ReAct | ITP-R | IWM | WKM | SFT |
|---|---|---|---|---|---|---|---|
| Qwen2.5-7B | 35.71 | 27.86 | 17.14 | 85.07 | 82.80 | 76.43 | 67.86 |
| Qwen3-8B | 41.43 | 28.57 | — | 88.57 | 82.14 | 79.29 | 70.71 |
| Llama-3.1-8B | 37.86 | 22.86 | — | 87.14 | 85.90 | 77.86 | 79.28 |

**ScienceWorld and WebShop, ITP-R:**

| Backbone | Seen | Unseen | WebShop |
|---|---|---|---|
| Qwen2.5-7B | 62.58 | 58.94 | 60.20 |
| Qwen3-8B | 61.85 | 56.95 | 68.10 |
| Llama-3.1-8B | 63.91 | 57.61 | 67.50 |

- ITP-R's margins over the best trained baseline are 1.24–6.95 points.
- On Qwen3 ScienceWorld Unseen, RAP (27.14) beats ITP-I (19.86).

**My checks on the table and code:**
- Per-type counts imply a 140-game ALFWorld split. The README eval uses --split seen → valid_seen.
- The Qwen2.5 ITP-R row is internally inconsistent: COOL=53.84 is only possible over 13 games and LOOK=76.00 only over 25, and 119/140 = 85.00 ≠ 85.07.
- The IWM rows do not fit the 140-game denominators.
- No variance or seeds are reported.
- No ITP WebShop runner or ITP-R eval script is in the repo.
- The released ALFWorld eval regexes fail to parse actions (verified by executing models.py:288 and 295).
- The README's online A2C example uses --env_split valid_seen, the same split as the README evaluation, which suggests possible train/test overlap. Unverified for the paper.
- The paper's ablations and analyses (adaptive vs fixed K, cost) could not be read.

DOES NOT COVER: **Nothing on the past side:**
- No reconstruction of past world or epistemic state.
- No strict epistemic cutoff or no-hindsight questioning of earlier versions of its own state. Its pseudo-labels in fact deliberately use hindsight from expert futures.
- No identity, objective or policy change tracking.
- No checkpoints, replay or forking.
- No 'never overwrite time, fork it' branch store with provenance.

**Gaps on the future side:**
- Only one imagined future per step, with no probabilities.
- No backward requirements or goal regression from desired or feared futures.
- No passive vs intervention-conditioned forecast distinction.
- Forecasts are not preserved as first-class objects, so prevented futures are not kept or labelled.
- No predicted-vs-realized comparison or calibration. Forecasts are logged next to outcomes but never compared.
- No cross-time queries.

Imagined futures are single-use prompt context, thrown away after each step.

RELATION TO smoke_v1: Low direct overlap. ITP addresses within-episode, step-level lookahead in short-horizon text environments: ALFWorld (≤40–50 steps), ScienceWorld and WebShop.

smoke_v1 tests something different: a later event changes the significance of an earlier world-authored decision (an ADR or ticket), and the agent must reopen it with evidence, separate what was true then / known then / known now, and remediate code. ITP has:
- no access to or reasoning about earlier decisions;
- no as-of epistemic reconstruction;
- no memory across events. Its default agent context is just the current observation.

An ITP-style contestant would add forward simulation ('if I change X, tests/behaviour Y will follow') before a remediation action. That relates only to the remediate step, and mainly to the NORTH_STAR 'simulate future states' component, which smoke_v1 does not centrally test.

ITP does not threaten the distinctness of the historical/epistemic part of the hypothesis. It does set a strong prior baseline for the prospective part: a learned WM with adaptive K-step lookahead conditioned into the prompt is an established technique with reported gains. Any 'future-state simulation' claim in temporal agency should therefore be framed against ITP, RAP, WKM and IWM rather than presented as new.

VERIFIER STRONGEST THREAT: ITP, together with RAP, WKM and IWM, shows that the prospective half of NORTH_STAR is established, published prior art with measured gains. That half is: simulate future states with a learned world model conditioned on the agent's own actions, interrogate the imagined trajectory (reflect on 'progress, risks, constraints'), then act from the present. ITP also formalizes 'present + imagined future' as one decision state (the POIMDP) and learns an adaptive budget for how far ahead to look, with a cost penalty. Any temporal-agency claim of novelty for 'simulate and interrogate possible future states' or for 'acting from the present while conditioning on imagined futures' is therefore pre-empted. The project's distinct residue must lie in what ITP structurally lacks: as-of epistemic reconstruction with a no-hindsight cutoff (ITP's own labels deliberately use hindsight), multiple preserved branches with provenance, labelling prevented futures, comparing predicted against realized outcomes, and cross-time queries. ITP also undercuts the project methodologically: it gets large gains from a single greedy imagined future pasted into a prompt, with no branching, probabilities or memory. A strong RAG/checkpoint baseline given a cheap 'imagine-then-act' prompt step could therefore capture most of any prospective advantage. If the project's contestant wins on remediation steps, the win may be attributable to ITP-style lookahead rather than to temporal addressability, so the benchmark needs an ablation that separates the two.

VERIFIER CORRECTIONS: None of the ratings were refuted. I re-checked all 20 against code and every one holds. | Minor qualification for #1 (partial): the evidence is generic transcript logging. The per-task JSON is written once with open(...,'w') at episode end, so it is not an append-only store. The partial rests on the in-context transcript when use_history=1. | Minor qualification for #18: the analysis did not mention the A2C critic's TD comparison of predicted value against realized reward, which is a narrow predicted-vs-realized analog. It does not change the rating because it is generic RL return learning, not comparison of stored state forecasts.

UNVERIFIED: I still could not read the paper body: arxiv.org is blocked and the WebSearch budget was exhausted (200/200), so no search extract was possible. The local mirror clones contain no ITP files. As a result, I cannot rule out that the paper describes something the released code does not: multiple sampled imagined trajectories, an analysis of foresight accuracy against outcomes, or backward/goal reasoning. The 'no' ratings for #13, #15 and #18 rest on the code and the abstract alone. Also unresolved: how ITP-R picks K at test time (no eval script exists), how the WebShop results were produced (no runner), whether D_roll was used to train the world model (the figure shows it, but no code generates it), whether Table 1 came from the released code (the regex bug suggests not), and whether ITP-R's RL actually trained on the evaluation split. The LLM digest's statements about limitations (multimodal settings, inference overhead, compounding world-model error) remain unverified. Verification notes: /tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/lit/verify/itp.md

VERIFIED RATINGS:
- 1 immutable_historical_observations: partial -- Borderline between partial and no; kept at partial. With use_history=1, the agent's context within an episode is an append-only Thought/Action/Obs transcript. Against that: the per-task log is written once at episode end with open(...,'w'), --override overwrites it, the default use_history=0 keeps o
- 2 historical_world_state: no -- The environment is reset for each task and only stepped forward. The world model only predicts forward. Nothing reconstructs an earlier world state.
- 3 historical_epistemic_state: no -- There is no record of what the agent believed at time t and no cutoff. Foresight is excluded from the history update, and by default the history is rebuilt from the current observation only.
- 4 historical_policy_objective_state: no -- The task is fixed per episode. The only checkpoints are per-epoch model weights, which are not agent-state provenance.
- 5 execution_checkpoints: no -- A grep for deepcopy/snapshot/restore in itp/ and eval/ found nothing in ITP. Resume works only at task level, by skipping task JSONs already written. The other checkpoint hits are model weights and gradient_checkpointing.
- 6 replay: no -- Every episode starts from env.reset(). No mechanism re-runs execution from a historical step.
- 7 fork_from_historical_state: no -- There is no branching from real states. The ITP-I step is linear: decide_k, then imagine, then reflect_and_act.
- 8 counterfactual_action_branches: partial -- Kept at partial. Before committing a real action, ITP simulates the future in the world model without committing, and the policy can deviate after reflecting. But it imagines exactly one greedy continuation per step: alternative actions are never enumerated, compared or selected. MCTS over alternati
- 9 branch_provenance: no -- No branches exist, so no parent, divergence point or reason is recorded. The per-step log only ties a foresight to step t.
- 10 explicit_current_belief_state: no -- Reflection and Thought are free text. Pick2Progress is a hand-coded tracker in the evaluation harness, built from gamefile-path metadata, not an agent belief state.
- 11 uncertainty_representation: no -- The world model decodes greedily (do_sample=False) and outputs no confidence. The K-head's categorical is a distribution over lookahead horizons, not over world states.
- 12 future_state_rollout: yes -- Confirmed. In ITP-R the policy proposes a_hat, the frozen world model predicts the next state, and this repeats K times. In ITP-I the world model writes one K-step foresight. The world model is trained on (state, action) to next_state.
- 13 multiple_prospective_branches: no -- Each step gets one imagined trajectory. The K candidates used in labeling are prefixes of a single teacher-forced trajectory (obs_list[k] = prediction from the expert state at t+k-1).
- 14 probability_over_futures: no -- No future is assigned a likelihood. The label score is the log-probability of the expert action minus λk, which is a property of the action, not of the future.
- 15 backward_requirements: no -- The code contains no goal regression. The abstract's 'trading off the ultimate goal and task progress' is realized only as the choice of K: an LLM prompt in ITP-I, and a K-head with a −λK cost in ITP-R. The paper body is unread.
- 16 intervention_aware_forecasting: partial -- Kept at partial. The ITP-R rollout is explicitly conditioned on the policy's own imagined actions. There is no passive or no-op forecast and no reflexive distinction. Any action-conditioned world model would earn this partial.
- 17 prevented_futures_preserved: no -- Foresight text is only logged. It is never labelled, revisited or scored, and it is dropped from the agent's context.
- 18 predicted_vs_realized: no -- foresight_text and obs_next sit side by side in the log, but no code compares them, and the world model is frozen in ITP-R. A narrow analog exists: the A2C critic compares V(s) with the realized r + γV(s') (TD error). That is generic return learning, not comparison of stored state forecasts, so 'no'
- 19 cross_time_state_querying: no -- There are no state_at, diff or as-of queries anywhere in the repo.
- 20 unified_temporal_abstraction: partial -- Kept at partial, weak. docs/poimdp.md says 'In this release, the POIMDP concept is expressed as a software boundary', made of an observable stream (the present) and an imaginable stream (the future). That covers 2 of the 4 kinds of state required: no history, no counterfactual past, no addressable t

## pmbench: PM-Bench: Evaluating Prospective Memory in LLM Agents (Genglin Liu, Saadia Gabriel; arXiv:2607.12385, July 2026)
Genglin Liu, Saadia Gabriel. arXiv:2607.12385, listed in the 15-Jul-2026 arXiv digest. The code repo's last commit is 2026-07-13. I could not see the affiliation: the digest metadata does not include it, and I did not infer it.

Sources: https://arxiv.org/abs/2607.12385 (NOT READ. arxiv.org is blocked and the session's WebSearch budget was already used up (200/200), so no search extract of); https://github.com/CSQianDong/Awesome-arXiv-Daily-Reporter (15-Jul-2026/AI/README.md:300-306; 15-Jul-2026/AI/papers.jsonl:34; commit 4d0c5775) (git sparse clone. Gives the verbatim abstract, title, authors and arXiv link. Local copy: scratchpad/lit/repos/csq_daily); https://github.com/genglinliu/PMBench (commit e1093c470c8981daf522d4ef047a7c3a71e077d7) (Located with git ls-remote on candidate names, then git clone --depth 1. This is the authors' release: scorer and runtim); https://github.com/CSQianDong/Awesome-arXiv-Daily-Reporter (2-Sep-2026/AI/README.md:139-145) -> arXiv:2609.01272 (git sparse clone. Abstract of a follow-up paper (Prospective Intention Store) that uses PM-Bench. Secondary source.); https://github.com/CSQianDong/Awesome-arXiv-Daily-Reporter (30-Sep-2026/AI/README.md:779-785) -> arXiv:2609.37125 (git sparse clone. Abstract of a follow-up paper (BudgetPM) that uses PM-Bench. Secondary source.)

SUMMARY: PM-Bench is a text benchmark that tests whether LLM agents carry out deferred intentions at the right cue or time while busy with an ongoing activity, in the style of the Virtual Week paradigm. The released scenario is one deterministic synthetic week: 7 days, 80 steps and 83 intentions. Of these, 57 are event-based and 26 time-based. Time is hidden unless the agent queries the clock, and 15 event cues appear only in hidden state channels that the agent must query. There are also 7 cross-day intentions, 11 explicit updates (6 reschedule, 3 override, 2 cancel) and lure actions in each step's menu. Scoring is micro Set-F1 of the chosen task set against the due set at each step, plus hit/late/miss and error categories. The authors released 64 runs (8 models x 8 configurations): full-context baseline, in-context TODO ledger, three heartbeat variants, a hierarchical coordinator with subagents, and two offline replay vote ablations. In the released report the best configuration is heartbeat-proactive, at 65.1% macro Set-F1 across models. The best single run is GPT-5.4 heartbeat-proactive at 79.1%. Hidden non-clock channels are almost never caught (best macro hit rate 16.7%). No configuration wins for every model. The benchmark tests holding and executing intentions only: there is no forecasting, simulation, branching or temporal querying. Its one 'later event changes a commitment' mechanism is explicit updates to intentions that are still pending.

CORE STATE: The environment state, held only by the simulator, is a per-day dict of task states. Each task state holds: original spec (task); mutable 'current' (type, cue_id, cue_channel, target_time, windows, label, action_text); and active, completed, completed_at, cue_seen, cue_step_idx, canceled, updated, has_update and result (sim/pm_bench.py:279-304). The world is an authored list of steps, each with time, vignette text, options, narrative cues, state_events per channel, updates and precomputed ground truth. On the agent side there is no common state abstraction; it depends on the configuration. The baseline uses the full chat transcript. The TODO ledger keeps at most 5 items {task_id, when, status, notes} (run_todo_ledger.py:38-56). The hierarchical setup gives each subagent one JSON memory file holding only its latest version, with no rolling history (run_hierarchical_agent_union_query.py:1-10).

BRANCHING/REVISIT: Agents get no branching or revisiting. Updates overwrite a task's 'current' fields. The original spec stays in state['task'], but intermediate versions are not kept, and updates to completed tasks are silently ignored (pm_bench.py:347-348). Harness-level revisits only:
- deterministic re-simulation from logs for scoring;
- offline replay ablations that re-derive a whole run's task choices from the same logged evidence and record source_union_run_dir (replay_union_votes.py:254);
- a debug-only 'Back One Step' in the human UI, which rebuilds the runtime from a prefix of the log and replaces the current runtime, discarding the later step rather than keeping it as a branch (engine.ts:2186-2217; App.tsx:317-326).

PRESERVED VS LOST: Preserved:
- the authored scenario, which is immutable input;
- per-step action logs (choice, task_ids, query counts, heartbeat flags) plus run metadata (model, backend, timestamps, duration; no token or cost fields);
- per-step ledger snapshots in .ledger.jsonl for TODO-ledger runs;
- per-step prompt logs, which are written but not released.

Lost:
- the intermediate versions of an updated intention ('current' is overwritten);
- TODO-ledger history inside the agent (replaced each step, done items pruned, old messages pruned above about 32k tokens);
- hierarchical subagent memory (one latest JSON per subagent, no rolling chat history);
- the observations themselves, which are not in the released logs.

The release also omits the .debug.jsonl files needed to re-derive the majority/unanimous ablations. The README names 'runs/March_ALL_results_v9' but the shipped directory is 'runs/all_results_v9'.

BELIEF STATE: The benchmark itself has no belief state. Two scaffolds add explicit intention state:
- **TODO ledger:** model-maintained records {task_id, when: exact time | 'cue: X' | 'unknown', status: pending|done|canceled, notes}, capped at 5 items and re-injected each step.
- **Hierarchical subagents:** each emits structured JSON {focus, state_query_suggestions[{channel, reason}], tasks_might_be_due[{task_handle, evidence, pending_state_queries}]}, stored only as its latest version.

Neither represents beliefs about the world beyond pending intentions. Neither has confidence values. Neither has a cutoff-aware view of past belief.

FUTURE: 'Prospective' here means prospective memory: keep a user-given intention ('do X when cue Y' or 'at time T') and execute it when the cue or time arrives. The abstract defines it as 'the ability to execute an intention at a specific future cue or state while other activities are ongoing'. The system prompt says 'remember to perform tasks at the correct time or event without reminders' (pm_bench.py:1282-1295). There is no model of future states. Agents are never asked to predict, simulate, assign probabilities or work backward from desired or feared outcomes. A code grep for predict, forecast, counterfactual, branch, fork, checkpoint, rollback, confidence, probab and uncertain over sim/ and the webapp finds only one prompt phrase ('Prefer precision over guessing when uncertain'). The future is a scheduled trigger, not a modeled state.

EVALUATION: **Scenario.** One fixed scenario, data/synthetic_week_v9.json, generated deterministically by week_builder_v9.py:
- 7 days, 80 steps;
- 83 intentions: 57 event-based (42 narrative cues, 15 hidden-channel cues) and 26 time-based with the clock hidden; 28 regular, 7 cross-day with 1-3 day delays, 12 introduced mid-day;
- 11 same-day updates;
- 10-12 lure actions per day, with 3 shown in each step's menu.

**Scoring.** Micro Set-F1 of the chosen set against the due set at each step (pm_bench.py:2422-2432). Secondary metrics: hit/late/miss, false alarm, commission, wrong-content, update hit/miss/violation, cross-day hit, proactive-monitoring hit by channel, exact-set match.

**Coverage.** 8 models: GPT-5.4, GPT-5.3-Codex, Llama 3.3 70B, Mistral Large 2512, Mistral Small 3.2 24B, Qwen3-32B/14B/8B. 8 setups, one run per cell, 64 runs in total. Six setups are live inference; two are offline replay ablations.

**Macro Set-F1 by setup (released report):**
| Setup | Macro Set-F1 |
|---|---|
| heartbeat-proactive | 65.1% |
| single-todo-ledger | 62.8% |
| single-baseline | 60.0% |
| heartbeat-auto-30m | 57.8% |
| heartbeat-auto-60m | 56.6% |
| hier-union-query | 45.2% |
| hier-majority-vote (replay) | 37.2% |
| hier-unanimous-vote (replay) | 35.3% |

**Other results.**
- Best per-run scores: GPT-5.4 heartbeat-proactive 79.1%, GPT-5.3-Codex single-baseline 78.9%.
- The best non-clock hidden-channel hit rate is 16.7% macro.
- The best setup differs by model.

**Verified locally.** The scenario validates, and rescoring the GPT-5.4 heartbeat-proactive log reproduces TP 55 / FP 3 / FN 26 and 79.1%.

**Discrepancy.** The abstract says 'the best method, a GPT-5.4 agent, reaches only 65.1% F1'. In the repo, 65.1% is the macro average of heartbeat-proactive across models, while GPT-5.4's own run scores 79.1%.

The human evaluation UI is released, but I could not verify any human results.

DOES NOT COVER: Not covered:
- **Past states:** no reconstruction or questioning of past versions of the agent's own state, and no strict epistemic cutoff.
- **Futures:** no simulation or interrogation of possible future states, no backward requirements derived from desired or feared futures, no forecasts (so no prevented-forecast handling and no predicted-vs-realized comparison), and no probabilities.
- **Branching:** no branches or forks with provenance ('never overwrite time, fork it'). Intention updates overwrite in place.
- **Identity and policy:** no tracking of identity, policy or model changes as first-class temporal state.
- **Temporal queries:** no as-of or diff queries.
- **Reopening:** no reopening of already-executed decisions. Updates to completed tasks are ignored (pm_bench.py:347-348).

RELATION TO smoke_v1: Closest overlap: both PM-Bench updates and smoke_v1 are about a later event changing an earlier commitment, and the agent has to notice it. The differences are large:

| Dimension | PM-Bench | smoke_v1 |
|---|---|---|
| How the change is signalled | Explicit notice naming the task and the change ('move it to 15:55', 'you do not need to worry about calling the insurance desk') | Not announced; the agent must work out that a later event changes the significance of an earlier decision |
| What changes | Pending user intentions, always same day and before the original due time | An already-made, world-authored decision (ADR/ticket) |
| Reopening | Never: updates to completed tasks are ignored | Reopen with evidence |
| Epistemic reasoning | None required | State what was true then / known then / known now about then |
| Remediation | None: the action is just choosing a menu item | Remediate the code |

PM-Bench adds something smoke_v1 lacks: proactive monitoring of hidden channels and cue timing over long delays, with distractors.

Its scaffolds are useful references when tuning the smoke_v1 baseline:
- the in-context TODO ledger is similar to a rolling summary or obligation list;
- the heartbeat is similar to periodic re-check prompting;
- 'no single strategy dominates' supports keeping the baseline configurable.

Overall PM-Bench does not pre-empt the temporal-agency hypothesis. It occupies the neighbouring 'remember future intentions' niche and could be cited as the prospective-obligation counterpart. Two of its design choices are worth avoiding: a menu that leaks active intentions, and the ground-truth fallback.

VERIFIER STRONGEST THREAT: PM-Bench, with its follow-ups the Prospective Intention Store (arXiv:2609.01272, 82.9% Set-F1 with lifecycle logic in code) and BudgetPM (arXiv:2609.37125), already covers the most practically important 'future' part of the temporal-agency thesis: obligations owed to the future, kept across long delays, with monitoring of hidden state and explicit revisions to commitments. The PIS result is especially damaging. It shows that a typed intention store driven by code, which is a plain structured-state, non-temporal baseline, beats every LLM-memory scaffold. That suggests the 'act at the right future time / respect changed instructions' part of the thesis can be solved by structured current-state plus lifecycle bookkeeping, with no time-addressable state at all. By analogy, a reviewer could argue that smoke_v1's 'later event changes the meaning of an earlier decision' might also yield to a typed decision/assumption store with invalidation rules, plus the strong RAG baseline, rather than needing historical reconstruction, forking or epistemic cutoffs. If so, the project's hypothesis shrinks to the parts PM-Bench lacks: reopening already-executed decisions, implicit invalidation, the distinction between known-then and known-now, and prevented or predicted futures. The project must show those parts need temporal machinery and not just a better current-state schema. PM-Bench does not pre-empt the hypothesis directly: it has no history, branching or forecasting.

VERIFIER CORRECTIONS: No rating is refuted. Every code citation I re-checked holds: apply_task_update ignores completed tasks and overwrites in place; snapshot and delta query semantics; append-only baseline messages; the ground-truth fallback sorted(due_now); the 5-item ledger cap; the latest-only subagent JSON memory; the UI step-back replacing the runtime; source_union_run_dir. | Omission: sim/run_eval.py:22-29 SETUP_CHOICES also includes 'multi_baseline' (sim/run_hierarchical_agent.py, markdown notebooks, one latest version each). It is not among the 8 reported setups and the analysis does not mention it. This does not affect any rating. | Minor: released run logs store resolved task ids (e.g. 'antibiotic_breakfast'), not menu handles, so they cannot show which handle the model emitted.

UNVERIFIED: The paper body is still unread: arxiv.org is blocked and the WebSearch budget is exhausted (200/200). I cannot rule out that the paper's text discusses or proposes things not in the code, such as forecasting framing, the human-study design, or limitations. The ratings rest entirely on the released code and abstract. Also unknown: whether the ground-truth fallback fired in released runs (prompt logs not released), which heartbeat mode was used (not recorded in metadata), and whether the repo is identical to what the paper used. The follow-up papers are known only from digest abstracts.

VERIFIED RATINGS:
- 1 immutable_historical_observations: partial -- Confirmed. In run_llm, messages is created at line 1749 and afterwards only appended to; grep finds no other assignment or deletion, so the baseline transcript is append-only. The scenario is fixed authored input. Against that, the TODO-ledger runner prunes old messages (_prune_messages, run_todo_le
- 2 historical_world_state: partial -- Confirmed. compute_groundtruth_for_day re-simulates task states deterministically from the scenario. The UI's rewindRuntimeToStep rebuilds runtime by replaying log_entries.slice(0,n). Both are harness-internal; the agent never gets an as-of view.
- 3 historical_epistemic_state: partial -- Confirmed but weak. Each step writes the full messages context to the prompt log (pm_bench.py:1925-1930), so the cutoff holds by construction, but these logs are not released. TODO-ledger runs release per-step ledger snapshots in .ledger.jsonl. These are passive researcher logs: there is no reconstr
- 4 historical_policy_objective_state: partial -- Confirmed. User instructions change over time through explicit updates; the python count gives 11 (6 reschedule, 3 override, 2 cancel). The original spec is kept in state['task'], the current version is overwritten in place, and an 'updated' flag is set. The system prompt says 'Always follow the mos
- 5 execution_checkpoints: partial -- Confirmed. Only the human-eval UI checkpoints: storage.ts saves the whole SessionRuntime to localStorage (pm_bench_frontend_autosave_v1), and App.tsx offers 'Resume Saved Session'. The LLM runners write their logs only at the end and have no resume.
- 6 replay: partial -- Confirmed. There are three harness-level forms: deterministic rescoring from action logs (I reran it and reproduced 79.1%), offline replay_union_votes, and the UI's log-prefix rewind. The LLM agent itself is never re-run from a historical point.
- 7 fork_from_historical_state: no -- Confirmed. handleStepBack replaces the runtime with the rewound one and drops the later step, gated by the 'Allow stepping backward for debugging' option. The replay ablations write new run directories but re-derive whole runs from logged votes; they do not fork from a chosen state.
- 8 counterfactual_action_branches: no -- Confirmed. The agent commits one action per step. The vote-rule ablations are researcher-side and open-loop over fixed logged evidence. A grep for counterfactual, branch or fork finds nothing.
- 9 branch_provenance: no -- Confirmed. Replay-derived runs record only run_metadata['source_union_run_dir'] and a mode label. That is a run-level parent pointer on an evaluation artifact, not a state branch, and it records no divergence point.
- 10 explicit_current_belief_state: partial -- Confirmed. The TODO ledger is {task_id, when, status, notes}, capped at MAX_LEDGER_ITEMS=5 and re-injected each step. Subagents emit structured JSON {focus, state_query_suggestions, tasks_might_be_due[evidence, pending_state_queries]} and keep one latest version each. Both are optional scaffolds and
- 11 uncertainty_representation: partial -- Confirmed but weak. Uncertainty appears only as the ledger 'when' value 'unknown', the instruction to 'keep the 5 most urgent/likely', and subagent pending_state_queries. There are no confidence or probability fields.
- 12 future_state_rollout: no -- Confirmed. A keyword grep for predict, forecast and simulat finds no world model or rollout. Here 'future' means a user-given trigger.
- 13 multiple_prospective_branches: no -- Confirmed absent.
- 14 probability_over_futures: no -- Confirmed. A grep for probab or confiden returns no hits.
- 15 backward_requirements: no -- Confirmed. The closest analogue is the agent deciding to query a channel now because a stored intention's trigger requires it (subagent pending_state_queries). But the trigger conditions are given by the user, not derived from a desired or feared future state.
- 16 intervention_aware_forecasting: no -- Confirmed. There are no forecasts.
- 17 prevented_futures_preserved: no -- Confirmed. Canceled tasks stay in the menu only as traps: the docstring says 'Canceled tasks remain visible so selecting them can be scored as a cancellation memory failure'.
- 18 predicted_vs_realized: no -- Confirmed. The scorer compares chosen task sets with ground-truth due sets. Nothing compares the agent's predictions with outcomes.
- 19 cross_time_state_querying: no -- Confirmed. Clock and snapshot channels return the current value only. Delta channels return events from the last query to now, with no t parameter. Neither is an as-of query or diff(t1,t2).
- 20 unified_temporal_abstraction: no -- Confirmed absent.

## memoryarena: MemoryArena: Benchmarking Agent Memory in Interdependent Multi-Session Agentic Tasks (arXiv:2602.16313)
Authors (from the verbatim arXiv abstract mirrored at CSQianDong/Awesome-arXiv-Daily-Reporter 19-Feb-2026/NLP/README.md:181-187): Zexue He, Yu Wang, Churan Zhi, Yuanzhe Hu, Tzu-Ping Chen, Lang Yin, Ze Chen, Tong Arthur Wu, Siru Ouyang, Zihan Wang, Jiaxin Pei, Julian McAuley, Yejin Choi, Alex Pentland. Affiliations not verified. Dates: the arXiv listing is Feb 2026 (digest dated 19-Feb-2026; the IAAR Awesome-AI-Memory list gives 2026-02-18). The repo's single commit is dated 2026-05-31. The ICML 2026 venue in the task prompt is not verified; the README BibTeX cites it as an arXiv preprint.

Sources: https://github.com/ZexueHe/MemoryArena (commit 6cd9de14b71915e39ac742a20dc33785e14b6aab) (Found with git ls-remote probes (WebSearch budget was used up), then a full git clone to scratchpad/lit/repos/ZexueHe_Me); https://arxiv.org/abs/2602.16313 (Verbatim abstract and author list mirrored in GitHub repo CSQianDong/Awesome-arXiv-Daily-Reporter, file 19-Feb-2026/NLP/); https://arxiv.org/html/2602.16313v1 (WebSearch extract from an earlier session, recorded in scratchpad/lit/notes/mage.md:13,99-102 (four domains; average 57 ); https://github.com/memgrafter/research-digests/blob/491d1e597ee1384396057fbe72e2bdec9f11c2c6/ml_research_analysis_2026/2602.16313_memoryarena-benchmarking-agent-memory-in-interdependent-multi-session-agentic-tasks_20260401_005644.md (git show from a blobless clone; saved as scratchpad/lit/memoryarena_memgrafter_digest.md. LLM-generated (stepfun step-3.); https://arxiv.org/abs/2608.13883 (MemoryLake on MemoryArena) (Third-party abstract in the same digest repo, 17-Aug-2026/AI/README.md:523-529. Secondary; used only for 'all five Memor); local probe scratchpad/lit/ma_probe.py (Ran memory/memory_systems/long_context.py and rag.py with a stub character tokenizer (tiktoken encoding download is bloc)

SUMMARY: MemoryArena is a benchmark and harness, not a memory system. Each task is a chain of interdependent subtasks (sessions). An agent solves the subtasks in order. A pluggable memory backend gets text records of earlier sessions and is asked for context at the start of later ones.

Domains (S4 extract, matching the code):
- bundled web shopping (WebShop-derived; buy compatible products one per step);
- group travel planning (TravelPlanner-derived; plan for successive travelers whose constraints chain to earlier travelers; 270 groups per setup_travel.md:7);
- progressive web search (BrowseComp-Plus queries decomposed into subqueries, then the full query);
- sequential formal reasoning (math and physics "papers" whose questions build on earlier results).

The memory API is minimal: add_chunk(str) and wrap_user_prompt(str)->str, served by FastAPI (memory/server.py). Shipped adapters: long_context, bm25, text-embedding-3-small RAG, Mem0, Mem0-graph, Letta, MIRIX, MemoRAG, a LangChain graph retriever labelled 'graphrag', and ReasoningBank. A-MEM, LightMem and Zep are registered but have no configs.

Metrics:
- shopping: exact-ASIN step match; task success = all steps matched; optional LLM-judged soft reward.
- travel: SR (all persons pass), PS (persons pass), SPS (constraint-slot rate).
- formal reasoning: SR (last subtask correct), progress score (fraction of subtasks correct), passrate@k.
- search: LLM-judged accuracy, evidence recall, calibration error.

Dependencies run strictly forward: later subtasks consume earlier outcomes. No implemented task requires noticing that later information invalidates an earlier decision and then revisiting it. The one prompt that allows adjusting earlier travelers' plans is defined but never imported. The repo has no top-level license.

CORE STATE: There is no first-class state abstraction. The harness keeps:
- a per-task memory instance keyed by user_id, e.g. f"shopping::{task_key}::{model}::{memory}" (run_shopping.py:443-445) or f"data_{data_idx}_{model}_{memory}" (run_travel.py:194). It lives in a process-local dict MEMORY_SYSTEMS (memory/server.py:74).
- environment instances per task_id (env_server.py:68).
- file artifacts: per-step interaction JSON, step results, scratchpads and logs.

Memory content is free text that each runner writes: shopping 'Step i / User Instruction / Agent Action / Env Observation / Done' (run_shopping.py:807-820); travel JSON {name, query, scratchpad, final_plan, judgement?} (agent/travel_planner.py:270-292); math '## Task / ## solution / (## Judge) / ## Tool Calls Info' (agent/math.py:145-161); search 'Subquery i / Predicted Answer / Trace' (browsecomp_plus_env.py:219-222). Each backend's internal representation is opaque to the harness. The only temporal fields are long_context's wall-clock stamps (long_context.py:20) and the Zep adapter's display of valid_at/invalid_at from Zep's service (zep.py:180-187).

BRANCHING/REVISIT: There is no branching. Each task runs as one linear sequence of subtasks. Shopping resume continues the same run directory and picks the latest artifact per step by mtime (run_shopping.py:461-487). There is no fork, no alternate-branch record and no rollback.

Revisit:
- Shopping purchases are terminal per step-episode, with no undo or return action. A grep for refund/cancel/undo/revis*/invalidat* found nothing relevant.
- Each subtask is scored once, when it is answered.
- The harness can *inject* ground truth about earlier steps: shopping feedback "...(ground truth: {target_asin} ...)" (summary_build.py:72-75) when include_history=True, or enable_feedback "The answer is {verdict} because the Ground Truth answer is: ..." (webshop_plus_client.py:998). Travel judgement_mode hint or answer (travel_env.py:160-163). Math judge_result_in_memory. All of these are off in the shipped configs. This tests whether the agent uses the given correction, not whether it notices.
- Travel's SYSTEM_PROMPT says 'You may adjust previous travelers' plans if needed to accommodate new constraints' (travel_planner_env/prompts.py:12-18), but it is never imported. The agent uses AGENT_SYSTEM_PROMPT and 'Create a travel plan for {name}' (agent/travel_planner.py:11-16; prompts.py:132). The scorer would accept a revised earlier plan, because parse_all_plans overwrites by name (run_travel.py:49). Each traveler's GT is fixed.

Verdict: no implemented task requires noticing that later information invalidates an earlier decision and revisiting it.

PRESERVED VS LOST: Preserved on disk, by the harness, for evaluation:
- Shopping: per-step interaction JSON with every turn's input_messages, including the memory-wrapped prompt (run_shopping.py:689-711, 859-875), timestamped step_results, and (with save_trajectories) the full observation per turn.
- Math: per-subtask memory_context, response, GT and judge result (run_math.py:206-216).
- Travel: per-group plans and scratchpads (run_travel.py:383-405).
- Search: the final memory context (browsecomp_plus_env.py:328-341).

Lost or mutable:
- Memory backends are not append-only. long_context truncates the oldest content past 120k tokens (long_context.py:27-30; confirmed by probe). Mem0, Letta and MIRIX consolidate and rewrite inside external services. MemoRAG re-memorizes the concatenated context on each add.
- Memory instances live in server RAM (server.py:74) and vanish on restart. Resume rebuilds them by re-adding entries, and long_context then stamps them with new wall-clock times, so original timing is lost.
- The shopping interaction file is rewritten in place after the step summary is computed (run_shopping.py:1126-1127).
- Environment state is not preserved across subtasks: shopping starts a new env per step (run_shopping.py:887-915). Travel tools are static CSV lookups.

BELIEF STATE: MemoryArena maintains no explicit belief state. Whatever the backend returns as text is what the agent 'knows'. Some plugged third-party backends keep their own structured memory: Letta memory blocks 'human' and 'persona' (letta.py:13-30), Mem0 extracted facts, MIRIX core and episodic stores, ReasoningBank success or failure lessons, and Zep facts with validity intervals. The harness reads none of this structure; it passes a text string through.

The closest artifact to a historical epistemic record is the per-turn logging of the exact memory-wrapped prompt (shopping input_messages; math memory_context). It is an offline trace, not queryable by the agent or the harness.

Uncertainty appears only in the search domain, inherited from BrowseComp-Plus: the agent states 'Confidence: X%' (search_agent/prompts.py:9), and the evaluator computes calibration error (run_search.py:186-190).

FUTURE: None. There is no world model, rollout, imagined future, forecast or probability over futures. Tasks are forward-dependent: later subtasks need earlier outcomes. Nothing asks the agent to anticipate future subtasks; future subtask text is withheld (task_files.py:214-219: "Ignores future steps").

EVALUATION: Benchmark-side metrics, verified in code:
- Shopping: per-step exact ASIN match; overall_success = all steps matched (run_shopping.py:1037-1047); optional soft reward 'r_type * (r_attr + r_price) / (# terms)' with an LLM attribute judge (compute_reward.py:5-10; default gpt-4o).
- Travel: SR = groups where all persons fully pass; PS = person full-pass rate; SPS = average pass rate over 'constraint slots', defined as slots where the person's GT differs from the base person's (travel_planner_env/eval.py:66-205).
- Formal reasoning: SR = last subtask correct; progress score = correct/length; passrate@k and cumulative passrate@k (formal_reasoning_env/eval.py:40-121; setup_formal_reasoning.md:113-138). An LLM judges math equivalence (math_env.py judge).
- Search: final-answer accuracy (LLM judge gpt-4.1), evidence recall, calibration error (run_search.py:168-430).

Paper-side results:
- Abstract (verbatim): agents near-saturated on LoCoMo 'perform poorly in our agentic setting'.
- S4 extract: average 57 action steps per task and >40k-token traces.
- LLM digest D (low confidence): 766 tasks; SR, PS, SR@k decay and latency; external memory and RAG help only in long-trace domains (search, formal reasoning) and add latency; travel SR near zero.

Baselines in the repo configs: long_context with gpt-5-mini, gpt-4.1-mini, claude-sonnet-4(-5) and gemini-3-flash; bm25; text-embedding-3-small; graphrag (LangChain GraphRetriever); memorag; reasoningbank; mem0; mem0-g; letta; mirix; none (travel). A third-party study (MemoryLake, arXiv 2608.13883) reports 0 SR in travel and 1/150 bundles in shopping for all compared systems. I did not verify the paper's own tables.

DOES NOT COVER: Almost all of the temporal-agency thesis is missing:
- no reconstruction or interrogation of past state with an epistemic cutoff (only offline logs);
- no 'what was true then / known then / known now about then' distinction;
- no revisiting or reopening of earlier decisions: the dependencies are forward-only, purchases are terminal, subtasks are scored once, and the travel prompt that permits adjusting earlier plans is dead code;
- no forks or branch provenance ('never overwrite time' is violated by long_context truncation and by consolidating backends);
- no future simulation, multiple futures or probabilities, no backward requirements, no intervention-aware or prevented-future handling, no predicted-vs-realized comparison;
- no tracking of identity, objective or policy changes;
- no as-of or diff queries.
Where later information corrects an earlier outcome (feedback modes), the harness hands the agent the ground truth. It does not test whether the agent notices.

RELATION TO smoke_v1: Overlap:
- Both evaluate long-lived agents across sessions with interdependent work.
- Both compare memory strategies against strong retrieval and long-context baselines. MemoryArena's long_context + BM25/embedding RAG + Mem0/Letta/MIRIX set resembles smoke_v1's 'event log + checkpoints + hybrid RAG + rolling summary' baseline. It could serve as an external sanity check that a temporal contestant does not regress on ordinary forward-dependency memory tasks.

Key difference: smoke_v1's core demand has no counterpart in MemoryArena as implemented. Smoke_v1 requires noticing that a later event changes the significance of an earlier, world-authored decision (ADR/ticket), reopening it with evidence, separating 'true then / known then / known now about then', and remediating code. MemoryArena decisions are agent-made (purchases, plans, answers), are never re-scored, and are not expected to be revisited. In MemoryArena, 'later information' is either the next subtask's requirements or ground truth injected by the harness.

So MemoryArena does not pre-empt smoke_v1's hypothesis. It does show that forward-only multi-session memory is already benchmarked: smoke_v1's distinctiveness must rest on retroactive invalidation and temporal epistemics, not on multi-session dependency per se.

Practical reuse notes:
- A temporal contestant could be plugged in as a memory system (two methods, registered in memory/server.py:49-62). However, runners call wrap_user_prompt only at subtask start (shopping: first turn only), so tool-style temporal queries would need runner changes.
- The runners hold ground truth (travel reset returns 'answers'; the shopping observation carries target_products), so adapting it under smoke_v1's no-leakage rule needs care.
- There is no top-level LICENSE, so reusing or redistributing MemoryArena code is not clearly permitted; citing and running it locally is the safe use.

VERIFIER STRONGEST THREAT: MemoryArena does not implement any of the temporal-agency mechanisms. Its threat is to the project's empirical claim, not its conceptual one. It shows, in a peer-visible 2026 benchmark, that agents near-saturated on LoCoMo do poorly when memory must guide action across interdependent sessions. It also supplies exactly the strong-baseline set the project names: long-context across four LLMs, BM25, embedding RAG, Mem0/Mem0-graph, Letta, MIRIX, MemoRAG and ReasoningBank. A reviewer can therefore argue three things. (1) "Multi-session agents fail because of memory use" is already benchmarked, so smoke_v1's gains must be attributable to retroactive revision and temporal epistemics specifically, not to better multi-session recall. (2) The travel domain already contains the seed of revision: a dead-code prompt allowing adjustment of earlier travelers' plans, and a scorer that accepts revised earlier plans by name-overwrite. Turning that on, or enabling the ground-truth feedback modes, would give a "revisit earlier decision in light of later constraint" test without any temporal machinery. That suggests revision can be framed as a prompt or task-design change rather than an architectural one. (3) MemoryArena's forward-chained, multi-domain, tool-using design (about 57 action steps on average, per a search extract of the paper) is larger and more realistic than a 10-event smoke scenario. If a temporal contestant cannot also win, or at least not regress, on MemoryArena-style forward dependencies, its advantage on smoke_v1 can be dismissed as benchmark-specific. The project's distinct hypothesis survives only if it rests on three things MemoryArena lacks: noticing invalidation of world-authored decisions without injected ground truth, keeping 'true then / known then / known now' separate, and prospective or intervention-aware reasoning.

VERIFIER CORRECTIONS: Overgeneralized: 'Memory instances live in server RAM (server.py:74) and vanish on restart'. ReasoningBank persists to ./reasoningbank_data/{user_id}_reasoning_bank.jsonl and reloads it at construction (reasoningbank.py:94,101: self.memory_bank = self._load_jsonl(self.storage_path)). It receives req.user_id (server.py:95-96), which is deterministic: shopping::{task_key}::{model}::{memory} (run_shopping.py:443-445) or data_{idx}_{model}_{memory} (run_travel.py:194). Implications, inferred from code and not executed: lessons from earlier runs carry over into re-runs of the same configuration, and shopping resume duplicates lessons (reload plus backfill re-add). Mem0, MIRIX and Letta get a fresh uuid4 or agent per init (server.py:100 factory(); mem0.py:16; mirix.py:16; letta.py:9), so their old data is orphaned in the cloud rather than lost. | Overgeneralized: 'Memory backends are not append-only'. RAGMemorySystem (bm25 and text-embedding-3-small) is strictly append-only (rag.py:39-47, _chunks.append; no delete or update). ReasoningBank appends JSONL records of LLM-derived lessons. Only long_context (truncation), MemoRAG and the cloud consolidators rewrite. No rating changes. | Nuance on 'the shopping interaction file is rewritten in place'. It is true for the current attempt (run_shopping.py:1124-1127). However, each attempt writes a new timestamped file (run_shopping.py:866-873), so earlier attempts' files are preserved. This slightly strengthens, but does not upgrade, the partial rating on capability 1. | Addition: the top-level example_travel_planner.py, which the analyst did not cite, also does not use the revision-permitting SYSTEM_PROMPT. A grep for 'adjust' matches only prompts.py:12-18. This reinforces the dead-code claim.

UNVERIFIED: WebSearch was exhausted (200/200) and arXiv and HuggingFace are blocked, so no paper-side claim could be verified independently. That covers the tables, task counts (766 is from an LLM digest), the backbone model, the limitations section, ICML acceptance, and whether the paper discusses revisiting decisions. The dataset contents are also unverified: whether any travel or search instance makes later information retroactively change earlier correctness. The ReasoningBank cross-run carryover and resume duplication are inferred from reading the code, not executed. The cloud backends (Mem0, Letta, MIRIX, Zep) were not run. Verification notes: /tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/lit/verify/memoryarena.md

VERIFIED RATINGS:
- 1 immutable_historical_observations: partial -- The harness writes a new timestamped file per attempt, eval_{stem}_step_{n}_{timestamp}.json, so earlier attempts survive. The current attempt's file is rewritten once with step_summary (run_shopping.py:1124-1127). Agent-facing memory is not an immutable record. long_context truncates the oldest con
- 2 historical_world_state: no -- Each shopping step gets a fresh env; travel tools are static CSV lookups; nothing does as-of reconstruction. A grep for snapshot, as_of and rollback finds nothing relevant.
- 3 historical_epistemic_state: partial -- Weak partial. Offline logs record the exact memory-wrapped prompt per turn or subtask (run_math.py:209 memory_context; shopping input_messages), which is cutoff-correct by construction. There is no API to reconstruct or query it, and the agent cannot use it.
- 4 historical_policy_objective_state: partial -- Weak partial. The static config and each step's task_instruction are logged per artifact. Objectives never change within a run, and nothing tracks changes.
- 5 execution_checkpoints: partial -- Weak partial. Shopping resumes at step granularity by replaying stored memory writes (backfill_memory_from_artifacts -> memory.add, run_shopping.py:823-856, 1080-1092). Runtime and backend state are not snapshotted. Fidelity is worse than stated: ReasoningBank reloads its persisted JSONL at init (re
- 6 replay: partial -- Weak partial. Resume re-executes from the first incomplete step. It cannot pick an arbitrary point, and runs are non-deterministic (temperature 1.0 in bm25.json, LLM judges, cloud backends).
- 7 fork_from_historical_state: no -- There is no branch concept. The run tag is model-mode-memory (run_shopping.py:351-355), and the latest artifact per step is chosen by st_mtime (run_shopping.py:461-487).
- 8 counterfactual_action_branches: no -- Actions commit straight to the env. No simulation or copy mechanism exists, and a grep finds no simulate, branch or fork code.
- 9 branch_provenance: no -- There are no branches, so there is no parent or divergence metadata.
- 10 explicit_current_belief_state: no -- The memory API is text-in/text-out (server.py:106-119). Backend-internal structure (Letta blocks, MIRIX core memory) is flattened to text in wrap_user_prompt (mirix.py:33-95) and never exposed as maintained state.
- 11 uncertainty_representation: partial -- Search domain only. The prompt asks for 'Confidence: ... between 0% and 100%' (prompts.py:9), and the evaluator computes calibration_error = abs(confidence/100 - acc) (run_search.py:189). Memory and state carry no uncertainty.
- 12 future_state_rollout: no -- No world model exists, and future steps are withheld from the agent (task_files.py docstring: '- Ignores future steps').
- 13 multiple_prospective_branches: no -- A grep for forecast, simulat and imagin finds nothing.
- 14 probability_over_futures: no -- The only probability is the current answer's confidence in search.
- 15 backward_requirements: no -- Task constraints are given; nothing derives preconditions from future states.
- 16 intervention_aware_forecasting: no -- No forecasting.
- 17 prevented_futures_preserved: no -- No forecasts exist, so nothing is preserved.
- 18 predicted_vs_realized: no -- Search calibration compares answer confidence with judged correctness at the same time, not a forecast with a realized future. ReasoningBank's success/fail judging (reasoningbank.py:195-208) rates past trajectories, not predictions. Ground-truth feedback modes are off in the shipped configs.
- 19 cross_time_state_querying: no -- wrap_user_prompt takes only a question. Zep prints '(Date range: {valid_at} - {invalid_at})' (zep.py:186), but Zep is registered with no shipped config, and it offers no as-of or diff query.
- 20 unified_temporal_abstraction: no -- There is no temporal abstraction.

