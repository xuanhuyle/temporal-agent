# Lane sweep: performative / reflexive forecasts and prevented futures

Lane: performative-prevented. Date: 2026-10-03.

## Method and evidence caveats

- **WebSearch was not available.** Every WebSearch call returned "this session has used its web search budget (200 of 200)".
  The four attempted queries are logged below. No result from them was used.
- Substitutes used:
  1. Regex search over a local index of 117,251 arXiv cs.AI and cs.CL daily listings (Dec 2024 to 1 Oct 2026). The index was built from the cloned repo
     `CSQianDong/Awesome-arXiv-Daily-Reporter` and cached at `lit/bo/daily.json`, then at `lit/pp/recs.pkl`. Scripts are `lit/pp/q.py` and `lit/pp/show.py`.
     Every arXiv URL tagged [IDX] below comes from that listing, with its abstract.
  2. GitHub code search through the GitHub MCP tool, followed by `raw.githubusercontent.com` fetches of the matching files. Raw copies are in `lit/pp/raw/`.
     Items tagged [GH] were confirmed this way. The GitHub file that carried the evidence is named in each entry.
- The cs.LG, stat.ML and epidemiology journal literature is not in the daily index. For that literature I relied on bibliographies, paper digests and metadata files mirrored on GitHub.
  I did not read the full texts unless an entry says so.
- Overlap with other lanes: `sweep-prospective-forecast.md` already covers Perdomo 2020, Performative Learning Theory (2602.04402), OPAB (2607.26908) and ForecastBench-Sim (2606.18686).
  `sweep-backward-optionality.md` covers JANUS (2607.19913). This note mentions them only where they bear on this lane.

## Works

### 1. Metaculus Conditional Pairs, and the `ConditionalQuestion` model in forecasting-tools used by LLM forecasting bots [GH] (threat: HIGH)
- URLs: https://github.com/Metaculus/metaculus/blob/main/front_end/src/app/(main)/faq/page.tsx ;
  https://github.com/Metaculus/forecasting-tools/blob/main/forecasting_tools/data_models/questions.py
- Verbatim (FAQ): "Conditional questions are automatically resolved when their Parent and Child resolve: When the Parent resolves Yes, the "if No" Conditional is Annulled. (And vice versa.) When the Child resolves, the Conditional that was not annulled resolves to the same value." ... "This triggers the second conditional ("if No") to be annulled. It is not scored."
- Verbatim (forecasting-tools): `class ConditionalQuestion(MetaculusQuestion): ... parent: MetaculusQuestion  child: MetaculusQuestion  question_yes ... question_no`;
  `class CanceledResolution(Enum): ANNULLED = "annulled"`. The bot prompt reads: "You are forecasting the CHILD question, assuming the PARENT question has resolved to {resolved}".
  The README says the package "integrates with the Metaculus FutureEval bot tournament".
- Why it matters: this is the deployed rule for "a forecast whose condition did not happen is kept but not scored". Set the parent to "the agent intervenes" and the child to "the bad outcome occurs".
  The "if no intervention" conditional then becomes the project's "prevented future". It is annulled, not scored as wrong. LLM forecasting bots already use the same data model.
- Caps: intervention_aware_forecasting, multiple_prospective_branches, probability_over_futures, prevented_futures_preserved, predicted_vs_realized.

### 2. Dickerman and Hernán (2020), "Counterfactual prediction is not only for causal inference", Eur J Epidemiol 35:615-617 [GH] (threat: HIGH)
- URL: https://doi.org/10.1007/s10654-020-00659-8. The bib entry is in `boyercb/validating-counterfactual-predictions/4_manuscripts/paper3.bib`.
- Companion paper: Dickerman et al. (2022), "Predicting counterfactual risks under hypothetical treatment strategies: an application to HIV", Eur J Epidemiol 37(4).
- Related entries in the TTE-open-problems file LRN-05: Lin, Sperrin, Jenkins, Martin and Peek (2021), "A scoping review of causal methods enabling predictions under hypothetical interventions", Diagn Progn Res 5(1):3 (https://doi.org/10.1186/s41512-021-00092-9).
  Also Luijken et al. (2024), "Risk-Based Decision Making: Estimands for Sequential Prediction Under Interventions", Biometrical J (https://doi.org/10.1002/bimj.70011).
- Why it matters: this is the standard formal treatment. The forecast target is the risk under a stated hypothetical strategy, P(Y^a | X), using potential outcomes.
  It is not the factual risk under whatever happens next. A forecast of Y^{no action} is not falsified when the action is taken, because the action makes it unobserved.
- Caps: intervention_aware_forecasting, multiple_prospective_branches, probability_over_futures.

### 3. Boeken, Zoeter and Mooij (CLeaR 2024), "Evaluating and Correcting Performative Effects of Decision Support Systems via Causal Domain Shift", arXiv 2403.00886 [GH] (threat: HIGH)
- URLs: https://arxiv.org/abs/2403.00886 (from `qhduan/cn-chat-arxiv` papers/24/03/2403.00886.json) ; PMLR v236 (`mlresearch/v236/_posts/2024-03-15-boeken24a.md`, openreview iYJgWivXX4)
- Verbatim: "In the case that the DSS serves as an alarm for a predicted negative outcome, naive retraining of the prediction model is bound to result in a model that underestimates the risk, due to effective workings of the previous model. In this work, we propose to model the deployment of a DSS as causal domain shift and provide novel cross-domain identification results for the conditional expectation E[Y|X], allowing for pre- and post-hoc assessment of the deployment of the DSS, and for re-training of a model that assesses the risk under a baseline policy where the DSS is not deployed."
- Why it matters: this is the formal statement of the alarm that prevents its own outcome, with an identification result for the "no-alarm" risk.
  It covers the project's "prevented forecast should not count against the forecaster", at the level of the model and its retraining.
- Caps: intervention_aware_forecasting, predicted_vs_realized, historical_policy_objective_state (pre- versus post-deployment policy regimes).
- Authors verified from `philipboeken/philipboeken.github.io/assets/pdf/papers/boeken2023evaluating-bibtex.txt`: "Boeken, Philip and Zoeter, Onno and Mooij, Joris"; PMLR v236 pp. 551-569.

### 4. "Calibration Is Not Control: Why LLM-Agent Oversight Needs Intervention" (Zhang et al., arXiv 2606.21399, Jun 2026) [IDX] (threat: HIGH, agent-specific)
- URL: https://arxiv.org/abs/2606.21399
- Verbatim: "Runtime oversight for LLM agents is commonly framed as scalar risk prediction ... We argue that this framing targets the wrong object for control. The relevant question is not how likely the agent is to fail if it continues, but whether an available intervention would improve the outcome ... we introduce prefix branching, a same-prefix counterfactual protocol that executes candidate actions from identical trajectory states ... recalibrating the same scalar score improves prediction metrics but leaves control regret unchanged".
- Why it matters: in LLM agents it replaces passive risk forecasts with action-conditioned forecasts ("intervention advantage").
  It evaluates them by forking from identical states, i.e., counterfactual branches with and without the intervention. That is the agent form of "score the intervention, not the passive forecast".
- Caps: intervention_aware_forecasting, counterfactual_action_branches, fork_from_historical_state, future_state_rollout, multiple_prospective_branches, predicted_vs_realized.

### 5. Vasudev, Russak, Bikel and Alshikh (arXiv 2602.03338, Feb 2026), "Accurate Failure Prediction in Agents Does Not Imply Effective Failure Prevention" ("The Intervention Paradox") [IDX] (threat: MEDIUM)
- URL: https://arxiv.org/abs/2602.03338. The title variant "The Intervention Paradox: ..." comes from `geostigma-hj/on_policy_intervention`. A replication digest is at `mixidota2/paper-lab/papers/intervention-paradox`.
- Verbatim: "a binary LLM critic with strong offline accuracy (AUROC 0.94) can nevertheless cause severe performance degradation, inducing a 26 percentage point (pp) collapse ... We identify a disruption-recovery tradeoff: interventions may recover failing trajectories but also disrupt trajectories that would have succeeded ... we propose a pre-deployment test that uses a small pilot of 50 tasks to estimate whether intervention is likely to help or harm".
- Translated from the Japanese digest: what is needed is a paired comparison of failures that were rescued and successes that were broken.
- Why it matters: this is the clinical "accurate ≠ beneficial" result reproduced for LLM agents. Forecast quality and intervention value are evaluated separately, using with/without-intervention counterfactuals.
- Caps: intervention_aware_forecasting, counterfactual_action_branches, predicted_vs_realized.

### 6. Sorenson (Aug 2026, independent preprint on GitHub), "Reflexive Model-World Systems: When Representations Become Causes" [GH] (threat: MEDIUM; not peer-reviewed)
- URL: https://github.com/corbensorenson/asi-stack-book/blob/main/papers/source/reflexive_model_world_systems.md
- Verbatim: "A successful prediction can therefore become observationally false because it was causally effective. This is not an edge case: alarms are often designed to invalidate their own forecasts."
  "The naive lineage underestimates mean baseline risk by approximately 24.9%. Yet the labels causing this error are evidence that the intervention worked. A dashboard that reports only mismatch between the alarm and observed outcome would punish causal success."
  The paper has a four-way evaluation matrix: "Baseline fidelity | On-policy fidelity | Steering utility". The row "High | Low | High" is labelled "Potentially successful self-negating intervention".
  "This matrix prevents a common category error: treating the observed post-deployment label as the only truth against which the original prediction should be judged."
  Its section 13.6 says: "observed regret may be endogenous to the policy that produced or prevented it ... Without this distinction, successful prevention can erase the evidence of risk".
- Why it matters: it nearly states the project's "prevented futures are not failed predictions" principle word for word, extended to model lineages and agent regret learning.
- Caps: intervention_aware_forecasting, prevented_futures_preserved (conceptual), predicted_vs_realized, historical_policy_objective_state (model lineage).

### 7. Armstrong and O'Rorke (2017), "Good and safe uses of AI Oracles" (counterfactual oracle), arXiv 1711.05541 [GH] (threat: MEDIUM)
- URL: https://arxiv.org/abs/1711.05541 (from `lihebi/biber-dist/cs.AI/cs.AI-2017-11.bib`). The AF post text is in `awestover/filtering-for-misalignment/labelled/alignmentforum/post3309.txt`.
- Verbatim (Armstrong, AF post): "If the prediction was sent out into the world, then O is attempting to make p_n into a self-confirming prediction ... we make O into a counterfactual Oracle; on some occasions, the output p_n is erased, and not seen by anyone ... the job of the counterfactual Oracle is ... to produce a prediction p_n that is the best prediction for o_n given the history h_{n-1} e".
  "the counterfactual prediction is easy to interpret: 'had we not seen p_n, that is what o_n would have been'".
  "the Oracle can be used to estimate the extent to which the prediction is manipulative, by contrasting its predictions for o_n given the h_{n-1}, and given h_{n-1} e."
- Why it matters: it is a clean way to evaluate a forecaster whose output would otherwise change the world. Randomly withhold the forecast ("erasure"), score only on those episodes, and keep the conditional forecast for the no-action world.
- Caps: intervention_aware_forecasting, predicted_vs_realized.

### 8. Oesterheld, Treutlein, Cooper and Hudson (UAI 2023), "Incentivizing honest performative predictions with proper scoring rules", arXiv 2305.17601 [GH] (threat: MEDIUM)
- URLs: https://arxiv.org/abs/2305.17601 ; https://proceedings.mlr.press/v216/oesterheld23a/oesterheld23a.pdf ; code: https://github.com/johannestreutlein/scoring-rules-performative
- Verbatim: "Proper scoring rules incentivize experts to accurately report beliefs, assuming predictions cannot influence outcomes. We relax this assumption ... We say a prediction is a fixed point if it accurately reflects the expert's beliefs after that prediction has been made. We show that in this setting, reports maximizing expected score generally do not reflect an expert's beliefs ... for binary predictions, if the influence of the expert's prediction on outcomes is bounded, it is possible to define scoring rules under which optimal reports are arbitrarily close to fixed points. However, this is impossible for predictions over more than two outcomes."
- Why it matters: it gives the scoring theory for reflexive forecasts. Scoring a forecast against its own post-forecast outcome creates an incentive to manipulate.
  It is a direct caution for any "predicted vs realized" learning loop in an agent that acts on its own forecasts.
- Caps: intervention_aware_forecasting, probability_over_futures, predicted_vs_realized.
- Same research line: Hubinger, Jermyn, Treutlein, Hudson and Woolverton (2023), "Conditioning Predictive Models: Risks and Strategies", arXiv 2302.00805 (from `Lyken17/arXiv-stats` info/23-Feb/3).

### 9. Decision markets and decision scoring rules: Othman and Sandholm (2010); Chen, Kash, Ruberry and Shnayder (2011); Oesterheld and Conitzer (2020) [GH] (threat: MEDIUM)
- URL (bibliography seen): https://github.com/buttermarkets/learn-futarchy/blob/main/sota-decision-markets.md
- Verbatim: "Othman & Sandholm (2010), *Decision Rules and Decision Markets* — when the price drives the choice, naive decision rules are manipulable".
  "Chen, Kash, Ruberry & Shnayder (2011), *Decision Markets with Good Incentives* — the strictly-proper construction (inverse-probability decision scoring)".
  "Chen & Kash (2011) ... the decision rule must sometimes randomize". "Oesterheld & Conitzer (2020), *Decision Scoring Rules* — follow the recommendation, pay the expert in shares of the outcome ... only the recommended action's value is elicited".
  "Oesterheld (2017), *Futarchy Implements Evidential Decision Theory*".
- Why it matters: this mechanism-design literature handles forecasts that select the action. Conditional forecasts for actions not taken are voided.
  Strict properness then requires randomizing over actions, and a deterministic chooser elicits only the chosen branch. An agent that always acts on its feared-future forecast can never verify that forecast.
- Caps: intervention_aware_forecasting, multiple_prospective_branches, probability_over_futures, prevented_futures_preserved (voided branches), predicted_vs_realized.

### 10. Counterfactual performance evaluation of prediction under interventions [GH] (threat: MEDIUM)
Two papers:
- Keogh and van Geloven (2024), Epidemiology 35(3):329-339, arXiv 2304.10005. Code: https://github.com/survival-lumc/Validation_Under_Interventions and the `ipeval` package.
- Boyer, Dahabreh and Steingrimsson (2025), Stat Med 44(23-24):e70287. R package: https://github.com/boyercb/cfperformance
- URLs: https://doi.org/10.1097/EDE.0000000000001713 ; https://doi.org/10.1002/sim.70287
- Verbatim (TTE-open-problems LRN-05, choxos): "Counterfactual analogues of the standard measures now exist: artificial censoring with inverse probability weighting extends calibration, the c-index, the time-dependent AUC and the Brier score to sustained strategies ... All of them are identified under the same conditional exchangeability and positivity conditions used to fit the model".
  The cfperformance README says it "provides methods for estimating model performance measures (MSE, AUC, calibration) under hypothetical/counterfactual interventions".
- Why it matters: these are working estimators for scoring a forecast of the outcome under no intervention when some units were intervened on. They depend on exchangeability and positivity.
- Caps: intervention_aware_forecasting, predicted_vs_realized, uncertainty_representation.

### 11. van Amsterdam, van Geloven, Krijthe, Ranganath and Cinà (2025), "When accurate prediction models yield harmful self-fulfilling prophecies", Patterns; arXiv 2312.01210 [GH] (threat: MEDIUM)
- URLs: https://arxiv.org/abs/2312.01210 ; https://doi.org/10.1016/j.patter.2025.101229 (from `vanAmsterdam/causal-data-science-summerschool` library.bib)
- Verbatim (taesiri/ArXivQA summary): "Theoretical results that good discrimination or calibration after deployment does NOT imply an OPM improved outcomes. Show that requiring an OPM to have good calibration before AND after deployment renders it useless for decision making."
- Why it matters: if a deployed forecaster is calibrated before and after it acts, its forecasts changed nothing. Predicted-vs-realized agreement after acting is therefore not a sign of a good forecaster.
- Caps: intervention_aware_forecasting, predicted_vs_realized.
- Authors verified from the library.bib entry: "Van Amsterdam, Wouter A.C. and Van Geloven, Nan and Krijthe, Jesse H. and Ranganath, Rajesh and Cinà, Giovanni".

### 12. Liley, Emerson, Mateen, Vallejos, Aslett and Vollmer (AISTATS 2021), "Model updating after interventions paradoxically introduces bias", arXiv 2010.11530 [GH] (threat: MEDIUM)
- URL: https://arxiv.org/abs/2010.11530 (id from `Lyken17/arXiv-stats` info/21-Feb/23). Also cited in `cran/OptHoldoutSize` vignettes/optimal_holdout_sizing.bib.
- The same bib lists related work:
  - Lenert, Matheny and Walsh (2019), "Prognostic models will be victims of their own success, unless…".
  - Sperrin, Jenkins, Martin and Peek (2019), "Explicit causal reasoning is needed to prevent prognostic models being victims of their own success".
  - Haidar-Wehbe et al., the OptHoldoutSize package: an untreated holdout set for safe updating.
- Why it matters: clinical ML has known since at least 2019 that labels from a model-triggered intervention cannot be treated as plain negatives. The proposed fixes are holdout sets, i.e., randomized withholding, and causal reasoning.
- Caps: intervention_aware_forecasting, predicted_vs_realized.
- Note: abstract not fetched. The description is based on the title and the bibliography context.

### 13. Perdomo, Zrnic, Mendler-Dünner and Hardt (ICML 2020), "Performative Prediction", arXiv 2002.06673 (foundational) [GH copy] (threat: MEDIUM)
- URL: https://arxiv.org/abs/2002.06673. Text copy: `lit/pf_raw/perdomo2020.md`, a GitHub mirror.
- Verbatim: "When predictions support decisions they may influence the outcome they aim to predict. We call such predictions performative ... Performative stability implies that the predictions are calibrated not against past outcomes, but against the future outcomes that manifest from acting on the prediction."
- Survey: Hardt and Mendler-Dünner (2023), "Performative Prediction: Past and Future", arXiv 2310.16608. Digest: `memgrafter/research-digests`. It distinguishes "learning (optimizing in current conditions) and steering".
- 2026 survey: "Dissecting Performative Prediction: A Comprehensive Survey", arXiv 2602.10176 (memgrafter digest). Related arXiv listings:
  - "Partially Performative Prediction", arXiv 2606.07890 (`ehijano/rss_fetch` stat.ML 2026-06-08).
  - Performative RL: 2512.20576 [IDX] and 2510.04430 (AutoResearch-Factory wiki).
- Caps: intervention_aware_forecasting, predicted_vs_realized.

### 14. ICML 2025 (author unverified), "Revisiting the Predictability of Performative, Social Events", arXiv 2503.11713 [GH] (threat: LOW)
- URL: https://arxiv.org/abs/2503.11713 (`zhaoyang97/Paper-Notes-en` docs/ICML2025/others)
- Verbatim (note): "Can social events still be accurately predicted when predictions actively influence outcomes? The answer is affirmative—yet such 'accurate' predictions can be entirely useless."
  "Theorem 5.1 ... predictor f can be performatively multicalibrated with respect to all bounded continuous functions c(x,p), yet simultaneously maximizes the performative risk".
- Why it matters: agreement between forecast and outcome under performativity can be manufactured. It is a weak learning signal.
- Caps: intervention_aware_forecasting, predicted_vs_realized.
- Note: the authorship (Perdomo) is from my recall and was not verified. The fetched note does not list authors; cite it as "arXiv 2503.11713 (ICML 2025)".

### 15. Howerton et al. (2023), "Evaluation of the US COVID-19 Scenario Modeling Hub for informing pandemic response under uncertainty", Nature Communications 14:7260 [GH] (threat: LOW)
- URLs: https://doi.org/10.1038/s41467-023-42680-x ; code: https://github.com/midas-network/covid19-scenario-hub_evaluation
- Verbatim (README): "**setup scenario plausibility:** assess the plausibility of SMH scenarios ... compare realized vaccine uptake to scenario specified vaccine uptake ... **score projections:** calculate coverage and weighted interval score (WIS)".
- Why it matters: public-health practice already separates scenario-conditional projections from forecasts. A projection is scored only where its scenario assumptions held.
- Caps: intervention_aware_forecasting, multiple_prospective_branches, probability_over_futures, uncertainty_representation, predicted_vs_realized.

## Secondary or context items seen (not in the main list)

- Gower-Winter and Krempl (2026), "Actions Have Consequences: Detecting Outcome Performativity using Intervention Testing", https://arxiv.org/abs/2607.26908 [IDX]. It detects performativity by A/B testing on the predictions.
- Rodemann, Fischer-Abaigar, Bailie and Muandet (2026), "Performative Learning Theory", https://arxiv.org/abs/2602.04402 [IDX]: "We cast such self-negating and self-fulfilling predictions as min-max and min-min risk functionals".
- Coston, Mishler, Kennedy and Chouldechova (2020), "Counterfactual Risk Assessments, Evaluation, and Fairness", https://arxiv.org/pdf/1909.00066.pdf (lihebi/biber-dist). Also Rambachan, Coston and Kennedy, arXiv 2212.09844 (cited in TTE LRN-05).
- Causal Agent Replay, https://arxiv.org/abs/2606.08275 [IDX]: "applies a do-operation to a step, and re-executes the trajectory forward".
  Comparison-Only Tiny Advisor (COTA), https://arxiv.org/abs/2608.21027 [IDX]: "pairwise supervision constructed from same-prefix counterfactual branches".
  Credit Without Ground Truth, https://arxiv.org/abs/2608.19760 [IDX].
- PrefixGuard, https://arxiv.org/abs/2605.06455 [IDX]: "first-alert diagnostics show that strong ranking does not imply deployment utility".
- Proactive Service Agents survey, https://arxiv.org/abs/2609.03727 [IDX]: "offline classification performance alone does not predict deployment benefit ... Reliable proactive service instead requires calibrated incremental intervention value, verifiable authorization, recoverable execution, and counterfactual evidence."
- Control-theoretic guardrails, https://arxiv.org/abs/2510.13727 [IDX]. Predictive guardrails "proactively correct risky outputs to safe ones". The feared future drives a correction in the present.
- ForecastBench-Sim, https://arxiv.org/abs/2606.18686 [IDX]: "paired intervention worlds for conditional or causal questions". This is covered in the prospective-forecast lane.
- Forecasting Research Institute (2024), "Conditional Trees" working paper (https://forecastingresearch.org/research/ai-conditional-trees). Its provenance came from `copyleftdev/superforecasting-skills-pack`.
- Performative Scenario Optimization, https://arxiv.org/abs/2603.29982 (cs.GT RSS). It is about performative guardrails against LLM jailbreaks and has low relevance.
- Agentic Digital Twins taxonomy, https://arxiv.org/abs/2601.18799 [IDX]: "constitutive coupling enables systems to create self-validating realities". This is conceptual.

## Queries run

WebSearch (all four failed because the budget was exhausted):
- `Performative Prediction Perdomo Zrnic Mendler-Dünner Hardt 2020`
- `Counterfactual prediction under hypothetical interventions Dickerman Hernán prediction models decision support`
- `evaluating clinical early warning system when predictions trigger interventions treatment paradox performance evaluation`
- `LLM agent forecasts self-fulfilling self-defeating performative prediction 2025`

Local arXiv cs.AI/cs.CL index (regex; `&&&` means AND):
- `performativ`
- `self-fulfil`
- `self-defeat|self-negating|self-destroying prophec`
- `prevention paradox|paradox of prevention`
- `decision-dependent distribution`
- `reflexiv &&& forecast|predict`
- `forecast &&& (change|alter|influence)s? (the )?(behavior|outcome)`
- `conditional forecast|conditional prediction market|decision market`
- `counterfactual predict &&& clinic|patient|treat`
- `drop-in|treatment paradox|confounding by intervention`
- `interventional forecast|intervention-aware forecast|policy-conditioned forecast|action-conditioned forecast`
- `averted|prevented outcome|prevented future`
- `off-policy evaluation &&& LLM|agent`
- `counterfactual (evaluation|replay|simulation) &&& LLM agent`
- `early warning &&& LLM|agent`
- `(predict|forecast) &&& trigger intervention &&& LLM|agent`
- `conditional (question|forecast|probabilit) &&& forecast`
- `forecast &&& intervention &&& LLM`
- `(anticipat|foresee|forecast) &&& prevent &&& (LLM|agent) &&& (risk|failure|incident)`
- `outcome performativ|performative (effect|shift|feedback)`
- `self-negat|self-preventing|self-refuting`
- `decision-focused (learning|forecast) &&& LLM`
- `counterfactual forecast|what-if forecast`
- `(interventional|action-conditioned) (prediction|forecast|world model) &&& LLM`
- `prediction market &&& agent &&& condition`
- `futarchy|decision market`
- `(scor|evaluat) &&& conditional (forecast|question)`
- `(resolution) &&& forecast &&& (counterfactual|intervention|annul)`
- `(pastcast|backtest|hindsight|leakage) &&& forecast &&& LLM`
- `predict its own behavior &&& agent`
- `(prevented|averted) (harm|failure) &&& counterfactual`
- `(predict) &&& failure &&& interven &&& agent &&& (harm|disrupt|counterfactual|would have)`
- `would have (succeeded|failed|occurred)`
- `counterfactual &&& (rescue|recover|averted|prevent) &&& agent`
- `(alarm|alert) &&& (LLM|agent)`
- `regret &&& prevent &&& forecast`
- `self-confirming|counterfactual oracle`
- `(performative|reflexive) &&& (LLM|agent) &&& (decision|forecast)`

GitHub code search (MCP):
- `"self-defeating" "performative prediction" arxiv`
- `"self-fulfilling prophecies" "prediction models" "treatment" arxiv`
- `"performative prediction" "past and future"`
- `"counterfactual prediction under hypothetical interventions"`
- `"Incentivizing honest performative predictions"`
- `"decision scoring rules" OR "decision markets with good incentives"`
- `"counterfactual oracle" erasure prediction`
- `"Good and safe uses of AI Oracles"`
- `"prediction under interventions" counterfactual performance`
- `"victims of their own success" prognostic models`
- `"Counterfactual prediction is not only for causal inference"`
- `"Counterfactual risk assessments, evaluation, and fairness"`
- `"Conditioning Predictive Models: Risks and Strategies"`
- `"Model updating after interventions paradoxically introduces bias" arxiv`
- `"performative effects of decision support systems"`
- `"prevention paradox" prediction model evaluation intervention`
- `"performative" "LLM agents" forecast self-fulfilling 2026`
- `"Counterfactual Reasoning and Learning Systems" Bottou`
- `"conditional forecasting" questions LLM forecasters arxiv`
- `"Performative Scenario Optimization"`
- `"Accurate Failure Prediction in Agents Does Not Imply Effective Failure Prevention"`
- `"JANUS" "Foreseeing Latent Risk ..."`
- `"Evaluation of the US COVID-19 Scenario Modeling Hub"`
- `"self-defeating" forecast epidemic projections`
- `metaculus conditional question "annulled"`
- `"conditional trees" forecasting Karger`
- `"Calibration Is Not Control" LLM-Agent Oversight`
- `"forecasts" "trigger interventions" agent "prevented" evaluation counterfactual LLM` (0 hits)

## Lane answers (short form; the full text is in the StructuredOutput)

1. **Is the problem already handled cleanly?** Yes, conceptually. Four mature treatments exist:
   - potential-outcome targets: Dickerman and Hernán; Keogh and van Geloven; Boyer et al.;
   - annulment of conditional branches: Metaculus Conditional Pairs; decision markets;
   - withholding the forecast at random: counterfactual oracle erasure; untreated holdouts (Liley; OptHoldoutSize);
   - causal-domain-shift correction: Boeken et al.

   Each one forbids scoring an averted outcome as a miss. Every route has an identifiability cost: positivity or randomization. A deterministic intervener cannot verify its own averted forecasts.
2. **What is the standard formal treatment?** Forecast P(Y^a | H_t) for a named action or strategy a, using potential outcomes or do().
   Score only the branch that was realized; annul the other, or score it with IPW under exchangeability. Performative and reflexive forecasts are treated as distribution maps D(theta), with fixed points or performative stability. Decision value is evaluated separately: net benefit, steering utility, intervention advantage.
3. **Is anything left for agents?** The narrow gap is persistence. No work found keeps averted forecasts as first-class, queryable memory objects in a long-lived LLM agent, with the forecaster version, the policy, the evidence cutoff, and a later status ("annulled / counterfactually verified / unverifiable"), and then reuses them.
   Agent work from 2026 (2602.03338, 2606.21399, COTA, CAR) already does the counterfactual evaluation with same-prefix branching, but only as an offline protocol.
