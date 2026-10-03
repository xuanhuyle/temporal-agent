# Literature sweep digest (10 lanes)

NOTE: the session WebSearch budget ran out during the sweep; several lanes used a local corpus of 117,831 verbatim arXiv cs.AI/cs.CL abstracts (Dec 2024-Sep 2026, from a GitHub daily-listing mirror), cloned repos, and curated lists.

######## LANE exec-state (15 works, 52 queries)
QUESTIONS: Q1. Which systems already provide fork/replay/branch provenance for agent state?

Many do, and the space is crowded in 2025-2026:
- ActiveGraph (arXiv 2605.21997; I verified this in the code). Runtime.fork(at_event) copies the log through at_event into a new run_id and replays it into a fresh graph. It then supports structural diff against the parent. Lineage is stored as (parent_run_id, forked_at_event_id), and goal-to-LLM-call lineage is recoverable.
- Shepherd (2605.10913). A Git-like typed execution trace where 'any past state can be cheaply forked and replayed'. It forks the process plus filesystem, and its core operations are Lean-mechanized.
- AgentGit (2511.00628; repo verified). Commit, revert and branch, where 'Rollbacks create new branches, preserving all timelines', plus tool-effect reversal.
- OpenRath (2606.19409). The Session is branchable and replayable and records lineage metadata.
- GCC (2508.00031). The agent itself issues COMMIT, BRANCH and MERGE over its reasoning context.
- Planarian (2609.35366). Snapshot, rollback and fork over local and remote environment state, using compensating actions.
- StateFork/Waypoint (2609.38648), DeltaBox (2605.22781), Crab (2604.28138) and BranchFS (2602.08199). Fast fork and restore of sandboxes.
- ACRFence (2603.20625). An effect log carrying branch identifiers.
- Chronicle (2609.20625). Cut-point replay over immutable envelopes.
- Causal Agent Replay (2606.08275). do-interventions at historical steps with forward re-execution.
- OpenHands SDK (2511.03690). Event-sourced S_t = f(S_{t-1}, e_t) with deterministic replay.
- Temporal-style durable execution. Event-history replay.
- Formal semantics already exist: 'When Can Agents Safely Checkpoint, Fork, Restore, and Merge?' (2608.22928) and 'Resume Means Resume' (2608.03836, TLA+).

Q2. Does any of them restore the agent's belief or reasoning state (not just messages) at a historical point?

Partially, yes, in several forms:
1. Structured working state replayed to a strict prefix. ActiveGraph's fork rebuilds the agent's typed graph of objects and relations from events up to and including at_event. That is an as-of reconstruction of whatever the agent represents in the graph, with no later events.
2. Full process state. Shepherd and Planarian snapshot the agent process, so any in-process belief structure comes back with it.
3. Memory state with a no-hindsight test. ChronoMem snapshots the whole memory at every write and evaluates 'whether an agent can behave counterfactually after rollback ... as if future updates never occurred'. This is the closest prior art to the project's strict epistemic cutoff.
4. Typed epistemic graph with dependency-aware rollback. DeepRewind models sources, evidence, claims, hypotheses, assumptions and commitments, and rolls back commitments when later evidence invalidates them.
5. Controlled hindsight at the restore boundary. RIR removes 'state claims invalidated by restoration' and passes only distilled reflection across. AgentRewind restores the agent context and injects rewind memory.
6. Message-level only. Claude Code /rewind, AgentGit and LangGraph restore conversation and checkpoint state.

What I did not find in this lane is any system that combines three things:
- (a) a first-class query, 'what did I believe/intend/what policy governed me at t, excluding everything after t';
- (b) the same abstraction used for prospective futures, with probabilities and backward requirements;
- (c) bookkeeping of prevented forecasts and of predicted versus realized outcomes.

Also missing are explicit historical objective/policy-state records. The closest are ActiveGraph's pack and config forks and the authority-at-decision-time work.
VERDICT: The execution-state lane removes most of the project's infrastructure novelty.
- Append-only histories, as-of reconstruction, checkpoint/restore of agent context plus environment, forking from any historical event with preserved parents, branch lineage, structural diff between branches, and counterfactual re-execution from past decisions are all published and often open-sourced in 2025-2026. ActiveGraph and Shepherd are the strongest; AgentGit, OpenRath, Planarian, AgentRewind and the OpenHands SDK add to them.
- Fork/restore semantics have been formalized (Lean, TLA+), and their safety failures are already catalogued (Safe to Resume?, ACRFence).
- ChronoMem already evaluates no-hindsight behaviour after memory rollback.
- DeepRewind already implements and measures the benchmark's target behaviour: a later piece of evidence invalidates an earlier commitment, which is then reopened through dependency-aware rollback over an explicit epistemic graph, together with reversibility estimates before committing.
- GitOfThoughts reports accuracy parity between a versioned, replayable reasoning substrate and simpler memory. That is a direct prior null for the claim that temporal navigation improves performance.

What survives in this lane:
- (1) Treating the agent's epistemic, objective and policy state at t as a first-class, cutoff-enforced query target, rather than a side effect of process or memory snapshots.
- (2) Unifying that historical machinery with prospective branches, backward requirements, prevented-forecast preservation and predicted-versus-realized calibration under one abstraction.

The project should therefore drop 'fork/replay/provenance' as a contribution. It should include an ActiveGraph/AgentGit-style fork baseline and a DeepRewind-style dependency-graph baseline, alongside checkpoint+RAG. Its hypothesis should be narrowed to whether cutoff-correct historical self-interrogation plus prospective/backward reasoning beats dependency tracking with rollback on decision-reopening tasks.

######## LANE belief-state (15 works, 49 queries)
QUESTIONS: Q1: Is "keep current beliefs, and detect when new evidence invalidates an assumption behind an earlier decision" already a studied capability with methods and benchmarks?

Yes. It is a crowded topic in 2026.

Benchmarks:
- STALE (2605.06527): 400 scenarios scored on State Resolution, Premise Resistance and Implicit Policy Adaptation (whether the agent applies an updated state in later behavior without being prompted). It names "implicit conflict", where a later observation invalidates an earlier memory without explicitly negating it. The best model reaches 55.2%. A prototype gets 91% on State Resolution but only 32% on Implicit Policy Adaptation.
- StateMemBench (2608.19652): 234 scenarios in which "facts, constraints, and decisions are revised". Ground truth comes from deterministic replay of symbolic event programs, which is nearly the project's own benchmark design.
- ClawArena (2604.04202): 64 scenarios with 365 updates, where "new information can invalidate earlier conclusions".
- Others: ManBench-Return (from TRACE 2609.33517), BeliefShift (2603.23848), FinalityBench (2609.04706), and two coding benchmarks with evolving requirements, EvoCode-Bench (2605.24110) and SlopCodeBench (2603.24755).

Methods:
- MemTX (2607.23929): retracting a belief "triggers typed cascading repair of its derived records and tool side effects", and irreversible tool calls are gated on the current belief state.
- PlanFence (2609.03340): calls the problem "derivation currency". Each plan stores links to the inputs it was derived from, and those inputs are rechecked before a protected action. It succeeded in 30/30 runs, versus 0/30 for a check that only compares against current state.
- Corollary (GitHub): truth-maintenance retraction cascades with a kept revision history.
- StateAuditor (2608.01619): repair is triggered by old-to-new transitions whose chronology has been verified.
- Smaller mechanisms: SyncPlan's Plan Staleness Detector (2608.01652), IDSS propagating new facts into action executability (2608.15755), and PCE treating assumptions as decision-tree nodes (2602.04326).
- Foundations: Doyle's truth maintenance system (1979) and de Kleer's assumption-based version.

What I could not find:
1. A benchmark that explicitly scores reopening and remediating an already executed decision. Existing benchmarks score current answers or later behavior. MemTX's repair of tool side effects is the closest.
2. Strong coverage of cases where the earlier fact stays true but a later event changes its significance. STALE's implicit conflict and TRACE's "inadmissible for action" cover this only partly.
3. A standard evaluation of recovery from corrected inputs. The Corollary README says so directly: "There is no standard evaluation for how well an agent recovers from a corrected input."

Q2: Is versioned belief state (what the agent believed at time t) studied?

Yes, mainly as memory or database infrastructure, and some of it is evaluated.
- Memvara: offers known_at=T ("what we believed at T") and as_of=T queries, so a later correction does not leak into the past view.
- TGMS (2607.10265): explicitly requires "reconstruction of prior belief states" when records are corrected. On correction probes it scores 0.897, versus 0 for two latest-state baselines and 0.154 for vector-RAG.
- TOKI (2606.06240): keeps the losing fact in an audit row and names "replay inconsistency, belief-drift skew, and audit erasure" as failure modes.
- A bitemporal graph store (2607.26520) keeps immutable identity nodes linked to versioned content.
- Kumiho (2603.17244) uses immutable revisions and proves standard belief-revision properties for them.
- A-TMA (2607.01935, seen only in a search extract) keeps superseded records for "what was true before" questions.
- Graphiti/Zep is covered in another lane.
- HindsightBench (2607.18867) audits hindsight leaking from model weights into dated decision tasks.

Not covered by any of these, and not found anywhere in 47 searches:
- versioning the agent's whole decision-time state (beliefs, plans, assumptions, uncertainty, policy), not just a fact store;
- an agent querying its own past state to decide whether to reopen a past decision;
- measuring that against a strong checkpoint-plus-retrieval baseline.
VERDICT: This lane undermines most of the project's belief-related claims. Keeping an explicit current belief state with uncertainty is established: Agent-BRACE, PABU and BeliefMem do it, and IDSS (2608.15755) keeps an explicit situation state that separates grounded facts from task judgments. So is detecting that a later event invalidates an earlier belief, which STALE, StateMemBench and ClawArena already benchmark. Repairing whatever depended on an invalidated belief is established too (MemTX, PlanFence, Corollary, and truth maintenance since 1979). Even "what did the agent believe at t, without hindsight" is commodity infrastructure: Memvara has a known_at/as_of API, TGMS evaluates it with correction probes, and TOKI and Kumiho do the same with formal grounding. What is left is narrow, and it is empirical rather than conceptual. Does making the agent's whole decision-time state addressable in time (assumptions, plans, policy, not just facts) beat a strong non-temporal baseline at reopening and remediating already executed decisions? That matters most when a later event changes an earlier decision's significance without contradicting any stored fact. The adversarial risk is that the property the project attributes to "temporal navigation" really comes from dependency links: PlanFence's derivation links and truth-maintenance justifications solve the stale-assumption case without any time abstraction. To keep a distinct hypothesis, the benchmark needs two extra contestants or ablations alongside checkpoint + RAG: a dependency-tracking agent (PlanFence/MemTX/Corollary style) and an explicit current-state wrapper (StateMemBench style). It also needs scenarios where those fail and as-of reasoning is needed: the significance changes with no fact being superseded, and the question is what the agent could reasonably have known at decision time. If dependency tracking matches the temporal contestant, the temporal hypothesis does not survive in this lane. One small gap is real: Corollary's README (Oct 2026) states there is no standard benchmark for recovery from corrected inputs.

######## LANE temporal-memory (15 works, 26 queries)
QUESTIONS: EVIDENCE CAVEAT: WebSearch was exhausted session-wide before this lane ran, and GitHub, PyPI and other search routes were blocked. Evidence therefore comes from primary repositories (cloned or raw-fetched, quoted verbatim) and from 17 fetched curated paper lists. For arXiv items found only in the lists, the evidence is the list's Chinese summary in my translation; those abstracts were not read and should be re-verified before citation.

Q1. Which existing systems support querying memory as-of a past transaction time ("what the agent knew then") vs valid time?

(a) Databases support both axes, and have for decades.
- XTDB is bitemporal by default. Its docs say "system-time referred to 'transaction time'". Auditing that needs data "'as we knew it at the time', _without_ subsequent corrections" is "the use case for `FOR SYSTEM_TIME AS OF ...`"; FOR VALID_TIME AS OF gives the corrected world timeline. The docs also sell "leakage-free training matrices" and backtesting "as-of successive moments in time ... without the need for explicit snapshots".
- Datomic offers d/as-of on transaction instants or txids, plus d/since, d/history and transaction-level provenance (:source/user). d/with gives speculative, uncommitted database values. Valid time was not verified.
- Event-sourced stores give transaction-time state-at-version, e.g. repository.get(id, version=N), but no valid time unless it is modelled.
- Dolt and lakeFS give commit-level "time travel and see lineage" plus branch diffs; this is transaction time only.

(b) Agent memory with an explicit known-at (transaction-time) axis.
- Memvara: valid_at= / known_at= / as_of= on every read.
- kaeru: native assertion/retraction Validity, and `at` reads "as-of any past moment".
- Talamus: `ask --as-of`, plus valid-time windows on facts.
- TOKI (2606.06240): bitemporal operator algebra with audit rows.
- MemStrata (2606.26511): bitemporal ledger, per the list summary.
- Covered elsewhere: Graphiti/Zep; TGMS (2607.10265, sibling lane); Graph-Native Bitemporal Store (2607.26520, sibling lane).
- Transaction-time-only version snapshots: ChronoMem (2607.27773), GitHarness (2609.36789), AgentGit, ActiveGraph.
- Mem++ keeps every dated version and filters by the question's time; that is valid/document time, and its transaction axis is unclear.

(c) Mainstream memory without as-of querying, judging from the READMEs.
- Mem0 2.x is now "ADD-only ... nothing is overwritten" with "time-aware retrieval", but per Memvara: "There is no time. One `updated_at` column".
- A-MEM: "dynamic memory evolution and updates", update()/delete().
- MemoryOS: the long-term profile is updated in place.
- MemOS: correct/replace via feedback.
- MIRIX: auto-dream "writes the result back".
- LangMem: "consolidates, and updates".
- Letta and Memory-R1: not verified.

(d) The empirical point that matters most for the project. In Memvara's cross-system benchmark, a single-clock vector-RAG over the full write log scores 100% on knowledge_time, current state, change time and provenance. Bitemporal memory wins only on historical_state (100 vs 85.2), driven by delayed-knowledge and correction cases, which Memvara puts at about 9% of temporal questions. "What the agent knew then" is therefore cheap: any append-only, ingestion-timestamped log with an as-of filter provides it. Two-axis temporal state matters only when valid time and transaction time diverge.

Q2. Is "never overwrite time, fork it" just event sourcing + bitemporality?

Substantially yes, plus Git-style branching and PROV-style provenance.
- "Never overwrite": an append-only event log ("a left-fold over a stream of events"), XTDB's immutable log, Datomic's history database, Mem0's ADD-only store.
- Addressable past world state vs past epistemic state: valid time vs transaction time.
- "Fork it" and diff: Dolt "fork, clone, branch, merge" and dolt_diff between branches; lakeFS zero-copy branches; Datomic d/with speculative values; on the agent side AgentGit "Non-Destructive Branching ... preserving all timelines" and ActiveGraph fork-at-event.
- Branch provenance: W3C PROV wasDerivedFrom / wasRevisionOf / wasInvalidatedBy / bundles.
- Policy or objective change over time: just another entity with its own timeline in a bitemporal store.

What these substrates do NOT provide by themselves:
1. Semantics for prospective, intervention-conditioned branches with likelihoods.
2. A "prevented, not wrong" forecast status.
3. Predicted-vs-realized links to the branch actually taken.
4. The behavioural claim that the agent will use as-of and diff queries to notice that a later event changes an earlier decision's significance.

Items 1-3 are thin schema additions on a bitemporal + branching store: a forecasts table keyed by branch, with valid-time ranges and a status column. Item 4 is directly targeted by existing methods and benchmarks:
- Dependency-Guided Rollback Repair (2608.10502)
- StateGuard (2609.34134)
- Execution-State Unlearning (2609.04875)
- Impact Is Not Invalidation (2609.25130)
- Correct Now, Insufficient Later (2609.20045)
- Belief-lane MemTX, PlanFence and STALE

So the slogan is not a new computational abstraction. Any residual novelty is behavioural and evaluative.
VERDICT: This lane is saturated at the storage layer and crowded at the agent-memory layer. Querying what was known then vs what was true then (transaction time vs valid time) is textbook bitemporal practice. XTDB documents the exact no-hindsight use case ("'as we knew it at the time', _without_ subsequent corrections", leakage-free backtesting), and Datomic has as-of, history and speculative d/with. Event sourcing gives append-only replay and state-at-version, Dolt and lakeFS give fork/branch/diff/merge of state, and W3C PROV gives revision and invalidation provenance. In 2025-2026 these were ported into agent memory several times: Memvara (known_at/valid_at/as_of), kaeru, Talamus, TOKI, MemStrata, Mem++, ChronoMem, GitHarness, TGMS and Graphiti/Zep; Mem0 itself moved to ADD-only. The evidence on whether this beats strong RAG is mixed and partly hostile. MemStrata reports large gains over a similarity-only RAG on evolving software facts. But Memvara's benchmark finds a single-clock, append-only RAG over the write log already perfect on knowledge-time questions, with bitemporal gains confined to late or corrected facts (about 9% of temporal questions); LSREP reports a structured memory lagging vector RAG, and GitOfThoughts (sibling lane) found accuracy parity. "Never overwrite time, fork it" is therefore event sourcing + bitemporality + Git-style branching + PROV provenance, not a novel abstraction. What remains is (1) a cheap schema extension for intervention-conditioned prospective branches with prevented-vs-wrong status and predicted-vs-realized links, and (2) a behavioural hypothesis about agents reopening and remediating past decisions. Dependency-guided rollback repair, StateGuard, Impact Is Not Invalidation and Correct Now, Insufficient Later already target that behaviour. For a fair test, the checkpoint+RAG contestant must have ingestion timestamps and as-of filtering, and scenarios must declare how often valid time and transaction time diverge, since prior evidence says only that regime separates the approaches. Notes with verbatim snippets: /tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/lit/notes/sweep-temporal-memory.md

######## LANE counterfactual-worldmodel (15 works, 15 queries)
QUESTIONS: Evidence caveat: WebSearch was unavailable for this lane. All 4 attempts returned 'used its web search budget (200 of 200)'. Evidence comes from official repos cloned and read here (READMEs plus code), from abstracts in the AGI-Edgerunners parsed_v5 JSON, and from maintainer-written TLDRs in OSU-NLP-Group/GUI-Agents-Paper-List. Early Experience (2510.08558) and SimuRA are confirmed by title and URL only.

Q1: Is 'explore alternative branches from a past state and learn from them' already standard?

Yes, within an episode or a training loop. It shows up in four families:
- **Tree search with backtracking from earlier nodes:** LATS (2310.04406), Agent Q (2408.07199), ExACT R-MCTS (2410.02052), SWE-Search (2410.20285), WebOperator (2512.12692, 'verified backtracking before replaying prior paths') and Agent Alpha (2602.02995).
- **Retrospective branch-from-error data synthesis:** Agent-R finds 'the first error step' and splices 'the adjacent correct path, which shares the same parent node in the tree'. ANCHOR finds 'branch points'. Tree-GRPO and ARPO use tree rollouts. Early Experience, if the unverified recall is right, takes alternative actions at expert states.
- **Executed counterfactual replay from any historical decision point:** C3 (2603.06859) states 'the transcript is the whole state, so you can reset the run to any message, swap it, and play the rest out ... the counterfactual is executed rather than predicted'.
- **Imagined branches via LLM world models:** RAP, WebDreamer, WMA, WebEvolver, Dyna-Think, WALL-E 2.0, WebWorld, Qwen-AgentWorld (MCP/Search/Terminal/SWE/Android/Web/OS), WM-R1 and Discriminative World Models (2609.02885).

All of these, however, branch inside a single task episode or a training batch. They use hindsight on purpose (final reward or outcome) and impose no epistemic cutoff. Their purpose is search, credit assignment or training-data generation. None asks whether a later event changes the significance of an already-committed earlier decision in a long-lived agent.

Q2: Do any keep the counterfactual branches with provenance and reuse them later?

Only partially.
- **Provenance inside a search or training run:** MCTS trees in LATS, Agent Q and ExACT keep parent pointers. Agent-R splices siblings by shared parent node. C3 logs parent_id and parent_id_true per node.
- **Cross-task reuse with provenance:** ExACT does this. It computes |expected V_next - actual Q|, reflects on the most unexpected step, and saves ReflectionRecord(intent, state, action, next_state, reflection, _from_task_hash) to a persistent FAISS DB that later tasks retrieve. It persists the distilled lesson, not the branches. WebATLAS (TLDR only) 'reuses past interaction outcomes as persistent experience memory and simulates candidate actions'.
- **Discarded or consumed branches:** training pipelines (Agent-R, Agent Q, Tree-GRPO, ANCHOR) save branches as datasets that gradient updates consume, after which provenance is lost. WebDreamer's released modules return simulations in memory and never persist them. Rollback systems (WebRollback, GA-Rollback, BEAP-Agent) deliberately discard the abandoned branch.

Not found in this lane:
- a lifelong, queryable store of counterfactual or prospective branches with provenance;
- revisiting branches under a strict as-of epistemic cutoff;
- averted forecasts kept and labelled 'prevented' rather than scored wrong (WMA, SeerGuard and MirrorGuard avert simulated harms but drop the forecast);
- intervention-aware forecast scoring.

WALL-E 2.0 and ExACT do compare predicted with realized outcomes, but only to repair the world model or policy, not to audit forecasts.
VERDICT: For this lane, the counterfactual and prospective machinery in the thesis is well-established prior art, and none of it is a distinct hypothesis: simulating futures, branching alternative actions from earlier states, executing counterfactual replays from historical decision points, and comparing predicted with realized outcomes. The lineage runs from RAP and LATS (2023) through WebDreamer and WMA (2024) and WebEvolver, Dyna-Think, WALL-E 2.0 and Agent-R (2025), to C3, WebWorld, Qwen-AgentWorld, WM-R1, SeerGuard and the Discriminative World Models paper (2026). C3 in particular already implements 'fork from any past message, execute alternatives, keep parent provenance', and ExACT already persists expected-vs-actual reflections with task provenance for later reuse. WMA and SeerGuard already do one-step feared-future avoidance. Four things this lane did not cover could still be a narrow hypothesis:
(1) revisiting past decisions under a strict epistemic cutoff, whereas every work found uses outcome hindsight by design;
(2) branches persisted as first-class, queryable, provenance-carrying records across a long-lived agent's lifetime, rather than consumed by training or discarded by rollback;
(3) prevented forecasts kept and scored as interventions rather than errors;
(4) the benchmark behaviour of noticing that a later event changes the significance of an earlier committed decision and reopening it, which none of these works evaluate (they score within-episode task success).
To be fair, the checkpoint+RAG baseline should be allowed WebDreamer- or WMA-style lookahead, rollback, and an ExACT-style expected-vs-actual reflection memory. Those components are standard, and they may be enough for the reopen behaviour. Caveat: WebSearch was exhausted, so this sweep relied on cloned repos and curated lists, and may miss 2026 papers that use the project's own vocabulary ('regret', 'prevented future', 'epistemic cutoff'). Notes are at /tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/lit/notes/sweep-counterfactual-worldmodel.md.

######## LANE prospective-forecast (15 works, 53 queries)
QUESTIONS: Q1. Is interrogating simulated future states or selves studied, and did it show measurable decision benefits?

(a) Human-facing future selves: studied, with RCT evidence of psychological effects, not of better decisions.
- Future You (Pataranutaporn et al., FIE 2024, arXiv 2405.12514; n=344): anxiety fell (-0.68 vs +0.21 for control, p=0.001) and future self-continuity rose.
- Future You multimodal (2512.06106; N=92): FSC, well-being and motivation rose, with no difference between text, voice and avatar.
- Simulating Life Paths (2512.05397; N=192): showed decision *shifts* (single-sided avatars persuade; a system-generated third option gets adopted). Its own limitations say "we assessed decision intentions rather than implemented behaviors".
- No study measured decision quality or realized outcomes.

(b) Agent-side future simulation: studied, with mixed results.
- Positive:
  - WiA-LLM (2509.04791) reaches 74.2% accuracy forecasting game-state changes.
  - Prospection-Guided Retrieval (2605.14177) uses imagined next steps as retrieval probes and gets about 3x recall.
  - FORESIGHT-9 (2608.29372) and ForecastBench-Sim (2606.18686) evaluate agents across branching or paired-intervention futures.
- Negative:
  - "Current Agents Fail to Leverage World Model as Tool for Foresight" (2601.03905): agents invoke simulation in fewer than 1% of cases, misuse rollouts about 15% of the time, and sometimes lose up to 5% performance.
  - Forecast-Dojo (2609.28876): an explicit belief notebook carried across dates improved Brier for only 6 of 12 models.
  - FORESIGHT-9: a fixed equal-weight policy beat 31 of 36 adaptive runs.
- Not found: any agent that interrogates a simulated future version of *itself* (future policy, objectives or identity) and shows a measured decision benefit. This is the only unoccupied slice, and it has no supporting evidence either.

Q2. Are predicted-vs-realized comparisons used for agent self-calibration?
Yes, extensively, and by 2026 the area is crowded.
- At inference time:
  - FutureSim's official harness feeds per-question 'Your prediction distribution ... | Truth ... | Brier' back to the agent, with the instruction "use this to learn from mistakes and improve calibration". Its code keeps an append-only PredictionHistory with get_prediction_as_of().
  - EpiEvolve (2606.05513) stores forecast outcomes in episodic memory under a chronological no-leakage protocol: accuracy 0.629 vs 0.561 for the backbone; recovery lag 5 to 2 weeks.
  - Live-Evo (2602.02369): Brier improves 20.8% on live Prophet Arena.
  - ForeDreamer (2608.20920) keeps experiential memory.
  - Frontier Autolab (2609.36739) uses a historian-judge plus a persistent Playbook.
- At training time: outcome-based RL (2505.17989; ECE 0.042), Foresight Learning (2601.06336; Brier 27% better, calibration error halved), OpenForecaster (2512.25070), and Forecast-Dojo SFT.

What is NOT covered is the project's narrower variant: keeping forecasts that the agent's own intervention averted as labelled, unscored objects, distinct from errors.
- The nearest prior art is performative-prediction theory (2002.06673; self-negating predictions in 2602.04402) and ForecastBench-Sim's paired intervention worlds.
- The 2026 survey of forecasting agents (2608.23058) says explicitly that "existing evaluations do not yet establish reflexive effects" and lists "methods for handling feedback between deployed forecasts and the outcomes being forecast" as future work.

Caveat on coverage: WebSearch was unavailable (budget exhausted). Coverage comes from 117k verbatim arXiv cs.AI and cs.CL abstracts (2025-03 to 2026-10), GitHub code search, and cloned repos. HCI-only (cs.HC) work and work not cross-listed to AI/CL may be missed.
VERDICT: Most of this lane is already occupied, in some cases as plain benchmark infrastructure.
- Strict-cutoff replay of an agent's information state, append-only and as-of-queryable forecast histories, and predicted-vs-realized feedback to the agent all ship in FutureSim's public harness. Forecast-Dojo, WorldReasoner, OracleProto and BTF-2 also cover them.
- Self-calibration from realized outcomes has measured gains in EpiEvolve, Live-Evo and ForeDreamer, plus several RL recipes.
- Prospective obligations, i.e. stored intentions with triggers, have their own benchmark cluster: PM-Bench, TriggerBench, PIS, BudgetPM, ChronosBench and ProEvent. PIS also shows that a typed store with logic in code is enough to beat retrospective memory.
- The project's evaluation premise is already built into public benchmarks. A later event changing the meaning of an earlier decision, which then has to be revisited, is in MerchantBench (365 days, delayed outcomes, revisit earlier decisions). Silent world changes against a persistent plan are in VibeLifeBench.
- Branching alternative futures from one information boundary exist at the world level in FORESIGHT-9 and ForecastBench-Sim.
- Future-self interrogation is established only for humans. It shows psychological effects and persuasion-driven decision shifts, not better decisions.

Several results actively undermine the project's assumed benefits:
- Agents rarely use world-model foresight and often misuse it (2601.03905).
- A carried explicit belief state helps only half the models (Forecast-Dojo).
- Prompt-based epistemic cutoffs leak badly (2601.13717). Hindsight-free reconstruction therefore needs structural isolation, and even then parametric knowledge leaks.

The residual hypotheses this lane leaves are narrow:
1. An agent that keeps forecasts averted by its own interventions as labelled, non-error objects. This is a self-negating-prediction case covered by performative-prediction theory, but no LLM-agent implementation or evaluation was found, and the 2026 forecasting-agent survey calls reflexive feedback an open gap.
2. An agent that interrogates a simulated future version of its own policy or objectives, with a measured decision benefit. Nothing was found.
3. One abstraction that unifies the existing slices. Each slice exists separately, so unifying them risks being engineering rather than a testable hypothesis, unless an experiment shows the unified version beats a strong baseline: a FutureSim/EpiEvolve-style memory plus a typed intention store plus outcome feedback.

######## LANE backward-optionality (15 works, 33 queries)
QUESTIONS: EVIDENCE NOTE: WebSearch was exhausted (200/200) before this lane started, so it ran 0 web searches. Evidence comes from 117,831 locally parsed cs.AI/cs.CL arXiv abstracts (Dec 2024 to Oct 2026, cloned daily-listing repo), from cloned READMEs (DeepMind side_effects_penalties, AUP, AI Safety Gridworlds, SafeLife, EMAworkbench, ToolEmu, RAFA), and from sibling-cloned lists. The archive misses cs.LG/cs.RO-only papers. Unconfirmed items: DAPP signposts and tipping points (Haasnoot 2013), Ren et al. 2024 'Thinking Forward and Backward', and the arXiv id of Krakovna 2020.

Q1. Is deriving present obligations or option-preserving actions by reasoning backward from simulated futures already studied?
Yes. Every component exists, and for LLM agents the 'feared future constrains the present' part is a crowded 2026 subfield.
(a) Backward from desired states:
- Classical goal regression is still active (2511.11095: 'perform goal regression on the resulting plans').
- LLM backward planning exists: BAR (2505.14079, 'planning starting from the terminal state') and Goal-Mem (2605.12213, backward chaining).
(b) Option preservation from imagined future goals:
- Relative reachability (1806.01186).
- Krakovna 2020, where 'the agent receives an auxiliary reward for preserving the ability to perform future tasks'.
- AUP (1902.09725).
- Heitzig & Potham 2508.00159 (power over a goal distribution, by backward induction).
(c) Simulate the future, act from the present:
- RAFA (2309.17382): plan a long-horizon trajectory, execute the first action, replan, with sqrt(T) regret.
- LLMPC (2501.02486).
- FLARE (2601.22311): value propagation back to early commitments.
(d) Feared or delayed futures turned into present constraints for LLM agents:
- SafePred (2602.01725): 'aligning predicted future risks with current decisions', with step-level interventions and task-level re-planning.
- JANUS (2607.19913): anticipation task plus adjudication.
- SIMMER (2606.14574): foresight simulation cuts irreversible failures by up to 75%.
- DreamGuard (2608.05695), SeerGuard (2607.15550), ARTIS (2602.01709) and SafeMCP (2606.01991).
(e) Robust or regret-style choice across plausible futures:
- SafeCommit (2608.04289): act only if safe in every retained world, otherwise take a low-side-effect probe or fallback.
- LCPI (2609.36741): act so that all remaining models admit a common continuation, with a last-identifiable-margin boundary.
- RDM/DMDU tooling (EMAworkbench).
- Plaut et al. (2502.14043): regret guarantees with irreversible costs.
(f) Reversibility estimation and reopening commitments:
- DeepRewind (2609.36344) estimates reversibility before committing and does 'dependency-aware rollback when later evidence invalidates them'.
- Irreversibility budgets (2609.00275) and EvoUndo (2608.28363).
(g) Benchmarks of delayed or irreversible significance:
- FinalityBench (2609.04706): hidden canonical event log, delayed and reordered events, irreversible actions, twin pairs indistinguishable at decision time; LLMs discover finality gating unprompted.
- SIMMER, AgentAbstain (2607.10059) and REVERSAL-BENCH (2609.17745).
Conclusion: the computational abstraction is not novel. The project cannot claim backward requirements or option preservation as a contribution in themselves.

Q2. Where is the residual gap for LLM agents?
It is narrow and mostly about persistence over time and evaluation, not mechanism.
(1) Feared futures are consumed immediately. In every LLM work found they are used once, at decision time, to block, prune, gate or replan the next action. None stores derived obligations or option-preserving conditions as first-class, timestamped, provenance-carrying state that is re-checked as later events arrive. That is the DAPP signpost/trigger pattern, which I could not even confirm in fetched sources. TriggerBench (2606.23459) and PM-Bench test prospective memory for obligations that are given, not derived.
(2) No reopening of executed external decisions. No work found scores whether an already executed decision preserved options in light of a future revealed later, and then remediates it. DeepRewind does this for epistemic commitments, and memory-rollback work (sibling lanes) does it for memory records. FinalityBench handles delayed information before an irreversible act, not reopening after it.
(3) Forecasts are not kept for calibration. No guardrail paper keeps blocked or averted risk forecasts, labelled as prevented rather than wrong, for later calibration. JANUS rewards forecasts by decision utility instead of accuracy, which only partly touches this.
(4) Evaluation without hindsight is missing. No backward or optionality evaluation was found that scores against the agent's information at time t.
Caveat: a strong checkpoint+RAG baseline prompted to 're-check prior commitments when new events arrive' may close gaps (1) and (2). FinalityBench shows plain LLMs discovering gating behaviour on their own. So the remaining hypothesis is empirical: does persisted, provenance-tracked feared-future state beat retrieval plus a re-check prompt on retroactive-significance tasks? It is not a new capability.
VERDICT: This lane offers little novelty to defend. Every piece of the thesis's 'backward requirements and option preservation' already exists. Goal regression and LLM backward planning cover it (classical regression planning, BAR, Goal-Mem). Option preservation from hypothetical future goals has been formalised since 2018-2020 (relative reachability, Krakovna's future-tasks auxiliary reward, AUP), and a 2025 agentic version computes it by backward induction (Heitzig & Potham). Receding-horizon 'reason for future, act for now' control with regret bounds exists for LLMs (RAFA, LLMPC). DMDU/RDM tooling derives policies from ensembles of futures. Most damaging, 2026 LLM-agent work explicitly turns feared and delayed futures into present constraints: SafePred, JANUS, SIMMER, DreamGuard, SeerGuard, ARTIS. SafeCommit chooses option-preserving probes across plausible worlds, LCPI formalises homogenize-to-preserve-options under irreversibility, and DeepRewind gates commitments on estimated reversibility and rolls them back when later evidence invalidates them. FinalityBench already provides an executable benchmark with a hidden canonical event log, delayed events, irreversible effects and twin pairs indistinguishable at decision time, and it finds that LLMs discover finality gating unprompted. The remaining gap is narrow and mostly about persistence and evaluation. Derived obligations or signposts would need to be kept as timestamped, provenance-tracked state, re-evaluated as events arrive, and used to reopen and remediate already-executed external decisions. Averted forecasts would be retained and labelled, and everything would be scored without hindsight. That is a testable empirical claim against a strong checkpoint+RAG baseline with a 're-check commitments' prompt, not a new capability. The project should drop 'backward requirements' and 'option preservation' as novelty claims, cite this prior art, and consider reusing FinalityBench's twin-pair and effect-level grading design.

######## LANE performative-prevented (15 works, 55 queries)
QUESTIONS: Evidence caveat: WebSearch was unavailable (session budget 200/200 exhausted). I searched instead with regex over a local index of 117k arXiv cs.AI/cs.CL listings (Dec 2024 to Oct 2026), with GitHub code search, and with raw.githubusercontent fetches. Notes and verbatim snippets: /tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/lit/notes/sweep-performative-prevented.md (raw copies in .../scratchpad/lit/pp/raw/).

Q1. Does existing literature already handle 'a forecast leads to an intervention, the forecasted outcome does not occur, and it is not scored as a failed prediction' cleanly?
Yes, conceptually, in at least four mature forms.
(a) Potential outcomes: the forecast is defined as risk under a named hypothetical strategy, P(Y^a|X). An intervened unit's Y^{no-action} is missing, not falsified. Sources: Dickerman & Hernán 2020; Keogh & van Geloven 2024; Boyer, Dahabreh & Steingrimsson 2025 (with code).
(b) Conditional-question annulment. Metaculus Conditional Pairs: when the parent resolves one way, the other conditional 'is Annulled ... It is not scored'. Metaculus/forecasting-tools ships a ConditionalQuestion model and an ANNULLED status that LLM forecasting bots use. Decision markets void the conditional market for the action not taken.
(c) Random withholding. Armstrong's counterfactual oracle scores only on erasure episodes. Clinical untreated holdouts follow the same idea: Liley et al. 2021; Lenert et al. 2019 and Sperrin et al. 2019 on models as 'victims of their own success'; OptHoldoutSize.
(d) Causal-domain-shift correction for alarms. Boeken et al. 2024: 'naive retraining ... underestimates the risk, due to effective workings of the previous model'. They identify the risk under the no-DSS policy.
A 2026 GitHub preprint (Reflexive Model-World Systems) states the principle almost word for word: 'A successful prediction can therefore become observationally false because it was causally effective', and 'a dashboard that reports only mismatch ... would punish causal success'. It adds a baseline / on-policy / steering-utility evaluation matrix.
The substantive catch, which works against the project: all of these make the prevented branch unscorable, or scorable only under exchangeability and positivity. Chen et al.'s full-support results show that decision markets must randomize to elicit every branch properly, and Oesterheld & Conitzer's decision scoring rules elicit only the chosen action. An agent that always intervenes when it fears an outcome cannot verify its 'prevented' forecasts from its own data. Labelling them 'prevented' is therefore an unverifiable claim unless the agent has a trusted simulator, randomized withholding, or holdouts.
Further undermining points:
- Self-scoring reflexive forecasts creates manipulation incentives (Oesterheld et al. UAI 2023: no proper scoring rule makes reports fixed points for more than two outcomes).
- Agreement between forecast and outcome after acting is a poor quality signal: van Amsterdam et al. 2025 ('calibration before AND after deployment renders it useless'); arXiv 2503.11713 ('accurate predictions can be entirely useless').

Q2. What is the standard formal treatment?
Potential outcomes or do-calculus. A forecast is P(Y^a | H_t) for an explicit action or strategy a:
- a 'passive' forecast takes a = the status-quo policy;
- a 'policy-conditioned' forecast takes a = the agent's planned policy, P(Y(pi));
- a 'reflexive/performative' forecast models the outcome distribution as a function of the published prediction itself, D(theta) (Perdomo et al. 2020). It is assessed by performative stability, fixed points (Oesterheld et al.) or performative multicalibration (arXiv 2503.11713).
Scoring uses a proper score on the realized branch only. The unrealized branch is annulled (Metaculus, decision markets) or estimated with IPW or artificial censoring under exchangeability and positivity (Keogh & van Geloven; Boyer et al.). Randomization is needed for strict properness across branches (Chen, Kash et al.).
The value of acting on a forecast is evaluated separately from its accuracy: net benefit, steering utility, or 'intervention advantage' (van Amsterdam; Reflexive Model-World Systems; Calibration Is Not Control 2606.21399). Public-health practice (COVID-19 Scenario Modeling Hub) scores scenario-conditional projections only where the scenario assumptions held.

Q3. Is anything left for agents specifically?
Less than the project assumes. The 2026 agent work already moves from passive risk forecasts to action-conditioned forecasts, evaluated with same-prefix counterfactual branching and replay:
- Calibration Is Not Control (2606.21399): 'prefix branching ... executes candidate actions from identical trajectory states'; recalibration 'leaves control regret unchanged';
- The Intervention Paradox (2602.03338): AUROC 0.94 critic, 26 pp collapse, disruption-recovery tradeoff;
- COTA (2608.21027) and Causal Agent Replay (2606.08275).
The bookkeeping fits Metaculus conditional pairs directly (parent = 'agent intervenes', child = 'feared outcome'), so a strong checkpoint+RAG baseline can store prevented forecasts as annotated memory records at negligible cost.
What I did not find: a long-lived LLM agent that persists averted forecasts as first-class, queryable memory objects. Such an object would carry the forecaster or policy version, the evidence cutoff, the triggering intervention and a later status (annulled / counterfactually checked / unverifiable). The agent would then use these objects for calibration or for reopening earlier decisions.
That gap is mostly engineering and integration. The open research questions are narrower:
(i) whether such records measurably help on decision-reopening tasks against a baseline that can also log them;
(ii) how an agent that cannot randomize, because of safety and positivity, should handle 'prevented' claims it cannot verify;
(iii) manipulation incentives when an agent scores its own reflexive forecasts.
VERDICT: This lane does not support novelty for the project's 'prevented futures preserved, not scored as wrong' component, or for its passive / policy-conditioned / reflexive forecast taxonomy. Both are established. The formal core is potential-outcome prediction under hypothetical interventions (Dickerman & Hernán 2020; Keogh & van Geloven 2024; Boyer et al. 2025). The scoring core is annulling unrealized conditional branches: Metaculus Conditional Pairs, already implemented for LLM forecasting bots in Metaculus/forecasting-tools, and decision markets. The reflexive tier is covered by performative prediction (Perdomo et al. 2020; Oesterheld et al. 2023), the counterfactual oracle (Armstrong 2017), and decision-support work showing that effective alarms corrupt naive evaluation and retraining (Boeken et al. 2024; Liley et al. 2021; van Amsterdam et al. 2025). A 2026 GitHub preprint (Reflexive Model-World Systems) states the project's principle almost verbatim, with a scoring matrix. In agents, 2026 papers already argue that risk forecasts are the wrong object, and they evaluate action-conditioned forecasts through same-prefix counterfactual branching (Calibration Is Not Control 2606.21399; Intervention Paradox 2602.03338). The literature also turns against the project in two ways. A deterministic self-intervening agent violates positivity, so its 'prevented' labels cannot be verified without randomization or a trusted simulator. And predicted-vs-realized comparison after acting is a weak, manipulable learning signal. What is left is narrow and largely engineering: no found work persists averted forecasts as typed, queryable memory objects across a long-lived LLM agent's lifetime, with policy version and cutoff, and reuses them. The project should frame this as an empirical question (does such bookkeeping beat a checkpoint+RAG baseline that can log the same records?), not as a new concept. Its benchmark should treat 'prevented' as annulled rather than scored, unless the scenario supplies verifiable counterfactual ground truth.

######## LANE benchmarks (15 works, 38 queries)
QUESTIONS: Q1: Does any existing benchmark test "a later event changes the significance of an earlier decision; the agent must notice unprompted, reopen it with evidence, distinguish known-then vs now, and remediate"?

No. I found no benchmark that tests all five parts together. But every part has a close benchmark, almost all from 2026.

(a) A later event invalidates or recontextualises an earlier item:
- STALE (2605.06527): "a later observation invalidates an earlier memory without explicit negation".
- ClawArena (2604.04202): "new information can invalidate earlier conclusions"; 365 staged updates with hidden ground truth.
- StateMemBench (2608.19652): "facts, constraints, and decisions are revised"; grades current versus superseded answers.
- MEMTRACK (2510.01353): a conflicting Slack/Linear/Git timeline.
- Impact Is Not Invalidation (2609.25130): execution-verified claim flips between commits.
- When Stale Constraints Go Unchecked (2608.25553): 74.7-77.3% of decisions stayed consistent with a superseded constraint.
- PlanFence (2609.03340): the freshness-only executor "acts on the obsolete plan in every task".

(b) Unprompted noticing, scored against over-intervention:
- TWIST (2609.28575): "unprompted tension detection" with "surface-matched hard negatives" that "price false intervention".
- STALE's Implicit Policy Adaptation dimension.
- VibeLifeBench (2608.10875): "changes are silent, so only an agent that re-inspects the world discovers them".
- KWBench (2604.15760): models "articulate the relevant ... concept correctly when asked, then fail to apply it unprompted".

(c) Reopening an earlier decision: only implicit or failure-triggered.
- MerchantBench (2607.28956) requires agents to "revisit earlier decisions", but scores only final net assets.
- StoryBench (2506.13356) revises earlier choices only after a failure.
- Dependency-Guided Rollback Repair (2608.10502) starts from "diagnosed faulty memories", so the fault is handed to the agent.
- No benchmark scores explicit per-decision reopen recall and precision.

(d) Known-then vs now:
- The clinical Hindsight Bias benchmark (2609.13454) compares a cutoff-truncated timeline with the full timeline and scores a hindsight-trap rate.
- FinalityBench (2609.04706) uses twin pairs whose views are identical at the decision instant.
- ChronoScope (2604.23051) shows drift toward present-day assumptions.
- None asks an agent to separate true-then / known-then / known-now-about-then for its own past decision.

(e) Remediation scored by execution:
- EvoCode-Bench (cumulative tests over still-active prior requirements), SWE-CI, DreamBench-SWE (hidden executable oracles), VibeLifeBench end state, tau2 DB end state, ClawArena shell checks.

The residual gap is the conjunction of three things. The earlier item is an agent-authored or team decision (ADR or ticket) whose premise stays historically true while its significance changes. Reopening is unprompted and scored per decision for recall and precision, with negative controls. Remediation is executable, in one software world.

Q2: Which benchmark is closest, and what would need adapting?

Closest overall: ClawArena. It already has hidden ground truth, multi-channel sessions, workspace files, staged updates that invalidate conclusions, and shell-based executable checks. To adapt it:
1. Retarget updates at decision artifacts instead of factual beliefs.
2. Replace probing questions with the project's no-hint trigger protocol, logging autonomous reopen actions.
3. Add negative-control updates.
4. Add three-way then/known-then/now probes.
5. Score remediation with repo tests.

Closest on the metrics: TWIST. "Unprompted tension detection plus hard negatives" equals governance recall plus false intervention rate. It would need to move from conversational drafts to decision records, and add remediation.

Closest on the software substrate:
- MEMTRACK: needs actions and decisions in place of QA.
- Impact Is Not Invalidation: ask "does decision D's premise still hold at t+1?" in place of "does claim C hold?". This maps directly onto the project's event classes A, E and G.

Closest on known-then: the clinical Hindsight Bias paired-cutoff design and FinalityBench's twin pairs. Both can be ported directly to historical-state fidelity.

Reusable components: STALE's IPA as the nearest single "notice and act" metric, and EvoCode-Bench's cumulative tests as the remediation scorer.

Evidence against the comparative hypothesis, from these benchmarks:
- STALE (a sibling's WebSearch extract): the updated evidence is retrieved in 67.8% of failed IPA cases.
- KWBench: the gap is acting unprompted, not knowledge.
- StateMemBench: a matched control attributes +15 to +32 points to explicit state structure.
- DreamBench-SWE: verbatim event memory (82/180) is about equal to structured memory (83/180).
- MEMTRACK: Mem0 and Zep do not help.
- TWIST: flat RAG already detects 0.76-0.97 of contradictions; it is weak on precision.

So the strong baseline should include explicit current state and per-claim re-checking. The project must show gains in precision at matched recall.

Evidence caveat: WebSearch was exhausted. All quotes come from:
- a local corpus of verbatim daily arXiv abstracts (cs.AI and cs.CL only);
- cloned repository READMEs and code;
- third-party digests, used for MEMTRACK only;
- the IAAR list summaries.

Notes are at /tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/lit/notes/sweep-benchmarks.md.
VERDICT: The benchmark lane is crowded in 2026, but I found no benchmark that tests the project's exact construct. Benchmarks already exist for each part:
- later evidence invalidating earlier memory: STALE, ClawArena, StateMemBench, MEMTRACK, Impact Is Not Invalidation;
- unprompted intervention with over-intervention controls: TWIST, VibeLifeBench;
- cutoff and hindsight-free scoring: the clinical Hindsight Bias benchmark, FinalityBench twin pairs;
- executable remediation under changing requirements: EvoCode-Bench, SWE-CI, DreamBench-SWE.

None combines all of the following in one software world: agent-authored decisions whose premise stays historically true while their significance changes; unprompted reopening scored for per-decision recall and precision with negative controls; a three-way then/known-then/now fidelity probe; and executable remediation.

The project's benchmark contribution is therefore integration. It is not a new kind of test. It should reuse and cite TWIST (hard negatives), ClawArena (hidden truth with staged updates), StateMemBench (event programs replayed into ground truth), FinalityBench (twin pairs) and EvoCode-Bench (cumulative tests).

The same benchmarks weaken the architecture thesis. Across STALE, KWBench, StateMemBench, DreamBench-SWE and MEMTRACK, failures come from not acting on evidence the agent already has, not from failing to reach the past. The fixes that work are explicit current-state structure and targeted re-checking, not temporal navigation. The surviving hypothesis is narrow: does as-of, diff and fork access raise unprompted reopen recall at matched precision over a baseline that already has timestamped RAG, explicit current state and per-claim re-checking? The benchmark must be built to make that comparison.

######## LANE identity-drift (15 works, 22 queries)
QUESTIONS: Q: Is tracking which objective, policy or model governed a past decision, and contrasting it with the current one, already handled by existing agent frameworks or audit/observability tooling?

A: The recording and contrast part is largely handled; the agent acting on it is not.

(1) Recording is standardised and productised.
- OpenTelemetry GenAI semantic conventions (open-telemetry/semantic-conventions-genai, registry.yaml, stability: development) define per-span gen_ai.agent.version ('The version of the GenAI agent'), gen_ai.prompt.name/version (which 'SHOULD match the version identifier used by' the prompt-management system), gen_ai.system_instructions, and gen_ai.request/response.model.
- MLflow (>= 3.4) creates a LoggedModel per Git commit and dirty diff, and 'Links all traces to this LoggedModel version'. Registry prompts loaded inside traced code are auto-linked to the trace. Prompt versions are 'immutable' with diff highlighting.
- Langfuse links prompt versions to traces, aggregates metrics per prompt version, records release (git hash) and per-observation version, and gives agents MCP/CLI access to 'Retrieve a prompt and compare its latest versions' and inspect observations.
- LangSmith Agent Server assistants version their config (prompts, LLM selection, tools): 'All versions remain available for reference and rollback'. The Context Hub keeps immutable agent and skill commits with parent hashes and diffs ('See exactly what changed between two versions of an agent').
- Phoenix span replay re-runs a recorded LLM span under a changed prompt or model.

(2) Research goes further on authority and lineage.
- AER (2603.21692): versioned plans with revision rationale, delegation authority chains, mock-replay counterfactual regression.
- Mandato (2608.14074): each tool call is evaluated against the applicable signed mandate chain and logged hash-chained.
- Autogenesis (2604.15034), ANNEAL (2605.16309) and DGM (2505.22954): version lineage with rollback or archives of the agent's own self-modifications.
- Counterfactual receipts (2608.20938): explain verdict transitions by replaced grounds, norms or authority.
- Who-Drifted (2606.15474): attributes metric drift to judge version bumps versus system change.
- IDs for AI Systems (2406.12137, pre-2025): instance IDs with ancestor/descendant links across reloads and branches.

(3) What remains open, with evidence.
- 2605.12078 finds vendor SDK trace regimes reconstruct only 42.9%-85.7% of strict governance properties ('on whose authority, against which policy'). The reasoning trace is missing in every regime.
- 2609.08258 shows that agent-memory systems which keep revoked policies (soft revocation) do not enforce the revocation; agents retrieve and act on the superseded policy. A simple guard is the proposed fix.
- No surveyed tool makes the agent itself, at decision time, re-check decisions made under an older policy and reopen them. The tools are built for developers, though Langfuse's MCP access makes agent-side querying feasible.
- The behavioural failure is already measured: Arike et al. 2025 (2505.02709) goal-switching condition with GD_inaction (failure to divest positions taken under the earlier goal), and AgentChangeBench (2510.18170) goal-shift recovery time.

Bottom line: 'which policy governed past action X, and how does it differ from now' is a solved data and attribution problem in tooling. The only unclaimed piece is whether agents, given cutoff-respecting access to that context, actually detect and remediate decisions whose standing changed, compared against strong baselines: versioned retrieval, a revocation guard, and trace access via MCP.
VERDICT: Adversarial verdict for this lane: as infrastructure, the "track identity, objective and policy change over time" component of temporal agency is not novel. Per-span attribution of agent version, prompt version, system instructions and model is standardised in the OTel GenAI conventions and shipped in MLflow, Langfuse, LangSmith and Phoenix. Version lineage with rollback, and archives of the agent's own past selves, are routine in self-evolving-agent work (Autogenesis, ANNEAL, DGM, EvoUndo). Trellis advertises "what an agent knew at any past step" as a time-travel query. Identity, goal and persona drift are measured phenomena with benchmarks (Arike 2025 and its 2026 follow-ups, ContextEcho with fork-based probing, AgentChangeBench). Arike's goal-switching GD_inaction metric already scores failure to remediate earlier decisions after the objective changes. Two works most constrain the project's benchmark. Revoked-but-Still-Authoritative (2609.08258) directly tests whether agents act on a superseded policy and finds a simple retrieval guard fixes much of it. FiscalQA Pro (2608.09393) shows as-of rule lookup reaches 98.3% with plain versioned retrieval. A narrow behavioural hypothesis survives, and it must beat these specific strong baselines rather than a memoryless agent: does structured, cutoff-respecting access to "the policy, belief and objective context in force at t", together with an explicit contrast with the current one, improve detection and remediation of earlier decisions whose significance changed? 2605.12078's finding that reasoning traces are universally missing from vendor traces is the one evidence-backed gap the project could legitimately target. Caveat: WebSearch was unavailable in this session, so coverage relies on an offline arXiv-abstract corpus (Dec 2024 to Sep 2026) and cloned docs; non-arXiv venues and blog posts are under-sampled. Notes with verbatim snippets: /tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/lit/notes/sweep-identity-drift.md

######## LANE epistemic-cutoff (15 works, 42 queries)
QUESTIONS: Q1: Is 'ask the past self with a strict epistemic cutoff' already a recognized problem with known methods and failure modes? Yes, clearly. It has several established names: look-ahead bias, parametric hindsight, temporal leakage, point-in-time evaluation, ex-ante reasoning. A curated bibliography (microprediction/pitllm, verified against the arXiv API) lists more than 40 papers.

Known method families:
(a) Point-in-time weights: Time Machine GPT 2404.18543, ChronoGPT 2502.21206, DatedGPT 2603.11838, Scaling PiT LMs 2607.11889, TiMoE 2508.08827 (per-query expert masking), PALM 2609.30316 (per-period adapters).
(b) Inference-time suppression: FinCAD 2605.24564, Merchant & Levy logit steering 2512.06607, TCFT critic 2605.14636, TEMPO RL 2605.18843, recall-based prompting 2606.05804.
(c) Input and provenance discipline:
- TimeSPEC claim-level provenance 2602.17234;
- OracleProto temporal masking 2605.03762;
- OpenPM 'every record visible to the agent must be available at the decision time' 2608.09988;
- the as-of information-set pinning agent pattern;
- an as_of<=T librarian/writer 2608.12984;
- a formal non-interference type system that covers agentic retrieval 2607.04958.
(d) Re-instantiating a blinded replica of the same model (Self-Blinding 2601.14553). This is the closest existing mechanism to 'ask my past self who did not know X'.
(e) At the agent-state level, Trellis 2606.29823 states 'reconstructing what an agent knew at any past step is a time-travel query'. 2609.12766 formalizes the historical state as (D_t, theta_t, M_<i).

Documented failure modes:
- Prompted or simulated cutoffs leak, especially through causally related knowledge (2510.02340; 2601.13717 reports a 52% SI-TI gap, with CoT and reasoning models no better).
- Date-filtered search leaks: 71% of questions have strong post-cutoff pages (2602.00758).
- Effective cutoffs precede declared ones by up to 8 months, and audits change with serving precision (2607.18867).
- Pre/post-cutoff comparisons provably cannot identify leakage (2608.02985).
- Freezing the corpus but not memory still leaks (2609.12766).
- Retained KV cache defeats transcript rollback, including under LangGraph time travel (2608.15939).
- Model aliases silently rotate weights (pinning pattern).
- Full-timeline exposure shifts judgments toward hindsight traps (2609.13454).
- A judge's hindsight confounds apparent learning across eras (Frontier Autolab 2609.36739).

Q2: Does a frozen LLM make a true past self impossible? For real-world outcomes and a general frontier model, effectively yes. The weights cannot un-know, and the evidence (2601.13717, 2510.02340, 2607.18867, and Lopez-Lira et al. 2504.14765 via pitllm: 'instructions to respect the date fail, and masking fails because the model reconstructs entities and dates from minimal context') shows that prompting cannot rewind them. A true past self requires three things:
(i) weights whose cutoff is at or before t (PiT models), or a world the model cannot have seen: synthetic or post-cutoff worlds, as in MPW 2603.04751, ParallelEvents 2609.00184 and FORESIGHT-9 2608.29372;
(ii) the input set, memory and serving state re-instantiated as of t (2609.12766, 2608.15939, pinning pattern);
(iii) if the agent's model or policy changed between t and now, the then-model pinned and still servable. Model behavior drifts across versions of the 'same' service (Chen, Zaharia and Zou 2307.09009), and HindsightBench shows audits depend on serving configuration.

For this project, the benchmark is a synthetic software world, so parametric knowledge of the specific outcome is mostly moot. The residual hindsight channels are context, memory, KV and serving state, plus model or policy changes. Those are exactly the channels that versioned agent state plus blinded-replica re-instantiation address, and prior art has already identified each of them.
VERDICT: The 'strict epistemic cutoff / ask the past self' part of the temporal-agency thesis is not novel as a problem, and mostly not novel as a method. Look-ahead bias and parametric hindsight form a mature 2023-2026 literature with:
- point-in-time model families;
- detection audits (HindsightBench, Shapley-DCLR, an identification impossibility result);
- negative results on prompted cutoffs;
- formalizations (temporal non-interference with availability vs reference time);
- practitioner patterns (as-of information-set pinning, which includes pinning the model snapshot).
The agent-specific version is also already stated:
- 2609.12766 defines historical state as (corpus, parameters, memory) and shows that un-versioned memory leaks hindsight;
- Trellis names 'what the agent knew at any past step' as a time-travel query;
- Self-Blinding shows that the working way to get a counterfactual self is to re-invoke a blinded replica rather than instruct the model;
- 2608.15939 shows that checkpoint or transcript time travel can still leak through KV state.
The project therefore cannot claim the cutoff discipline, the past-self query, or knowledge of its failure modes as contributions. It should cite these works and adopt their controls: a clean-control arm, a paired cutoff vs full-information design with hindsight-trap metrics, a Temporal Violation Rate audit over memory, and model or serving pins.
What remains is narrower and empirical. In a synthetic world, where parametric leakage is moot by construction, does a long-lived agent that keeps versioned, as-of-queryable state (beliefs, policy and memory as of t) notice that a later event changes the significance of an earlier decision, and reopen and remediate it better than a strong as-of-filtered checkpoint+RAG baseline? That has to be shown with leakage audits, not assumed. No work found in this lane combines cutoff-clean past-self reconstruction with decision reopening or remediation in a lifelong agent. But each ingredient exists, and the remaining hypothesis is a systems-integration and benchmark claim, not a conceptual one.



# All works found (deduplicated)

- [high] The Log is the Agent: Event-Sourced Reactive Graphs for Auditable, Forkable Agentic Systems (ActiveGraph) | arXiv 2605.21997; code github.com/yoheinakajima/activegraph (Apache-2.0, pip install activegraph) | https://arxiv.org/abs/2605.21997 | lanes: exec-state | citation check: arXiv id+title verified in corpus
  WHAT: Agent runtime whose source of truth is an append-only event log. The working graph of typed objects and relations is a deterministic projection of that log. Runtime.fork(at_event) copies the log up to and including at_event into a new run_id and replays it into a fresh graph. The fork can then be reconfigured (different behaviours, prompts or policy) and structurally diffed against the parent. Cache replay means the shared prefix makes no new LLM calls. Lineage is stored as (parent_run_id, forked_at_event_id), and goal-to-model-call lineage is recoverable. The docs call this 'Hypothesis testing on an agentic system, without losing the parent run.'
  WHY: This is the closest existing implementation of 'never overwrite time, fork it' as one abstraction over historical and counterfactual state. It also supplies as-of state through a strict-prefix fork, plus diff(t1-branch, t2-branch) and full provenance. What it lacks is the prospective side: no imagined futures, no probabilities over futures, no backward requirements, no prevented-forecast bookkeeping. Without that side, the 'unified temporal abstraction' claim reduces to ActiveGraph plus a planner.
  CAPS: immutable_historical_observations, historical_world_state, historical_epistemic_state, execution_checkpoints, replay, fork_from_historical_state, counterfactual_action_branches, branch_provenance, cross_time_state_querying
- [high] Shepherd: Enabling Programmable Meta-Agents via Reversible Agentic Execution Traces (v1 title: A Runtime Substrate Empowering Meta-Agents with a Formalized Execution Trace) | arXiv 2605.10913 (Yu, Chong, Nandi, Soylu, Sun, Manning, Shi) | https://arxiv.org/abs/2605.10913 | lanes: exec-state | citation check: arXiv id+title verified in corpus
  WHAT: Records every agent-environment interaction as a typed event in a Git-like execution trace, where any past state can be cheaply forked and replayed. It forks the agent process and its filesystem (5x faster than Docker, with over 95% prompt-cache reuse on replay), and its core operations are mechanized in Lean. Use cases are supervisor intervention mid-trajectory, counterfactual meta-optimization (a meta-agent branches to explore alternative paths) and tree-RL from forked turns.
  WHY: It provides a formalized substrate for forking from any historical state and running counterfactual branches. Because it restores the whole agent process, any in-process belief state is restored too. That removes 'fork past self' as a contribution. The project would have to show value in what the agent does with the forks, such as cutoff-correct questioning or prospective reasoning, not in the forking itself.
  CAPS: immutable_historical_observations, historical_world_state, execution_checkpoints, replay, fork_from_historical_state, counterfactual_action_branches, branch_provenance
- [high] ChronoMem: Version Control and Semantic Rollback for Large Language Model Agent Memory | arXiv 2607.27773 (Su, Xu, Zuo, Bertino); integrated into Google ADK | https://arxiv.org/abs/2607.27773 | lanes: exec-state | citation check: arXiv id+title verified in corpus
  WHAT: Commits whole-memory snapshots at each memory write and keeps structured version histories. Natural-language undo intents are mapped to concrete historical versions using hybrid retrieval and reranking. It introduces a 'post-exposure evaluation protocol that tests whether an agent can behave counterfactually after rollback -- answering queries and summarizing history as if future updates never occurred.'
  WHY: It is direct prior art for reconstructing the agent's past knowledge with a no-hindsight constraint, at the memory layer, and it comes with a benchmark protocol that measures leakage of later information after rollback. The project's 'strict epistemic cutoff' claim and any hindsight-leakage metric must be positioned against it.
  CAPS: immutable_historical_observations, historical_epistemic_state, execution_checkpoints, replay, cross_time_state_querying
- [high] DeepRewind: Predicting and Repairing Premature Commitments in Deep Research Agents | arXiv 2609.36344 (Abaskohi, Dabiriaghdam, Wang, West, Carenini) | https://arxiv.org/abs/2609.36344 | lanes: exec-state,backward-optionality | citation check: arXiv id+title verified in corpus
  WHAT: Represents the agent's evolving epistemic state as a typed graph of sources, evidence, claims, hypotheses, assumptions, commitments, plans and drafts. Before accepting an intermediate conclusion, a prompt-based world model predicts the conclusion's impact and estimates its reversibility (hypothesis narrowing, information loss, recovery cost, contradiction-trigger coverage). A controller blocks risky commitments, and a consistency monitor performs dependency-aware rollback when later evidence invalidates a commitment. It reduces premature commitments by 59.1% relative to Open Deep Research.
  WHY: This is the project's benchmark behaviour (a later event changes the significance of an earlier decision, so the agent reopens and remediates it) already implemented and measured, via dependency tracking over an explicit epistemic graph rather than temporal navigation. Its reversibility-before-commitment gate also overlaps 'option-preserving actions'. A dependency-graph baseline in this style is a necessary contestant, separate from checkpoint+RAG.
  CAPS: explicit_current_belief_state, uncertainty_representation, future_state_rollout, backward_requirements, execution_checkpoints, replay, branch_provenance
- [high] MemTX: Transactional Belief Commit for Stateful Agent Memory | arXiv 2607.23929 | https://arxiv.org/abs/2607.23929 | lanes: belief-state | citation check: arXiv id+title verified in corpus
  WHAT: A protocol that keeps recording an observation separate from committing a belief. Each record carries evidence, permissions, provenance and validity. Writes are staged in snapshot-isolated transactions and pass a validate-and-commit pipeline. Irreversible tool calls are gated on in-flight belief state. Per the search extract: 'retracting a belief triggers typed cascading repair of its derived records and tool side effects'. The action-safety and cascade-repair-completeness invariants were model-checked over 5.5M states. It leads 8 baselines across 5 backbones and is the only method with 'zero downstream harm on every backbone'.
  WHY: Directly mechanizes 'new evidence invalidates a belief, then repair the decisions and side effects that depended on it', including remediation of executed tool effects, and evaluates it against baselines. It needs no temporal-navigation abstraction: dependency links plus transactional commit are enough. It is a natural strong non-temporal baseline for the project's reopen/remediate benchmark.
  CAPS: explicit_current_belief_state, uncertainty_representation, immutable_historical_observations
- [high] Fresh Memory, Stale Plans: Derivation Currency / Dependency-Scoped Validation for Distributed LLM-Agent Memory (PlanFence) | arXiv 2609.03340 | https://arxiv.org/abs/2609.03340 | lanes: belief-state | citation check: arXiv id+title verified in corpus
  WHAT: Defines the failure 'fresh memory, stale plan': an agent holds the latest requirement but acts on a plan derived from an older one. Freshness checks miss this because they compare against current state (observation currency), not against the plan's inputs (derivation currency). PlanFence stores exact links from each plan to its recorded inputs. Before a protected action it follows those links to an action-specific dependency frontier, refreshes changed heads, and allows one replan before blocking. In 30 live five-agent workflows with a revision after planning, a freshness-only executor used the stale plan every time; PlanFence completed all 30.
  WHY: This is close to the project's core benchmark property: a later revision invalidates the assumption behind an earlier decision (a plan), and the agent must detect that and replan. It works by recording what the decision was derived from at decision time, a narrow form of 'what did the agent know when', with no general temporal-state abstraction. It undermines any claim that time-addressable state is needed for this behavior.
  CAPS: explicit_current_belief_state, cross_time_state_querying, branch_provenance
- [high] Corollary: an agent runtime where state is beliefs (truth maintenance for LLM agents) | GitHub gabe-santana/corollary (PyPI corollary 0.1.0a2) | https://github.com/gabe-santana/corollary | lanes: belief-state | citation check: non-arXiv
  WHAT: Replaces the message log with a belief base built on a justification-based TMS (Doyle 1979). Each belief has a claim, confidence, source, valid_until and follows_from. Correcting a premise retracts dependent conclusions and re-derives only those ('retraction cascades'). Conflicts are first-class objects. Evidence expires through TTL and half-life and triggers re-verification. Revisions are kept ('Retracted revisions remain queryable with their reason'), with kb.revisions(), kb.history and a change log. Belief snapshots persist as JSON. An ATMS mode is on the roadmap. README: 'There is no standard evaluation for how well an agent recovers from a corrected input. We want to build one.'
  WHY: Shipping code for an explicit belief/assumption state with dependency-directed invalidation and a revision history. It covers the 'assumption invalidated -> dependent conclusions reopened' mechanism with no temporal-navigation framing. It is pre-alpha with no published evaluation, and its README says a benchmark is missing. That leaves room for the project's benchmark, though not for the mechanism.
  CAPS: explicit_current_belief_state, uncertainty_representation, immutable_historical_observations, cross_time_state_querying, execution_checkpoints
- [high] STALE: Can LLM Agents Know When Their Memories Are No Longer Valid? | arXiv 2605.06527 | https://arxiv.org/abs/2605.06527 | lanes: belief-state,benchmarks | citation check: arXiv id+title verified in corpus
  WHAT: Benchmark with 400 expert-validated conflict scenarios and 1,200 queries, with contexts up to 150K tokens. It probes State Resolution (detecting that a prior belief is outdated), Premise Resistance (rejecting queries that presuppose a stale state) and Implicit Policy Adaptation (applying the updated state in downstream behavior without being prompted). It names 'Implicit Conflict': a later observation invalidates an earlier memory without explicitly negating it. The best model reaches 55.2% overall. A write-side prototype scores 91% on SR but 32% on IPA.
  WHY: Benchmarks detection of a later event that implicitly changes what an earlier memory means, and the gap between knowing and acting on it. That overlaps the project's 'agent notices a later event changes the significance of an earlier decision'. Remaining difference: STALE scores later answers and plans, not reopening and remediating an already executed decision.
  CAPS: explicit_current_belief_state
- [high] Memvara: bitemporal memory for AI agents | GitHub memvara/memvara (PyPI memvara 0.19.0) | https://github.com/memvara/memvara | lanes: belief-state | citation check: non-arXiv
  WHAT: Bitemporal claim store with valid time and knowledge time. Reads take valid_at=T ('what we believe TODAY about how the world was at T'), known_at=T ('what we believed at T') or as_of=T ('what we believed at T, about T'). A later correction is invisible to an as_of query that predates it. Contradictions on single-valued predicates are resolved deterministically. why() returns the cited episodes and the superseded claim.
  WHY: Reconstructing what the agent believed at t with no hindsight is a library call for fact memory. The project cannot claim historical epistemic state or as-of querying as novel at the memory layer. Its residue has to be epistemic state beyond facts (plans, assumptions, policy) and showing that such queries change decisions.
  CAPS: immutable_historical_observations, historical_world_state, historical_epistemic_state, cross_time_state_querying, explicit_current_belief_state
- [high] ClawArena: Benchmarking AI Agents in Evolving Information Environments | arXiv 2604.04202 | https://arxiv.org/abs/2604.04202 | lanes: belief-state,benchmarks | citation check: arXiv id+title verified in corpus
  WHAT: Benchmark for persistent assistants that 'must maintain correct beliefs as their information environment evolves', where 'new information can invalidate earlier conclusions'. It covers multi-source conflict reasoning, dynamic belief revision and implicit personalization, with 64 scenarios, 8 domains, 1,879 rounds and 365 dynamic updates. Revision difficulty depends on how the update is designed, not on whether an update is present.
  WHY: Another existing benchmark for dynamic belief revision after invalidating updates, across agent frameworks and models. The project's benchmark has to show it measures something beyond this, namely reopening past decisions as opposed to answering correctly now.
  CAPS: explicit_current_belief_state, uncertainty_representation
- [high] Memvara: bitemporal memory for AI agents (plus its cross-system Agent Memory Benchmark) | GitHub memvara/memvara v0.19.0 (PyPI memvara) | https://github.com/memvara/memvara | lanes: temporal-memory | citation check: non-arXiv
  WHAT: Stores claims as (subject, predicate, object) slots with two clocks. Every read takes valid_at= ("what we believe TODAY about how the world was at T"), known_at= ("what we believed at T") or as_of= (both clocks). why() returns the source episodes and the superseded claim. It ships a public benchmark across systems. There, a single-clock vector-RAG over the whole write log ("answers a question about a past instant with the most recent write it had received by then") scores 100% on knowledge_time and current state. Memvara wins only on historical_state (100 vs 85.2), driven by delayed-knowledge and correction questions, about 9% of temporal questions.
  WHY: Shipping code already provides 'what the agent knew at t' vs 'what was true at t' as library calls. Its own benchmark undercuts the project's comparative thesis. A strong append-only, timestamped RAG with an ingestion-time filter already answers knowledge-time questions. Two-axis temporal state helps only when valid and transaction time diverge (late or retroactive news). Caveat: the corpus was authored by the maintainers.
  CAPS: immutable_historical_observations, historical_world_state, historical_epistemic_state, explicit_current_belief_state, cross_time_state_querying
- [high] Temporal Validity in Retrieval Memory: Eliminating Stale-Fact Errors for AI Agents over Evolving Knowledge (MemStrata) | arXiv 2606.26511 | https://arxiv.org/pdf/2606.26511v1 | lanes: temporal-memory | citation check: arXiv id+title verified in corpus
  WHAT: According to the list summary, it maintains timeliness with deterministic (subject, relation, object) supersession rules in a bitemporal ledger, with no similarity threshold and no LLM call on the read path. It proves cosine similarity cannot separate contradiction from duplication (AUROC 0.59). It targets evolving software knowledge: code renames, config, dependency and API changes. It ties RAG on static knowledge. On evolving knowledge it scores 0.95-1.00 vs RAG 0.20-0.47, and cuts stale-fact errors from 15-40% to about 0%.
  WHY: It is a published head-to-head of temporal-validity memory vs RAG in the project's own domain, a software world with evolving facts. It already claims the 'temporal beats RAG' result for fact QA. Its RAG baseline appears similarity-only, so it is not the strong as-of-filtered baseline. The project would need to show something beyond this, such as decision reopening rather than fact freshness.
  CAPS: immutable_historical_observations, historical_world_state, explicit_current_belief_state, cross_time_state_querying
- [high] XTDB: general-purpose bitemporal database (docs: 'Time in XTDB', backtesting, point-in-time feature extraction) | GitHub xtdb/xtdb (docs in repo) | https://github.com/xtdb/xtdb | lanes: temporal-memory | citation check: non-arXiv
  WHAT: Immutable-log database with bitemporal indexes. The docs state verbatim: "You might also hear system-time referred to 'transaction time'". Also: "Some use cases (e.g. auditing) will need to see the data 'as we knew it at the time', _without_ subsequent corrections - this is the use case for `FOR SYSTEM_TIME AS OF ...`". FOR VALID_TIME AS OF gives the corrected world timeline. Backtesting can "simulate querying as-of successive moments in time ... without the need for explicit snapshots". Point-in-time extraction is pitched as "Build leakage-free training matrices with one bitemporal SQL query."
  WHY: The project's 'historical epistemic state with strict cutoff, no hindsight' vs 'historical world state' is the system-time vs valid-time distinction. XTDB documents it as a product feature, including the no-lookahead backtesting use case. That is prior art for the core computational abstraction.
  CAPS: immutable_historical_observations, historical_world_state, historical_epistemic_state, cross_time_state_querying
- [high] From Faulty Memories to Corrected Actions: Dependency-Guided Rollback Repair for Memory-Augmented Agents | arXiv 2608.10502 | https://arxiv.org/pdf/2608.10502 | lanes: temporal-memory | citation check: arXiv id+title verified in corpus
  WHAT: Per the list summary, after a memory fault is diagnosed it repairs both answers and persistent state. A dependency graph invalidates successors that lost their support and selectively replays the affected computations. Controlled and trajectory-derived tests show better recovery while normal memories are preserved. Related works: StateGuard (2609.34134), which uses dependency graphs and learns verification and repair from counterfactual trajectories to stop stale analysis artifacts propagating; and Execution-State Unlearning (2609.04875), which restores checkpoints by provenance and rebuilds affected later steps with sanitized replay.
  WHY: 'A later finding invalidates an earlier memory, so reopen and remediate downstream outputs and state' is the project benchmark's target behaviour. It already exists as a method with an evaluation, built from dependency tracking and selective replay rather than a temporal-agency abstraction.
  CAPS: execution_checkpoints, replay, explicit_current_belief_state
- [high] C3: Contextual Counterfactual Credit Assignment for Multi-Agent Reinforcement Learning in LLM Collaboration | arXiv 2603.06859 | https://arxiv.org/abs/2603.06859 | lanes: counterfactual-worldmodel | citation check: arXiv id+title verified in corpus
  WHAT: Treats the shared multi-agent transcript as the full state, so it can 'reset the run to any message, swap it, and play the rest out'. It samples alternatives at a decision point, replays each to the final reward, and computes leave-one-out counterfactual credit ('the counterfactual is executed rather than predicted'). The code logs parent_id and parent_id_true for every branch node.
  WHY: This is the clearest instance found of 'fork from a historical decision point, execute the alternative, compare outcomes' for LLM agents, with branch provenance in code. It shows the fork-and-compare mechanism is not new. It differs from the project in four ways: it is used for training credit assignment, it uses the final reward (full hindsight), it has no epistemic cutoff, and its branches are not a lifelong queryable store.
  CAPS: execution_checkpoints, replay, fork_from_historical_state, counterfactual_action_branches, branch_provenance
- [high] FutureSim: Replaying World Events to Evaluate Adaptive Agents | arXiv 2605.15188 | https://arxiv.org/abs/2605.15188 | lanes: prospective-forecast | citation check: arXiv id+title verified in corpus
  WHAT: A chronological replay of real news (Jan to Mar 2026) in which agents forecast events beyond their knowledge cutoff while questions resolve over simulated time. The environment shows only articles dated on or before the simulated date. It keeps an append-only per-agent PredictionHistory, which can be queried with get_prediction_as_of(agent_id, target_date). Each simulated day the agent gets resolution feedback with its predicted distribution next to the truth and its Brier score. The harness prompt says: "use this to learn from mistakes and improve calibration". Results: the best agent reaches about 25% accuracy, and many score a worse Brier skill score than making no prediction.
  WHY: In the forecasting domain this public harness already has a strict epistemic cutoff, an as-of-queryable and append-only forecast history, and predicted-vs-realized feedback that the agent uses to self-calibrate. Those are three pillars of the 'time as addressable state' thesis, and here they are ordinary benchmark infrastructure.
  CAPS: immutable_historical_observations, historical_world_state, replay, uncertainty_representation, probability_over_futures, predicted_vs_realized, cross_time_state_querying
- [high] Forecast-Dojo: Replayable Environments for Benchmarking and Training LLM Forecasting Agents | arXiv 2609.28876 | https://arxiv.org/abs/2609.28876 | lanes: prospective-forecast | citation check: arXiv id+title verified in corpus
  WHAT: Replays 1,568 resolved Polymarket events at fixed sequences of historical dates, with the same information cutoff for every model (18.8M dated articles). In memory-on mode the agent carries a 'belief notebook' between dates that summarises its current assessment, supporting evidence and open questions. Every step is scored against the realized outcome, and those scores feed back into learning (SFT proof of concept). Key finding: the belief notebook cut research cost by a median of 24%, but Brier improved for only 6 of 12 models.
  WHY: It is a direct prior instance of replaying the agent's information state at past dates with no hindsight, while carrying an explicit belief state forward. It is also direct negative evidence: an explicit belief state carried across time did not reliably improve decisions. That undermines the assumption that structured temporal state gives an advantage over strong memory-free retrieval.
  CAPS: immutable_historical_observations, historical_epistemic_state, replay, explicit_current_belief_state, uncertainty_representation, probability_over_futures, predicted_vs_realized
- [high] EpiEvolve: Self-Evolving Agents for Streaming Pandemic Forecasting under Regime Shifts | arXiv 2606.05513 (under review) | https://arxiv.org/abs/2606.05513 | lanes: prospective-forecast | citation check: arXiv id+title verified in corpus
  WHAT: Wraps a frozen LLM forecaster in a streaming loop where labels arrive after the predictions. It stores forecast outcomes in hierarchical episodic memory, reflects on the delayed labels, retrieves cases relevant to the current regime, and distills recurring errors into strategic rules. It reuses its own past predictions and outcomes under a chronological protocol that prevents future leakage. Reported results: accuracy 0.629 vs 0.561 for the static backbone and 0.325 for the CDC ensemble; recovery lag after regime shifts falls from 5 to 2 weeks.
  WHY: This is the clearest example of an agent comparing its own predictions with realized outcomes to self-calibrate under a no-hindsight protocol, with a measured gain. The project's 'compare predicted vs realized futures' component is therefore not novel as a mechanism.
  CAPS: predicted_vs_realized, historical_epistemic_state
- [high] MerchantBench: Benchmarking LLM Agents for Long-Term Coherence in E-Commerce Operations | arXiv 2607.28956 | https://arxiv.org/abs/2607.28956 | lanes: prospective-forecast,benchmarks | citation check: arXiv id+title verified in corpus
  WHAT: A 365-day order-level e-commerce simulation with 26 tools. Supplier events are observable promptly while order outcomes arrive late, so agents must 'follow individual order lifecycles and revisit earlier decisions'. The best LLM configuration reaches only 27.3% of human final net assets.
  WHY: The overlap is with the benchmark, not the mechanism. The project's core test ('a later event changes the significance of an earlier decision, so the agent must reopen or remediate it') is already built into a public, Apache-licensed, long-horizon benchmark with delayed feedback and a human baseline. A new benchmark has to show it isolates something MerchantBench does not.
  CAPS: explicit_current_belief_state, predicted_vs_realized
- [high] VibeLifeBench: Can Your Life Agent Be Proactive and Persistent in a Living World? | arXiv 2608.10875 | https://arxiv.org/abs/2608.10875 | lanes: prospective-forecast,benchmarks | citation check: arXiv id+title verified in corpus
  WHAT: 200 multi-week life-assistant tasks over 22 mock services. The world advances on its own clock, and many changes are silent, so only an agent that re-inspects the world discovers them. Grading reads only what the agent actually left behind: end state, timeliness, and whether implicit constraints were upheld. All seven frontier models tested score low.
  WHY: The overlap is again with the benchmark. It already tests keeping one plan coherent while the world changes unannounced and constraints are implicit. That is very close to 'notice that later events change the significance of earlier decisions', so it weakens the novelty of the project's evaluation design.
  CAPS: explicit_current_belief_state, historical_policy_objective_state
- [high] SafePred: A Predictive Guardrail for Computer-Using Agents via World Models | arXiv 2602.01725 | https://arxiv.org/abs/2602.01725 | lanes: backward-optionality | citation check: arXiv id+title verified in corpus
  WHAT: A world-model-based predictive guardrail for computer-use agents. It predicts short- and long-term risks of candidate actions ('aligning predicted future risks with current decisions'), prunes actions that lead to high-risk states, and turns predicted risks into 'step-level interventions and task-level re-planning'. Its explicit target is delayed-consequence risk, e.g. 'cleaning logs leads to future audits being untraceable'.
  WHY: It already implements 'derive present actions and replans from feared, delayed futures' for LLM agents, with strong reported numbers (over 97.6% safety). Its delayed-consequence example has the same structure as the project's 'earlier decision gains significance later' scenarios.
  CAPS: future_state_rollout, backward_requirements, uncertainty_representation, multiple_prospective_branches
- [high] SafeCommit: Certifying When Memory-Grounded Agents May Safely Act | arXiv 2608.04289 | https://arxiv.org/abs/2608.04289 | lanes: backward-optionality | citation check: arXiv id+title verified in corpus
  WHAT: Builds 'a calibrated set of plausible latent worlds from memory, observations, tool outputs, provenance, and policy constraints'. It permits a side-effectful action only when a conformal certificate shows it is safe in every retained world. Otherwise it 'selects a low-side-effect probe that targets the worlds blocking certification, or returns a conservative fallback', with a bound on unsafe commits.
  WHY: This is robust decision making (safe across all plausible worlds, otherwise buy information with a low-impact probe) built as an LLM-agent runtime layer. It takes the 'option-preserving action derived from multiple possible futures' part of the thesis.
  CAPS: explicit_current_belief_state, uncertainty_representation, multiple_prospective_branches, probability_over_futures, backward_requirements
- [high] FinalityBench: An Effect-Level Benchmark for Agent Decisions Under Delayed and Conflicting Financial Finality | arXiv 2609.04706 | https://arxiv.org/abs/2609.04706 | lanes: backward-optionality,benchmarks | citation check: arXiv id+title verified in corpus
  WHAT: An executable benchmark in which an agent must ship, re-capture, refund or wait, 'knowing some of those cannot be undone'. It 'keeps a hidden canonical event log' with delayed, duplicated and reordered delivery. Grading is on executed monetary effects, and 45 twin pairs are indistinguishable at the decision instant but need different dispositions. LLMs 'discover the finality-gating strategy without being told it'.
  WHY: Its benchmark machinery is very close to the project's: hidden canonical event log, delayed events, irreversible actions, twin-pair indistinguishability and effect-level scoring. Plain LLM agents learning to gate irreversible actions unprompted weakens the claim that explicit temporal machinery is necessary. It is a design precedent the project must cite or reuse.
  CAPS: immutable_historical_observations, uncertainty_representation, backward_requirements, cross_time_state_querying, historical_epistemic_state
- [high] Metaculus Conditional Pairs (annulment rule) and the ConditionalQuestion data model in forecasting-tools for LLM forecasting bots | Metaculus platform FAQ and Metaculus/forecasting-tools (software, live) | https://github.com/Metaculus/metaculus/blob/main/front_end/src/app/(main)/faq/page.tsx | lanes: performative-prevented | citation check: non-arXiv
  WHAT: Each conditional pair has a Parent and a Child question, with an 'if Yes' and an 'if No' conditional. Verbatim: 'When the Parent resolves Yes, the "if No" Conditional is Annulled ... It is not scored.' forecasting-tools models ConditionalQuestion(parent, child, question_yes, question_no) and CanceledResolution.ANNULLED. Bots in the Metaculus FutureEval bot tournament are prompted to forecast the child 'assuming the PARENT question has resolved to {resolved}'.
  WHY: This is a deployed scoring rule for 'keep the forecast, label it, do not score it' when its condition did not occur. Set the parent to 'agent intervenes' and the child to 'feared outcome'; the 'if no intervention' branch is then exactly the project's prevented future, and it is annulled rather than counted wrong. LLM forecasting bots already use this data model. The project's 'prevented futures preserved' rule is therefore a renaming of conditional-question annulment, not a new scoring idea.
  CAPS: intervention_aware_forecasting, multiple_prospective_branches, probability_over_futures, prevented_futures_preserved, predicted_vs_realized
- [high] Counterfactual prediction is not only for causal inference (Dickerman & Hernán) | Eur J Epidemiol 35(7):615-617, doi 10.1007/s10654-020-00659-8 | https://doi.org/10.1007/s10654-020-00659-8 | lanes: performative-prevented | citation check: non-arXiv
  WHAT: Argues that prediction models used for decisions should predict risk under specified hypothetical interventions (potential outcomes Y^a), not factual risk under whatever care follows. Follow-up: Dickerman et al. 2022, 'Predicting counterfactual risks under hypothetical treatment strategies: an application to HIV'.
  WHY: This is the standard formal treatment the lane asks about. A forecast of Y^{no action} is a claim about a potential outcome, and taking the action leaves it unobserved rather than falsified. The project's 'passive vs policy-conditioned' distinction is this framework.
  CAPS: intervention_aware_forecasting, multiple_prospective_branches, probability_over_futures
- [high] Evaluating and Correcting Performative Effects of Decision Support Systems via Causal Domain Shift (Boeken, Zoeter, Mooij) | CLeaR 2024, PMLR v236:551-569; arXiv 2403.00886 | https://arxiv.org/abs/2403.00886 | lanes: performative-prevented | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: Verbatim: 'In the case that the DSS serves as an alarm for a predicted negative outcome, naive retraining of the prediction model is bound to result in a model that underestimates the risk, due to effective workings of the previous model.' The paper models DSS deployment as a causal domain shift. It gives identification results for E[Y|X] under the baseline no-DSS policy, which supports pre- and post-hoc assessment and correct retraining.
  WHY: This is a formal, peer-reviewed treatment of an alarm that prevents its own outcome. It shows how to keep the risk target under the no-intervention policy instead of treating prevented events as evidence of low risk.
  CAPS: intervention_aware_forecasting, predicted_vs_realized, historical_policy_objective_state
- [high] Calibration Is Not Control: Why LLM-Agent Oversight Needs Intervention | arXiv 2606.21399 | https://arxiv.org/abs/2606.21399 | lanes: performative-prevented | citation check: arXiv id+title verified in corpus
  WHAT: Argues that runtime oversight framed as scalar risk forecasting 'targets the wrong object'. It defines 'intervention advantage', the expected utility gain from intervening rather than continuing. It introduces 'prefix branching, a same-prefix counterfactual protocol that executes candidate actions from identical trajectory states'. Recalibrating the risk score 'improves prediction metrics but leaves control regret unchanged'. An action-conditioned controller cuts regret from 0.506 to 0.110 on ALFWorld.
  WHY: In LLM agents it already separates passive forecasts from action-conditioned forecasts. It evaluates them by forking from identical states with and without the intervention, which is the agent-native form of 'score the intervention, not the averted passive forecast'. It weakens any claim that intervention-aware forecasting for agents is unexplored.
  CAPS: intervention_aware_forecasting, counterfactual_action_branches, fork_from_historical_state, future_state_rollout, multiple_prospective_branches, predicted_vs_realized
- [high] TWIST: A Proposed Benchmark for Intervention Quality in Conversational Memory, with a Human-Validated Draft-Alignment | arXiv 2609.28575 | https://arxiv.org/abs/2609.28575 | lanes: benchmarks | citation check: arXiv id+title verified in corpus
  WHAT: A benchmark suite with four tracks: "unprompted tension detection, vetting outgoing drafts against the record, answering with current beliefs while preserving supersession history, and governing sensitive recall". It extends LoCoMo. Every detect or block metric is paired with "surface-matched hard negatives" that "price false intervention". Results: flat-RAG baselines detect 0.76-0.97 of contradictions but falsely flag 16-43% of safe drafts. A coherence-oriented system reaches 0.98-1.00 specificity but catches only 42% of contradictions.
  WHY: Unprompted detection paired with a hard-negative control is the same construct as the project's temporal governance recall plus false intervention rate. Supersession history is a then-versus-now requirement. Adversarial point: plain RAG already reaches high recall, so the project has to win on precision at matched recall. It does not test agent decisions or remediation.
  CAPS: explicit_current_belief_state, immutable_historical_observations, cross_time_state_querying
- [high] Revoked but Still Authoritative: An Empirical Study of Revocation Enforcement in Agent-Memory Systems | arXiv 2609.08258 | https://arxiv.org/abs/2609.08258 | lanes: identity-drift | citation check: arXiv id+title verified in corpus
  WHAT: Loads five agent-memory systems with a revoked policy and its replacement. Tests whether the revoked record is still retrieved and whether the agent acts on it, across 9 policy scenarios x 9 models x 6 defense conditions. Finds no system enforces revocation by default: the revoked fact outranks its replacement and leads to the unsafe action. Proposes a retrieval-time guard that withholds revoked or conflicting records.
  WHY: Closest existing test of the project's benchmark premise: a later event changes which policy governs, and the question is whether the agent acts from the current one. It also shows the soft-revocation pattern (keep history, mark invalid) fails without enforcement, and that a simple guard largely fixes it. That raises the bar for any claim that 'temporal navigation' is needed.
  CAPS: immutable_historical_observations, historical_policy_objective_state, cross_time_state_querying
- [high] Experience Graphs: The Data Foundation for Self-Improving Agents (Trellis) | arXiv 2606.29823 | https://arxiv.org/abs/2606.29823 | lanes: identity-drift,epistemic-cutoff | citation check: arXiv id+title verified in corpus
  WHAT: Treats an agent's exploration history (artifacts, tool outputs, rewards, sibling comparisons, causal lineage) as governed, queryable database state. States that 'reconstructing what an agent knew at any past step is a time-travel query'. Grounded in Meta's KernelEvolve production system.
  WHY: Presents historical epistemic-state reconstruction, branch lineage and as-of queries as infrastructure byproducts of a database design, not a new cognitive capability. This directly undercuts the 'time as an addressable dimension of state' framing for long-lived agents.
  CAPS: immutable_historical_observations, historical_epistemic_state, execution_checkpoints, fork_from_historical_state, branch_provenance, cross_time_state_querying
- [high] OpenTelemetry GenAI semantic conventions (gen_ai.agent.version, gen_ai.prompt.version, gen_ai.system_instructions) | OpenTelemetry spec repo open-telemetry/semantic-conventions-genai (model/gen-ai/registry.yaml, stability: development) | https://github.com/open-telemetry/semantic-conventions-genai | lanes: identity-drift | citation check: non-arXiv
  WHAT: Standard span attributes recording, per agent/LLM operation: agent id, name and version ('The version of the GenAI agent'), prompt name and version ('SHOULD match the version identifier used by that system' when a prompt management system is used), system instructions, and the requested and response model.
  WHY: Recording which agent version, prompt version, instructions and model governed each past action is being standardised across vendors, so the project cannot claim policy/identity-over-time tracking as novel infrastructure.
  CAPS: historical_policy_objective_state, immutable_historical_observations
- [high] MLflow GenAI: Prompt Registry (immutable versions linked to traces) and Git-based application version tracking | MLflow docs (mlflow/mlflow docs/docs/genai/prompt-registry, version-tracking), MLflow >= 3.4 | https://github.com/mlflow/mlflow/blob/master/docs/docs/genai/version-tracking/track-application-versions-with-mlflow.mdx | lanes: identity-drift | citation check: non-arXiv
  WHAT: Creates a LoggedModel per Git state (branch, commit, dirty diff) and 'Links all traces to this LoggedModel version'. Prompts loaded from the registry inside traced functions are automatically linked to the active trace. Prompt versions are immutable, carry commit messages, can be diffed side by side, and support aliases and rollback.
  WHY: Answers the lane question directly for the developer side: every past trace can be attributed to the exact code and prompt version that produced it, and versions can be compared.
  CAPS: historical_policy_objective_state, immutable_historical_observations, cross_time_state_querying
- [high] Reasoning Provenance for Autonomous AI Agents: Structured Behavioral Analytics Beyond State Checkpoints and Execution Traces (Agent Execution Record) | arXiv 2603.21692 | https://arxiv.org/abs/2603.21692 | lanes: identity-drift | citation check: arXiv id+title verified in corpus
  WHAT: Defines the Agent Execution Record. It records intent, observation and inference as queryable fields per step, plus versioned plans with revision rationale, evidence chains, verdicts with confidence, and delegation authority chains. It enables confidence calibration, cross-agent comparison and counterfactual regression testing via mock replay. Argues reasoning provenance cannot in general be reconstructed from checkpoints or traces.
  WHY: Already makes the project's 'checkpoints are not enough; keep why-records with versioned plans and authority' argument, and ships a reference SDK. It overlaps the provenance and replay part of the thesis.
  CAPS: immutable_historical_observations, historical_policy_objective_state, replay, counterfactual_action_branches, branch_provenance, uncertainty_representation
- [high] A Historical Corpus Is Not a Historical System: Auditing Hindsight Leakage in Stateful Data Discovery | arXiv 2609.12766 | https://arxiv.org/pdf/2609.12766 | lanes: epistemic-cutoff | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: Formalizes point-in-time (PIT) discovery via historical state (D_t, theta_t, M_<i): corpus, model/retriever parameters and interaction memory at t. Introduces a paired replay that changes only memory availability, plus a Temporal Violation Rate audit. Shows that freezing the corpus while leaving memory unconstrained inflates results (Recall@100 +2.62-5.24) and masks real harms. Conclusion: 'Historical evaluation must version and validate memory with the corpus.'
  WHY: Formalizes and audits the project's core move: reconstructing a past system state (world + model + memory) with a strict cutoff. It also shows empirically that hindsight leaks through un-versioned memory. Its paired-replay leakage protocol is what the project's no-hindsight claim would need. It is not a long-lived LLM agent reopening decisions, so the remediation angle remains open.
  CAPS: historical_world_state, historical_epistemic_state, historical_policy_objective_state, replay, cross_time_state_querying
- [high] Self-Blinding and Counterfactual Self-Simulation Mitigate Biases and Sycophancy in Large Language Models | arXiv 2601.14553 | https://arxiv.org/pdf/2601.14553 | lanes: epistemic-cutoff | citation check: arXiv id+title verified in corpus
  WHAT: Studies whether LLMs can approximate 'what decision they would have made had they not known certain facts'. Prompting models to ignore or pretend not to know the information fails and sometimes backfires. Querying a blinded replica of the model (its own API without the information) yields fairer decisions.
  WHY: This is the 'ask the past self' mechanism under another name. The counterfactual self is obtained by re-invoking the same model with the information withheld, not by instruction. The paper also shows that the naive instruction-based version fails. The domain is bias and sycophancy rather than time, but the computation is the same.
  CAPS: historical_epistemic_state
- [medium] AgentRewind: Recoverable Execution for Long-Horizon LLM Agents | arXiv 2608.14380 (Zhuang, Chen, Duan, Zheng, Li, Zhang) | https://arxiv.org/abs/2608.14380 | lanes: exec-state | citation check: arXiv id+title verified in corpus
  WHAT: Transparently records the trajectory (task instruction, LLM inputs and outputs, tool calls and results) and aligned checkpoints of agent context plus controlled environment. When the agent judges that it is stuck, it selects an earlier checkpoint. Both context and environment are restored, and agent-written 'rewind memory' is injected into the restored context. It contributes MettleBench, long-horizon engineering assignments with a series of related requirements.
  WHY: It jointly restores the agent's message-level epistemic state and the world state at a historical point, with agent-chosen rewind. That is the 'go back to a past self' mechanic, with deliberate hindsight carried in. MettleBench (a series of related requirements over a long horizon) is a candidate for benchmark reuse or a competitor to it.
  CAPS: immutable_historical_observations, historical_world_state, historical_epistemic_state, execution_checkpoints, replay
- [medium] Rollback the World, Keep the Reflection: Rollback-Induced Reflection for Long-Horizon LLM Agents (RIR) | arXiv 2609.18304 | https://arxiv.org/abs/2609.18304 | lanes: exec-state | citation check: arXiv id+title verified in corpus
  WHAT: Treats recovery as a rollback-boundary control problem: when to intervene, where to resume, and what information survives. It restores the world to a prior state, and 'state claims invalidated by restoration are removed'. Rollback-Consistent Reflection Memory separates branch-local state restored with the checkpoint from reusable knowledge (objective, environment knowledge, milestones, conditioned failure analysis). It deliberately excludes the agent's current state so that stale claims are not reintroduced.
  WHY: It explicitly governs which later knowledge may cross into a restored past state, the controlled-hindsight mirror of the project's strict epistemic cutoff, and shows gains across backbones. The project's cutoff discipline needs to argue why no-hindsight reconstruction beats RIR-style selective hindsight on the target tasks.
  CAPS: historical_epistemic_state, execution_checkpoints, replay, explicit_current_belief_state, predicted_vs_realized
- [medium] Planarian: Managing Agent State with Statepoints | arXiv 2609.35366 | https://arxiv.org/abs/2609.35366 | lanes: exec-state | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: An agent runtime with 'statepoints', consistent and restorable point-in-time versions of environment state spanning local sandboxes (incremental process and filesystem snapshots) and remote services (recorded compensating actions). It offers three primitives to agents and users: snapshot, rollback (restore and replay compensations) and fork (multiple isolated branches from a statepoint for parallel exploration). It reports up to 15x task-quality improvement and 3% overhead.
  WHY: It establishes agent-callable snapshot, rollback and fork over the whole environment, including remote effects, as an existing systems primitive. Its scope is world state, not belief or objective state, so it threatens only the infrastructure side of the project.
  CAPS: historical_world_state, execution_checkpoints, replay, fork_from_historical_state, counterfactual_action_branches
- [medium] AgentGit: A Version Control Framework for Reliable and Scalable LLM-Powered Multi-Agent Systems | arXiv 2511.00628; AAAI-26 WMAC workshop; code github.com/HKU-MAS-Infra-Layer/Agent-Git | https://arxiv.org/html/2511.00628 | lanes: exec-state | citation check: arXiv id+title verified in corpus
  WHAT: A Git-like layer over LangGraph/Agno. A 'Commit State' is a saved snapshot of agent state (internal context plus tool usage). State Revert restores it, and Tool Revert undoes side effects via reversion or compensating actions. 'Non-Destructive Branching: Rollbacks create new branches, preserving all timelines.' The paper criticizes LangGraph for deleting subsequent results on revert.
  WHY: 'Preserving all timelines' is essentially the project's 'never overwrite time, fork it' slogan, already shipped for LangGraph agents, with tool-effect reversal included.
  CAPS: execution_checkpoints, replay, fork_from_historical_state, counterfactual_action_branches, branch_provenance
- [medium] Git Context Controller: Manage the Context of LLM-based Agents like Git (GCC) | arXiv 2508.00031 | https://arxiv.org/abs/2508.00031 | lanes: exec-state | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: The agent itself issues COMMIT, BRANCH, MERGE and CONTEXT over a persistent, navigable context workspace. This gives milestone checkpoints, isolated exploration of alternative reasoning paths, merging of divergent paths and hierarchical retrieval of historical context. There is a global roadmap (main.md), and each branch carries commit summaries, traces and metadata.
  WHY: It versions reasoning context (not just environment) under agent control, with branch provenance and historical retrieval. It is a direct predecessor of 'agent navigates its own past states as an addressable dimension'.
  CAPS: execution_checkpoints, fork_from_historical_state, counterfactual_action_branches, branch_provenance, explicit_current_belief_state, cross_time_state_querying
- [medium] GitOfThoughts: Version-Controlled Reasoning and Agent Memory You Can Replay, Diff, and Merge | arXiv 2606.14470 (Shekar, H S, Krishnan; QpiAI) | https://arxiv.org/abs/2606.14470 | lanes: exec-state | citation check: arXiv id+title verified in corpus
  WHAT: Stores the agent's reasoning tree as a git repo: thoughts are commits, scores are notes, outcomes are tags, and retrieval is git log. It compares five memory substrates (none, markdown, vector DB, graph, git). On new problems memory did not help. Git gives auditability, provenance, line-level diffs over reasoning, deterministic replay and mergeable memory 'at accuracy parity with every other substrate'.
  WHY: It is prior negative evidence for the project's core question. A versioned, diffable, replayable reasoning history gave operational benefits but no accuracy gain over simpler memory. The project's hypothesis that temporal navigation helps task performance must beat this null, and a fair baseline must include such substrates.
  CAPS: immutable_historical_observations, replay, branch_provenance, cross_time_state_querying
- [medium] OpenRath: Session-Centered Runtime State for Agent Systems | arXiv 2606.19409 (Wen, Wang, Xu) | https://arxiv.org/abs/2606.19409 | lanes: exec-state | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: Makes the Session a first-class runtime value that is branchable, inspectable, replayable and composable. It records conversation chunks, sandbox placement, lineage metadata, token usage, pending work and tool evidence. Sessions can be forked, merged after review, persisted as evidence and replayed. It targets the fragmentation of 'transcripts, tool effects, memory events, workspace placement, branch provenance, and replay evidence'.
  WHY: It unifies runtime state, branch provenance and replay into one object passed between agents. That is a competing framing of 'state with history as a first-class value', without time-indexed beliefs or futures.
  CAPS: immutable_historical_observations, execution_checkpoints, replay, fork_from_historical_state, branch_provenance
- [medium] The OpenHands Software Agent SDK (event-sourced state model) | arXiv 2511.03690; docs.openhands.dev/sdk/arch/events; earlier OpenHands ICLR 2025 arXiv 2407.16741 | https://arxiv.org/pdf/2511.03690 | lanes: exec-state | citation check: arXiv id+title verified in corpus
  WHAT: Every interaction (LLM action, tool observation, user input) is an immutable event appended to a log. State is reconstructed at any time by folding the log, S_t = f(S_{t-1}, e_t), giving deterministic replay, crash recovery and auditability. The event stream is both the agent's memory and the integration point.
  WHY: The default architecture of a leading open coding agent already provides append-only observations and state-at-t reconstruction. Any 'immutable history + as-of state' claim is baseline infrastructure, and a strong checkpoint+RAG contestant can legitimately be built on it.
  CAPS: immutable_historical_observations, historical_world_state, execution_checkpoints, replay, cross_time_state_querying
- [medium] Safe to Resume? Breaking Execution Continuity of Agent Execution via Rollback (with companions: Exact Checking for Execution Edits, arXiv 2608.22928; ACRFence, arXiv 2603.20625) | arXiv 2608.29381 (Wu, Li, Jiang, Niu, Wang, Zhang) | https://arxiv.org/abs/2608.29381 | lanes: exec-state | citation check: arXiv id+title verified in corpus
  WHAT: The first systematic security study of agent checkpoint/rollback (C/R). It finds that 'a faithfully restored checkpoint may resume an execution whose states, assumptions, and external effects never coexisted in any valid history'. It gives five failure modes (inconsistent internal state, stale external dependencies, nondeterministic replay, unrecorded external effects) and attacks on Hermes, Cline and LangGraph. The companions add a Lean-mechanized exact safety checker for Checkpoint/Fork/Restore/Merge ('An execution edit cannot undo an earlier authorization or a tool request already sent') and an effect log with branch IDs that enforces replay-or-fork semantics.
  WHY: It undermines naive fork-from-the-past semantics. In a world with irreversible external effects, a restored historical state is not a coherent past self. The project's historical forks must handle effect consistency, or be limited to read-only reconstruction, or they inherit these failure modes. This line of work already formalizes branch semantics more rigorously than the project.
  CAPS: execution_checkpoints, replay, fork_from_historical_state, branch_provenance
- [medium] Causal Agent Replay: Counterfactual Attribution for LLM-Agent Failures (CAR) | arXiv 2606.08275 (Shah) | https://arxiv.org/abs/2606.08275 | lanes: exec-state | citation check: arXiv id+title verified in corpus
  WHAT: Models an agent run as a structural causal model. It applies do-interventions to individual steps and re-executes forward under the same stochastic policy, measuring the shift in the outcome distribution. It uses a contrastive estimator with a point-of-commitment rule and Monte-Carlo Shapley credit over interacting steps.
  WHY: It already does 'fork from a historical decision, roll forward many futures, compare outcome distributions' for agents, which covers the counterfactual-past-decision half of the project's temporal interrogation, with causal estimators.
  CAPS: replay, fork_from_historical_state, counterfactual_action_branches, multiple_prospective_branches, probability_over_futures
- [medium] TGMS: An Agent-Native Bi-Temporal Graph Management System (validated temporal operators, trace-grounded answer checking) | arXiv 2607.10265 | https://arxiv.org/abs/2607.10265 | lanes: belief-state | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: Bi-temporal property graph that exposes 13 verified temporal operators to an LLM as tools. The model plans and verbalizes, and the operators execute deterministically with content-addressed traces. The paper notes that 'when records are corrected, reconstruction of prior belief states' is required. On correction probes TGMS scores 0.897, the two latest-state baselines score 0, and vector-RAG scores 0.154.
  WHY: Already a measured comparison of as-of belief reconstruction against latest-state and vector-RAG baselines, which is a QA-scale version of the project's temporal-vs-RAG hypothesis. It shows the advantage on questions about the past. Whether that advantage carries over to decisions remains open.
  CAPS: historical_world_state, historical_epistemic_state, cross_time_state_querying, immutable_historical_observations
- [medium] Graph-Native Cognitive Memory for AI Agents: Formal Belief Revision Semantics for Versioned Memory Architectures (Kumiho) | arXiv 2603.17244 | https://arxiv.org/abs/2603.17244 | lanes: belief-state | citation check: arXiv id+title verified in corpus
  WHAT: Graph memory built from immutable revision nodes, mutable tag pointers to the current revision, typed dependency edges and URI addressing. It proves a correspondence with AGM belief revision (K*2-K*6) and Hansson's belief-base postulates. The same graph versions agent-produced work. LoCoMo F1 is 0.565.
  WHY: 'Never overwrite, add a revision' and formally grounded belief revision with dependency edges are already published for agent memory. That weakens 'never overwrite time' as a distinctive principle for belief state.
  CAPS: immutable_historical_observations, explicit_current_belief_state, cross_time_state_querying, branch_provenance
- [medium] Can Agent Memory Systems Track Evolving State? (StateMemBench) | arXiv 2608.19652 | https://arxiv.org/abs/2608.19652 | lanes: belief-state | citation check: arXiv id+title verified in corpus
  WHAT: 234 multi-session scenarios in which 'facts, constraints, and decisions are revised'. Scenarios are generated as symbolic event programs (rule declarations, value updates, commitments) rendered into dialogue, and ground-truth state comes from deterministic replay. It defines 'state drift' and scores whether answers use the superseded value. A lightweight state wrapper raises current-state accuracy by +32 to +67 points across six memory backends.
  WHY: Its construction (deterministic event program, replayed ground truth, revised decisions, drift scoring) closely mirrors the project's benchmark infrastructure. It shows that an explicit current-state layer beats plain memory retrieval by a wide margin. The project's baseline should include a comparable state wrapper, or it risks being weak.
  CAPS: explicit_current_belief_state, immutable_historical_observations
- [medium] TRACE: Governing Memory Validity in Evolving Multi-Agent Systems | arXiv 2609.33517 | https://arxiv.org/abs/2609.33517 | lanes: belief-state | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: Training-free layer for agents that return after an absence. It reconciles 'a departure checkpoint against absence-period updates', resolves explicit and implicit invalidation, and releases a bounded Return View only when it covers the role's 'open obligations'. Memories can be correct and relevant yet 'inadmissible for action'. It reports 92.6-98.3% valid-information availability and 98.4-99.5% invalid-information rejection on ManBench-Return.
  WHY: Diffs a checkpoint against the present to find implicitly invalidated items and open obligations. That is a concrete, evaluated form of 'compare past state with present and see which earlier commitments no longer hold'.
  CAPS: execution_checkpoints, explicit_current_belief_state, cross_time_state_querying
- [medium] When Memory Updates but Behavior Does Not: Repairing Implicit Stale Dependencies in Personalized Agent Responses (StateAuditor) | arXiv 2608.01619 | https://arxiv.org/abs/2608.01619 | lanes: belief-state | citation check: arXiv id+title verified in corpus
  WHAT: Targets STALE's implicit policy adaptation gap. It audits 'from stored state to draft': an LLM proposes candidate old-to-new transitions from timestamped evidence, and deterministic code checks provenance and chronology (that the new evidence really is newer) before allowing repair. On STALE's full protocol it gains +5.0 points (95% CI +2.9 to +7.2).
  WHY: Shows that chronology-verified transitions (old to new) are already used to trigger repair of outputs that depend on stale state, with a measured gain. This is a narrow temporal mechanism of the kind the project would generalize.
  CAPS: explicit_current_belief_state, cross_time_state_querying
- [medium] Agent-BRACE: Decoupling Beliefs from Actions in Long-Horizon Tasks via Verbalized State Uncertainty | arXiv 2605.11436 | https://arxiv.org/abs/2605.11436 | lanes: belief-state | citation check: arXiv id+title verified in corpus
  WHAT: Splits the agent into a belief-state model and a policy model trained jointly with RL. The belief state is a set of atomic natural-language claims, each with an ordinal certainty label on a words-of-estimative-probability scale (confirmed to unknown). Reported gains are +14.5% (Qwen2.5-3B) and +5.3% (Qwen3-4B), with near-constant context.
  WHY: An explicit, structured current belief state with per-claim uncertainty already exists and is trained end to end, so the project cannot claim an explicit belief state with uncertainty as a contribution. It does not version beliefs over time.
  CAPS: explicit_current_belief_state, uncertainty_representation
- [medium] Truth / Reason Maintenance Systems (Doyle 1979 TMS; de Kleer assumption-based TMS) | Foundational AI (Doyle 1979; de Kleer ATMS 1986) | https://en.wikipedia.org/wiki/Reason_maintenance | lanes: belief-state | citation check: non-arXiv
  WHAT: Records the justification for every belief and supports dependency-directed backtracking, so beliefs are revised when assumptions change or contradictions arise. The ATMS tracks the assumption sets (environments) under which each belief holds, which lets several assumption contexts coexist. LLM-era reimplementations include Corollary, ftl-reasons (github.com/benthomasson/ftl-reasons) and lemmalog (github.com/afogel/lemmalog).
  WHY: The basic abstraction for detecting that an assumption behind a conclusion was withdrawn and retracting what depended on it is 45+ years old. LLMs mainly remove the cost of writing justifications by hand. Any novelty claim has to be about temporal navigation, not invalidation tracking.
  CAPS: explicit_current_belief_state, uncertainty_representation
- [medium] HindsightBench: A Black-Box Behavioral Audit Protocol for Parametric Hindsight in Time-Indexed LLM Decision Tasks | arXiv 2607.18867 | https://arxiv.org/abs/2607.18867 | lanes: belief-state,epistemic-cutoff | citation check: arXiv id+title verified in corpus
  WHAT: Audits how LLMs leak parametric knowledge of realized outcomes into historical (financial) decision tasks. It uses a four-arm date-manipulation matrix and memory probes to estimate a 'behaviorally effective knowledge cutoff'. Effective cutoffs differ by 22 months across vendors and come up to 8 months before the vendor-reported dates.
  WHY: A 'strict epistemic cutoff, no hindsight' claim has a known failure mode, leakage from model weights, and an existing audit method for it. For a synthetic software world this matters less, but any real-world as-of evaluation in the project needs such a leakage control.
  CAPS: historical_epistemic_state, historical_policy_objective_state
- [medium] Datomic: as-of / since / history database values, speculative d/with, transaction provenance | Datomic (official tutorials GitHub Datomic/day-of-datomic; Datomic/mbrainz-sample) | https://github.com/Datomic/day-of-datomic | lanes: temporal-memory | citation check: non-arXiv
  WHAT: "Datomic is a database of flexible, time-based facts". Tutorials show (d/as-of db #inst "2014-01-01"), (d/since ...) and (d/history db), plus ";; what was the title as of earlier point in time? (:story/title (d/entity (d/as-of db tx) story))" and ";; who changed the title, and when?" through transaction attributes (:source/user). (d/with db [tx]) yields "another database *value*" speculatively, without committing it.
  WHY: It shows that immutable database values queryable as-of a past transaction, provenance on transactions, and speculative what-if values that are never committed are all long-standing database primitives. That covers the substrate for 'reconstruct what was known then' and 'explore an alternative without committing'. Valid-time support was not verified this session.
  CAPS: immutable_historical_observations, historical_world_state, historical_epistemic_state, counterfactual_action_branches, branch_provenance, cross_time_state_querying
- [medium] Event sourcing (Python eventsourcing library as reference implementation) | GitHub pyeventsourcing/eventsourcing; PyPI eventsourcing | https://github.com/pyeventsourcing/eventsourcing | lanes: temporal-memory | citation check: non-arXiv
  WHAT: Aggregates are reconstructed from stored domain events. The docs say "event sourcing is simply a left-fold over a stream of events". Past states are addressable with repository.get(dog_id, version=1). Snapshotting "reduces access-time for aggregates that have many events". Events and snapshots are versioned.
  WHY: 'Never overwrite' plus replay plus state-at-version is the canonical event-sourcing pattern, with snapshots as a cache over the log. Agent frameworks have already adopted it: OpenHands SDK and ActiveGraph, per sibling-lane search. A checkpoint+log baseline is therefore the standard design, not a strawman.
  CAPS: immutable_historical_observations, historical_world_state, execution_checkpoints, replay, cross_time_state_querying
- [medium] Dolt (Git for Data) and lakeFS (data version control) | GitHub dolthub/dolt; GitHub treeverse/lakeFS | https://github.com/dolthub/dolt | lanes: temporal-memory | citation check: non-arXiv
  WHAT: Dolt: "a SQL database that you can fork, clone, branch, merge, push and pull just like a Git repository". It also says "A Dolt commit allows you to time travel and see lineage". Branches can be compared with dolt_diff('main','modifications','employees'). lakeFS (https://github.com/treeverse/lakeFS): "keeping track of more than just the current state of data. This makes reproducing its state at any point in time straightforward", with zero-copy branches.
  WHY: The 'fork it, never overwrite' half of the slogan is Git semantics applied to state, productized for databases and data lakes: branch from a commit, diff two branches, merge, keep lineage. AgentGit, GCC and ActiveGraph (sibling lanes) already port this to agents.
  CAPS: immutable_historical_observations, execution_checkpoints, replay, fork_from_historical_state, branch_provenance, cross_time_state_querying
- [medium] Impact Is Not Invalidation: Ask About the Claim, Not the Diff | arXiv 2609.25130 | https://arxiv.org/pdf/2609.25130 | lanes: temporal-memory,benchmarks | citation check: arXiv id+title verified in corpus
  WHAT: Per the list summary, it evaluates when a coding agent's stored memory assertions become invalid after repository changes. Claim flips are verified by execution. Across 10,369 assertions from 23 Python libraries, asking about the specific claim reaches precision 0.705-0.974. Judging the whole diff reaches only 0.291-0.329.
  WHY: The setting is a software world where a later change alters the validity of an earlier stored belief, with execution-verified ground truth, which is close to the benchmark premise. The result suggests the effective mechanism is claim-targeted re-checking, not temporal navigation per se.
  CAPS: explicit_current_belief_state, cross_time_state_querying, historical_world_state
- [medium] GitHarness: Git Init Your Harness Working Memory for Perpetual User Requirements | arXiv 2609.36789 | https://arxiv.org/pdf/2609.36789 | lanes: temporal-memory | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: Requirements and their work state are organized as branchable, versioned memory, and still-valid historical results are kept. A Git Agent learns to recognize requirement changes and choose a compatible historical state. A unified restore/branch interface excludes stale information. MTAgentBench reports gains across five task types; the summary gives no unified numbers.
  WHY: When requirements change, the agent selects a compatible past state and forks from it. That is temporal navigation of the agent's own working state, triggered by a later event, evaluated on a benchmark of changing requirements. It overlaps the 'reopen earlier work after a later event' scenario.
  CAPS: execution_checkpoints, replay, fork_from_historical_state, branch_provenance, cross_time_state_querying
- [medium] Mem++: Non-Destructive Memory for Long-Term Organizational LLM Agents | arXiv 2610.02002 | https://arxiv.org/pdf/2610.02002 | lanes: temporal-memory | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: It keeps organizational documents and their old versions in full, with author and date, and defers selection to query time. Writes call no generative model. Reads filter by the question's time, fuse lexical and semantic ranks, and let the answer model choose the valid version. It scores +8.0-13.1 over the strongest memory baseline on OrgMemBench. On other conversational benchmarks, rankings vary with the variant and answer model.
  WHY: The memory half of 'never overwrite time', with time-filtered retrieval, is published with an evaluation. Its benchmark-dependent advantage warns that non-destructive temporal memory does not uniformly beat strong baselines.
  CAPS: immutable_historical_observations, historical_world_state, cross_time_state_querying
- [medium] TOKI: A Bitemporal Operator Algebra for Contradiction Resolution in LLM-Agent Persistent Memory | arXiv 2606.06240 | https://arxiv.org/abs/2606.06240 | lanes: temporal-memory | citation check: arXiv id+title verified in corpus
  WHAT: Per the list summary, it treats contradiction resolution in persistent agent memory as a write-time consistency problem. It defines a bitemporal operator algebra with explicit isolation assumptions, provenance annotation and audit rows. It states the correctness contract memory systems need when beliefs evolve or conflict. A sibling-lane search extract says it preserves "the losing fact in an audit row" and names "replay inconsistency, belief-drift skew, and audit erasure".
  WHY: It is already a formal two-time-axis semantics for how agent beliefs evolve, including replay consistency. Any formalization of 'temporal agency' state would be judged against it.
  CAPS: immutable_historical_observations, historical_epistemic_state, cross_time_state_querying
- [medium] The Immutable Past: Formalizing State Mutability and Conflict Resolution in Mutable RAG (GC-Mem) | arXiv 2609.16073 | https://arxiv.org/pdf/2609.16073 | lanes: temporal-memory | citation check: arXiv id+title verified in corpus
  WHAT: Per the list summary, GC-Mem addresses old facts overpowering current state in append-only agent memory. It uses temporal dominance and contradiction detection to remove superseded evidence while keeping unrelated valid long-term records. It reports more than 90% conflict-resolution accuracy on its cumulative benchmark, with precision/recall conditions for deployment.
  WHY: It formalizes the cost of 'never overwrite': append-only memory without supersession semantics degrades current answers. The fix is a temporal-dominance (valid/transaction-time) rule, so the formal treatment of immutable history plus current-state resolution already exists.
  CAPS: immutable_historical_observations, explicit_current_belief_state
- [medium] Correct Now, Insufficient Later: Auditing Update Sufficiency in Context Compression | arXiv 2609.20045 | https://arxiv.org/pdf/2609.20045 | lanes: temporal-memory | citation check: arXiv id+title verified in corpus
  WHAT: Per the list summary, it defines 'update sufficiency': compressed memory that answers the current question correctly should still keep the historical differences that future updates need. It builds paired histories with the same current answer and the same later update but different future correct answers, in a small synthetic audit. It finds that correct current answers can mask lost update evidence, and identifies identifier shortcuts. Generalization to natural tasks is not yet verified.
  WHY: It is the clearest prior statement of the project's core intuition: a checkpoint or summary that is right now can fail when a later event changes what the earlier history means. Its paired-history design is a ready-made leakage-controlled benchmark template, so the argument is pre-empted as novel.
  CAPS: immutable_historical_observations, predicted_vs_realized
- [medium] Agent-R: Training Language Model Agents to Reflect via Iterative Self-Training | arXiv 2501.11425 | https://arxiv.org/abs/2501.11425 | lanes: counterfactual-worldmodel | citation check: arXiv id+title verified in corpus
  WHAT: Uses MCTS to build revision trajectories. The actor model finds 'the first error step' in a failed trajectory and splices it 'with the adjacent correct path, which shares the same parent node in the tree'. It then trains the agent on the bad-prefix, revision-thought, good-continuation data.
  WHY: It retrospectively finds which earlier decision went wrong and learns from the alternative sibling branch. That is the 'reopen an earlier decision' idea, but within a single episode and with outcome hindsight, and its output is training data rather than an agent-time remediation behaviour.
  CAPS: fork_from_historical_state, counterfactual_action_branches, branch_provenance, replay
- [medium] ExACT: Teaching AI Agents to Explore with Reflective-MCTS and Exploratory Learning | arXiv 2410.02052 (ICLR 2025) | https://arxiv.org/abs/2410.02052 | lanes: counterfactual-worldmodel | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: R-MCTS with contrastive reflection and backtracking. After a task, the code computes |expected V_next - actual Q| per step and picks the 'most_unexpected' state-action. It generates a reflection and stores a ReflectionRecord (intent, state, action, next_state, reflection, _from_task_hash) in a persistent FAISS DB, which retrieve_reflections() queries in later tasks. Exploratory Learning trains models to 'backtrack to viable ones'.
  WHY: This is the closest found to 'compare expected vs realized, keep the lesson with provenance, reuse it later across tasks'. It is a strong, implementable baseline ingredient for checkpoint+RAG. It stores distilled reflections, not the branches, and has no epistemic cutoff.
  CAPS: predicted_vs_realized, counterfactual_action_branches, multiple_prospective_branches, fork_from_historical_state, branch_provenance, immutable_historical_observations
- [medium] Is Your LLM Secretly a World Model of the Internet? Model-Based Planning for Web Agents (WebDreamer) | arXiv 2411.06559 | https://arxiv.org/abs/2411.06559 | lanes: counterfactual-worldmodel | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: Uses an LLM as a world model to predict webpage changes for each candidate action over k imagination steps, with several simulations per action. It scores the simulations and picks an action ('speculative planning'). The released modules keep simulations in memory only and do not persist them.
  WHY: It makes 'simulate possible futures before acting' standard prior art (WebDreamer and successors). It shows imagined futures are routinely discarded after the decision, so the project cannot claim prospective simulation itself, only what it does with the simulated branches afterwards.
  CAPS: future_state_rollout, multiple_prospective_branches, counterfactual_action_branches
- [medium] Web Agents with World Models: Learning and Leveraging Environment Dynamics in Web Navigation (WMA) | arXiv 2410.13232, ICLR 2025 | https://arxiv.org/abs/2410.13232 | lanes: counterfactual-worldmodel | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: A world-model-augmented web agent that 'simulates the outcomes of its actions' to avoid irreversible mistakes ('repeatedly buying a non-refundable flight ticket'). It uses transition-focused natural-language state-difference prediction and a value model for policy selection.
  WHY: Feared-future avoidance (simulate harm, then avoid the action) is already standard. It is a one-step, action-filter version of the project's 'backward requirements from feared futures'. The averted future is not preserved or labelled.
  CAPS: future_state_rollout, counterfactual_action_branches, multiple_prospective_branches
- [medium] WALL-E 2.0: World Alignment by NeuroSymbolic Learning improves World Model-based LLM Agents | arXiv 2504.15785 (NeurIPS 2025 per repo) | https://arxiv.org/abs/2504.15785 | lanes: counterfactual-worldmodel | citation check: arXiv id+title verified in corpus
  WHAT: An MPC agent where the LLM is 'an efficient look-ahead optimizer of future steps' actions by interacting with the neurosymbolic world model'. It refines symbolic rules by '(1) comparing predicted and actual trajectories; (2) learning new symbolic knowledge from real trajectories'.
  WHY: It already uses systematic predicted-vs-realized comparison to update an agent's world knowledge. The comparison is used to fix the world model, not to calibrate forecasts or tell prevented futures apart from wrong ones.
  CAPS: future_state_rollout, predicted_vs_realized, counterfactual_action_branches
- [medium] Agent Learning via Early Experience | arXiv 2510.08558 | https://arxiv.org/abs/2510.08558 | lanes: counterfactual-worldmodel | citation check: arXiv id+title verified in corpus
  WHAT: UNVERIFIED (from recall): the agent tries alternative actions at states from expert trajectories, observes the resulting states, and trains on implicit world modelling plus self-reflection that contrasts expert and alternative actions.
  WHY: If the recalled description is accurate, it is a direct, widely cited 2025 instance of 'explore alternative branches from past states and learn from them'. Its content must be verified before it is cited.
  CAPS: counterfactual_action_branches, fork_from_historical_state, future_state_rollout
- [medium] Live-Evo: Online Evolution of Agentic Memory from Continuous Feedback | arXiv 2602.02369 | https://arxiv.org/abs/2602.02369 | lanes: prospective-forecast | citation check: arXiv id+title verified in corpus
  WHAT: An online self-evolving memory with an Experience Bank and a Meta-Guideline Bank. It updates experience weights from realized feedback: experiences that help are reinforced, and misleading or stale ones are down-weighted and forgotten. On the live Prophet Arena benchmark over 10 weeks it improves Brier score by 20.8% and market returns by 12.9%.
  WHY: This is live, outcome-driven self-calibration of a forecasting agent with a large measured gain. It is a strong baseline that a temporal contestant must beat. Its decay-and-forget design also contrasts with 'never overwrite time', which gives the project an ablation axis to test.
  CAPS: predicted_vs_realized, probability_over_futures
- [medium] ForecastBench-Sim: A Simulated-World Forecasting Benchmark | arXiv 2606.18686 (Forecast@ICML 2026 workshop per survey 2608.23058) | https://arxiv.org/abs/2606.18686 | lanes: prospective-forecast | citation check: arXiv id+title verified in corpus
  WHAT: Built on Freeciv game rollouts. Forecasters receive a snapshot of the world state and answer questions about hidden future states. The simulation then continues and the forecasts are scored. Because the world is simulated, the benchmark can generate 'paired intervention worlds for conditional or causal questions' and resolved examples of rare outcomes.
  WHY: It already scores intervention-conditioned forecasts against paired counterfactual worlds, which is the evaluation machinery behind 'intervention-aware forecasting'. It does this at the environment level in a game, and does not keep the agent's own averted forecasts.
  CAPS: future_state_rollout, multiple_prospective_branches, intervention_aware_forecasting, probability_over_futures, predicted_vs_realized
- [medium] FORESIGHT-9: Prospective and Process-Aware Evaluation of Adaptive Trading Agents | arXiv 2608.29372 | https://arxiv.org/abs/2608.29372 | lanes: prospective-forecast | citation check: arXiv id+title verified in corpus
  WHAT: Nine auditable counterfactual stress 'worldlines' branch from a common July 2026 information boundary. A deterministic generator realizes them, and observations are disclosed according to in-world time. It evaluates whether the state and execution of an adaptive agent stay coherent across alternative futures. Process telemetry showed a case where decision records claimed an active factor ensemble while the holdings had collapsed to equal weight. A fixed equal-weight policy beat 31 of 36 runs.
  WHY: This is 'fork, don't overwrite' applied to the future: several alternative futures branch from one information boundary, with a time-gated epistemic state and audit traces. It also shows empirically that what an agent reports about its own state can diverge from what actually happened, which bears on any self-reported temporal state.
  CAPS: multiple_prospective_branches, fork_from_historical_state, historical_epistemic_state, immutable_historical_observations
- [medium] Long-term Task-oriented Agent: Proactive Long-term Intent Maintenance in Dynamic Environments (ChronosBench) | arXiv 2601.09382 | https://arxiv.org/abs/2601.09382 | lanes: prospective-forecast | citation check: arXiv id+title verified in corpus
  WHAT: Defines two capabilities. Intent-conditioned monitoring: the agent writes trigger conditions from the dialog history. Event-triggered follow-up: it re-engages the user when environment updates satisfy those conditions. ChronosBench has 1,052 dialogs, including intent shifts. A fine-tuned model reaches 85.19% completion on complex tasks.
  WHY: It covers reopening a dormant task when the world changes, with stored structured trigger conditions. Those conditions are a weak form of present obligations derived from a desired future. It is limited to user intents, not the agent's own past decisions.
  CAPS: backward_requirements, explicit_current_belief_state
- [medium] Making Prospective Memory SLM-Shaped: Typed Intention Stores for Small-Model Agents (with TriggerBench 2606.23459, BudgetPM 2609.37125, 2603.23530, 2609.22091) | arXiv 2609.01272 | https://arxiv.org/abs/2609.01272 | lanes: prospective-forecast | citation check: arXiv id+title verified in corpus
  WHAT: Argues that prospective memory is schema-constrained state tracking. It proposes a Prospective Intention Store with lifecycle logic in code and scoped language work on the model. Results on PM-Bench: DeepSeek-Chat reaches 82.9% Set-F1; Gemma-E2B goes from 4.2% to 66.2%; retrospective-memory methods reach at most 54.4%. Related work in the same cluster: TriggerBench shows prospective memory decays with context length while retrospective memory saturates. BudgetPM budgets the external checks that stored intentions require. 'Memory That Looks Forward' keeps a dated or trigger-conditioned commitment ledger.
  WHY: Prospective obligations in agents are a crowded, measured area by late 2026. PIS is also a deflationary result: a typed store with logic in code beats retrospective memory. Any gain on prospective tasks may therefore come from schema plus code rather than from a temporal abstraction, so the baseline must include such a store.
  CAPS: explicit_current_belief_state
- [medium] Current Agents Fail to Leverage World Model as Tool for Foresight | arXiv 2601.03905 | https://arxiv.org/abs/2601.03905 | lanes: prospective-forecast | citation check: arXiv id+title verified in corpus
  WHAT: Gives VLM agents generative world models as simulation tools. Agents invoke simulation in fewer than 1% of cases, misuse predicted rollouts about 15% of the time, and show inconsistent or degraded performance (up to 5%) when simulation is available or enforced. The bottleneck is deciding when to simulate, how to interpret rollouts, and how to integrate them.
  WHY: This is direct evidence against the assumption that letting agents simulate and question future states yields decision benefits. The project must show its prospective interface avoids these failures, or its benefit claim is already contradicted.
  CAPS: future_state_rollout
- [medium] Simulated Ignorance Fails: A Systematic Study of LLM Behaviors on Forecasting Problems Before Model Knowledge Cutoff | arXiv 2601.13717 (IJCAI 2026 per paper lists) | https://arxiv.org/abs/2601.13717 | lanes: prospective-forecast | citation check: arXiv id+title verified in corpus
  WHAT: Uses 477 Metaculus questions and 9 models to test whether prompting a model to suppress later knowledge ('simulated ignorance') approximates true ignorance. Cutoff instructions close only 52% of the gap, chain-of-thought does not remove leakage, and reasoning models leak more despite cleaner traces. The related OracleProto (2605.03762) concludes that 'pretend not to know' cannot replace a genuine knowledge boundary.
  WHY: This undermines a naive implementation of 'reconstruct what the agent believed at t with no hindsight'. Instruction-based cutoffs leak, so the cutoff must be enforced by data and context isolation. Even then, parametric knowledge of the world after t leaks. It constrains how the benchmark must be built and limits the hindsight-free claims the project can make.
  CAPS: historical_epistemic_state
- [medium] Performative Prediction (with Performative Learning Theory 2602.04402) | arXiv 2002.06673 (ICML 2020) | https://arxiv.org/abs/2002.06673 | lanes: prospective-forecast | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: Formalizes predictions that influence the outcomes they predict, and defines performative stability, under which predictions are 'calibrated not against past outcomes, but against the future outcomes that manifest from acting on the prediction'. The 2026 follow-up casts self-negating and self-fulfilling predictions as risk functionals.
  WHY: This is the established abstraction for 'forecasts conditioned on, and altered by, one's own intervention'. The project's 'prevented futures preserved, not scored as wrong' is a specific self-negating-prediction case and must be positioned against this theory. No LLM-agent work was found that keeps averted forecasts as labelled objects, so the narrow residual remains.
  CAPS: intervention_aware_forecasting, predicted_vs_realized
- [medium] Penalizing side effects using stepwise relative reachability / Avoiding Side Effects By Considering Future Tasks (Krakovna et al.) | arXiv 1806.01186; NeurIPS 2020 (future-tasks paper) | https://github.com/google-deepmind/deepmind-research/tree/master/side_effects_penalties | lanes: backward-optionality | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: Impact penalties defined as deviation from a baseline state (starting state, inaction, or stepwise inaction with rollouts), with unreachability, relative reachability or attainable-utility deviation measures. In the NeurIPS 2020 follow-up, 'the agent receives an auxiliary reward for preserving the ability to perform future tasks', which is equivalent to relative reachability with an inaction baseline.
  WHY: This is the foundational formalisation of option-preserving action derived from hypothetical future goals, measured against counterfactual baselines, with code. 'Option-preserving actions' in the thesis must be positioned as an LLM-agent instantiation of this, not a new idea. The NeurIPS 2020 arXiv id was not confirmed.
  CAPS: backward_requirements, counterfactual_action_branches, future_state_rollout, multiple_prospective_branches
- [medium] Conservative Agency via Attainable Utility Preservation (Turner et al.) | arXiv 1902.09725 | https://arxiv.org/abs/1902.09725 | lanes: backward-optionality | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: Penalises changes to the agent's ability to achieve a set of auxiliary goals ('quantifying and penalizing the change an agent has on the world around it'). It is tested in gridworlds that score a hidden performance function. Gridworlds frames the problem as minimising effects 'especially those that are irreversible'.
  WHY: Preserving attainable value across a distribution of possible future objectives is an established safety abstraction for option preservation. Any 'option-preserving' claim needs to be differentiated from it, for example by persistence across time or by the LLM setting.
  CAPS: backward_requirements, counterfactual_action_branches, multiple_prospective_branches
- [medium] JANUS: Foreseeing Latent Risk for Long-Horizon Agent Safety | arXiv 2607.19913 | https://arxiv.org/abs/2607.19913 | lanes: backward-optionality | citation check: arXiv id+title verified in corpus
  WHAT: Trains a guard with two coupled tasks: 'an anticipation task that forecasts safety-relevant futures and an adjudication task that decides safety from both the observed prefix and anticipated future'. Training uses CoAA-RL, 'which rewards forecasts by their utility for downstream safety judgment', and the guard blocks unsafe actions before execution.
  WHY: It trains 'imagine the feared future, then constrain the present action'. Scoring forecasts by their usefulness to the decision rather than by realised accuracy partly overlaps the project's idea that prevented forecasts should not be scored as wrong.
  CAPS: future_state_rollout, backward_requirements, intervention_aware_forecasting
- [medium] SIMMER: Benchmarking Latent Failures in LLM Executable Planning with a World Model | arXiv 2606.14574 | https://arxiv.org/abs/2606.14574 | lanes: backward-optionality | citation check: arXiv id+title verified in corpus
  WHAT: A symbolic kitchen world model (77 actions, about 46,800 interactions) that detects 'latent failures [that] do not immediately halt plan execution but silently compromise goal achievement', many of them irreversible. 'counterfactual foresight simulation can reduce latent failures by up to 72% and irreversible cases by up to 75%'.
  WHY: It is a benchmark built around early decisions whose harm only shows later, and it shows that forward foresight simulation fixes much of the problem. The project's benchmark has to show what persistence over time adds beyond that.
  CAPS: future_state_rollout, counterfactual_action_branches, backward_requirements
- [medium] Distinguish or Homogenize: Last-Chance Policy Identification and Risk-Budgeted Recovery under Irreversible Resource Depletion | arXiv 2609.36741 | https://arxiv.org/abs/2609.36741 | lanes: backward-optionality | citation check: arXiv id+title verified in corpus
  WHAT: Under irreversible depletion, the agent either spends resources to distinguish latent fault models or changes the state 'so that the remaining models admit a common acceptable continuation'. Correctness is evaluated 'at the state the agent reaches'. A Last Identifiable Margin marks the boundary, and RBCP plans under a hard worst-case failure budget. A sham control confirms the effect.
  WHY: It formalises option-preserving present action under irreversibility and model uncertainty, with a 'last chance' boundary that resembles DMDU tipping points. Not LLM-specific.
  CAPS: uncertainty_representation, multiple_prospective_branches, backward_requirements, future_state_rollout
- [medium] Reason for Future, Act for Now: A Principled Framework for Autonomous LLM Agents with Provable Sample Efficiency (RAFA) | arXiv 2309.17382; ICML 2024 | https://arxiv.org/abs/2309.17382 | lanes: backward-optionality | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: The LLM 'plans a future trajectory over a long horizon', takes only 'the initial action of the planned trajectory', stores feedback, and replans from the new state. This casts LLM reasoning as Bayesian-adaptive MDP planning with a sqrt(T) regret bound. LLMPC similarly frames LLM prompting as model predictive control.
  WHY: 'Act from a defined present by simulating the future, then replan' is receding-horizon control with a regret guarantee, already established for LLM agents. The thesis cannot claim the act-from-the-present loop as novel.
  CAPS: future_state_rollout, explicit_current_belief_state, uncertainty_representation, predicted_vs_realized
- [medium] Exploratory Modeling workbench (EMA) for decision making under deep uncertainty / Robust Decision Making | TU Delft open-source toolkit (PyPI ema_workbench) | https://github.com/quaquel/EMAworkbench | lanes: backward-optionality | citation check: non-arXiv
  WHAT: Computational experiments over ensembles of uncertain futures 'for decision making under deep uncertainty and robust decision making'. It includes directed search over decision levers ('the first step in the Many Objective Robust Decision Making process') and scenario discovery of the conditions under which strategies fail.
  WHY: Deriving present policy and its vulnerability conditions from simulated ensembles of futures is a mature methodology with tooling. The thesis's 'backward requirements from feared futures' is essentially DMDU applied to agent state. DAPP signposts and tipping points were not confirmed in any fetched source (unverified).
  CAPS: multiple_prospective_branches, future_state_rollout, uncertainty_representation, backward_requirements
- [medium] Accurate Failure Prediction in Agents Does Not Imply Effective Failure Prevention ("The Intervention Paradox") (Vasudev, Russak, Bikel, Alshikh) | arXiv 2602.03338 | https://arxiv.org/abs/2602.03338 | lanes: performative-prevented | citation check: arXiv id+title verified in corpus
  WHAT: An LLM critic with offline AUROC 0.94 can still cause a 26 pp collapse when its predictions trigger interventions. The paper identifies a 'disruption-recovery tradeoff: interventions may recover failing trajectories but also disrupt trajectories that would have succeeded'. It proposes a 50-task pilot test of whether intervening helps.
  WHY: It reproduces the clinical result 'accurate forecasts are not the same as beneficial interventions' for LLM agents. Forecast accuracy and the value of acting on it are scored separately, using with/without-intervention counterfactual runs. Part of the agent-specific space is already taken.
  CAPS: intervention_aware_forecasting, counterfactual_action_branches, predicted_vs_realized
- [medium] Reflexive Model-World Systems: When Representations Become Causes (Sorenson) | Independent preprint on GitHub (corbensorenson/asi-stack-book), not peer-reviewed | https://github.com/corbensorenson/asi-stack-book/blob/main/papers/source/reflexive_model_world_systems.md | lanes: performative-prevented | citation check: non-arXiv
  WHAT: Defines counterfactual-label mismatch: 'A successful prediction can therefore become observationally false because it was causally effective ... alarms are often designed to invalidate their own forecasts.' A simulation shows naive retraining underestimates baseline risk by about 24.9%, and 'A dashboard that reports only mismatch between the alarm and observed outcome would punish causal success.' It proposes a four-way evaluation matrix (baseline fidelity / on-policy fidelity / steering utility / legitimacy). Its 'High/Low/High' row is labelled 'Potentially successful self-negating intervention'. It also notes that agent regret learning must separate deployed-policy regret from counterfactual regret.
  WHY: It states the project's principle almost word for word, with a scoring matrix that keeps a self-negating forecast from being counted as a failure, and it extends the idea to agent regret learning. It is not peer-reviewed, but it shows the idea is already in circulation in 2026.
  CAPS: intervention_aware_forecasting, prevented_futures_preserved, predicted_vs_realized, historical_policy_objective_state
- [medium] Good and safe uses of AI Oracles (counterfactual oracle) (Armstrong & O'Rorke) | arXiv 1711.05541 | https://arxiv.org/abs/1711.05541 | lanes: performative-prevented | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: The oracle's output is erased at random. The oracle is trained and scored only on erasure episodes, so it predicts what would happen if its prediction were not seen. Verbatim: 'had we not seen p_n, that is what o_n would have been'. Contrasting predictions given h and given h+erasure 'reveals the extent to which the prediction is potentially manipulative'.
  WHY: It is the cleanest recipe for scoring a forecaster whose output would otherwise change the world: randomly withhold the forecast and score only those episodes. It covers the 'reflexive forecast' tier of the project's taxonomy, and it makes clear that verifying a prevented forecast needs randomization.
  CAPS: intervention_aware_forecasting, predicted_vs_realized
- [medium] Incentivizing honest performative predictions with proper scoring rules (Oesterheld, Treutlein, Cooper, Hudson) | UAI 2023, PMLR v216:1564-1574; arXiv 2305.17601 | https://arxiv.org/abs/2305.17601 | lanes: performative-prevented | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: Studies proper scoring when predictions influence outcomes. Reports that maximize expected score generally do not reflect beliefs. For binary outcomes with bounded influence, scoring rules exist whose optimal reports are close to fixed points; this is impossible for more than two outcomes. The paper also discusses performative stability.
  WHY: It is the scoring theory for reflexive forecasts. Learning from 'predicted vs realized' when the agent's own forecast drives the outcome rewards manipulation. Any agent-side calibration loop over its own reflexive forecasts inherits these impossibility results.
  CAPS: intervention_aware_forecasting, probability_over_futures, predicted_vs_realized
- [medium] Decision markets and decision scoring rules (Othman & Sandholm 2010; Chen, Kash, Ruberry & Shnayder 2011; Oesterheld & Conitzer 2020) | Bibliography: buttermarkets/learn-futarchy sota-decision-markets.md (EC/WINE-line papers) | https://github.com/buttermarkets/learn-futarchy/blob/main/sota-decision-markets.md | lanes: performative-prevented | citation check: non-arXiv
  WHAT: Studies conditional forecasts that select the action. 'When the price drives the choice, naive decision rules are manipulable' (Othman & Sandholm). Strict properness requires a 'full-support' decision rule that 'must sometimes randomize' (Chen & Kash; Chen et al.). Decision scoring rules are truthful without randomizing, 'but only the recommended action's value is elicited' (Oesterheld & Conitzer).
  WHY: Conditional forecasts for actions not taken are voided. The mechanism-design literature then shows that a deterministic chooser can never verify the branch it avoided. This directly limits what 'preserving prevented futures' can be used for when scoring.
  CAPS: intervention_aware_forecasting, multiple_prospective_branches, probability_over_futures, prevented_futures_preserved, predicted_vs_realized
- [medium] Prediction under interventions: evaluation of counterfactual performance using longitudinal observational data (Keogh & van Geloven) / Estimating and evaluating counterfactual prediction models (Boyer, Dahabreh & Steingrimsson) | Epidemiology 35(3):329-339 (arXiv 2304.10005); Stat Med 44(23-24):e70287 | https://doi.org/10.1002/sim.70287 | lanes: performative-prevented | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: Extends calibration, c-index, AUC and Brier score to outcomes under a hypothetical strategy, using artificial censoring and IPW, so a 'risk under no treatment' forecast can be scored on data where some units were treated. Valid under conditional exchangeability and positivity. R packages: ipeval and cfperformance.
  WHY: These are working estimators for scoring forecasts of the world without intervention when the intervention happened for some cases. They make explicit that this scoring is only identified under exchangeability and positivity, which a self-intervening deterministic agent violates.
  CAPS: intervention_aware_forecasting, predicted_vs_realized, uncertainty_representation
- [medium] When accurate prediction models yield harmful self-fulfilling prophecies (van Amsterdam, van Geloven, Krijthe, Ranganath, Cinà) | Patterns 2025 (doi 10.1016/j.patter.2025.101229); arXiv 2312.01210 | https://arxiv.org/abs/2312.01210 | lanes: performative-prevented | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: Shows that outcome prediction models used for treatment decisions can harm patients while keeping good discrimination after deployment. Verbatim: 'good discrimination or calibration after deployment does NOT imply an OPM improved outcomes'. Also: 'requiring an OPM to have good calibration before AND after deployment renders it useless for decision making.'
  WHY: It shows that predicted-vs-realized agreement after acting is not a measure of forecast quality, and that drift after deployment is the expected sign of a useful forecast. Any project metric built on post-action forecast-outcome comparison needs this correction.
  CAPS: intervention_aware_forecasting, predicted_vs_realized
- [medium] Model updating after interventions paradoxically introduces bias (Liley, Emerson, Mateen, Vallejos, Aslett, Vollmer); with Lenert et al. 2019 and Sperrin et al. 2019 on 'victims of their own success' | AISTATS 2021; arXiv 2010.11530 | https://arxiv.org/abs/2010.11530 | lanes: performative-prevented | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: Shows that retraining a risk score on data generated after the score triggered interventions biases the updated model. Companion work proposes untreated holdout sets (OptHoldoutSize) and explicit causal reasoning so that prognostic models are not 'victims of their own success'. Abstract not fetched; the description is based on the title and bibliography context.
  WHY: Clinical ML has documented since 2019 that labels prevented by intervention must not be read as negatives, and that the fix is randomized holdouts or causal adjustment. This predates the project's 'prevented futures' rule by years.
  CAPS: intervention_aware_forecasting, predicted_vs_realized
- [medium] Performative Prediction (Perdomo, Zrnic, Mendler-Dünner, Hardt), with the follow-up survey 'Performative Prediction: Past and Future' (Hardt & Mendler-Dünner, arXiv 2310.16608) | ICML 2020; arXiv 2002.06673 | https://arxiv.org/abs/2002.06673 | lanes: performative-prevented | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: Defines predictions that influence their target through a distribution map D(theta), and defines performative stability and optimality. Verbatim: 'Performative stability implies that the predictions are calibrated not against past outcomes, but against the future outcomes that manifest from acting on the prediction.' The survey separates 'learning' from 'steering'.
  WHY: This is the foundational ML abstraction for reflexive forecasts. It redefines what 'calibrated' means once a forecast changes the outcome, which undercuts any claim that reflexive forecasting is new. It is also covered by the prospective-forecast lane.
  CAPS: intervention_aware_forecasting, predicted_vs_realized
- [medium] Can Agent Memory Systems Track Evolving State? (StateMemBench / StateMem) | arXiv 2608.19652 | https://arxiv.org/abs/2608.19652 | lanes: benchmarks | citation check: arXiv id+title verified in corpus
  WHAT: 234 multi-session scenarios in which "facts, constraints, and decisions are revised". Closed-pool grading checks whether an answer reflects the current state or a superseded one. Scenarios are symbolic event programs replayed deterministically into ground truth (per a sibling extract). A state-first wrapper lifts current-state accuracy by 32-67 points. A "length- and cost-matched control attributes +15 to +32 of those points to state structure".
  WHY: Its construction (an event program replayed deterministically to ground truth, with current-versus-superseded grading) matches the project's. Its strongest finding favours explicit current-state structure, not temporal navigation, and that is the baseline the project must beat.
  CAPS: immutable_historical_observations, explicit_current_belief_state, cross_time_state_querying
- [medium] MEMTRACK: Evaluating Long-Term Memory and State Tracking in Multi-Platform Dynamic Agent Environments | arXiv 2510.01353 | https://arxiv.org/abs/2510.01353 | lanes: benchmarks | citation check: arXiv id+title verified in corpus
  WHAT: Asynchronous events are injected into mock Slack, Linear and Git servers as "a chronologically platform-interleaved timeline, with noisy, conflicting, cross-referring information". "Questions are introduced strictly sequentially to remove the possibility of preemptive solution planning." GPT-5 reaches about 60% correctness, and the Mem0 and Zep backends do not improve on it (per the digest).
  WHY: It is the closest existing software-organisation substrate (tickets, chat and Git on one timeline with conflicts) to the project's world. It is QA-scored, with no decision reopening or remediation. The null result for memory backends warns that memory architecture may not be the binding constraint.
  CAPS: immutable_historical_observations, explicit_current_belief_state, cross_time_state_querying
- [medium] EvoCode-Bench: Evaluating Coding Agents in Multi-Turn Iterative Interactions | arXiv 2605.24110 | https://arxiv.org/abs/2605.24110 | lanes: benchmarks | citation check: arXiv id+title verified in corpus
  WHAT: 26 stateful coding tasks and 227 rounds. Each task "preserves the agent's workspace for 5-15 rounds" and "uses cumulative executable tests to check new requirements and still-active prior ones". Multi-turn scores are 22-40 points below single-round scores, and stronger agents "expose specification-tracking and regression failures".
  WHY: It provides a ready executable remediation scorer for requirement changes in a persistent codebase (the project's event class B). It does not test unprompted reopening of earlier decisions, so the project could reuse its scoring rather than claim novelty there.
  CAPS: historical_policy_objective_state, explicit_current_belief_state
- [medium] Hindsight Bias in Clinical Temporal Reasoning: How Future Data Exposure Affects Large Language Model Judgment | arXiv 2609.13454 | https://arxiv.org/abs/2609.13454 | lanes: benchmarks,epistemic-cutoff | citation check: arXiv id+title verified in corpus
  WHAT: A paired benchmark of 171 case reports. Each question is "tied to a clinically meaningful cutoff and paired with a prospective reference answer and an outcome-consistent hindsight trap". Models answer from a timeline truncated at the cutoff or from the complete timeline. Metrics are Acc, hindsight trap rate, answer instability rate and hindsight bias rate. "Temporal masking reduces bias without lowering accuracy."
  WHY: It is a ready, published design for the project's 'historical-state fidelity' metric (what was known then versus now), with a hindsight-trap scorer. Adversarial point: simple temporal masking already removes the bias, so a strict epistemic cutoff needs no special architecture. Related: ChronoScope (2604.23051), where models drift 'toward present-day assumptions'.
  CAPS: historical_epistemic_state, cross_time_state_querying, predicted_vs_realized
- [medium] DreamBench-SWE: A Multi-Session Memory-Hygiene Benchmark for Software Agents | arXiv 2608.20664 | https://arxiv.org/abs/2608.20664 | lanes: benchmarks | citation check: arXiv id+title verified in corpus
  WHAT: Later software tasks depend on "non-inferable evidence from earlier sessions" and are "scored by executable hidden oracles". A preregistered successor audit was "frozen before successor outcome inspection". Pass counts: no memory 21/180, deterministic verbatim event memory 82/180, typed-plus-raw 83/180, Mem0 literal storage 97/180. It does "not establish ... superiority among memory-bearing conditions".
  WHY: It already uses the project's rules: frozen scenarios, hidden executable oracles and artifacts kept, in a multi-session software world. Its results are a direct caution for the comparative hypothesis: verbatim event memory is about as good as structured memory, and differences between memory systems are not significant.
  CAPS: immutable_historical_observations, explicit_current_belief_state
- [medium] Langfuse prompt management linked to traces, releases/versioning, and agentic (MCP/CLI) access | Langfuse docs (langfuse/langfuse-docs content/docs/prompt-management, observability) | https://github.com/langfuse/langfuse-docs/blob/main/content/docs/prompt-management/features/link-to-traces.mdx | lanes: identity-drift | citation check: non-arXiv
  WHAT: Prompt versions and labels are linked to generations in traces, with per-version metrics. A 'release' (git hash/semver) and a per-observation 'version' attribute are recorded. Agents can query observations and 'Retrieve a prompt and compare its latest versions' through an MCP server, CLI or skill.
  WHY: Shows that even agent-side access to 'which prompt/release governed past action X, and how it differs from the current one' is already possible through tooling. The residual novelty is only in agents using this access to reopen decisions themselves.
  CAPS: historical_policy_objective_state, immutable_historical_observations, cross_time_state_querying
- [medium] LangSmith Agent Server assistant versioning and Context Hub commits | LangSmith docs (langchain-ai/docs src/langsmith/assistants.mdx, context-engineering-concepts.mdx, context-hub-webhooks.mdx) | https://github.com/langchain-ai/docs/blob/main/src/langsmith/assistants.mdx | lanes: identity-drift | citation check: non-arXiv
  WHAT: Assistants package prompts, LLM selection and tools as configurations; 'Each update creates a new version', 'All versions remain available for reference and rollback'. The Context Hub stores agent and skill repos as immutable commits with parent_commit_hash and files_changed, so you can 'See exactly what changed between two versions of an agent'. Prompt commits support diff.
  WHY: Versioned agent identity and objective configuration with lineage and diffs is a shipping product feature, alongside the LangGraph time-travel features that are analysed separately.
  CAPS: historical_policy_objective_state, branch_provenance, cross_time_state_querying
- [medium] Property-Level Reconstructability of Agent Decisions: An Anchor-Level Pilot Across Vendor SDK Adapter Regimes | arXiv 2605.12078 | https://arxiv.org/abs/2605.12078 | lanes: identity-drift | citation check: arXiv id+title verified in corpus
  WHAT: Applies a Decision Trace Reconstructor to pinned trace examples from six vendor SDK regimes (cloud-agent, observability, tool-use, telemetry, protocol). Classifies each Decision Event Schema property ('what the agent did, on whose authority, against which policy, and from what reasoning') as fillable, partially fillable, unfillable or opaque. Strict governance completeness ranges from 42.9% to 85.7%; the reasoning trace is the regime-independent gap.
  WHY: This is the most direct empirical answer to the lane question. Existing traces only partly reconstruct which policy governed a decision, so a narrow gap remains. The framing ('against which policy') is already established.
  CAPS: historical_policy_objective_state
- [medium] Technical Report: Evaluating Goal Drift in Language Model Agents | arXiv 2505.02709 | https://arxiv.org/abs/2505.02709 | lanes: identity-drift | citation check: arXiv id+title verified in corpus
  WHAT: Stock-trading simulation in which the agent gets a goal via system prompt, then faces competing pressures. Includes a goal-switching condition (an instrumental-goal phase, then the system goal at a $5B AUM threshold). Measures GD_actions and GD_inaction, the latter being failure to divest positions taken earlier. Drift correlates with in-context pattern-matching as context grows.
  WHY: Already scores whether an agent remediates earlier decisions (divests) after the governing objective changes. That is close to the benchmark's 'later event changes significance of earlier decision' test, and has follow-ups (Inherited Goal Drift 2603.03258, Asymmetric Goal Drift 2603.03456).
  CAPS: historical_policy_objective_state
- [medium] Autogenesis: A Self-Evolving Agent Protocol | arXiv 2604.15034 | https://arxiv.org/abs/2604.15034 | lanes: identity-drift | citation check: arXiv id+title verified in corpus
  WHAT: Models prompts, agents, tools, environments and memory as protocol-registered resources with explicit state, lifecycle and versioned interfaces. A self-evolution layer proposes, assesses and commits improvements 'with auditable lineage and rollback'.
  WHY: Versioned identity and policy components with lineage are a protocol-level primitive in self-evolving agent work. Related: ANNEAL 2605.16309 (governed patches with full provenance and deterministic rollback) and EvoUndo 2608.28363.
  CAPS: historical_policy_objective_state, execution_checkpoints, branch_provenance
- [medium] Darwin Godel Machine: Open-Ended Evolution of Self-Improving Agents | arXiv 2505.22954 | https://arxiv.org/abs/2505.22954 | lanes: identity-drift | citation check: arXiv id+title verified in corpus
  WHAT: Self-modifying coding agent that keeps an archive of generated agents and grows it by sampling any archived agent and creating a new version, forming 'a growing tree of diverse, high-quality agents'. Each change is validated on benchmarks.
  WHY: 'Never overwrite, fork' is already the organising principle for the evolution of an agent's own policy and code, with branching from historical selves. Huxley-, Mendel- and Red-Queen-Gödel machines extend it.
  CAPS: historical_policy_objective_state, fork_from_historical_state, branch_provenance, multiple_prospective_branches
- [medium] Layered Mutability: Continuity and Governance in Persistent Self-Modifying Agents | arXiv 2604.14717 | https://arxiv.org/abs/2604.14717 | lanes: identity-drift | citation check: arXiv id+title verified in corpus
  WHAT: Framework of five mutable layers (pretraining, alignment, self-narrative, memory, weights) with drift, governance-load and hysteresis quantities. A ratchet experiment shows that reverting an agent's self-description after memory accumulation does not restore baseline behaviour (identity hysteresis ratio 0.68). Cites work on 'temporal identity in language-model agents'.
  WHY: Frames identity change over time and its weak reversibility as a governance problem. This conceptually preempts the 'track identity changes' theme, and suggests restoring an old self-description does not restore the old self.
  CAPS: historical_policy_objective_state
- [medium] AI-Assisted Engineering Should Track the Epistemic Status and Temporal Validity of Architectural Decisions (First Principles Framework) | arXiv 2601.21116 | https://arxiv.org/abs/2601.21116 | lanes: identity-drift | citation check: arXiv id+title verified in corpus
  WHAT: Proposes epistemic layers (conjecture vs validated), conservative assurance aggregation, and automated evidence-decay tracking that surfaces stale assumptions behind decisions. A retrospective audit found 20-25% of architectural decisions had stale evidence within two months.
  WHY: Proposes resurfacing earlier decisions when their basis expires, which overlaps the benchmark's 'notice that an earlier decision's standing changed and reopen it'. AssumptionMiner 2607.22898 is covered by the benchmark lane.
  CAPS: explicit_current_belief_state, uncertainty_representation, cross_time_state_querying
- [medium] Temporal Misgrounding in Legal RAG: A Versioned-Corpus Benchmark for French Tax Law (FiscalQA Pro) | arXiv 2608.09393 | https://arxiv.org/abs/2608.09393 | lanes: identity-drift | citation check: arXiv id+title verified in corpus
  WHAT: A versioned corpus of 32,436 article-versions (1938-2031), scored by which rule version applied at the question's date. Static RAG retrieves the date-applicable version 0% of the time; a retriever over a multi-version index reaches 98.3% strict accuracy.
  WHY: 'Which rule or policy governed at time t' is a solved retrieval problem once versions are indexed. This is a strong-baseline warning: an as-of policy lookup does not need a new temporal-agency architecture.
  CAPS: historical_world_state, historical_policy_objective_state, cross_time_state_querying
- [medium] ContextEcho: A Benchmark for Persona Drift in Long Agentic-Coding Sessions | arXiv 2605.24279 | https://arxiv.org/abs/2605.24279 | lanes: identity-drift | citation check: arXiv id+title verified in corpus
  WHAT: Measures persona and identity drift across Claude Code sessions of 3,746-9,716 turns over 23 models. Uses a 'snapshot-then-probe protocol that forks conversation state without perturbing the main session'. Finds compaction does not reset drift and a single-shot anchor restores it.
  WHY: Already forks an agent's historical state to interrogate its identity at a point in time without contaminating the live branch. This is a concrete instance of 'question past versions of the self' for identity drift.
  CAPS: execution_checkpoints, fork_from_historical_state, historical_policy_objective_state
- [medium] As-Of Information-Set Pinning (agent design pattern) | agentpatternscatalog/patterns (GitHub pattern catalog) | https://github.com/agentpatternscatalog/patterns/blob/main/patterns/as-of-information-set-pinning.md | lanes: epistemic-cutoff | citation check: non-arXiv
  WHAT: A codified agent pattern: fix one as-of timestamp per dated decision. Every read (model snapshot, corpus/index version, reference-data vintage, table version) resolves to an immutable version stored as a pin manifest. Re-execution replays the manifest, and an unresolvable version fails rather than falling back to live data. It lists failure modes: model alias rotation, re-crawled index, retention expiry, silent fallback, pinning data but not the model.
  WHY: Practice-level prior art for reconstructing a past decision with its exact information set, including the model weights. It already states 'Lookahead leaks through the weights as well as the data' and contrasts itself with replay/time-travel, which 'still resolves live tools against today's data'.
  CAPS: immutable_historical_observations, historical_world_state, historical_policy_objective_state, replay, cross_time_state_querying
- [medium] Reconcile Once, Write Anytime: A Trust-Tiered Librarian and a Multi-Agent Writer for Drift-Free, Point-in-Time Research | arXiv 2608.12984 | https://arxiv.org/pdf/2608.12984 | lanes: epistemic-cutoff | citation check: arXiv id+title verified in corpus
  WHAT: A deterministic librarian ingests timestamped sources into evidence cards, a metric ledger and a claim graph. A multi-agent writer composes reports 'at any knowledge cutoff T, reading only evidence with as_of <= T (no look-ahead)'. Red-team refutations propagate back and self-correct later runs. Replay shows zero look-ahead violations across seven cutoffs.
  WHY: An LLM agent system with an enforced as-of read discipline, a maintained claim graph and a replay audit for look-ahead violations. Refutations propagating to later runs come close to 'reopen'. It writes reports and does not remediate decisions.
  CAPS: immutable_historical_observations, historical_epistemic_state, explicit_current_belief_state, replay, cross_time_state_querying
- [medium] Simulated Ignorance Fails: A Systematic Study of LLM Behaviors on Forecasting Problems Before Model Knowledge Cutoff (with: Can Prompts Rewind Time for LLMs? arXiv 2510.02340; Can LLMs Be Constrained to the Past? arXiv 2606.05804) | arXiv 2601.13717 | https://arxiv.org/pdf/2601.13717 | lanes: epistemic-cutoff | citation check: arXiv id+title verified in corpus
  WHAT: Tests whether prompting models to suppress post-cutoff knowledge (simulated ignorance) approximates true ignorance, on 477 questions and 9 models. Cutoff instructions leave a 52% performance gap, CoT does not suppress prior knowledge, and reasoning models are worse. 2510.02340 finds prompted cutoffs work for directly queried facts but fail for causally related knowledge. 2606.05804's recall-based prompting narrows but does not close the gap.
  WHY: Undermining result: a 'past self' made by instructing the current model to forget is known to leak, especially through causally downstream knowledge. A naive LLM 'past self' cannot carry a strict-cutoff claim.
  CAPS: historical_epistemic_state
- [medium] All Leaks Count, Some Count More: Interpretable Temporal Contamination Detection in LLM Backtesting (TimeSPEC); with Temporal Leakage in LLM Backtesting: Measurement, Validation, and Adjusted Scores (arXiv 2608.02985) | arXiv 2602.17234 | https://arxiv.org/pdf/2602.17234 | lanes: epistemic-cutoff | citation check: arXiv id+title verified in corpus
  WHAT: Decomposes model rationales into atomic claims, classifies their temporal verifiability and computes a Shapley-weighted decision-critical leakage rate. TimeSPEC interleaves generation with claim verification and regeneration, so that 'every supporting claim can be traced to sources available before the cutoff date'. The follow-up 2608.02985 proves that passive pre/post-cutoff backtests cannot separate leakage from recency or skill, and that a known cutoff or a matched clean control is required.
  WHY: Claim-level provenance to pre-cutoff sources is a concrete mechanism for reasoning under a strict epistemic cutoff. The impossibility result implies the project's no-hindsight claim needs a clean control arm, not a before/after comparison.
  CAPS: historical_epistemic_state, predicted_vs_realized
- [medium] Look-Ahead-Freedom as Temporal Non-Interference: A Verifiable Correctness Property for Backtesting and Agentic Trading Pipelines | arXiv 2607.04958 (cs.CR) | https://arxiv.org/abs/2607.04958 | lanes: epistemic-cutoff | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: Identifies look-ahead-freedom with temporal non-interference over a time-indexed information lattice. It gives a pipeline calculus separating a datum's availability time from its reference time, proves undecidability when availability is value-dependent, and gives a linear-time sound type-and-effect checker for the value-independent fragment (point-in-time and vintage reads, agentic retrieval).
  WHY: 'Strict epistemic cutoff' already has a formal definition (non-interference with bitemporal availability vs reference time) and a static checker that covers agentic retrieval. A third-party review (pitllm) flags an error in the halting reduction but keeps the decidable checker.
  CAPS: historical_epistemic_state, cross_time_state_querying
- [medium] Temporal Leakage in Search-Engine Date-Filtered Web Retrieval: A Case Study from Retrospective Forecasting | arXiv 2602.00758 | https://arxiv.org/pdf/2602.00758 | lanes: epistemic-cutoff | citation check: arXiv id+title verified in corpus
  WHAT: Audits Google Search's before: filter. 71% of questions return at least one page with strong post-cutoff leakage, and for 41% a page directly reveals the answer. Forecast Brier improves from 0.242 to 0.108 with leaky documents. Mechanisms: updated articles, related-content modules, bad timestamps, absence signals. Recommends frozen time-stamped snapshots.
  WHY: Documents failure modes of 'knowledge cutoff via retrieval restricted to a date'. Any strong as-of-filtered RAG baseline faces the same failure modes unless its store is append-only and bitemporal. It sets the bar for what a 'strict cutoff' must guarantee.
  CAPS: historical_world_state
- [medium] Aborted but Not Forgotten: KV-Cache Retention Breaks Rollback Consistency in Language Agents | arXiv 2608.15939 | https://arxiv.org/pdf/2608.15939 | lanes: epistemic-cutoff | citation check: arXiv id+title verified in corpus
  WHAT: Shows that rolling back an agent by editing the transcript is unsound when the serving session retains KV state. Retained KV alone flips a protected effect in 25/63 audited cells across 7 open-weight families, including under LangGraph time-travel. It defines 'rollback consistency' and fixes it with transaction-local cache restoration.
  WHY: A known failure mode for reconstructing a past self or branch: hindsight can persist below the application layer, so checkpoint- or transcript-level time travel does not guarantee a clean epistemic cutoff.
  CAPS: execution_checkpoints, fork_from_historical_state, historical_epistemic_state
- [low] Claude Code checkpoints and /rewind | Anthropic product feature (documented in third-party guides) | https://theaiarchitects.com/blog/claude-code-checkpoints | lanes: exec-state | citation check: non-arXiv
  WHAT: Creates a checkpoint after every prompt, capturing file edits made through Claude's edit tools. The user can restore code and conversation, conversation only, or code only, or 'summarize from here'. Bash-made changes are not restored, and branches are not kept.
  WHY: It is the productized coding-agent baseline for rewinding to a past conversation and code state, and it is relevant because the project's world is a software world. It is user-driven and message-level only. It shows the gap (bash/external effects are not restored) that systems like Crab and Planarian address.
  CAPS: execution_checkpoints, replay, historical_epistemic_state
- [low] PABU: Progress-Aware Belief Update for Efficient LLM Agents | arXiv 2602.09138 | https://arxiv.org/abs/2602.09138 | lanes: belief-state | citation check: arXiv id+title verified in corpus
  WHAT: A belief-state framework that represents agent state by explicitly modeling task progress and selectively keeping past actions and observations. At each step the agent predicts relative progress and decides whether to store the new interaction. It reaches 81.0% completion across 8 AgentGym environments (+23.9% over full-history SoTA) and averages 9.5 steps (-26.9%).
  WHY: Here 'belief state' means compressed, filtered history for efficiency. It neither tracks assumptions nor revises past decisions, so overlap with the temporal-agency thesis is small. It does show a selective-retention baseline beating full-history conditioning, which matters for how strong the project's RAG baseline needs to be.
  CAPS: explicit_current_belief_state
- [low] W3C PROV Data Model (via the prov Python reference implementation) | W3C Recommendation PROV-DM (2013); GitHub trungdong/prov | https://github.com/trungdong/prov | lanes: temporal-memory | citation check: non-arXiv
  WHAT: The README says: "A Python implementation of the [W3C PROV Data Model]" with "In-memory classes for every PROV-DM record type". The source implements wasRevisionOf, wasInvalidatedBy (PROV_INVALIDATION), derivation, attribution and bundles (provenance of provenance).
  WHY: Branch and revision provenance (parent, derivation, invalidating activity, responsible agent) already has a standard vocabulary. A bespoke provenance schema would need to justify itself against PROV. This weakens 'provenance' as a novelty component.
  CAPS: branch_provenance
- [low] kaeru (with Talamus): bitemporal agent-memory tools with as-of reads over MCP | GitHub LamantinAI/kaeru; GitHub ampres-ai/talamus | https://github.com/LamantinAI/kaeru | lanes: temporal-memory | citation check: non-arXiv
  WHAT: kaeru: "Every node and edge is **bi-temporal** — the substrate stores assertion / retraction history natively, so time-travel queries are out of the box and conflict resolution is non-destructive (the old version is invalidated, not deleted)." Also "`at` reads a node in full as it is now or as-of any past moment", and "every mutation writes an audit node, so changes to memory themselves become reasoning surface for the agent." Talamus (https://github.com/ampres-ai/talamus): "notes have version history, facts have valid-time windows, and `talamus ask --as-of 2026-01` answers from the brain as it was."
  WHY: As-of memory reads for coding agents are a commodity feature in 2026. kaeru also exposes the memory's own mutation history to the agent for reasoning. Both are pre-1.0 and unevaluated, so they show existence rather than effectiveness.
  CAPS: immutable_historical_observations, historical_world_state, historical_epistemic_state, branch_provenance, cross_time_state_querying
- [low] Reasoning with Language Model is Planning with World Model (RAP) | arXiv 2305.14992 (EMNLP 2023) | https://arxiv.org/abs/2305.14992 | lanes: counterfactual-worldmodel | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: Repurposes the LLM 'as both a world model and a reasoning agent' with MCTS, to explore 'alternative reasoning paths, anticipating future states and rewards'.
  WHY: It established the computational abstraction 'LLM as world model + search over imagined branches' that most 2025-2026 world-model agents build on.
  CAPS: future_state_rollout, multiple_prospective_branches, counterfactual_action_branches
- [low] Language Agent Tree Search Unifies Reasoning Acting and Planning in Language Models (LATS) | arXiv 2310.04406, ICML 2024 | https://arxiv.org/abs/2310.04406 | lanes: counterfactual-worldmodel | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: MCTS over agent trajectories with environment feedback, LM value estimates and self-reflection on failed trajectories. It samples multiple trajectories ('--iterations: maximum number of trajectories to sample') from earlier tree nodes.
  WHY: It is the canonical evidence that branching from earlier states and learning from failed branches is standard for LLM agents, including in LangGraph. Its tree is per task and not a lifelong temporal store.
  CAPS: fork_from_historical_state, counterfactual_action_branches, branch_provenance, multiple_prospective_branches
- [low] Dyna-Think: Synergizing Reasoning, Acting, and World Model Simulation in AI Agents | arXiv 2506.00320 | https://arxiv.org/abs/2506.00320 | lanes: counterfactual-worldmodel | citation check: arXiv id+title verified in corpus
  WHAT: A Dyna-style thinking framework that 'integrates planning with an internal world model with reasoning and acting'. DIT distills R1 thinking focused on world-model simulation of the proposed action. DDT first trains world modelling (state prediction, critique generation), then the policy. Evaluated on OSWorld.
  WHY: Dyna-style simulate-then-act inside the agent's own reasoning is now trained into models. This weakens any claim that future-state simulation is a distinct agent capability.
  CAPS: future_state_rollout, counterfactual_action_branches
- [low] Scaled language world models for agents: WebEvolver (2504.21024), WebWorld (2602.14721), Qwen-AgentWorld (2606.24597) | arXiv 2504.21024 / 2602.14721 / 2606.24597 | https://arxiv.org/abs/2606.24597 | lanes: counterfactual-worldmodel | citation check: arXiv id in corpus, title differs: WebEvolver: Enhancing Web Agent Self-Improvement with Coevolving World Model
  WHAT: WebEvolver: a co-evolving world model acting 'as a virtual web server' for training data and 'as an imagination engine during inference, enabling look-ahead simulation'. WebWorld: a world model trained on more than 1M real web interactions. Qwen-AgentWorld: 'a native language world model that simulates agentic environments ... across seven unified domains: MCP, Search, Terminal, SWE, Android, Web, and OS'.
  WHY: Learned dynamics models for tool, terminal, SWE and web agents are now off-the-shelf, at up to 35B MoE open weights. Future-state rollout for a software-world benchmark is therefore a commodity component that a baseline can also use.
  CAPS: future_state_rollout, multiple_prospective_branches
- [low] Explicit rollback/backtracking for web and GUI agents: WebRollback (2504.11788), WebCoT (2505.20013), GA-Rollback (2503.02519), WebOperator (2512.12692), BEAP-Agent (2601.21352) | arXiv 2504.11788 (EACL 2026 oral per list) et al. | https://arxiv.org/abs/2504.11788 | lanes: counterfactual-worldmodel | citation check: arXiv id in corpus, title differs: Enhancing Web Agents with Explicit Rollback Mechanisms
  WHAT: Agents 'revert back to a previous state in its navigation trajectory' (WebRollback). WebCoT distils 'reflection & lookahead, branching, and rollback' into CoT. GA-Rollback has an assistant trigger rollback on incorrect actions. WebOperator does 'verified backtracking before replaying prior paths'. BEAP-Agent supports 'state rollback and task updates'.
  WHY: Reverting to and replaying from earlier states is routine. However, rollback discards the abandoned branch, which is the opposite of 'never overwrite time, fork it'. This contrast is where the project's preservation claim could still differ.
  CAPS: fork_from_historical_state, replay, execution_checkpoints
- [low] Tree-structured rollouts in agentic RL: Tree-GRPO (2509.21240), ARPO (2507.19849), Agent Q (2408.07199), ANCHOR (2602.07153) | Tree-GRPO ICLR 2026; ARPO arXiv 2507.19849; Agent Q arXiv 2408.07199; ANCHOR arXiv 2602.07153 | https://arxiv.org/abs/2509.21240 | lanes: counterfactual-worldmodel | citation check: arXiv id in corpus, title differs: Agentic Reinforced Policy Optimization
  WHAT: Branches rollouts from intermediate agent steps instead of independent chains. Tree-GRPO uses 'tree-search rollout strategy ... Tree-based process supervision signal'. Agent Q generates DPO pairs from MCTS siblings. ANCHOR identifies 'branch points' and generates 'verified alternative task continuations'.
  WHY: Branching from shared historical prefixes and learning from sibling comparisons is mainstream in agent RL and data synthesis. The branches are consumed by gradient updates, not kept as addressable records.
  CAPS: fork_from_historical_state, counterfactual_action_branches, branch_provenance, multiple_prospective_branches
- [low] Large Language Models as Theory of Mind Aware Generative Agents with Counterfactual Reflection (ToM-agent) | arXiv 2501.15355 | https://arxiv.org/abs/2501.15355 | lanes: counterfactual-worldmodel | citation check: arXiv id+title verified in corpus
  WHAT: Keeps the counterpart's inferred beliefs, desires and intentions with separate confidence levels. A 'counterfactual intervention method ... reflects on the gap between the predicted responses of counterparts and their real utterances'.
  WHY: It combines explicit beliefs with confidence and predicted-vs-actual reflection in one agent loop, a pattern that overlaps the project's belief-state plus forecast-review components.
  CAPS: explicit_current_belief_state, uncertainty_representation, predicted_vs_realized
- [low] Pre-execution consequence prediction for agent safety: SeerGuard (2607.15550), MirrorGuard (2601.12822) | arXiv 2607.15550 / 2601.12822 | https://arxiv.org/abs/2607.15550 | lanes: counterfactual-worldmodel | citation check: arXiv id in corpus, title differs: SeerGuard: A Safety Framework for Mobile GUI Agents via World Model Prediction
  WHAT: SeerGuard's 'safety-augmented world model jointly predicts likely next states and action risk so the agent can reject harmful actions before execution'. MirrorGuard trains on high-risk trajectories synthesised in a text simulator and corrects insecure reasoning before acting.
  WHY: Feared-future-driven intervention is now applied to safety. These systems avert predicted harms but never record the averted forecast as 'prevented, not wrong'. The project's prevented-futures claim survives here only as a bookkeeping and scoring difference.
  CAPS: future_state_rollout, uncertainty_representation, counterfactual_action_branches
- [low] Simulating Life Paths with Digital Twins: AI-Generated Future Selves Influence Decision-Making and Expand Human Choice (with Future You 2405.12514 and 2512.06106) | arXiv 2512.05397 | https://arxiv.org/abs/2512.05397 | lanes: prospective-forecast | citation check: arXiv id+title verified in corpus
  WHAT: An RCT (N=192) with age-progressed, voice-cloned LLM avatars of participants 30 years in the future, each having 'lived through' alternative life paths for a pending binary decision. Single-sided avatars shifted choices toward the presented option. A system-generated third option increased adoption of that new alternative. The limitations section says: 'we assessed decision intentions rather than implemented behaviors'. Related studies: Future You 2024 (n=344; anxiety -0.68 vs +0.21 for control; future self-continuity up) and Future You multimodal (N=92; FSC, well-being and motivation up, with no difference between modalities).
  WHY: Interrogating simulated future selves is established for humans, but the measured effects are psychological or decision shifts driven by persuasion, not decision quality. No agent-side analogue was found. That leaves 'an agent interrogates its own simulated future self or policy' open, but also with no evidence of benefit.
  CAPS: future_state_rollout, multiple_prospective_branches
- [low] FutureX: An Advanced Live Benchmark for LLM Agents in Future Prediction (with ForecastBench 2409.19839, Prophet Arena 2510.17638) | arXiv 2508.11987 (ICLR 2026) | https://arxiv.org/abs/2508.11987 | lanes: prospective-forecast | citation check: arXiv id+title verified in corpus
  WHAT: A live daily benchmark where questions are collected before their events, 25 LLMs and agents predict, and answers are crawled after resolution, so the benchmark is contamination-free by construction. ForecastBench (ICLR 2025) is the probability and Brier counterpart with superforecaster baselines. Prophet Arena decomposes live forecasting into pipeline stages and adds market returns.
  WHY: This is the mature infrastructure for scoring agent predictions against realized outcomes. It is not agent self-calibration, but it means any 'predicted vs realized' claim in the project is evaluation plumbing that already exists, not a contribution.
  CAPS: predicted_vs_realized
- [low] Why Reasoning Fails to Plan: A Planning-Centric Analysis of Long-Horizon Decision Making in LLM Agents (FLARE) | arXiv 2601.22311 | https://arxiv.org/abs/2601.22311 | lanes: backward-optionality | citation check: arXiv id+title verified in corpus
  WHAT: Shows that step-wise reasoning yields 'early myopic commitments that are systematically amplified over time and difficult to recover from'. FLARE enforces 'explicit lookahead, value propagation, and limited commitment' so that 'downstream outcomes [can] influence early decisions'.
  WHY: It is empirical evidence that propagating value back from future outcomes and limiting commitment fixes early-commitment failures in LLM agents. This is the within-episode version of the project's claim.
  CAPS: future_state_rollout, backward_requirements
- [low] BAR: A Backward Reasoning based Agent for Complex Minecraft Tasks | arXiv 2505.14079 | https://arxiv.org/abs/2505.14079 | lanes: backward-optionality | citation check: arXiv id+title verified in corpus
  WHAT: An LLM agent that 'make[s] the planning starting from the terminal state', with recursive goal decomposition, state-consistency maintenance and stage memory. It outperforms forward planners on complex Minecraft tasks.
  WHY: It shows that LLM backward planning and goal regression from a desired terminal state is an existing technique. It does not cover feared futures, persistence across events, or option preservation.
  CAPS: backward_requirements
- [low] Asking for Help Enables Safety Guarantees Without Sacrificing Effectiveness | arXiv 2502.14043 | https://arxiv.org/abs/2502.14043 | lanes: backward-optionality | citation check: arXiv id+title verified in corpus
  WHAT: Drops the assumption 'that all errors are recoverable' and proves that any algorithm that avoids catastrophe by asking for help also achieves sublinear regret in any MDP, 'including MDPs with irreversible costs'.
  WHY: It is the formal basis for irreversibility-aware deferral with regret guarantees, the theoretical answer to 'how should an agent act given feared irreversible futures'.
  CAPS: uncertainty_representation, backward_requirements
- [low] Model-Based Soft Maximization of Suitable Metrics of Long-Term Human Power | arXiv 2508.00159 | https://arxiv.org/abs/2508.00159 | lanes: backward-optionality | citation check: arXiv id+title verified in corpus
  WHAT: Defines an agent objective of aggregate long-term human power (the 'ability to pursue diverse goals' over 'a wide variety of possible human goals'), computed 'by backward induction or approximating it via a form of multi-agent reinforcement learning from a given world model'.
  WHY: It is a recent agentic-AI objective that is explicitly option preservation computed backward from a distribution of futures. Option preservation as an agent objective is not new.
  CAPS: multiple_prospective_branches, backward_requirements, future_state_rollout
- [low] Revisiting the Predictability of Performative, Social Events | ICML 2025; arXiv 2503.11713 | https://arxiv.org/abs/2503.11713 | lanes: performative-prevented | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: Uses performative multicalibration (outcome indistinguishability) to show that performative social events can be predicted accurately. It also constructs a case where a predictor is performatively multicalibrated yet maximizes performative risk: 'accurate predictions can be entirely useless'.
  WHY: Agreement between forecast and outcome can be manufactured under performativity. This weakens 'compare predicted vs realized' as a learning signal for agents whose forecasts are acted on.
  CAPS: intervention_aware_forecasting, predicted_vs_realized
- [low] Evaluation of the US COVID-19 Scenario Modeling Hub for informing pandemic response under uncertainty (Howerton et al.) | Nature Communications 14:7260, doi 10.1038/s41467-023-42680-x | https://github.com/midas-network/covid19-scenario-hub_evaluation | lanes: performative-prevented | citation check: non-arXiv
  WHAT: Evaluates scenario-conditional epidemic projections. It first assesses 'scenario plausibility' by comparing realized vaccine uptake and other assumptions with the scenario specifications. It then scores projections (coverage, WIS) against null comparators, so projections conditional on scenarios that did not happen are not treated as failed forecasts.
  WHY: Public-health forecasting already distinguishes scenario projections from forecasts and scores conditional projections only where their conditions held. This is a large-scale institutional precedent for the project's principle.
  CAPS: intervention_aware_forecasting, multiple_prospective_branches, probability_over_futures, uncertainty_representation, predicted_vs_realized
- [low] SlopCodeBench: Benchmarking How Coding Agents Degrade Over Long-Horizon Iterative Tasks | arXiv 2603.24755 | https://arxiv.org/abs/2603.24755 | lanes: benchmarks | citation check: arXiv id+title verified in corpus
  WHAT: 20 problems and 93 checkpoints "in which agents repeatedly extend their own prior solutions under evolving specifications that force architectural decisions without prescribing internal structure". It tracks verbosity and structural erosion. No agent solves any problem end-to-end, and erosion rises in 80% of trajectories.
  WHY: It is the closest coding benchmark in which early architectural decisions meet later specification changes, which relates to ADRs. It scores code-quality decay, not noticing or reopening decisions. Related: SWE-CI (2603.03823), with 233-day and 71-commit evolution histories, and MaintainBench (2503.24260).
  CAPS: historical_policy_objective_state
- [low] LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory | arXiv 2410.10813 (ICLR 2025) | https://github.com/xiaowu0162/LongMemEval | lanes: benchmarks | citation check: arXiv id NOT in local corpus (unverified)
  WHAT: "500 high quality questions to test five core long-term memory abilities", including "Knowledge Updates", "Temporal Reasoning" and "Abstention", over a "timestamped chat history". Question types include knowledge-update and temporal-reasoning. Successor LongMemEval-V2 (2605.12493) adds "dynamic state tracking" and "premise awareness" for web agents.
  WHY: It is the foundational benchmark for knowledge updates and temporal reasoning in memory. All of it is prompted QA where the latest value wins, with no decisions, no unprompted noticing and no remediation. It establishes the baseline task family that the project's scenarios go beyond.
  CAPS: immutable_historical_observations, explicit_current_belief_state, cross_time_state_querying
- [low] MemoryAgentBench: Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions | arXiv 2507.05257 (ICLR 2026) | https://github.com/HUST-AI-HYZ/MemoryAgentBench | lanes: benchmarks | citation check: arXiv id+title verified in corpus
  WHAT: "Four Core Competencies for Evaluation: Accurate Retrieval (AR) Test-Time Learning (TTL) Long-Range Understanding (LRU) Conflict Resolution (CR)". The new datasets are EventQA and FactConsolidation. In the conflict-resolution task, "the task prompt tells it that a larger serial number is a newer fact" (methods/total_agent_memory.py).
  WHY: It shows that standard 'conflict resolution' benchmarking is prompted recency resolution where the latest value wins. That is far from reopening decisions whose premise was historically valid, which confirms the gap rather than closing it.
  CAPS: explicit_current_belief_state
- [low] Scaling Point-in-Time Language Models (with Time Machine GPT arXiv 2404.18543, ChronoGPT arXiv 2502.21206, DatedGPT 2603.11838, TiMoE 2508.08827, PALM 2609.30316) | arXiv 2607.11889 | https://arxiv.org/pdf/2607.11889 | lanes: epistemic-cutoff | citation check: arXiv id+title verified in corpus
  WHAT: Trains decoder-only models up to 4B parameters on 1T chronologically filtered FineWeb tokens, with monthly checkpoints 2013-2024. It narrows the gap to unconstrained open models. The family: TiMaGPT (2024, 'nonprognosticative' yearly GPT-2s), ChronoGPT (yearly 1999-2024), DatedGPT (yearly 1.3B), TiMoE (masks experts whose window ends after the query timestamp) and PALM (adds a period via a LoRA adapter on pre-decision-date text).
  WHY: The established structural answer to 'the model already knows the outcome': a past self needs weights that also stop at t. It is costly, lags frontier models, and post-training can leak (pitllm: 'A sequence can be clean at the first stage and leak at the second, and most of them are'). It is model-level, not agent state, so it is low threat to agent novelty but sets a hard limit on what a frozen frontier model can claim.
  CAPS: historical_epistemic_state, historical_policy_objective_state, cross_time_state_querying
- [low] Teaching Large Language Models When Not to Know: Learning Temporal Critique for Ex-Ante Reasoning (TCFT) | arXiv 2605.14636 | https://arxiv.org/pdf/2605.14636 | lanes: epistemic-cutoff | citation check: arXiv id+title verified in corpus
  WHAT: Shows that temporal leakage under prompted cutoffs depends on cutoff formulation and instruction placement. It argues 'ex-ante correctness is not an intrinsic property of an answer, but a relation between the answer and the cutoff', and trains a critic to identify post-cutoff leakage and judge temporal admissibility (leakage down 38-42 points on Qwen2.5 7B/14B).
  WHY: A trained cutoff-admissibility checker is a component the project might otherwise present as new (a 'no hindsight' verifier).
  CAPS: historical_epistemic_state
- [low] Agentic Time Machine as an Infrastructure for Future-Event Forecasting | arXiv 2606.21013 | https://arxiv.org/pdf/2606.21013 | lanes: epistemic-cutoff | citation check: arXiv id+title verified in corpus
  WHAT: An agent sandbox that 'approximately reconstructs the web state at any chosen past time by filtering post-cutoff content'. Offline scores under it correlate with live FutureX scores, and a planner-solver-aggregator forecaster is evaluated in it.
  WHY: External-world as-of reconstruction for agents is already infrastructure. It does not reconstruct the agent's own beliefs, policy or memory.
  CAPS: historical_world_state, replay


# Deep reads of top sweep works

## The Log is the Agent: Event-Sourced Reactive Graphs for Auditable, Forkable Agentic Systems (ActiveGraph) | arXiv 2605.21997 (Nakajima, 2026); code github.com/yoheinakajima/activegraph v1.12.0, Apache-2.0, PyPI 'activegraph' | https://arxiv.org/abs/2605.21997
SUMMARY: ActiveGraph is a production agent runtime: v1.12, Apache-2.0, pip-installable, with an arXiv paper. Its source of truth is an append-only event log, and its working graph of typed objects and relations is a deterministic projection of that log. Runtime.fork(at_event) copies the parent's log up to and including at_event into a new run_id and replays it. Lineage is stored as (parent_run_id, forked_at_event_id, label). The fork can be reconfigured, structurally diffed against the parent, and promoted back with a fail-closed three-way merge. Strict replay re-fires behaviors and detects divergence by prompt hash. LLM and tool caches mean a fork's shared prefix makes no new calls. Causal-chain walks go from an artifact back to its LLM call and then to the goal. It covers the retrospective and counterfactual half of 'never overwrite time, fork it' thoroughly. It has nothing prospective: no forecasts, no probabilities over futures, no backward requirements, and no prevented-forecast or predicted-vs-realized ledger.
MECHANISM: The mechanism has eight parts:
1. Event store (SQLite or Postgres): each event has id, type, payload, actor, caused_by and timestamp, and the graph is a projection of the events. Emit is commit-first; payloads are detached canonical copies.
2. Fork: SQLiteEventStore.fork_run copies rows with seq <= the cut into a new run and writes a lineage row. The fork's Graph is rebuilt by _replay_event. Unfired events are re-queued so behaviors fire after the fork point. The LLM, tool and embedding caches are pre-filled from the PARENT's full log (CONTRACT v0.6 #8).
3. Diff: compute_diff(parentGraph, forkGraph) splits non-lifecycle events into shared prefix, parent-only and fork-only, and lists objects and relations whose final states differ. It is structural only.
4. Promote: build_base_graph replays the parent up to the fork point. That base, the parent now and the fork now are compared three ways. Fork-only changes are applied under a promote.applied marker; changes on both sides fail closed.
5. Trials: run_forked_trial runs a candidate pack in a subprocess against a fork.
6. Compaction: a runtime.snapshot event plus an archive tier; nothing is deleted. An operator-side truncate_after does DELETE events.
7. Audit: llm.requested stores the full prompt (first attempt), and opt-in context.read events record which object ids each behavior read.
8. Policy and authority changes are logged as events (authority.ceiling_changed, pack.loaded with settings and prompt hashes, pack.settings_overridden, dev.override).
EVALUATION: Paper evaluation: not verified (arXiv blocked, WebSearch budget exhausted). The repo has an extensive test suite (tests/test_fork.py, test_replay.py, test_tool_replay.py, test_promote.py, test_compaction.py, among others) and deterministic quickstart snapshots. The quickstart's fork-and-diff example reports 61 divergent objects and 49 divergent relations, but that is a demo, not a benchmark. I found no task-level evaluation of whether forking or replay improves agent decisions.

I ran my own probe against the clone (scratchpad/lit/repos/ag_probe.py):
- A: a fork at evt_003 holds only objects created at or before that event, a strict prefix.
- B: promote.build_base_graph(g, e) works as state_at(e).
- C: compute_diff over two as-of graphs gives diff(t1,t2) within one run, but only through internal APIs.
- D: the runs table records parent_run_id, forked_at_event_id and label.
- E: with replay_tool_cache=True, a fork cut at goal.created (before any tool call) received the parent's POST-cutoff tool observation ('breach_disclosed', cache_hit=True). With caches off it read the live present world ('calm'). Neither is the world as of t.
- F: the fork inherited the parent's current Frame ('G-revised-later'), not the frame in force at the cutoff.
THREAT: HIGH for the retrospective and counterfactual half of the thesis.

1. The phrase 'never overwrite time, fork it' describes this shipped, tested, Apache-2.0 runtime with a paper. It provides:
   - an append-only log as the source of truth;
   - inclusive-cutoff forks with (parent_run_id, forked_at_event_id, label) lineage;
   - strict replay with divergence detection, and structural diff;
   - a fail-closed fork-test-promote loop for an agent to test a change against its own history ('Hypothesis testing on an agentic system, without losing the parent run');
   - retention-pinned provenance, and causal lineage from artifact to LLM call to goal.
   Capabilities 1, 2 and 5-9 are prior art, and most of 19 (as-of state) is reachable.
2. A competent baseline contestant could be built directly on it.

The residual space is narrower than the project currently claims:
- (a) A strict epistemic cutoff during re-execution. ActiveGraph deliberately pre-fills fork caches from the parent's FULL log, and my probe showed a fork receiving a post-cutoff tool observation. Uncached tools read the present world. So 'question your past self with no hindsight' is NOT provided, but the claim must be framed as cutoff-safe re-execution, not as 'reconstruct past state'.
- (b) Restoring the policy, objective and identity in force at t. Forks inherit the current frame, policy and behaviors, and there is no drift tracking.
- (c) The whole prospective side: imagined futures, probabilities, backward requirements, intervention-conditioned forecasts, prevented-forecast preservation, and a predicted-vs-realized ledger.
- (d) Semantic, not structural, detection that a later event changes the significance of an earlier decision. ActiveGraph says 'Semantic comparison is a behavior's job, not the runtime's'.
- (e) Any benchmark evidence that temporal navigation helps.

Without (c) and (d), the project's 'unified temporal abstraction' reduces to ActiveGraph plus a planner. A secondary threat: the sibling activegraph-packs repo already pairs predictions with outcomes under a log-ordered no-backfill guard (narrowly, for approval verdicts). That chips at the novelty of the 'predicted vs realized without hindsight' scaffolding, though not at forecasting world states.
UNVERIFIED: The full paper text and its evaluation section could not be read: arxiv.org is blocked, and this session's WebSearch budget (200 calls) was exhausted before this deep read. The paper claims rely on abstract extracts recorded by the earlier exec-state sweep, which may be lightly paraphrased. Also unread:
- whether the paper itself discusses epistemic cutoffs, hindsight leakage, or prospective use;
- the author list beyond 'Nakajima, 2026' as stated in the README;
- the Regimes follow-up paper (arXiv 2606.10241);
- docs.activegraph.ai and activegraph.ai (both blocked; the repo docs/ folder was used instead).
The activegraph-packs repo was only grep-inspected, and only for context. All runtime ratings come from reading the v1.12.0 source and docs, plus an executed probe.
RATINGS: 1:yes, 2:yes, 3:partial, 4:partial, 5:yes, 6:yes, 7:yes, 8:yes, 9:yes, 10:partial, 11:partial, 12:partial, 13:partial, 14:no, 15:no, 16:no, 17:no, 18:no, 19:partial, 20:partial

## Shepherd: Enabling Programmable Meta-Agents via Reversible Agentic Execution Traces (v1 title: A Runtime Substrate Empowering Meta-Agents with a Formalized Execution Trace) | arXiv 2605.10913 (cs.AI, 12 May 2026). Authors: Simon Yu, Derek Chong, Ananjan Nandi, Dilara Soylu, Jiuding Sun, Christopher D. Manning, Weiyan Shi (Northeastern University and Stanford University). | https://arxiv.org/abs/2605.10913
SUMMARY: Shepherd is a Python runtime for meta-agents, meaning agents that observe, intercept, fork, revert, modify and replay other agents. Every model call, tool call and file change is recorded as a typed effect. The blog describes the trace as "a commit graph where any past state is reachable by its hash". A scope fork copies the agent's process and context together with an OverlayFS filesystem layer. Measured costs: about 134 to 143 ms per fork regardless of image size (5x faster than docker commit), about 10 KB per fork, and about 95% KV-cache reuse when a byte-identical prefix is replayed. The deterministic core is said to be mechanized in Lean. Three meta-agents are demonstrated: (1) a live supervisor that coordinates parallel coding agents on CooperBench (pair pass rate 28.8% to 54.7%); (2) Counterfactual Replay Optimization (CRO), which forks a finished run at the first commit a workflow edit touches and replays only the suffix (beats GEPA and MetaHarness on 4 of 5 benchmarks at lower wall-clock); (3) Tree-GRPO, where a meta-agent picks fork turns in RL rollouts and K sibling continuations give per-step credit (Terminal-Bench 2.0: 34.2 to 39.4 with Qwen3.5-35B-A3B).
MECHANISM: Functional-programming framing: a Task is a typed function; an Effect is an algebraic effect that records the intent before the result, which leaves a gap where a supervisor can intercept; a Scope is a scoped handler with fork/merge/discard/materialize primitives; a Trace is a persistent, content-addressed data structure. The frozen substrate code states the invariant "state(t) = fold(apply_effect, effects[0:t], initial_state)" over an "immutable, append-only sequence of effects". Combinators built on these primitives include gate, speculate, retry and parallel ("Gate before escape, not reverse after"). Recorded effects include PromptSent (complete system and user prompts, model_id), LLMResponseReceived, AgentThinking, ToolCallStarted/Completed/Rejected, and file read/create/patch/delete. compare_streams() and explain_outcome_difference() diff two runs. The world layer is vcs-core, "provenance-native version control for executable worlds" built on bare Git (pygit2). It provides scopes as branches, `checkout REF --dest` to extract world state at a historical ref, and DiscardSnapshot/ScopeMerge records carrying parent_world_id, so discarded worlds are archived. In Tree-RL, a stronger LLM reads the finished transcript and its reward and returns {branch_turn, reason}; in the teacher variant it also returns an alternative bash command. K branches then resume from the exact token prefix and overlay at turn t*-1.
EVALUATION: The infrastructure evaluation is strong: fork and revert latency across a 138x range of image sizes, a zero-token observation-overhead check, and KV-cache reuse swept over fork depth and K. Each application has one benchmark study.
- CooperBench supervision: coop 28.8%, Sonnet supervisor 45.3%, Opus supervisor 54.7%, solo ceiling 57.2%.
- CRO against GEPA and MetaHarness on HoVer, MATH, IFBench, LiveCodeBench and TB-2, with GPT-5.4-mini as executor and GPT-5.4 as proposer.
- Tree-GRPO against flat GRPO at matched compute on TB-2 (avg@5 over 89 tasks, 5 seeds), for two models.

Caveats:
- The headline numbers changed between v1 ("up to 11 points", four benchmarks) and v3/blog (five benchmarks, +27.5% relative on LiveCodeBench, +12.8% on TB-2).
- The released live-intervention README says a 100-pair subset; the blog says 479 pairs.
- The README says the main results use prompt v6, which marks revert/redirect "DO NOT USE" and allows only informational steers, while the blog describes inject/handoff/discard.
- CRO's optimizer runner is not public.

None of the evaluations tests:
- epistemic cutoff or hindsight leakage;
- belief tracking;
- forecasting;
- remediation in an irreversible world with exogenous events.
THREAT: High for substrate claims, medium for the benchmark's behaviour claim.

Substrate claims. Shepherd is formalized and well-engineered prior art for capabilities 1, 2 and 5 to 9 together:
- append-only typed traces;
- world-state revert;
- checkpoints of process, context and filesystem;
- byte-identical prefix replay;
- forks with the original preserved;
- counterfactual branches;
- a provenance commit graph that archives discarded worlds.

So 'never overwrite time, fork it' and 'agents can navigate to past states' are not contributions.

Strict-cutoff questioning of a past self. A fork at turn t restores exactly the agent's context as of t, which is a no-hindsight past self. Shepherd also supports injecting notes into a worker, so a meta-agent can compose fork and inject to question a past self at a cutoff. The project's claim must therefore rest on:
- a structured, queryable belief state;
- as-of querying without resuming execution;
- evidence that the cutoff improves decisions.

Tree-RL meta-agent selector. This is the most direct overlap with the benchmark. It reads a finished trajectory and its outcome, picks 'the turn where a different choice would most plausibly change the outcome', records a reason and, in the teacher variant, an alternative action, then forks from that past turn. That is 'a later outcome changes the significance of an earlier decision, so reopen it', implemented and evaluated, although offline, for training credit assignment, by a separate stronger model, with the terminal reward as the only hindsight.

CRO. It identifies the first past step a policy edit affects and replays from there. That pre-empts 'a policy change reopens affected past decisions' as a mechanism.

Speculate-then-commit forks. These are an executed form of prospective lookahead, so any future-simulation claim needs a Shepherd-style executed-lookahead baseline wherever the environment can be sandboxed.

What survives:
- explicit belief, assumption and uncertainty state;
- all forecast machinery (probabilities, backward requirements, intervention-conditioned forecasts, prevented-forecast bookkeeping, predicted-versus-realized calibration);
- reasoning by the agent about its own history, rather than a separate meta-agent;
- the key setting: exogenous later events in a world that cannot be rewound, where escaped effects cannot be reverted ('ContainmentError: If effects after checkpoint were materialized'; 'Gate before escape, not reverse after'), so the agent must remediate in the present rather than revert and retry;
- evaluation of hindsight leakage and cutoff correctness.
UNVERIFIED: - **Paper body.** arxiv.org was blocked and the WebSearch budget was exhausted (200/200), so I could not read the arXiv PDF or HTML. Paper sections, the exact Lean theorem statements, and the differences between v1, v2 and v3 are known only through the v1 abstract, the homepage v3 abstract, the blog and the code.
- **Lean.** Neither public repo contains a .lean file. The kernel-v3-reference README says 'the Lean proof catches up' and 'proof-level semantic adequacy remains the job of the Lean development'. How much is mechanized is unverified.
- **Shipped library versus paper.** The public library (v0.3.1) does not ship the paper's meta-agent surface:
  - replay is 'not yet a shipped API';
  - oversee(...) task-as-value delegation is 'explicitly deferred';
  - the generated CLI reference has no revert, log or plugin commands, unlike the homepage 'Try it' commands;
  - the blog's PyPI link (0.0.1) is a placeholder 'with no public API'.
- **Paper code.** Fork, revert and replay as used in the paper live in the frozen snapshot inside shepherd-experiments. CRO's optimizer scripts live in a private '<anon-runner>' repo, and the dcx/poc-crank-v2 Code link is not publicly clonable, so CRO cannot be reproduced from public code.
- **Experiment details.** The live-intervention README says a 100-pair subset where the blog says 479 pairs. The README says the main results use prompt v6, which disables revert and redirect, while the blog describes inject, handoff and discard actions.
- **Truncated effects.** I inferred, but did not run code to confirm, whether the root-scope persisted JSONL keeps effects that restore() truncated from the in-memory stream.
RATINGS: 1:yes, 2:yes, 3:partial, 4:partial, 5:yes, 6:yes, 7:yes, 8:yes, 9:yes, 10:no, 11:no, 12:partial, 13:partial, 14:no, 15:no, 16:no, 17:no, 18:no, 19:partial, 20:partial

## DeepRewind: Predicting and Repairing Premature Commitments in Deep Research Agents | arXiv 2609.36344 (v1 2026-09-28); REALM@EMNLP 2026 workshop per README BibTeX (OpenReview LGVrhRguSJ, not fetched). Abaskohi, Dabiriaghdam, Wang, West, Carenini. Code: github.com/AmirAbaskohi/DeepRewind (MIT, HEAD 9282f0f) | https://arxiv.org/abs/2609.36344
SUMMARY: DeepRewind adds a control layer to LangChain's Open Deep Research. It records the agent's epistemic state as an append-only typed graph: Source, Evidence, Claim, Hypothesis, Assumption, Commitment, DraftFragment and PlanStep nodes, joined by supports, contradicts, depends_on, locks_in, used_in, derived_from, revises and invalidates edges. When the agent judges the evidence sufficient and is about to commit to an iteration's claim, an LLM world model predicts the one-step graph delta of that single commit action. Structural scores computed on a deep-copied, simulated post-commit snapshot then feed a binary commit/not-commit gate. The scores are κ (drop in entropy over competing hypotheses, including a lock-in term), λ (contradiction mass), γ (dependent-recovery cost) and TC (probe coverage). A blocked commit becomes a PlanStep marked "retain as contested", and the agent keeps researching. Each accepted commitment registers a trigger. After every iteration a monitor checks for new high-reliability contradicting Evidence that pushes the claim's belief below a threshold. If it finds one, a deterministic reduced repair contests the claim, retracts the commitment and its unique justifications, marks dependents stale, preserves independently supported nodes, and puts the topic back into the research queue. A switching experiment tests this directly: a seeded prior favours A, the agent commits, high-confidence contradiction of A and support for B is injected, and an LLM judge checks whether the answer recovers to B. The arms are base, shadow, gate, rollback and no-rollback. The abstract reports +3.6 pp insight recall and 59.1% fewer premature commitments than Open Deep Research on DRBench and LiveDRBench.
MECHANISM: The paper text was unreachable, so this is from the code. (1) epistemic_graph.py writes JSONL events, each with a timestamp: node, edge, contested, retraction, stale and rollback. Its docstring says "beliefs are never silently overwritten ... we add a revises/invalidates edge to a new node instead of mutating the old one". Alongside, it keeps an in-memory mirror whose status fields are mutated. (2) world_model.py prompts the LLM with "one candidate COMMIT action. Predict how the graph will change if the action is taken, and estimate the reversibility". Source and Evidence nodes are masked from prediction. (3) world_model_scoring.py computes belief β(c) as a logistic sum of ±weight × reliability over Evidence edges, hypothesis plausibility as a softmax, κ as the normalized entropy drop between the current snapshot and apply_commit_to_snapshot (which adds wm_commit_lockin_strength), λ, γ, IRR and TC. decide() returns not_commit if the claim is contested, or if IRR·(1−TC) exceeds τ. (4) world_model_monitor.consistency_violated counts only contradicts edges from Evidence nodes that are newer than the commit iteration and meet ρ*/w*, and requires β_now < β*. (5) world_model_rollback.reduced_repair/apply_repair retracts via append-only status events, with no restoration. deep_researcher.py then adds the claim's topic to pending_reopen_topics, which become seed topics for the next proposal iteration. (6) Organic contradiction detection is an LLM reconcile_epistemic_state call that compares new findings with ALL prior claims and hypotheses. It emits Claim→Claim edges. (7) experiments/hooks.py injects synthetic Evidence→Claim contradictions (reliability and weight 0.95), "Explicitly ... to the actual commitment claim so monitor/rollback can fire on that exact target".
EVALUATION: The headline numbers (59.1% fewer premature commitments, +3.6 pp insight recall on DRBench and LiveDRBench) come from the abstract only. The repo has no code for either metric, and its benchmark script targets Salesforce/LiveResearchBench and "performs no evaluation". experiments/analyze.py computes recovered_to_b, answer divergence across seeded initial conditions, a seeding-susceptibility flip fraction, and a "calibration" correlation between the LLM's κ/λ/γ and the structural κ/λ/γ. My executed probe used the repo's graph, scoring, monitor and rollback modules with default config. The organic path (new Claim contradicts and invalidates the committed Claim, as deep_researcher.py:1169 produces) left belief at 0.622 and the monitor fired 0 times. An Evidence→Claim contradiction from an unrated source (default reliability 0.5) gave belief 0.5 and 0 firings. The synthetic switch injection gave belief 0.401, 1 firing, and a repair plan that retracted cmt1 and hyp1 and reopened clm1. Grep confirms that the only Evidence-sourced contradicts edges come from experiments/hooks.py:76,197. In the released code, then, dependency-aware rollback fires only in the synthetic switching study, and organic gains would come from the gate, which means extra research iterations. Also, consolidated findings (deep_researcher.py:1426-1430) and the final-report used_in links (line 2044) are not filtered by retraction, so retracted findings still reach the report writer. The paper may differ from this code.
THREAT: HIGH for the benchmark behaviour and for the alternative explanation "dependency tracking suffices". LOW to MEDIUM for temporal navigation as such. DeepRewind publishes, with code and a controlled ablation (base, shadow, gate, rollback, no-rollback; seeded prior, commitment, injected contradiction, recovered-to-B), the behaviour the project benchmarks: a later observation invalidates an earlier commitment, and the agent retracts it, reopens it and remediates. Its mechanism is a typed justification and dependency graph with a consistency monitor. That is LLM-era truth maintenance in the Doyle 1979 TMS lineage, not addressable time. So "noticing that a later event changes the significance of an earlier decision requires temporal navigation" now has direct prior art that gets the behaviour without it. Its reversibility gate (IRR·(1−TC), 'continue exploring before committing') is also measured prior art for option-preserving actions derived from a feared lock-in future. Consequence for the project: it must add a DeepRewind-style dependency-graph contestant (decision records with depends_on edges, plus a retract/reopen monitor) beside checkpoint+RAG. Otherwise any temporal-contestant win is confounded with dependency tracking. The switching protocol and the shadow and no-rollback arms can be reused as benchmark design. What DeepRewind leaves open: past-state reconstruction with a strict epistemic cutoff; replay and forks; multiple or probabilistic futures; prevented-forecast accounting; prediction-vs-outcome comparison; tracking of identity and policy change; external side-effecting actions (it remediates only by re-research); and, most importantly, inferring WHICH earlier decision is affected when the link is implicit, indirect or far back. Its switching study wires the contradiction directly to the committed claim. Its organic detection is an exhaustive LLM comparison over all prior items within one short run. In the released code, organic contradictions never fire rollback (probe-verified), so long-horizon, no-hint detection and reopening precision/recall over many decisions remain open.
UNVERIFIED: I could not read the full paper. arxiv.org and openreview.net are blocked, and the WebSearch budget was exhausted. Unverified as a result: the definitions of 'premature commitment' and 'insight recall'; the 59.1% and +3.6 pp figures; the models, question counts, seeds and whether budgets were matched across arms; the DRBench/LiveDRBench protocol; and whether the paper's rollback path differs from the released code. In the released code, organic contradictions do not fire the monitor and retracted findings are not filtered from the report input. Also unverified: the OpenReview page and workshop acceptance (from the README BibTeX only), and whether the abstract's 'LiveDRBench' is the same benchmark as the repo's Salesforce/LiveResearchBench script, which performs no evaluation.
RATINGS: 1:yes, 2:no, 3:partial, 4:no, 5:no, 6:no, 7:no, 8:partial, 9:partial, 10:yes, 11:yes, 12:partial, 13:no, 14:no, 15:partial, 16:partial, 17:partial, 18:no, 19:partial, 20:no

## FutureSim: Replaying World Events to Evaluate Adaptive Agents | arXiv 2605.15188 (2026-05-14); code at OpenForecaster/futuresim @908322f | https://arxiv.org/abs/2605.15188
SUMMARY: FutureSim is a forecasting benchmark and harness that replays real news from Jan to Mar 2026 in chronological order. Questions resolve over simulated days. The environment shows only articles dated on or before the simulated date: search is date-capped, article files are staged by date, ground truth is hidden, and the agent runs in a network-isolated sandbox. Agents submit probability distributions over at most 5 outcomes and can revise them every day. Scoring is a time-weighted Brier skill score over an append-only per-agent PredictionHistory that supports an as-of query (get_prediction_as_of). Each day the agent receives "Your prediction distribution: {...} | Truth: ... Brier ..." feedback, with the instruction "use this to learn from mistakes and improve calibration". In the active_memory2 mode it then runs a lesson-extraction step ("why you were right or wrong"), and its memory is snapshotted read-only per day. The harness also supports resume, restart-from-day forks into new directories with restart_source/restart_from_day recorded, and bootstrapping from a fixed Day-0 state. That bootstrap is used for no-memory vs memory comparisons and for good vs bad warmup comparisons. Abstract: "the best agent's accuracy being 25%, and many having worse Brier skill score than making no prediction at all."
MECHANISM: Code read at @908322f:
(1) Date gating. agents/search_tools/handler.py caps search at allowed_max_date = current_date - search_cutoff_days. lancedb/store.py filters "date <= timestamp ... AND (date_publish IS NULL OR date_publish <= ...)" with the comment "max_date prevents future leakage". article_corpus.py stages only the date directories up to the cutoff and filters JSONL rows by date. env._get_safe_active_questions blanks ground_truth_answer.
(2) environment/scoring/base.py PredictionHistory appends DailyPrediction(agent_id, qid, day, outcomes) per agent. get_prediction_as_of(agent_id, target_date) is documented as "Get agent's active prediction as of target_date (carry-forward)". resolve_question integrates peer or Brier-skill scores over the change points of that history.
(3) SimLogger writes an append-only actions.jsonl of predictions and resolutions. replay.rescore "Rebuilds prediction histories from actions.jsonl and replays all resolutions". replay.restore_state rebuilds env state for --resume. Note that env._resolve_question deletes the in-memory history on resolution; only the log keeps it.
(4) scripts/run_forecast_sim.py prepare_restart_directory copies the log entries and memory snapshots dated before restart_day into a NEW "_restart" directory and records restart_source and restart_from_day in config.json. minimalHarness state._apply_bootstrap seeds a run from a fixed Day-0 mem.csv, meta.yaml and prediction.json. Configs use this for "compare active_memory2 vs no_memory with the same starting point" and for badWarmup (weaker model's Day-0) vs goodWarmup (GPT-5.5's Day-0).
(5) mcp_server._build_feedback_recap shows the predicted distribution vs the truth with Brier and TW-Score, plus cumulative metrics. _save_active_memory_for_today writes memory/{date}/{mem.csv,meta.yaml} and chmods them 0o444. The handholding v2/v3 prompts say "resubmit any forecast where new evidence has shifted your view ... A forecast is never 'done' while its question is still active". The avg_submission_tv_to_prev metric measures how far successive forecasts move.
EVALUATION: Frontier agents run in their native CLI harnesses (Codex, Claude Code, OpenCode configs in the repo) on about 3 months of Al Jazeera-derived OpenForesight questions (split aljazeera2026Q1 / aljazeeraQ12026v37), with daily wakeups. Metrics are accuracy (top choice), Brier skill score, time-weighted score, expected accuracy and average TV distance between consecutive submissions. Per the abstract, the best agent reaches 25% accuracy and many agents have a worse Brier skill score than making no prediction. The repo configs show the ablations: no_memory vs active_memory vs active_memory2, resume vs fresh session, search backends, handholding v1/v2/v3, and good vs bad warmup bootstraps. A third-party summary (InMatrix) says agents given a bad initial prediction anchored and struggled to recover. I could not verify that against the paper text.
THREAT: HIGH (in the forecasting lane), and it bears on the benchmark construct as well as the infrastructure.
(1) The strict no-hindsight cutoff on world state is FutureSim's core plumbing, with public code. It uses four mechanisms: date-capped search, date-staged files, hidden ground truth and a network-isolated sandbox. So "replay with a strict epistemic cutoff" is not a novel contribution.
(2) FutureSim already has an append-only, as-of-queryable forecast ledger with time-weighted scoring, plus daily predicted-vs-realized feedback that the agent is told to use for self-calibration and lesson extraction. Capability 18 and much of 19 are therefore standard.
(3) Fork and replay from a past day is implemented at experimenter level, with the original run preserved and restart_source/restart_from_day recorded (--restart_from). This matches "never overwrite time, fork it" for runs, though not for agent-internal branches.
(4) The badWarmup/goodWarmup bootstraps are the closest analog to the project's benchmark. The agent inherits earlier, wrong commitments and has to notice from incoming evidence that they need revision. The harness pushes this ("A forecast is never 'done' while its question is still active") and measures it (TV distance between successive forecasts). A third-party summary reports that agents anchor and fail to recover. A reviewer could reasonably call the project's 'later event changes the significance of an earlier decision' benchmark a software-world port of FutureSim's anchoring/revision test.
(5) FutureSim also supplies a strong, tested memory baseline design (active_memory2: per-question notes plus meta-insights, daily read-only snapshots, a feedback-driven lesson step) that a temporal contestant would have to beat.

What remains distinct for the project:
- Agency and intervention: the world is fixed, so there is no intervention-aware forecasting and no prevented-futures preservation.
- Future-state rollout and backward requirements.
- An agent-facing temporal interrogation API (the as-of query is scorer-only), and the known-then vs known-now distinction.
- Reopening closed, executed decisions with lasting side effects and remediation, as opposed to updating open forecasts.
- Identity, objective and policy drift tracking.
- A unified historical/actual/counterfactual/prospective state abstraction.
UNVERIFIED: I could not read the full paper text: arxiv.org and *.github.io are blocked, and the WebSearch budget was exhausted (200/200) before this deep read. The paper-level facts I have are only the verbatim abstract from the daily-digest corpus (25% best accuracy; many agents worse than no prediction on Brier skill score) and the author list. The bad-initial-prediction anchoring result, the claim that structured memory improved performance, and the model names (GPT-5.5, Claude Opus 4.6, DeepSeek V4 Pro) come from a third-party summary (InMatrix) and from repo config file names, not from the paper. Exact ablation numbers are unverified. I also could not find where the local MinimalHarness path writes the per-day predictions/YYYY-MM-DD.json files that the prompt advertises; only the OpenReward integration writes them (_upload_prediction_snapshot). The blogpost (openforecaster.github.io/futuresim) was not read. Notes with verbatim snippets are at /tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/lit/notes/deep-3.md.
RATINGS: 1:yes, 2:yes, 3:partial, 4:partial, 5:partial, 6:yes, 7:yes, 8:partial, 9:partial, 10:partial, 11:yes, 12:no, 13:partial, 14:yes, 15:no, 16:no, 17:no, 18:yes, 19:partial, 20:no

## Forecast-Dojo: Replayable Environments for Benchmarking and Training LLM Forecasting Agents | arXiv 2609.28876 (v1, announced 2026-09-25); preprint, no venue stated | https://arxiv.org/abs/2609.28876
SUMMARY: Forecast-Dojo replays 1,568 resolved Polymarket events (1,338 train / 230 eval, split by time) at a fixed sequence of historical forecast dates, 3 to 10 per event (eval: 797 event-dates, about 3.5 steps per event). At each date the agent sees only an 18.8M-article CC-News corpus filtered to that date. The cutoff is enforced at search and again at scrape, and model knowledge cutoffs predate the eval period. The agent outputs a probability distribution, which is scored against a realized outcome that is never shown to it. Three settings are compared on identical tasks and budgets:
- no-tools;
- memory-free: date-filtered search, read and python, with a fresh context at every date;
- memory-on: as memory-free, plus a JSON 'belief notebook' passed to the next date. It holds an assessment p, open_questions, and an 'append-only' evidence_ledger whose entries carry claim, supports, rules_out, date_observed, status active/superseded, and note.

Findings across 12 models:
- Tools improve Brier for all 12 models.
- The notebook lowers research cost (median -24% for the 5 proprietary models) but improves Brier for only 6 of 12.
- My own computation from Table 3: the mean memory-on minus memory-free delta is +0.002, i.e. slightly worse.
- Within-event Brier improvement is no better with memory (0.670->0.606 memory-free vs 0.671->0.612 memory-on).
- Every model trails the market (best 0.546 vs 0.498).

An SFT demo distills memory-free teacher trajectories into a 30B student: Brier 0.924 -> 0.749.
MECHANISM: Formal episode. For a question Q there are ordered dates tau_1 < ... < tau_T. At each step the agent sees I_{<=tau_t} = {d : date(d) <= tau_t}, and these sets are nested. Within a step the agent builds a history H_t from search(query, top_k), scrape(article_id) and python(code). Scrape rejects ids it did not return and articles dated after the forecast date. The step emits p_{Q,t}. The environment computes r_{Q,t} = S(p_{Q,t}, Y) outside the agent context.

Memory-on carries only M_t to the next step: "Previous conversation turns, reasoning traces, and tool observations are discarded, making M_t the only explicitly transferred information."

Notebook rules (from the prompt):
- "Append, don't overwrite ... mark the old one 'superseded' rather than deleting it; never silently drop a fact you once recorded."
- "Keep p consistent with the active ledger."

Logging keeps H_t and M_t per step so trajectories can be analysed or used for training. "Each step can be reset and rerun across models or repeated trials".

Leakage controls:
- article timestamps from structured-metadata cascades;
- date filtering before similarity ranking;
- an LLM judge that screens retrieved evidence for outcome leakage;
- models chosen so their cutoffs precede the eval window.

Forecast dates are chosen per sqrt-sized temporal bin, weighted 0.7 by market-belief movement and 0.3 by news volume. Unusable outputs are scored as uniform. A leave-one-model-out 'new evidence' index counts notebook ledger entries dated between consecutive forecast dates.
EVALUATION: 12 models (5 proprietary, 7 open-weight) on 230 held-out events / 797 event-dates, with 4 rollouts each. Tool budgets are identical in both memory modes: 120 iterations and 400 calls per step. Metrics: multiclass Brier, fractional-tie accuracy, Information-alpha vs the market, and log loss for SFT. 95% CIs come from an event bootstrap. Uniform and market references are included.

Main memory findings:
- 6/12 models improve with the notebook, 6/12 worsen.
- For GPT-5.6 Sol, the gain comes from fewer unusable reports (4.49% -> 0.53%). The paired difference on usable forecasts is only +0.0010.
- For GPT-5.5, cost drops 33% while the paired Brier difference is +0.007 (CI includes 0).
- My derived check from Tables 3 and 11: 4 of the 6 improvers (Sol, MiniMax, gpt-oss, Nemotron) also cut failure rates by 3.7 to 6.7 points. Because failures are scored as uniform, much of the apparent notebook gain is reliability, not better probabilities.
- Evidence capture kappa correlates with episode gain (Spearman 0.74). The authors call this correlational.

SFT: the student is trained on full Qwen3-235B teacher trajectories, memory-free. No outcome-based filtering is described, so the demo does not actually use outcome feedback or the belief notebook.

Limitations:
- episodes are short;
- the agent's actions are passive;
- the notebook is lossy and latest-only;
- the code repo is claimed but not located.
THREAT: HIGH threat to novelty claims about the harness and benchmark, and to "explicit carried belief state with supersede-not-delete provenance". Forecast-Dojo already provides:
- chronological replay at fixed historical dates with a strict epistemic cutoff;
- ground truth hidden from the agent and scored per step;
- identical tool budgets across memory conditions;
- matched information states across contestants;
- per-step trajectory logging.

These match CLAUDE.md rules 3, 5 and 8. Its notebook already implements an append-only, valid-dated, supersede-not-delete belief ledger with open questions.

MEDIUM-HIGH as prior negative evidence on the core bet:
- Under controlled, matched conditions, a structured belief state carried across time did not improve decision quality (6/12; mean dBrier +0.002, my computation).
- Within-event improvement was not faster with memory.
- It did reduce cost (median -24%) and output failures.
- Its memory-free arm (date-filtered dense retrieval over the full world log) is close to the project's null-hypothesis baseline (EXPERIMENT.md section 7). The result therefore predicts that the null survives on quality, with differences showing up mainly in cost and reliability.
- The project's scorer must separate those confounds: paired comparisons on valid outputs, failure-rate control, and cost reported separately.

What it does NOT cover, which is where a residual hypothesis can still live:
- consequential agent decisions whose significance a later event changes, and reopening or remediating them;
- agent-private state (its own decisions and rationale) that cannot be re-retrieved from a shared world corpus;
- long histories (about 3.5 steps per event, at most 10; no variation in history length, causal depth or lag);
- addressable, versioned past belief states (only the latest lossy notebook is carried);
- counterfactual branches with provenance, backward requirements, intervention-aware or prevented-future accounting, and policy/identity tracking;
- comparison against RAG over the agent's own past trajectories.
UNVERIFIED: - arxiv.org (blocked) and WebSearch (session budget 200/200 exhausted): the full text was read only via a third-party MinerU conversion of the v1 PDF (ZhangCurosr mirror, re-fetched and byte-identical). Figures are images and were not viewed; Table 1's check/cross glyphs were lost in conversion.
- The code/data repository: the PDF abstract says 'Our code and data are publicly available', but the RSS abstracts omit that sentence and no repo URL survives in the converted text. GitHub code search found no official repo, and repo search returned HTTP 502.
- Whether SFT trajectories were filtered by outcome: none is described ('full assistant trajectory', memory-free).
- Venue or peer review: none found.
- Model names and cutoff dates (e.g., GPT-5.6 Sol, Claude Opus 4.8) are as reported by the paper, not independently checked.
- The per-model memory deltas and the failure-rate confound analysis are my own arithmetic from Tables 3 and 11.

Notes: /tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/lit/notes/deep-4.md; raw copies in /tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/lit/deep4_raw/.
RATINGS: 1:partial, 2:partial, 3:partial, 4:no, 5:partial, 6:yes, 7:partial, 8:no, 9:no, 10:yes, 11:yes, 12:no, 13:partial, 14:yes, 15:no, 16:no, 17:no, 18:yes, 19:partial, 20:no

## Calibration Is Not Control: Why LLM-Agent Oversight Needs Intervention | arXiv 2606.21399 (cs.AI preprint, v1, 2026-06-19). Authors: Chubin Zhang, Zhenglin Wan, Xingrui Yu, Jingxuan Wu, Qi Wen, Pengfei Zhou, Wangbo Zhao, Ivor Tsang. No code release found. | https://arxiv.org/abs/2606.21399
SUMMARY: The paper argues that runtime oversight of LLM agents targets the wrong object when it uses scalar risk forecasting: "The relevant question is not how likely the agent is to fail if it continues, but whether an available intervention would improve the outcome."

Key concepts:
- "Two trajectory prefixes can have the same risk estimate while requiring different actions, because one remains recoverable and the other does not."
- It names this mismatch "target error". It defines "intervention advantage", the expected utility gain from intervening rather than continuing, as the decision object.
- It introduces "prefix branching, a same-prefix counterfactual protocol that executes candidate actions from identical trajectory states".

Results:
- Across four benchmarks, action-conditioned control gives regime-dependent gains over scalar routing.
- Recalibrating the scalar score "improves prediction metrics but leaves control regret unchanged".
- A "simple prefix-only action-conditioned controller" cuts regret from 0.506 to 0.110 on ALFWorld.
- Gains shrink when interventions are weak or when the scalar already preserves intervention-relevant information.

Body-level details come only from an LLM-generated digest (paper-daily-site) and are not primary:
- formal "control sufficiency" and "scalar abstraction loss";
- the candidate action set continue/defer/repair/stop;
- branching "without lookahead leakage" to estimate oracle actions and regret.

An independent citing paper (ControlScope, CMU/Tsinghua) confirms: "Zhang et al. (2026a) evaluate interventions by branching from the same trajectory prefix and distinguish intervention value from continuation risk."
MECHANISM: The decision object changes from a passive forecast to an action-conditioned one:
- Passive: P(fail | continue, prefix).
- Action-conditioned: A(a | prefix) = E[U | do(a), prefix] - E[U | continue, prefix], for interventions a such as defer, repair or stop.

Measurement uses prefix branching:
- At each trajectory prefix, the harness restores the identical trajectory state.
- It executes each candidate action, including "continue", to completion.
- The outcomes give the oracle action, intervention advantage and controller regret.
- Whether the state is restored by environment snapshot or deterministic replay, and whether replay fidelity is checked, is not stated in any text I could access.

The calibration decomposition recalibrates the same scalar and shows that prediction metrics improve while regret does not.

The deployed controller is "prefix-only" and action-conditioned. Most plausibly it is a learned estimator that sees only the prefix: branching supplies training labels and evaluation, and no rollouts run at decision time. This reading is inferred, not verified. Everything sits inside one episode on ALFWorld-style interactive benchmarks, with an overseer external to the agent.
EVALUATION: Strong conceptual and empirical result for within-episode agent oversight. It is the clearest LLM-agent statement that a passive forecast's calibration and control value are different objects, and that interventions should be judged on same-prefix counterfactual branches.

Limitations, from the abstract:
- The gains are regime-dependent: large only in the "strongest interactive regime", and they shrink with weak interventions.
- Only ALFWorld is named; the other three benchmarks are unknown to me.

The protocol needs resettable simulators, so it does not address deployment-time evaluation, where only one branch is realized.

I could not read the full text: arxiv.org was blocked and the WebSearch budget was exhausted. Ratings rest on:
- the verbatim abstract, confirmed in five or more independent index records;
- one LLM-generated full-text digest;
- one citing paper.

The pneuma-lab audit checked only the abstract. It found "same-prefix branching yes; the 100% replay match and discard rule not stated".
THREAT: HIGH for three of the project's claims.

1. Intervention-aware forecasting for LLM agents is prior art.
   - The paper makes the passive vs action-conditioned forecast distinction the central object of agent oversight and formalizes the failure of passive scoring as "target error".
   - Other agent work does the same with-and-without-intervention evaluation: Vasudev et al. 2602.03338, and COTA 2608.21027 with "same-prefix counterfactual branches".
   - Any claim that "agents should forecast conditioned on their own interventions, and interventions should be scored, not passive forecasts" is not novel.

2. "Fork from an identical historical state and compare actions" is an established agent-evaluation protocol. ControlScope (Sept 2026) reuses "same-state branching" as standard method, so "never overwrite time, fork it" is not a novel evaluation idea for agents.

3. Calibration is the wrong value claim. The calibration decomposition shows that better passive forecasts do not reduce control regret. That undercuts a predicted-vs-realized calibration loop as a value claim unless it is tied to action choice.

Adversarially, the paper also suggests that explicit runtime temporal navigation may be unnecessary:
- The regret reduction comes from a "simple prefix-only" controller, with branching apparently used only for labels and evaluation (inferred, not verified).
- A learned prefix-to-action-value estimator is therefore a strong non-temporal baseline the project must beat.
- The project should also report the regime boundary: gains "shrink when interventions are weak or when scalar routing already preserves intervention-relevant information".

What it does NOT cover, which is where the project's residual space lies:
- Long-lived, cross-session agents with persistent memory.
- Reconstructing past epistemic state from a store, and as-of or diff queries.
- Retrospective reopening: noticing that a later event changes the significance of an already-committed earlier decision and remediating it. The paper's overseer only decides whether to intervene now.
- Deployment-time handling of prevented forecasts. Prefix branching needs a resettable simulator; in deployment only one branch is realized, so preserving and labelling averted forecasts (annulled or unverifiable) stays open.
- Policy, objective or identity history; backward requirements; reflexive forecasts; an explicit belief state; a unified temporal abstraction.
- The agent's own self-forecasting, as opposed to an external overseer.
UNVERIFIED: Full text was not accessed: arxiv.org was blocked and the WebSearch budget was exhausted (200/200) before this task. GitHub code search for body phrases found no full-text mirror.

Unverified:
- The formal definitions (control sufficiency, target error, scalar abstraction loss).
- The identity of the three benchmarks other than ALFWorld.
- The units and normalization of the 0.506 and 0.110 regret figures.
- How prefix states are restored (environment snapshot or deterministic replay), and whether replay fidelity is checked or mismatches discarded.
- Whether branches are sampled repeatedly to estimate expected utility.
- How the prefix-only controller is trained, and whether it ever branches at decision time.

The candidate action set (continue/defer/repair/stop), "without lookahead leakage" and the section numbers come only from an LLM-generated digest (cyk1337/paper-daily-site). No code release was found: TengJiao33 records has_code false and paper-daily-site records github null.

The capability ratings for branch_provenance and prevented_futures_preserved are inferences from the protocol design, not explicit claims in the paper.
RATINGS: 1:no, 2:partial, 3:partial, 4:no, 5:partial, 6:partial, 7:yes, 8:yes, 9:partial, 10:no, 11:partial, 12:partial, 13:partial, 14:partial, 15:no, 16:yes, 17:partial, 18:yes, 19:no, 20:no

## Experience Graphs: The Data Foundation for Self-Improving Agents (Trellis) | arXiv 2606.29823v1 (submitted 2026-06-29, announced 2026-06-30). Primary category cs.DB, also cs.AI and cs.MA. CC BY 4.0. Authors are Gang Liao, Gaoxiang Liu and others at Meta Platforms, plus Daniel J. Abadi at UMD. The paper is a vision-style systems preprint with no venue stated. | https://arxiv.org/abs/2606.29823
SUMMARY: Trellis argues that the exploration history of long-horizon search agents, such as KernelEvolve-style MCTS or evolutionary code search, should live as first-class, governed, queryable database state instead of JSON checkpoints and logs. That history is an "experience graph": attempt nodes with parent links, artifacts, tool outputs, fitness rewards, siblings and mutable search statistics.

The system has three parts. An inner loop of stateless agent sessions produces one node per invocation. An outer-loop "control plane" picks the search policy. A store holds everything. Resume, reuse, repair, train, replay, observe, audit and govern are all recast as queries.

The temporal part works like this. Nodes are insert-only. Every in-place field mutation (visit_count, ucb_score, island_id) is written to a change log keyed by a logical step number. "Any past state is reconstructible by replaying the log backward to a target step." The paper's stated motivation is to avoid leaking future information into training trajectories.

The only measurement is a cross-session memory ablation on KernelEvolve (about 100-node sessions, 3 sessions per configuration). It compares no memory with retrieval-injection rates p=0.1 and p=0.5. Injecting memory cut buggy nodes from 55% to 34% (p=0.1) and 21% (p=0.5). It reached a 1.2x speedup in about 5 steps instead of 51, and used 52% fewer tokens per valid node. It also anchored the search: the best single solution, 1.49x versus 1.36x, came from the no-memory run.

Time travel and as-of reconstruction are never evaluated. Bi-temporal semantics are listed as an open problem.
MECHANISM: The logical model is a relational schema with four levels:
- tasks: specification, target environment, success metric;
- sessions: who is searching, with which algorithm, how far they have got;
- nodes: parent link, artifacts, execution output, fitness, evaluation evidence, algorithm metadata;
- prompt_history: "the exact messages the LLM saw and produced".

Other storage and execution choices:
- Large artifacts go to object storage, linked by reference.
- Skills and declarative facts are versioned files in a distributed file system mounted over FUSE, with provenance back to the episodes that justified them.
- Queries are SQL, Cypher (virtual parent-child edges) and vector search, planned together by Axiom over Velox.

Temporal mechanism (L662-677):
- "Nodes are inserted once and never deleted."
- Field-level mutations go to a change-data-capture (CDC) style change log keyed by logical step (evaluation order, not wall clock).
- AS-OF reconstruction replays that log to a target step.
- SFT trajectories read "each node as of its own step" because "replaying it from final state leaks future information into the example".

Resumption and branching:
- Recovery is a frontier query, and an interrupted inner session is "reattached rather than restarted".
- A child node can inherit its parent's session or rebuild context through an ancestor query.
- GRPO samples a stored state, generates N children, evaluates them in the target environment and appends one canonical node back.

Training data comes from siblings and paths:
- DPO preference pairs are a sibling pattern match.
- SFT examples are root-to-leaf paths.
- GRPO groups use SQL window functions.

Retracting a source node must propagate to the training views derived from it.

Proposed only, not built: value models over graph state, bi-temporal valid/transaction time, first-class temporal query predicates, and a "scientific society" whose claims carry lifecycle states and whose leaderboards separate score from confidence.
EVALUATION: The single study is the KernelEvolve cross-session reuse ablation. Model, 100-step budget, worker count and greedy search were held fixed. Three sessions were run per configuration (no memory, p=0.1, p=0.5), about 100 nodes each.

| Measure | No memory | p=0.1 | p=0.5 |
| --- | --- | --- | --- |
| Buggy nodes | 55% | 34% | 21% |
| Valid nodes meeting baseline speedup | 79.5% | 90.8% | 100% |
| Steps to reach 1.2x | 51 | about 5 | about 5 |
| Distinct strategy combinations | 20 | not given | 8 |
| Best single solution | 1.49x | 1.36x (memory) | 1.36x (memory) |

Tokens per valid node fell 52% with memory. At p=0.5 the search collapsed onto 8 strategy combinations, which the authors describe as anchoring.

Two further claims are qualitative only:
- In production, crashed sessions resume on another worker with no lost nodes.
- The same foundation was retargeted to MTIA silicon bug-hunting by changing only the fitness function and skills.

What is not evaluated:
- correctness or usefulness of AS-OF reconstruction or time travel;
- replay or audit;
- branch provenance;
- any effect of temporal access on agent decisions.

The authors call these "preliminary results; a fuller evaluation is left to future work".
THREAT: The threat is high for the infrastructure framing and low for the behavioural and prospective claims.

1. **The substrate is already claimed as a by-product.** A Meta and UMD database team, with the system deployed in production, presents the following as "architectural byproducts" and as "old ideas [temporal DBs, MVCC, CDC] applied to a new object":
   - append-only, never-overwritten agent experience;
   - as-of reconstruction of "what an agent knew at any past step";
   - replay;
   - forking from any stored state with lineage;
   - resumable sessions;
   - audit of which prior items influenced a decision.

   So "time as an addressable dimension of agent state" (state_at(t), fork with provenance, never overwrite time) cannot be the project's contribution. That is true here, and through the temporal-database tradition Trellis cites.

2. **The no-hindsight rationale is already stated.** "Reconstructing a trajectory from final state would train the model on decisions justified by information that did not yet exist" is the strict epistemic cutoff, applied to training-data fidelity.

3. **The benchmark question is named as a data-level problem.** The bi-temporal agenda lists "late-arriving corrections, memory-drift detection ..., distillation audit ('what did the agent know at time T, and was it still true?')". It also requires retracting a source node to propagate to everything derived from it. That is the data-system form of the benchmark question: a later event changes the standing of an earlier decision, which must be reopened. Trellis frames this as view maintenance and leaves it unbuilt.

4. **The only experiment supports the baseline.** Retrieval-injected cross-session memory gives the gains; time travel plays no measured role. Trellis also shows that reuse anchors the search, which tells the project to tune the strong baseline's injection rate.

**What survives.** Trellis does not cover:
- an agent using its own as-of epistemic or policy state while deliberating. The agent is stateless; as-of serves training, replay and audit;
- any behavioural test that temporal access improves decisions or the detection of stale decisions;
- two time axes (valid time and transaction time), or the external world state;
- irreversible single-timeline settings, since its domain is sandboxable search where every branch can be executed;
- anything prospective: rollouts, futures with probabilities, backward requirements, intervention-aware forecasts, preserved prevented futures, predicted-versus-realised calibration;
- identity, objective or policy drift tracking.

The residual hypothesis must therefore be behavioural. With cutoff-respecting access to its own past belief and policy context, and forecasts to contrast against it, does the agent detect and remediate earlier decisions whose standing a later event changed? It has to beat a strong baseline: a Trellis-style as-of store or versioned RAG with a tuned injection rate.
UNVERIFIED: - **No direct fetch of arXiv.** arxiv.org is blocked, and the WebSearch budget was exhausted (200/200), so no arXiv HTML summaries were possible. The full text came from a third-party Markdown conversion of the arXiv LaTeXML HTML (will-rice/llm-self-improvement-papers). Its abstract and metadata match the arXiv RSS and two other mirrors. The body abstract is longer than the RSS abstract, which is typical when arXiv metadata is shortened; both contain the time-travel sentence.
- **Figures 1-4 were not visible.** Their numbers were taken from captions and body text.
- **No official code was found.** The paper links no Trellis repository. GitHub repository search for KernelEvolve returned 502 errors. The only implementation found is an unofficial third-party reproduction (lmccccc/XEvolve agentdb), which I did not evaluate.
- **The Meta engineering blog and the KernelEvolve tech report (arXiv 2512.23236) were not read.** The blog host did not respond from the sandbox.
- **Unknown extent of what is built.** The paper does not say how much of the CDC/AS-OF machinery runs in production as opposed to being designed. Time-travel queries are never evaluated, and no as-of query syntax or API is shown, only a description of replaying the log.
- **Unknown versioning of the knowledge tiers.** It is unclear whether the knowledge tiers (skills, declarative facts) are covered by the same AS-OF mechanism or only versioned files.
- **No external status found.** I found no venue acceptance, peer review or citing follow-up work.
RATINGS: 1:yes, 2:partial, 3:yes, 4:partial, 5:yes, 6:yes, 7:yes, 8:yes, 9:yes, 10:partial, 11:no, 12:no, 13:no, 14:no, 15:no, 16:no, 17:no, 18:no, 19:yes, 20:partial

## Reasoning Provenance for Autonomous AI Agents: Structured Behavioral Analytics Beyond State Checkpoints and Execution Traces (Agent Execution Record, AER) | arXiv 2603.21692. v1 is dated 23 Mar 2026 (PDF stamp; announced 24 Mar), cs.AI, 8 pages, single author Neelmani Vispute (Oracle Cloud Infrastructure). v2 was announced 13 Apr 2026 as a replace-cross: it adds co-author Aditya Kadam and cross-lists to cs.DC and cs.SE, with an unchanged abstract. License is CC BY-SA 4.0. | https://arxiv.org/abs/2603.21692
SUMMARY: This is a position and formalization paper from Oracle Cloud Infrastructure. Its claim is that state checkpoints (the LangGraph checkpointer), observability traces (LangSmith, Langfuse, Datadog), OTel GenAI and PROV-AGENT cover the "mechanical layer" of agent execution. None of them stores "structured reasoning provenance" as a first-class, schema-level object.

It introduces the Agent Execution Record (AER), a per-investigation set of JSON/JSONL files:
- envelope.json: written once. It holds agent_version, model, prompt_version, the delegation authority chain, permissions scope, and the retrieval context that "actually entered the agent's context window".
- plans.jsonl: versioned plans with supersedes, revision_trigger and rationale fields.
- steps.jsonl: per step, the intent, tool_calls with outputs, observation, inference, the plan_version in force, and tokens.
- verdict.json: the conclusion with confidence, evidence_chain, alternatives_rejected (with rejected_by step pointers) and remediation.

It formalizes Computational State S_k=(M_k,C_k,T_k) against Reasoning Provenance R_k=(I_k,O_k,N_k,P_k). A non-identifiability proposition argues that R cannot in general be faithfully reconstructed from S as a normalized, cross-run-comparable representation. The three reasons given are intent multiplicity, observation ambiguity and inference volatility.

There are three replay modes:
- Narrate: read-only.
- Mock: re-run the reasoning on recorded tool outputs under a new model or prompt, with a per-step and verdict divergence report.
- Live: re-execute against live systems.

It describes a local-first JSONL SDK with start_investigation, log_plan, log_step and record_verdict, plus a Kafka/Avro scale-out design. The running example is a production root-cause-analysis agent (Jira DBINFRA-1458). The evaluation is only planned. The storage comparison (4-22x more compact than cumulative checkpoints) is based on a "stylized 10-step investigation".
MECHANISM: AER relies on contemporaneous, schema-constrained self-annotation by the agent at execution time:
- Prompts make the agent emit intent, observation and inference per step.
- The SDK writes these to JSONL alongside the tool I/O.
- A re-plan writes a new plan version that points to the plan it supersedes and to the step that triggered it.
- The final verdict carries a scalar confidence, an evidence chain of step ids, and rejected hypotheses, each with the step that disconfirmed it.

Mock replay feeds the recorded tool outputs to a different model or prompt and compares observations, inferences and the verdict step by step. Batch mock replay over pinned investigations gives population-level regression metrics: verdict convergence rate, re-plan frequency shift, and hypothesis breadth.

Lifecycle management:
- Records are evicted by count (default 50) or by time (default 14 days) unless pinned or promoted.
- The schema evolves additively.
- Raw capture and field-level redaction are configurable.

The agent itself is never described as reading AERs. They exist for platform teams' population-level analytics ("the BI layer for autonomous agent reasoning").
EVALUATION: There are no empirical results. In the paper's own words: "The paper's primary contribution is the AER abstraction and its formalization; empirical validation across diverse workloads is ongoing work." Section 7 is a "planned evaluation methodology" with five parts:
- 10 behavioral-analytics questions, each scored as answerable or not from AER, checkpoints or traces. The paper only hypothesizes the outcome.
- Mock-replay regression on 50 incidents.
- Storage measured on 100 investigations.
- An expressiveness comparison on 20 incidents.
- A preliminary faithfulness check: expert rating of intents, action/intent consistency, and predictive validity of confidence.

The only numbers are the 4-22x storage ratio (about 560 KB vs 25-130 KB), which the paper itself calls "preliminary motivation, not a validated empirical result". The faithfulness of self-reported reasoning is acknowledged as a known risk (post-hoc rationalization, format gaming).

No public code was found:
- The v1 full text has no repository URL.
- GitHub code search for the SDK API names and the record file names returns only paper mirrors.
- PyPI 'aer' is an unrelated EMR CLI.
- The memgrafter digest also notes that the SDK location is unspecified.

A third party (Ala-ADN/gommage) has built an "AER ... inspired by Vispute (2026)" replay proxy. That is not the authors' artifact.
THREAT: HIGH for the provenance and replay part of the thesis and for benchmark fairness. LOW for the prospective and temporal-navigation core.

(1) Prior art for the argument. The project argues that checkpoints and traces are not enough and that why-records are needed: decision provenance, versioned plans, authority. AER (v1 March 2026, v2 April 2026) already makes this argument explicitly against the LangGraph checkpointer and against LangSmith/Langfuse/Datadog, OTel GenAI and PROV-AGENT. It gives a formal proposition and names three sources of non-identifiability: intent multiplicity, observation ambiguity and inference volatility. The project cannot claim this motivation as new.

(2) Plan versioning and policy records already exist. Plans are versioned rather than overwritten (supersedes plus revision_trigger plus rationale), and each run records model, prompt version and the delegation authority chain. This already gives the project's "never overwrite, version/fork with provenance" for plans, and its identity/policy tracking, at investigation granularity.

(3) Epistemic cutoff is already a stated principle. "Retrieval provenance over availability provenance" (log what entered the context, not what was queryable) is a stated precursor of the project's strict epistemic cutoff, as a logging principle rather than an enforced reconstruction.

(4) Policy-counterfactual replay is covered. Mock replay re-runs recorded history with observations fixed and the policy changed, then diffs per step and on the verdict.

(5) The most consequential point is for the benchmark. EXPERIMENT.md gives the temporal contestant 'decision provenance' but gives the baseline only 'decision records retrievable by semantic search'. AER shows that rich structured decision records are non-temporal, checkpoint-adjacent technology:
- intent, observation and inference per step;
- plan versions with revision triggers;
- evidence chains;
- rejected alternatives;
- confidence.

Unless the strong baseline also gets AER-grade decision records, any temporal-contestant win on "a later event changes the significance of an earlier decision" may come from richer provenance logging, not from temporal navigation. That confound would violate CLAUDE.md rule 4 (strong baseline).

What AER does NOT cover:
- Anything prospective: rollouts, multiple futures, probabilities, backward requirements, intervention-aware forecasting, prevented futures.
- Reconstruction of world state at t, and as-of or diff queries.
- Agent-facing use. AER is a developer and platform analytics layer; the agent never reads its own past records when deciding.
- Retroactive reopening or remediation of earlier completed decisions when a later event changes their significance. revision_trigger only links forward plan revisions within one short investigation.
- Lifelong scope. The defaults evict after 50 records or 14 days, and multi-agent support is future work.
- Empirical results.

The residual hypothesis that survives is behavioral. Does an agent that can query cutoff-respecting past states and decision records, and contrast them with the present, reopen affected decisions better than an agent with equally rich AER-style records under checkpoint + RAG?
UNVERIFIED: - I could not fetch arxiv.org directly (blocked), and WebSearch was exhausted (200/200) before this task started, so I made no web-search queries.
- The full text I read is a third-party markdown conversion of the v1 PDF (twenhui2-afk/daily-paper-reader). The conversion is cut off at the 'References' heading, so the reference list (the digest says 11 refs) and the exact bibliographic details of PROV-AGENT [3] were not read.
- The v2 (13 Apr 2026) body was not read. Only its unchanged abstract, the added co-author Aditya Kadam and the added cs.DC/cs.SE categories are verified, via an arXiv RSS dump and arXiv-stats metadata. v2 may add evaluation results, a code link or other content I did not see.
- The reference implementation and SDK (start_investigation/log_plan/log_step/record_verdict, the `aer replay` CLI) could not be located on GitHub code search or PyPI, so whether replay, eviction and the other described behaviors are actually implemented is unverified.
- The 'preliminary deployment on a production platformized root cause analysis agent' has no reported data.
- The memgrafter digest is LLM-generated and was used only as corroboration (e.g., that the SDK location is unspecified).
RATINGS: 1:partial, 2:no, 3:partial, 4:partial, 5:no, 6:yes, 7:partial, 8:partial, 9:partial, 10:partial, 11:partial, 12:no, 13:no, 14:no, 15:no, 16:no, 17:no, 18:partial, 19:partial, 20:no

## ChronoMem: Version Control and Semantic Rollback for Large Language Model Agent Memory | arXiv 2607.27773 (v1 2026-07-30, v2 2026-08-05), cs.CL. Su (Purdue), Xu (Rutgers), Zuo (Rutgers), Bertino (Purdue). Preprint only; no peer-reviewed venue found by independent DBLP/Crossref audits. | https://arxiv.org/abs/2607.27773
SUMMARY: ChronoMem is a version-control layer for an LLM agent's long-term memory, built on Google's Agent Development Kit (ADK).
- On every memory write it commits a whole-memory snapshot into an append-only event log with materialised snapshots and a HEAD pointer, stored in SQLite.
- Each version gets a semantic commit descriptor: {delta, summary, op, labels}.
- A natural-language "undo" request is resolved to a version. BM25 (FTS5) and dense retrieval are fused with RRF, then reranked with a cross-encoder. The resolved version is restored deterministically.
- Interface invariant: after rollback to v*, every subsequent read is scoped to v*.
- Its "post-exposure" protocol ingests the full stream, then rolls back, then tests whether the agent answers and summarizes "as if future updates had never occurred".
- Benchmarks are LoCoMo and MemoryAgentBench, run with Llama-3.1-8B, Qwen2.5-7B and Mistral-7B.
- Prompt-only "ignore later info" scores almost zero (0.9–2.8 F1 on LoCoMo); snapshot restore scores 31–38 F1.
- Version selection Recall@1 is only 20.5% on LoCoMo and 33.4% on MAB.
- History is linear: rollback truncates later versions ("Git reset, not revert"). Branching is stated as a limitation and listed as future work.
MECHANISM: Event-sourced memory with a materialised snapshot per write and a HEAD pointer.
- Commit-on-write produces a version v with a semantic descriptor.
- NL rollback intent goes to hybrid lexical+dense retrieval over the descriptors, then RRF (k0=60), then a cross-encoder rerank, which yields the target version v*.
- ID-based restore moves HEAD to v* and truncates the versions after it.
- All reads afterwards are scoped to S(v*).
- Evaluation has two axes: (i) semantic version resolution (Recall@1/5, Scope@2); (ii) behavioural correctness after restore (rollback-consistent QA F1, summarization ROUGE/F1).
- Baselines: prompt-only rollback, full-history prompt rollback, retrieval-only (vector DB) rollback.
EVALUATION: Datasets are LoCoMo and MemoryAgentBench (MAB). On MAB, downstream QA is limited to the Accurate Retrieval split. Both are adapted to a post-exposure setting, with rollback queries generated from ground-truth anchors.

Version selection, Recall@1 / Recall@5 / Scope@2:
- LoCoMo: ChronoMem 20.5 / 38.9 / 31.2, against 12.0 / 28.1 / 17.9 for hybrid RRF.
- MAB: ChronoMem 33.4 / 60.2 / 58.0.

Rollback-consistent QA F1 on LoCoMo (Llama / Qwen / Mistral):
- prompt-only 2.3 / 2.8 / 0.9;
- full-history 19.3 / 20.6 / 13.5;
- RAG-only 28.9 / 27.1 / 19.4;
- ChronoMem 36.1 / 38.5 / 31.3.
- On MAB, ChronoMem scores 53.8 / 55.1 / 44.6.

The paper reports roughly +10 points over the strongest baseline without global snapshot restoration.

Weaknesses noted by readers:
- The §5.1 prose for MAB Recall@1 (39.4) does not match Table 3 (33.4).
- Recall@1 is low in absolute terms.
- Concurrency is not evaluated.
- Rollback intents are synthetic.
- Global restore discards independent later work.

These numbers come from a secondary full-text reader (jenslaufer, arXiv HTML v2), not from my own read of the PDF.
THREAT: HIGH for the retrospective / no-hindsight half of the thesis.

Why it threatens novelty:
- **Direct prior art for the strict epistemic cutoff at the memory layer.** It has a hard read-scoping invariant ('every subsequent read is scoped to v*'). It also has a named post-exposure evaluation protocol that measures whether behaviour leaks information from after the cutoff once the agent has seen it. The project cannot claim 'reconstruct what the agent knew at t without hindsight' or a 'hindsight-leakage metric' as new. It must cite and position against this protocol, and could reuse its metrics.
- **The architecture-versus-prompting argument is already made.** Prompt-only rollback scores 0.9–2.8 F1 against 31–38 for restore. This is the core motivation for explicit temporal state over prompting.
- **Same substrate.** It already ships the project's foundation: append-only event log, per-write snapshots, HEAD pointer and event-sourcing lineage.
- **Baseline consequence (CLAUDE.md rule 4).** A strong 'checkpoint + RAG' baseline should be configurable to include ChronoMem-style per-write versioning with as-of read scoping. Otherwise any win by the temporal contestant can be attributed to versioned memory that already exists.

What it does not cover:
- **Non-destructive navigation.** Rollback is a linear Git reset, so the agent cannot consult its past self and keep its present. Forking and branch provenance are absent.
- **The opposite direction from the project's benchmark.** ChronoMem removes later information. The benchmark needs the agent to use a later event to reassess an earlier decision and reopen it. ChronoMem's tasks are conversational QA and summarization, not agentic decisions with consequences.
- **Trigger.** Rollback is triggered by an explicit user undo, and queries are synthesized from ground-truth anchors. There is no agent-initiated detection that something should be revisited.
- **What is versioned.** No world-state vs epistemic-state separation; no policy, objective or identity history; no structured beliefs or uncertainty.
- **The prospective half is absent.** No rollouts, backward requirements, prevented futures, or predicted-vs-realized comparison.

Version selection is weak (Recall@1 20.5%), which suggests exact as-of addressing beats NL undo. That is an engineering point, not a novelty claim.
UNVERIFIED: I could not fetch the paper PDF/HTML myself: arxiv.org is blocked and the WebSearch budget (200/200) was already exhausted at the start of this task.

What I relied on instead:
- the verbatim abstract, from several arXiv daily mirrors;
- paper prose and section headings reproduced in the Black-Lake whitepaper review (v1);
- mechanism details and table numbers from secondary full-text readers: jenslaufer (v2 HTML) and mzayan (targeted inspection of v2).

Specific numbers, the §5.1 versus Table 3 inconsistency, the Cohere Rerank-3.5 / RRF k0=60 details and the 'Git reset, not revert' truncation are all secondary paraphrase.

Code was not found, so the 'first open-source system' claim is unverified:
- 13 plausible GitHub names failed `git ls-remote`;
- there is no PyPI package;
- google/adk-python has no ChronoMem code;
- GitHub repository search returned 502 errors;
- Black-Lake and mzayan independently report no verified code link.

The meaning of 'integrated into ADK' is unverified; it is probably a layer on ADK's memory interface rather than upstream code.

Also unknown:
- whether truncated versions are physically deleted or only made unreachable;
- whether rollback is itself logged as an event;
- whether wall-clock as-of queries are supported;
- the exact definition of Scope@2.

Notes with verbatim snippets are in /tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/lit/notes/deep-8.md, and raw sources are in .../scratchpad/lit/deep8_raw/.
RATINGS: 1:partial, 2:no, 3:yes, 4:no, 5:partial, 6:partial, 7:no, 8:no, 9:no, 10:no, 11:no, 12:no, 13:no, 14:no, 15:no, 16:no, 17:no, 18:no, 19:partial, 20:no

## Corollary: an agent runtime where the unit of state is a belief, not a message (JTMS truth maintenance for LLM agents) | GitHub gabe-santana/corollary (MIT, pre-alpha); PyPI corollary 0.1.0a1 and 0.1.0a2 (both uploaded 2026-10-02); single author Gabriel Santana; first commit 2026-10-01, HEAD 1ad7230 2026-10-02 | https://github.com/gabe-santana/corollary
SUMMARY: Corollary is a pre-alpha Python library from October 2026. It replaces an LLM agent's message log with a belief base built on a justification-based truth maintenance system (JTMS, Doyle 1979). The LLM is a stateless proposer that may only emit call_tool, cite, claim or answer actions as JSON. The runtime executes tools and records their results as premises. It validates claims: dependencies must be visible and IN, formulas are re-executed, and quotes are span-matched. It records each claim with justifications. Under the default "conservative" policy, a claim depends on everything visible in the context it came from. The kernel computes well-founded IN/OUT labels. Retracting or superseding a premise cascades OUT through its dependents. propagate()/agent.repair() then re-derives only the affected region, with early cutoff, and reports a diff of what changed. Evidence can expire (TTL) or fade (half-life), which triggers reverify(). Value and constraint conflicts are first-class and hidden from the model until resolved. A TrustLedger learns each source's reliability from outcomes. Beliefs are immutable and revisioned. Retracted revisions are kept with their reasons, an append-only event history is kept, and the whole base (revisions, justifications, history, ledger) saves to and loads from JSON. There is no evaluation beyond 386 unit tests and a deterministic demo: a 20-conclusion report where 12 conclusions change, 7 are untouched, with 13 rule evaluations and 0 model calls. The README says: "There is no standard evaluation for how well an agent recovers from a corrected input. We want to build one."
MECHANISM: Data model. Nodes are belief revisions (key@n) holding an immutable Belief (key, value, claim, source, confidence, created_at). Justifications are hyperedges from antecedent refs, pinned to revisions, to a conclusion. They also carry recipe input keys (for re-derivation), `unless` out-list keys (non-monotonic defeaters), an optional formula, valid_until and half_life.

Labeling. A node is IN iff it is not retracted and some justification is valid: all antecedents IN, no unless key believed, not expired. Labels are the least fixpoint, recomputed only over the downstream region of a change (SCCs ordered by Tarjan). A belief that depends on its own absence (an odd loop) is rejected.

Change handling. retract() takes effect immediately and marks dependents OUT. assert_(supersede=True) retracts older revisions. refresh() expires evidence and is called before every step and projection. propagate() re-runs rules and asks the model to re-derive model-justified beliefs from their current inputs. The re-derive prompt shows the previous conclusion value but not the retracted inputs. An unchanged recomputed value revives the old revision, which is the early cutoff.

Projector. Builds every model context from IN, unconflicted beliefs above a confidence threshold. The history and transcript are never shown to the model.

Learning. A TrustLedger learns reliability = (prior*n0 + correct)/(n0 + total) from retractions with fault="source", human conflict resolutions, independent corroborations, verified model formulas and citations, and manual record_outcome. Retractions with fault="none" (the world changed) are not counted as errors.

Verification. A deterministic verifier runs structure, grounding, arithmetic (rule and formula replay), citation, temporal and numeric-provenance checks. TemporalCheck fails a proof if evidence has expired at check time or a justification was created before an antecedent existed.

Other. narrow() prunes dependencies by counterfactual ablation: it re-asks the model with one antecedent removed. Persistence is via a JSON snapshot; labels are recomputed on load, and rules, policy and clock are not saved. ATMS (alternatives in parallel) is on the roadmap only.
EVALUATION: None. Corollary has no paper, no benchmark and no comparison against message-log or RAG agents. Evidence consists of 386 unit tests, which I ran locally (all pass in 5.4s), the mypy-strict and 95%-branch-coverage claims in the FAQ, and deterministic examples. The flagship self_repairing_report.py, which I ran, prints "12 conclusions changed, 7 were untouched, 1 recomputed but unchanged ... Rule evaluations during the repair: 13. Model calls: 0" and "Verification PASSED: 6 checks". The README lists benchmarks as an open problem.

My own probes:
(a) Explicitly correcting a premise (retract + re-assert) re-derived a downstream "decision" from use-libfoo to use-libbar. decision@1 was preserved with why_out "lost support: libfoo:safe", and Proof.diff showed the change.
(b) A later, unanticipated fact on a different key (cve:libfoo) left the decision IN. Nothing reopened it.
(c) The decision reopened on that fact only when the programmer had declared unless=["cve:libfoo"] at derivation time ("defeated by: cve:libfoo"). The LLM contract has no unless field.
(d) TrustLedger.reliability(at=2026-01-01) was lowered by an outcome recorded on 2026-06-01: 0.864 against a prior of 0.95. Its `at` parameter does not enforce an epistemic cutoff.
(e) restore() mutates a retracted revision back to IN in place.
THREAT: HIGH threat to the mechanism. LOW to MODERATE threat to temporal navigation proper.

(1) Mechanism pre-empted. Corollary ships tested code (386 passing tests) for the exact "assumption or premise invalidated -> dependent conclusions, including a final answer or decision, reopened and re-derived" loop. It keeps the old conclusion revision with its pinned decision-time inputs and a reason, and reports a diff of what changed. Time-driven invalidation (TTL, half-life, re-verification) is included. All of this is done with no temporal navigation: classical dependency-directed backtracking (Doyle 1979) plus incremental recomputation. Wherever the dependency was recorded at decision time and the later event arrives as a correction or supersession of it, the project's benchmark crux ("notice that a later event changes the significance of an earlier decision and reopen it") has a cheaper, non-temporal solution.

(2) Confound. Its design is deliberately anti-history: the model never sees the history or transcript, only current IN beliefs. It is therefore a principled strong non-temporal contestant. If the project's temporal agent beats checkpoint+RAG, "recorded dependencies + retraction cascade" explains the win as well as "time as an addressable dimension" does. The project needs a dependency-tracking or TMS baseline arm, configured strongly as CLAUDE.md requires, or its result is confounded.

(3) Benchmark first-mover risk. The author states the intent to build "a standard evaluation for how well an agent recovers from a corrected input", which overlaps the project's benchmark.

(4) TemporalCheck ("no conclusion predates the beliefs it uses") is a narrow proof-level form of epistemic-cutoff discipline.

What it does not cover, and where the project's residual hypothesis sits:
(a) Noticing unanticipated later events that change an earlier decision's significance without retracting any premise. My probe shows a new fact on a different key leaves the decision IN. Reopening requires a defeater (unless=) declared up front, which is available only in the programmatic API and not in the LLM contract, or a registered Constraint, or an explicit retract/supersede of the same key.
(b) Remediating executed actions or side effects. Corollary only repairs beliefs and answer text.
(c) Whole-state as-of reconstruction with a strict cutoff. Labels are current-only, and TrustLedger at= leaks later outcomes (verified).
(d) Policy, objective and identity versioning; fork/branch with provenance; counterfactual action branches; prospective futures and probabilities; backward requirements; intervention-aware or prevented forecasts. None exist, and ATMS is roadmap only.
(e) Any empirical evidence that the approach helps LLM agents. There is none.
UNVERIFIED: The web search budget was exhausted, so I could not look for external mentions, blog posts, an accompanying paper, or which related TMS-for-LLM repos came first (e.g. benthomasson/ftl-reasons and afogel/lemmalog, named in the earlier sweep). GitHub HTML and API are blocked, so stars, issues, Discussions and release pages are unchecked. The docs site gabe-santana.github.io/corollary is blocked; I used the repo's docs/ folder instead. The Claude and OpenAI adapters were not run without an API key, so I did not observe real-LLM behavior (dependency confabulation, re-derivation quality); only the scripted and offline paths were exercised. Any private development history before the 2026-10-01 initial commit, such as a draft evaluation, is unknown. Its claims of 95% branch coverage and mypy-strict were not re-run; only pytest was run.
RATINGS: 1:partial, 2:no, 3:partial, 4:no, 5:partial, 6:partial, 7:no, 8:no, 9:no, 10:yes, 11:yes, 12:no, 13:no, 14:no, 15:no, 16:no, 17:no, 18:partial, 19:partial, 20:no

## Memvara: bitemporal memory for AI agents | GitHub memvara/memvara (commit f263e3f, Release 0.19.0, 2026-10-01); PyPI memvara 0.19.0 (first release 0.1.0 on 2026-08-14), Apache-2.0. Software, not a paper. | https://github.com/memvara/memvara
SUMMARY: Memvara is a shipped Python library, MCP server and hosted service. It stores agent memory as bitemporal (subject, predicate, object) claims. Each claim has a world clock (valid_from/valid_to) and a belief clock (recorded_at/invalidated_at). Eight reads (search, get_all, count, history, why, produced, neighborhood, paths_between) accept three time arguments: valid_at=T (what we now believe was true at T), known_at=T (what we believed at T) and as_of=T (both clocks at T). Contradictions on single-valued predicates are resolved deterministically by a keyed slot lookup, with no model call. A superseded claim is 'ended' (the world changed), a wrong one is 'retired' (the record was wrong), and erasure is separate. why() returns the source episodes and the superseded claim. ask(question, at=T) renders three readings per fact slot: now, then (today's belief about T) and stated (what the store would have said at T), plus a 'diverged' flag. since(T) returns added and gone claims between T and now. The repo includes a self-authored, deterministic 'Agent Memory Benchmark' (262 events, 100 questions) with knowledge_time questions. Memvara scores 92.0% on it, against 89.0% for a one-clock full-log vector-RAG baseline. There is nothing on agent execution, branching, futures or forecasting.
MECHANISM: SQLite tables for claims, episodes, links, entities and erasures, plus FTS5 and an mmap vector sidecar. A read is a SQL predicate over four columns: recorded_at <= known_at, invalidated_at > known_at, valid_from <= valid_at, valid_to > valid_at. Writes go through a deterministic reconciler: normalise the predicate, fold the entity, look up the (subject, predicate) slot, and for cardinality ONE close the incumbent's valid_to and set invalidated_by. Closures are stamped in place on the existing row (UPDATE claims SET valid_to / invalidated_at / salience / sources) and a witness entry is added to meta. There is no append-only mutation log. Because valid_to is stamped in place by the later write, row-level as_of reads apply endings that had not yet been recorded at T, and the docs say so. ask() rebuilds the 'stated' view by dating each ending at its successor's recorded_at. LLM extraction (add()) is optional; remember() is model-free. Agentic extraction can propose memories, but only the reconciler writes.
EVALUATION: Self-authored, deterministic benchmark (benchmarks/agent_memory, v1 dataset, no LLM judge). memvara 0.9.0: 92.0% overall, 100% on the temporal and knowledge_time categories, 16.7% on multi_hop. vector-rag (one clock, keeps every observation): 89.0% overall, 100% on knowledge_time. naive overwrite dict: 50.0%. The authors' own reading: 'Three points separate memvara from a baseline built out of numpy in an afternoon'. The whole lead comes from 4 delayed-knowledge/correction questions. There are also retrieval-only LOCOMO/LongMemEval numbers, one judged LongMemEval-S run in a separate harness (MemoryBench), and an authored support-corpus demo. LIMITATIONS says there is no production use by external users and no independent reproduction. My probes, run on the cloned source with a numpy venv: (1) Rome recorded 01-04, then Berlin valid 03-01 but recorded 03-22. At t=03-15, get_all(as_of=t) and search(as_of=t) both return [], although the store held Rome then. ask().stated returns ['Rome'] with diverged=True. since(03-10) reports '+1 -0', so it misses the supersession its docstring says lands in both sets. (2) A backdated forget(close='ended', at=03-01) issued today, and also the case of an erased successor, both make ask().stated at 03-15 return [], so even ask() leaks hindsight in those cases. The ask() narration for (2) also says 'retired' where the state is 'ended'.
THREAT: HIGH for the memory-layer part of the thesis; LOW for the agentic and prospective parts.
(1) A stable, Apache-2.0 pip package already does bitemporal fact memory for agents with valid vs knowledge time. It provides as-of, valid_at and known_at reads, the 'world changed' (ended) vs 'record was wrong' (retired) distinction, supersession provenance (why().superseded) and ask(), which compares 'what we would have said at T' with 'what we now believe about T'. Reading.diverged is documented as 'the record changed under a decision somebody already made. An agent that acted on 2026-03-15 acted on `stated`, and is being audited against `then`'. That is close to the project's motivating failure. The project cannot claim historical epistemic reconstruction of facts, as-of querying or belief-revision provenance as novel.
(2) Under the project's strong-baseline rule, a checkpoint+RAG contestant could reasonably add a memvara-style bitemporal store or a one-clock full-log RAG. Any temporal-agency advantage must exceed that.
(3) Memvara's own benchmark is evidence against large effect sizes at the memory layer. A one-clock vector-RAG over the full log scored 89.0% vs 92.0% and got knowledge_time 100% right; the whole gap is 4 delayed-knowledge/correction questions. History reconstruction alone may add little over strong log+RAG unless scenarios are built around late-arriving knowledge that changes earlier decisions.

What it does NOT cover, which is the project's residue:
(a) Strict hindsight-free reconstruction. Row-level as_of reads leak later-recorded endings by design. ask() still leaks for backdated no-successor endings and erased successors (my probe), and there is no append-only log of when each mutation was believed. A rigorous, leakage-tested cutoff is still open, but it is an engineering contribution, not a conceptual one.
(b) Epistemic state beyond facts: the context at decision time, plans, assumptions, rationale.
(c) Dependencies from decisions to beliefs, and automatic reopening or remediation. There is no truth maintenance: 'derives' links exist, but 'Nothing in the engine writes one today', and supersession propagates nowhere. diverged appears only when someone asks about that slot and instant.
(d) Checkpoints, replay, forks, counterfactual branches and branch provenance.
(e) Everything prospective: rollouts, multiple futures, probabilities, backward requirements, intervention-aware forecasts, prevented futures (its ended/retired vocabulary would mislabel an averted forecast as 'never true'), and predicted-vs-realized.
(f) Agent policy and objective history as first-class state.
(g) Evidence that temporal queries change actions. Its evaluation is fact QA, not agent decisions.

The project's surviving claim must sit in (b), (c), (e) and (g), and its benchmark should include a bitemporal-memory baseline arm.
UNVERIFIED: The WebSearch budget for this session was exhausted (200/200), so I found no external search hits on Memvara: no papers, blog posts or third-party adoption reports. The URL and facts rest on the git clone, PyPI JSON and my local probe runs. I could not see GitHub stars, issues or the full commit history (the clone is a single squashed or shallow commit; api.github.com is blocked). Authorship is unknown: there is no author field in pyproject or on PyPI. I did not reproduce the benchmark numbers (92.0/89.0/50.0) or the ~10k-test / 100%-coverage claims; they are as reported in the repo. The two papers memvara cites as related work (arXiv:2607.26520, Niksarli and Baheti, 'A Graph-Native Bitemporal Memory Store for Conversational AI Agents'; arXiv:2512.12818, 'Hindsight is 20/20') could not be checked by search. Only github.com/vectorize-io/hindsight was confirmed to exist, via git ls-remote. The hosted memvara.dev service and its REST API are closed source and were not examined.
RATINGS: 1:partial, 2:yes, 3:partial, 4:partial, 5:no, 6:no, 7:no, 8:no, 9:no, 10:yes, 11:partial, 12:no, 13:no, 14:no, 15:no, 16:no, 17:no, 18:no, 19:yes, 20:partial

## Memvara: bitemporal memory for AI agents (plus its cross-system Agent Memory Benchmark) | GitHub memvara/memvara v0.19.0 (HEAD f263e3f, 2026-10-01); PyPI memvara 0.19.0, Apache-2.0, first release 0.1.0 on 2026-08-14 | https://github.com/memvara/memvara
SUMMARY: Memvara is a shipping Python library (numpy only, no model calls on reads, SQLite store) that keeps agent memory as (subject, predicate, object) claims. Each claim has two independent clocks: valid time (valid_from/valid_to, when it held in the world) and transaction time (recorded_at/invalidated_at, when the store believed it). Eight reads take valid_at= ("what we believe TODAY about how the world was at T"), known_at= ("what we believed at T") or as_of= (both clocks). ask(question, at=T) returns per-slot Readings with now / then / stated ("what this store would have answered at that instant") and a `diverged` flag. The README glosses that flag as "the record changed under a decision somebody already made". why() returns the source episodes and the superseded claim. since(when) returns added/gone deltas. Superseded claims are 'ended' or 'retired', not deleted. The repo also ships a self-authored, deterministic, cross-system Agent Memory Benchmark: 262 events, 100 questions, 16 scenarios. I re-ran it: memvara 92.0%, vector-rag 89.0%, naive 50.0%. The vector-rag baseline is an append-only time-stamped log that answers with a single cutoff. It scores 100% on knowledge_time, current state, provenance, change time, change detection and contradiction. It loses only 4 of 27 historical_state questions (85.2% vs 100%), all delayed-knowledge or same-instant-correction cases. That is 4 of 47 temporal questions, about 8.5%.
MECHANISM: Write path: remember(s,p,o, valid_from, recorded_at, sources) or add(text). add() runs model-free tiers (dedupe, salience gate, rule extractor) and then optionally one LLM extraction call. A deterministic reconciler normalises the predicate, folds the entity key and applies predicate cardinality. A new value on a single-valued slot closes the old claim's valid_to in place and sets invalidated_by ('ended'). A same-instant correction closes transaction time ('retired'). A lower-confidence candidate is kept beside the incumbent as a Dispute. Read path: SQL range predicates over the four time columns (valid_at/known_at/as_of/valid_during), plus hybrid vector+BM25 (+ optional graph) retrieval with per-predicate decay. ask() walks the supersession chain via _stated_at and dates each ending at the successor's recorded_at, which gives a strict 'what the store would have said at T'. The generic get_all(as_of=T) does not do this. The INTERNALS doc says the row 'applies an ending that had not been recorded at T', and they decline to fix it. Provenance: claim_sources joins claims to raw episode turns; why()/produced() traverse it. Typed links 'extends'/'derives' exist, but nothing in the engine writes 'derives' and nothing propagates. Benchmark: a five-method adapter protocol. The runner strips gold answers and hands every system structured triples and the predicate schema. Scoring is exact and deterministic, with no LLM judge. Baselines are naive (overwrite dict) and vector-rag (append-only log, hashed TF-IDF, recorded_at cutoff, with the same retraction rule as memvara).
EVALUATION: The evaluation is a self-authored synthetic benchmark (the doc says 'The corpus is authored by the maintainers of one of the systems under test'). Extraction is out of scope: every event carries a structured triple. 83 of 100 questions hand the system the slot ('probe'), only 4 carry known_at, and 7 are knowledge_time. Answers are values, not agent actions or prose. The vector baseline uses hashed TF-IDF, not a neural embedder. Within those limits it is careful and honest. Gold answers come from four published rules, and the baseline gets the same correction rule. Results are deterministic, and I reproduced them exactly at HEAD f263e3f / memvara 0.19.0 (92.0 / 89.0 / 50.0, temporal 100 vs 91.5, knowledge_time 100 vs 100). The authors' own reading cuts against their product: 'Three points separate memvara from a baseline written in numpy in an afternoon' and 'The bitemporal advantage is real and it is narrow ... roughly nine per cent of realistic temporal questions are that case.' A separate bench/temporal.py (six families, 120 questions) has memvara at 100% against a 'no-clocks' present-tense baseline at 53.3%. That baseline is weaker, and the doc calls it 'an illustration of a mechanism, not evidence against another system'. My own runs confirmed two weaknesses. (1) Generic as-of reads apply hindsight. With Rome recorded 01-01, Berlin valid 03-01 but recorded 03-22, and T=03-15: get_all(as_of=T)=[], since(T).gone=[], while ask().stated=['Rome']. (2) Undeclared predicates never supersede ('auth_strategy' kept both values live). Nothing evaluates agents acting over time, reopening decisions, or remediation.
THREAT: HIGH for the historical and epistemic half of the thesis. Memvara ships, as a pip-installable Apache-2.0 library with deterministic, model-free reads, the exact triad the project lists as 'Historical-state fidelity' (EXPERIMENT.md §11): 'what was true then; what it knew then; what it knows now about then'. These map to Memvara's Reading.then / Reading.stated / Reading.now. It also ships 'bitemporal facts' and 'decision provenance' (why(): source episodes + superseded claim), which are listed ingredients of the temporal contestant (§8). Reading.diverged, glossed in the README as 'that is what anyone acting on it then acted on', is a fact-slot-level primitive for the project's step 1, 'detect variance' (a later record changed the basis of an earlier decision). None of these can be claimed as novel. More damaging, its own cross-system benchmark is evidence for the project's null hypothesis on the epistemic-cutoff component. An append-only, time-stamped log with an ingestion-time filter, essentially the project's §7 baseline ('append-only raw event log ... metadata filters for time'), scores 100% on knowledge_time, current state, provenance, change time, change detection and contradiction. Two-clock state helps only on 4 of 47 temporal questions (8.5%), all delayed-knowledge or same-instant corrections, which are the project's event classes C (delayed evidence) and D (retroactive fact). The overall gap is 3 points. Prediction: on historical-state fidelity the project's strong baseline should tie except on C/D-type 'what we now know about then' questions. The project should either include a memvara-style bitemporal store in the baseline as an ablation, or concede that any edge there is narrow. What Memvara does NOT cover, which is the residual space: no engine-written links from facts to assumptions, decisions or artifacts ('derives' exists but 'Nothing in the engine writes one today'), no propagation, and no push trigger. Variance is seen only if someone calls ask() on the right slot and instant. It does no reopening, re-deciding or present-state remediation (steps 3-5 of the project's hypothesis), and its benchmark scores values, not agent actions. It has no execution checkpoints, replay, forks, counterfactual branches or branch provenance, and no prospective machinery at all: no rollouts, future probabilities, backward requirements, intervention-aware forecasts, prevented-future bookkeeping or predicted-vs-realized. Policy and objective versioning is limited to storing preferences or goals as generic claims. Implementation lessons for the project's 'topology integrity' metric: deterministic supersession requires a declared predicate schema (undeclared slots never supersede), and the generic as-of reads apply later endings with hindsight. Only ask()/history(known_at=) are strict.
UNVERIFIED: The session's WebSearch budget was exhausted (200/200), so I could not search the web this lane. I could not check memvara.dev, the hosted service, third-party reviews or citations, or independent replications of the benchmark. Everything rests on the cloned repo, the PyPI JSON and my local runs. I did not verify the LongMemEval/LOCOMO and MemoryBench numbers in docs/BENCHMARKS.md, the hosted /v1 API, or the MCP server. I did not read all 858 files. Capability ratings come from the README, the concept docs, types.py, the core.py read paths, the store DDL, grep for checkpoint/fork/forecast/branch/predict (no agent-level hits), and targeted local scripts. The published benchmark table is labelled memvara 0.11.3; I reproduced the same figures at 0.19.0, but not at 0.11.3. Authorship and affiliation of the maintainers is not stated in the files I read.
RATINGS: 1:partial, 2:yes, 3:yes, 4:partial, 5:no, 6:no, 7:no, 8:no, 9:no, 10:yes, 11:partial, 12:no, 13:no, 14:no, 15:no, 16:no, 17:no, 18:no, 19:yes, 20:no

