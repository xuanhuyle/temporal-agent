# Sweep: backward planning, option preservation, irreversibility, regret, DMDU

Lane: backward-optionality. Date: 2026-10-03.

## Method and evidence caveat (read first)

- WebSearch was unavailable for this lane. All 4 attempted calls returned "this session has used its web search
  budget (200 of 200 WebSearch calls)". A broad host-reachability probe was refused by the sandbox permission
  classifier, so it was not retried by any other route.
- Evidence comes from:
  - [DAILY-ABS]: the abstract text in a local clone of `CSQianDong/Awesome-arXiv-Daily-Reporter`, which a sibling lane
    had already put under `repos/pf/daily`. It holds daily cs.AI and cs.CL arXiv listings with titles, authors, PDF links
    and full abstracts, from Dec 2024 to 1 Oct 2026. I parsed it into 117,831 unique records
    (`scratchpad/lit/bo/daily.json`, with the scripts `bo/index.py`, `bo/q.py` and `bo/show.py`) and ran regex queries
    over titles and abstracts. Limitation: only cs.AI and cs.CL are covered, so cs.LG/cs.RO-only papers and anything
    before Dec 2024 are missing.
  - [REPO]: README or source text from repositories cloned into `scratchpad/lit/repos/bo/`:
    alexander-turner/attainable-utility-preservation, google-deepmind/deepmind-research (sparse: side_effects_penalties),
    google-deepmind/ai-safety-gridworlds, PartnershipOnAI/safelife, quaquel/EMAworkbench, ryoungj/ToolEmu. I also read
    the sibling clone `repos/cf/agentification_RAFA_code`.
  - [LIST-ABS]: an abstract stored in `repos/cf/lists/AGI-Edgerunners_LLM-Agents-Papers/parsed_v5/*.json`.
- Every quote below is copied verbatim from those sources. Anything taken from memory is marked UNVERIFIED.

## Queries run

Attempted but not executed:
1. WebSearch [arxiv] "backward planning large language models goal regression 2025" (budget exhausted)
2. WebSearch [arxiv] "LLM agent irreversible action detection benchmark 2025" (budget exhausted)
3. WebSearch [arxiv] "relative reachability side effects penalizing Krakovna" (budget exhausted)
4. WebSearch [arxiv] "attainable utility preservation conservative agency Turner" (budget exhausted)

Executed locally. These are regex queries over the 117,831 daily abstracts unless marked otherwise.
5. `backward (planning|chaining|reasoning|search)|goal regression|regression planning|reverse planning` AND `LLM|agent`
6. `irreversib|reversib|undoab|cannot be undone|point of no return` AND `agent|LLM` (all fields)
7. title: `irreversib|reversib|undo|option value|optionality|preserv* options|reachab`
8. `anticipated regret|minimax regret|regret minimi|regret-aware|regret theory|future regret`
9. `deep uncertainty|robust decision.making|adaptive (policy )?pathway|signpost|tipping point|scenario planning|real options|backcasting|pre-?mortem|foresight`
10. `side.effect|impact (regulari|measure|penalt)|attainable utility|relative reachability|low.impact|conservative agen`
11. grep the cloned curated lists (15 lists) for `backward|goal regression|irreversib|side effect|regret|reachab|safe exploration|deep uncertainty|premortem|backcast`
12. JSON abstracts (AGI-Edgerunners parsed_v5): `backward planning|goal regression|irreversib|side effect|reversib|regret|option value|deep uncertainty`
13. `model.predictive control|receding.horizon|reason for future` AND `LLM`
14. `means-ends|precondition|prerequisite|necessary conditions` AND `backward|goal|future|planning`
15. `empowerment|power-seeking|keep options|option preserv|optionality|least commitment|deferred commitment`
16. `obligation|commitment tracking|prospective memory|deadline` (titles) AND `agent|LLM`
17. `contingency plan|anticipat* failure|pre-?mortem|feared|what could go wrong|proactive risk` AND `agent|LLM`
18. `safe exploration|reversibility|irreversible (state|action)|recoverab|reset-free` AND `RL|agent|LLM`
19. abstracts that mention irreversibility, an agent, and benchmark/detect/predict, with the matching sentence extracted
20. `deep uncertainty|Knightian|robust (decision|policy)|scenario discovery|stress-test` AND `LLM|agent`
21. `backward induction|working backward|reason backward from|from the goal` AND `LLM|agent`
22. `forward and backward|bidirectional plan` (LLM backward-planning papers from before 2025)
23. `regression (search|planning)|goal regression|weakest precondition|backward search` (classical)
24. `hindsight (goal|experience|relabel)|goal-conditioned` AND `LLM`
25. `value of waiting|wait or act|when to act|defer decision|premature commitment|commit too early`
26. `future self|future selves|self-continuity` AND `agent|LLM`; `shield|look-ahead guard|predictive guardrail|consequence-aware`
27. `change impact analysis|future-proof|architecture decision`; `delayed (consequence|effect|harm|risk)|emerge with a delay`
28. reversibility estimation inside agent planning (sentence extraction, filtered)
29. `contingent plan|robust plan|multiple futures|plausible worlds|hedging` AND `LLM|agent`
30. `averted|prevented (outcome|future)|self-defeating|performative prediction`
31. Repo greps: the DeepMind side_effects_penalties README; AUP README; ai-safety-gridworlds README (`side effect|irreversib`);
    SafeLife README; EMAworkbench docs (`deep uncertainty|robust decision making|adaptive policy pathways|signpost|tipping`);
    ToolEmu prompts (`irreversib|reversib`). PyPI JSON lookups for `adaptation-pathways` returned nothing.

---

## Works (ranked by threat to this lane's claim)

### 1. SafePred: A Predictive Guardrail for Computer-Using Agents via World Models (arXiv 2602.01725, Feb 2026). Threat: HIGH
- URL: https://arxiv.org/abs/2602.01725 [DAILY-ABS]. Authors: Yurun Chen, Zeyi Liao, Ping Yin, Taotao Xie, Keting Yin, Shengyu Zhang.
- Verbatim: "seemingly reasonable actions can lead to high-risk consequences that emerge with a delay (e.g., cleaning logs
  leads to future audits being untraceable), which reactive guardrails cannot identify within the current observation space."
- Verbatim: "we propose a predictive guardrail approach, with the core idea of aligning predicted future risks with current decisions."
- Verbatim: "Decision optimization: translating predicted risks into actionable safe decision guidances through step-level
  interventions and task-level re-planning."
- Capabilities: 12 future_state_rollout, 15 backward_requirements (feared future to present pruning/replanning),
  11 (risk semantics), partly 13.
- Why it matters: this is "derive present actions from feared, delayed futures" for LLM agents, published with numbers
  ("over 97.6% safety performance"). Its delayed-consequence example is the same shape as the project's
  "earlier decision gains significance later" case.

### 2. SafeCommit: Certifying When Memory-Grounded Agents May Safely Act (arXiv 2608.04289, Aug 2026). Threat: HIGH
- URL: https://arxiv.org/abs/2608.04289 [DAILY-ABS]. Authors: Mayur Akewar, Ravi Ranjan.
- Verbatim: "A central failure mode is premature commitment: an agent acts before resolving whether its memory grounding
  is stale, conflicting, incomplete, or corrupted."
- Verbatim: "The layer constructs a calibrated set of plausible latent worlds from memory, observations, tool outputs,
  provenance, and policy constraints. It permits a side effectful action only when a conformal action certificate shows
  that the action is safe in every retained world. Otherwise, it selects a low-side-effect probe that targets the worlds
  blocking certification, or returns a conservative fallback."
- Capabilities: 10, 11, 13 multiple_prospective_branches (plausible worlds), 14 (calibrated coverage),
  15 (option-preserving probe or fallback chosen from the worlds that block action).
- Why it matters: this is robust decision making (act only when safe across all retained worlds, otherwise buy
  information cheaply) turned into an LLM-agent runtime with a formal bound. It takes the "option-preserving action"
  half of the thesis.

### 3. DeepRewind: Predicting and Repairing Premature Commitments in Deep Research Agents (arXiv 2609.36344, Sep 2026). Threat: HIGH
- URL: https://arxiv.org/abs/2609.36344 [DAILY-ABS]. The exec-state sibling lane also lists it.
- Verbatim: "represents the agent's evolving epistemic state as a typed graph of sources, evidence, claims, hypotheses,
  assumptions, commitments, plans, and drafts. Before accepting an intermediate conclusion, a prompt-based world model
  predicts its impact and estimates reversibility based on hypothesis narrowing, information loss, recovery cost, and
  contradiction-trigger coverage. A binary controller blocks risky commitments, while a consistency monitor performs
  dependency-aware rollback when later evidence invalidates them."
- Capabilities: 10, 11, 12, 15 (reversibility-gated commitment), 5/6 (rollback), 9 (dependency edges).
- Why it matters: it estimates reversibility before committing and reopens commitments when later evidence invalidates
  them. That is the project's benchmark behaviour, but for epistemic commitments only, not external side effects.

### 4. FinalityBench: An Effect-Level Benchmark for Agent Decisions Under Delayed and Conflicting Financial Finality (arXiv 2609.04706, Sep 2026). Threat: HIGH (benchmark design) / MEDIUM (thesis)
- URL: https://arxiv.org/abs/2609.04706 [DAILY-ABS]. Author: Abhishek Sharma.
- Verbatim: "An agent resolving the exception must decide whether to ship goods, re-submit a capture, refund or wait,
  knowing some of those cannot be undone."
- Verbatim: "It keeps a hidden canonical event log and derives each system's view from a separately faulted delivery stream"
- Verbatim: "45 twin pairs (90 tasks): tasks whose four system views are identical at the decision instant, whose
  authoritative probes both return unknown, and whose eventual correct dispositions differ."
- Verbatim: "A runtime gating irreversible actions on an authoritative finality probe reaches 85.4% ... Language models
  reach the same exact rate as the hand-written gate on a stratified subset, lose about twice as much money, and
  discover the finality-gating strategy without being told it."
- Capabilities: 1 (hidden canonical log), 11, 15 (wait or gate before irreversible effects), 19 (system views as of the
  decision instant).
- Why it matters: it is an executable, effect-graded benchmark with a hidden event log, delayed events, irreversible
  actions and twin-pair indistinguishability. That is very close to the project's benchmark machinery. The finding that
  LLMs discover finality gating unprompted weakens the case that explicit temporal machinery is needed.

### 5. Penalizing side effects using stepwise relative reachability / Avoiding Side Effects By Considering Future Tasks (Krakovna et al., arXiv 1806.01186; NeurIPS 2020). Threat: MEDIUM-HIGH (foundational)
- URLs: https://arxiv.org/abs/1806.01186 and code https://github.com/google-deepmind/deepmind-research/tree/master/side_effects_penalties [REPO]
- Verbatim (README): "we give the agent a general penalty for impacting the environment, defined as a deviation from some
  baseline state. For example, a reversibility penalty measures unreachability (deviation) of the starting state (baseline)."
- Verbatim (README): "In our latest paper "Avoiding Side Effects By Considering Future Tasks" by Krakovna et al (NeurIPS
  2020), the agent receives an auxiliary reward for preserving the ability to perform future tasks. This approach is
  equivalent to relative reachability with an inaction baseline in deterministic environments."
- Baselines in code: "starting state (`start`), inaction (`inaction`), stepwise inaction with rollouts (`stepwise`)".
- The arXiv id of the NeurIPS 2020 paper was not confirmed (UNVERIFIED: 2010.07877).
- Capabilities: 12 (rollouts for the stepwise baseline), 13 (a distribution over possible future tasks), 15 (option
  preservation derived from hypothetical future goals), 8 (inaction counterfactual baseline).
- Why it matters: "preserve the ability to achieve possible future goals, measured against a counterfactual baseline"
  is option-preserving action from imagined futures, formalised and implemented since 2018-2020.

### 6. Conservative Agency via Attainable Utility Preservation (Turner et al., arXiv 1902.09725). Threat: MEDIUM (foundational)
- URL: https://arxiv.org/abs/1902.09725 ; code https://github.com/alexander-turner/attainable-utility-preservation [REPO]
- Verbatim (README): "A test-bed for the Attainable Utility Preservation method for quantifying and penalizing the change
  an agent has on the world around it."
- Related [REPO]: AI Safety Gridworlds (https://arxiv.org/pdf/1711.09883.pdf) item 2 says: "Avoiding side effects: How can
  we incentivize agents to minimize effects unrelated to their main objectives, especially those that are irreversible";
  SafeLife (https://arxiv.org/abs/1912.01217) is a side-effects benchmark.
- Capabilities: 15 (preserve attainable value for auxiliary goals), 8 (counterfactual inaction), 13.
- Why it matters: option value over a set of auxiliary future objectives is an established safety abstraction. The
  project's "option-preserving actions" needs to be positioned against it.

### 7. JANUS: Foreseeing Latent Risk for Long-Horizon Agent Safety (arXiv 2607.19913, Jul 2026). Threat: MEDIUM-HIGH
- URL: https://arxiv.org/abs/2607.19913 [DAILY-ABS]
- Verbatim: "trains guards to anticipate delayed risks from partial trajectories ... learns a shared policy with two coupled
  tasks: an anticipation task that forecasts safety-relevant futures and an adjudication task that decides safety from both
  the observed prefix and anticipated future. The two tasks are jointly optimized with CoAA-RL, which rewards forecasts by
  their utility for downstream safety judgment."
- Capabilities: 12, 15 (feared future to present block), partial 16/17 (forecasts are scored by decision utility, not by
  realised accuracy).
- Why it matters: it trains "simulate the feared future, then constrain the present". Scoring forecasts by their
  usefulness to the decision, not by whether they came true, partly overlaps the "prevented futures not scored as wrong"
  idea.

### 8. SIMMER: Benchmarking Latent Failures in LLM Executable Planning with a World Model (arXiv 2606.14574, Jun 2026). Threat: MEDIUM
- URL: https://arxiv.org/abs/2606.14574 [DAILY-ABS]
- Verbatim: "Unlike immediate failures that trigger instant feedback at execution time and enable timely correction, latent
  failures do not immediately halt plan execution but silently compromise goal achievement. In severe cases, they cause
  irreversible harm."
- Verbatim: "explicit state reasoning via counterfactual foresight simulation can reduce latent failures by up to 72% and
  irreversible cases by up to 75%"
- Capabilities: 12, 8, 15 (partial), plus a symbolic world model that flags latent hazards.
- Why it matters: it is a benchmark whose central construct is an early decision that only fails later, and foresight
  simulation is shown to fix much of it. The project's "notice and remediate" framing has to separate itself from this.

### 9. Distinguish or Homogenize: Last-Chance Policy Identification and Risk-Budgeted Recovery under Irreversible Resource Depletion (arXiv 2609.36741, Sep 2026). Threat: MEDIUM
- URL: https://arxiv.org/abs/2609.36741 [DAILY-ABS]
- Verbatim: "an agent can spend resources to distinguish among latent fault models, or to change the system state so that the
  remaining models admit a common acceptable continuation--at which point further diagnosis becomes unnecessary."
- Verbatim: "correctness is evaluated at the state the agent reaches rather than at the initial state. The Last Identifiable
  Margin (LIM) marks the feasibility boundary between distinguishing and homogenizing."
- Verbatim: "A sham control--cost-matched actions that preserve model incompatibility--eliminates the gain entirely"
- Capabilities: 11, 13, 15 (choose present actions that keep all candidate futures acceptable), 12.
- Why it matters: it formalises option-preserving action under irreversibility, with a last-chance boundary much like the
  DMDU "tipping point". It is not LLM-specific.

### 10. Reason for Future, Act for Now (RAFA) (Liu et al., arXiv 2309.17382, ICML 2024). Threat: MEDIUM (foundational for LLMs)
- URL: https://arxiv.org/abs/2309.17382 ; code https://github.com/agentification/RAFA_code [REPO + LIST-ABS]
- Verbatim (abstract): "plans a future trajectory over a long horizon ("reason for future"). At each step, the LLM agent takes
  the initial action of the planned trajectory ("act for now"), stores the collected feedback in the memory buffer, and
  reinvokes the reasoning routine to replan the future trajectory from the new state."
- Verbatim: "the novel combination of long-term reasoning and short-term acting achieves a $\sqrt{T}$ regret."
- Related [DAILY-ABS]: LLMPC https://arxiv.org/abs/2501.02486: "examines these prompting techniques through the lens of model
  predictive control (MPC)."
- Capabilities: 12, 10 (posterior over the environment), 11, 18 (feedback updates the posterior).
- Why it matters: "simulate the future, act from the present, replan" is receding-horizon control with a regret guarantee
  for LLM agents. "Act from a defined present" is not new.

### 11. Exploratory Modeling workbench / Robust Decision Making under deep uncertainty (Kwakkel, TU Delft). Threat: MEDIUM (conceptual)
- URL: https://github.com/quaquel/EMAworkbench [REPO]; docs https://emaworkbench.readthedocs.io/en/latest/index.html
- Verbatim (README): "exploratory modeling aims at offering computational decision support for decision making under deep
  uncertainty and robust decision making."
- Verbatim (docs, directed-search tutorial): "Directed search is most often used to search over the decision levers in order
  to find good candidate strategies. This is for example the first step in the [Many Objective Robust Decision Making process]"
- The Dynamic Adaptive Policy Pathways concepts (signposts, adaptation tipping points; Haasnoot et al. 2013) were not
  confirmed in any fetched source and are UNVERIFIED here. The repo docs do not use those words.
- Capabilities: 13 (ensembles of futures), 12, 11, 15 (scenario discovery finds the conditions under which a strategy fails,
  which become the requirements a robust strategy must meet).
- Why it matters: deriving present policy from an ensemble of simulated futures, with the failure conditions found
  automatically, is a mature methodology with tooling. The project's "backward requirements from feared futures" is DMDU
  applied to LLM agent state.

### 12. Why Reasoning Fails to Plan: FLARE (arXiv 2601.22311, Feb 2026). Threat: MEDIUM-LOW
- URL: https://arxiv.org/abs/2601.22311 [DAILY-ABS]
- Verbatim: "locally optimal choices induced by step-wise scoring lead to early myopic commitments that are systematically
  amplified over time and difficult to recover from. We introduce FLARE (Future-aware Lookahead with Reward Estimation) as a
  minimal instantiation of future-aware planning to enforce explicit lookahead, value propagation, and limited commitment in
  a single model, allowing downstream outcomes to influence early decisions."
- Capabilities: 12, 15 (value propagated back from the future to early decisions).
- Why it matters: it gives empirical evidence that backward value propagation and limited commitment fix early myopic
  commitments in LLM agents.

### 13. BAR: A Backward Reasoning based Agent for Complex Minecraft Tasks (arXiv 2505.14079, May 2025). Threat: MEDIUM-LOW
- URL: https://arxiv.org/abs/2505.14079 [DAILY-ABS]
- Verbatim: "we leverage backward reasoning and make the planning starting from the terminal state, which can directly achieve
  the task goal in one step. Specifically, we design a BAckward Reasoning based agent (BAR). It is equipped with a recursive
  goal decomposition module, a state consistency maintaining module and a stage memory module"
- Related [DAILY-ABS]: Goal-Mem https://arxiv.org/abs/2605.12213 ("performs explicit backward chaining from the user's
  utterance as a goal"); classical goal regression is still active: https://arxiv.org/abs/2511.11095 ("perform goal
  regression on the resulting plans, and lift the corresponding outputs to obtain a set of first-order Condition -> Actions rules").
  UNVERIFIED (not found locally): Ren et al. 2024 "Thinking Forward and Backward: Effective Backward Planning with LLMs".
- Capabilities: 15 (regression from the goal to subgoals and preconditions).
- Why it matters: backward planning with LLMs exists as a planning technique. It works from a desired terminal state, not
  from a feared one, and is not persistent over time.

### 14. Asking for Help Enables Safety Guarantees Without Sacrificing Effectiveness (Plaut, Lievano-Karim, Russell; arXiv 2502.14043). Threat: LOW-MEDIUM
- URL: https://arxiv.org/abs/2502.14043 [DAILY-ABS]
- Verbatim: "Most reinforcement learning algorithms with regret guarantees rely on a critical assumption: that all errors are
  recoverable. ... We prove that any algorithm that avoids catastrophe in their setting also guarantees high reward (i.e.,
  sublinear regret) in any Markov Decision Process (MDP), including MDPs with irreversible costs."
- Capabilities: 11, 15 (defer or ask before irreversible steps).
- Why it matters: it is the theory for irreversibility plus regret. Deferring to help before irreversible steps is the
  formal answer to "how should an agent act given feared irreversible futures".

### 15. Model-Based Soft Maximization of Suitable Metrics of Long-Term Human Power (Heitzig, Potham; arXiv 2508.00159). Threat: LOW-MEDIUM
- URL: https://arxiv.org/abs/2508.00159 [DAILY-ABS]
- Verbatim: "power as the ability to pursue diverse goals ... considers a wide variety of possible human goals. We derive
  algorithms for computing that metric by backward induction or approximating it via a form of multi-agent reinforcement
  learning from a given world model."
- Capabilities: 13, 15 (preserve the options others hold over a goal distribution, by backward induction).
- Why it matters: it is a recent agentic-AI objective that is literally option preservation computed backward from futures.

---

## Also seen (lower threat or covered by other lanes)

- DreamGuard https://arxiv.org/abs/2608.05695: "predicts future latent states from which DreamGuard derives immediate-hazard and prefix-risk evidence".
- SeerGuard https://arxiv.org/abs/2607.15550: "anticipating likely outcomes to identify risks before they are executed".
- ARTIS https://arxiv.org/abs/2602.01709: "decouples exploration from commitment by enabling test-time exploration through simulated interactions prior to real-world execution".
- SafeMCP https://arxiv.org/abs/2606.01991: "constrains tool acquisition via predictive reasoning regarding future safety risks" (power-seeking).
- TRACES https://arxiv.org/abs/2605.27690: prefix-level trajectory risk states.
- EvoUndo https://arxiv.org/abs/2608.28363: "verifying recoverability of model-generated self-modifications across counterfactual states".
- The Irreversibility Budget https://arxiv.org/abs/2609.00275: "a cumulative account of residual value-at-risk that a trusted runtime maintains for each principal".
- Time-Consistent Counterfactual Actuarial Runtime https://arxiv.org/abs/2605.26508: "irreversible-authority premium".
- REVERSAL-BENCH https://arxiv.org/abs/2609.17745: "reset-free agents are consistently absorbed into irrecoverable states as rho increases".
- ToolEmu https://arxiv.org/abs/2309.15817 [REPO]: its safety evaluator says "Severe risky outcomes entail consequences that are significant and often irreversible."
- AgentAbstain https://arxiv.org/abs/2607.10059: "post-hoc abstention, in which agents execute irreversible actions before recognizing abstention triggers".
- Action-Graded Severity Scale https://arxiv.org/abs/2607.07474: reversibility as a severity axis.
- Learning from the Irrecoverable (ELPO) https://arxiv.org/abs/2602.09598: "localize the first irrecoverable step".
- WorldEvolver https://arxiv.org/abs/2606.30639: "extracts persistent heuristic rules from prediction-observation mismatches" (predicted vs realised).
- When Agents Commit Too Soon https://arxiv.org/abs/2606.22936: premature commitment diagnostics.
- VibeLifeBench https://arxiv.org/abs/2608.10875: "many of its changes are silent, so only an agent that re-inspects the world discovers them" (multi-week timelines). Relevant to the benchmark premise; the memory/belief lanes cover it.
- TriggerBench https://arxiv.org/abs/2606.23459 (prospective memory: obligations are given, not derived).
- What-If Analysis (WiA-LLM) https://arxiv.org/abs/2509.04791; From Control to Foresight https://arxiv.org/abs/2603.11677 (simulation-in-the-loop position paper).
- SciPaths https://arxiv.org/abs/2605.14600: "reasoning backward from a target contribution to the enabling scientific building blocks" (an evaluation of backward requirements, in another domain).
- AgentHER https://arxiv.org/abs/2603.21357 (hindsight relabelling for LLM agents).

## Lane answers (short)

Q1. Is "derive present obligations or option-preserving actions by reasoning backward from simulated future states"
already studied? Yes, in every component.
- Backward from a desired state: classical goal regression is still active (2511.11095), and LLM backward planning exists
  (BAR, Goal-Mem).
- Option preservation from imagined future goals: relative reachability, future-tasks auxiliary reward, AUP (2018-2020,
  with code), and Heitzig 2025.
- Simulate the future, act from the present: RAFA and LLMPC.
- Feared future constraining the present action in LLM agents: SafePred, JANUS, SIMMER, DreamGuard, SeerGuard, ARTIS
  and SafeMCP, which together make a crowded 2026 subfield.
- Robust or option-preserving choice across plausible worlds: SafeCommit (act only if safe in every retained world,
  else probe), LCPI (homogenize), and DMDU/RDM tooling.
- Reversibility estimation with later rollback: DeepRewind.
- Benchmarks with delayed finality or irreversibility: FinalityBench, SIMMER, AgentAbstain, REVERSAL-BENCH.

Q2. Residual gap: see the structured output. In short, none of the works found persists derived obligations or
signposts as first-class, timestamped state that is re-evaluated when later events arrive. None evaluates whether an
already-executed decision kept options open given a future revealed later, scored without hindsight. None keeps blocked
or averted forecasts labelled for calibration. That gap is narrow, and a strong checkpoint+RAG baseline with a
"re-check commitments" prompt may close it.
