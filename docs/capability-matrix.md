# Capability matrix: temporal-agency capabilities in existing systems

Status: Milestone 2.5 research reset, 2026-10-03. Evidence labels ([code],
[abs], [ext], [3p], [unv], [ns]) are defined in
[research-landscape-2026-10.md §1](research-landscape-2026-10.md#1-method-and-evidence-limits).

- The full evidence for each cell is in
  [`research/m2.5-evidence/capability-matrix-evidence.md`](../research/m2.5-evidence/capability-matrix-evidence.md):
  one justification per non-trivial Matrix A cell. Matrix B cells are
  justified in the notes under Matrix B.
- The raw notes are in `research/m2.5-evidence/notes/` and `verify/`.

## 1. The twenty capabilities

A system is rated on what **it itself provides**, not on what could be built
on top of it.

| # | capability | operational definition |
|---|---|---|
| 1 | immutable historical observations | raw observations and events are kept append-only and never overwritten by later processing |
| 2 | reconstructable historical world state | the external world or environment as of an earlier time t can be recovered |
| 3 | reconstructable historical epistemic state | what the **agent** believed or knew at t can be recovered, with a cutoff that excludes later information |
| 4 | historical policy/objective state | the goals, instructions, policy or model that governed the agent at t are recorded, together with changes to them |
| 5 | execution checkpoints | restorable snapshots of the agent's execution state |
| 6 | replay | execution can be re-run from a historical point |
| 7 | fork from historical state | a new branch can start from an earlier state while the original is preserved |
| 8 | counterfactual action branches | alternative actions can be explored from a state, simulated or run in copies, without committing to them |
| 9 | branch provenance | each branch records its parent, its divergence point and the action or reason behind it |
| 10 | explicit current belief state | a maintained, structured representation of current beliefs, assumptions and requirements, separate from raw history |
| 11 | uncertainty representation | explicit uncertainty, confidence or unresolved items in the state |
| 12 | future-state rollout | future states are simulated conditional on actions (world model, imagination) |
| 13 | multiple prospective branches | several alternative futures are maintained or compared at once |
| 14 | probability/plausibility over futures | imagined futures carry a likelihood |
| 15 | backward requirements from future states | present obligations or preconditions are derived from a desired or feared future (goal regression) |
| 16 | intervention-aware forecasting | forecasts are explicitly conditioned on the agent's own interventions: passive vs policy-conditioned vs reflexive |
| 17 | preservation of prevented futures | forecasts that did not come true because the agent intervened are kept and labelled, not scored as wrong |
| 18 | predicted-vs-realized comparison | earlier predictions are compared with what actually happened, for calibration or learning |
| 19 | cross-time state querying | first-class queries such as `state_at(t)`, `diff(t1, t2)` and as-of reads |
| 20 | unified temporal abstraction | one abstraction spans historical, actual, counterfactual and prospective states |

Legend: ● yes · ◐ partial · `·` no · ? unclear.

## 2. Matrix A: agent systems

The first nine rows are the mandatory systems. Each was rated by one analyst
and re-checked by an adversarial verifier (6 of 180 ratings were corrected).
The remaining rows are the sweep's highest-threat works, each rated in a
single deep read, except Memvara, which had two.

| system | rating basis | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MAGE (2606.06090) | verified; [abs] (also on MSR page [ns]) + [ext] | ◐ | · | ◐ | · | ◐ | ◐ | ● | · | ◐ | ◐ | ◐ | · | · | · | · | · | · | · | · | ◐ |
| FlowState (2609.34565) | verified; [ext] + verbatim abstract [3p] | ◐ | · | ◐ | ◐ | · | · | · | · | · | ● | ◐ | · | · | · | · | · | · | · | ◐ | ◐ |
| LangGraph 1.2 persistence | verified; [code] + probes | ◐ | · | ◐ | ◐ | ● | ● | ● | ◐ | ◐ | · | · | · | · | · | · | · | · | · | ◐ | ◐ |
| PoS (2610.01415) | verified; [code] | ● | · | ◐ | ◐ | · | · | · | · | · | ● | ● | · | · | · | ◐ | · | · | · | ◐ | · |
| Graphiti / Zep (2501.13956) | verified; [code] | ◐ | ◐ | ◐ | ◐ | · | · | · | · | · | ◐ | · | · | · | · | · | · | · | · | ◐ | · |
| COUNTERMEM (2609.31874) | verified; abstract only [3p] | ? | ◐ | · | · | ◐ | ◐ | ◐ | ● | ◐ | · | ? | ◐ | ◐ | · | · | · | · | · | · | · |
| Imagine-then-Plan (2601.08955) | verified; [code] | ◐ | · | · | · | · | · | · | ◐ | · | · | · | ● | · | · | · | ◐ | · | · | · | ◐ |
| PM-Bench (2607.12385) | verified; [code] | ◐ | ◐ | ◐ | ◐ | ◐ | ◐ | · | · | · | ◐ | ◐ | · | · | · | · | · | · | · | · | · |
| MemoryArena (2602.16313) | verified; [code] | ◐ | · | ◐ | ◐ | ◐ | ◐ | · | · | · | · | ◐ | · | · | · | · | · | · | · | · | · |
| ActiveGraph (2605.21997) | single; [abs] + [code] + probes | ● | ● | ◐ | ◐ | ● | ● | ● | ● | ● | ◐ | ◐ | ◐ | ◐ | · | · | · | · | · | ◐ | ◐ |
| Shepherd (2605.10913) | single; [abs] + experiment code | ● | ● | ◐ | ◐ | ● | ● | ● | ● | ● | · | · | ◐ | ◐ | · | · | · | · | · | ◐ | ◐ |
| DeepRewind (2609.36344) | single; [abs] + [code] + probe | ● | · | ◐ | · | · | · | · | ◐ | ◐ | ● | ● | ◐ | · | · | ◐ | ◐ | ◐ | · | ◐ | · |
| FutureSim (2605.15188) | single; [abs] + [code] | ● | ● | ◐ | ◐ | ◐ | ● | ● | ◐ | ◐ | ◐ | ● | · | ◐ | ● | · | · | · | ● | ◐ | · |
| Forecast-Dojo (2609.28876) | single; [abs] + [3p] full text | ◐ | ◐ | ◐ | · | ◐ | ● | ◐ | · | · | ● | ● | · | ◐ | ● | · | · | · | ● | ◐ | · |
| Calibration Is Not Control (2606.21399) | single; [abs] + [3p] full-text digest | · | ◐ | ◐ | · | ◐ | ◐ | ● | ● | ◐ | · | ◐ | ◐ | ◐ | ◐ | · | ● | ◐ | ● | · | · |
| Trellis / Experience Graphs (2606.29823) | single; [abs] + [3p] full text; **design only** | ● | ◐ | ● | ◐ | ● | ● | ● | ● | ● | ◐ | · | · | · | · | · | · | · | · | ● | ◐ |
| AER (2603.21692) | single; [abs] + [3p] full text | ◐ | · | ◐ | ◐ | · | ● | ◐ | ◐ | ◐ | ◐ | ◐ | · | · | · | · | · | · | ◐ | ◐ | · |
| ChronoMem (2607.27773) | single; [abs] + [3p] | ◐ | · | ● | · | ◐ | ◐ | · | · | · | · | · | · | · | · | · | · | · | · | ◐ | · |
| Corollary (GitHub, JTMS) | single; [code] + probes | ◐ | · | ◐ | · | ◐ | ◐ | · | · | · | ● | ● | · | · | · | · | · | · | ◐ | ◐ | · |
| Memvara (GitHub, bitemporal) | two single reads; [code] + probes | ◐ | ◐ | ◐* | ◐ | · | · | · | · | · | ● | ◐ | · | · | · | · | · | · | · | ● | ◐* |

\* Two independent deep reads of Memvara disagreed:
- capability 3: partial vs yes;
- capability 20: partial vs no.

The table shows the more conservative reading on 3 and the more generous
reading on 20 (◐; the second read gave ·).

**Caveats on the single-read rows:**
- **Trellis** describes a design and never evaluates its time travel, so its
  "yes" cells are as described, not demonstrated.
- **Shepherd's** fork and replay live in the frozen experiment code behind the
  paper. The public library v0.3.1 lists replay as a "direction".

## 3. Matrix B: concept-level references, this repository, and the target

These rows are mostly not agent systems. They show that the capabilities
agent systems leave thin (13, 15 and 17) are covered outside agents, by
decision-theoretic, causal-inference and planning work. Database work covers
the retrospective columns (1, 2 and 19). Two concept rows include LLM-agent
works (BAR, SafePred), rated from abstracts only and not deep-read.

Concept-row ratings come from the lane evidence in research-landscape §3.
The baseline row comes from the code in `src/baseline/` and `src/harness/`.

| reference | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Bitemporal DBs + event sourcing + data versioning (XTDB, Datomic, eventsourcing, Dolt/lakeFS, W3C PROV) [ns] | ● | ● | ◐ | · | ◐ | ◐ | ◐ | ◐ | ◐ | · | · | · | · | · | · | · | · | · | ● | · |
| Potential outcomes + conditional-forecast annulment (Dickerman & Hernán; Metaculus Conditional Pairs; decision markets; performative prediction [unv]) [ns] | · | · | · | · | · | · | · | · | · | · | ● | · | ◐ | ● | · | ● | ● | ● | · | · |
| Option preservation and feared-future constraints (relative reachability, AUP [unv]; SafeCommit, LCPI, SafePred, SIMMER [abs]) | · | · | · | · | · | · | · | ◐ | · | · | ◐ | ◐ | ◐ | ◐ | ● | ◐ | · | · | · | · |
| Goal regression / backward planning (classical regression planning; BAR 2505.14079 [abs]) | · | · | · | · | · | · | · | · | · | · | · | · | · | · | ● | · | · | · | · | · |
| **This repo: Milestone 2 conventional baseline** [code] | ● | ● | ◐ | ◐ | ◐ | ◐ | · | · | · | ◐ | ◐ | · | · | · | · | · | · | · | ◐ | · |
| **NORTH_STAR.md target** | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● | ● |

Notes on Matrix B:

- **Bitemporal DBs.**
  - 3 is partial: transaction time gives "what the store had recorded at t",
    which is exactly an agent's knowledge state if the agent's beliefs are the
    store's rows. XTDB's docs present `FOR SYSTEM_TIME AS OF` for data "as we
    knew it at the time, without subsequent corrections".
  - 7 is partial: Dolt and lakeFS branch data from earlier commits (data
    only, not agent state).
  - 8 is partial: Datomic `d/with` applies a transaction speculatively
    without committing it.
- **Potential outcomes and annulment.**
  - 17 is "yes" as a scoring practice: Metaculus annuls the unrealized
    conditional ("It is not scored").
  - 16 is the definition of a forecast P(Y^a | H_t) under a named strategy.
  - Neither is an agent capability. Both are the formal treatment an agent
    would adopt.
- **This repo's baseline** (`src/baseline/`):
  - 1: `events.jsonl` is append-only and fsynced before any processing.
  - 2: the A1 world-history tools `read_at`/`list_at`/`diff` give every
    contestant past repository states.
  - 3 is partial: per-event notes and `memory_search` take seq filters, but
    `summary.json` is overwritten. The context the agent saw at t is kept
    only in the harness trace (every model request), which no contestant can
    query.
  - 4 is partial: `metadata.json` records the model, the instruction version
    and hash, and the preset; `events.jsonl` keeps every delivered
    requirement change append-only. Nothing versions policy within a run,
    and the agent does not consult these records (as for MemoryArena).
  - 5 is partial: `checkpoint.json` keeps only the latest state, for
    restart.
  - 6 is partial: replay exists only at harness level, as recorded-backend
    re-serving, and is not agent-facing.
  - 10 is partial: the rolling summary is free text that is asked to keep
    "decisions in force with their stated reasons and assumptions".
  - 11 is partial: notes and summary are asked to keep assumptions and open
    or blocked work, in free text; there are no confidence fields.
  - 19 is partial: A1 diffs over world states and seq-filtered memory search.
  - The baseline is therefore weaker than FlowState, PoS and Memvara on 10
    (◐ vs ●), and weaker than Memvara on 19 (◐ vs ●). On 3 it matches all
    three at ◐; Memvara reaches ● only under the second deep read. PlanFence
    is not rated in this matrix.

## 4. Column-level findings

What each capability's column shows across all 26 rows:

| # | best coverage found | verdict |
|---|---|---|
| 1-2 | ActiveGraph, Shepherd, FutureSim (●); bitemporal DBs (● concept level) | saturated |
| 3 | ChronoMem (● memory layer, with a read-scoping invariant and a post-exposure leakage protocol); Trellis (● as design); Memvara known_at, PoS belief snapshots, LangGraph `get_state`, FlowState request tags (◐) | **mechanism exists.** Every partial is a leak or a missing API, not a missing concept. |
| 4 | ◐ at most (13 of 25 rows; · in the rest): LangGraph config capture and server assistant versions; Graphiti procedure entities; AER envelope; OTel GenAI conventions (research-landscape §3.8) | solved as data and attribution; no agent *uses* it |
| 5-9 | LangGraph, ActiveGraph, Shepherd, MAGE (fork ●), COUNTERMEM and Calibration Is Not Control (counterfactual branches ●) | saturated |
| 10-11 | 10: FlowState, PoS, DeepRewind, Forecast-Dojo, Corollary, Memvara (●); 11: PoS, DeepRewind, FutureSim, Forecast-Dojo, Corollary (●) | saturated |
| 12 | ITP (●); ActiveGraph, Shepherd, DeepRewind, COUNTERMEM, Calibration Is Not Control (◐) | established (ITP, RAP, WebDreamer, WMA) |
| 13 | ◐ at most (8 of 25 rows; · in the rest): several executed forks (Shepherd, ActiveGraph), several outcomes of one question (FutureSim, Forecast-Dojo), conditional pairs (concept level) | no persisted set of imagined multi-step futures in any rated system |
| 14 | FutureSim and Forecast-Dojo (●, as probabilities over outcomes); potential outcomes (● concept level) | established |
| 15 | PoS and DeepRewind (◐); goal regression and option preservation (● in Matrix B, including LLM-agent works BAR and SafePred rated from abstracts) | no deep-read agent persists *derived* obligations, but the computation is classical |
| 16 | Calibration Is Not Control (●); ITP and DeepRewind (◐) | established for agents |
| 17 | Calibration Is Not Control and DeepRewind (◐, incidental); annulment (● as practice) | **no agent keeps averted forecasts as typed records.** This is a thin schema addition with a positivity limit (residual-hypotheses.md §4). |
| 18 | FutureSim, Forecast-Dojo, Calibration Is Not Control (●) | established |
| 19 | Memvara and Trellis (●); bitemporal DBs (● concept level); many ◐ | established |
| 20 | ◐ at most. ActiveGraph, Shepherd, LangGraph and MAGE unify historical, actual and counterfactual. ITP pairs present and imagined future state (◐) but has no history. No system spans all four kinds. | one of three columns with no "yes" (with 4 and 13); here the gap is integration (research-landscape §4) |

**Reading the matrix adversarially.** Computed from the tables above,
excluding the target row:

- **"Yes" in some agent system:** capabilities 1-3, 5-12, 14, 16, 18 and 19.
- **"Yes" only in Matrix B rows:** 15 (backward requirements) and 17
  (prevented futures).
  - 15: classical regression planning, but also LLM-agent works (BAR,
    SafePred) rated from abstracts only and not deep-read.
  - 17: scoring practice only (conditional-forecast annulment).
  - Among deep-read agent systems, both are at most partial.
- **No "yes" anywhere:** 4, 13 and 20.
  - **4 (historical policy/objective state)** is at most partial among the
    systems rated here (◐ in 12 of 20 agent rows, and in this repo's
    baseline). The tooling that solves it as data (OTel GenAI
    attributes, MLflow, Langfuse and LangSmith versioning) was not rated as a
    row, and no agent *uses* such records when deliberating.
  - **13 (multiple prospective branches)** is at most partial (◐ in 6 of 20
    agent rows and 2 concept rows). Agent
    systems hold several executed forks or several outcome probabilities, but
    no system maintains a set of imagined, multi-step alternative futures
    that persists. Scenario-ensemble work (FORESIGHT-9, ForecastBench-Sim,
    RDM) was found by the sweep but not deep-read.
  - **20 (unified abstraction)** has no "yes". The closest systems
    (ActiveGraph, Shepherd, LangGraph, MAGE) unify historical, actual and
    counterfactual state. They miss the prospective kind, which is covered
    by separate prior art (ITP, FutureSim, potential outcomes). ITP pairs the
    present with an imagined future but has no history.

None of the three gaps is a missing concept:
- 4 is an agent-side use of existing records;
- 13 is a persistence choice over existing rollout and scenario machinery;
- 20 is composition.

The matrix therefore supports research-landscape §4: what is left is
composition and agent-side use, not a missing capability.

## 5. Justification of non-obvious cells

Per-cell evidence for every Matrix A row is in the evidence file linked at
the top.
The cells most likely to be challenged:

**MAGE.**
- **3 ◐.** Revise restores the agent-facing memory (C, R) to a step-id
  boundary, then **injects hindsight** through H (diagnostics and
  alternatives from the later branch). There is no query and no cutoff.
- **7 ●.** "Revise restores a target boundary and resumes on a new branch"
  (verbatim abstract), and the flawed segment is kept as an inactive sibling
  [ext].
- **6 ◐.** Execution resumes from a historical point; deterministic replay
  is not described.

**FlowState.**
- **3 ◐.** Judgement nodes are tagged with their source request and cannot
  be deleted (D7 is kept after D8), so "known then" is the filter
  `source_request <= k`.
- **3 is not ●** because there is no as-of operator and disclosed history
  sits next to current knowledge.
- **19 ◐.** States are addressable by id and relation, but not by time.

**LangGraph.**
- **3 ◐.** `get_state(checkpoint_id)` returns the in-graph state at a
  super-step, a natural cutoff. Re-execution, however, uses the *current*
  tools, LLM and Store: probe 3 read the present Store value during a replay.
- **4 ◐.** Each checkpoint copies primitive `config.metadata` and
  `configurable` keys, and the Agent Server versions assistants. Runtime
  `context=` is not recorded.
- **8 ◐.** Forks are real executions with side effects, not simulations.

**PoS.**
- **3 ◐.** `belief_update_history` and `belief_snapshots` are written at
  commit time, so they carry no hindsight (verified by re-running a probe).
  The policy never reads them.
- **15 ◐.** Achievement gaps are the difference between goal and belief:
  one level, regenerated each step, with no feared futures.

**Graphiti.** **3 ◐.** `created_at`/`expired_at` approximate what the graph
held at t, but `invalid_at` is overwritten in place (a hindsight leak) and
nodes are unversioned.

**COUNTERMEM.** **8 ●.** "a copy or reset of the original state", local
alternatives, executable verification (verbatim abstract). Ratings 12 and 13
rest on the same sentence and are not independent evidence.

**ITP.**
- **16 ◐.** Rollouts are conditioned on the policy's own imagined actions,
  but there is no passive forecast.
- **20 ◐.** The POIMDP pairs the present with an imagined future, but has no
  history and no branches.

**ActiveGraph.**
- **3 ◐.** The as-of graph projection is strict. Forks pre-fill LLM and tool
  caches from the parent's **full** log, and probe E delivered a post-cutoff
  observation.
- **7 ● and 9 ●.** `Runtime.fork(at_event)` with
  (parent_run_id, forked_at_event_id, label).

**DeepRewind.**
- **15 ◐, 16 ◐, 17 ◐.** A one-step world-model prediction of its own commit
  action gates commitment by a reversibility score. Blocked-commit
  predictions remain in the append-only world-model log
  (`decision=not_commit`), and the claim is kept through a separate
  "retain_as_contested" plan step. The preservation is incidental, with no
  scoring semantics.
- A probe with default thresholds found that **organic contradictions did
  not fire rollback** (only the synthetic switch injection did), and no
  organic code path sets source reliability. Whether the paper's results
  used this path is unknown.

**FutureSim and Forecast-Dojo.**
- **14 ● and 18 ●.** Both keep explicit distributions scored by Brier.
  FutureSim feeds results back to the agent during the run ("Your prediction
  distribution ... | Truth ..."). Forecast-Dojo attaches the scores to logged
  trajectories for training; its agent never sees outcomes within an
  episode.
- **17 ·.** The world does not react to the agent, so there is nothing to
  prevent.

**Calibration Is Not Control.**
- **16 ●.** Intervention advantage replaces passive risk as the decision
  object.
- **17 ◐.** Same-prefix branching yields the continue-branch outcome even
  when an intervention averts failure, so a passive forecast is checked
  against a counterfactual rather than counted wrong. This is inferred from
  the protocol; nothing is persisted.

**ChronoMem.** **3 ●**, memory layer only. "after rollback to v*, every
subsequent read is scoped to v*" [3p], plus a post-exposure protocol testing
"whether an agent can behave counterfactually after rollback" [abs].

**Memvara.**
- **2 ◐.** `valid_at=` gives a valid-time view of stored fact claims only,
  as for Graphiti, not of the environment.
- **3 ◐.** `known_at=` / `as_of=` per fact slot. Row-level as-of reads apply
  later-recorded endings, as documented in its INTERNALS and confirmed by a
  probe.
- **19 ●.** Eight reads take time arguments, plus `since(T)`.

**Corollary.** **10 ●, 11 ●.** A JTMS belief base with IN/OUT labels,
justifications, TTL and decay. Retraction cascades through dependents. A
probe found that a later fact on a *different key* leaves a decision in
force.
