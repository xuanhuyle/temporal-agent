# Deep read: Experience Graphs: The Data Foundation for Self-Improving Agents (Trellis)

Gang Liao, Yujia He, Abdullah Ozturk, Zhouyang Li, Ying Wang, Zhitong Guo, Hongsen Qin, Yaobin Qin, Tao Yang, Zewei Jiang,
Dianshi Li, Jort Gemmeke, Jiangyuan Li, Liyuan Li, Nathan Yan, Masha Basmanova, Uladzimir Pashkevich, Matt Steiner,
Pedro Pedreira, Rob Fergus, Anirudh Goyal, Carole-Jean Wu, Gaoxiang Liu, Andrew Witten, Daniel J. Abadi.
Affiliations: Meta Platforms, plus Abadi at University of Maryland, College Park. Corresponding authors: Liao, Liu, Abadi.
arXiv 2606.29823v1, submitted 2026-06-29T06:02:20Z and announced 2026-06-30 ("Announce Type: new").
Primary category cs.DB, cross-listed in cs.AI and cs.MA. Licence CC BY 4.0. Venue: arXiv preprint. No venue is stated.
It reads as a database-vision paper (CIDR style). The authors call their measurements "preliminary results".

Date of this read: 2026-10-03. Lanes: identity-drift and epistemic-cutoff. Also relevant to exec-state and temporal-memory.

## What was read, and how

- **Full paper text: READ IN FULL.** That covers the abstract, sections 1 to 9 and the reference list (1401 lines). It is a
  third-party Markdown conversion of the arXiv HTML (LaTeXML) rendering. The anchors (`#S2.F1`, `#bib.bib7`) and the
  `ltx_verbatim` blocks are LaTeXML artefacts.
  - https://raw.githubusercontent.com/will-rice/llm-self-improvement-papers/main/papers/arxiv-2606-29823v1--6e98abcf640a.md
    The front matter reads `identifier: arxiv:2606.29823v1` and `url: https://arxiv.org/abs/2606.29823v1`. The
    `main` and `master` refs are byte-identical. sha256 `51a58d2e3e84ad76b6ee6a568ea6889db9eb48481b684434cbd1d5d5ba443feb`.
    Local copy: `scratchpad/lit/deep6_raw/wr_main.md`. Line numbers below refer to this file.
  - Figures 1 to 4 are images and were **not** available (architecture, search strategies, best-fitness curve, valid/buggy
    bars). The numbers quoted from them come from their captions and the body text.
  - I found the mirror with GitHub code search (MCP), query `"experience graph" Trellis "time-travel query"`. arxiv.org is
    blocked from here, and the WebSearch budget for the session was exhausted (200/200), so no WebSearch was possible.
- **Metadata and abstract were cross-checked** against three independent mirrors:
  - arXiv RSS (cs.DB, 2026-06-30), captured by https://raw.githubusercontent.com/ehijano/rss_fetch/master/rss_data/cs.DB/2026-06-30_cs.DB.xml
    It shows `arXiv:2606.29823v1 Announce Type: new`, categories cs.DB/cs.AI/cs.MA and `dc:rights` CC BY 4.0.
  - https://raw.githubusercontent.com/Mont9165/arxiv-issue-bot/main/data/papers/2606.29823.md gives "Primary category: `cs.DB`".
  - https://raw.githubusercontent.com/flybfree/AI-Wiki/master/raw/papers/2026-06-29_06-02-20Z_ExperienceGraphs_TheDataFoundationforSelf_Improvin.md
  - The local Awesome-arXiv-Daily clone, `scratchpad/lit/repos/pf/daily/30-Jun-2026/AI/README.md`.
  - **Discrepancy, which is benign:** the arXiv metadata abstract is a shortened version of the abstract in the paper body.
    The body version adds "security research", "compare alternatives", "mutable search statistics" and the sentence "Even
    the file-based memory that production agents have converged on ... captures what an agent _knows_, not the
    reward-bearing experience graph of what its search _tried_." Both versions contain the time-travel sentence.
- **Code from the authors: NOT FOUND (not verified).**
  - The paper links no repository for Trellis. It links only Axiom (`github.com/facebookincubator/axiom`), the query
    optimiser it builds on, and the KernelEvolve references (arXiv 2512.23236; an ISCA paper; a Meta engineering blog post).
  - GitHub repository search for "KernelEvolve" returned 502 twice. GitHub code search for `Trellis "experience graph"
    language:Python` found only third-party files.
  - **Unofficial reproduction:** `lmccccc/XEvolve`, file `code/agentdb/src/agentdb/database.py`. Its docstring says
    "PostgreSQL persistence for the local Experience Graphs reproduction"; "A narrow PostgreSQL implementation of the Trellis
    logical schema". It implements a `state_mutations` table and `as_of_step` reads. It is not by the authors and was not
    evaluated here. Its existence shows the design is easy to implement. sha256 `df96e9bd...`.
  - The Meta engineering blog (engineering.fb.com) did not respond from this sandbox (HTTP 000).

## Plain summary

Trellis argues that the search history of long-horizon "explore" agents should be the primary state of a governed
database rather than JSON checkpoints and logs. Examples of such agents are KernelEvolve, AlphaEvolve-style evolutionary
search and MCTS over code.

The history forms an "experience graph": a tree or DAG of attempt nodes. Each node carries a parent link, artifacts,
execution output, a fitness reward, sibling relations and mutable search statistics (visit_count, ucb_score, island_id).

The architecture has three parts:
- an inner loop: a stateless agent session that makes one node per invocation;
- an outer loop: a control plane that selects the search policy;
- a persistent store.

Many agent operations are recast as queries over that store: resume, reuse, repair, train, replay, observe, audit and
govern.

The time-related mechanism works as follows:
- Nodes are insert-only.
- Every in-place field mutation goes to a change log keyed by a logical step number (evaluation order).
- AS-OF reconstruction then recovers the state at any step.
- The authors justify this explicitly as preventing future-information leakage into training trajectories.

There is one evaluation, a KernelEvolve cross-session memory ablation. It compares no memory with retrieval-injection
rates p=0.1 and p=0.5, over about 100-node sessions, 3 sessions per configuration, using greedy search.

| Measure | No memory | With memory |
| --- | --- | --- |
| Buggy-node rate | 55% | 34% (p=0.1); 21% (p=0.5) |
| Steps to reach 1.2x speedup | 51 | about 5 (both settings) |
| Tokens per valid node | baseline | 52% lower |
| Single best solution | 1.49x | 1.36x |

The study also reports an exploration-anchoring trade-off: the no-memory baseline found the single best solution.

**Time travel, AS-OF reconstruction and branching are never evaluated empirically.**

## Verbatim evidence (line numbers in wr_main.md)

**Abstract (L94-98).** This is the headline claim, made in the abstract and the core thesis:

> "Frontier selection is a query, cross-session reuse is vector-seeded graph retrieval, training-data extraction is a
> materialized view, and reconstructing what an agent knew at any past step is a time-travel query. When the database
> owns the experience graph instead of the agent process, agents become stateless, serverless compute, and crash
> recovery, horizontal scaling, and a closed-loop training flywheel emerge as architectural byproducts."

**Introduction (L168-171).**

> "recovery is a query against the frontier, cross-session reuse is a vector-seeded graph traversal, training-data
> extraction is a materialized view, and agent replay is an as-of temporal query."

**Contributions (L188-190).** The paper identifies the following as a common access pattern:

> "append-heavy writes mixed with multi-hop path updates, vector retrieval, and as-of temporal reconstruction"

**Multi-version state and time travel (L662-677).** This is the core mechanism:

> "Nodes are inserted once and never deleted, but some fields are mutated in place: backpropagation rewrites visit
> counts and rewards along the ancestor chain, and evolution reassigns a node's island. To avoid discarding history,
> Trellis captures every field-level mutation in a lightweight change log keyed by a logical _step number_, the
> evaluation order rather than wall-clock time, so that progress is comparable across machines and runs. This turns the
> experience graph into a multi-version object: any past state is reconstructible by replaying the log backward to a
> target step."
>
> "Multi-version state is not merely an observability convenience—it is a correctness requirement for training. The
> statistics an agent acted on—the visit counts and UCB scores that drove a frontier choice—are exactly the fields
> backpropagation later overwrites; reconstructing a trajectory from final state would train the model on decisions
> justified by information that did not yet exist."

**SFT trajectories (L690-699).** This is an explicit no-hindsight cutoff:

> "the numeric state that drove each decision—visit counts, UCB scores, island membership—is mutated in place by later
> search, so replaying it from final state leaks future information into the example. A faithful trajectory reads each
> node _as of_ its own step, an AS-OF reconstruction over the change log ... A recursive ancestor query then reconstructs
> any trajectory with full provenance."

**Table 1 (L362-370): episodic memory compared with the experience graph.**
- Structure: "tree / DAG: nodes with parent links, rewards, and siblings".
- Mutability: "mutable: visit_count, ucb_score, island_id rewritten by search algorithms".
- Time travel: episodic memory has "none"; the experience graph has "CDC changelog → AS-OF reconstruction at any step".

**Table 2 (L375-384): agent operations as queries.**
- "Replay | Reconstruct a node's state _as of_ any past step."
- "Audit | Trace which prior attempts, tool outputs, and documents influenced a given decision."
- "Observe | ... render lineage graphs."
- "Repair | Query all prior failures sharing the same error signature to avoid repeating known dead ends."

**Logical model (L520-532).**

> "Tasks define the problem: specification, target environment, and success metric. Sessions record who is searching,
> with which algorithm, and how far they have gotten. Nodes capture every individual attempt: parent link, generated
> artifacts, execution output, fitness score, evaluation evidence, and algorithm-specific metadata ... Prompt histories
> preserve the exact messages the LLM saw and produced."

**Context as managed state (L542-550).**

> "The prompt_history table serves two roles: it supplies the transcript that trajectory replay requires for training,
> and it lets a child node either inherit its parent's session as a cheap resume or reconstruct context from the graph
> through an ancestor query."

**Checkpoint and resume (L335-342; L770-776).**

> "The foundation collapses this difference by treating the inner-loop session itself as resumable state—each node
> references the session that produced it—so an interrupted session is reattached rather than restarted."

> "any worker resumes from the last committed node: recovery is a frontier query rather than checkpoint
> deserialization"

**Skills and memory are versioned (L578-585).**

> "Trellis stores them as versioned artifacts in a distributed file system ... a governed, audited update to shared
> state, with provenance linking each distilled skill back to the episodes and exploration nodes that justified it."

**GRPO forks from stored historical states (L719-725).**

> "We sample a state from the persistent buffer, generate N child candidates (a GRPO group), evaluate them in the target
> environment, compute group-normalized advantages, train using the policy gradient, and append one canonical node back."

**Inner loop: sandboxed alternatives (L255-260).**

> "consume a task description and context from the outer loop, generate candidate artifacts via LLM inference, execute
> and evaluate in an isolated sandbox, and persist the structured output ... The agent then terminates; it holds no
> state."

**Value models: proposed, not built (L729-737).**

> "A value model can estimate the expected gain from expanding a given frontier node, reusing a prior subtree, merging
> two branches, or invoking a verifier—conditioning not on a token sequence but on graph features"

**Invalidation propagation (L750-755; L899-903).** This is a data-level analogue of "a later event changes the standing of
earlier derived things":

> "when a source node is retracted or invalidated, the training examples derived from it must be retracted too. The data
> foundation must propagate these retractions through materialized views while respecting access policies"

**Bi-temporal memory (L923-933).** The authors list this as an open problem, not as something built:

> "The change log ... versions exploration state along a single axis—evaluation order—which already supports time
> travel over a search. Full bi-temporal semantics add a second axis, separating _valid time_ (when a fact was true) from
> _transaction time_ (when the entry was committed), unlocking late-arriving corrections, memory-drift detection across
> environment changes, and distillation audit ("what did the agent know at time T, and was it still true?"). Lifting
> versioning from a field-level log to first-class temporal predicates in the query layer—and planning queries that
> range over both axes—is an open problem."

**Retrieval quality (L913-917).** This is also an open problem:

> "How should the store score memory quality, detect stale or low-quality entries that would reinforce past mistakes ...
> and keep retrieval fresh as hardware and workloads drift?"

**Scientific societies (L957-959).** This is a vision only:

> "a leaderboard that separates score from confidence, an idea store whose claims carry state machines (proposed → tested
> → replicated → distilled)"

**Related work (L1018-1019; L1052-1054).**

> "[run trackers] offer no as-of reconstruction of the state an agent acted on"

> "Temporal databases, MVCC, and CDC provide the historical lineage for the time-travel design. Trellis applies those
> old ideas to a new object: the mutable search state of a self-improving agent."

**Graphiti (L983-986).** The authors call Graphiti "the closest prior work in spirit, though aimed at enterprise memory
rather than RSI experience graphs and without CDC, materialized training views, or a graph-native query layer."

## Capability ratings (only what Trellis itself provides; "design" means described, not evaluated)

1. **immutable_historical_observations: YES (design).**
   - "Nodes are inserted once and never deleted".
   - Every field-level mutation is captured in a change log.
   - prompt_history keeps "the exact messages the LLM saw and produced".
   - Artifacts and logs go to object storage "preserving full lineage".
   - Caveat: node rows themselves are mutated in place; immutability comes from the CDC log. Retraction of source nodes
     exists for governance.
2. **historical_world_state: PARTIAL.**
   - The search state (graph, statistics, artifacts and tool outputs per node) can be reconstructed AS-OF a step.
   - The external environment is not versioned (hardware, workloads, ground truth).
   - Valid time and "memory-drift detection across environment changes" are explicitly listed as open problems.
3. **historical_epistemic_state: YES (narrow scope, design-level).**
   - It reconstructs "what an agent knew at any past step" as an AS-OF query: exact prompts plus the statistics that drove
     each choice.
   - The rationale is explicitly no-leakage: "decisions justified by information that did not yet exist".
   - Limits:
     - Versioning runs on a single logical-step axis.
     - The reconstruction is consumed by training extraction, replay and audit, not by the agent deliberating.
     - It recovers inputs and statistics, not structured beliefs.
     - The bi-temporal question "what did the agent know at T, and was it still true?" is left open.
4. **historical_policy_objective_state: PARTIAL.**
   - Sessions record the algorithm. Tasks record the specification and success metric.
   - Skills and declarative facts are versioned, with provenance back to the episodes that justified them.
   - There is no per-node model or prompt-policy version, and no analysis of objective or identity change over time.
5. **execution_checkpoints: YES.**
   - Database-native state replaces JSON checkpoints: "any worker resumes from the last committed node".
   - The inner-loop session is resumable: "reattached rather than restarted".
   - Production crash recovery is reported qualitatively.
6. **replay: YES (design).**
   - Table 2 lists "Replay: Reconstruct a node's state as of any past step".
   - prompt_history supplies the transcript for trajectory replay.
   - The GRPO path re-executes N children from a sampled stored state.
7. **fork_from_historical_state: YES.**
   - Any stored node can be expanded into new children, and the originals are never deleted.
   - A child either inherits the parent session or rebuilds context through an ancestor query.
   - GRPO forks from sampled past states.
   - Not described: forking from an AS-OF version of the mutable statistics.
8. **counterfactual_action_branches: YES (search sense).**
   - Siblings from one parent are alternative actions from the same state, evaluated "in an isolated sandbox".
   - DPO pairs are built from sibling comparisons.
   - This is not causal counterfactual reasoning about past real decisions.
9. **branch_provenance: YES.**
   - Records parent link, session, algorithm and prompt_history, plus an analysis report per node.
   - Supports "Audit: Trace which prior attempts, tool outputs, and documents influenced a given decision".
   - Lineage graphs can be rendered. Distilled skills link back to their source episodes.
10. **explicit_current_belief_state: PARTIAL (weak).**
    - There is only a versioned, governed declarative-facts tier (CLAUDE.md or MEMORY.md style text) plus numeric search
      statistics.
    - Typed beliefs, assumptions and requirements are absent.
    - The claim state machine ("proposed → tested → replicated → distilled") is vision only.
11. **uncertainty_representation: NO.**
    - "A leaderboard that separates score from confidence" is vision only, and match "confidence" is an open question.
    - Fitness and is_buggy are outcomes, not uncertainty.
12. **future_state_rollout: NO.**
    - The value model over graph states is proposed, not built.
    - MCTS here expands real, sandbox-executed nodes, not simulated futures.
13. **multiple_prospective_branches: NO.**
    - The frontier holds several open branches, but they are executed attempts, not imagined futures. In sandboxable
      domains, executing a branch replaces prospection.
14. **probability_over_futures: NO.** UCB scores and visit counts are search statistics, not likelihoods of imagined
    futures.
15. **backward_requirements: NO.** Skills define success criteria, and the ISA coverage matrix targets gaps left by earlier
    sessions. Neither derives present obligations from a future state.
16. **intervention_aware_forecasting: NO.**
17. **prevented_futures_preserved: NO.** Failed or buggy nodes are kept and queried ("Repair"), but those are realised
    failures, not averted forecasts.
18. **predicted_vs_realized: NO.** No stated predictions are recorded and compared with outcomes. MCTS backpropagation of
    rewards is standard search, not calibration.
19. **cross_time_state_querying: YES (state_at; design-level).**
    - The paper offers "AS-OF reconstruction at any step", an "as-of temporal query" and a "time-travel query".
    - A diff between two steps is structurally the slice of the change log between them, but it is not described as a
      query.
    - The authors themselves say "first-class temporal predicates in the query layer" are an open problem; today the
      reconstruction is done by log replay. Versioning is single-axis.
20. **unified_temporal_abstraction: PARTIAL.**
    - One experience graph plus change log covers historical states (AS-OF), the current state (frontier and best node)
      and alternative branches (siblings), all through "one data interface".
    - Prospective, imagined or forecast states are absent.

## How Trellis threatens the project's novelty

1. **It removes the infrastructure novelty of "time as an addressable dimension of agent state".**
   - A Meta and UMD team with a database pedigree (Abadi), with the design deployed in production, presents the following
     as ordinary database consequences ("architectural byproducts", "old ideas [temporal DBs, MVCC, CDC] applied to a new
     object"):
     - append-only experience;
     - AS-OF reconstruction of "what an agent knew at any past step";
     - replay;
     - branching with lineage;
     - resumable sessions;
     - audit of what influenced a decision.
   - Any claim that the project's contribution is the state abstraction itself (state_at(t), fork with provenance,
     never-overwrite) is now prior art twice over: in Trellis, and in the temporal and MVCC database tradition it cites.
2. **It already states the epistemic-cutoff rationale.**
   - "Reconstructing a trajectory from final state would train the model on decisions justified by information that did
     not yet exist" is the no-hindsight principle, applied to training-data fidelity.
   - The project cannot claim a strict epistemic cutoff on reconstructed past state as a new idea. At most it can claim to
     apply that cutoff to the agent's own decision-time reasoning.
3. **It names the project's benchmark question as a data-level open problem.**
   - The bi-temporal paragraph lists "late-arriving corrections, memory-drift detection across environment changes, and
     distillation audit ('what did the agent know at time T, and was it still true?')".
   - The retraction paragraph requires propagating invalidation from a source node to everything derived from it.
   - Together these are the data-system version of "a later event changes the significance of an earlier decision;
     reopen and remediate it".
   - Trellis frames this as view maintenance and auditing, not agent behaviour, and it does not build it.
4. **Its only experiment supports the baseline side.**
   - Retrieval-injected cross-session memory (vector-seeded, RAG-like) gives about 10x faster convergence and 52% lower
     tokens per valid node.
   - Time travel plays no role in the measured gain.
   - It also reports an anchoring cost of reuse (the single best solution came from no memory). That is a known failure
     mode, and the project's baseline should be tuned against it (the injection rate p is a knob).

## What Trellis does NOT cover, and where a residual hypothesis can live

- **Who uses the temporal machinery.** In Trellis, AS-OF reconstruction serves training extraction, replay, observability,
  audit and recovery. The agent never queries its own past epistemic state while deliberating, and never asks "would my
  earlier self, with only what it knew then, have decided differently?" The agent process is stateless by design.
- **No behavioural evaluation of temporal navigation.** Nothing measures whether as-of access improves an agent's decisions
  or its detection of stale decisions. AS-OF correctness is not measured either.
- **Single-axis time.** Only logical evaluation order is versioned. The authors explicitly leave valid time versus
  transaction time, late corrections, and "was it still true?" open. Neither the external world state nor ground-truth
  change is versioned.
- **The domain is sandboxable optimisation with objective rewards** (kernels; silicon bug-hunting). There, every branch can
  be executed and scored, so prospection, forecasting and counterfactual reasoning about irreversible past actions are
  unnecessary. The project's setting, a long-lived agent on one real timeline where later events re-value earlier
  committed decisions, is not addressed.
- **The prospective side is absent.** Trellis has no:
  - future-state rollout or multiple imagined futures;
  - probabilities over futures;
  - backward requirements;
  - intervention-aware forecasts;
  - preserved prevented futures;
  - predicted-versus-realised calibration.
  Value models and confidence-bearing leaderboards appear only on the agenda.
- **Identity and objective drift.** Trellis versions skills and records the algorithm per session. It does not track the
  instructions, policy or model governing the agent over time, or analyse their changes.
- **Artefact status.** It is a vision-style systems paper with preliminary results. No official code was found; there is
  an unofficial reproduction in lmccccc/XEvolve. Only the cross-session reuse claim has numbers, from 3 sessions per
  configuration on one task family.

## Net assessment

The threat is **HIGH for the architectural or infrastructure framing**: time-indexed agent state, as-of reconstruction
with no-hindsight rationale, fork and lineage, never-overwrite. The threat is **LOW for the behavioural and prospective
claims**.

After Trellis, along with the LangGraph time travel and Graphiti work being analysed separately, the project should not
claim novelty for the substrate. A surviving hypothesis would be agent-facing and behavioural. Given cutoff-respecting
access to its own past epistemic and policy state, plus forecasts and a way to contrast them, does the agent detect and
remediate earlier decisions whose standing a later event changed? It must do so better than a strong baseline: a
Trellis-style as-of store or versioned RAG, with the retrieval-injection rate tuned.
