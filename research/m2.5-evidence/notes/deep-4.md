# Deep read: Forecast-Dojo: Replayable Environments for Benchmarking and Training LLM Forecasting Agents

Liqin Ye*, Haorui Wang*, Fardin Ahmed, Rongzhi Zhang, Yuan He, Ziyuan Lin, Yanbin Yin, Jing Peng, Michael Galarnyk,
Sudheer Chava, Chao Zhang (Georgia Tech, Amazon, U. Florida). arXiv 2609.28876 (v1, announced 2026-09-25, "Announce
Type: new"). Venue: arXiv preprint only; no venue is stated anywhere I could see.

Date: 2026-10-03. Lane: prospective-forecast (also relevant to: epistemic-cutoff, belief-state, benchmarks).

## What was read, and how

- **Full paper text: READ IN FULL** (889 lines, body plus appendices A–C and prompts). It is a MinerU PDF-to-markdown
  conversion of the arXiv v1 PDF, mirrored by a third party:
  - https://raw.githubusercontent.com/ZhangCurosr/zhangcursor-papers-arxiv-ai-001/main/2026-09-25/FORECAST-DOJO-REPLAYABLE-ENVIRONMENTS-FOR-BENCHMARKING-AND-T_aa56f76c/full.md
    Re-fetched in this session and byte-identical (`cmp`) to the earlier copy at `scratchpad/lit/pf_raw/forecastdojo_full.md`.
    sha256 `74c770b76af4065deff2fa50c19ff2121c0e3cc2bf73e17a6bf59a32c1d990aa`. Local copy: `scratchpad/lit/deep4_raw/full_zc.md`.
  - The sibling `meta.json` says `"source": "https://arxiv.org/pdf/2609.28876v1.pdf"`, `"created_at": "2026-09-25 23:12:09"`.
  - Figures are images and could not be inspected. In Table 1 the check/cross glyphs were lost in conversion, so the
    paper's self-positioning table cannot be read.
- **Abstract confirmed by three independent mirrors:**
  - https://raw.githubusercontent.com/qhduan/cn-chat-arxiv/master/papers/26/09/2609.28876.json
    (`"link": "https://arxiv.org/abs/2609.28876"`, `"arXiv:2609.28876v1 Announce Type: new"`; abstract truncated);
  - https://raw.githubusercontent.com/mrpunkdasilva/data-science/main/capstone/data/corpus/2609.28876v1.txt;
  - the `CSQianDong/Awesome-arXiv-Daily-Reporter` clone (@4d0c577), `25-Sep-2026/AI/README.md`, line 819:
    `[PDF](https://arxiv.org/pdf/2609.28876)`, with the author list.
  - In all three RSS abstracts the text ends at "...supervised fine-tuning as a proof of concept." The sentence "Our code
    and data are publicly available." appears only in the PDF abstract.
- **Code: NOT FOUND.**
  - GitHub code search for `"Forecast-Dojo"` returned 90 hits. All are digests, newsletters or mirrors; none is an official
    repo.
  - Searches for `"belief_notebook" "evidence_ledger"`, `forecast_dojo language:Python` and `"forecast-dojo" pyproject/setup.py`
    returned 0 hits.
  - Repo search (`search_repositories`) returned HTTP 502 twice.
  - The PDF text contains no repo URL; it may have been a hyperlink that the conversion lost.
  - A third-party blog summary (raw.githubusercontent.com/ShoubhikBanerjee/blog/master/p/forecast-dojo-.../index.html) has
    no code link either.
- **Not available:** arxiv.org, which is blocked. WebSearch was also unavailable: "this session has used its web search
  budget (200 of 200)".

## What the system is (verbatim)

- Abstract: "We introduce Forecast-Dojo, a replayable environment for benchmarking and training LLM forecasting agents. It
  combines resolved prediction-market questions with dated news, allowing agents to research an event and revisit their
  predictions at successive historical dates. ... Forecast-Dojo contains 1,568 Polymarket events, split by time into training
  and evaluation periods, and 18.8M dated news articles. ... A belief notebook carried between dates lowers research cost
  but does not consistently improve forecast quality."
- Section 1: "At each step, an LLM agent can search a temporally-restricted information corpus, inspect full documents, and
  use computational tools to produce a probabilistic forecast using only information available by that date. Each step can
  be reset and rerun across models or repeated trials, while steps from the same event can be traversed sequentially with
  persistent agent memory. The realized outcome is retained by the environment for immediate scoring but never exposed to
  the agent during its forecasting."
- Section 1: "the ideal setting combines the two: the forecasting problem evolves as new evidence becomes available, yet each
  past step can be replayed with the same task and information cutoff. Models can then be compared under identical
  conditions and scored immediately".
- Section 2: "Forecast-Dojo instead treats time progression as part of the experimental design: each event is replayed at a
  fixed sequence of historical checkpoints shared by all agents. This produces matched longitudinal trajectories, allowing
  models to be compared at identical information states".
- Information cutoff (Eq. 1): `I_{<=tau_t} = {d in I : date(d) <= tau_t}`, with `I_{<=tau_t} ⊆ I_{<=tau_{t+1}}`.
  - A.1: "The date restriction is applied before similarity ranking, and full-article access independently rechecks the same
    temporal constraint."
  - The tool prompt says: "Pass an id copied verbatim from one of your own prior search hits; IDs you did not receive, and
    articles published after the forecast date, are rejected."
- Defined present (memory-free prompt): "forecast date: treat this as today. Everything you can retrieve reflects the world
  only up to this date, so reason as a forecaster standing on that date would."
- Parametric-leakage control (5.1): "For every model, either its reported knowledge or training-data cutoff or, when
  unavailable, its checkpoint release date predates the evaluation period (see Table 9)."
- Content-level leakage screen (A.2): an LLM judge screens retrieved evidence for outcome leakage. "The judge does not
  receive the structured realized outcome, final market prices, or crowd trajectory." Only events with
  `v_Q = SUFFICIENT and l_Q = false` are kept.
- Memory modes (3, 4.4):
  - "In memory-on forecasting, the agent produces a belief notebook M_t that summarizes its current assessment, supporting
    evidence, and open questions. At the next step, M_t is provided alongside the question and new forecast date".
  - "Previous conversation turns, reasoning traces, and tool observations are discarded, making M_t the only explicitly
    transferred information."
- Belief-notebook schema (Figure 6 prompt):
  - "assessment — your current view: p ... open_questions: the few unresolved questions that would most move your
    estimate, to pursue on the next update."
  - "The evidence_ledger is an append-only list of the facts you have established. Each entry contains: claim ... supports
    ... rules_out ... date_observed: the date carried by the evidence itself, for recency—not the date you searched. status:
    "active", or "superseded" once later evidence overrides it. note: brief provenance or quality caveat".
  - "Append, don't overwrite. Add new facts as new entries. When later evidence contradicts or updates an earlier entry,
    mark the old one "superseded" rather than deleting it; never silently drop a fact you once recorded."
  - "Keep p consistent with the active ledger."
- Outcome feedback (3): "Once the realized outcome Y is available, the environment assigns feedback r_{Q,t} = S(p_{Q,t}, Y)
  ... The outcome and feedback are not part of the agent's forecasting context."
- Logging (4.5): "With trajectory logging enabled, each completed forecast step retains its available within-step
  interaction history H_t, including model messages and tool interactions, and, in memory-on mode, the belief notebook M_t."
  "Forecast-Dojo also supports trajectory-level analyses of how beliefs evolve across forecast steps."
- Episode length (4.3, A.3):
  - `T_Q = clamp(round(sqrt(n_Q)), 3, 10)` forecast steps per event.
  - The evaluation split has 230 events and 797 event-dates, so about 3.5 steps per event.
  - Figure 3 caption: "Only 67 of the 230 events have a fourth step and 25 have a fifth".
- Budgets (B.2): "Tool runs share a budget of 120 tool iterations and 400 calls per forecast step"; Table 10: "Tool budgets
  are per forecast step and identical in memory-free and memory-on mode".

## Key empirical results (verbatim, then my derived reading)

- 5.2: "Adding a belief notebook lowers mean Brier for six models but raises it for the other six. For example, GPT-5.5
  changes from 0.564 to 0.571, whereas GPT-5.6 Sol improves from 0.554 to 0.546. The latter improvement coincides with a
  reduction in unusable reports from 4.49% to 0.53%. When both settings produce a usable forecast, however, the paired
  memory-on-minus-memory-free Brier difference for GPT-5.6 Sol is only +0.0010."
- 5.3: "Mean Brier decreases from 0.670 to 0.606 with memory-free research and from 0.671 to 0.612 with memory-on research."
  So within-event improvement is no better with the carried belief state.
- 5.4: "For the five proprietary models, memory-on execution costs less per forecast than memory-free execution in every
  case. The reduction ranges from 8% for Claude Opus 4.6 to 33% for GPT-5.5, with a median of 24% ... GPT-5.5 costs a third
  less, $3.90 instead of $5.85 per forecast, while its paired Brier difference is +0.007 with a 95% confidence interval that
  includes zero." Also: "lower research cost is memory's clearest benefit in the evaluated protocols."
- Conclusion: "persistent memory reduces research cost more consistently than it improves forecast quality."
- 5.3: "evidence capture, κ ... correlates with first-to-last Brier improvement in the memory-on setting (Spearman ρ = 0.74)".
  B.7 adds: "These relationships are correlational. Notebook entries are self-reported, their recorded dates need not always
  be correct".
- **My derived check** (from Table 3 and Table 11; script output in this session):
  - Memory-on minus memory-free Brier, per model:
    - Sol -0.008; 5.5 +0.007; 5.4 -0.003; Opus 4.8 +0.016; Opus 4.6 -0.005; GLM-5 +0.007; Qwen3.5 +0.004;
    - Kimi +0.021; MiniMax -0.014; DeepSeek +0.011; gpt-oss -0.003; Nemotron -0.007.
    - Mean +0.0022, so slightly worse with memory. 6 improve, 6 worsen.
  - Four of the six improvers also show large drops in unusable-output rate:
    - Sol -3.96 pts; MiniMax -3.67; gpt-oss -5.81; Nemotron -6.68.
  - Unusable outputs are scored as uniform (Brier 1-1/K), so part of the notebook's apparent gain is better output
    reliability, not better probabilities.
  - The paper itself makes this point for Sol (paired +0.0010).
- SFT (5.5, B.2):
  - "We collect trajectories from Qwen3-235B-A22B-Thinking-2507 ... and supervised fine-tune Qwen3-30B-A3B-Thinking-2507 for
    three epochs over the full assistant trajectory." Brier falls from 0.924 to 0.749.
  - B.2: "The training use case in Table 4 uses memory-free execution, the same no-belief system prompt".
  - **Correction to the task brief:** the SFT does not use the belief notebook, and the text describes no outcome-based
    filtering of trajectories. It is teacher-trajectory distillation.
  - So the claim "scores feed back into learning" is something the environment offers, not something the SFT demo shows.

## Capability ratings (what the work itself provides)

| # | capability | rating | evidence |
|---|---|---|---|
| 1 | immutable_historical_observations | partial | The frozen, dated 18.8M-article corpus has nested as-of views (I_{<=τt} ⊆ I_{<=τt+1}). The agent's evidence_ledger is "append-only ... mark the old one superseded rather than deleting it". But that ledger is append-only only by prompt instruction: the LLM re-emits the whole JSON each step, and nothing enforces it. The immutable store is the external world corpus, not the agent's own experience log. |
| 2 | historical_world_state | partial | Reconstructs the public information set as of τ (date-filtered corpus) and the daily market belief m_{Q,t}. The market belief is not shown to agents. This is a document set, not a structured world-state snapshot. |
| 3 | historical_epistemic_state | partial | Strict information cutoff per historical date, enforced at search and at scrape. Model knowledge cutoffs predate the evaluation period, and the agent sees "only information available by that date". The agent's belief at t is logged (M_t, p_t, H_t). But the agent cannot reconstruct or question its own past belief at an arbitrary earlier t. It receives only M_{t-1}. Reconstruction is a harness/analysis property, not an agent operation. |
| 4 | historical_policy_objective_state | no | Same fixed prompt and model throughout. No tracking of goals, instructions or policy changes. |
| 5 | execution_checkpoints | partial | "Each step can be reset and rerun". The step boundary (question, τ_t, corpus cutoff, M_{t-1}) acts as a restorable state. There are no snapshots of in-step agent execution. |
| 6 | replay | yes | "each past step can be replayed with the same task and information cutoff". Each event is replayed at "a fixed sequence of historical checkpoints shared by all agents"; 4 rollouts per event-date. |
| 7 | fork_from_historical_state | partial | Re-running a historical step creates a new trajectory, and the logged original is kept. The 4 rollouts keep separate notebooks. The paper never forks a memory-on chain from an intermediate notebook, and no fork operation is described. |
| 8 | counterfactual_action_branches | no | Forecasting is passive, and rollouts are stochastic samples, not alternative actions. |
| 9 | branch_provenance | no | Records are indexed by (event, date, rollout) and keep H_t and M_t. There is no parent, divergence-point or reason metadata. |
| 10 | explicit_current_belief_state | yes | The belief notebook holds assessment p, open_questions, and an evidence_ledger whose entries have claim, supports, rules_out, date_observed, status (active/superseded) and note. "Keep p consistent with the active ledger." |
| 11 | uncertainty_representation | yes | Full probability distribution, open_questions (unresolved items), status superseded, and per-entry quality caveats ("note"). |
| 12 | future_state_rollout | no | No action-conditioned simulation of future states. The prompt suggests "Monte Carlo the paths and count outcomes" for interacting quantities, but these are not conditioned on agent actions and are not part of the environment. |
| 13 | multiple_prospective_branches | partial | A distribution over K mutually exclusive outcomes; the prompt says "Consider the realistic scenarios and how likely each is". The outcome set is fixed by the market; the agent does not generate future branches. |
| 14 | probability_over_futures | yes | p_{Q,t} ∈ Δ^{K-1}, scored by Brier, log loss, accuracy and Info-α. ECE is supported. |
| 15 | backward_requirements | no | Nothing derives present obligations from a desired or feared future. open_questions are forward investigative to-dos, not backward requirements. |
| 16 | intervention_aware_forecasting | no | Forecasts cannot affect outcomes. Market probabilities are deliberately kept out of the prompt. |
| 17 | prevented_futures_preserved | no | Every step is scored against the realized outcome. There is no notion of an averted future. |
| 18 | predicted_vs_realized | yes | Each step is scored against the realized Y: "r_{Q,t} = S(p_{Q,t}, Y)". Feedback is attached to logged trajectories for learning. Caveat: the agent never sees outcomes within an episode, and the SFT demo does not use outcome feedback. |
| 19 | cross_time_state_querying | partial | Agent-facing as-of retrieval over the world corpus (date <= τ). Researcher-side cross-step diff over notebooks: ΔE_t counts ledger entries with τ_{t-1} < date_observed <= τ_t. No agent-facing state_at(t) or diff(t1,t2) over its own state. |
| 20 | unified_temporal_abstraction | no | The "forecast episode" formalism links past information states, the carried belief and outcome probabilities. It has no counterfactual or branch state and no single addressable temporal-state abstraction. |

## How it threatens the project

1. **Harness and benchmark methodology: the project cannot claim novelty here (HIGH).** Forecast-Dojo already provides:
   - replay of a chronological world at fixed historical dates with a strict information cutoff;
   - ground truth hidden from the agent and scored per step;
   - identical tool budgets across memory conditions;
   - per-step trajectory logging;
   - reuse of the same episodes for training.

   The project's CLAUDE.md rules have direct analogues: rules 3 (no ground-truth leakage), 5 (same model, tools, events
   and budgets) and 8/9 (traces, determinism). Its "aligned evaluation ... at identical information states" is the
   project's contestant-isolation design, in the forecasting domain.
2. **Explicit belief state, done better than a toy.** The notebook is:
   - an append-only evidence ledger;
   - with per-entry `date_observed`, which is close to valid time;
   - with `status: superseded`, i.e. supersede and never delete;
   - with provenance notes and open questions.

   This is a concrete prior instance of "never overwrite, supersede with provenance" at the belief level, carried across
   time. Capabilities 10 and 11 are not novel.
3. **Direct negative evidence for the core bet (MEDIUM-HIGH).** Under controlled, matched conditions, an explicit structured
   belief state carried across time:
   - did not improve decision quality (6/12; mean ΔBrier +0.002);
   - did not speed within-event improvement (0.059 vs 0.064 Brier drop);
   - did reduce cost (median -24%) and output failures.

   The memory-free agent has date-filtered dense retrieval over the full world log. That is close to the project's
   null-hypothesis baseline (EXPERIMENT.md §7: "append-only raw event log ... embeddings/vector retrieval ... metadata
   filters for time"). So this is outside evidence that the null tends to survive on quality and that structured state
   pays off mainly in cost.
   - The project's kill rule (§13) requires "comparable total inference cost". Forecast-Dojo suggests cost is where a
     difference will show up first.
   - Its reliability effect (fewer unusable outputs) is a confound the project's scorer must separate. Use paired
     comparisons on valid outputs, as Forecast-Dojo does for GPT-5.6 Sol.

## What it does NOT cover (where the project's residual hypothesis could still live)

- **No consequential decisions or commitments by the agent.** Forecasts are passive. The agent never takes an action whose
  significance a later event can change. Nothing tests reopening or remediating earlier decisions, which is the project's
  benchmark target (EXPERIMENT.md §1: "later information changes the significance of earlier decisions").
- **All relevant state is public and can be retrieved again.** The memory-free agent can rebuild everything from the dated
  corpus at each step, so a carried belief state is mostly redundant except for cost. In the project's world, the agent's
  own past decisions and rationales are private, so re-retrieving the world does not recover them. That regime is untested
  here.
- **Very short histories.** About 3.5 steps per event, with at most 10. The project's continue rule needs an advantage that
  grows with history length, causal depth or temporal lag. None of these are varied here.
- **Only a lossy, latest-only belief state.** Earlier notebooks M_1..M_{t-2} are not addressable by the agent, and there is
  no traversal back to "what I believed at τ_1 and why". The negative result is about a carried summary, not about
  addressable, versioned past states with causal links.
- **No counterfactual or branching operations, no backward requirements, no intervention-aware or reflexive forecasts, no
  prevented-future accounting, no policy/identity tracking.** (Capabilities 4, 8, 9, 12, 15, 16, 17, 20 are all "no".)
- **No comparison against RAG over the agent's own past trajectories.** The contrast is notebook vs nothing (plus world
  retrieval). It is not structured temporal state vs strong memory retrieval over past interactions.

## Net assessment

- Threat level: **HIGH** to novelty claims about:
  - replayable as-of evaluation with an epistemic cutoff;
  - explicit carried belief state with supersede-not-delete provenance;
  - predicted-vs-realized scoring.
- **MEDIUM-HIGH** as prior negative evidence against "structured temporal state improves decisions". It favours the null
  hypothesis wherever the needed history can be retrieved again from a shared world record.
- It does not touch the project's narrower hypothesis: agent-private decision provenance + later event → reopen/remediate,
  with advantage growing in history length and causal depth.
- If the project keeps that hypothesis, it should cite Forecast-Dojo as the closest controlled negative result and design
  for its confounds:
  - report cost and quality separately;
  - use paired comparisons on valid outputs;
  - control for output-failure rates;
  - match tool budgets.

## Could not verify

- The arXiv page itself (blocked). The full text comes from a third-party MinerU conversion of the v1 PDF. Figures are
  images (not viewed), and Table 1's check marks were lost.
- The code/data repository. The PDF abstract claims "Our code and data are publicly available", but no URL survives in the
  converted text and GitHub code search found no official repo.
- Whether the SFT trajectories were filtered by outcome. None is described: "full assistant trajectory".
- Any venue or peer review.
- Model names and cutoff dates (e.g., "GPT-5.6 Sol", "Claude Opus 4.8") are as reported in the paper; I did not check them
  independently.
