# Sweep: belief-state lane

Explicit belief / epistemic / assumption state maintenance in LLM agents (2025-2026).
Date of sweep: 2026-10-03. Method: 47 executed WebSearch queries (arXiv-restricted and open web) + git clones of two repos
(Corollary, Memvara) under `scratchpad/lit/repos/`. WebSearch budget for the session ran out at the end of the sweep
(3 last queries were not executed: AUQ 2601.15703, A-TMA 2607.01935, Supersede 2606.27472 detail lookups).

Snippet provenance: "search extract" = text returned by the WebSearch tool summarizing the cited arXiv HTML page
(may be lightly paraphrased by the search tool). "README verbatim" = copied from the cloned repository.
Already analyzed elsewhere and NOT re-analyzed here: MAGE (2606.06090), FlowState (2609.34565), LangGraph time travel,
PoS belief states (2610.01415), Graphiti/Zep, COUNTERMEM, Imagine-then-Plan, PM-Bench, MemoryArena.

---

## Tier 1: high threat

### 1. MemTX: Transactional Belief Commit for Stateful Agent Memory (arXiv 2607.23929, 2026)
- URLs: https://arxiv.org/abs/2607.23929 , https://arxiv.org/html/2607.23929v2
- Search extract: "Current agent memory systems treat every accepted write as immediately actionable truth, so a polluted
  tool result, a stale update, or a teammate's half-finished note can silently drive an irreversible action. The design
  conflates two events that deployments must keep apart: recording an observation and committing a belief."
- Search extract: "Each record carries evidence, permissions, provenance, and validity. Writes are staged inside
  snapshot-isolated transactions and admitted by a validate-and-commit pipeline, irreversible tool calls are gated on
  in-flight belief state, and retracting a belief triggers typed cascading repair of its derived records and tool side
  effects."
- Search extract: "Two invariants, action-safety gating and cascade-repair completeness, are machine-checked ... 5.5
  million protocol states, with zero violations." "leads all eight baselines ... the only method with zero downstream
  harm on every backbone."
- Why it matters: "new evidence invalidates a belief -> repair the decisions/side effects that depended on it" is
  already a mechanism with a benchmark-style evaluation, framed as belief commit + cascade repair, with no temporal
  navigation abstraction.

### 2. Fresh Memory, Stale Plans: Derivation Currency / Dependency-Scoped Validation (PlanFence) (arXiv 2609.03340, 2026)
- URLs: https://arxiv.org/abs/2609.03340 , https://arxiv.org/html/2609.03340
- Authors (search extract): Evan Chen, Shiqiang Wang, Christopher G. Brinton.
- Search extract: "A large language model (LLM) agent that inherits a plan through shared memory can hold the latest
  requirement yet act on a plan derived from an older one: fresh memory, stale plan. Freshness checks miss this failure
  because they compare local copies with current state (observation currency) rather than the inputs the plan was
  derived from (derivation currency)."
- Search extract: "Stored plans carry exact links to their recorded inputs; before a protected action, PlanFence follows
  those links to an action-specific dependency frontier, asks each input's owner for its current head, refreshes what
  changed, and allows one replan before blocking."
- Search extract: "In 30 live five-agent workflows with a revision inserted after planning, a freshness-only executor
  acts on the stale plan every time, whereas PlanFence ... completes all 30 correctly."
- Why it matters: this is the "assumption behind an earlier decision was invalidated by a later revision" capability,
  named, mechanized (decision-time input links = what the plan knew when it was derived), and evaluated.

### 3. Corollary: truth maintenance agent runtime (GitHub gabe-santana/corollary, v0.1.0a2, Oct 2026)
- URLs: https://github.com/gabe-santana/corollary , https://pypi.org/project/corollary/0.1.0a2/
- Cloned: scratchpad/lit/repos/corollary (last commit 2026-10-02 "Release 0.1.0a2").
- README verbatim: "An agent runtime where the unit of state is a belief, not a message. Every conclusion your agent
  reaches carries its proof. Correct one fact, and everything that followed from it updates itself."
- README verbatim: "Underneath sits a **Truth Maintenance System** (Doyle, 1979): every belief records what supports it,
  and when that support is withdrawn, dependent beliefs are retracted automatically."
- README verbatim: "**Retraction cascades.** A tool returns a corrected figure. Every conclusion derived from the old
  value is retracted and re-derived, surgically."
- README verbatim: "**Beliefs that expire.** ... Stale beliefs trigger re-verification instead of silent reuse."
- docs/guides/belief-base.md verbatim: "Retracted revisions remain queryable with their reason." ; `kb.revisions("growth")
  # every revision, oldest first` ; `for event in kb.history:  # Event(at, action, ref, detail)`
- Roadmap verbatim: "[x] Persistent belief snapshots (JSON)" ; "[ ] Assumption-based (ATMS) mode for exploring
  alternative hypotheses in parallel"
- README verbatim (open problems): "**Benchmarks.** There is no standard evaluation for how well an agent recovers from a
  corrected input. We want to build one."
- Why it matters: explicit belief state + justifications + retraction cascade + revision history is shipping code.
  Pre-alpha, no published evaluation.

### 4. STALE: Can LLM Agents Know When Their Memories Are No Longer Valid? (arXiv 2605.06527, 2026)
- URLs: https://arxiv.org/abs/2605.06527 , https://arxiv.org/html/2605.06527v1
- Authors (search extract): Hanxiang Chao, Yihan Bai, Rui Sheng, Tianle Li, Yushi Sun.
- Search extract: "400 expert-validated conflict scenarios (1,200 evaluation queries across three probing dimensions)
  ... contexts up to 150K tokens ... State Resolution (detecting that a prior belief is outdated), Premise Resistance
  (rejecting queries that falsely presuppose a stale state), and Implicit Policy Adaptation (proactively applying updated
  states in downstream behavior)."
- Search extract: "Implicit Conflict: a later observation invalidates an earlier memory without explicit negation,
  requiring contextual inference and commonsense reasoning to detect."
- Search extract: "even the best evaluated model achieving only 55.2% overall accuracy." "write-side prototype achieves
  91% accuracy on state resolution but only 32% on IPA, and the updated evidence is visible in 67.8% of failed IPA cases."
- Why it matters: the "later event implicitly changes what an earlier memory means" detection problem is benchmarked,
  including the "knows it but does not act on it" gap.

### 5. Memvara: bitemporal memory for AI agents (GitHub memvara/memvara, v0.19.0, Oct 2026)
- URLs: https://github.com/memvara/memvara , https://pypi.org/project/memvara/ ; related blog
  https://dev.to/ethanbeirne/bitemporal-ai-memory-how-to-preserve-what-an-agent-knew-then-2g96
- Cloned: scratchpad/lit/repos/memvara (last commit 2026-10-01 "Release 0.19.0").
- README verbatim: "Bitemporal memory for AI agents. Know what was true. Know when it was true. Know why you believe it."
- README verbatim:
  `mem.get_all(valid_at=T)   # what we believe TODAY about how the world was at T`
  `mem.get_all(known_at=T)   # what we believed at T, about the world as it is now`
  `mem.get_all(as_of=T)      # both clocks at T — what we believed at T, about T`
- README verbatim: "A correction that arrives in August about June is invisible to `as_of=June`, because that call
  rewinds the belief clock past the correction".
- README verbatim: "**Auditable** | A claim carries the episodes cited for it and the claim it superseded, and `why()`
  returns both."
- Why it matters: "belief at time t with no hindsight" (as_of) is a library call for fact memory.

## Tier 2: medium threat

### 6. TGMS: An Agent-Native Bi-Temporal Graph Management System (arXiv 2607.10265, 2026)
- URLs: https://arxiv.org/abs/2607.10265 , https://arxiv.org/html/2607.10265
- Search extract: "Temporal graph question answering requires exact composition over time and, when records are
  corrected, reconstruction of prior belief states." "exposes thirteen verified temporal operators as agent tools ...
  bi-temporal by default." "On correction probes, TGMS obtains 0.897; the two latest-state baselines obtain zero, while
  vector-RAG obtains 0.154 by answering current-belief cases."
- Why it matters: evaluated "prior belief state" reconstruction vs latest-state and RAG baselines (a mini version of
  the project's temporal-vs-RAG comparison, for QA rather than decisions).

### 7. Graph-Native Cognitive Memory for AI Agents: Formal Belief Revision Semantics for Versioned Memory Architectures (Kumiho) (arXiv 2603.17244, 2026)
- URLs: https://arxiv.org/abs/2603.17244 , https://arxiv.org/html/2603.17244v1 , https://kumiho.io/en
- Search extract: "The structural primitives required for cognitive memory -- immutable revisions, mutable tag pointers,
  typed dependency edges, URI-based addressing -- are identical to those required for managing agent-produced work as
  versionable assets." "a correspondence between the AGM belief revision framework and the operational semantics of a
  property graph memory system, proving satisfaction of the basic AGM postulates (K*2--K*6) and Hansson's belief base
  postulates".
- Why it matters: "never overwrite, add a revision" + formal belief revision is already claimed for agent memory.

### 8. Can Agent Memory Systems Track Evolving State? (StateMemBench) (arXiv 2608.19652, 2026)
- URLs: https://arxiv.org/abs/2608.19652 , https://arxiv.org/pdf/2608.19652
- Authors (X post in search results): Xinyi Fan, Miri Liu, Ruozhen Yang, Siru Ouyang, Jiawei Han.
- Search extract: "as facts, constraints, and decisions are revised over a long interaction, answers must reflect the
  current state and not a superseded one." "234 multi-session scenarios". "generates scenarios as symbolic event
  programs, which are sequences of operations such as rule declarations, value updates, and commitments ... derive a
  'ground truth' state by replaying the events deterministically." "lifting current-state accuracy by +32 to +67 points
  ... across six memory and retrieval backends."
- Why it matters: benchmark construction is very close to the project's (deterministic event log -> ground-truth state,
  decisions revised, drift scored).

### 9. ClawArena: Benchmarking AI Agents in Evolving Information Environments (arXiv 2604.04202, 2026)
- URLs: https://arxiv.org/abs/2604.04202 , https://arxiv.org/html/2604.04202v1
- Search extract: "AI agents deployed as persistent assistants must maintain correct beliefs as their information
  environment evolves ... new information can invalidate earlier conclusions". "three coupled challenges: multi-source
  conflict reasoning, dynamic belief revision, and implicit personalization". "64 scenarios across 8 professional
  domains, totaling 1,879 evaluation rounds and 365 dynamic updates." "belief revision difficulty is determined by update
  design strategy rather than the mere presence of updates."

### 10. TRACE: Governing Memory Validity in Evolving Multi-Agent Systems (arXiv 2609.33517, 2026)
- URLs: https://arxiv.org/abs/2609.33517 , https://arxiv.org/html/2609.33517
- Search extract: "memories can be correctly retrieved, relevant to the current task, and faithful to their source, yet
  still be inadmissible for action—such as when an itinerary saved before a pause still names a hotel the team has since
  replaced." "reconciling a departure checkpoint against absence-period updates, resolving explicit and implicit
  invalidation, and releasing a bounded Return View only when it covers the returning role's open obligations."
  "92.6–98.3% valid-information availability with 98.4–99.5% invalid-information rejection on ManBench-Return".
- Why it matters: checkpoint-vs-now diff + implicit invalidation + open obligations, all without a general temporal
  abstraction.

### 11. When Memory Updates but Behavior Does Not: Repairing Implicit Stale Dependencies (StateAuditor) (arXiv 2608.01619, 2026)
- URLs: https://arxiv.org/abs/2608.01619 , https://arxiv.org/html/2608.01619v1
- Search extract: "Memory-augmented agents can know that a user's stored state is outdated and still plan around the old
  value." "An LLM proposes candidate old-to-new transitions from timestamped evidence; deterministic code pins each
  quotation to a single entry, checks that the new evidence really is newer, and lets only these verified transitions
  trigger repair. What is verified is provenance and chronology - not semantic supersession." "+5.0-point paired gain
  (95% CI [+2.9,+7.2]) coming almost entirely from IPA and premise resistance."

### 12. Agent-BRACE: Decoupling Beliefs from Actions in Long-Horizon Tasks via Verbalized State Uncertainty (arXiv 2605.11436, 2026)
- URLs: https://arxiv.org/html/2605.11436v1 , https://arxiv.org/pdf/2605.11436
- Search extract: "decouples an LLM agent into a belief state model and a policy model, jointly optimized via
  reinforcement learning." "a set of atomic natural language claims about the environment, each annotated with an
  ordinal verbalized certainty label ranging from certain to unknown." "+14.5% (Qwen2.5-3B-Instruct) and +5.3%
  (Qwen3-4B-Instruct) ... near-constant context window independent of episode length."

### 13. Truth / reason maintenance systems (Doyle 1979 TMS; de Kleer ATMS) - foundational
- URL: https://en.wikipedia.org/wiki/Reason_maintenance (search hit); Corollary README cites Doyle 1979.
- Search extract: "Truth Maintenance Systems (TMSs) were introduced by Doyle (1979) as a domain-independent method for
  supporting dependency-directed backtracking, representing data and their justifications while providing the ability to
  revise beliefs when assumptions change or contradictions arise." "later extended by De Kleer with assumption-based TMS".
- Other LLM-era TMS repos seen in search: https://github.com/benthomasson/ftl-reasons ("Reason Maintenance System —
  automatic belief retraction and dependency-directed backtracking (Doyle 1979)"), https://github.com/afogel/lemmalog
  ("Datalog engine for LLM agent memory: ... provenance-tracked facts, incremental derivation").
- Why it matters: "detect when an assumption is withdrawn and retract dependent conclusions" is a 1979 abstraction; ATMS
  maintains multiple assumption contexts simultaneously.

## Tier 3: low threat (in lane, but weak overlap)

### 14. HindsightBench: Black-Box Behavioral Audit Protocol for Parametric Hindsight in Time-Indexed LLM Decision Tasks (arXiv 2607.18867, 2026)
- URLs: https://arxiv.org/abs/2607.18867 , https://arxiv.org/html/2607.18867v1
- Search extract: "how large language models leak parametric knowledge of realized outcomes into historical financial
  decision tasks." "four-arm date-manipulation matrix (revealed/date-only/masked/transplanted)". "effective cutoffs span
  22 months across vendors and precede vendor-reported dates by up to eight months."
- Why it matters: "strict epistemic cutoff (no hindsight)" is an audited problem; for synthetic worlds parametric leak is
  moot, but it shows the cutoff claim needs a leakage test.

### 15. PABU: Progress-Aware Belief Update for Efficient LLM Agents (arXiv 2602.09138, Feb 2026)
- URLs: https://arxiv.org/abs/2602.09138 , https://arxiv.org/html/2602.09138v1
- Authors (search extract): Haitao Jiang, Lin Ge, Hengrui Cai, Rui Song.
- Search extract: "a belief-state framework that compactly represents an agent's state by explicitly modeling task
  progress and selectively retaining past actions and observations." "81.0% task completion rate, outperforming previous
  SoTA models with full-history belief by 23.9%" "reducing the average number of interaction steps to 9.5".
- Why it matters: "belief state" here = compressed retained history; it does not track assumptions or revise past
  decisions. Low overlap with the project's thesis.

---

## Additional works seen (not in top 15)
- TOKI: Bitemporal Operator Algebra for Contradiction Resolution (2606.06240) https://arxiv.org/abs/2606.06240v1 -
  "provenance annotation that preserves the losing fact in an audit row"; names anomalies "replay inconsistency,
  belief-drift skew, and audit erasure".
- A Graph-Native Bitemporal Memory Store for Conversational AI Agents (2607.26520) https://arxiv.org/abs/2607.26520 -
  "immutable identity node linked to versioned content nodes carrying two closed-open time intervals"; time-travel path
  80% R@10 on knowledge-update.
- When Stale Constraints Go Unchecked (2608.25553) https://arxiv.org/abs/2608.25553 - "treating historical provenance
  as immutable while what changes is which record is current"; stale-consistent decisions in ~75% of episodes.
- Belief Memory / BeliefMem (2605.05583) https://arxiv.org/abs/2605.05583 - "retaining multiple candidate conclusions
  with their probabilities ... updated via Noisy-OR".
- Towards a Belief-Based World Model for LLM Agents (2609.00455) https://arxiv.org/abs/2609.00455 - belief exposing
  "what is known and uncertain about the current state".
- Intent-Driven Situation Tracking (IDSS) (2608.15755) https://arxiv.org/abs/2608.15755 - "propagates new facts to task
  constraints to update action executability".
- SyncPlan (2608.01652) https://arxiv.org/html/2608.01652v1 - "Plan Staleness Detector ... triggers replanning when
  environmental changes invalidate its assumptions".
- From Assumptions to Actions (PCE, ICLR 2026) (2602.04326) https://arxiv.org/abs/2602.04326 - assumptions as decision
  tree internal nodes scored by scenario likelihood.
- BeliefShift (2603.23848) https://arxiv.org/abs/2603.23848 - Belief Revision Accuracy, Contradiction Resolution Rate;
  2,400 trajectories (user-belief drift, not agent world-belief).
- PROJECTMEM (2606.12329) https://arxiv.org/abs/2606.12329 - "append-only, plain-text event log of typed events -
  issues, attempts, fixes, decisions, and notes" for coding agents, plus pre-action gate.
- Beyond Memory: Transactional Continuity Kernel (2608.11632) https://arxiv.org/abs/2608.11632 - typed changes against
  "an exact predecessor head"; Commit/Reject/Quarantine/Defer; branch head.
- Always-On Agents survey (2606.30306) https://arxiv.org/abs/2606.30306 - lifecycle "written, validated, organized,
  retrieved, acted upon, updated, forgotten, audited, and sometimes rolled back"; 435-work corpus "concentrates more
  heavily on accumulating and retrieving state than on governing, recovering, or relinquishing it."
- FinalityBench (2609.04706) https://arxiv.org/abs/2609.04706 - hidden canonical event log, systems "hold contradictory
  beliefs", irreversible actions; graded on executed effects.
- MemSecBench (2607.27080) https://arxiv.org/abs/2607.27080 - persistence -> consequence -> selective repair.
- LEDGER claim-to-evidence trace graphs (2608.18398) https://arxiv.org/abs/2608.18398
- From Agent Traces to Trust survey (2606.04990) https://arxiv.org/html/2606.04990v1 - search extract mentions an
  "Invalidate" relation for when new observations make prior assumptions unusable.
- EvoCode-Bench (2605.24110) https://arxiv.org/html/2605.24110 ; SlopCodeBench (2603.24755)
  https://arxiv.org/html/2603.24755v1 - coding agents under evolving requirements.
- MemAudit (2606.24595) https://arxiv.org/html/2606.24595v2 - reconstruct hidden user state from memory left behind.
- Requirements traceability / change impact with LLMs (SE lineage, not agent belief state): LLM-Driven Cost-Effective
  Requirements Change Impact Analysis (2511.00262) https://arxiv.org/pdf/2511.00262 ; TraceDev traceability-driven
  multi-agent requirement-to-code (2607.18886) https://arxiv.org/pdf/2607.18886 ; TraceLLM (Requirements Engineering
  journal, 2026) https://link.springer.com/article/10.1007/s00766-026-00460-1 . Search extract: "Effective traceability
  supports crucial software engineering tasks, including change impact analysis".
- ReplayLens (2609.34177) https://arxiv.org/abs/2609.34177 - black-box audit of how agents use logged outcomes
  (outcome reassignment, pair transport, renaming, key-slot reassignment).
- SeekBench (ICLR 2026, 2509.22391) https://github.com/SHAO-Jiaqi757/SeekBench - epistemic competence (grounding,
  recovery, calibration) of search agents.


## Lane questions

**Q1. Is "maintain current beliefs + detect when new evidence invalidates an assumption behind an earlier decision"
already a studied capability with methods and benchmarks?** Yes, and it is a crowded 2026 topic.
- Benchmarks: STALE (400 scenarios; State Resolution / Premise Resistance / Implicit Policy Adaptation; best model 55.2%;
  91% SR vs 32% IPA), StateMemBench (234 scenarios; "facts, constraints, and decisions are revised"; ground truth by
  deterministic replay of symbolic event programs), ClawArena (64 scenarios, 365 dynamic updates; "new information can
  invalidate earlier conclusions"), ManBench-Return (TRACE), BeliefShift, FinalityBench; coding-side EvoCode-Bench and
  SlopCodeBench (evolving requirements).
- Methods: MemTX ("retracting a belief triggers typed cascading repair of its derived records and tool side effects";
  irreversible calls gated on belief state), PlanFence ("derivation currency": plans store links to their inputs and are
  revalidated before protected actions; 30/30 vs 0/30 for freshness-only), Corollary (TMS retraction cascades,
  re-derivation, revision history), StateAuditor (verified old-to-new transitions trigger repair), SyncPlan (Plan
  Staleness Detector), IDSS (new facts propagate to constraints and action executability), PCE (assumptions as explicit
  decision-tree nodes). Foundational: Doyle's TMS (1979) and de Kleer's ATMS.
- Gaps I could not close: (a) most benchmarks score current answers or later behavior, not explicit reopening and
  remediation of an already executed decision. MemTX's cascade repair of tool side effects is the closest. (b) Cases where
  the earlier fact stays true but a later event changes its significance are covered only partly, by STALE's "implicit
  conflict" and TRACE's "inadmissible for action". (c) Corollary's README (Oct 2026) says: "There is no standard
  evaluation for how well an agent recovers from a corrected input."

**Q2. Is versioned belief state (belief at time t) studied?** Yes, as memory or database infrastructure, and some of it
is evaluated. Memvara exposes `known_at=T` ("what we believed at T") and `as_of=T`. TGMS evaluates "reconstruction of
prior belief states" on correction probes (0.897 vs 0 for latest-state baselines, 0.154 for vector-RAG). TOKI and
2607.26520 are bitemporal stores with audit rows. Kumiho has immutable revisions with AGM proofs. A-TMA (seen only in a
search extract) keeps superseded and transition records for "what was true before" queries. Graphiti/Zep is covered in
another analysis. HindsightBench audits parametric hindsight leakage in time-indexed decisions. What these do not cover:
versioning the agent's whole decision-time epistemic state (beliefs plus plans, assumptions, uncertainty and policy).
They also do not use as-of queries over the agent's own past state to decide whether to reopen a past decision, with
that capability scored against a strong RAG baseline. I found no work that does this.

## Queries run (47 executed)
1. PABU Progress-Aware Belief Update LLM agents 2602.09138 [arxiv]
2. LLM agent explicit belief state maintenance assumption tracking benchmark 2025
3. belief revision LLM agents new evidence invalidates earlier conclusion benchmark [arxiv]
4. truth maintenance system LLM agent assumptions dependency retraction
5. LLM agent detect stale assumption behind earlier decision reopen revisit decision when new information arrives [arxiv]
6. requirements traceability large language models change impact analysis 2025
7. versioned belief state agent memory "as of" time bitemporal what the agent knew
8. Agent-BRACE decoupling beliefs from actions verbalized state uncertainty [arxiv]
9. Belief Memory agent memory under partial observability 2605.05583 [arxiv]
10. TOKI bitemporal operator algebra contradiction resolution LLM agent persistent memory [arxiv]
11. Graph-Native Cognitive Memory formal belief revision semantics versioned memory architectures AGM [arxiv]
12. ClawArena benchmarking AI agents evolving information environments belief revision [arxiv]
13. LLM agent retroactively reassess past actions after later evidence changes their significance remediation benchmark
14. STALE benchmark implicit conflict state resolution premise resistance implicit policy adaptation memory [arxiv]
15. "Can Agent Memory Systems Track Evolving State" StateMemBench facts constraints decisions revised
16. When Memory Updates but Behavior Does Not repairing implicit stale dependencies personalized agent [arxiv]
17. TRACE governing memory validity evolving multi-agent systems [arxiv]
18. ReplayLens auditing agents use of outcomes hindsight [arxiv]
19. Fresh Memory, Stale Plans: Derivation Currency for Distributed LLM-Agent Memory [arxiv]
20. HindsightBench black-box behavioral audit parametric hindsight time-indexed LLM decision tasks [arxiv]
21. MemTX transactional belief commit stateful agent memory [arxiv]
22. LLM agent planning explicit assumptions monitor assumption violation replan execution monitoring [arxiv]
23. agent tracks open questions unresolved uncertainties ledger long-horizon LLM agent "open questions"
24. BeliefShift temporal belief consistency opinion drift evidence-driven revision LLM agents [arxiv]
25. coding agent benchmark evolving requirements mid-task requirement change revisit earlier implementation 2026 [arxiv]
26. Beyond Memory transactional continuity kernel long-lived AI agents [arxiv]
27. When Stale Constraints Go Unchecked budgeted verification failures inherited agent memory [arxiv]
28. agent decision provenance record assumptions at decision time audit "what the agent knew" LLM decision log rationale
29. Graph-Native Bitemporal Memory Store conversational AI agents valid time transaction time [arxiv]
30. Towards a Belief-Based World Model for LLM Agents [arxiv]
31. Always-On Agents survey persistent memory state governance LLM agents versioned belief [arxiv]
32. Intent-Driven Situation Tracking user-centric multi-turn agents [arxiv]
33. reconstruct what an LLM agent believed at a past step belief trajectory audit point-in-time agent memory benchmark "knowledge time"
34. MemSecBench memory poisoning persistence consequence selective repair downstream actions [arxiv]
35. "Do LLM Agents Know How to Ground, Recover, and Assess" epistemic competence information-seeking agents
36. FinalityBench effect-level benchmark agent decisions delayed conflicting financial finality [arxiv]
37. From Assumptions to Actions uncertainty-aware planning embodied agents LLM reasoning assumptions [arxiv]
38. SyncPlan plan staleness detector replanning invalidated assumptions long-horizon LLM coordination [arxiv]
39. MemTX retracting a belief triggers typed cascading repair derived records tool side effects compensation downstream harm benchmark [arxiv]
40. PlanFence derivation currency dependency frontier protected action handoff stale plan evaluation [arxiv]
41. STALE benchmark LLM agents memories no longer valid authors 55.2% frontier models memory frameworks Mem0 [arxiv]
42. PROJECTMEM local-first event-sourced memory judgment layer AI coding agents decisions [arxiv]
43. Beyond Approved Actions runtime validation of persistent outcomes agent workflows [arxiv]
44. Kumiho graph-native cognitive memory immutable revisions tag pointers AGM postulates agent
45. agent memory benchmark questions about superseded past state "what was the value before" history queries knowledge update temporal versioning evaluation 2026 [arxiv]
46. TGMS agent-native bi-temporal graph management system validated temporal operators trace-grounded answer checking [arxiv]
47. Corollary truth maintenance agent runtime beliefs retraction cascade LLM
(not executed, budget exhausted: AUQ uncertainty-aware memory; A-TMA superseded transition records; Supersede memory-update gap)
