# Research landscape, October 2026: temporal agency against prior work

Status: Milestone 2.5 research reset, dated 2026-10-03. Research and
documentation only. No benchmark, baseline, ground-truth or `src/tesseract/`
file was changed.

Companion documents:
- [capability-matrix.md](capability-matrix.md): the 20-capability matrix;
- [NORTH_STAR_V2_PROPOSAL.md](NORTH_STAR_V2_PROPOSAL.md): UX metaphors separated from computational primitives;
- [residual-hypotheses.md](residual-hypotheses.md): hypotheses and the disposition;
- [benchmark-reuse-assessment.md](benchmark-reuse-assessment.md): is the benchmark redundant?;
- [m2.5-decision-record.md](m2.5-decision-record.md): the decision.

The evidence base (notes, verbatim snippets, probe scripts and outputs,
digests, the multi-agent synthesis) is archived in
[`research/m2.5-evidence/`](../research/m2.5-evidence/README.md).

---

## 0. Summary

The question was whether "explicit temporal navigation" still names a
distinct research hypothesis once 2025-2026 work is counted. The answer is
**no for concepts and mechanisms. Only narrow empirical questions remain.**

- **Every operation NORTH_STAR §4 assigns to "Tesseract" ships in open
  code.** That covers `state_at`, `diff`, `trace`, `fork_from`, `compare` and,
  as a composition, `past_self`.
  - ActiveGraph [code] provides append-only event-log state, `fork(at_event)`
    with lineage, as-of projection and diff.
  - LangGraph [code] provides checkpoints, replay and `update_state` forks.
  - Memvara [code] provides `valid_at` / `known_at` / `as_of` reads and
    `ask()` readings of now, then and stated.
  - Shepherd [abs; experiment code] forks the process, the context and the
    filesystem together.
- **The historical-state-fidelity triad EXPERIMENT.md §11 scores is a shipped
  library API.** The triad is true then / known then / known now about then.
  Memvara's `ask(at=T)` returns exactly those three readings and a
  "diverged" flag [code].
- **Reopening an earlier decision when later evidence invalidates its basis is
  published, with code, through dependency tracking rather than time.** See
  PlanFence [abs], Corollary [code], DeepRewind [abs, code] and MemTX [abs].
  FlowState's motivating example has the same structure as `smoke_v1`'s
  premise [ext].
- **The future side is classical.** Every piece of it already exists:
  - action-conditioned rollout (Imagine-then-Plan [code]; RAP, WebDreamer, WMA);
  - receding-horizon control (RAFA);
  - goal regression (BAR [abs]);
  - option preservation (relative reachability, AUP; SafeCommit and LCPI [abs]);
  - feared-future constraints (SafePred, SIMMER, JANUS [abs]);
  - prospective memory (PM-Bench [code]; PIS [abs]);
  - "prevented futures": conditional-forecast annulment and potential
    outcomes (Metaculus [ns], Dickerman & Hernán [ns]).
- **Every unification attempt reduces to composition.** "Never overwrite time,
  fork it" is event sourcing plus bitemporality plus Git-style branching plus
  PROV provenance.
- **Nearby measured comparisons lean toward the null. None measures decision
  reopening itself.**
  - Memvara's own benchmark gives bitemporal memory a lead of 92.0 vs 89.0
    over one-clock RAG. The whole lead comes from 4 delayed-knowledge or
    correction questions [code].
  - Forecast-Dojo: a carried belief notebook "lowers research cost but does
    not consistently improve forecast quality" [abs].
  - GitOfThoughts finds that, on novel problems, "no memory format reliably
    helps", a versioned git substrate included [abs].
  - STALE locates the failure in acting on evidence, not in reaching it [abs].
- **The one real capability gap is not a temporal one.** It is noticing,
  unprompted, that a later event changes an earlier decision's significance
  when no dependency was recorded and no fact is contradicted. Every
  dependency-tracking mechanism found needs the link recorded or declared.
  Nothing ties the gap to temporal navigation.

The most threatening prior work is Memvara, ActiveGraph, Shepherd, the
dependency-tracking cluster (PlanFence, Corollary, DeepRewind, MemTX) and
FlowState. The ranking is in §6.

---

## 1. Method and evidence limits

**Scope.** The nine mandatory systems listed in the milestone prompt, then a
ten-lane sweep of adjacent work:
- execution state;
- belief state;
- temporal memory and bitemporal databases;
- counterfactuals and world models;
- prospective cognition and forecasting;
- backward planning and optionality;
- performative prediction and prevented futures;
- benchmarks;
- identity and policy drift;
- epistemic cutoff and hindsight.

**Process.** Each phase ran as a multi-agent workflow:
1. Primary-source reads of the nine mandatory systems. Each read was followed
   by an independent verifier that tried to refute its ratings; 6 of 180
   ratings were changed.
2. A ten-lane sweep: 140 distinct works, with 12 deep reads covering 11
   works.
3. An adversarial synthesis. It ran in four stages:
   - a composition attack, a steelman, a future-side analyst, a benchmark
     assessor and a UX analyst;
   - three track proposers (historical, prospective, unified);
   - three judges with different lenses;
   - a decision maker, a dissenter and a final reconciler.

**Access limits.** These are significant, and they are stated plainly.
- The container's egress policy blocked arxiv.org, export.arxiv.org,
  huggingface.co, alphaxiv.org, semanticscholar.org, openreview.net,
  docs.langchain.com and *.github.io. **No arXiv full text was read
  directly.**
- WebSearch worked server-side until the session budget (200 calls) ran
  out, partway through the deep reads.
- What remained available:
  - `git clone` of public GitHub repositories, used for code and docs of
    LangGraph, Graphiti, PoS, ITP, PM-Bench, MemoryArena, ActiveGraph,
    Shepherd, Memvara, Corollary, DeepRewind, FutureSim, XTDB, Datomic and
    others;
  - raw.githubusercontent.com;
  - PyPI;
  - microsoft.com, for MAGE's publication page and verbatim abstract;
  - a local corpus of **117,831 verbatim arXiv cs.AI/cs.CL listings**
    (Dec 2024 to Sep 2026), parsed from a GitHub-hosted daily-listing mirror.
- **Consequences:**
  - Paper bodies were usually unread.
  - Many headline numbers are abstract-level.
  - cs.LG-only and pre-2025 work is under-sampled.
  - 2026 work that uses this project's own vocabulary may have been missed.

**Citation check.** Every arXiv id the sweep cited was looked up in the
corpus.
- 91 of 118 matched on both id and title.
- 27 were absent. Most are pre-2025 or cs.LG work outside the corpus, such as
  performative prediction 2002.06673, relative reachability 1806.01186, LATS
  and RAP.
- One cited id, `2025.10122` for van Amsterdam et al., is malformed and is
  not used. The same paper appears elsewhere as 2312.01210, also unverified.

**Evidence labels** used in all M2.5 documents:

| label | meaning |
|---|---|
| [code] | read or executed in a cloned repository or its docs (probes are in the evidence archive) |
| [abs] | arXiv id and title verified in the local corpus; claim taken from the verbatim abstract |
| [ext] | WebSearch extract of the arXiv HTML page (a summarizer's restatement, often near-verbatim) |
| [3p] | third-party mirror, digest or PDF conversion |
| [unv] | arXiv id not verified locally (pre-2025, outside cs.AI/cs.CL, or post-corpus); cited from agent notes |
| [ns] | non-arXiv source (docs, journal DOI, product documentation) |

---

## 2. The mandatory systems

The ratings below are the verified ratings from the capability matrix. "Covers"
and "does not cover" refer to NORTH_STAR.md.

### 2.1 MAGE: memory as execution-state management (arXiv 2606.06090, Microsoft Research)

**Sources.** The abstract is verbatim from the Microsoft Research publication
page [ns]. Mechanism details come from WebSearch extracts of the arXiv HTML
[ext]. No code exists: `github.com/microsoft/MAGE` is an unrelated multimodal
project.

**Mechanism.**
- A per-task, two-layer state tree: raw action-observation nodes at the
  bottom, subgoal summary nodes (with `cover_nodes` and a diagnostic `note`)
  at the top.
- The agent sees S=(C,R,H):
  - C: summaries on the active root-to-current path;
  - R: raw steps since the last compression;
  - H: hints from earlier sibling branches.
- Four operations:
  - **Grow:** automatic, every step.
  - **Compress:** triggered by the agent marking a subgoal done, or by a
    length threshold.
  - **Maintain:** an LLM validates the new summary.
  - **Revise:** "restores a target boundary and resumes on a new branch". The
    flawed segment is kept as an inactive sibling branch, and hints carry
    forward through H.

**Evaluation.** MemoryArena with Qwen3.6-27B and ReAct. The abstract reports
"+7.8–20.4 pp over baselines, while reducing token consumption by 55.1%".
Ablations credit Revise with 4.0 to 5.2 pp of success rate [ext].

**Covers.** "Fork, never overwrite" for the agent's own memory. It also
reopens an earlier boundary when a later check finds it wrong, and empirical
evidence shows path-structured memory beating similarity retrieval.

**Does not cover.**
- It has no epistemic cutoff. H deliberately carries hindsight into restored
  states.
- It does not reconstruct world state, and no environment rollback is
  described.
- It has nothing prospective and no as-of queries.
- It works within a single task episode only.

**Threat.** High for the "reopen and fork" move. A temporal win over a
baseline without path structure would be confounded.

### 2.2 FlowState: execution state as memory (arXiv 2609.34565, Ant Group)

**Sources.** Abstract and metadata come from GitHub-hosted digests [3p]. Method
and results come from WebSearch extracts only [ext]. Code is "to be released".

**Mechanism.**
- Typed state nodes (judgements, preferences, knowledge, attributes) with
  typed relations, including supersedes, tagged with their source request.
  Historical nodes cannot be deleted.
- **Incremental State Update** validates Add/Update/Remove deltas. Update and
  Remove apply only to nodes created in the current request.
- **Progressive State Access** discloses historical states by id or by
  following relations, down to the raw tool observations.

**Evaluation.** With DeepSeek-V4-Flash, against full context: +4.55 pp success
rate on MemoryArena and +13.95 pp pass rate on τ³-Bench, with 43.2% and
40.6% fewer tokens [ext].

**Covers.** Earlier decisions are preserved and reopened with their evidence
chain when new information arrives. The motivating example has decision D7
kept and D8 added after a price change, which is structurally `smoke_v1`'s
premise. Every node's `source_request` makes "known then" a filter.

**Does not cover.**
- no as-of operator or enforced cutoff;
- no branching;
- nothing prospective;
- no world-state history.

The D7/D8 behaviour was **not evaluated in isolation**; only aggregate
metrics were reported.

**Threat.** High. It is a published structured-state alternative explanation
for any temporal-contestant win.

### 2.3 LangGraph persistence and time travel (langgraph 1.2.12, langgraph-checkpoint 4.2.0) [code]

**Sources.** Code and docs, cloned, plus five executed probes.

**Mechanism.**
- A checkpoint at every super-step, keyed by (thread_id, checkpoint_ns,
  checkpoint_id). It holds channel values and versions, `versions_seen`,
  pending writes, and metadata (source, step, parents).
- **Replay** (`invoke(None, past_config)`) writes a `source="fork"` checkpoint
  and re-executes every node after the checkpoint. LLM and tool calls run
  again, side effects repeat, and interrupts re-fire.
- **`update_state(past_config, values, as_node)`** writes a
  `source="update"` child checkpoint that becomes the thread head. The
  original stays reachable.
- Subgraphs are checkpointed under `node:task_id` namespaces.

**Not preserved.**
- external side effects;
- nondeterministic model outputs (except under the opt-in node cache);
- the long-term Store, which is overwritten in place, so a probe's replay
  read the *present* Store;
- code, prompt or model versions;
- decision rationale;
- beliefs.

**Covers.** "Never overwrite time, fork it" for execution state. Fork reasons
can be attached as filterable metadata, and server-side assistant versioning
tracks configuration.

**Threat.** High for the retrospective half. `get_state(checkpoint)` is
`state_at` with a natural cutoff on whatever the graph held.

### 2.4 PoS: explicit belief states (arXiv 2610.01415, Nankai, Alibaba and Tsinghua)

**Sources.** The official code and project page (`luoyu100/PoS`) [code]. The
paper body was unread.

**Mechanism.**
- B_t = (W_t, G, Δ^E_t, Δ^A_t):
  - W_t: an entity/state/relation world graph. Each record has a probability
    and an observed/inferred tag;
  - G: a fixed goal;
  - Δ^E_t: epistemic gaps;
  - Δ^A_t: achievement gaps;
  - one Active Gap.
- A "Belief Sentinel" audits each delta for internal contradiction and for
  contradiction with the raw trajectory, using quote grounding.
- "Belief trapping" (static, cycle or drift) is detected over K=8 snapshots
  and triggers recovery constraints.

**Evaluation.** Best in all 12 benchmark × backbone settings: ALFWorld,
LOCA-Bench, RCA-100 and ClinDiag, against ACON, PACE, HiAgent and
LongHorizon-Harness. The cost is about 5× total tokens on RCA-100. These
figures are the authors' transcription in the repo.

**Covers.** An explicit present belief state with uncertainty, open
questions and obligations.

**Does not cover.** It is strongly present-centric:
- beliefs are overwritten in place, with no time fields;
- no fork, replay or prospection.

**Threat.** It is evidence that a better *present* beats better access to the
*past*, and it is a confound for any temporal win.

### 2.5 Graphiti / Zep: temporal context graph (Graphiti v0.30.2; Zep, arXiv 2501.13956) [code]

**Sources.** The code was read. Only the paper's abstract was read, from a
screenshot in the repo.

**Mechanism.**
- Fact edges carry `valid_at`/`invalid_at` (world time, extracted by an LLM)
  and `created_at`/`expired_at` (transaction time, from the wall clock).
- A contradiction judged by the LLM invalidates the older edge; nothing is
  deleted.
- Episodes give provenance. Backdated facts are reconciled on valid time.
- Edge search accepts date filters on all four timestamps.
- Default retrieval returns invalidated facts.
- Nodes are upserted in place.

**Covers.** Bitemporal world facts with provenance. The shipped MCP server
also stores procedures and requirements as typed, validity-windowed memory.

**Does not cover.**
- agent decisions or beliefs as versioned state;
- forks;
- anything prospective;
- changes of significance without a contradiction.

### 2.6 COUNTERMEM: world-model-verified counterfactual memory (arXiv 2609.31874)

**Sources.** The verbatim abstract only, from GitHub mirrors [3p]. No code is
public. Its arXiv comment says "ICLR 2027", probably meaning a submission.

**Mechanism.**
- After a failed action, the system copies or resets the original state and
  tries local alternative actions.
- Each alternative is checked by an *executable* world model: tests, proof
  checkers or solvers.
- Only improvements are stored, each as (original action, corrected action,
  checked outcomes, conditions for reuse).
- An RL-trained selector picks a record or skips memory.

**Evaluation.** With gpt-oss-120b: +12.6 pp on average over ReAct and
Reflexion across 12 settings, with 7.7–42.0% fewer task-run tokens.

**Covers.** Counterfactual action branches from a historical state, verified
and persisted.

**Does not cover.**
- an epistemic cutoff (it uses hindsight by design);
- branch histories with provenance;
- anything prospective.

### 2.7 Imagine-then-Plan (arXiv 2601.08955; code `loyiv/ITP`) [code]

**Mechanism.** A world model, LoRA-tuned on (state, action) → next-state text
from expert trajectories, imagines a K-step future before each action.
- **ITP-I:** the LLM chooses K and pastes one greedy foresight text into its
  prompt.
- **ITP-R:** a learned K-head and value head, trained with pseudo-labels that
  use hindsight from expert trajectories, then online A2C with a cost on K.
- **What it does not do:**
  - Only one imagined trajectory is produced. It is not scored, branched or
    kept.
  - Imagined futures are dropped from context and never compared with
    reality.
  - There is no backward reasoning.

**Evaluation.** ALFWorld overall, with ITP-R: 85.07 / 88.57 / 87.14 on three
7-8B backbones. On Qwen3 ScienceWorld-unseen, RAP beats ITP-I (27.14 vs
19.86).

**Code concerns.**
- The released ALFWorld evaluation's action-parsing regexes never match.
- The README's RL example trains on the evaluation split.
- One Table 1 row is internally inconsistent.

**Threat.** Simulate-then-act from the present is established. Large gains
came from the *cheapest* lookahead.

### 2.8 PM-Bench: prospective memory (arXiv 2607.12385; code `genglinliu/PMBench`) [code]

**Setup.** One deterministic synthetic week: 80 steps and 83 intentions (57
event-based, 26 time-based). It has hidden clocks and channels, 11 explicit
updates, and lures. Scoring is per-step Set-F1.

**Results.** Across 8 models and 8 configurations (64 runs), the best is
heartbeat-proactive at 65.1% macro Set-F1, and the best single run is 79.1%.
Hidden channels are almost never caught (16.7%).

**Prospective memory is not forecasting.** It means remembering to act on an
intention, not predicting or simulating a future. Updates apply only to
*pending* intentions; updates to completed tasks are ignored. A follow-up,
PIS (arXiv 2609.01272) [abs], reaches 82.9% Set-F1 with a typed intention
store whose lifecycle logic is in code. Structured present state beats LLM
memory scaffolds.

### 2.9 MemoryArena (arXiv 2602.16313, ICML 2026; code `ZexueHe/MemoryArena`) [code]

**What it is.** A benchmark and harness, not a memory system. It has four
domains: bundled shopping, group travel, progressive search and formal
reasoning. Each task is a chain of interdependent subtasks. Memory plugs in
through `add_chunk` / `wrap_user_prompt`.

**Shipped baselines.** Long-context, BM25, embedding RAG, Mem0 and Mem0-graph,
Letta, MIRIX, MemoRAG, a LangChain graph retriever and ReasoningBank.

**What it does not test.** Dependencies run strictly forward. **No
implemented task requires noticing that later information invalidates an
earlier decision.** A travel prompt that would allow revising earlier plans
is dead code, and feedback modes hand the agent ground truth. The repository
has no LICENSE file.

---

## 3. The wider landscape, by lane

Each lane lists the most relevant works found, with evidence labels. Full
entries are in `research/m2.5-evidence/synth/digest_sweep.md`.

### 3.1 Execution state: fork, replay and provenance for agents

- **ActiveGraph**, "The Log is the Agent" (2605.21997) [abs, code]:
  - the event log is the source of truth;
  - `Runtime.fork(at_event)` copies the log up to and including `at_event`
    and replays it;
  - lineage is recorded as (parent_run_id, forked_at_event_id);
  - forks can be structurally diffed and promoted back with a fail-closed
    three-way merge;
  - the docs say: "Hypothesis testing on an agentic system, without losing
    the parent run";
  - a probe found that fork caches pre-filled from the parent's *full* log
    can leak a post-cutoff observation.
- **Shepherd** (2605.10913, Stanford/Northeastern) [abs; experiment code]:
  - a typed, Git-like execution trace;
  - process, context and filesystem forks in about 134-143 ms;
  - "gate before escape" for external effects;
  - counterfactual replay optimization;
  - the public library v0.3.1 lists replay as a "direction".
- **Others:**
  - AgentGit (2511.00628) [abs];
  - OpenHands SDK event sourcing (2511.03690) [abs];
  - C3 (2603.06859) [abs; quote from its README, code]: "the counterfactual is executed rather than
    predicted";
  - Causal Agent Replay (2606.08275) [abs];
  - formal checkpoint, fork and merge semantics, e.g. "When Can Agents Safely
    Checkpoint, Fork, Restore, and Merge?" (2608.22928) [ext].
- **ChronoMem** (2607.27773) [abs] snapshots memory on every write and scopes
  reads after rollback. Its "post-exposure" protocol tests whether behaviour
  leaks post-cutoff information. Prompt-only rollback scores far below
  snapshot restore; those numbers come via a secondary reader.
- **Trellis / Experience Graphs** (2606.29823, Meta + UMD) [abs] describes
  "what an agent knew at any past step" as an AS-OF query. It is a design for
  developers and training only and was never evaluated.
- **Lane verdict.** Append-only histories, as-of reconstruction, forks with
  lineage, diffs and counterfactual re-execution are published and mostly
  open-sourced. "Fork / replay / provenance" cannot be claimed.

### 3.2 Belief state and dependency-tracked revision

- **Benchmarks:**
  - STALE (2605.06527) [abs]: 400 scenarios on "implicit conflict", where a
    later observation invalidates an earlier memory without explicit
    negation. The best model scores 55.2%, and there is "a pervasive gap
    between retrieving updated evidence and acting on it".
  - StateMemBench (2608.19652) [abs]: "facts, constraints, and decisions are
    revised".
  - ClawArena (2604.04202) [abs].
- **Mechanisms that reopen dependents when a premise changes:**
  - PlanFence (2609.03340) [abs]: in 30 live workflows, a freshness-only
    executor "acts on the obsolete plan in every task, whereas PlanFence
    completes all tasks without an invalid action".
  - MemTX (2607.23929) [abs]: typed cascading repair, including tool side
    effects.
  - DeepRewind (2609.36344) [abs, code]: a typed epistemic graph with
    dependency-aware rollback. A probe found its organic contradiction path
    never fired rollback.
  - Corollary [code]: JTMS truth maintenance for LLM agents, 386 passing
    tests. A probe found that a later fact on a different key leaves a
    decision in force.
- **Versioned belief infrastructure:**
  - Memvara (§3.3);
  - TOKI (2606.06240) [abs];
  - Kumiho (2603.17244) [abs], immutable revisions with belief-revision
    properties;
  - TGMS (2607.10265) [unv].
- **Lane verdict.** Explicit current belief state, implicit-invalidation
  benchmarks, cascading repair, and even "what did the agent believe at t"
  are all established. What remains is a behavioural, empirical question.
  Whatever the project attributes to time may in fact come from dependency
  links.

### 3.3 Temporal and versioned memory, and its database foundations

- **Databases:**
  - XTDB [ns, docs] is bitemporal by default. Its docs present
    `FOR SYSTEM_TIME AS OF` as the way to see data "as we knew it at the
    time, without subsequent corrections", including leakage-free
    backtesting.
  - Datomic [ns] offers `as-of`, `since`, `history` and speculative `d/with`.
  - Event sourcing gives state-at-version.
  - Dolt and lakeFS give branch, diff and merge of data.
  - W3C PROV gives `wasRevisionOf` and `wasInvalidatedBy`.
- **Agent memory:**
  - Memvara [code], Apache-2.0, v0.19.0:
    - `valid_at=` means "what we believe today about T", `known_at=` means
      "what we believed at T", and `as_of=` sets both clocks;
    - `ask(at=T)` returns now / then / stated readings and a `diverged` flag,
      documented as "the record changed under a decision somebody already
      made";
    - superseded claims are "ended" (the world changed) or "retired" (the
      record was wrong);
    - **its own cross-system benchmark** scores Memvara 92.0%, a one-clock
      append-only vector-RAG 89.0% and a naive overwrite store 50.0%. Its
      README says the temporal category "is the whole of memvara's lead", and
      the four questions vector-RAG misses are the delayed-knowledge and
      correction ones. On `knowledge_time` both score 100%;
    - caveats: the maintainers wrote the corpus, and the baseline embedder is
      hashed TF-IDF.
  - Graphiti/Zep (§2.5).
  - MemStrata (2606.26511) [abs; numbers via a list summary] reports large
    gains over a similarity-only RAG on evolving software facts.
- **Lane verdict.** "Never overwrite time, fork it" is event sourcing plus
  bitemporality plus Git-style branching plus PROV. The slogan is not a new
  computational abstraction.

### 3.4 Counterfactual reasoning and world models

- **Tree search with backtracking:** LATS, RAP (both [unv]) and later
  successors.
- **Branching from the first error:** Agent-R (2501.11425) [abs].
- **Executed counterfactual replay:** C3, Causal Agent Replay.
- **LLM world models:**
  - WebDreamer, WMA [unv];
  - WebEvolver (2504.21024) [abs];
  - Dyna-Think (2506.00320) [abs];
  - WALL-E 2.0 (2504.15785) [abs], which repairs its world model from the gap
    between predicted and actual trajectories.
- **Lane verdict.** Branching from past states and simulating alternatives is
  standard. Two things were not found: branches kept as a lifelong,
  queryable store with provenance, and any revisiting under a strict cutoff.
  Every work found uses outcome hindsight by design.

### 3.5 Prospective cognition, forecasting and future-self interfaces

- **FutureSim** (2605.15188) [abs, code]:
  - replays real news with date-capped search;
  - keeps an append-only `PredictionHistory` with `get_prediction_as_of`;
  - gives daily feedback of the form "Your prediction distribution ... |
    Truth ... | Brier";
  - the best agent reaches 25% accuracy.
- **Forecast-Dojo** (2609.28876) [abs] replays 1,568 Polymarket events with a
  date cutoff and compares memory-free and memory-on agents at identical
  budgets. A carried notebook "lowers research cost but does not consistently
  improve forecast quality".
- **Self-calibration from outcomes:** EpiEvolve (2606.05513) [abs], Live-Evo
  (2602.02369) [abs].
- **"Current Agents Fail to Leverage World Model as Tool for Foresight"**
  (2601.03905) [abs]: agents invoke simulation in under 1% of cases, misuse it
  about 15% of the time, and lose up to 5%.
- **Human future-self interfaces:**
  - Future You (2405.12514) [unv];
  - Simulating Life Paths (2512.05397) [abs].
  They show affective and persuasive effects. The latter "assessed decision
  intentions rather than implemented behaviors".
- **Lane verdict.** Strict-cutoff replay, as-of forecast ledgers and feedback
  from predicted vs realized outcomes ship as benchmark infrastructure. No
  agent interrogates a simulated future version of *itself* with a measured
  benefit. That slot is empty, and nothing supports filling it.

### 3.6 Backward planning, option preservation, irreversibility

- **Goal regression:** classical regression planning; BAR (2505.14079) [abs]
  plans "starting from the terminal state".
- **Option preservation from imagined future goals:**
  - relative reachability (1806.01186) [unv];
  - AUP (1902.09725) [unv];
  - Heitzig & Potham (2508.00159) [abs].
- **Receding horizon:** RAFA (2309.17382) [unv], "reason for future, act for
  now", with √T regret.
- **Feared futures as present constraints:**
  - SafePred (2602.01725) [abs];
  - SIMMER (2606.14574) [abs]: foresight cuts irreversible failures by up to
    75%;
  - JANUS (2607.19913) [abs].
- **Robust choice across plausible worlds:** SafeCommit (2608.04289) [abs],
  LCPI (2609.36741) [abs].
- **FinalityBench** (2609.04706) [abs] uses a hidden canonical event log,
  delayed and reordered events, irreversible effects, and twin pairs that are
  identical at the decision instant.
- **Lane verdict.** No novelty to defend. The only gap found is that derived
  obligations are used once at decision time and not persisted and
  re-checked. That gap is a typed obligation store plus truth maintenance,
  not time navigation (see residual-hypotheses.md §4).

### 3.7 Reflexive forecasts and prevented futures

- **Potential outcomes.** A forecast is P(Y^a | H_t) for a named strategy a
  (Dickerman & Hernán 2020 [ns]). If the agent takes another action, Y^a is
  *missing*, not falsified.
- **Scoring practice:**
  - Metaculus Conditional Pairs annul the unrealized branch ("It is not
    scored") [ns], and the `forecasting-tools` library ships an ANNULLED
    status;
  - decision markets void the conditional market for the action not taken;
  - the COVID-19 Scenario Modeling Hub scores a projection only where its
    scenario held [ns].
- **Reflexive tier:**
  - performative prediction, Perdomo et al. (2002.06673) [unv];
  - fixed-point scoring, Oesterheld et al. (2305.17601) [unv];
  - the counterfactual oracle, Armstrong (1711.05541) [unv].
- **Clinical "victims of their own success":** Boeken et al. (2403.00886)
  [unv]; Liley et al. (2010.11530) [unv].
- **For agents:** Calibration Is Not Control (2606.21399) [abs] argues that
  the decision object is intervention advantage evaluated by same-prefix
  branching. Recalibration "leaves control regret unchanged": 0.506 → 0.110
  on ALFWorld comes from changing the decision object, not from calibration.
- **What the literature adds against the project: positivity.**
  - An agent that always intervenes when its forecast fires cannot verify,
    from its own data, that the averted outcome would have happened.
  - "Prevented" and "false alarm followed by a harmless intervention" look
    identical.
  - So NORTH_STAR §8's "Future A remains a valid prevented future"
    overclaims. The correct status is *annulled / unverifiable*, unless the
    agent randomizes, holds out cases, or has a trusted simulator.

### 3.8 Identity, objective and policy over time

- **Recording which agent version, prompt version, instructions and model
  governed a span:**
  - OpenTelemetry GenAI semantic conventions [ns];
  - MLflow, Langfuse and LangSmith assistant versioning [ns].
- **Research:**
  - AER (2603.21692) [abs]: decision records with plan versions, rejected
    alternatives and the authority chain. It argues that reasoning provenance
    cannot be reconstructed from computational state.
  - Goal drift, Arike et al. (2505.02709) [abs].
  - Revoked but Still Authoritative (2609.08258) [abs]: a retrieval guard
    fixes much of the acting-on-revoked-policy failure.
  - FiscalQA Pro (2608.09393) [abs]: as-of rule lookup reaches 98.3% with
    versioned retrieval.
- **Lane verdict.** Solved as data and attribution. What remains is
  behavioural.

### 3.9 Epistemic cutoff and hindsight

- **Point-in-time models:** Time Machine GPT, ChronoGPT, DatedGPT and others
  (listed in the pitllm bibliography).
- **Prompted cutoffs leak:**
  - Simulated Ignorance Fails (2601.13717) [abs];
  - date-filtered search leaks too.
- **Retained KV cache defeats transcript rollback,** including under
  LangGraph time travel: Aborted but Not Forgotten (2608.15939) [abs].
- **The working method is a separate call on a restricted context:**
  - Self-Blinding (2601.14553) [abs], which queries "a blinded replica"
    rather than instructing the model to ignore information;
  - clinical temporal masking (2609.13454) [abs]: "temporal masking reduces
    bias without lowering accuracy".
- **Lane verdict.** "Ask the past self with a strict cutoff" is a recognised
  problem with known methods and known failure modes. In a synthetic world,
  leakage of the outcome from model weights is moot. The remaining channels
  (context, memory, cache, serving state, policy changes) are exactly the
  ones prior art already names.

### 3.10 Benchmarks

See [benchmark-reuse-assessment.md](benchmark-reuse-assessment.md). In short,
every component of `smoke_v1`'s construct has a 2026 benchmark, but no
benchmark combines all of them:
- unprompted per-decision reopen recall and precision, with negative
  controls;
- a three-way fidelity probe;
- executable remediation in one software world.

That combination is integration.

---

## 4. Attacking the novelty: the composition test

The milestone asked whether the whole idea can be reproduced by composing:

> (MAGE or FlowState) + LangGraph checkpoint/fork + PoS belief state + Graphiti
> temporal facts + COUNTERMEM counterfactual branches + Imagine-then-Plan rollout

**Six-system composition.** It reproduces:
- the retrospective substrate;
- a present belief state;
- bitemporal facts;
- verified counterfactual repair;
- action-conditioned lookahead.

It leaves out:
- cutoff discipline: MAGE and COUNTERMEM inject hindsight on purpose,
  Graphiti leaks later `invalid_at` values, and LangGraph replay reads the
  present Store;
- prospective bookkeeping: forecast records, annulment, predicted vs
  realized;
- identity tracking.

**Extended with the strongest works found in the sweep**, the stack covers
every NORTH_STAR section and invariant:
- ActiveGraph or Shepherd for fork and replay;
- Memvara or XTDB for known-then and true-then;
- ChronoMem for cutoff-scoped reads;
- DeepRewind, PlanFence and Corollary for reopening;
- FutureSim for predicted vs realized;
- Calibration Is Not Control, potential outcomes and Metaculus annulment for
  intervention-conditioned and prevented futures;
- relative reachability, AUP, SafeCommit and LCPI for optionality;
- OTel and AER for identity and policy.

The attack mapped 47 items: §1-§17, the ten invariants of §19, and
EXPERIMENT.md §1. Each item's residual (what is left of it) was classified:

| residual | items | examples |
|---|---|---|
| nothing | 15 | Chronicle; `state_at`; `diff`; `trace`; `fork_from`; predicted-vs-realized; invariants 1, 2, 4, 5, 7, 9, 10 |
| terminology | 9 | "family of selves"; "present as control surface"; the five future-self questions of §6; the reflexivity taxonomy; irreversibility/optionality |
| UX | 1 | the "temporal dialogue" (§14) |
| integration | 18 | the S_t 8-tuple as one object; the temporal graph; Historian; `past_self`; `compare`; TVA; backward requirements; prevented futures; identity; the §15 loop; §16 operational time; temporal multiplicity; invariants 3, 6, 8 |
| measurable effect | 2 | an executable past self vs retrieval over equally rich records (§5); interrogating simulated future selves (§6) |
| capability | 2 | runtime detection of reflexivity (§9; collapses to policy-conditioned forecasting for a single agent); EXPERIMENT §1: detecting changed significance through *implicit* links (not specific to time) |

**Classification of what remains** (the milestone's categories):

| category | verdict |
|---|---|
| novel terminology | yes: Chronicle / Historian / Tesseract / TVA, "selves", "prevented future" |
| novel UX | possibly: "talk to my past/future self" as an interface. No evidence it improves decisions; human studies show persuasion effects. |
| novel integration | yes: one runtime enforcing all ten invariants, plus persisted averted-forecast and derived-obligation records. The temporal-memory lane calls these "thin schema additions". |
| novel architecture | no: every component and every combination named in NORTH_STAR maps to shipped or published mechanisms |
| novel capability | no capability attributable to temporal navigation. The one real gap, implicit significance detection, is a relevance and judgement problem. |
| novel measurable effect | untested. Two narrow empirical questions remain (residual-hypotheses.md); the evidence leans toward the null. |

Integration alone does not justify the project. Nothing in the evidence shows
that this integration creates a new capability or a substantial gain in
performance or efficiency.

---

## 5. Evidence on effect sizes (null and negative results)

These results matter more than the mechanism catalogue. They bound what a
temporal architecture could plausibly win. **None of them measures decision
reopening directly.** They concern nearby constructs, and they are mixed.

| result | source | relevance |
|---|---|---|
| Bitemporal 92.0 vs one-clock append-only RAG 89.0. The whole lead is 4 delayed-knowledge or correction questions; `knowledge_time` is 100 vs 100. | Memvara benchmark [code] (self-authored corpus; hashed TF-IDF baseline) | "What did I know then" is cheap. Two clocks matter only when valid time and transaction time diverge. |
| A carried belief notebook "lowers research cost but does not consistently improve forecast quality". | Forecast-Dojo [abs] | The closest matched-budget test of carried state against date-filtered retrieval. Effect on quality: none consistent. Effect on cost: lower. |
| On novel problems, "no memory format reliably helps" across five substrates, including a versioned git one; memory pays only for near-duplicate cases. | GitOfThoughts (2606.14470) [abs] | A direct prior null for "versioned history improves accuracy". |
| No memory 21/180; verbatim event memory 82/180; typed+raw 83/180; one Mem0 configuration 97/180. "Does not establish ... superiority among memory-bearing conditions." | DreamBench-SWE (2608.20664) [abs] | A software world with hidden oracles. Memory helps; architectures are not separated. |
| "A pervasive gap between retrieving updated evidence and acting on it"; best model 55.2%. | STALE [abs] | The failure is in acting, not in reaching the past. |
| Agents invoke simulation in under 1% of cases, misuse it about 15% of the time, and lose up to 5%. | 2601.03905 [abs] | Prior against foresight machinery. |
| +15 to +32 points attributed to "state structure rather than added context" (length- and cost-matched). | StateMemBench [abs] | Structure, not added context, carries the gains. No time-indexed arm was compared. |
| Freshness-only executor: obsolete plan in every one of 30 workflows; PlanFence: none. | PlanFence [abs] | Dependency links solve the stale-premise case without time. |
| Typed intention store: 82.9% Set-F1 on PM-Bench. | PIS (2609.01272) [abs] | Structured present state beats LLM memory scaffolds on prospective obligations. |
| Recalibration "leaves control regret unchanged". | Calibration Is Not Control [abs] | Predicted-vs-realized calibration has no value claim unless tied to action choice. |

---

## 6. Prior work ranked by threat to the thesis

1. **Memvara** [code]. It ships the EXPERIMENT §11 triad (true then / known
   then / known now about then) as `ask()` readings, plus a "diverged" flag.
   Its own benchmark puts the two-clock advantage in a narrow regime.
   - Caveat: "diverged" is computed at query time. Nothing writes
     fact-to-decision links or triggers reopening.
2. **ActiveGraph** [code] and **Shepherd** [abs]. They provide the Tesseract
   operations as a runtime: fork at any event with lineage, as-of projection,
   diff, replay, and process-level forks.
3. **The dependency-tracking cluster: PlanFence, Corollary, DeepRewind,
   MemTX.** They reopen decisions when a recorded premise changes, with no
   time machinery. The project's behavioural claim needs this as its strong
   null.
4. **FlowState** [ext]. Its motivating example has the same structure as
   `smoke_v1`. It is a structured-state explanation for any win.
5. **PoS** [code]. A better present beats better access to the past.
6. **The causal-inference and forecasting literature** (potential outcomes,
   conditional-forecast annulment, performative prediction, Calibration Is
   Not Control). It settles "prevented futures" and the reflexivity taxonomy,
   and adds the positivity limit.
7. **Imagine-then-Plan with RAP, WMA, SafePred and SIMMER.** It settles
   "simulate futures, act from the present".

---

## 7. Known gaps in this review

- **Paper bodies unread:** MAGE, FlowState, PoS, Zep, COUNTERMEM, ITP,
  PM-Bench, MemoryArena, DeepRewind, ChronoMem, Calibration Is Not Control
  and others. Ratings rest on code where it exists, otherwise on abstracts or
  search extracts.
- **Under-sampled:** pre-2025 and cs.LG/cs.RO/cs.DB-only work, including
  classical work on temporal databases with indeterminate valid time, and
  dynamic adaptive policy pathways ("signposts").
- **Possibly missed:** 2026 work that uses this project's own vocabulary
  ("prevented future", "temporal self"), because WebSearch was exhausted
  before the lanes could run.
- **Unverified:** several citations, listed with [unv] or [3p] labels.
- **Not reproduced:** no result in this review was reproduced, except
  Memvara's benchmark and the probes in the evidence archive.
