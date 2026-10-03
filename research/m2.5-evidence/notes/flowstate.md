# FlowState: Execution State as Memory for Long-Horizon LLM Agents (arXiv:2609.34565)

Analyst notes, compiled 2026-10-03. Every claim below is tagged with its source and how it was obtained.

## 0. Method and caveats

- arxiv.org (abs, html, pdf) cannot be reached from this container: the egress policy blocks curl and WebFetch. The orchestrator had already verified this, so I did not retry.
- All paper content below comes from the **WebSearch tool** run server-side. Most queries used `allowed_domains: ["arxiv.org"]`. The tool returns a model-written summary of the arXiv HTML/abs page, with quoted-looking sentences. I call these **search extracts (SE)**. They are *not* a byte-exact copy of the paper. Where a summarizer added its own inference (phrases like "This means", "This suggests", "appears to"), I flag it and do not treat it as the paper's claim.
- **No code was found.** A GitHub-restricted search returned only unrelated "flowstate" repos (hyperlaunch/flow_state, makasim/flowstate, agenticair/flow-state, fixpoint-labs/flow-state-dev, amanning3390/flowstate-qmd, ...). None mention Ant Group, ISU or PSA. So I cloned nothing, and **nothing below is verified in code**.
- The session's WebSearch budget (200 calls, shared with other agents) **ran out partway through this analysis**. As a result, some items stay unverified (see section 9).

## 1. Sources

| # | URL | How obtained |
|---|-----|--------------|
| S1 | https://arxiv.org/abs/2609.34565 | WebSearch summary of the abs page (title, authors, date, abstract) |
| S2 | https://arxiv.org/html/2609.34565 | WebSearch summaries of the HTML full text, about 35 targeted queries (method, rules, ablations, results, related work, reproducibility) |
| S3 | github.com (search restricted to that domain) | WebSearch only; no matching repo found |

The bibliographic data comes from S1/S2 SE:
- Authors: Minghao Li, Bangyan Li, Zifan Wang, Yulong Li, Hu Xu, Gan Zhang, Jingtong Wu, Wenqiang Xu. One SE spelled the last author "Wenqiang Wu", most likely a summarizer typo; the others say "Xu".
- Affiliation, per SE: "all from Ant International, Ant Group".
- Submitted: "September 28, 2026" (SE).

## 2. Abstract-level claims (S1/S2 SE, consistent across more than 6 queries)

> "FlowState treats execution state as memory that can be retained and revisited across requests, unifying current decision-making with the reuse of historical information."

> "Long-horizon tasks require LLM agents to continually draw on information from earlier interactions. However, retaining the full history increases context costs, while compressing it risks losing details needed later, and the relevance of historical information often becomes apparent as the task progresses."

> "FlowState preserves semantically typed state nodes, their relations, and references to raw tool observations, separating persistent retention from on-demand access. Within a single execution loop, Incremental State Update (ISU) maintains the current state based on new inputs and feedback, while Progressive State Access (PSA) progressively reveals historical states and supporting evidence as needed during reasoning."

> "Together, these mechanisms enable agents to reassess prior decisions in light of new information and guide subsequent actions."

> "Compared with a full-context baseline using the same DeepSeek-V4-Flash model, FlowState improves the average success rate on MemoryArena and the average pass rate on τ³-Bench by 4.55 and 13.95 percentage points, respectively, while reducing total token consumption by 43.2% and 40.6%."

## 3. Motivating example: reassessing an earlier decision

The motivating example is a **hotel booking** (SE, S2). It is strikingly close to the smoke_v1 premise.

> "A user books hotel A for $200, planning to reconsider if B becomes cheaper, then handles other travel arrangements. On September 12, B drops to $160, but A's $80 cancellation fee makes switching costlier ($240 vs. $200)."

> "the cancellation policy may be overlooked in full context, lost during compression, or stored but not retrieved."

> "FlowState preserves decision D7 and its links to cancellation terms C2 and policy evidence E4 beyond the current view."

> "PSA revisits decision D7 and linked evidence, while ISU combines the new price with this evidence to form an updated decision to keep A (D8)."

Reading: the earlier decision D7 is kept, and a new decision node D8 is created. Whether D8 is formally linked to D7 by `supersedes` is not stated in the extracts; it is plausible given the relation set, but **unverified**.

## 4. Formal model (S2 SE)

### 4.1 Task structure
> "A sequential interaction task consists of user requests q_1,…,q_K. For request q_k, the agent interacts with the environment over T_k ReAct decision steps, each corresponding to one model invocation."

### 4.2 Three stores
- **Persistent State Repository M_k**
  > "M_k is the persistent state repository at the start of request q_k. It stores prior user requests, state nodes, and relations among nodes. Each node records its source request, semantic identifier, category, and full content. A raw tool result is also retained as an accessible state node if it is referenced by a state newly created by the model."

  > "the runtime maintains the Persistent State Repository but does not place it directly in the model context"
- **Historical State Index G_k**
  > "The Historical State Index (G_k) is a lightweight index of historical states constructed at the start of each request covering all preceding requests. For each request, a state entry contains only its semantic identifier and a concise summary maintained for that state. The lightweight index G_k is included in the model context for the request."

  > "Full contents persist in a Persistent State Repository, while identifiers and concise summaries form a Historical State Index included in the model context"
- **Active State S_{k,t}**
  > "The Active State contains states created during the current request, together with disclosed historical states and their relations, with the full contents of undisclosed historical states excluded."

### 4.3 State node types
"Table 6 summarizes the five state types", in Section 2.1 "Persistent Execution State" (SE). The definition sentence, quoted by SE:
> "FlowState classifies information by source and role: user-side *preferences* record the user's preferences, requirements, and constraints; environment-side *knowledge* records tool observations, while *attributes* capture entity-level information distilled from those observations; and agent-side *judgements* record the agent's assessments of task objectives, plans, decisions, and risks, while *artifacts* record reusable outputs produced by the agent."

Another SE phrasing: "Agent-side judgements record agent assessments of task goals, plans, intermediate decisions, and execution risks."

The five types are:
1. **preferences** (user-side)
2. **knowledge** (environment-side; raw tool observations)
3. **attributes** (environment-side; entity-level info distilled from observations)
4. **judgements** (agent-side; objectives, plans, decisions, risks)
5. **artifacts** (agent-side; reusable outputs)

The full text of Table 6 was **not retrieved**.

### 4.4 Relation types
Two independent SE returns agree on this.
> "The relation types in FlowState include: supports, derives, follows, and supersedes. Every edge points from the state being added or updated (source) to the state_id in that ref (target), and all relation types use this direction."

> "Directed relations are declared through refs"

> "each relation specifies its type and the identifier of the related node, allowing the model to decide whether to access that node in a subsequent step."

The relation types are **supports, derives, follows, supersedes**. Their per-type definitions were **not retrieved**: one query for them returned nothing from FlowState, and a different paper (NEST) surfaced instead.

### 4.5 ISU (Incremental State Update)
> "Incremental State Update (ISU) creates and revises current states from new inputs and execution feedback without reconstructing the entire state."

> "The model uses the current context to produce a candidate state delta comprising three operations on state nodes: Add, Update, and Remove."

> "Add creates a state for the current request; Update and Remove apply only to states created during the current request."

> "The state delta is validated before it is committed ... the validated state delta is committed to the Active State, yielding the intermediate Active State after ISU."

Validation rules, from a single SE that paraphrases the "execution rules P" and `Validate_upd`:
> "Each Add operation in ΔS_(k,t) requires an unused semantic identifier"

> "References in proposed state relations must resolve to valid node identifiers"

> "The target of each Update or Remove operation must be present in S_(k,t) and must have been created during the current request."

> "Operations failing these conditions are excluded from the validated state delta"

### 4.6 PSA (Progressive State Access)
> "Progressive State Access (PSA) retrieves historical content through the index or relations in already disclosed states, tracing back to raw observations as needed."

> "At step t, the model uses state identifiers and their summaries in G_k, together with disclosed relations in S_(k,t), to specify a set R_(k,t) of historical states to access. The Disclose function returns the contents and relations of validated target states that are not already in the active state"

> "The agent selectively expands historical states through the same representation used for current states, separating persistent retention from context visibility to keep the working context compact."

### 4.7 End of request: persistence and immutability of history
> "At the end of q_k, newly created states and relations retained for subsequent requests are incorporated into M_(k+1)."

> "the Persist operation incorporates request q_k and the newly created states and relations retained at the end of the request into M_(k+1), and retains any raw tool results referenced by those states as knowledge nodes."

> "new states record their respective request as their source request; historical states retain their original source requests and cannot be deleted."

> "At the end of each request, the resulting states and updated index are retained for future reuse."

Summarizer inference, **not** paper text:
- One SE added: "This means that unreferenced raw observations are discarded from the Persistent State Repository."
- Another added: "This suggests that unreferenced tool outputs are effectively discarded".

The paper text itself says only that raw results are retained *if referenced*. Whether unreferenced raw results are kept anywhere else, such as a trajectory log, is **unclear**.

## 5. Evaluation (S2 SE)

### 5.1 Benchmarks
> "FlowState is evaluated on a subset of MemoryArena environments (Bundled Web Shopping, Group Travel Planning, and Formal Reasoning: Math and Physics) and on τ³-Bench (Airline and Retail). The former tests information reuse across interdependent subtasks; the latter tests policy-constrained tool use."

τ³-Bench base task sets, per SE: "50 airline tasks and 114 retail tasks".

### 5.2 Baselines
> "The study compared FlowState against Full Context (full interaction history), memory-system methods (ReasoningBank, BM25, and Mem0), a state-tracking method (ZipAct), and a hybrid method (ZipAct+BM25)."

> "All methods use DeepSeek-V4-Flash in the primary comparison, while Full Context is also evaluated with GPT-5.6-terra and Qwen3.5-397B-A17B."

> "To assess whether FlowState's benefits persist across base models, the authors evaluate it with DeepSeek-V4-Flash, GPT-5.6-terra, and Qwen3.5-397B-A17B, comparing each with Full Context using the same model."

### 5.3 Headline numbers
- MemoryArena: +4.55 pp average SR vs Full Context, and 43.2% fewer total tokens.
- τ³-Bench: +13.95 pp average pass rate, and 40.6% fewer tokens.
  > "FlowState improves Pass Rate over Full Context by 20.0 and 7.9 percentage points on Airline and Retail, respectively, and DB Accuracy by 7.5 and 5.3 percentage points."

  The mean of 20.0 and 7.9 is 13.95, which matches the abstract.
- > "On Bundled Web Shopping, FlowState achieves a PS (Progress Score) of 42.89%, outperforming the strongest memory-system baseline by 11.78 percentage points."
- > "On Group Travel Planning, it reaches a PS of 12.57%, exceeding the best baseline by 5.61 percentage points."
- > "FlowState surpasses ZipAct+BM25 on all nine performance metrics"

  Also: "Directly combining state tracking with historical retrieval (ZipAct+BM25) does not yield consistent gains".
- Physics, single SE, unconfirmed: "On Physics tasks, it reduces token consumption by 51.69% with DeepSeek-V4-Flash."

### 5.4 Ablations (Table 3; Group Travel Planning and Bundled Web Shopping; values from a single SE)

Variant definitions (SE):
- > "w/o PSA" "removes the Historical State Index and progressive access, instead retaining the full contents of all ISU-generated historical states in the Active State across subtasks"
- > "w/o ISU" "retains PSA's access mechanism but populates the Historical State Index with historical state nodes assembled by predefined rules at subtask boundaries" / "constructs a state node from the final response at the end of each query, linking it to the raw tool results from that query through fixed rules without involving ISU."

| Variant | Travel SR | Travel PS | Travel sPS | Travel tokens | Shop SR | Shop PS | Shop tokens |
|---|---|---|---|---|---|---|---|
| FlowState | 0.74 | 12.57 | 91.87 | 128.93M | 5.33 | 42.89 | 44.83M |
| w/o PSA | 0.37 | 9.36 | 87.18 | 160.27M | 3.33 | 44.67 | 115.37M |
| w/o ISU | 0.00 | 9.15 | 90.34 | 93.16M | 0.00 | 32.11 | 69.01M |

Paper interpretation (SE):
> "Removing ISU reduces SR to zero in both environments, with lower PS as well. With PSA still available, this comparison suggests that states constructed and updated during execution better support task completion than rule-generated historical state nodes at subtask boundaries."

My observations, from the SE numbers only:
- Absolute SRs are very low. Group Travel SR is 0.74%.
- w/o PSA has a *higher* PS than full FlowState on Web Shopping (44.67 vs 42.89).
- w/o ISU uses *fewer* tokens than FlowState on Travel Planning (93.16M vs 128.93M).

So the ablation does not show a uniform win on every metric. The number of runs or seeds and any variance were not retrieved.

## 6. Related-work positioning (S2 SE)

- ZipAct: "ZipAct replaces the growing history with a continuously updated compact state". FlowState's claimed difference: typed, individually addressable nodes kept across requests, with retention separated from visibility.
- MAGE, described by the paper as concurrent work:
  > "Concurrent work, MAGE (Chen et al., 2026), organizes execution history as a hierarchical state tree with active-path context and branching revision."

  Per the same SE, MAGE has "Grow / Compress / Maintain / Revise (restores a target boundary and resumes on a new branch)". FlowState contrasts itself with MAGE and **does not** describe any branching or restore. MAGE is worth a separate analysis for the fork/revisit capabilities.

## 7. Code availability (S2 SE)

> "We will release the complete source code at an appropriate time."

The same SE said: "The paper includes runtime prompt templates in Appendix B.3". A loosely worded addition, "code and result data are indicated to be available", contradicts the quoted sentence and is treated as noise. The GitHub search found no repo. **Status: not released as of 2026-10-03, as far as could be determined.**

## 8. Limitations

- The paper's own Limitations section: **not retrieved**. Several queries failed to surface it.
- Limitations I observed from the extracts:
  - Every comparison except Full Context uses a single backbone (DeepSeek-V4-Flash).
  - The ablation covers only 2 MemoryArena environments.
  - Absolute SR on Group Travel is very low.
  - No code is available.
  - State quality depends on the LLM's own ISU deltas. Validation is syntactic: ids, references, and the current-request scope.

## 9. Could not verify

1. The full text of Table 6, the five-type taxonomy. I have the definition sentence only.
2. Per-type definitions of the relations supports / derives / follows / supersedes, and whether D8 is linked to D7 by `supersedes`.
3. Whether superseded historical states are marked in the Historical State Index, and whether a historical state's "concise summary maintained for that state" can change after its request ends.
4. Whether states that ISU Removes or Updates within a request leave any trace. They appear not to be persisted, but this is not stated.
5. Whether unreferenced raw tool results are logged anywhere outside memory. Only summarizer inference says they are discarded.
6. Whether ISU is a separate LLM call or part of the same step's invocation, and the latency or extra-call overhead.
7. Main-results tables per environment, including Math and Physics. The 51.69% Physics token figure comes from a single unconfirmed SE.
8. Metric definitions (SR, PS, sPS), number of runs, and variance.
9. The paper's own Limitations / Future Work section.
10. The prompt templates in Appendix B.3.
11. Any code. None exists publicly, as far as I could find.
12. Absence claims (no rollout, branching, forecasting, or calibration) are based on (a) no such mechanism in any of about 35 method-focused extracts, and (b) one SE stating "The search results do not mention FlowState supporting counterfactual reasoning or simulation of future states" and that FlowState "does NOT appear to implement branching". These are absence-of-evidence judgements, not quotes of the paper denying the features.
    - The same SE also asserted FlowState "appears to support checkpoint restoration". This is summarizer inference from "retained and revisited"; no restore mechanism appears in any extract, so I reject it.
