# NORTH_STAR v2: proposal

Status: **proposal only**, Milestone 2.5, 2026-10-03.
- NORTH_STAR.md is unchanged and should not be edited until this proposal is
  accepted or rejected.
- Evidence labels are defined in
  [research-landscape-2026-10.md §1](research-landscape-2026-10.md#1-method-and-evidence-limits).
- The disposition this proposal sits under is **A (Stop)**. See
  [residual-hypotheses.md](residual-hypotheses.md) and
  [m2.5-decision-record.md](m2.5-decision-record.md).

## 1. Why a v2 is needed

NORTH_STAR v1 describes one intuition at three levels without separating
them:

- **UX metaphors:** past self, present self, future self, temporal dialogue,
  "go to March", temporal multiplicity.
- **Named components:** Chronicle, Historian, Tesseract, TVA.
- **Computational claims:** an epistemic cutoff, forks with provenance,
  action-conditioned simulation, backward requirements, preserved prevented
  futures, predicted-vs-realized calibration, identity across time.

The M2.5 review found two things:

- **The computational claims all have prior art**, at the level of concept
  and mechanism:
  - research-landscape §4: 47 items mapped;
  - capability-matrix §4: no capability lacks a "yes" except composition (20),
    agent-side use of policy records (4), and persistence of imagined futures
    (13).
- **The metaphors and named components therefore carry the novelty claim
  without earning it.**

A v2 must state the thesis at the level where it can be falsified:
implementation-neutral capabilities, measured against the strongest existing
composition.

## 2. Three layers

### 2.1 UX metaphor (an interface, not a claim)

Examples: "talk to my past self", "what did I know then?", "talk to a future
self", "what will I regret?", "this didn't happen because I acted".

These are legitimate interfaces. Human future-self interfaces have measured
*affective* and *persuasive* effects:
- Future You (2405.12514) [unv];
- Simulating Life Paths (2512.05397) [abs], which "assessed decision
  intentions rather than implemented behaviors".

Neither shows effects on decision quality. A metaphor carries no capability
claim, and none of these should appear in a hypothesis.

### 2.2 Backend capability (implementation-neutral)

What the agent can do, whatever the mechanism. Examples:
- answer "what had reached me by t";
- re-judge a past decision without information after t;
- estimate the consequence of an alternative action;
- derive an obligation from a feared outcome;
- score a forecast only on the branch that was realized.

### 2.3 Computational primitives

Eight primitives cover all 19 UX concepts examined (§3). Each has shipped or
published prior art:

| id | primitive | prior art |
|---|---|---|
| P1 | append-only log | event sourcing; ActiveGraph; OpenHands SDK; this repo's `events.jsonl` |
| P2 | as-of / bitemporal query | XTDB, Datomic, Memvara `known_at`/`valid_at`/`as_of`, LangGraph `get_state(checkpoint)`, this repo's A1 `read_at` |
| P3 | diff | ActiveGraph `compute_diff`, Dolt, this repo's A1 `diff` |
| P4 | typed contemporaneous records with provenance and dependency edges (decision, policy envelope, forecast, obligation) | AER, FlowState, DeepRewind, Corollary, PlanFence, PIS |
| P5 | fork with lineage | LangGraph, ActiveGraph, Shepherd, AgentGit |
| P6 | replay | LangGraph, ActiveGraph strict replay, this repo's recorded backend |
| P7 | a model call on a constructed context (cutoff or imagined) | Self-Blinding "blinded replica", ITP foresight, ContextEcho snapshot-then-probe |
| P8 | executed continuation in a resettable environment | COUNTERMEM, C3, Shepherd, Calibration Is Not Control prefix branching |

Their realizations form a ladder, cheapest first:

| rung | realization | inference? |
|---|---|---|
| R1 | stored contemporaneous record | none |
| R2 | query (as-of, bitemporal, diff) | none |
| R3 | reconstructed context at t (the input set materialized) | none |
| R4 | replay of recorded calls | none (reproduces, adds nothing) |
| R5 | executable instantiation: (a) same model on a cutoff context; (b) then-model and then-policy pinned; (c) a fork that continues acting in a resettable environment; (d) present model on an imagined future state | yes |

## 3. UX concepts mapped to capabilities and primitives

Condensed from the synthesis's UX analysis (19 rows; full table in
`research/m2.5-evidence/synth/synthesis.json`, key `ux`).

| human-facing concept | required capability | possible backend primitives | existing systems that already provide it | what appears missing |
|---|---|---|---|---|
| "Talk to my past self" | Ask a new question of a reconstruction of S_t. The answer must be free of anything after t, and the present must not be perturbed. | R3 + R5a (blinded replica) with clean serving state (no KV/cache carry-over); the then-model pinned if it changed; replica checked to reproduce the original decision before its testimony counts | Self-Blinding (2601.14553) [abs]: prompting to ignore information "fails ... and occasionally backfires"; a blinded replica works. ContextEcho (2605.24279) [abs]: snapshot-then-probe. Shepherd fork + inject [abs]. ChronoMem post-exposure protocol [abs]. | Evidence that the replica's answers improve a downstream decision more than reading contemporaneous records. Untestable in this repo: decisions are world-authored (milestone-2 §0), and contestants keep neither their context nor their summary at t. |
| "What did I know then?" | Return exactly what had reached the agent by t (transaction-time cutoff). | P1 + P2 (ingestion timestamps + as-of filter); per-write snapshots; a read-scoping invariant. No inference. | XTDB `FOR SYSTEM_TIME AS OF` [ns]; Datomic `as-of` [ns]; Memvara `known_at` [code]; ChronoMem [abs]; FutureSim `get_prediction_as_of` [code]; PoS belief snapshots [code]; LangGraph `get_state` [code] | Nothing mechanical. In Memvara's benchmark a one-clock append-only RAG scores 100% on `knowledge_time`, the same as the bitemporal store [code]. Leak hygiene remains: Graphiti `invalid_at` overwrite, Memvara row-level as-of, ActiveGraph fork caches. |
| "Fork from an earlier state" | A new branch whose initial state equals agent and world state at t, with lineage, leaving the original untouched. | P5: event-sourced fold, copy-on-write snapshot, (parent, fork point) lineage, fail-closed merge, containment of external effects | ActiveGraph `fork(at_event)` [code]; Shepherd process + filesystem fork [abs]; LangGraph `update_state` [code]; AgentGit [abs]; MAGE Revise [ext]; COUNTERMEM [3p] | Saturated. Hard limit: effects that escaped to the outside world cannot be forked (Shepherd: "gate before escape, not reverse after"). This repo's contestants cannot rebuild their own S_t: `summary.json` is overwritten and workspace intents log no content. |
| "What if I had chosen differently?" | Estimate the consequences of an alternative action at a past decision point; keep the result as a counterfactual, never as an observation. | P8 (executed: fork, apply alternative, re-feed exogenous inputs) or P7 (imagined world-model call); a counterfactual record with parent and assumptions | C3 (2603.06859) [abs; quote from its README, code]: "the counterfactual is executed rather than predicted". Causal Agent Replay [abs]; COUNTERMEM [3p]; Calibration Is Not Control prefix branching [abs]; Agent-R [abs]; ITP / WebDreamer / WMA / WALL-E 2.0 | No lifelong, queryable store of counterfactual branches. All found works use outcome hindsight by design. Executed counterfactuals assume the exogenous inputs do not react to the agent. |
| "Talk to a future self" | Interrogate a simulated agent or world state at t+Δ under an explicit branch (action, assumptions, plausibility, horizon) for warnings and requirements. | P7 (R5d) over a rollout from a world model or sandboxed execution; a branch record. The "self" is a prompt framing. | ITP [code]; RAP, Dyna-Think [abs]; Shepherd speculate-then-commit [abs]; SIMMER [abs]; FORESIGHT-9, ForecastBench-Sim [abs] | No agent interrogates a simulated future version of its own policy or objectives with a measured benefit. Agents rarely use foresight tools (2601.03905 [abs]: <1% invocation, ~15% misuse). A future self knows nothing the present model plus simulator does not. |
| "What will I regret?" | Rank present actions by expected loss against the best alternative across plausible futures, weighting irreversibility. | A set of futures or models; a utility; per-action outcome estimates; a reversibility score; robust or minimax-regret choice; intervention advantage | Calibration Is Not Control (intervention advantage; ALFWorld regret 0.506 → 0.110) [abs]; SafeCommit, LCPI [abs]; DeepRewind reversibility gate [abs]; Plaut et al. (2502.14043) [abs]; RAFA √T regret [unv]; relative reachability, AUP [unv] | Regret is a quantity over a decision set, not a conversation. Learning from realized regret needs counterfactual outcomes, which hits positivity (row "this forecast did not happen"). |
| "What must I do now for future state Y to remain reachable?" | Derive preconditions and deadlines backward from a desired or feared state; prefer option-preserving actions; persist derived obligations with provenance and re-check them as events arrive. | Goal regression / backward chaining; reachability or attainable-utility measures; an obligation record (condition, deadline, derived-from branch); a trigger monitor; re-validation | BAR (2505.14079) [abs]; relative reachability, AUP [unv]; Heitzig & Potham [abs]; SafeCommit, LCPI [abs]; SafePred, SIMMER, JANUS [abs]; PIS typed intention store [abs]; FlowState conditional plan [ext]; DeepRewind per-commitment trigger [abs] | No LLM work found that persists *derived* obligations as timestamped, provenance-carrying state re-checked as events arrive. PIS suggests that if built, it is a typed store plus code plus truth maintenance, not temporal navigation. |
| "This forecast did not happen because I acted on it" | Store each forecast as conditional on a named action or policy, P(Y \| do(a), H_t). Link the action actually taken. Mark forecasts on unrealized branches as annulled or unverifiable, not wrong. Verify "prevented" only where a holdout or a trusted simulator exists. | Forecast record {conditioning action or policy version, evidence cutoff, horizon, probability, branch}; status realized / annulled / counterfactually checked / unverifiable; proper scoring on the realized branch; a counterfactual estimator | Dickerman & Hernán (potential outcomes) [ns]; Metaculus Conditional Pairs annulment and the `forecasting-tools` ANNULLED model [ns]; decision markets; performative prediction [unv]; Boeken et al. [unv]; Calibration Is Not Control [abs]; ForecastBench-Sim paired intervention worlds [abs] | The concept is settled. No long-lived LLM agent persists averted forecasts as typed records. That is schema work. **Positivity:** an agent that always intervenes cannot verify its "prevented" labels from its own data, and self-scoring reflexive forecasts creates manipulation incentives. |
| Comparing predicted future state with realized future state | When a horizon arrives, join the forecast with the outcome, score it, and update calibration or policy, keeping realized-branch forecasts apart from annulled ones. | Append-only, as-of-queryable forecast ledger; resolution join; proper scoring rule; feedback/lesson memory; a branch tag | FutureSim `PredictionHistory` + "Your prediction ... \| Truth ... \| Brier" feedback [code]; EpiEvolve, Live-Evo [abs]; Forecast-Dojo [abs]; WALL-E 2.0 [abs]; ExACT [unv] | Calibration Is Not Control: recalibration "leaves control regret unchanged" [abs]. The loop has no value claim unless tied to action choice. Agreement measured after acting is weak and manipulable. |
| Preserving identity, objective and policy changes across time | Record which model, instructions, tools, objectives and authority governed each past action; contrast them with the current ones; flag decisions made under superseded policy; re-instantiate the old policy only when needed. | Versioned config envelope per action (model id, prompt hash, tool set, objective); policy/authority event log; revocation guard; pins keeping the then-model servable | OpenTelemetry GenAI conventions [ns]; MLflow, Langfuse, LangSmith assistant versioning [ns]; LangGraph per-checkpoint config [code]; AER envelope [abs]; Revoked but Still Authoritative (retrieval guard) [abs]; FiscalQA Pro (98.3% as-of rule lookup) [abs]; goal-drift benchmarks [abs]; Layered Mutability (identity hysteresis) [abs] | Recording is solved in tooling. No agent uses it while deliberating. In this repo the model and guidance are fixed per run (A3, C2), so identity change is untestable by construction. |
| "Where am I in time?" | One authoritative present coordinate per reasoning step (own timeline, world clock, branch), with clock conflicts detected | Monotonic event seq; event timestamp; HEAD + branch id; a clock tool | PM-Bench hidden clocks [code]; ChronoMem HEAD [abs]; Memvara two clocks [code]; this repo's `<<event seq=N>>` and A1 reveal order | A field, not a capability. Repo hazard: the Claude CLI backend adds the real date to every request (C1), so contestants see two competing "nows". The effect is unmeasured. |
| "Why did I do this?" | Retrieve the contemporaneous basis of a past decision: context, assumptions, rejected alternatives, confidence, governing policy | P4 decision records written at decision time; prompt logs; causal-chain walks | AER (with a non-identifiability argument) [abs]; ActiveGraph causal walk [code]; DeepRewind epistemic graph [abs]; Memvara `why()` [code]; Corollary `why_out` [code] | An executable copy is **counterproductive** here. Re-instantiating the past self yields a new post-hoc rationale; the contemporaneous record is the testimony. What remains open is whether recorded reasons are faithful. |
| "Does this new fact change what I decided earlier?" | Unprompted, detect that a later event changes the basis or significance of a committed decision; identify it; reopen it with evidence; remediate | Decision-to-assumption dependency edges with retraction cascade (TMS); derivation-currency checks; retrieval over decision records; LLM relevance judgement; executable tests | DeepRewind [abs]; Corollary [code]; PlanFence [abs]; MemTX [abs]; FlowState [ext]; MAGE [ext]; STALE, StateMemBench, ClawArena, TWIST benchmarks [abs] | Mechanisms need the link recorded or declared. **Implicit, unanticipated significance changes are the open problem.** Nothing ties them to temporal navigation; they are a relevance and judgement problem. |

The remaining rows of the full table cover:
- "what changed between then and now";
- "what do I still owe";
- "keep my branches from contaminating each other";
- "it happened sometime between March 3 and 8";
- "show me exactly what I did".

All five decompose into P1-P6 with shipped prior art. The interval-uncertain
past (§11 of v1) was not found in agent memory. No lane targeted it,
classical temporal databases probably cover it, and its expected effect is
tiny.

## 4. When is an executable LLM copy actually needed?

**Never for retrieval.** What happened, what was known at t, what changed,
which policy governed, why a decision was taken, and which forecasts were
made or annulled are all R1 or R2.

R5 is needed in exactly four cases:

1. **A hindsight-free re-judgement of a past decision (R5a).** The present
   self cannot do this by instruction:
   - Self-Blinding [abs];
   - Simulated Ignorance Fails (2601.13717) [abs];
   - ChronoMem's prompt-only rollback, far below snapshot restore [abs].

   What works is *a separate call on a restricted context*, not a persistent
   "self". Plain temporal masking already gets the effect (clinical Hindsight
   Bias 2609.13454: "temporal masking reduces bias without lowering
   accuracy") [abs].
2. **A counterfactual injection** ("would you still have chosen X had you
   known Y?"): R5a plus an injected fact.
3. **Executed consequences of an alternative action (R5c).** This needs a
   resettable environment. In deployment only one branch is realized.
4. **"What would my old policy or model have done?" (R5b).** This needs the
   then-weights to remain servable. Layered Mutability (2604.14717) [abs]
   finds that reverting a self-description does not restore behaviour.

**Where R5 is counterproductive: "why did I do this?"** NORTH_STAR §5 says
the present self "does not reconstruct what its former self probably
thought. It asks the former self." That is backwards. Asking a
re-instantiated former self *is* a reconstruction: a fresh sample with the
same weights. Under AER's intent-multiplicity and inference-volatility
argument [abs], only a contemporaneous record is testimony.

**Validity conditions for any R5 past self:**
- no post-t content in context, memory, caches or KV state. Retained KV flips
  results under LangGraph time travel: Aborted but Not Forgotten, 2608.15939
  [abs];
- tools resolved against the world as of t;
- the then-policy in force;
- memory versioned together with the world;
- no outcome leakage from the model's weights (moot in synthetic worlds);
- the replica reproduces the original decision before its testimony counts.
  This repo's Claude CLI backend has no temperature control, so reproduction
  is not guaranteed.

## 5. The candidate abstraction: improve or reject

> An agent can navigate, interrogate and reason over alternative versions of
> its own state — historical, actual, counterfactual and prospective — while
> preserving the epistemic and causal boundaries of each state.

**Assessment, clause by clause.**

| clause | status |
|---|---|
| navigate versions of its own state | P2 + P5 + P6, shipped (ActiveGraph, Shepherd, LangGraph) |
| interrogate | P7 on a constructed context (Self-Blinding, ContextEcho, ITP) |
| reason over historical / actual / counterfactual | composition of the above (ActiveGraph unifies these three, capability 20 partial) |
| … and prospective | ITP, FutureSim, potential outcomes, as separate mechanisms; unification is integration |
| preserving epistemic boundaries | read-scoping (ChronoMem), as-of filters (XTDB, Memvara), blinded replicas. Engineering: close known leaks |
| preserving causal boundaries | gate-before-escape (Shepherd), fail-closed merge (ActiveGraph), annulment of unrealized branches (potential outcomes, Metaculus) |

**Verdict: reject it as a research thesis.** It accurately *describes* a
composition of existing mechanisms. It names no capability that the
composition lacks, and no measurable effect that the composition would fail
to produce. "Preserving the boundaries" is the only non-trivial clause, and
it is leak hygiene for documented failures:
- ActiveGraph fork caches;
- LangGraph replay reading the present Store;
- Memvara's row-level as-of;
- KV retention.

**The alternative "deeper primitives" the milestone asked about are all
occupied:**

| candidate deeper primitive | already occupied by |
|---|---|
| state-space navigation | ActiveGraph, Shepherd (fork / as-of / diff over one log) |
| execution-state management | MAGE, FlowState, LangGraph |
| belief-state evolution | PoS, Corollary (JTMS), Kumiho, DeepRewind |
| trajectory management | Trellis (design), Shepherd, AgentGit |
| policy evaluation over versioned state | AER mock replay, Shepherd counterfactual replay optimization, Calibration Is Not Control prefix branching |

None of them is a new north star. Each is a named, populated 2025-2026 area.

## 6. What survives as a research object (if anything)

The only reframing the review supports is **not an architecture and not a
temporal-navigation thesis**:

> **Commitment standing under late information.** A long-lived agent holds
> commitments (decisions, parked work, adopted assumptions), each with
> premises and evidence. Their *standing* must stay current as information
> arrives late, out of order, or only implicitly bearing on them. The open
> question is which minimal representation each regime needs, and at what
> cost:
> - current state plus re-checking;
> - dependency-tracked commitments (TMS);
> - time-indexed (bitemporal or versioned) state.

How it would be measured:
- per-decision reopen precision at matched recall, with negative controls;
- executable remediation;
- metered cost.

What is in favour of it as an object:
- It is the CLAUDE.md question ("does explicit temporal navigation help?")
  asked without presupposing that the answer is a temporal architecture.
- No released benchmark measures it as such: per-decision reopen
  recall/precision, plus negative controls, plus remediation, in one world.
- Its one genuinely open capability is noticing *implicit* significance
  changes, where no link was recorded and no fact is contradicted.

Time enters only through the gap between when evidence was valid and when it
became known (event classes C and D). Prior evidence puts the advantage of
two-clock state in a narrow regime, and the mechanisms for the other regimes
already exist:
- DeepRewind, PlanFence, MemTX, Corollary (dependency tracking);
- PIS (typed intention stores);
- StateMemBench's state wrapper (explicit current state).

Under disposition A **this is not authorized**. It would be a *separate*,
measurement-first program with its own novelty check against:
- STALE;
- ClawArena;
- TWIST;
- StateMemBench;
- MerchantBench;
- the recovery evaluation Corollary's README says it wants to build.

If someone wants to pursue the original intuition anyway, this is the
honest form to state it in.

## 7. Corrections to v1 that hold under any disposition

| v1 text | correction | why |
|---|---|---|
| §4 Chronicle / Historian / Tesseract / TVA as required components | Drop as components; describe only capabilities and primitives (P1-P8) | Each maps to existing systems: event log; interpretation layer (Graphiti, Memvara, DeepRewind); temporal query/fork API (ActiveGraph, LangGraph); integrity checks (Shepherd gate, fail-closed merge) |
| §5 "It asks the former self" (a past self that is not a summary but an executable reconstruction) | The contemporaneous record is the testimony. A cutoff replica (R5a) is a *re-judgement* tool for hindsight-free evaluation, not testimony. | AER non-identifiability [abs]; Self-Blinding [abs]; prompted cutoffs leak (2601.13717) [abs] |
| §6 / §14 future selves "provide warnings, requirements, regrets" | A rollout plus a pre-mortem prompt. Test it against a matched-budget single-prompt pre-mortem before building any future-self machinery. | No agent evidence. Human evidence is affective and persuasive. Agents rarely use foresight (2601.03905) [abs]. |
| §8 "Future A remains a valid prevented future" | "Annulled / unverifiable counterfactual"; verifiable only with a holdout, randomization or a trusted simulator | Potential outcomes; Metaculus annulment; positivity; self-scoring manipulation incentives (Oesterheld et al. [unv]) |
| §9 four-way forecast taxonomy | Cite it as potential outcomes (passive vs P(Y^a)), intervention advantage, and performative prediction | Calibration Is Not Control [abs]; Perdomo et al. [unv] |
| §13 irreversibility and optionality "as a first-class temporal variable" | Cite relative reachability, AUP, SafeCommit and LCPI; not a contribution | research-landscape §3.6 |
| §15 "compare predicted futures vs realized future, calibrate" | Invalid for any forecast that triggered an action, unless randomized, held out or simulated; calibration has value only when tied to action choice | Positivity; Calibration Is Not Control: recalibration "leaves control regret unchanged" |
| §17 "temporal multiplicity" as a superpower | A UX description of P5-P8, with no demonstrated decision benefit over composition | GitOfThoughts [abs]; Forecast-Dojo [abs]; Memvara benchmark [code] |
| §19 invariants 1-10 | Keep them as engineering requirements and cite their mechanisms (table below); they are not research contributions | — |

**Invariants mapped to existing mechanisms:**

| invariant | existing mechanism |
|---|---|
| 1 past events immutable | event sourcing; ActiveGraph; Shepherd; XTDB |
| 2 interpretations revisable | Graphiti invalidate-not-delete; Memvara ended/retired; Kumiho; Corollary |
| 3 no post-t knowledge in past selves | ChronoMem read-scoping + post-exposure protocol; XTDB system time; Self-Blinding |
| 4 future selves are simulations, never memories | ITP excludes foresight from history; PoS observed/inferred tags; Datomic `d/with` |
| 5 every future on an explicit branch | Metaculus ConditionalQuestion; Shepherd scopes; Calibration Is Not Control prefix branches |
| 6 information may cross branches, state may not | MAGE hints vs restored state; Rollback-Induced Reflection; ActiveGraph fail-closed promote |
| 7 intervention creates a new trajectory | LangGraph `update_state`; ActiveGraph fork; potential outcomes Y^a vs Y^0 |
| 8 prevented futures preserved | Metaculus annulment; COVID-19 Scenario Modeling Hub scenario-conditional scoring (as "annulled", see §8 correction) |
| 9 only the present commits actions | Shepherd gate-before-escape; MemTX irreversible-call gating |
| 10 provenance and epistemic status on every claim | W3C PROV; Graphiti episodes; Memvara `why()`; PoS observed/inferred + probability |

**Novelty claims to drop:**
- "time as an addressable dimension of state";
- "never overwrite time, fork it" (event sourcing + bitemporality + branching
  + PROV);
- fork/replay/provenance;
- backward requirements;
- option preservation;
- the reflexivity taxonomy;
- prevented futures;
- predicted-vs-realized calibration;
- the past-self / future-self architecture.

## 8. What this proposal does not do

- It does not rewrite NORTH_STAR.md. The milestone instruction was to propose
  only.
- It does not authorize any implementation, scenario family or experiment.
- It does not claim that temporal navigation was shown not to help.
  EXPERIMENT.md §13 was never run. The stop rests on coverage, attribution
  and value of information (residual-hypotheses.md §6).
