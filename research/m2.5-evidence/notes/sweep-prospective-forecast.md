# Sweep: prospective cognition and forecasting for LLM agents

Lane: prospective-forecast. Date: 2026-10-03.

## Method and evidence caveat (read first)

- **WebSearch was unavailable.** All 4 attempted WebSearch calls returned "this session has used its web search budget
  (200 of 200 WebSearch calls)". GitHub `search_repositories` returned HTTP 502 on 4 attempts. No search-engine results were obtained.
- Evidence comes from these sources:
  1. **GitHub code search** (MCP `search_code`, 24 successful queries). Used to locate repos and third-party paper digests.
  2. **raw.githubusercontent.com fetches** of the files those searches found. Raw copies are in `scratchpad/lit/pf_raw/`.
  3. **git clones** in `scratchpad/lit/repos/pf/`:
     - `forecastingresearch/forecastbench` @ 24e86cf (2026-10-02)
     - `OpenForecaster/futuresim` @ 908322f (2026-06-25)
     - `YichengYang-Ethan/ai-forecasting-atlas` @ 3464717 (2026-08-22). This is a third-party secondary source.
     - a sparse clone of `CSQianDong/Awesome-arXiv-Daily-Reporter` @ 4d0c577 (2026-10-01). Its `*/AI/README.md` and
       `*/NLP/README.md` files cover 449 days (roughly 2025-03 to 2026-10) and hold **117,251 arXiv titles with their
       abstracts**. These are the arXiv RSS abstracts, copied verbatim.
  4. A local regex search tool (`scratchpad/lit/pf_tools/dsearch.py`) over that abstract corpus, run with 23 query patterns.
- Evidence tiers used below:
  - **[ABS]**: arXiv abstract, verbatim, from the daily-digest corpus.
  - **[REPO]**: official repo README or code read in this session.
  - **[FULLTEXT-3P]**: full paper text mirrored in a third-party GitHub repo (ZhangCurosr/*, will-rice/*). It looks like the
    paper text, but it was not fetched from arXiv.
  - **[NOTE-3P]**: a third-party summary. Never used alone for a numeric claim.
- arxiv.org itself was never fetched (blocked). The arXiv URLs below are the PDF links printed in the digest corpus, or the
  links given in official repos.

## Queries run

WebSearch (all failed: budget exhausted):
1. `prospective memory benchmark LLM agents intention 2025` (allowed_domains arxiv.org)
2. `ForecastBench dynamic benchmark AI forecasting capabilities`
3. `FutureX live benchmark LLM agents future prediction`
4. `MIT Media Lab Future You future self chatbot study results anxiety future self-continuity`

GitHub repo search (all failed: HTTP 502): `forecastbench` (x2), `FutureX benchmark future prediction agents`,
`prospective memory LLM`, `awesome LLM forecasting papers`.

GitHub code search (successful):
`"ForecastBench" filename:README.md` · `"FutureX" "live benchmark" future prediction` · `"prospective memory" LLM agent arXiv` ·
`"future self" chatbot "Future You" MIT` · `"ProactiveBench" OR "proactive agent" arXiv 2410.12361` ·
`"simulated ignorance" forecasting LLM` · `"FutureSim" forecasting replay arXiv` · `"Bench to the Future" pastcasting` ·
`forecasting LLM "reinforcement learning" "real-world outcomes" live resolved questions agent` ·
`"LLM-based Agents for Forecasting and Prediction" arXiv` · `"Outcome-based Reinforcement Learning to Predict the Future"` ·
`"scenario planning" "large language models" arXiv foresight scenarios generation` · `"backcasting" LLM agent desired future` ·
`FutureSim "submit_prediction"` · `"Forecast-Dojo" forecasting agents replayable` ·
`"Approaching Human-Level Forecasting with Language Models" 2402.18563` · `"Future You" "future self-continuity" 2405.12514` ·
`"intention reconsideration" Kinny Georgeff BDI` · `"Performative Prediction" Perdomo 2020 "self-fulfilling"` ·
`"Simulating Life Paths with Digital Twins" OR "2512.05397"` · `"EpiEvolve" streaming pandemic forecasting` ·
`"MerchantBench" e-commerce long-term coherence` · `"FORESIGHT-9" worldlines trading agents` · `"ChronosBench" proactive intent maintenance`

Local abstract-corpus regex queries (117,251 abstracts):
`prospective memory` · `future[- ]self` · `pre-?mortem` · `backcast` · `self-fulfilling|performative predict|reflexiv` x forecast x agent ·
forecast x agent x `past mistakes|lessons|resolved outcomes|outcome feedback|self-improv` · forecast x memory x agent ·
`conditional forecast|decision-conditional|policy-conditioned|decision market|futarchy` ·
`scenario planning|strategic foresight|futures studies|foresight` x LLM · commitment x track x agent ·
`(revisit|reopen|reconsider|revise) (earlier|past|prior) (decision|plan)` · `expected vs actual|prediction error|surprise` x agent ·
`predict its own success|self-prediction` · `self-defeating|averted|prevented` x forecast · `performative prediction` ·
`worldlines|alternative futures|possible futures` x LLM · counterfactual x forecast x LLM · `(past|future) self` x agent ·
`BDI|belief-desire-intention` x LLM · `intention reconsideration` · `backward planning|goal regression` x LLM ·
`prospection|episodic future thinking|mental time travel` · `Hindcast|Prophet Arena|ForecastBench-Sim|SocietyBench` ·
`conditional|interventional questions` x forecast.

---

## Works (ranked by importance for this lane)

### 1. FutureSim: Replaying World Events to Evaluate Adaptive Agents (2026) [ABS][REPO]
- URL: https://arxiv.org/abs/2605.15188 . Code: https://github.com/OpenForecaster/futuresim (cloned @ 908322f).
- Authors (from a third-party note, emptymalei/swarm-notes-ts): Goel, Chandak, Arun, Prabhu, Staab, Hardt, Andriushchenko, Geiping.
- [ABS] "we propose building grounded simulations that replay real-world events in the order they occurred. We build FutureSim,
  where agents forecast world events beyond their knowledge cutoff while interacting with a chronological replay of the world:
  real news articles arriving and questions resolving over the simulated period. ... the best agent's accuracy being 25%, and many
  having worse Brier skill score than making no prediction at all."
- [REPO README] "Futuresim is a forecasting simulator for LLM agents. It advances a dated question market, exposes only the
  information available at each simulated date, records agent forecasts, and scores them over time."
- [REPO code] `environment/scoring/base.py`:
  - `class PredictionHistory: """Track all predictions for a question."""`. Per agent it holds a list of `DailyPrediction`
    entries, appended through `add_prediction`.
  - `def get_prediction_as_of(self, agent_id, target_date)`, documented as `"Get agent's active prediction as of target_date (carry-forward)."`
  - `environment/article_corpus.py` filters articles with `if article_date and article_date > cutoff_iso: ...`.
  - `environment/replay.py::rescore`: "Rebuilds prediction histories from actions.jsonl and replays all resolutions."
- [REPO prompt] `agents/minimalHarnessAgent/prompts/prompt.py`: "You'll receive resolution feedback with your Brier score per
  question — use this to learn from mistakes and improve calibration." The handholding v2 prompt adds: "**revise any forecast on a
  still-active question where new evidence has shifted your view** ... A forecast is never "done" while its question is still active."
- [REPO code] `agents/basicAgent/feedback.py` builds a "LAST SESSION'S RESULTS" block in the form "Your prediction distribution: ... | Truth: ...".
- Caps:
  - immutable_historical_observations: dated corpus and an append-only actions log.
  - historical_world_state: the info set as of the simulated date.
  - replay.
  - uncertainty_representation and probability_over_futures: distributions per question.
  - predicted_vs_realized.
  - cross_time_state_querying: `get_prediction_as_of`.
- Threat: **HIGH**. In the forecasting domain this system already has three of the project's pieces:
  1. Strict date-gated information.
  2. An append-only, as-of-queryable forecast history.
  3. Predicted-vs-realized feedback given to the agent so it can improve its calibration.

### 2. Forecast-Dojo: Replayable Environments for Benchmarking and Training LLM Forecasting Agents (2026) [ABS][FULLTEXT-3P]
- URL: https://arxiv.org/abs/2609.28876 (digest PDF link https://arxiv.org/pdf/2609.28876). Full text mirror:
  ZhangCurosr/zhangcursor-papers-arxiv-ai-001 `2026-09-25/FORECAST-DOJO-.../full.md`.
- [ABS] "allowing agents to research an event and revisit their predictions at successive historical dates. The same tasks and
  tools support repeated evaluation, collection of training interactions, and feedback from recorded outcomes ... A belief
  notebook carried between dates lowers research cost but does not consistently improve forecast quality. ... Our code and data are publicly available."
- [FULLTEXT-3P] "In memory-on forecasting, the agent produces a belief notebook M_t that summarizes its current assessment,
  supporting evidence, and open questions." It also says: "Adding a belief notebook lowers mean Brier for six models but raises it for the other six."
- [FULLTEXT-3P] "each past step can be replayed with the same task and information cutoff. Models can then be compared under
  identical conditions". Another passage: "matched longitudinal trajectories, allowing models to be compared at identical information states".
- Caps:
  - immutable_historical_observations: 18.8M dated articles.
  - historical_epistemic_state: re-creates the agent's information state at each past date.
  - replay.
  - explicit_current_belief_state: the belief notebook.
  - uncertainty_representation: open questions and probabilities.
  - probability_over_futures.
  - predicted_vs_realized.
- Threat: **HIGH**, for two reasons:
  - It covers replay under a strict cutoff together with a carried explicit belief state.
  - It is direct **negative evidence**: an explicit belief state carried across time helped only 6 of 12 models.

### 3. EpiEvolve: Self-Evolving Agents for Streaming Pandemic Forecasting under Regime Shifts (2026) [ABS]
- URL: https://arxiv.org/abs/2606.05513. Author page: BUILDERlym.github.io `_publications/epievolve.md`, venue "Under Review".
- [ABS] "operational pandemic forecasting is a streaming process in which labels arrive after predictions and disease regimes
  shift over time. ... EpiEvolve adapts by storing forecast outcomes in a hierarchical episodic memory, reflecting on delayed
  labels, retrieving cases relevant to the current regime, and distilling recurring errors into strategic rules. The resulting
  context lets the forecaster reuse its own past predictions and outcomes in later weeks while following a chronological protocol
  that prevents future leakage. ... reaches 0.629 average accuracy, compared with 0.561 for the static backbone and 0.325 for the
  external CDC ensemble, and reduces recovery lag after regime shifts from 5 to 2 weeks."
- Caps: predicted_vs_realized. Also a weak historical_epistemic_state, because the chronological no-leakage protocol is part of the evaluation.
- Threat: **HIGH** for the claim "compare predicted vs realized futures for self-calibration". It does this with a frozen model,
  and it shows a measured gain.

### 4. Live-Evo: Online Evolution of Agentic Memory from Continuous Feedback (2026) [ABS]
- URL: https://arxiv.org/abs/2602.02369.
- [ABS] "Live-Evo decouples what happened from how to use it via an Experience Bank and a Meta-Guideline Bank ... maintains
  experience weights and updates them from feedback: experiences that consistently help are reinforced and retrieved more often,
  while misleading or stale experiences are down-weighted and gradually forgotten ... On the live Prophet Arena benchmark over a
  10-week horizon, Live-Evo improves Brier score by 20.8% and increases market returns by 12.9%". The abstract also says "Our code is available at this https URL". The link was not verified.
- Caps: predicted_vs_realized, probability_over_futures.
- Threat: MEDIUM-HIGH. It learns online from realized outcomes in a live forecasting stream.
- Note the difference from the project: it *forgets* stale experience, while the project keeps every branch.

### 5. ForecastBench-Sim: A Simulated-World Forecasting Benchmark (2026) [ABS]
- URL: https://arxiv.org/abs/2606.18686. The forecasting survey 2608.23058 cites it as "Forecast@ICML 2026 Workshop".
- [ABS] "Forecasters receive a fixed world report (a structured snapshot of the current game state) and answer questions about
  hidden future states; the benchmark then continues the simulation and scores forecasts. Because the world is simulated, the
  same setup can generate continuous or binary forecasting questions at arbitrary time horizons, paired intervention worlds for
  conditional or causal questions, and resolved examples of rare or disruptive outcomes."
- Caps: future_state_rollout (the environment's), multiple_prospective_branches (paired intervention worlds),
  intervention_aware_forecasting (conditional and causal questions), probability_over_futures, predicted_vs_realized.
- Threat: MEDIUM. It already scores intervention-conditioned forecasts against counterfactual worlds. It does so in a game, at the
  environment level, and does not track the agent's own interventions.

### 6. FORESIGHT-9: Prospective and Process-Aware Evaluation of Adaptive Trading Agents (2026) [ABS]
- URL: https://arxiv.org/abs/2608.29372.
- [ABS] "a prospective and process-aware benchmark built from nine auditable counterfactual stress worldlines branching from a
  common July 2026 information boundary. ... a deterministic generator realizes the trajectories, while observations are disclosed
  according to in-world time. ... a fixed equal-weight policy outperforms 31 of 36 runs. Process telemetry exposes failures that
  terminal returns conceal: ... decision records continued to report an active factor ensemble. FORESIGHT-9 therefore evaluates
  not only portfolio outcomes, but whether adaptive agent state and execution remain coherent across alternative futures. We
  release the worldlines, trajectories, audit traces, and regeneration scripts."
- Caps: multiple_prospective_branches; fork_from_historical_state (world-level fork from a shared information boundary);
  historical_epistemic_state (in-world-time disclosure); immutable_historical_observations (audit traces).
- Threat: MEDIUM. It is "never overwrite time, fork it" at the evaluation-world level. It also shows that what an agent reports
  about its own state can diverge from what it executed.

### 7. MerchantBench: Benchmarking LLM Agents for Long-Term Coherence in E-Commerce Operations (2026) [ABS][REPO]
- URL: https://arxiv.org/abs/2607.28956. Code: https://github.com/KhanCold/merchantbench (README fetched; Apache-2.0).
- [ABS] "Evaluating this capacity requires a persistent environment in which actions constrain future choices, feedback arrives
  at heterogeneous delays, and incoherent behavior produces measurable cumulative effects. ... MerchantBench couples promptly
  observable Upstream Supplier Events with delayed Downstream Order Outcomes, requiring agents to follow individual order
  lifecycles and revisit earlier decisions. ... the best LLM configuration attaining only 27.3% of the mean final net assets achieved by human participants."
- [REPO README] "The environment couples promptly observable supplier changes with delayed order outcomes, so decisions must
  remain coherent as evidence accumulates across a long operating horizon."
- Caps: none of the internal mechanisms. The overlap is at the benchmark level.
- Threat: **HIGH to the benchmark**. "Later event changes the significance of an earlier decision, so revisit it" is already
  built into this 365-day public benchmark.

### 8. VibeLifeBench: Can Your Life Agent Be Proactive and Persistent in a Living World? (2026) [ABS]
- URL: https://arxiv.org/abs/2608.10875.
- [ABS] "The world advances on its own clock, and many of its changes are silent, so only an agent that re-inspects the world
  discovers them. Every task is graded by fine-grained, weighted checks that read only what the agent actually left behind,
  covering the end state, the timeliness of its actions, and whether it upheld the implicit constraints. ... We will open-source
  all tasks, environments, and the evaluation framework." Per the LowEntropyAI note, it has 200 tasks, 22 mock services, 7,453 events and 1,483 silent mutations.
- Caps: none internal. The overlap is at the benchmark level.
- Threat: **HIGH to the benchmark**. It already tests multi-week plans that must stay coherent under unannounced world changes.
- Code: announced, not yet released.

### 9. Long-term Task-oriented Agent: Proactive Long-term Intent Maintenance in Dynamic Environments (ChronosBench) (2026) [ABS]
- URL: https://arxiv.org/abs/2601.09382.
- [ABS] "(i) Intent-Conditioned Monitoring: The agent autonomously formulates trigger conditions based on dialog history; (ii)
  Event-Triggered Follow-up: The agent actively engages the user upon detecting useful environmental updates. ... ChronosBench ...
  our fine-tuned model ... achieves a task completion rate of 85.19% for complex tasks including shifts in user intent".
- A third-party note (memgrafter) says the agent outputs structured JSON with fields `proactive_action, response_text, task_description, trigger_condition`.
- Caps: backward_requirements (weak: trigger conditions are present monitoring obligations derived from the user's desired outcome);
  explicit_current_belief_state (weak: stored structured intents).
- Threat: MEDIUM. It covers "reopen a dormant task when the world changes", but only for user intents and not for the agent's own past decisions.

### 10. Making Prospective Memory SLM-Shaped: Typed Intention Stores for Small-Model Agents (2026) [ABS]
This entry also covers the rest of the prospective-memory cluster beyond PM-Bench.
- URL: https://arxiv.org/abs/2609.01272.
- [ABS] "We argue that this loop is schema-constrained state tracking rather than open-ended reasoning, and that small models can
  execute it when the action space is typed. We propose the Prospective Intention Store (PIS) that puts lifecycle logic in code
  and scoped language work on the model. ... On PM-Bench, DeepSeek-Chat with PIS reaches 82.9% Set-F1. ... PIS further reaches
  70.1% Set-F1, where retrospective memory methods stay at most 54.4%."
- Related works in the same cluster, all [ABS]:
  - **TriggerBench** (https://arxiv.org/abs/2606.23459): "PM is notably harder than RM: on identical contexts, RM near-saturates
    up to 100K tokens, while PM decays sharply as context length scales."
  - **BudgetPM** (https://arxiv.org/abs/2609.37125): "the stored intention does not reveal whether that condition currently holds
    ... BudgetPM-Sequential distills full-episode hindsight schedules into a lightweight policy that decides when to spend or reserve
    capacity using only pre-query information at deployment."
  - **Did You Forget What I Asked?** (https://arxiv.org/abs/2603.23530): compliance drops 2-21% under load. A salience-enhanced
    trailing reminder restores it to 90-100%.
  - **Memory That Looks Forward** (https://arxiv.org/abs/2609.22091): "Commitments are held in an explicit ledger as dated or
    trigger-conditioned entries".
  - **Delivery, Not Storage** (https://arxiv.org/abs/2607.20972): "memories carry first-class trigger conditions over a composable
    vocabulary (path, symbol, semantic, event, temporal), evaluated deterministically by the harness".
  - **Remember When It Matters** (https://arxiv.org/abs/2607.08716): a proactive memory agent. It improves pass@1 by +8.3pp on Terminal-Bench 2.0 and +6.8pp on tau^2-Bench.
- Caps: explicit_current_belief_state (a typed store of pending obligations).
- Threat: MEDIUM.
  - Prospective obligations are already a crowded, measured area.
  - PIS's result is a deflationary argument: a typed store, with lifecycle logic in code, beats retrospective memory. The gain
    comes from schema plus code, not from a richer temporal abstraction.

### 11. Simulating Life Paths with Digital Twins: AI-Generated Future Selves Influence Decision-Making and Expand Human Choice (2025) [ABS][FULLTEXT-3P]
This entry also covers the rest of the future-self cluster.
- URL: https://arxiv.org/abs/2512.05397. Full-text mirror: will-rice/tts-papers `papers/arxiv-2512-05397--5c9e0ac745a1.md`.
- [ABS] "randomized controlled study (N=192) ... single-sided avatars increased shifts toward the presented option, while balanced
  presentation produced movement toward both. Introducing a system-generated third option increased adoption of this new
  alternative compared to control".
- [FULLTEXT-3P, limitations] "we assessed decision intentions rather than implemented behaviors. Follow-up studies tracking
  behavioral follow-through would clarify the persistence and practical significance of observed effects."
- Related: **Future You** (Pataranutaporn et al., FIE 2024; https://arxiv.org/abs/2405.12514). It appears in the Luvata/arxive
  2024-05-22 cs.AI listing with this abstract: "After a brief interaction with the 'Future You' character, users reported decreased anxiety, and increased future self-continuity."
  - The wiki note jmeier1963/omegawiki gives the details: n=344, 4 arms. Anxiety changed by -0.68 vs +0.21 for control, p=0.001.
- Related: **Future You multimodal** (https://arxiv.org/abs/2512.06106) [ABS]: "randomized controlled study (N=92) ... All personalized
  modalities strengthened Future Self-Continuity (FSC), emotional well-being, and motivation compared to control ... with no significant differences between formats."
- Related: **AI-Powered Episodic Future Thinking** (https://arxiv.org/abs/2503.16484): a usability/qualitative study only.
- Caps: future_state_rollout, multiple_prospective_branches (dual and three-option futures). All of this is human-facing.
- Threat: LOW-MEDIUM. Interrogating simulated future selves is studied, but only for humans. The measured outcomes are
  psychological (anxiety, FSC) and decision *shifts*, not decision quality.

### 12. Current Agents Fail to Leverage World Model as Tool for Foresight (2026) [ABS]
- URL: https://arxiv.org/abs/2601.03905.
- [ABS] "some agents rarely invoke simulation (fewer than 1%), frequently misuse predicted rollouts (approximately 15%), and often
  exhibit inconsistent or even degraded performance (up to 5%) when simulation is available or enforced. ... the primary bottleneck
  lies in the agents' capacity to decide when to simulate, how to interpret predicted outcomes, and how to integrate foresight into downstream reasoning."
- Caps: future_state_rollout. This is negative evidence.
- Threat: MEDIUM, as an undermining result. Giving agents a future simulator does not by itself produce decision benefit.

### 13. Simulated Ignorance Fails: A Systematic Study of LLM Behaviors on Forecasting Problems Before Model Knowledge Cutoff (2026) [NOTE-3P + list hit]
- URL: https://arxiv.org/abs/2601.13717. Found in memgrafter/research-digests, CSQianDong 21-Jan-2026 and the IJCAI 2026 lists.
- [NOTE-3P, quoting the abstract] "Across 477 competition-level questions and 9 models, SI consistently fails: cutoff instructions
  close only 52% of the SI–TI gap, CoT reasoning does not eliminate leakage, and reasoning-optimized models exhibit worse SI
  fidelity despite cleaner traces." The note lists the authors as Zehan Li, Yuxuan Wang, Ali El Lahib, Ying-Jieh Xia and Xinyu Pi.
- Related [ABS] **OracleProto** (https://arxiv.org/abs/2605.03762): "Prompting models to 'pretend not to know' cannot replace a
  genuine knowledge boundary." It reports reducing residual leakage "to the 1% level, an order of magnitude below tool-only temporal filtering".
- Related [ABS] **Pitfalls in Evaluating Language Model Forecasters** (https://arxiv.org/abs/2506.00723): "many forms of temporal leakage".
- Caps: historical_epistemic_state. The result is negative for prompt-based cutoffs.
- Threat: MEDIUM, as an undermining result. "Reconstruct what I believed at t with no hindsight" cannot be achieved by instructing
  an LLM that already holds later information. It has to be enforced structurally by data isolation. Even then, parametric
  knowledge of the world after t leaks if the model was trained past t.

### 14. Performative Prediction (Perdomo, Zrnic, Mendler-Dünner, Hardt, 2020) [foundational]
- URL: https://arxiv.org/abs/2002.06673. Text copy: Bhavyashah94/FraudxAI `docs/papers/2020_perdomo_performative_prediction.md`.
- [copy of the abstract] "When predictions support decisions they may influence the outcome they aim to predict. We call such
  predictions performative ... Performative stability implies that the predictions are calibrated not against past outcomes, but
  against the future outcomes that manifest from acting on the pred[iction]".
- 2026 follow-ups, both [ABS]:
  - **Performative Learning Theory** (https://arxiv.org/abs/2602.04402): "We cast such self-negating and self-fulfilling predictions as min-max and min-min risk functionals".
  - **Outcome Performativity A/B Detection** (https://arxiv.org/abs/2607.26908).
- Caps: intervention_aware_forecasting; predicted_vs_realized (redefined against post-action outcomes).
- Threat: MEDIUM. This is the established abstraction for "a forecast that changes the outcome". The project's "prevented futures
  are not scored as wrong" is a specific self-negating case of it.
- Gap: no LLM-agent work found here keeps an averted forecast as a labelled object.

### 15. FutureX: An Advanced Live Benchmark for LLM Agents in Future Prediction (2025; ICLR 2026) [ABS][NOTE-3P]
This entry also covers ForecastBench.
- URL: https://arxiv.org/abs/2508.11987.
- [ABS] "supporting real-time daily updates and eliminating data contamination through an automated pipeline for question
  gathering and answer collection. We evaluate 25 LLM/agent models".
- Follow-up: FutureX-Pro (https://arxiv.org/abs/2601.12259).
- **ForecastBench** (Karger et al., ICLR 2025; https://arxiv.org/abs/2409.19839; repo https://github.com/forecastingresearch/forecastbench).
  [REPO] "A dynamic, contamination-free benchmark of LLM forecasting accuracy with human comparison groups".
- **Prophet Arena** [ABS] (https://arxiv.org/abs/2510.17638): "continuously collects live forecasting tasks and decomposes each task into distinct pipeline stages".
- Caps: predicted_vs_realized (benchmark-level scoring after resolution).
- Threat: LOW. These are infrastructure for scoring forecasts against outcomes, not agent self-calibration.

---

## Other relevant hits (not ranked)

- **Survey: LLM-based Agents for Forecasting and Prediction** (https://arxiv.org/abs/2608.23058) [FULLTEXT-3P, ZhangCurosr mirror].
  - Abstract: "Future work requires calibration under distribution shift, contamination-resistant live evaluation, explicit reporting
    of cost and accuracy together, and methods for handling feedback between deployed forecasts and the outcomes being forecast."
  - Body: "In reflexive domains such as markets, published forecasts can influence the outcomes they are intended to predict ...
    Prospective market-linked benchmarks could test such feedback, but existing evaluations do not yet establish reflexive effects".
  - This supports the claim that reflexive and intervention-aware forecasting is an acknowledged gap.
- **Future-as-Label / Foresight Learning** (https://arxiv.org/abs/2601.06336) [ABS]: "Supervision is derived solely from
  post-resolution outcomes ... Qwen3-32B trained using Foresight Learning improves Brier score by 27% and halves calibration error".
- **Outcome-based RL to Predict the Future** (https://arxiv.org/abs/2505.17989) [ABS via HuggingAGI digest]: "ECE = 0.042".
- **OpenForecaster / Scaling Open-Ended Reasoning to Predict the Future** (https://arxiv.org/abs/2512.25070) [ABS]:
  "we use an offline news corpus, both for data generation and retrieval".
- **Bench to the Future** (https://arxiv.org/abs/2506.21558) and **BTF-2** (https://arxiv.org/abs/2604.26106) [ABS].
  - BTF-2: "frozen 15M-document research corpus ... evaluate agent strategic reasoning without hindsight bias. We find the better
    forecaster differs primarily in its pre-mortem analysis of its blind spots and consideration of black swans."
- **WorldReasoner** (https://arxiv.org/abs/2606.11816) [ABS]: "a simulated forecast date, and access only to evidence available
  before that date; after resolution, the framework scores the submitted probability, cited evidence, and optional causal event graph."
- **TimeSeek** (https://arxiv.org/abs/2604.04220) [ABS]: forecasts at "five temporal checkpoints" across the life of a market.
- **ForeDreamer** (https://arxiv.org/abs/2608.20920) [ABS]: "separates factual memory ... from experiential memory, persistent
  agent experience accumulated across forecasting episodes".
- **Frontier Autolab** (https://arxiv.org/abs/2609.36739) [ABS]:
  - "Each era is temporally gated: the firm decides from a dated briefing, a historian-judge then reveals what happened and scores
    the decision ... lessons enter a persistent Playbook."
  - Finding: a "foresight-commitment gap".
- **ProEvent** (https://arxiv.org/abs/2607.17701) [ABS]: "current agents frequently overact and struggle with event cancellation.
  Notably, even GPT-5.1 only reacts correctly in 26.7% of scenarios."
- **Thinking Ahead: Prospection-Guided Retrieval** (https://arxiv.org/abs/2605.14177) [ABS]: imagined next steps used as retrieval
  probes; "nearly 3x recall on MemoryQuest". This is a measurable benefit from simulating futures, but for retrieval rather than decisions.
- **From Control to Foresight: Simulation as a New Paradigm for Human-Agent Collaboration** (https://arxiv.org/abs/2603.11677)
  [ABS]: a perspective paper on "simulation-in-the-loop". No empirical results.
- **What-If Analysis of LLMs (WiA-LLM)** (https://arxiv.org/abs/2509.04791) [ABS]: "74.2% accuracy in forecasting game-state changes".
- **Agent-Supported Foresight (Futures Wheel)** (https://arxiv.org/abs/2602.08565) [ABS]: in-silico agents produce scenario consequences, with an expert comparison.
- **Pro2Guard** (https://arxiv.org/abs/2508.00500) and **JANUS** (https://arxiv.org/abs/2607.19913) [ABS]:
  - Both anticipate future risk from partial trajectories and intervene before it happens.
  - The averted futures are not kept as objects.
- **Belief-Calibrated Optimization** (https://arxiv.org/abs/2609.01861) [ABS]: "writes that belief down as a persistent in-context
  document and continually revises that document as new candidates are evaluated".
- **ai-forecasting-atlas** (third-party, cloned).
  - "Already crowded — think twice": it lists "Another live forecasting benchmark", "Retrospective / backtest evaluation" and
    "Live RL from real-world outcomes" (described as "At least three groups have shipped it").
  - It is secondary; not used for primary claims.
- Classic BDI intention reconsideration (Kinny & Georgeff; Schut et al. "intention reconsideration"). Only citeseer-dump hits were
  found (sivaramanl/Information-Retrieval `schut00intention`), so this is **not verified** here. It would be the pre-LLM prior art
  for "reopen a commitment when circumstances change".

## Lane answers (summary)

**Q1. Is interrogating simulated future states/selves studied, and did it show measurable decision benefits?**
- **Humans, yes.** RCTs show measurable *psychological* effects, but decision quality is unmeasured:
  - Future You 2024 (n=344): anxiety down, future self-continuity (FSC) up.
  - Future You multimodal (N=92): FSC, well-being and motivation up.
  - Life Paths (N=192): decision shifts and choice expansion. Its own limitations say "we assessed decision intentions rather than implemented behaviors".
- **Agents, studied but mixed.**
  - Positive: WiA-LLM forecasts game-state changes better. Prospection-guided retrieval gets about 3x recall.
  - Negative: "Current Agents Fail to Leverage World Model as Tool for Foresight" finds agents rarely invoke simulation, misuse
    rollouts in about 15% of cases, and sometimes lose up to 5% performance.
  - Forecast-Dojo: a carried belief notebook improves Brier in only 6 of 12 models.
- **Not found:** an agent interrogating a *simulated future version of itself* (its own future policy, objectives or identity)
  with a measured decision benefit.

**Q2. Are predicted-vs-realized comparisons used for agent self-calibration?**
- **Yes, widely, and in 2026 it is crowded.** At inference:
  - FutureSim's harness prompt: "use this to learn from mistakes and improve calibration".
  - EpiEvolve's episodic memory of forecast outcomes.
  - Live-Evo's feedback-weighted experience bank: Brier improved 20.8%.
  - ForeDreamer's experiential memory.
  - Frontier Autolab's Playbook.
- At training time: outcome-based RL (2505.17989), Foresight Learning (2601.06336), OpenForecaster (2512.25070) and Forecast-Dojo SFT.
- **Not found:** keeping forecasts that were *averted by the agent's own intervention* as labelled, unscored objects.
  - Performative prediction theory (2002.06673, 2602.04402) and ForecastBench-Sim's paired intervention worlds come closest.
  - The 2026 forecasting-agents survey explicitly calls reflexive feedback an open gap.
