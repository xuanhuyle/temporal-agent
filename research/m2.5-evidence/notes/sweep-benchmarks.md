# Sweep: benchmarks lane

Benchmarks for long-horizon agent memory, state and temporal reasoning (2024-2026).
Date: 2026-10-03. Already analysed elsewhere and NOT re-analysed here: MAGE, FlowState, LangGraph time travel, PoS,
Graphiti/Zep, COUNTERMEM, Imagine-then-Plan, PM-Bench, MemoryArena.

## Method and evidence caveat (read first)

- **WebSearch was unavailable.** All 3 calls I attempted returned "this session has used its web search budget (200 of
  200 WebSearch calls)". A broad host-reachability probe (crossref/openalex/etc.) was refused by the sandbox permission
  classifier. I did not retry it by any route.
- **What I used instead.** Every quote below comes from one of these sources. Nothing comes from memory.
  - **[DAILY-ABS]**: the full arXiv abstract, verbatim, from `scratchpad/lit/bo/daily.json`.
    - That file holds 117,831 cs.AI/cs.CL records from Dec 2024 to 1 Oct 2026.
    - A sibling lane parsed it from a git clone of `CSQianDong/Awesome-arXiv-Daily-Reporter`.
    - I queried it with my own scripts, `scratchpad/lit/bench_sweep/bq.py` (regex over title and abstract) and `show.py`.
    - The URL given for each work is that record's `url` field.
  - **[REPO]**: README or source text from repositories I cloned into
    `scratchpad/lit/repos/bench_*`. They are xiaowu0162/LongMemEval, snap-research/locomo,
    HUST-AI-HYZ/MemoryAgentBench, sierra-research/tau2-bench, EternityYW/TRAM-Benchmark, zchuz/TimeBench,
    zhaochen0110/conflictbank, for-ai/MemoryCode, thomasjoshi/agents-never-forget (SWE-Bench-CL) and
    TheAgentCompany/TheAgentCompany.
  - **[DIGEST]**: third-party LLM-written paper digests from `memgrafter/research-digests`, fetched via
    raw.githubusercontent.com into `scratchpad/lit/bench_sweep/digests/`. These are secondary sources and paraphrase
    the papers.
  - **[TITLE-INDEX]**: 133,792 arXiv ids and slug titles (2024-04 to 2026-04), taken from the file names of the same
    digest repo (`bench_sweep/mg_titles.txt`). I used it only to confirm that ids and titles exist.
  - **[IAAR-ZH]**: the Chinese one-paragraph summaries in IAAR-Shanghai/Awesome-AI-Memory (`verify/awesome/iaar.tsv`).
  - **[SIBLING]**: a WebSearch extract recorded by another lane in `notes/sweep-belief-state.md`.

## Ranked works

### 1. TWIST: A Proposed Benchmark for Intervention Quality in Conversational Memory (arXiv 2609.28575, Sep 2026). Threat: HIGH
- URL: https://arxiv.org/abs/2609.28575 . Author: Subrat Panda. Code: not stated ("proposed benchmark suite"; extends the
  LoCoMo harness).
- [DAILY-ABS] "TWIST is a proposed benchmark suite for a complementary, unmeasured property: intervention quality --
  whether a deployed memory system, exercised through its own ingest/recall/vet surface, acts correctly at belief change
  points. Four tracks cover unprompted tension detection, vetting outgoing drafts against the record, answering with
  current beliefs while preserving supersession history, and governing sensitive recall."
- [DAILY-ABS] "pairing every detect/block metric with a matched do-not-over-detect control: surface-matched hard negatives
  price false intervention, so no track can be gamed by flagging everything."
- [DAILY-ABS] "flat-RAG baselines detect 0.76-0.97 of true contradictions but falsely flag 16-43% of surface-matched safe
  drafts depending on backend, while a deployed coherence-oriented system almost never over-flags (0.98-1.00
  specificity) yet catches 42% of true contradictions -- a trade-off no recall-only score can see."
- How it maps to the project:
  - "Unprompted tension detection plus a hard-negative control" is the same construct as the project's temporal
    governance recall plus false intervention rate (EXPERIMENT.md section 11).
  - "Preserving supersession history" is a then-versus-now requirement.
- Where it stops short: it is conversational memory, not decisions. It has no remediation of artifacts and no software
  world.
- Adversarial point: flat RAG already reaches high recall on contradiction detection. The weakness of RAG is precision,
  so the project must win on precision at matched recall, not on recall alone.
- Capabilities: 10, 1 (supersession history kept), 19 (partial).

### 2. STALE: Can LLM Agents Know When Their Memories Are No Longer Valid? (arXiv 2605.06527, May 2026). Threat: HIGH
- URL: https://arxiv.org/abs/2605.06527 . Authors: Hanxiang Chao, Yihan Bai, Rui Sheng, Tianle Li, Yushi Sun.
- [DAILY-ABS] "We identify a critical and underexplored failure mode, Implicit Conflict: a later observation invalidates
  an earlier memory without explicit negation, requiring contextual inference and commonsense reasoning to detect."
- [DAILY-ABS] "400 expert-validated conflict scenarios (1,200 evaluation queries across three probing dimensions) ...
  State Resolution (detecting that a prior belief is outdated), Premise Resistance (rejecting queries that falsely
  presuppose a stale state), and Implicit Policy Adaptation (proactively applying updated states in downstream behavior)."
- [DAILY-ABS] "reveals a pervasive gap between retrieving updated evidence and acting on it, with even the best evaluated
  model achieving only 55.2% overall accuracy ... they struggle to recognize when a change in one aspect of the user's
  state should invalidate related memories."
- [SIBLING] "write-side prototype achieves 91% accuracy on state resolution but only 32% on IPA, and the updated evidence
  is visible in 67.8% of failed IPA cases."
- How it maps to the project: "a later observation implicitly invalidates an earlier item, and the agent must act on it
  proactively" is the project's construct at the level of facts and preferences.
- Adversarial point: the bottleneck is acting on evidence the system already retrieved, not reaching history. That
  weakens "temporal navigation" as the fix. A follow-up, StateAuditor (2608.01619), already reports STALE results.
- Capabilities: 10.

### 3. ClawArena: Benchmarking AI Agents in Evolving Information Environments (arXiv 2604.04202, Apr 2026). Threat: HIGH
- URL: https://arxiv.org/abs/2604.04202 . The abstract says "Code is available at this https URL".
- [DAILY-ABS] "evidence is scattered across heterogeneous sources that often contradict one another, new information can
  invalidate earlier conclusions, and user preferences surface through corrections rather than explicit instructions."
- [DAILY-ABS] "Each scenario maintains a complete hidden ground truth while exposing the agent only to noisy, partial,
  and sometimes contradictory traces across multi-channel sessions, workspace files, and staged updates. Evaluation is
  organized around three coupled challenges: multi-source conflict reasoning, dynamic belief revision, and implicit
  personalization ... Two question formats, multi-choice (set-selection) and shell-based executable checks".
- [DAILY-ABS] "64 scenarios across 8 professional domains, totaling 1,879 evaluation rounds and 365 dynamic updates ...
  belief revision difficulty is determined by update design strategy rather than the mere presence of updates."
- How it maps to the project: it is the closest overall harness. It has hidden ground truth, staged updates, workspace
  files and executable checks, which mirrors the project's isolated world, events, evaluator-only truth and hidden tests.
- Gap: revision is probed by questions, so it is prompted. The targets are conclusions and beliefs, not
  agent-authored decisions. There are no then-versus-now probes.
- Capabilities: 10, 11.

### 4. Can Agent Memory Systems Track Evolving State? (StateMemBench) (arXiv 2608.19652, Aug 2026). Threat: MEDIUM
- URL: https://arxiv.org/abs/2608.19652 . Authors: Xinyi Fan, Miri Liu, Ruozhen Yang, Siru Ouyang, Jiawei Han.
- [DAILY-ABS] "as facts, constraints, and decisions are revised over a long interaction, answers must reflect the current
  state and not a superseded one ... StateMemBench, a benchmark of 234 multi-session scenarios ... Its closed-pool
  grading scores whether an answer reflects the current state, the superseded state, or fails otherwise".
- [DAILY-ABS] "lifting current-state accuracy by +32 to +67 points on StateMemBench across six memory and retrieval
  backends. A length- and cost-matched control attributes +15 to +32 of those points to state structure rather than
  added context."
- [SIBLING] "generates scenarios as symbolic event programs ... derive a 'ground truth' state by replaying the events
  deterministically."
- How it maps to the project: its construction (an event program replayed deterministically into ground truth) is the
  project's construction. The "current vs superseded" grading is a then-versus-now scorer.
- Adversarial point: explicit current-state structure, not history navigation, delivers the gain under a matched
  control.
- Capabilities: 1, 10, 19.

### 5. MEMTRACK: Long-Term Memory and State Tracking in Multi-Platform Dynamic Agent Environments (arXiv 2510.01353, Oct 2025). Threat: MEDIUM
- URL: https://arxiv.org/abs/2510.01353 ([TITLE-INDEX] and the DEEP-PolyU list link). Code: unknown.
  `git ls-remote` on two guessed repo names failed.
- [DIGEST] "simulates realistic enterprise workflows by integrating asynchronous events across Slack, Linear, and Git,
  with noisy, conflicting, and cross-referring information."
- [DIGEST, quoting the abstract] "Each benchmark instance provides a chronologically platform-interleaved timeline, with
  noisy, conflicting, cross-referring information"; "questions are introduced strictly sequentially to remove the
  possibility of preemptive solution planning".
- [DIGEST] "GPT-5 achieves only 60% Correctness"; "Memory backends (MEM0, ZEP) fail to improve performance".
- How it maps to the project: it is the closest software-organisation substrate (tickets, chat and Git events on one
  timeline). It is QA-scored, not decision reopening.
- Adversarial point: the memory backends did not help, which warns against assuming that memory architecture is the
  binding constraint.
- Capabilities: 1, 10, 19.

### 6. FinalityBench: Agent Decisions Under Delayed and Conflicting Financial Finality (arXiv 2609.04706, Sep 2026). Threat: MEDIUM
- URL: https://arxiv.org/abs/2609.04706 . Author: Abhishek Sharma.
- [DAILY-ABS] "It keeps a hidden canonical event log and derives each system's view from a separately faulted delivery
  stream ... Grading is on executed monetary effects".
- [DAILY-ABS] "45 twin pairs (90 tasks): tasks whose four system views are identical at the decision instant, whose
  authoritative probes both return unknown, and whose eventual correct dispositions differ."
- [DAILY-ABS] "Language models ... discover the finality-gating strategy without being told it."
- How it maps to the project:
  - The twin-pair design is a rigorous way to score decisions against "what was knowable at the decision instant".
  - The canonical log is the project's immutable event stream.
- Capabilities: 1, 3, 11.

### 7. MerchantBench: Long-Term Coherence in E-Commerce Operations (arXiv 2607.28956, Jul 2026). Threat: MEDIUM
- URL: https://arxiv.org/abs/2607.28956 . Code: https://github.com/KhanCold/merchantbench (README fetched by a sibling
  lane: `pf_raw/merchantbench_readme.md`).
- [DAILY-ABS] "a persistent environment in which actions constrain future choices, feedback arrives at heterogeneous
  delays ... MerchantBench couples promptly observable Upstream Supplier Events with delayed Downstream Order Outcomes,
  requiring agents to follow individual order lifecycles and revisit earlier decisions."
- [DAILY-ABS] "the best LLM configuration attaining only 27.3\% of the mean final net assets achieved by human
  participants."
- Gap: it is scored only by final net assets. It does not measure explicit reopen events or then-versus-now fidelity.
- Capabilities: 10, 18 (delayed outcomes against earlier decisions, implicit).

### 8. VibeLifeBench: Can Your Life Agent Be Proactive and Persistent in a Living World? (arXiv 2608.10875, Aug 2026). Threat: MEDIUM
- URL: https://arxiv.org/abs/2608.10875 . Code: "We will open-source" (not yet released).
- [DAILY-ABS] "Each task is a scripted multi-week timeline in a simulated world of 22 mock services. The world advances on
  its own clock, and many of its changes are silent, so only an agent that re-inspects the world discovers them. Every
  task is graded by fine-grained, weighted checks that read only what the agent actually left behind, covering the end
  state, the timeliness of its actions, and whether it upheld the implicit constraints."
- How it maps to the project: it tests unprompted noticing of unannounced changes, graded on world end state. The
  domain is personal life, not software decisions.
- Capabilities: 10, 4 (implicit constraints over time, partial).

### 9. Impact Is Not Invalidation: Ask About the Claim, Not the Diff (arXiv 2609.25130, Sep 2026). Threat: MEDIUM
- URL: https://arxiv.org/abs/2609.25130 . Author: Atul Anand.
- [DAILY-ABS] "Memory systems for coding agents must decide, when a repository changes, which of their stored claims have
  become false."
- [DAILY-ABS] "Asked instead whether one specific claim still holds, the same models on the same diffs reach 0.705 to
  0.974 [precision vs 0.291-0.329 for diff-level judging]."
- [DAILY-ABS] "Ground truth is execution, not annotation: a claim is a test function passing at commit t, and it has
  flipped if that same assertion text fails at t+1 ... 10,369 claims with 184 execution-verified flips mined from 23
  Python libraries".
- How it maps to the project: it is a software-world, execution-verified "later change falsifies an earlier stored
  item" benchmark.
- Adversarial point: targeted per-claim re-checking wins. That is cheap and needs no temporal navigation.
- Capabilities: 2, 10, 19.

### 10. EvoCode-Bench: Evaluating Coding Agents in Multi-Turn Iterative Interactions (arXiv 2605.24110, May 2026). Threat: MEDIUM
- URL: https://arxiv.org/abs/2605.24110 . Code: "We release the benchmark data and Harbor multi-turn infrastructure."
- [DAILY-ABS] "can an agent keep its own codebase working as requirements change? ... 26 stateful coding tasks and 227
  evaluated rounds. Each task preserves the agent's workspace for 5-15 rounds, states requirements through observable
  behavior, and uses cumulative executable tests to check new requirements and still-active prior ones."
- [DAILY-ABS] "stronger agents survive long enough to expose specification-tracking and regression failures."
- How it maps to the project: it is a ready remediation scorer (cumulative executable tests over a persistent
  workspace) for "requirement changes". It does not test reopening decisions.
- Capabilities: 4, 10.

### 11. SlopCodeBench: How Coding Agents Degrade Over Long-Horizon Iterative Tasks (arXiv 2603.24755, Mar 2026). Threat: LOW
- URL: https://arxiv.org/abs/2603.24755 .
- [DAILY-ABS] "20 problems and 93 checkpoints, in which agents repeatedly extend their own prior solutions under evolving
  specifications that force architectural decisions without prescribing internal structure ... No agent solves any
  problem end-to-end across 11 models".
- How it maps to the project: earlier architectural decisions meet later specification changes. It is scored by code
  erosion, not by reopening the decision.
- Related: SWE-CI (2603.03823, https://arxiv.org/abs/2603.03823) [DAILY-ABS] "each corresponding on average to an
  evolution history spanning 233 days and 71 consecutive commits"; MaintainBench (2503.24260) "a benchmark comprising
  requirement changes".
- Capabilities: 4.

### 12. Hindsight Bias in Clinical Temporal Reasoning: How Future Data Exposure Affects LLM Judgment (arXiv 2609.13454, Sep 2026). Threat: MEDIUM (for the "known then vs now" metric)
- URL: https://arxiv.org/abs/2609.13454 . Authors: Misaki Matsuura, Sayantan Kumar, Ojas Kadam, Jeremy C. Weiss.
- [DAILY-ABS] "questions are tied to a clinically meaningful cutoff and paired with a prospective reference answer and an
  outcome-consistent hindsight trap. Models answer each question using either a TTS truncated at the cutoff or the
  complete timeline ... We evaluate accuracy (Acc), hindsight trap rate (HTR), answer instability rate (AIR), and
  hindsight bias rate (HBR)".
- [DAILY-ABS] "full timeline exposure produces consistent hindsight-sensitive shifts, while temporal masking reduces bias
  without lowering accuracy."
- How it maps to the project: it is a ready paired design for the project's "historical-state fidelity" metric.
- Adversarial point: plain temporal masking already removes the bias, so no special architecture is needed for the
  cutoff.
- Related: ChronoScope (2604.23051) [DAILY-ABS] "models often drifting toward present-day assumptions despite correct
  underlying knowledge"; HindsightBench (2607.18867) [SIBLING].
- Capabilities: 3, 19.

### 13. DreamBench-SWE: A Multi-Session Memory-Hygiene Benchmark for Software Agents (arXiv 2608.20664, Aug 2026). Threat: MEDIUM (methodology and baseline evidence)
- URL: https://arxiv.org/abs/2608.20664 . Author: Sarthak Singh.
- [DAILY-ABS] "later software tasks depend on non-inferable evidence from earlier sessions and are scored by executable
  hidden oracles ... a separately preregistered v2.1 successor audit designed after that study but frozen before
  successor outcome inspection."
- [DAILY-ABS] "no external memory achieved 21/180 passes ..., deterministic verbatim event memory 82/180 ..., the
  typed-plus-raw reference probe 83/180 ..., and one pinned hosted Mem0 literal-storage configuration 97/180 ... it does
  not establish an external-system mechanism, superiority among memory-bearing conditions".
- How it maps to the project: it has the same research hygiene as the project's CLAUDE.md: frozen scenarios, hidden
  oracles and kept artifacts.
- Adversarial point: verbatim event memory is nearly as good as structured memory, and differences between memory
  systems do not reach significance. That is evidence the project's comparative effect may be small.
- Capabilities: 1, 10.

### 14. LongMemEval (arXiv 2410.10813, ICLR 2025). Threat: LOW (foundational)
- URL: https://arxiv.org/abs/2410.10813 ; code https://github.com/xiaowu0162/LongMemEval (cloned).
- [REPO] "We release 500 high quality questions to test five core long-term memory abilities: ... Knowledge Updates *
  Temporal Reasoning * Abstention"; "attribute-controlled pipeline to compile a coherent, extensible, and timestamped
  chat history"; question types include `temporal-reasoning` and `knowledge-update`.
- Successor: LongMemEval-V2 (2605.12493) [DAILY-ABS] "five core memory abilities for web agents: static state recall,
  dynamic state tracking, workflow knowledge, environment gotchas, and premise awareness".
- Gap: knowledge updates are prompted QA (latest value wins). Nothing is reopened.
- Capabilities: 1, 10, 19.

### 15. MemoryAgentBench: Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions (arXiv 2507.05257, ICLR 2026). Threat: LOW
- URL: https://arxiv.org/abs/2507.05257 ; code https://github.com/HUST-AI-HYZ/MemoryAgentBench (cloned).
- [REPO] "Four Core Competencies for Evaluation: Accurate Retrieval (AR) Test-Time Learning (TTL) Long-Range
  Understanding (LRU) Conflict Resolution (CR)"; "We also newly constructed two datasets **EventQA** and
  **FactConsolidation**."
- [REPO, methods/total_agent_memory.py] "the task prompt tells it that a larger serial number is a newer fact".
- Takeaway: "conflict resolution" here is latest-wins, with recency labelled explicitly in the prompt.
- Capabilities: 10.

## Also checked (lower relevance; URLs from the sources stated)

- **tau-bench / tau2 / tau3-bench**
  - Sources: [REPO] https://github.com/sierra-research/tau2-bench ; tau2 paper https://arxiv.org/abs/2506.07982 .
  - Domains: "airline · retail · telecom · banking_knowledge".
  - Scoring (docs/evaluation.md): "the only thing that matters for scoring is whether the predicted DB end state matches
    the target DB end state and whether the required strings were communicated".
  - README governance note: "results produced with tau2-bench < 1.0.1 are not comparable with >= 1.0.1".
  - Relevance: single-episode policy following. It does not test multi-event reopening. Its end-state grading is a
    reusable pattern.
- **MemoryCode** ("From Tools to Teammates", arXiv 2502.13791)
  - Repo: [REPO] https://github.com/for-ai/MemoryCode .
  - "An **Instruction** is a coding instruction that is introduced in a session by the mentor ... It can be updated
    throughout the dialog history."
  - Relevance: a multi-session coding benchmark with instruction updates, which is prompted compliance, not
    decision reopening.
- **SWE-Bench-CL** (arXiv 2507.00014)
  - Repo: [REPO] https://github.com/thomasjoshi/agents-never-forget .
  - "Tasks within each repository are primarily ordered by their creation date, simulating the natural evolution of a
    codebase".
  - Relevance: it measures forgetting and transfer, not reopening.
- **LoCoMo** (arXiv 2402.17753)
  - Repo: [REPO] https://github.com/snap-research/locomo .
  - "ten conversations ... annotated for the question-answering and event-summarization tasks".
- **Temporal reasoning QA benchmarks.** None involves agents, decisions or state.
  - TRAM (arXiv 2310.00835), [REPO] https://github.com/EternityYW/TRAM-Benchmark : "ten temporal reasoning tasks,
    presented as multiple-choice questions".
  - TimeBench (arXiv 2311.17667), [REPO] https://github.com/zchuz/TimeBench .
  - Test of Time (arXiv 2406.09170) [DIGEST]: "synthetic datasets that avoid reliance on real-world knowledge".
- **Knowledge-conflict and belief-revision benchmarks.** These are static QA or user-belief tracking.
  - ConflictBank (arXiv 2408.12076), [REPO] https://github.com/zhaochen0110/conflictbank : "three main conflict causes:
    misinformation conflict, temporal conflict, and semantic conflict".
  - Belief-R (arXiv 2406.19764) [DIGEST]: "whether models can appropriately update or maintain their prior beliefs".
  - BeliefShift (arXiv 2603.23848) [DAILY-ABS]: "Temporal Belief Consistency, Contradiction Detection, and
    Evidence-Driven Revision".
  - WikiContradict (2406.13805) [TITLE-INDEX].
- **Intent, constraint and staleness benchmarks**
  - IntentFlux (2609.32520) [DAILY-ABS]: "superseded parts of the user's intent continue to influence the final answer or
    tool action".
  - When Stale Constraints Go Unchecked (2608.25553) [DAILY-ABS]: "native allocation produced stale-consistent decisions
    in 77.3%, 74.7% and 74.7% of episodes".
  - Temporal Validity on Real Software Histories (2608.20685) [DAILY-ABS]: "RAG serves the superseded value 36-38% of
    the time".
- **Methods evaluated on small purpose-built benchmarks** (methods, not benchmarks)
  - PlanFence (2609.03340) [DAILY-ABS]: "In 30 controlled live workflows with a post-plan revision, a freshness-only
    executor acts on the obsolete plan in every task".
  - Dependency-Guided Rollback Repair (2608.10502) [DAILY-ABS]: "given a failed execution and diagnosed faulty memories".
    The fault is given to the agent, not noticed unprompted.
  - Correct Now, Insufficient Later (2609.20045) [DAILY-ABS]: a paired-history audit.
- **Long-horizon coherence simulators with delayed consequences**
  - Vending-Bench (2502.15840) [DIGEST]: "misinterpreting delivery schedules, forgetting orders".
  - YC-Bench (2604.01212) [DAILY-ABS]: "adapting when early mistakes compound".
  - AhaBench (2609.05435).
  - CostBench (2511.02734) [DIGEST]: "four types of runtime blocking events".
  - StoryBench (2506.13356) [DAILY-ABS]: "requiring models to independently trace back and revise earlier choices after
    failure". The revision is triggered by failure.
- **Unprompted recognition**
  - KWBench (2604.15760) [DAILY-ABS]: "Same models articulate the relevant game-theoretic concept correctly when asked,
    then fail to apply it unprompted."
- **Memory lifecycle benchmarks**
  - EvoArena (2606.13681).
  - MemOps (2607.12893): "relying on stale values after a correction".
  - WorldMemArena (2605.29341): "revise what has gone stale, and surface the right evidence at decision time".
  - Evo-Memory (2511.20857).
- **ADR-related.** I found no evaluation benchmark for reopening architecture decisions.
  - GADR (2608.17694) [DAILY-ABS]: generates "Nygard-formatted ADR drafts" from meeting transcripts.
  - AssumptionMiner (2607.22898) [DAILY-ABS]: "explicit assumption layer ... targeted regeneration of only the code
    affected by a revised assumption" (180-task benchmark).
  - Design-constraint compliance benchmark (2604.05955).
- **Replay-based evaluation in forecasting** (covered by the prospective lane)
  - FutureSim (2605.15188): "replay real-world events in the order they occurred".
- **Enterprise worlds with exact ground truth**
  - Era by Eon (2609.09853).
  - TheAgentCompany (2412.14161) [REPO].

## Lane answers

### Q1. Does any benchmark test the full construct?

The full construct is: "a later event changes the significance of an earlier decision; the agent must notice unprompted,
reopen it with evidence, distinguish known-then vs now, and remediate". **No benchmark I found tests all five parts
together.** Each part already has a close benchmark, almost all from 2026:

| Part | Benchmarks |
|---|---|
| Later event invalidates or recontextualises an earlier item | STALE (implicit conflict), ClawArena ("new information can invalidate earlier conclusions"), StateMemBench ("facts, constraints, and decisions are revised"), MEMTRACK (conflicting Slack/Linear/Git timeline), Impact Is Not Invalidation (commit falsifies a stored claim), When Stale Constraints Go Unchecked, PlanFence. |
| Unprompted noticing, scored against over-intervention | TWIST (unprompted tension detection with matched hard negatives), STALE IPA, VibeLifeBench (silent changes), KWBench. |
| Reopening an earlier decision | Only implicit or failure-triggered: MerchantBench ("revisit earlier decisions", scored by net assets), StoryBench (after failure), Dependency-Guided Rollback Repair (fault given). No benchmark scores explicit reopen events with recall and precision. |
| Known-then vs now | Clinical Hindsight Bias benchmark (cutoff vs full timeline, hindsight-trap rate), FinalityBench twin pairs (indistinguishable at the decision instant), ChronoScope. None asks the agent to separate "true then / known then / known now about then" for its own past decision. |
| Remediation, scored executably | EvoCode-Bench, SWE-CI, DreamBench-SWE (hidden executable oracles), VibeLifeBench end state, tau2 DB end state, ClawArena shell checks. |

The residual gap is the conjunction:
- the earlier item is an agent-authored or team decision (ADR or ticket) whose premise stays historically true while its
  significance changes;
- reopening is triggered without a prompt and scored per decision for recall and precision, with negative controls;
- remediation is verified by execution.

### Q2. Which benchmark is closest, and what would need adapting?

**Closest overall: ClawArena (2604.04202).** It already has hidden ground truth, multi-channel sessions, workspace
files, staged updates that invalidate conclusions, and shell-based executable checks. To adapt it:
1. Make updates target earlier decision artifacts instead of factual beliefs.
2. Drop the probing questions. Log autonomous reopen actions after each update, following the project's trigger
   protocol.
3. Add negative-control updates.
4. Add then / known-then / known-now probes.
5. Score present remediation with repo tests.

**Closest on the metrics: TWIST (2609.28575).**
- Its "unprompted tension detection" plus "surface-matched hard negatives" is the project's governance recall plus false
  intervention rate.
- It already shows that flat RAG is high-recall but low-precision, while a coherence-oriented system is the opposite.
- To adapt it: move from conversational drafts to decision records, and add remediation.

**Closest on the software substrate:**
- MEMTRACK (Slack/Linear/Git event timelines; QA-only). It would need decisions and actions.
- Impact Is Not Invalidation (execution-verified claim flips between commits). Asking "does decision D's premise still
  hold at t+1?" in place of "does claim C hold?" is close to the project's event classes A, E and G.

**Closest on "known then":**
- The paired cutoff design of the clinical Hindsight Bias benchmark.
- FinalityBench's twin pairs. They can be ported directly to the project's historical-state fidelity metric.

**Practical recommendation:** reuse these designs and cite them as prior art.
- STALE's IPA is the nearest single metric to "notice and act".
- EvoCode-Bench's cumulative tests are the nearest remediation scorer.

**Adversarial evidence against the comparative hypothesis, from these benchmarks:**
- STALE: the evidence is retrieved in 67.8% of failed IPA cases. KWBench: models know the concept but do not apply it
  unprompted. Failures look like action and initiative, not access to history.
- StateMemBench: explicit current-state structure explains the gains in a matched control.
- DreamBench-SWE: verbatim event memory is about equal to structured memory.
- MEMTRACK: Mem0 and Zep do not help.
- TWIST: RAG already catches 0.76-0.97 of contradictions.

## Lane verdict

This lane is crowded in 2026, but the exact construct is not yet benchmarked.

- **What exists.** Benchmarks for later evidence invalidating earlier memory (STALE, ClawArena, StateMemBench, MEMTRACK,
  Impact Is Not Invalidation), unprompted intervention with over-intervention controls (TWIST, VibeLifeBench),
  hindsight-free cutoff evaluation (clinical Hindsight Bias, FinalityBench twin pairs) and executable remediation under
  changing requirements (EvoCode-Bench, SWE-CI, DreamBench-SWE).
- **What none of them combines.** Agent-authored decisions whose premise stays historically true while their
  significance changes, unprompted reopening scored for per-decision recall and precision with negative controls, an
  explicit three-way then/known-then/now fidelity probe, and executable remediation in one software world.
- **So the benchmark's novelty is integration.** It is not a new kind of test, and it must cite TWIST, STALE, ClawArena,
  StateMemBench and FinalityBench as direct precedents.
- **The same literature undermines the architecture thesis.** Across STALE, KWBench, StateMemBench, DreamBench-SWE and
  MEMTRACK, the bottleneck is acting on evidence the agent already has, not reaching the past. The fixes that work are
  explicit current-state structure and targeted re-checking, not temporal navigation. The baseline should therefore
  include explicit state and per-claim re-checking. The distinct hypothesis that remains is narrow: as-of, diff and fork
  access improves unprompted reopen recall at matched precision over such a baseline.

## Queries run (this lane)

Attempted, not executed (WebSearch budget exhausted):
1. [arxiv] "LongMemEval knowledge updates temporal reasoning benchmark long-term interactive memory"
2. [arxiv] "MemoryAgentBench conflict resolution incremental multi-turn memory agents benchmark"
3. "benchmark agent must revisit earlier decision after new information invalidates assumption"

Local IAAR list:
4. titles `bench|benchmark|arena|testbed`
5. zh summaries `(早期|先前|之前|此前|过去|旧)(的)?(决策|决定|结论|判断|计划)|重新(审视|评估|打开|考虑|检查)|回溯|追溯`
6. titles and zh `swe|software|coding|code|repositor|requirement` / `需求变更|需求变化|代码库|仓库|软件`
7. all curated lists: `tau-bench|TRAM|Test of Time|TimeBench|ConflictBank|Belief|MEMTRACK|MemoryAgentBench|LoCoMo|SWE-bench|Evo-Memory`

Title index (133,792 arXiv ids):
8. `memtrack|longmemeval|locomo|memoryagentbench|evo-memory|memoryarena|memorycode|tools-to-teammates`
9. `tau-bench|tau2|dual-control`
10. `knowledge-update|belief-revision|belief-update|stale|outdated|obsolete`
11. `swe-bench|evolving-(code|software|requirement|spec)|requirement change|slop`
12. `architecture-decision|design-decision|decision-record|adr-|technical-debt`
13. `temporal-reasoning bench|test-of-time|timebench|tram|time-sensitive`
14. `knowledge-conflict|conflicting-evidence|contradict bench|conflictbank|wikicontradict`
15. `(revisit|reconsider|retrospect|hindsight|reopen|undo|backtrack).*(agent|llm|decision|bench)`
16. `(dynamic|changing|evolving|non-stationary).*(environment|world|information|state).*(agent|bench|llm)`
17. `(proactive|unprompted|anticipat).*(agent|bench)`
18. `vending|long-term-coherence|delayed-consequence|consequential`
19. `(replan|plan-repair|adaptation).*(bench|agent|llm)`
20. `(assumption|premise|presuppos).*(agent|bench|llm|detect)`
21. `multi-session|cross-session|lifelong.*(agent|bench)|long-horizon.*(memory|bench)`

Daily abstracts (117,831 records):
22. `later (event|evidence|information|observation|update)s? (invalidat|change|alter|undermin|overturn|contradict)`
23. `(earlier|prior|past|previous|original) (decision|choice|commitment|plan|conclusion) ... (revisit|reopen|reconsider|re-evaluat|revis|invalid|outdated|stale|wrong)`
24. `(evolving|changing|shifting|updated|revised|new) (requirement|specification|spec)|requirement (change|drift|evolution)`
25. `silent(ly)? (change|update|drift)|re-?inspect|without (being )?(told|notif|prompt)|unprompted|proactive(ly)? (detect|notice|identif|flag|surface)`
26. `known at (the|decision) time|available at the time|at decision time|hindsight bias|outcome bias|without hindsight`
27. `architecture decision|design rationale|decision record|decision log|ADR`
28. `(Slack|Jira|tickets?|issue tracker|pull requests?)` with `memory|timeline|state|evolv|long-horizon|multi-session|enterprise`
29. `supersed|supersession|retroactive|backdated|late-arriving|out-of-order update`
30. `temporal reasoning` with benchmark
31. `LongMemEval[- ]?V2`
32. `delayed (outcome|consequence|effect|feedback)|actions constrain future`
33. `belief revision|revise (its|their) beliefs|belief update` with benchmark
34. `(reopen|re-open|re-examin|re-audit|revisit) (a|the)? (decision|commitment|ticket|issue|choice|plan)`
35. `(earlier|prior) (decision|assumption) ... (later|subsequent) (event|incident|change)` (0 hits)
36. `(stale|outdated|obsolete|invalidated|superseded) (plan|decision|assumption|commitment|conclusion)`

Repositories:
37. `git ls-remote` on 19 candidate repos. 13 resolved, and I cloned 10 of them.
38. raw.githubusercontent fetch of 8 memgrafter digests: MEMTRACK, Vending-Bench, CostBench, SWE-Bench-CL, Evo-Memory,
    Belief-R, Test of Time, tau2.
