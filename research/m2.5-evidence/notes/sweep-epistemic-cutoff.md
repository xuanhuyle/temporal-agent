# Sweep: epistemic cutoff / point-in-time reconstruction / hindsight leakage

Lane: epistemic-cutoff. Date: 2026-10-03.

## Method and evidence caveat (read first)

- **WebSearch was unavailable.** All 3 attempted WebSearch calls returned "this session has used its web search budget
  (200 of 200 WebSearch calls)". No search-engine results were obtained in this lane.
- Evidence comes from these sources:
  1. **Local arXiv abstract corpus**: 121,290 arXiv RSS abstracts (cs.AI + cs.CL + cs.IR, roughly 2025-03 to 2026-10),
     copied verbatim by the GitHub repo `CSQianDong/Awesome-arXiv-Daily-Reporter`. AI/NLP came from the sibling cache
     (`pf_tools/entries.json`). I added IR via a sparse clone at `scratchpad/lit/repos/ec/daily_ir`. Search tool:
     `scratchpad/lit/ec_tools/esearch.py`. Limitation: q-fin-only and cs.CR-only papers are absent (e.g. Fonseca 2607.04958,
     TEMPO 2605.18843 and Lopez-Lira 2504.14765 are not in the corpus).
  2. **GitHub MCP code search** (4 queries). Used to confirm pre-2025 foundational work and q-fin/cs.CR papers.
  3. **Clones** in `scratchpad/lit/repos/ec/`:
     - `microprediction/pitllm` @ c69b272 (2026-09-10). This is a curated, third-party bibliography of point-in-time LLMs.
       It says "arXiv identifiers were checked against the arXiv API". The site HTML is in `docs/`, with key-ideas notes and
       critical reviews.
     - `agentpatternscatalog/patterns` @ 2a8900b (2026-09-22), sparse clone of `patterns/`.
  4. **raw.githubusercontent.com**: the Fonseca abstract, from `Mont9165/arxiv-issue-bot`, saved to `scratchpad/lit/ec_raw/fonseca.md`.
- Evidence tiers:
  - **[ABS]**: verbatim arXiv abstract from the digest corpus. The URL is the arXiv PDF link printed in the corpus.
  - **[ABS-3P]**: verbatim arXiv abstract mirrored by a third-party GitHub digest repo.
  - **[BIB-3P]**: entry or note in the pitllm curated bibliography. These are third-party words.
  - **[REPO]**: a document read from a cloned repository.
- arxiv.org itself was never fetched. Full texts were not read, so all claims are abstract-level.

## Queries run

WebSearch (all failed, budget exhausted):
1. `look-ahead bias large language models financial backtesting` (allowed_domains arxiv.org)
2. `Time Machine GPT temporally restricted language models`
3. `point-in-time LLM pretraining knowledge cutoff to avoid lookahead bias`

Local abstract-corpus regex queries (121,290 abstracts):
4. `(look-?ahead|lookahead) bias`
5. `knowledge cut-?off` AND `(leak|contamin|hindsight|look-?ahead)`
6. `point-in-time` AND `(LLM|language model|retriev|agent)`
7. `hindsight bias`
8. `outcome bias`
9. `chronologically consistent`
10. `simulated ignorance|pretend (not to know|ignorance)`
11. `pastcast|retro-?cast|backcast(ing)? (eval|bench)`
12. `temporal(ly)? (leak|contamina)`
13. `past self|earlier self|former self|younger self` AND time terms
14. `what (it|the model|the agent|they) (knew|believed|would have)`
15. `ex-ante|ex ante` AND time terms
16. `unlearn` AND time terms
17. `hindsight (leak|contamina|information)`
18. `as[_ -]of (date|time|query|retriev)|as_of`
19. `available (at|before) (the )?(decision|prediction|query) (time|date|point)`
20. `(frozen|time-?stamped|archiv\w+) (web )?snapshot`
21. `date-?(restricted|filtered|bounded|constrained) (search|retriev)`
22. `post-?mortem` AND LLM/agent AND past terms
23. `retrospective (decision|audit)|decision (audit|review)`
24. `(model|version) (deprecat|drift|update)` AND reproducibility terms
25. `counterfactual (self|cognition)|blinded replica|self-blind`
26. `time-?travel` AND LLM/agent
27. `information (set|boundary|boundaries)` AND LLM/agent
28. `temporal (integrity|validity|causality|discipline|compliance)`
29. `epistemic state` AND LLM/agent
30. `what (an|the) agent (knew|believed|knows)|agent knew`
31. `reconstruct ... (knowledge|belief|state) (at|as of)`
32. `outcome (knowledge|information|exposure|-conditioned)|knowledge of the outcome`
33. `histor\w+ (LLM|language model)s?` AND simulation terms
34. `behavio(u)r (change|drift) over time / across versions`
35. `knowledge cut-?off` AND `(simulat|replay|sandbox|agent|persona)`

GitHub code search (MCP):
36. `"Time Machine GPT" arXiv`
37. `"Chronologically Consistent Large Language Models"`
38. `"How is ChatGPT's Behavior Changing over Time" 2307.09009`
39. `"Look-Ahead-Freedom as Temporal Non-Interference"`

Repos read: microprediction/pitllm (index.html bibliography, ideas.html key-ideas notes),
agentpatternscatalog/patterns (`as-of-information-set-pinning.md`).

---

## Works (ranked by importance to this lane)

### 1. A Historical Corpus Is Not a Historical System: Auditing Hindsight Leakage in Stateful Data Discovery (arXiv 2609.12766, Sep 2026). Threat: HIGH
- URL: https://arxiv.org/pdf/2609.12766. Authors: Yixi Zhou, Fan Zhang, Sikun Wang, Yingfan Xu, Haipeng Zhang. [ABS]
- Verbatim: "Offline replay should estimate what a discovery system could retrieve at a historical point, yet freezing the corpus
  leaves interaction memory unconstrained. We formalize point-in-time (PIT) discovery through historical state $(D_t, \theta_t, M_{< i})$
  and introduce a paired replay that changes only memory availability."
- Verbatim: "Future inflated Asset Recall@100 by 2.62-5.24 points; all 12 paired intervals excluded zero. With behavior-only
  trace memory, PIT underperformed the no-memory Stateless condition; Future masked 32.7-48.4% of that harm."
  ... "Historical evaluation must version and validate memory with the corpus."
- Why it matters: it states the project's "historical system state" in a formal way. The state is a triple: world/corpus D_t,
  parameters θ_t and memory M_<i. The paper shows empirically that freezing only the world leaks hindsight through memory. That is
  the project's "strict epistemic cutoff over the agent's own state" claim, with a paired-replay leakage audit (Temporal Violation Rate).
  It is a retrieval/discovery system, not a long-lived LLM agent that reopens decisions.
- Caps: historical_world_state, historical_epistemic_state, historical_policy_objective_state (θ_t), replay, cross_time_state_querying.

### 2. Experience Graphs: The Data Foundation for Self-Improving Agents (Trellis) (arXiv 2606.29823, Jun 2026). Threat: HIGH (for the abstraction claim)
- URL: https://arxiv.org/pdf/2606.29823. Authors: Gang Liao ... Masha Basmanov (Meta). [ABS]
- Verbatim: "This search produces a structured object we call an experience graph: executable artifacts, tool outputs, rewards,
  sibling comparisons, and causal lineage. Yet existing agent frameworks treat this experience as disposable state ..."
- Verbatim: "Frontier selection is a query, cross-session reuse is vector-seeded graph retrieval, training-data extraction is a
  materialized view, and **reconstructing what an agent knew at any past step is a time-travel query**."
- Verbatim: "We ground the design in KernelEvolve, a production accelerator-kernel optimizer at Meta".
- Why it matters: it claims, in a database-architecture framing, the project's "time as an addressable dimension of agent state".
  It provides branching with lineage, and it names past-knowledge reconstruction as a query. It does not address parametric hindsight
  or prospective branches.
- Caps: immutable_historical_observations, historical_epistemic_state, execution_checkpoints, fork_from_historical_state,
  branch_provenance, cross_time_state_querying.

### 3. Self-Blinding and Counterfactual Self-Simulation Mitigate Biases and Sycophancy in LLMs (arXiv 2601.14553, Jan 2026). Threat: HIGH (for the "ask the past self" mechanism)
- URL: https://arxiv.org/pdf/2601.14553. Authors: Brian Christian, Matan Mazor. [ABS]
- Verbatim: "decision-makers need to approximate what decision they would have made had they not known certain facts ...
  This counterfactual self-simulation is notoriously hard for humans".
- Verbatim: "We show that prompting models to ignore or pretend not to know biasing information fails to offset these biases and
  occasionally backfires. However, unlike humans, LLMs can be given access to a ground-truth model of their own counterfactual
  cognition -- their own API. We show that this access to the responses of a blinded replica enables fairer decisions".
- Why it matters: "ask my past self, who did not know X" is this paper's mechanism. The past self is a blinded replica: the same
  model re-invoked without the information. It also shows the naive alternative (instructing the model to ignore X) fails. The
  domain is bias and sycophancy, not time. The structure is the same.
- Caps: historical_epistemic_state (counterfactual knowledge state via re-instantiation).

### 4. As-Of Information-Set Pinning (agent design pattern; agentpatternscatalog/patterns, 2026). Threat: MEDIUM
- URL: https://github.com/agentpatternscatalog/patterns/blob/main/patterns/as-of-information-set-pinning.md [REPO, @2a8900b]
- Verbatim (Intent): "Bind every input a dated decision may read, including the model snapshot, retrieval corpus, reference data
  and table version, to the information set that existed at its as-of timestamp, and record the pin."
- Verbatim (Forces): "Lookahead leaks through the weights as well as the data, because a model trained on unrestricted corpora
  embeds information published after the period it is asked to reason about".
- Verbatim (Failure modes): "The pin manifest records a model alias rather than a dated snapshot, so a vendor rotation silently
  changes the weights behind an apparently pinned decision." ... "Only the data is pinned while the retrieval index is re-crawled
  in place, so the same query returns documents that did not exist at the as-of timestamp."
- Verbatim (Related): "Replay / Time-Travel — Replay re-runs a stored trace from a chosen step but still resolves live tools
  against today's data; pinning is what makes those reads return the original information set."
- Why it matters: this is practice-level prior art for "reconstruct a past decision with its exact information set, including the
  model". It lists the main failure modes: model-alias drift, unpinned index, retention expiry and silent fallback.
- Caps: immutable_historical_observations, historical_world_state, historical_policy_objective_state (model snapshot pin),
  replay, cross_time_state_querying.

### 5. Reconcile Once, Write Anytime: A Trust-Tiered Librarian and a Multi-Agent Writer for Drift-Free, Point-in-Time Research (arXiv 2608.12984, Aug 2026). Threat: MEDIUM
- URL: https://arxiv.org/pdf/2608.12984. [ABS]
- Verbatim: "A deterministic 'librarian' ingests timestamped sources into a trust-tiered ontology, layering evidence cards, an
  authoritative metric ledger, and a claim graph into an always-current source of truth ... A portable multi-agent 'writer'
  runtime then composes a contradiction-free, evidence-grounded report at any knowledge cutoff T, reading only evidence with
  as_of <= T (no look-ahead); red-team verdicts flow back into the librarian."
- Verbatim: "A red-team refutation propagates back and self-corrects a later run with zero manual edits. Replay exhibits zero
  look-ahead violations across seven cutoffs while the library grows from 235,373 to 555,312 cards."
- Why it matters: it is an agent system with an as_of<=T read discipline, a maintained claim graph (explicit belief state) and replay
  audited for look-ahead. A refutation propagating to later runs is close to "reopen". The scope is report writing, not decision remediation.
- Caps: immutable_historical_observations, historical_epistemic_state, explicit_current_belief_state, replay, cross_time_state_querying.

### 6. Simulated Ignorance Fails (arXiv 2601.13717, Jan 2026), with Can Prompts Rewind Time? (arXiv 2510.02340, Oct 2025) and Can LLMs Be Constrained to the Past? (arXiv 2606.05804, Jun 2026). Threat: MEDIUM (undermining)
- URLs: https://arxiv.org/pdf/2601.13717 ; https://arxiv.org/pdf/2510.02340 ; https://arxiv.org/pdf/2606.05804 [ABS]
- 2601.13717 verbatim: "Simulated Ignorance (SI), prompting models to suppress pre-cutoff knowledge ... SI fails systematically:
  (1) cutoff instructions leave a 52% performance gap between SI and TI; (2) chain-of-thought reasoning fails to suppress prior
  knowledge, even when reasoning traces contain no explicit post-cutoff references; (3) reasoning-optimized models exhibit worse SI
  fidelity ... prompts cannot reliably 'rewind' model knowledge."
- 2510.02340 verbatim: "while prompt-based simulated knowledge cutoffs show effectiveness when directly queried with the
  information after that date, they struggle to induce forgetting when the forgotten content is not directly asked but causally
  related to the query."
- 2606.05804 verbatim: "Self-Recall (SR), which asks the model to restate its cutoff constraint, and Question-Recall (QR) ...
  outperform both direct-answer prompting and conventional step-by-step reasoning baselines".
- pitllm review [BIB-3P]: "The 52% is the share of a performance gap left after the prompting intervention, not a measured
  quantity of leakage."
- Why it matters: a known failure mode. A "past self" produced by instructing the current model to forget leaks. Causally downstream
  knowledge leaks most.
- Caps: historical_epistemic_state.

### 7. Hindsight Bias in Clinical Temporal Reasoning: How Future Data Exposure Affects LLM Judgment (arXiv 2609.13454, Sep 2026). Threat: MEDIUM
- URL: https://arxiv.org/pdf/2609.13454. [ABS] (also in sweep-benchmarks.md)
- Verbatim: "questions are tied to a clinically meaningful cutoff and paired with a prospective reference answer and an
  outcome-consistent hindsight trap. Models answer each question using either a TTS truncated at the cutoff or the complete
  timeline ... full timeline exposure produces consistent hindsight-sensitive shifts, while temporal masking reduces bias without
  lowering accuracy."
- Why it matters: it is a ready-made paired design for "judge a past decision with vs. without later information". It reports
  metrics (HTR, AIR, HBR) that the project could reuse to score "no hindsight" when reopening decisions.
- Caps: historical_epistemic_state, predicted_vs_realized (weak).

### 8. HindsightBench: A Black-Box Behavioral Audit Protocol for Parametric Hindsight in Time-Indexed LLM Decision Tasks (arXiv 2607.18867, Jul 2026). Threat: MEDIUM
- URL: https://arxiv.org/pdf/2607.18867. Author: Haozhe Jia. [ABS] (also in sweep-belief-state.md)
- Verbatim: "Large language models leak parametric knowledge of realized outcomes into historical financial decision tasks.
  Existence is settled". "four-arm date-manipulation matrix (revealed/date-only/masked/transplanted)".
- Verbatim: "effective cutoffs span 22 months across vendors and precede vendor-reported dates by up to eight months ...
  (iii) audit results are not invariant to serving -- BF16 serving of an FP8-referenced model breaks the trigger estimate's
  stability while AWQ-INT4 preserves it".
- Why it matters: it answers "the model already knows the outcome" directly. It also shows that a "frozen" model is not frozen across
  serving configurations, so the past self also depends on the serving stack.
- Caps: historical_epistemic_state, historical_policy_objective_state (model/serving version as a variable).

### 9. All Leaks Count, Some Count More: Interpretable Temporal Contamination Detection in LLM Backtesting (TimeSPEC) (arXiv 2602.17234, Feb 2026), with Temporal Leakage in LLM Backtesting: Measurement, Validation, and Adjusted Scores (arXiv 2608.02985, Aug 2026). Threat: MEDIUM
- URLs: https://arxiv.org/pdf/2602.17234 ; https://arxiv.org/pdf/2608.02985. Authors: Zeyu Zhang, (Ryan Chen), Bradly C. Stadie. [ABS]
- 2602.17234 verbatim: "This requires models to reason only with information available at a specified past date ... decomposes
  model rationales into atomic claims and categorizes them by temporal verifiability, then applies Shapley values ... TimeSPEC,
  which interleaves generation with claim verification and regeneration to proactively filter temporal contamination -- producing
  predictions where every supporting claim can be traced to sources available before the cutoff date."
- 2608.02985 verbatim: "Models legitimately know more about times near their cutoff, so recency mimics leakage, and we prove no
  passive backtest can separate the two from genuine skill. Measurement, not just detection, requires information from outside the
  backtest ... A known cutoff identifies leakage at the boundary; a matched clean control identifies it globally".
- Why it matters: claim-level provenance to pre-cutoff sources is a concrete mechanism for "reason with a strict epistemic cutoff".
  The impossibility result shows that a no-hindsight claim needs a clean control arm, not a before/after comparison.
- Caps: historical_epistemic_state, predicted_vs_realized.

### 10. Look-Ahead-Freedom as Temporal Non-Interference: A Verifiable Correctness Property for Backtesting and Agentic Trading Pipelines (arXiv 2607.04958, Jul 2026). Threat: MEDIUM
- URL: https://arxiv.org/abs/2607.04958 (seen in [ABS-3P] `Mont9165/arxiv-issue-bot/data/papers/2607.04958.md`). Author: Xavier Fonseca. cs.CR primary.
- Verbatim: "fixing an epoch, the demand that the future not influence the present is temporal non-interference over a
  time-indexed information lattice. From this identification we develop a pipeline calculus separating a datum's availability from
  its reference time ... Where availability may depend on data values, look-ahead-freedom is undecidable (indeed Pi-0-1-hard) ...
  On the value-independent fragment (covering windowing, resampling, joins, point-in-time and vintage reads, and agentic retrieval)
  we give a type-and-effect system that is sound and decidable in linear time."
- pitllm review [BIB-3P]: "Verified error · the halting reduction ... Decidable type-checking remains a weaker, useful guarantee."
- Why it matters: "strict epistemic cutoff" already has a formal definition: non-interference, with availability time kept separate
  from reference time (bitemporal). It covers agentic retrieval and comes with a checker.
- Caps: historical_epistemic_state, cross_time_state_querying.

### 11. Temporal Leakage in Search-Engine Date-Filtered Web Retrieval (arXiv 2602.00758, Feb 2026). Threat: MEDIUM-LOW
- URL: https://arxiv.org/pdf/2602.00758. [ABS]
- Verbatim: "auditing Google Search with a before: filter, 71% of questions return at least one page containing strong post-cutoff
  leakage, and for 41%, at least one page directly reveals the answer ... (Brier score 0.108 vs. 0.242 with leak-free documents) ...
  updated articles, related-content modules, unreliable metadata/timestamps, and absence-based signals ... date-restricted search is
  insufficient for temporal evaluation."
- Why it matters: it documents failure modes of "knowledge cutoff via retrieval restricted to a date". These are the same failure
  modes a strong as-of-filtered RAG baseline would face, unless the store is append-only and bitemporal.
- Caps: historical_world_state.

### 12. Aborted but Not Forgotten: KV-Cache Retention Breaks Rollback Consistency in Language Agents (arXiv 2608.15939, Aug 2026). Threat: MEDIUM (failure-mode prior art)
- URL: https://arxiv.org/pdf/2608.15939. [ABS]
- Verbatim: "Stateful language agents assume a rejected branch can be taken back by clearing it from the application transcript.
  We show this breaks when the serving session retains key/value (KV) state across the logical abort ... rollback consistency: a
  complete abort must restore the state the model attends, not just the transcript ... retained KV alone flips a typed protected
  effect in 25 of 63 audited cells ... The channel reproduces ... under LangGraph time-travel, where verified logical rollback can
  still leave attended KV stale."
- Why it matters: reconstructing a past self from the transcript or checkpoint is not enough if serving state persists. This hindsight
  channel sits below the application layer.
- Caps: execution_checkpoints, fork_from_historical_state, historical_epistemic_state (failure mode).

### 13. Point-in-time LLM families: Scaling Point-in-Time Language Models (arXiv 2607.11889, 2026), with Time Machine GPT (arXiv 2404.18543, NAACL Findings 2024), ChronoGPT (arXiv 2502.21206), DatedGPT (2603.11838), TiMoE (2508.08827) and PALM (2609.30316). Threat: LOW (for agents), foundational
- URLs: https://arxiv.org/pdf/2607.11889 [ABS] ; https://arxiv.org/abs/2404.18543 and https://arxiv.org/abs/2502.21206 [BIB-3P, pitllm README; GitHub code search]
  ; https://arxiv.org/pdf/2603.11838 ; https://arxiv.org/pdf/2508.08827 ; https://arxiv.org/pdf/2609.30316 [ABS]
- 2607.11889 verbatim: "Large language models trained on unrestricted internet corpora inevitably embed information from the future,
  introducing lookahead bias ... Point-in-time language models--trained exclusively on text available up to each calendar date--
  eliminate this leakage by construction ... a sequence of monthly model checkpoints spanning 2013-2024."
- Time Machine GPT (HuggingAGI/HuggingArxiv mirror of abstract): "a series of point-in-time LLMs called Time Machine GPT (TiMaGPT),
  specifically designed to be nonprognosticative. This ensures they remain uninformed about future factual information and linguistic changes."
- TiMoE verbatim: "At inference time, TiMoE masks all experts whose training window ends after the query timestamp and merges the
  remaining log-probabilities in a shared space, guaranteeing strict causal validity".
- PALM verbatim: "fits a low-rank adapter on text published before the decision date without modifying any pretrained weight".
- pitllm [BIB-3P]: "A sequence can be clean at the first stage and leak at the second, and most of them are." (about post-training)
- Why it matters: this is the structural answer to "the weights already contain the future". The past self needs a model whose
  weights also stop at t. It is expensive, it lags behind frontier models, and post-training can still leak.
- Caps: historical_epistemic_state, historical_policy_objective_state, cross_time_state_querying (TiMoE: per-query cutoff).

### 14. Teaching LLMs When Not to Know: Temporal Critique Fine-Tuning for Ex-Ante Reasoning (TCFT) (arXiv 2605.14636, May 2026). Threat: LOW-MEDIUM
- URL: https://arxiv.org/pdf/2605.14636. [ABS]
- Verbatim: "prompting can steer models into a temporal frame, but does not endow them with the ability to verify whether a response
  is temporally admissible ... ex-ante correctness is not an intrinsic property of an answer, but a relation between the answer and the
  cutoff ... TCFT teaches the model to identify post-cutoff leakage, explain temporal boundary violations, and judge temporal admissibility."
- Why it matters: a trained cutoff critic is a mechanism the project might reinvent as a "no hindsight" checker.
- Caps: historical_epistemic_state.

### 15. Agentic Time Machine as an Infrastructure for Future-Event Forecasting (arXiv 2606.21013, Jun 2026). Threat: LOW
- URL: https://arxiv.org/pdf/2606.21013. [ABS]
- Verbatim: "we introduce Agentic Time Machine (TM), an infrastructure that approximately reconstructs the web state at any chosen past
  time by filtering post-cutoff content ... offline scores under TM correlate strongly with live FutureX scores".
- Why it matters: it is an agent sandbox for reconstructing world state at time t. It covers the external world, not the agent's own state.
- Caps: historical_world_state, replay.

## Additional supporting items (not ranked)

- **How is ChatGPT's behavior changing over time?** (Chen, Zaharia, Zou; arXiv 2307.09009, 2023). https://arxiv.org/abs/2307.09009
  [ABS-3P, qhduan/cn-chat-arxiv mirror]: "when and how these models are updated over time is opaque ... GPT-4 (March 2023) was very good
  at identifying prime numbers (accuracy 97.6%) but GPT-4 (June 2023) was very poor on these same questions (accuracy 2.4%)". It is evidence
  that "the model governing the agent at t" changes, and that this must be recorded as part of historical policy state.
- **Pitfalls in Evaluating Language Model Forecasters** (arXiv 2506.00723). https://arxiv.org/pdf/2506.00723 [ABS]: "many forms of temporal leakage".
- **Frontier Autolab** (arXiv 2609.36739). https://arxiv.org/pdf/2609.36739 [ABS]: "Scores rise across eras in every run while the judge's
  own hindsight subscore falls (within-run r = -0.58), so apparent learning is confounded with recall of history". (Also in sweep-prospective-forecast.md.)
- **OpenPM** (arXiv 2608.09988). https://arxiv.org/pdf/2608.09988 [ABS]: "Every record visible to the agent must be available at the
  decision time ... Each run produces audit artifacts, including a contamination certificate ... We isolate constructor behavior by
  capturing analyst evidence once and replaying it across constructor models."
- **From Knowing to Doing (KTD-Fin)** (arXiv 2605.28359). https://arxiv.org/pdf/2605.28359 [ABS]: "data-side masking protocol to anonymize
  key identifiers and calendar information consistently across prompts and tools, separating historical market memory from investment decision-making."
- **Evaluating the Search Agent in a Parallel World (MPW)** (arXiv 2603.04751) and **Synthetic Worlds for Temporal Evaluation** (arXiv 2609.00184):
  synthetic/fictional future worlds avoid parametric contamination. This is the same move the project's synthetic benchmark makes.
- **Can LLMs Be Constrained to the Past?** (2606.05804). **Detecting Lookahead Bias in LLM Forecasts** (2512.23847), **The Memorization Problem**
  (2504.14765), **TEMPO** (2605.18843), **When Alpha Disappears** (2605.23959) and **Fake Date Tests** (2601.07992) are listed in the pitllm bibliography
  [BIB-3P]. The pitllm note on the Memorization Problem: "instructions to respect the date fail, and masking fails because the model reconstructs
  entities and dates from minimal context."
- **Measuring temporal effects of agent knowledge by date-controlled tool use** (arXiv 2503.04188). https://arxiv.org/pdf/2503.04188 [ABS].
- **ChronoMem** (2607.27773). This is context only, covered in sweep-exec-state.md: a post-exposure protocol, "answering queries and summarizing
  history as if future updates never occurred."
- `Koukyosyumei/h5i-db` ROADMAP.md (GitHub code search hit) proposes an "`asof(t)`-scoped session mode" for agent backtests. It cites
  Fonseca and "When Alpha Disappears". This is practitioner uptake.

## Lane answers (short)

1. *Is "ask the past self with a strict epistemic cutoff" already a recognized problem with known methods and failure modes?* Yes.
   It is a named problem: look-ahead bias, parametric hindsight, temporal leakage, point-in-time evaluation, ex-ante reasoning. It has
   at least 4 method families:
   - point-in-time weights (TiMaGPT, ChronoGPT, DatedGPT, Scaling PiT, TiMoE, PALM);
   - inference-time suppression (FinCAD, Merchant & Levy logit steering, TCFT, TEMPO, recall-prompting);
   - input and provenance discipline (TimeSPEC claim-level provenance, OracleProto temporal masking, OpenPM, as-of pinning, the
     Fonseca type system, the as_of<=T librarian);
   - blinded-replica re-instantiation (Self-Blinding).

   Documented failure modes:
   - prompted cutoffs leak, especially for causally related knowledge (2510.02340, 2601.13717);
   - date-filtered search leaks (71% of questions, 2602.00758);
   - effective cutoffs differ from declared ones (HindsightBench, Dated Data);
   - serving configuration changes audits (HindsightBench);
   - before/after-cutoff comparisons cannot identify leakage (2608.02985);
   - frozen corpus plus unversioned memory still leaks (2609.12766);
   - KV-cache retention defeats transcript rollback (2608.15939);
   - model aliases rotate weights (as-of pinning pattern);
   - outcome-conditioned judging shifts answers (2609.13454).
2. *Does a frozen LLM make a true past self impossible?* With a general-purpose frontier model, yes for parametric knowledge of
   real-world outcomes. The model cannot un-know, and prompting cannot rewind it. A true past self needs (a) weights with a cutoff
   at or before t, or (b) a world the model cannot have seen (synthetic or post-cutoff). Then it needs (c) the input set, memory and
   serving state re-instantiated as of t. If the agent's model was swapped between t and now, the "past self" must also pin the
   then-model, which may be retired. In the project's synthetic software world, (b) holds, so parametric hindsight is mostly moot.
   The residual risks are hindsight via context, memory and KV state, and a changed model or policy. Those are the parts that
   versioned agent state addresses.
