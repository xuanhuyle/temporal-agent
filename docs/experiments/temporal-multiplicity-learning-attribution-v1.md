# Temporal Multiplicity, Existential Experiment 1: learning attribution (v1)

| | |
|---|---|
| **Verdict** | **NO_MEANINGFUL_SIGNAL**: an equal-budget sequential baseline made the same developmental decision in 16/16 paired decisions. Both conditions had zero regret, and a single unaided reflection also had zero regret (96/96). |
| Stop condition | A (real paired result) and B (the baseline trivially solves the task). |
| Real-model calls | 456 state executions plus 128 decision calls (v2); 39 plus 12 in the pilot. All calls used the same model. |
| Raw data | `results/temporal-multiplicity/learning-attribution-v1/` (`pilot/`, `v2/`, `scripts/`) |
| Code | `src/multiplicity_experiments/learning_attribution.py`, `experiments/multiplicity_learning/episodes.json`. The v2 design was frozen at `d0b2f18`, before any v2 output. |

## 1. Question

Can an agent use executable earlier and ablated versions of itself to identify what actually caused it to become more capable? And can it use that knowledge to choose what to learn next better than the same model using ordinary reflection on the same compute?

## 2. World and conditions

**World.** A fictional skill: "Orbital Post" parcel pricing, scored exactly by the evaluator.
- Price = base price by weight band, times a zone factor (A1/B2/C3/D4), times 2 for express, plus 9 for fragile, rounded up to a multiple of 5.
- Knowledge is held as text modules on `AgentState`.
- A state's capability is measured by running the model with only that state's modules on 16 tasks. Every state is run 3 times (replicates).
- The effects of modules are therefore real model behaviour, not stipulated numbers. That includes redundancy, interference, interaction and implicit rules.

**States.** All states are made with the existing primitive:
- `TemporalMultiplicity.snapshot` of S3;
- `fork(epistemic_cutoff=k)` for the past selves S0..S2;
- `fork(mutations=(Mutation("forget.module:X"),))` for ablations. This is a one-line `forget.` mutation added to `apply_mutations`.
- A candidate is added through a `knowledge.` mutation.

**Decision (v2).**
- The reference capacity is full. The agent must learn one of 3 candidates and forget one of its 3 learned modules. That gives 9 possible actions, all evaluated offline on a held-out task split.
- Value of an action = acc(S3 − X + C) − acc(S3) on held-out tasks.
- Regret = best action value − chosen action value.

**What both conditions see:**
- the learning history S0..S3;
- the full text of every module held;
- dev-split accuracy after each learning step, broken down by task family (correct/attempted over 3 runs);
- the candidate titles only.

| condition | additionally gets |
|---|---|
| **multiplicity** | Dev-split results of the forked selves S3 − X for every learned X. S3 − last is reported as identical to S2. |
| **baseline** | "You cannot run any further evaluations." It spends the matched budget on 6 independent reflections and a synthesis that weighs them. |

**Subject isolation.**
- Every subject call is a Claude Code `web-fetch` subagent. Its only tool is WebFetch, and it has no file or shell access.
- It receives only the constructed prompt and must return a JSON schema.
- Across all 586 v2 subject agents there were 584 tool calls, all of them the structured-output return; there were 0 WebFetch calls. The other 2 agents were cut off when the first executor run was stopped and never returned.
- Prompts never contain held-out tasks, candidate contents or the analyst's notes. This is enforced by `tests/test_multiplicity_learning_attribution.py`.
- `claude -p` was not used.

## 3. Compute budget (per decision; measured from subagent transcripts)

| condition | calls | input tokens | output tokens |
|---|---|---|---|
| multiplicity | 1 decision + 6 ablation executions (2 non-trivial ablations × 3 replicates) | ≈ 74k | ≈ 7.4k |
| baseline | 6 reflections + 1 synthesis | ≈ 78k | ≈ 14.9k |

About 9k of each call's input is the subagent's fixed harness prompt, the same in both conditions. The ablation executions are per episode and shared by its 2 repeats; they are counted per decision here. The baseline never spent less than multiplicity.

## 4. Episodes (v2)

The initial modules always stay. "Designed trap" is the analyst's note, which is never shown to the subject. Δ is the measured held-out effect, acc(S3) − acc(S3 − X).

| ep | start | learned in order (held-out Δ) | candidates | designed trap |
|---|---|---|---|---|
| E1 | ZONE | EXAMPLES (+62), BASE (+35), FRAG (+19) | EXPR, HEAVY, MEMO | EXAMPLES is the only source of rounding; its chronological gain is masked |
| E2 | BASE | EXAMPLES (+69), ZONE (0), EXPR (+19) | FRAG, HEAVY, CUSTOMS | EXAMPLES carries rounding and zone factors, so ZONE is redundant |
| E3 | BASE, ROUND | ZONE_OLD (−12), ZONE (+25), FRAG (+25*) | EXPR, ERRATA, HEAVY | conflicting zone table; FRAG has no tasks |
| E4 | BASE, ROUND | ZONE (+44), MEMO (0), ZONE_OLD (0) | FRAG, EXPR, ERRATA | conflict learned last; irrelevant memo |
| E5 | BASE, ZONE | ROUND (+12), EXAMPLES (0), FRAG (+19) | EXPR, HEAVY, MEMO | redundant pair (ROUND / EXAMPLES) |
| E6 | ZONE, ROUND | BASE (+67), CUSTOMS (+2), FRAG (+35) | HEAVY, EXPR, EXAMPLES | control |
| E7 | ROUND | ZONE (+62), CUSTOMS (0), BASE (+81) | HEAVY, ERRATA, EXPR | interaction: ZONE alone scores 0, and all gain shows up when BASE arrives |
| E8 | ZONE | MEMO_R (+62), BASE (+62), CUSTOMS (0) | EXPR, HEAVY, FRAG | rounding is buried in a "service memo"; its chronological gain is 0 |

\* E3 has no fragile tasks. FRAG's measured +25 comes from prompt sensitivity: removing FRAG changes which of the two conflicting zone tables the model follows. It is a measurement artefact, not a real effect.

The environment does defeat chronology. A rule that forgets the module with the smallest chronological gain has a mean forget-regret of 0.21: it fails E1 (0.52), E7 (0.69) and E8 (0.50). A rule that forgets the module with the smallest dev-split ablation effect has a mean forget-regret of 0.00.

## 5. Raw paired outcomes (v2, held-out)

Each cell gives the chosen action as `learn/−forget`, then its gain in accuracy points. r0/r1 are two independent repeats.

| ep | best action (gain) | multiplicity r0 · r1 | baseline r0 · r1 | regret M · B |
|---|---|---|---|---|
| E1 | EXPR/−FRAG (+19) | EXPR/−FRAG · EXPR/−FRAG | EXPR/−FRAG · EXPR/−FRAG | 0 · 0 |
| E2 | FRAG/−ZONE (+19) | FRAG/−ZONE · FRAG/−ZONE | FRAG/−ZONE · FRAG/−ZONE | 0 · 0 |
| E3 | EXPR/−ZONE_OLD (+50) | same · same | same · same | 0 · 0 |
| E4 | FRAG/−MEMO or −ZONE_OLD (+31) | FRAG/−ZONE_OLD · same | FRAG/−ZONE_OLD · same | 0 · 0 |
| E5 | EXPR/−ROUND or −EXAMPLES (+38) | EXPR/−EXAMPLES · same | EXPR/−EXAMPLES · same | 0 · 0 |
| E6 | HEAVY/−CUSTOMS (+33) | same · same | same · same | 0 · 0 |
| E7 | HEAVY/−CUSTOMS (+19) | same · same | same · same | 0 · 0 |
| E8 | EXPR/−CUSTOMS (+38) | same · same | same · same | 0 · 0 |
| **all** | | **16/16 best, mean regret 0** | **16/16 best, mean regret 0** | |

Candidate rankings also agreed: both conditions put the best candidate first in every decision. The 96 individual baseline reflections, each 1/7 of the budget, chose the best action 96/96 times.

## 6. Attribution (causal effect class per learned module)

The truth is the class of the held-out Δ: essential ≥ 25, helpful ≥ 12, harmful ≤ −12, otherwise no_effect.

| | hits |
|---|---|
| multiplicity | 33/48 |
| baseline (synthesis) | 36/48 |
| single reflections | 221/288 |

Where the conditions differ, the ablation evidence imported dev-split noise into multiplicity's labels:
- E2: ZONE was labelled "harmful" from 94% vs 85%.
- E6: CUSTOMS was labelled "harmful" from 75% vs 71%.
- E5: ROUND was labelled no_effect. Its truth is helpful (+12), a borderline case.

Most baseline misses are essential-vs-helpful boundary calls (E1 FRAG, E2 EXPR, E5). Neither condition caught E3's ZONE_OLD as harmful: on the dev split it measured 0.

The baseline reached the traps' answers from the module contents and per-family breakdowns. Verbatim, from the r0 syntheses:
- **E1, on EXAMPLES:** "It is my only source for rounding."
- **E8:** "MEMO_R is essential, but this is worked out from the arithmetic, not measured."
- **E7:** "ZONE is essential, even though adding it at S1 coincided with a drop from 19% to 0%. That drop happened while no base price existed, so ZONE had nothing to multiply."

## 7. Pilot and the one redesign

The pilot had 3 episodes, 1 sample per state, and a plain "learn one more" decision. Both conditions chose identically in 3/3 with zero regret, so the choice was driven only by which task family was uncovered. Attribution was 3/3 for both in P2 and P3. In P1, a single-sample ablation misled multiplicity into calling MEMO essential, while the baseline said no_effect; P1's held-out S3 (25%) also disagreed with its dev S3 (100%).

The pilot therefore answered "does not discriminate". The single allowed redesign (v2) changed two things:
- **Capacity constraint:** the agent must also forget one learned module, so attribution changes the decision.
- **Noise:** 3 replicates per state.

v2 is the first full result. It was not redesigned again.

## 8. Major confounds

1. **Ceiling.** Both conditions, and single reflections, sit at zero regret, so the experiment cannot show a difference smaller than "both perfect". The optimal action was inferable from three things:
   - module content, which shows which modules are irrelevant, conflicting, redundant or carry an implicit rule;
   - per-family breakdowns, which show what each step fixed;
   - candidate titles, which point to the uncovered family.

   Readable module text and family-level history were part of the spec ("content of all modules", "naturally available measurements"). Removing them would have weakened the baseline artificially.
2. **Measurement noise.** Only 16 tasks per state; many replicates were identical, but the conflicting-table states flip between samples. The attribution truth for E3 is unstable, and dev-split ablations sometimes mislead.
3. **Subject context.** The subagent harness adds a fixed system prompt, the same in both conditions and carrying no ground truth. The served model per subagent was not independently verified. Every call inherited the session's model, and the session's configured and last-served models match.
4. **Benchmark fixes during analysis**, each applied identically to both conditions:
   - Free-text `choice` answers ("Learn EXPR and forget EXAMPLES.") are resolved to the single key they name (`dd4c46d`).
   - This affected 8/16 multiplicity and 2/16 baseline final answers, and left no invalid choices. Without it, multiplicity would have been penalised.
5. **Logistics.** The executor run was split into 4 parallel workflows mid-run for throughput. The 18 outputs already completed were reused; their prompts were identical. There were 2 repeats per decision, and sampling temperature was not controlled.
6. **Generality.** One synthetic domain, 8 episodes and 1 model. No p-values were computed.

## 9. Verdict: NO_MEANINGFUL_SIGNAL

The agent could execute and intervene on ablated versions of itself, but this produced no developmental knowledge or decision that the same model, on equal or less compute, failed to reach by ordinary reasoning over its history and module contents:
- next-learning decisions: identical, 16/16, both at zero regret;
- attribution: no better (33/48 vs 36/48), with the experimental evidence adding noise.

The environment did make chronology insufficient; a chronology-only rule loses 0.21 per decision. However, the model does not reason from chronology alone when the content of what it learned is readable.

The decisive open variable is whether learned knowledge is semantically inspectable. Here it always was, and inspection replaced experimentation. A future test of the primitive would need learned state whose causal role cannot be read off its content. One example is opaque or parametric modules with honest content, where the only route to attribution is intervention.

This is recorded as an untested proposal. It is not built here and is not a rescue of this result.

**Re-score from the raw outputs.** Model calls go through `scripts/` with Claude Code `web-fetch` subagents. The two commands below reproduce `v2/evals.json` and `v2/scored.json` byte-identically:

    R=results/temporal-multiplicity/learning-attribution-v1/v2
    PYTHONPATH=src python -m multiplicity_experiments.learning_attribution score-evals --jobs $R/exec_jobs.json --outputs $R/exec_outputs.json --out evals.json
    PYTHONPATH=src python -m multiplicity_experiments.learning_attribution score-decisions --evals evals.json --decisions $R/decisions.json --out scored.json
