# Deep-read 5: "Calibration Is Not Control: Why LLM-Agent Oversight Needs Intervention" (arXiv 2606.21399)

## Bibliographic facts (verified)
- Title: "Calibration Is Not Control: Why LLM-Agent Oversight Needs Intervention".
- Authors: Chubin Zhang, Zhenglin Wan, Xingrui Yu, Jingxuan Wu, Qi Wen, Pengfei Zhou, Wangbo Zhao, Ivor Tsang.
- Venue: arXiv preprint, cs.AI, v1, published 2026-06-19T13:08:17Z. Canonical URL: https://arxiv.org/abs/2606.21399.
- Code: none found.
  - TengJiao33 digest record: `"has_code": false, "repo_url": ""`.
  - cyk1337 paper-daily-site record: `"github":null,"project":null`.
- Sister paper from the same group, same day: "Don't Blindly Trust It: How Unreliable Feedback Breaks Tool-Using LLM Agents" (https://arxiv.org/abs/2606.21409). It uses a matched-loop counterfactual design that varies only the returned observation.

## Access limits (read this first)
- I did NOT read the full text. arxiv.org, alphaxiv and HF are blocked, and the WebSearch budget was exhausted (200/200) when this task started.
- GitHub code search for body-only phrases ("scalar abstraction loss", "control sufficiency" plus "intervention advantage") returned 0 hits, so no full-text mirror is indexed.
- Evidence tiers used below:
  - [ABS] The verbatim abstract. Identical copies appear in at least five independent records:
    - a local cs.AI daily dump: `scratchpad/lit/repos/pf/daily/23-Jun-2026/AI/README.md`;
    - `scratchpad/lit/bo/daily.json`;
    - `repo2anonymous/uq-agents-survey-artifacts/data/corpus.json`;
    - `kidkuddy/loop-engineering-mapping-study` batch-034;
    - `TengJiao33/ArXiv_Daily_Digest/.../2026-W26/papers.jsonl`.
  - [SUM] An LLM-generated summary on `cyk1337/paper-daily-site` (`tag/intervention-advantage.txt`). It refers to section numbers, so it was apparently built from the full text, but it is not primary.
  - [CIT] A third-party citing paper: ControlScope (CMU/Tsinghua, full text mirrored at `ZhangCurosr/zhangcursor-papers-arxiv-cl-001/2026-09-29/ControlScope-.../full.md`).
- The GitHub note named in `how_found` (`usaginoki/mbzuai-master-thesis/Backlog/ZhangC2026 - Calibration Is Not Control.md`) is itself marked "summary: ABSTRACT-ONLY".

## Verbatim snippets

### [ABS] arXiv abstract
> "Runtime oversight for LLM agents is commonly framed as scalar risk prediction: estimate failure likelihood, confidence, or uncertainty, then intervene once the score crosses a threshold. We argue that this framing targets the wrong object for control. The relevant question is not how likely the agent is to fail if it continues, but whether an available intervention would improve the outcome. Two trajectory prefixes can have the same risk estimate while requiring different actions, because one remains recoverable and the other does not. We formalize this mismatch as target error and identify intervention advantage, the expected utility gain from intervening rather than continuing, as the decision object for oversight. To measure this mismatch, we introduce prefix branching, a same-prefix counterfactual protocol that executes candidate actions from identical trajectory states. Across four benchmarks, action-conditioned control yields regime-dependent gains over scalar routing. In a calibration decomposition, recalibrating the same scalar score improves prediction metrics but leaves control regret unchanged, showing that calibration alone does not repair target error. A simple prefix-only action-conditioned controller substantially reduces regret in the strongest interactive regime, from 0.506 to 0.110 on ALFWorld. Gains shrink when interventions are weak or when scalar routing already preserves intervention-relevant information. These results suggest that LLM-agent oversight should move from calibrated risk scoring toward action-conditioned value estimation."

### [SUM] paper-daily-site summary (summary_en, LLM-generated)
> "The paper formalizes control sufficiency and target error: a scalar summary incurs abstraction loss when it merges states that require different optimal actions. The control-relevant quantity is intervention advantage, the expected utility gain from intervening rather than continuing. To measure this quantity empirically without lookahead leakage, the paper introduces prefix branching: at a shared trajectory prefix, branch execution of candidate actions such as continue, defer, repair, and stop. This yields counterfactual outcomes from an identical state, making it possible to estimate oracle actions, scalar abstraction loss, and controller regret."

> "Focus on Section 2 for the formalization of control sufficiency and Section 3 for the prefix branching protocol."

The zh version gives the same action set: "分别执行 continue / defer / repair / stop 等候选动作，构造无未来信息泄漏的反事实对照" ("execute candidate actions such as continue / defer / repair / stop, building counterfactual comparisons with no leakage of future information").

### [CIT] ControlScope (independent authors) on this paper
> "Intervention value and execution interfaces. Zhang et al. (2026a) evaluate interventions by branching from the same trajectory prefix and distinguish intervention value from continuation risk. ... We use same-state branching to study the executable scope of a revision and the outcome of the operation an agent selects."

### [CIT, abstract-level check] pneuma-lab audit
`fireheartjerry/pneuma-lab/docs/research/neurips-2026-workshop/21-pivot-and-claim-retirement.md`:
> "2606.21399 | Calibration Is Not Control (Zhang) | PARTIAL — same-prefix branching yes; the 100% replay match and discard rule not stated".

The audit itself says: "Verification was against abstracts only". So the replay-verification mechanism remains unknown.

## Mechanism (as far as verifiable)
1. **Decision object.**
   - Passive forecast: risk = P(fail | continue).
   - Intervention advantage: A(a | prefix) = E[U | do(a), prefix] - E[U | continue, prefix], for a in {defer, repair, stop, ...} [ABS + SUM].
2. **Target error / scalar abstraction loss.** A scalar score merges prefixes that need different optimal actions, for example a recoverable and an unrecoverable prefix at the same risk [ABS + SUM].
3. **Prefix branching.**
   - For each prefix, restore the identical trajectory state.
   - Execute each candidate action, then let the episode finish.
   - Record the outcomes and derive the oracle action and the regret.
   - The SUM describes this as "without lookahead leakage" [ABS + SUM].
   - How the state is restored (environment snapshot or deterministic replay) is NOT verified.
4. **Calibration decomposition.** Recalibrating the scalar improves prediction metrics; control regret is unchanged [ABS].
5. **Controller.**
   - "prefix-only action-conditioned controller": on ALFWorld, regret falls from 0.506 to 0.110.
   - The gains are "regime-dependent" across four benchmarks; only ALFWorld is named in the abstract [ABS].
   - "Prefix-only" most plausibly means the deployed controller sees only the prefix and does not roll out branches at decision time. Branching supplies the labels and the evaluation. This is inferred, not verified.

## Capability ratings (only what the work provides)

| # | Capability | Rating | Basis |
|---|---|---|---|
| 1 | immutable_historical_observations | no | Prefixes are held fixed as experimental units. There is no append-only observation store as an agent feature. |
| 2 | historical_world_state | partial | The harness restores the environment state at a prefix to branch ("identical trajectory states"). It is not a queryable reconstruction, and the mechanism is unknown. |
| 3 | historical_epistemic_state | partial | The controller is "prefix-only", and branching is "without lookahead leakage" [SUM]. Restoring the prefix restores the agent's context at t. This is a cutoff inside one episode, not belief reconstruction from long-lived memory. |
| 4 | historical_policy_objective_state | no | Not addressed. |
| 5 | execution_checkpoints | partial | Implied: candidate actions run "from identical trajectory states". The checkpoint mechanism is not described in the available text. |
| 6 | replay | partial | Continuations are re-executed from a historical prefix for every candidate, including "continue". This is an offline evaluation harness, not an agent runtime feature. Whether the prefix is replay-verified is not stated in the abstract. |
| 7 | fork_from_historical_state | yes | "same-prefix counterfactual protocol that executes candidate actions from identical trajectory states". ControlScope: "branching from the same trajectory prefix". |
| 8 | counterfactual_action_branches | yes | Candidate actions (continue/defer/repair/stop) are executed as counterfactual branches. They are used to estimate oracle actions and regret, not committed. |
| 9 | branch_provenance | partial (inferred) | Advantage per (prefix, action) requires keying each branch by its divergence prefix and action. No provenance or lineage data model is documented. |
| 10 | explicit_current_belief_state | no | None. |
| 11 | uncertainty_representation | partial | Scalar failure likelihood, confidence and uncertainty are the baselines, and their calibration is measured. There are no structured unresolved items. |
| 12 | future_state_rollout | partial | Action-conditioned futures are executed in the benchmark environment, not simulated by the agent. The controller outputs action-conditioned values, not future states. |
| 13 | multiple_prospective_branches | partial | Several candidate-action futures per prefix exist simultaneously in the protocol. At runtime only value estimates over actions exist. |
| 14 | probability_over_futures | partial | The failure probability under continuation and the expected utility per action are expectations over futures. There is no explicit distribution over enumerated imagined futures. |
| 15 | backward_requirements | no | It chooses among interventions. It does not derive present obligations or preconditions from a desired or feared future. The "recoverable vs not" framing is adjacent to option preservation, but no derivation is offered. |
| 16 | intervention_aware_forecasting | yes | The core contribution: a passive risk forecast vs an action-conditioned forecast ("intervention advantage"). Reflexive forecasting (the forecast changing the world by being made) is not covered. |
| 17 | prevented_futures_preserved | partial (inferred) | The same-prefix design yields the continue-branch outcome even when an intervention would avert failure. A passive failure forecast is therefore checked against a counterfactual continuation, not the intervened outcome. There is no persistent, labelled store of averted forecasts, and the design works only in resettable simulators. |
| 18 | predicted_vs_realized | yes | The calibration decomposition compares predicted risk with realized branch outcomes. Regret is computed against oracle outcomes. |
| 19 | cross_time_state_querying | no | None. |
| 20 | unified_temporal_abstraction | no | The prefix/branch unit spans history, counterfactual and outcome inside one episode as an evaluation device. There is no agent-facing temporal abstraction. |

## How it threatens the project's novelty (precise)
1. **Intervention-aware forecasting for LLM agents is not new.** This paper makes the passive vs action-conditioned distinction the central object of LLM-agent oversight. It also gives a formal name for the failure of passive scoring ("target error"). Two other agent papers already do counterfactual intervention evaluation, both recorded with URLs in `notes/sweep-performative-prevented.md`:
   - Vasudev et al. 2602.03338;
   - COTA 2608.21027 ("pairwise supervision constructed from same-prefix counterfactual branches").
   Any project claim that "agents should forecast conditioned on their own interventions, not passively" is prior art as of June 2026.
2. **"Fork from identical state and compare actions" is an established agent-evaluation protocol.** Prefix branching is that protocol, and ControlScope (Sept 2026) already reuses "same-state branching" as standard method. The project's "never overwrite time, fork it" and counterfactual branches therefore cannot be claimed as a new evaluation idea for agents.
3. **Calibration is the wrong yardstick.** The calibration decomposition shows directly that better passive forecasts do not buy better control. This undercuts a predicted-vs-realized calibration loop as the project's value claim unless the loop is tied to action selection.
4. **Adversarial implication for the project's thesis.**
   - The regret reduction comes from a "simple prefix-only" controller. Branching is used to produce labels and to evaluate, apparently not at decision time.
   - If that holds, a learned prefix-to-action-value map, which is a strong non-temporal baseline, may capture most of the benefit. Explicit runtime temporal navigation would then add nothing.
   - The paper also reports that gains "shrink when interventions are weak or when scalar routing already preserves intervention-relevant information". Action-conditioned machinery pays only in narrow regimes.
   - The project's benchmark should include such a baseline and should report the regime boundary.

## What it does NOT cover (residual space for the project)
- **Long-lived agents and cross-session memory.** All of it is within-episode runtime oversight (ALFWorld-style). There is no reconstruction of past belief states from a persistent store and no as-of or diff queries.
- **Retrospective reopening.** The overseer decides at prefix t whether to intervene now. It does not detect that a later event changes the significance of an earlier, already-committed decision and then reopen it. This is the project's benchmark target.
- **Deployment-time prevented forecasts.** Prefix branching needs a resettable simulator. In deployment only one branch is realized, so preserving and labelling averted forecasts ("annulled / unverifiable"), and scoring them without a runnable counterfactual, stays open.
- **Other temporal dimensions.** It covers none of:
  - policy, objective or identity history;
  - backward requirements;
  - reflexive forecasts;
  - an explicit belief state;
  - a unified temporal abstraction.
- **Who forecasts.** The overseer is a controller external to the agent, not the agent interrogating its own past or future selves.

## Could not verify
- Full text, including:
  - the formal definitions (control sufficiency, target error, scalar abstraction loss);
  - the identity of the other three benchmarks;
  - the units of the 0.506 and 0.110 regret figures;
  - how prefix states are restored (snapshot or replay) and whether replay fidelity is checked;
  - whether branches are sampled repeatedly to estimate expected utility;
  - how the controller is trained;
  - whether the deployed controller ever branches at decision time.
- Any code release. None found; two digests record no code.
- The SUM details (the continue/defer/repair/stop set, "without lookahead leakage", the section numbers) come from an LLM-generated summary only.

## Sources
- https://arxiv.org/abs/2606.21399 (canonical; listed in every index record; not fetchable here)
- https://github.com/cyk1337/paper-daily-site (file `tag/intervention-advantage.txt`, via raw.githubusercontent.com)
- https://github.com/ZhangCurosr/zhangcursor-papers-arxiv-cl-001 (file `2026-09-29/ControlScope-Workflow-Revision-and-Reliability-in-LLM-Agents_a3d68506/full.md`)
- https://github.com/usaginoki/mbzuai-master-thesis (file `Backlog/ZhangC2026 - Calibration Is Not Control.md`; cloned to `repos/usaginoki_mbzuai-master-thesis`)
- https://github.com/TengJiao33/ArXiv_Daily_Digest (file `data/editing-reliability-evaluation/2026-W26/papers.jsonl`)
- https://github.com/repo2anonymous/uq-agents-survey-artifacts (files `data/corpus.json` and `bib/core-corpus.bib`)
- https://github.com/fireheartjerry/pneuma-lab (file `docs/research/neurips-2026-workshop/21-pivot-and-claim-retirement.md`)
- https://github.com/spotter-agent/spotter (file `docs/reference.md`; a practitioner design that adopts Advantage(action | prefix))
- https://arxiv.org/abs/2606.21409 (sister paper, title verified from the daily index)
- Raw downloads: `scratchpad/lit/deep5_raw/`
