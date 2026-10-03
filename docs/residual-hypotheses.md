# Residual hypotheses and disposition

Status: Milestone 2.5, 2026-10-03.

- Evidence labels are defined in
  [research-landscape-2026-10.md §1](research-landscape-2026-10.md#1-method-and-evidence-limits).
- The multi-agent synthesis behind this document (attack, steelman, future
  analysis, proposers, judges, decision, dissent, reconciliation) is archived
  in `research/m2.5-evidence/synth/synthesis.json`.

> **Disposition: A, Stop.** This stops the temporal-architecture program
> (Tesseract and the planned scenario families) on value-of-information
> grounds. It is **not** an EXPERIMENT.md §13 kill:
> - §13 was never run;
> - no real-model contestant has run on anything;
> - whether temporal navigation helps an agent reopen and remediate decisions
>   remains untested.
>
> Two narrow hypotheses are recorded with fixed kill rules, parked and not
> authorized. See §6.

---

## 1. How the candidates were produced and judged

1. **Attack phase.** Five independent analyses:
   - a composition attacker, which tried to reproduce all of NORTH_STAR from
     prior work;
   - a steelman, which looked for the strongest honest residue;
   - a future-side analyst;
   - a benchmark assessor;
   - a UX-vs-primitives analyst.
2. **Proposers.** One per track (historical, prospective, unified). Each
   could propose at most three falsifiable candidates, or none.
3. **Judges.** Three, with different lenses:
   - prior-art distinctness;
   - experimental design;
   - effect-size skepticism.

   Each scored every candidate from 1 to 5 on distinctness, falsifiability,
   cheapness, plausible effect and importance.
4. **Decision maker,** then a **dissenter** told to argue the opposite
   disposition, then a **reconciler**.
   - The dissenter found 7 factual errors and 9 overclaims in the first
     decision. All were corrected.
   - The disposition stayed A.
   - The dissent and the reply are summarized in §6.4.

## 2. All candidates, with judge scores

Scores are distinctness / falsifiability / cheapness / plausible effect /
importance (1-5), then keep (K) or drop (–), from the prior-art,
experimental and skeptic judges in that order.

| id | track | candidate (short) | prior-art judge | experimental judge | skeptic judge | outcome |
|---|---|---|---|---|---|---|
| H1 | historical | A strict-cutoff evaluator attributes faults in the agent's own reopened decisions better than a present self with full information and bitemporal readings, and this improves later decisions | 2/3/2/2/3 – | 2/3/2/2/2 – | 3/4/2/2/2 – | **killed** |
| H2 | historical | Bitemporal decision-premise indexing beats register + TMS arms on class-D backfill | 2/4/2/2/4 K | 3/4/2/2/4 K | 3/4/2/2/3 K | **parked** (§3.1) |
| H3 | prospective | Outcome-feedback memory mis-learns after its own successful interventions; annulled forecast records fix this | 2/4/4/2/2 – | 2/5/4/2/2 K | 4/5/3/1/2 – | **parked, off-objective** (§3.2) |
| H4 | prospective | A per-event prospection step raises recall for implication-only reopenings over an equal-budget re-check pass | 2/3/3/2/2 – | 3/3/3/1/2 – | 3/4/3/1/2 – | **killed** |
| H5 | unified | One time-parameterised `state(seq, kind, query)` interface beats separate tools at equal information | 2/2/4/1/2 – | 2/2/4/1/1 – | 2/3/4/1/1 – | **killed** |

**Why the killed candidates were killed.**
- **H1.** The direction of stage 1 is already shown in three domains:
  - Self-Blinding [abs];
  - clinical temporal masking [abs];
  - ChronoMem [abs].

  Frontier Autolab (2609.36739) [abs-level] already measures the
  historian-judge hindsight confound. `smoke_v1` has 3 world-authored
  reconsiderations, while stage 1 needs at least 30 agent-authored ones.
  Under AER's inference-volatility argument [abs], a masked re-judgement is a
  fresh sample, not testimony.
- **H4.** A positive result would be a prompt policy that the baseline is
  entitled to adopt. "Implication-only" scenarios, defined by the absence of
  any lexical, declared or contradiction link, build CLAUDE.md rule-2 tuning
  into the construct. The evidence also puts the bottleneck at acting on
  evidence already held, not at retrieving it:
  - STALE [abs];
  - KWBench [abs-level];
  - 2601.03905 [abs].
- **H5.** With equal information, unifying the accessor is an interface
  choice. On `smoke_v1` (n=3, every trigger solvable from the current
  workspace plus the current event) both arms are expected to hit the
  ceiling, so a null there cannot be interpreted.

**Steelman candidates that did not survive.**
- **C3: implicit significance detection.** A real gap, but not temporal (§5).
- **C4: executable past self.** Commodity mechanism, and AER's
  non-identifiability argument applies.
- **C5: interrogating simulated future selves.** It breaks down into option
  preservation, information-buying and pre-mortem, all already covered.
- **C6: derived watch conditions from simulated futures.** A prompt-policy
  variant. It cannot catch unanticipated changes.
- **C7: an agent-facing, leakage-audited `state_at` over the whole
  decision-time state.** Engineering: every ingredient exists.
- **C8: interval-uncertain past.** Non-coverage cannot be established, and
  the expected effect is tiny.

## 3. The residual hypotheses (at most three; two survive)

### 3.1 H2: bitemporal decision premises for retroactive facts (historical track)

**Hypothesis.** The setting is retroactive-fact events (EXPERIMENT class D):
at T2 the agent learns that the world changed at T1 < T2, and remediation
requires backfilling effects produced in [T1, T2). The claim:
- **The temporal agent:** records each decision's decision-time ("stated")
  premise readings and flags those that diverge from the corrected ("then")
  readings.
- **The comparison:** the better of two arms:
  - (a) a one-clock as-of log plus an explicit decision register with
    per-premise re-checks;
  - (b) arm (a) plus a dependency/TMS arm whose links are inferred by the LLM.
- **The predicted effect:** higher backfill-remediation success, or higher
  reopen precision at matched recall, with an advantage that grows with the
  number of decisions inside the window and with the lag.

| field | content |
|---|---|
| existing prior art | Bitemporal reads and a "diverged" flag: Memvara `ask()` then/stated/now [code]. XTDB system vs valid time [ns]. Graphiti valid-time reconciliation of backdated facts [code]. Dependency-tracked reopening: PlanFence [abs], Corollary [code], DeepRewind [abs], MemTX [abs]. |
| missing primitive | Engine-written links from decisions to the premise slots they read, so a backdated correction yields the set of affected decisions (Memvara's `derives` links exist but "nothing in the engine writes one today"; `diverged` is a query-time flag). Scoping a backfill window over *decisions* rather than fact values has not been evaluated anywhere. |
| why it might matter | Class-D corrections (a provider changed behaviour weeks ago, a configuration was wrong since T1) are where silent damage accumulates. Correct backfill scope is a reliability and economic property. It is the one regime where prior work found any edge for two-clock state over a timestamped baseline. |
| minimal experiment | 2-3 frozen class-D scenarios with hidden backfill tests and histories longer than the long-context window. T1 is explicit in half the scenarios and indirect in the other half. ≥50% distractors. Negative controls: decisions before T1 on the same slots. TWIST-style surface-matched near-misses and FinalityBench-style twin pairs. Arms: (a), (b), (a) + an off-the-shelf bitemporal store (Memvara, Apache-2.0), and the temporal arm. All arms use a neural embedding model (deviation D1 lifted), with the same model, tools and budgets. Arms (a) and (b) are added through a logged protocol amendment applied to every contestant. ≥3 seeds; paired analysis per in-window decision, clustered by scenario; cost reported next to quality. |
| strong null | max(arm a, arm b): a register with explicit premise slots plus as-of filtering, plus an LLM-inferred TMS. Not naive RAG. |
| kill criterion | Kill if, at 20 in-window decisions and far lag, the paired 95% CI on both backfill success and reopen precision at matched recall includes 0, or if the advantage does not change with window size. Report the effect as negligible in aggregate if a pre-registered census puts class-D-with-backfill below about 10% of reopen triggers. |
| implementation cost | **medium.** New frozen scenarios with hidden tests, long histories, a neural embedder, and three new arms. Every judge rated cheapness 2. |
| prior evidence against | With an explicit T1, a register plus a date filter yields the same backfill set; with an indirect T1, both arms depend on the same LLM inference. Memvara's two-clock lead is 4 of 47 temporal questions, in a self-authored fact-QA corpus with a hashed TF-IDF baseline [code]. TWIST: flat RAG already detects 0.76-0.97 of contradictions [abs]. A win would come from an off-the-shelf store, so it would not make Tesseract a distinct architecture. |

**Status: parked.** Not authorized. It is the first experiment to run if a
re-open trigger fires (§6.5).

### 3.2 H3: prevented-future mis-learning (prospective track; off-objective)

**Hypothesis.** The setting is a world where the agent's own risk-triggered
interventions suppress the harms it forecast. The claim has three parts:
- **The failure mode:** an LLM agent that self-calibrates from realized
  outcomes through reflective memory drifts toward under-warning, although
  the true hazard is constant.
- **The fix that works:** storing intervened-on forecasts as annulled records
  excluded from calibration removes the drift.
- **The fix that does not:** logging the action next to the outcome with a
  one-line causal caveat does not remove it.

| field | content |
|---|---|
| existing prior art | The concept is settled: potential outcomes (Dickerman & Hernán [ns]), Metaculus annulment [ns], "victims of their own success" (Boeken et al. 2403.00886 [unv]; Liley et al. 2010.11530 [unv]), performative prediction [unv]. Outcome-feedback self-calibration for LLM agents: Live-Evo [abs], EpiEvolve [abs], FutureSim feedback [code], all in worlds the agent cannot influence. |
| missing primitive | A typed, annulled forecast record in agent memory: conditioning action or policy version, evidence cutoff, triggering intervention, status annulled / checked / unverifiable. |
| why it might matter | A reliability and safety property for any agent that learns from outcome feedback. Successful prevention could teach it to stop preventing. |
| minimal experiment | A small reactive simulator, not `smoke_v1`. A constant hidden hazard p is signalled by noisy evidence. The agent may apply a costly safeguard; a randomized 15% holdout silently fails the safeguard, which restores positivity. Arms: (A) action logged with no caveat; (B) action logged with a one-line causal caveat; (C) intervened-on forecasts stored as annulled and excluded from calibration. Controls: no memory; random exclusion of the same size as C. ≥60 episodes and ≥5 seeds per arm. Slope of forecast and safeguard rate over episodes. |
| strong null | Arm B: the same reflective memory, with the action logged beside every outcome and a causal caveat in the prompt. Any checkpoint+RAG baseline can log this at negligible cost. |
| kill criterion | Kill if arm A shows no downward drift (95% CI on the slope includes 0), or if arm B removes the drift to within arm C's CI. Stop the whole study if the no-memory control shows that memory does not move forecasts. |
| implementation cost | **small.** A simulator plus three memory variants, no benchmark world. |
| prior evidence against | LLMs reflecting in natural language may avoid the error unprompted. FinalityBench shows LLMs discovering causal gating unprompted [abs]. The decisive B-vs-C contrast is likely null. A positive result would only replicate a predicted consequence in a new model class. |

**Status: parked and off-objective.** It is at most a safety note for
outcome-feedback memories. It is **not** evidence for temporal navigation,
so it cannot justify continuing this project.

### 3.3 The third slot is deliberately empty

The milestone allowed up to three hypotheses. No third candidate survived on
both the thesis and the evidence. The strongest non-survivor is in §5. It is
a real capability gap, but not a temporal one.

---

## 4. Past and future, treated separately

### 4.1 Historical-state hypothesis: killed as a distinct capability

Is there meaningful value, beyond MAGE, FlowState and checkpoint replay, in
maintaining historically faithful epistemic state?

- **The mechanism exists:**
  - known_at / valid_at / as_of, and now/then/stated: Memvara [code], XTDB
    [ns];
  - read-scoping with a post-exposure leakage protocol: ChronoMem [abs];
  - a fork that restores the exact context at t: ActiveGraph [code], Shepherd
    [abs];
  - a blinded replica in place of an "ignore this" instruction: Self-Blinding
    [abs];
  - decision records with plan versions, rejected alternatives and the policy
    in force: AER [abs].
- **Its value over a timestamped baseline is bounded.** In Memvara's own
  benchmark, one-clock append-only RAG equals bitemporal memory on
  `knowledge_time` (100 vs 100). Two clocks matter only where valid time and
  transaction time diverge [code].
- **"Ask the former self" is undermined.** A re-instantiated past self is a
  fresh sample. The contemporaneous record is the testimony (AER [abs]). The
  past self is also untestable in this repository, because decisions are
  world-authored (milestone-2 §0).
- **What remains:**
  - H2, parked;
  - engineering: closing documented cutoff leaks in ActiveGraph fork caches,
    LangGraph replay reading the present Store, Memvara's row-level as-of,
    and KV retention (2608.15939 [abs]).

### 4.2 Prospective-state hypothesis: killed as a distinct capability

Is there meaningful value, beyond world-model lookahead and conventional
planning, in interrogating possible futures and reasoning backward from them?

The concepts must first be separated. The future-side analyst's table:

| concept | definition | canonical prior art | what NORTH_STAR adds | residual |
|---|---|---|---|---|
| forecasting | a distribution over a future outcome given H_t; passive P(Y \| H_t, status quo) vs action-conditioned P(Y^a \| H_t) vs performative | FutureSim, Forecast-Dojo, EpiEvolve, Live-Evo [abs]; potential outcomes [ns]; performative prediction [unv] | tags each forecast with branch, assumptions, policy and horizon; the four-way taxonomy | none conceptual |
| scenario simulation | coherent alternative futures driven by exogenous uncertainty; a strategy stress-tested across them | DMDU/RDM (EMA workbench) [ns]; COVID-19 Scenario Modeling Hub [ns]; FORESIGHT-9, ForecastBench-Sim [abs] | scenarios as branches in the agent's own temporal graph | persisting an ensemble across the agent's life: a modest engineering integration (cf. adaptive policy pathways, unverified here) |
| action-conditioned rollout | predicting ŝ_{t+1..t+K} given a candidate action; imagined or executed | ITP [code]; RAP, WebDreamer, WMA [unv]; Dyna-Think [abs]; prefix branching [abs] | simulating the agent's whole situated state, not only the environment | none for environment rollout; self-state rollout is untested and has a low prior |
| world model | a transition model T(s, a) → s', the component behind rollout | RAP, WMA; WebEvolver, WALL-E 2.0 [abs]; ITP LoRA world model [code]; SIMMER [abs] | implies a self-model (how beliefs and goals evolve) | no agent self-model used for decisions found; absence of evidence |
| planning | search over model-predicted futures with values backed up to the present choice | RAP, LATS [unv]; FLARE (2601.22311) [abs] | calls planning outputs "requirements from future selves" | none |
| model-predictive control | optimise over horizon H, execute the first action, observe, re-plan | RAFA [unv]; LLMPC [lane note] | the §15 "temporal control loop" | none. MPC also argues *against* storing derived requirements when re-planning is cheap |
| backward planning | from a desired or feared terminal condition, work back to dated preconditions | classical goal regression; BAR [abs]; Heitzig & Potham [abs]; SafePred, JANUS, SIMMER [abs] | derived obligations kept as O_t inside temporal state | thin: persistence + re-check = prospective memory + truth maintenance |
| regret analysis | learning-theoretic bounds; minimax regret over scenarios; measured counterfactual regret; pre-mortem | RAFA; Plaut et al. [abs]; RDM; Calibration Is Not Control [abs] | a future self that reports regret | none. Counterfactual regret about one's own interventions hits positivity |
| prospective memory | hold an intention across a delay and execute it on cue or time | PM-Bench [code]; PIS 82.9% Set-F1 [abs]; ChronosBench [abs] | obligations *derived* from simulated futures | very thin; ChronosBench already has agent-formulated triggers |
| future-self UX | dialogue with a simulated future self, framed around identity | Future You [unv]; Simulating Life Paths [abs] (human, affective/persuasive) | the agent's own executable future selves | unoccupied for agents and unsupported by any evidence |

**Residual capability in "deriving present obligations or option-preserving
actions by reasoning backward from simulated future states".**

The claim breaks into five parts. Each already exists:

| part | prior art |
|---|---|
| D: source (a simulated future) | ITP, RAP, WMA, SafePred, SafeCommit |
| R: representation | — |
| P: persistence with provenance | PM-Bench, PIS, DeepRewind's per-commitment trigger, adaptive policy pathways |
| T: trigger re-evaluation | same as P |
| A: resulting action | RAFA, AUP, SafeCommit |

| prior art | D | P | T | A | pre-empts |
|---|---|---|---|---|---|
| ITP [code] | one greedy imagined trajectory, adaptive K | no (dropped after each step) | no | next action | simulate futures, act from the present |
| RAP / LATS / WebDreamer / WMA [unv] | several imagined branches, searched | episode only | no | select or veto (WMA: irreversible-harm avoidance) | multiple futures; feared-future veto |
| RAFA [unv] | long-horizon plan | feedback only | by re-planning | first action | the §15 loop |
| relative reachability / AUP [unv]; Heitzig & Potham [abs] | distribution over future goals | no | no | option-preserving action | §13 optionality |
| SafePred / JANUS / SIMMER [abs] | feared delayed future | no | no | block or re-plan | "future sends warnings backward" |
| SafeCommit / LCPI [abs] | retained plausible worlds | no | no | act, probe or fallback | robust option-preserving choice |
| DeepRewind [abs, code] | one-step world-model prediction of a commit | yes, within a run | per-commitment trigger + monitor | gate; roll back later | the derived reopen trigger (organic firing absent in released code) |
| PM-Bench / PIS / ChronosBench | given or dialog-derived intentions | yes | yes | execute when due | the P and T machinery |

What is missing is one system combining D (from a simulated future) with P
and T, which acts by reopening executed decisions.

- **That is integration.** A re-check prompt over a stored list matches it
  for short lists: the repo baseline's summary already tracks "open, parked
  or blocked work and what it is waiting for".
- **Typed triggers plus TMS links match it at scale** (PIS, PlanFence).
- **Re-planning from the present matches it** when re-planning is cheap
  (MPC), and also catches conditions nobody anticipated.

The only honest residue is "future-mediated relevance": an event bears on a
past decision only through a simulated future. Its prior is low:
- agents rarely use foresight (2601.03905 [abs]);
- Forecast-Dojo's carried notebook does not consistently help [abs];
- FinalityBench shows LLMs finding gating unprompted [abs].

It also cannot be tested in the current harness. The `smoke_v1` event stream
does not react to the agent, decisions are world-authored, and the only
actions are reopen and note.

**The prevented future.** A forecast leads to an intervention, so the
forecast outcome never happens.

- **Formal treatment (settled).** The forecast target is the potential
  outcome Y^{a0} under a named strategy. If the agent takes a1, Y^{a0} is
  *missing, not falsified*. Practice annuls the unrealized branch:
  - Metaculus Conditional Pairs ("It is not scored") [ns];
  - the ANNULLED status in `forecasting-tools` [ns];
  - decision markets;
  - scenario-conditional scoring at the COVID-19 Scenario Modeling Hub [ns].
- **Reflexive tier:**
  - performative prediction [unv];
  - fixed-point scoring [unv];
  - counterfactual oracles [unv];
  - clinical "victims of their own success" (Boeken et al. [unv]: "naive
    retraining ... underestimates the risk, due to effective workings of the
    previous model").
- **What the literature adds against NORTH_STAR §8: positivity.** Take a
  deterministic policy "intervene iff f(H) > τ".
  - For every history where the forecast fires, P(A = a0 | H) = 0, so
    E[Y^{a0} | H] is not identified from the agent's own data. That is
    exactly the region where the forecast matters.
  - "Prevented" and "false alarm followed by a harmless intervention" are
    observationally identical.
  - NORTH_STAR guards against one error (prevention mistaken for failed
    prediction). It leaves the symmetric, self-serving error open:
    failed prediction relabelled as prevention, which is incentive-compatible
    for a self-scoring agent.
- **Remedies, none agent-specific:**
  - randomized withholding or holdouts;
  - a resettable simulator or fork (software worlds are favourable here: a
    feared failing test can be executed in a sandbox, which any contestant
    can already do with A1 `read_at` plus A2 `run_command`);
  - delayed external evidence (event class C);
  - identification under assumptions (Boeken).
- **Left for agents:**
  - bookkeeping (typed averted-forecast records, schema work);
  - one failure-mode study (H3);
  - evaluation design: an evaluator that controls the world has positivity,
    e.g. FinalityBench twin pairs and ForecastBench-Sim paired worlds.

**Future-self UX.**
- **Human evidence:** affective (Future You: lower anxiety, higher
  future-self continuity) and persuasive (Simulating Life Paths: one-sided
  avatars shift choices). Neither measures decision quality.
- **Agent evidence:**
  - none positive for interrogating one's own future self;
  - negative for foresight use (2601.03905);
  - mixed for ITP's single pasted foresight (it helps on ALFWorld and loses
    to RAP on Qwen3 ScienceWorld-unseen).
- **A future "self" for a stateless model** is the same weights given a
  described future state. It adds only rollout computation, a forked memory
  copy (commodity) or isolation.
- **The decisive ablation:** a single-prompt pre-mortem against a
  role-separated, world-model-driven, forked copy, at equal budget. Nothing
  should be built before that ablation, and before a benchmark where the
  agent makes its own forward-looking decisions.

**Verdict.** The concepts and the mechanisms are prior art. H3 is a narrow,
off-objective reliability study. "Future-mediated relevance" has a low prior
and cannot be tested in the current harness.

### 4.3 Unified-state-space hypothesis: killed as a distinct abstraction

Does putting historical, current, counterfactual and prospective states
behind one abstraction create a measurable advantage over composing
specialized mechanisms?

At equal information, unification can differ from composition in only four
ways:

- **(a) The agent's interface and affordances.** An interface effect, tested
  by H5. That test cannot be interpreted on `smoke_v1`, and the evidence puts
  the bottleneck in judgement, not access (STALE, 2601.03905).
- **(b) Joins across kinds of state.** With equal information, an explicit
  join in a composed stack is identical by construction. What is left
  collapses into (a), or into "future-mediated relevance" (§4.2).
- **(c) Reliability at the seams, i.e. cutoff leaks between stores.** A
  single fold over one log removes these by construction (Shepherd), and a
  composed stack fixes them by configuration. This is engineering.
- **(d) Cost.** Untested. Forecast-Dojo's notebook reduced research cost
  [abs], but against re-retrieval, which the §7 baseline already does.

**Verdict.** ActiveGraph already unifies historical, actual and
counterfactual state. Its deep read concludes that the unified claim reduces
to "ActiveGraph plus a planner". No channel was found that could separate
unification from composition at equal information.

---

## 5. The real gap that is not a residual hypothesis

**Organic detection.** The capability: noticing, unprompted, that a later
event changes the significance of an earlier decision when the dependency was
never recorded and no fact is contradicted. It is EXPERIMENT.md §1, step 1
("detect variance").

**Evidence that nothing covers it:**
- Corollary: a later fact on a different key left the decision in force
  (probe) [code].
- DeepRewind's organic contradiction path fired rollback 0 times (probe)
  [code].
- Graphiti invalidates only on contradiction [code].
- Nothing writes Memvara's `derives` links [code].
- No benchmark scores per-decision reopen recall and precision (benchmark
  sweep).

**Why it is not a temporal hypothesis.** As-of reads, diffs, forks and
bitemporal validity act on state that someone has already chosen to look at;
they do not create links nobody recorded. Every candidate fix is available to
a non-temporal arm:
- extracting assumptions when the decision is made;
- inferring relevance when the event arrives;
- re-checking the decisions in force.

Nearby evidence locates the failure in acting on evidence the agent already
holds:
- STALE: "a pervasive gap between retrieving updated evidence and acting on
  it" [abs];
- KWBench [abs-level].

This is an argument from decomposition, not a measurement. It could be the
object of a separate program, "commitment standing under late information"
(NORTH_STAR_V2_PROPOSAL.md §6). It does not support continuing a
temporal-architecture project.

---

## 6. Disposition

### 6.1 Decision: A, Stop

Of the four options (A Stop; B Observe; C one cheap experiment; D Continue),
the decision is **A**. Existing systems cover the meaningful capability, and
there is no strong residual hypothesis.

1. **The mechanisms are covered.** Of 47 NORTH_STAR / EXPERIMENT items
   (research-landscape §4):
   - 15 have no residual;
   - 9 are terminology;
   - 1 is UX;
   - 18 are integration;
   - 2 are untested measurable effects;
   - 2 are capability gaps, neither attributable to temporal navigation.
2. **No strong residual hypothesis exists.**
   - All three judges scored every candidate's plausible effect at 2 or
     lower.
   - The only hypothesis on the thesis that all judges kept, H2, is medium
     cost and predicts a tie by its own mechanism.
   - H3 is cheap and clean but off-objective.
3. **Attribution.** A §13 "continue" result against the frozen §7 baseline
   could not be credited to temporal navigation without register,
   dependency/TMS and typed-intention arms. EXPERIMENT.md §8 bundles
   non-temporal structure (decision provenance, causal edges) with
   time-indexing, and nearby evidence shows non-temporal structure producing
   large effects:
   - StateMemBench: +15 to +32 points to "state structure rather than added
     context" [abs];
   - PlanFence: 30 of 30 workflows vs every task acting on the obsolete plan
     [abs];
   - PIS: 82.9% [abs].

   This is not a reinterpretation of CLAUDE.md rule 4, which only requires the
   baseline to be "strong and configurable". Adding such arms would need a
   logged amendment applied to every contestant.
4. **Effect-size evidence is nearby, not matched, and leans toward the
   null.** See research-landscape §5. None of it measures decision reopening.

### 6.2 Why not B, C or D

- **D (Continue)** requires a clearly differentiated capability with
  evidence. There is none.
- **C (one cheap experiment)** requires *exactly one* residual hypothesis
  that can be tested *cheaply*.
  - H2 is not cheap.
  - H3 is cheap but does not test the thesis.
  - The obvious cheap run, a real-model `smoke_v1` with baseline presets plus
    register and Memvara arms, does not test temporal navigation either:
    - every `smoke_v1` trigger can be solved from the current workspace plus
      the current event (benchmark-reuse-assessment §3);
    - A1 already gives every contestant as-of reads and diffs;
    - n=3.

    Saturation and missed visible evidence both point to diligence and
    register arms, not to time-indexing.
- **B (Observe)** is the closest alternative. B requires an *interesting
  conceptual gap that is too weak to implement now*. The one interesting gap
  (§5) is not a gap in *temporal navigation*. It is a judgement and relevance
  gap that non-temporal arms can address. In practice A with explicit re-open
  triggers (§6.5) differs little from B. A reasonable reviewer could choose
  B.

### 6.3 Sunk-cost check

- **Invested so far:**
  - Milestones 1-2, roughly 14k lines of harness, evaluator, runtime,
    baseline and gateway code, with tests, CI and two adversarial reviews;
  - a frozen `smoke_v1`;
  - this review.

  None of it entered the decision.
- **Counterfactual test:** with no repository and the current evidence,
  would one start Tesseract or author class-D families today? No. One would
  pre-register H2 and build nothing.
- **Marginal cost is not sunk cost.** The harness makes a real-model run
  cheap. That run still cannot discriminate time-indexing, so its low price
  does not change the disposition.
- **Reverse check:** A was not chosen to avoid work. The harness stays
  intact, H2 has a frozen design and kill rule, and the re-open triggers can
  actually fire.

### 6.4 The dissent, and why it did not change the disposition

The dissenter argued for **C**, along four lines:

1. CLAUDE.md says "test, rather than assume", and the §13 kill rule is
   empirical. A stops without running it.
2. A rested on a reading of rule 4 that would move the temporal contestant's
   components into the baseline. That would be a protocol change made after
   the attack phase.
3. The nulls cited measure different constructs (fact QA, forecasting,
   recall), not decision reopening.
4. Forecast-Dojo's cost reduction (median −24%, per a third-party full-text
   reading) was omitted, although §13 also counts cost.

**Accepted:**
- All factual corrections. For example: Memvara's benchmark is
  self-authored; Trellis is a design only; Shepherd's public library lacks
  replay; DeepRewind's organic path never fired; DreamBench-SWE does not show
  parity (Mem0 reached 97/180).
- The rule-4 argument is **withdrawn** and replaced by the attribution
  argument in §6.1(3).
- This stop is **not** a §13 verdict, and the record says so.

**Not accepted: C.**
- The proposed cheap run does not test a temporal-navigation hypothesis
  (§6.2).
- Forecast-Dojo's cost result compares carried state with re-retrieval, which
  the §7 baseline already has, so it yields no cost hypothesis specific to
  time-indexing.

**What the dissenter said would change its mind:**
- matched null evidence on decision reopening;
- a released benchmark showing parity between time-indexed and register or
  TMS arms.

Neither exists. The first appears as trigger (a) in §6.5.

### 6.5 Re-open triggers

Any one of these reopens the question. H2 is then the first experiment to
run.

- **(a)** A published or reproducible matched result on reopening or
  remediating decisions in which a time-indexed arm (bitemporal, as-of or
  versioned decision state, off-the-shelf allowed) beats the better of a
  decision-register arm and a dependency/TMS arm, with a CI excluding 0.
- **(b)** A result in which whole-state temporal navigation (as-of and fork
  over the agent's full decision-time state) beats a baseline that already
  has a register, TMS and a bitemporal store. This would justify
  reconsidering Tesseract as an architecture.
- **(c)** Full-text evidence that dependency tracking fails exactly where
  time-indexing succeeds. Candidates: the DeepRewind paper body, or the
  recovery evaluation Corollary's README says it wants to build.
- **(d)** Evidence that detecting implicit links improves with time-indexed
  state rather than with relevance inference or re-check policies.

### 6.6 What this disposition is not

- **Not a claim that temporal navigation was shown not to help.**
- **Not a §13 kill.** §13 was never run, and no real-model contestant has
  run.
- **Not a judgement on the infrastructure.** The harness, evaluator, runtime
  and model gateway are reusable (m2.5-decision-record.md).
- **Not authorization** for any experiment, scenario family, or Tesseract
  code.
