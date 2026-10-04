# Temporal Multiplicity — Long-Horizon Calibration v1
## Find the operating regime before testing the primitive

You are working in:

`xuanhuyle/temporal-agent`

Start from the latest `research/temporal-multiplicity-long-horizon-v1` branch / PR #6.

Create a new branch:

`research/temporal-multiplicity-calibration-v1`

This is **not** another Temporal Multiplicity experiment.

It is a bounded engineering calibration task whose sole purpose is to locate a realistic long-horizon regime where a strong ordinary agent begins to suffer non-trivial, reproducible degradation from repeated context compaction.

Do **not** run conditions A/B/C.
Do **not** execute historical selves as a treatment.
Do **not** try to prove Temporal Multiplicity.
Do **not** build a new agent framework.

The output of this task is a calibrated operating point — or a clear conclusion that the current environment cannot produce one cheaply.

---

# 0. Why this task exists

PR #6 correctly returned `NO_HEADROOM`, but the environment had a design property that made that result unsurprising:

> a perfect compactor could preserve every scored rule losslessly in <=50% of persistent memory.

That protected the ordinary agent from the compression pressure we were trying to study.

The correction is not to handcraft harder traps.

The correction is to make **compression pressure an explicit independent variable** and empirically map the baseline degradation curve before authorizing any expensive hypothesis test.

The engineering question is:

> **At what compression pressure does a strong long-running agent transition from near-lossless continuity to meaningful but non-catastrophic degradation?**

That is the regime a later A/B/C experiment should use.

---

# 1. Reuse the existing harness

Reuse as much as possible from:

- `src/multiplicity_experiments/long_horizon.py`
- `experiments/multiplicity_long_horizon/runtime.js`
- PR #6 raw/result conventions

Do not rewrite the long-horizon runtime unless a small parameterization is required.

The existing strengths should remain:

- real repeated model-written compaction;
- bounded persistent memory;
- bounded working context;
- immutable raw archive;
- exact ground truth;
- checkpoint logging;
- isolated subject agents;
- future-blind generic compaction prompt.

The main change should be **parameterizing state load / compression pressure**, not inventing a new benchmark architecture.

---

# 2. Controlled variable: compression pressure

Define an explicit calibration variable:

[
R = \frac{L}{M}
]

where:

- `L` = the character length of a canonical, lossless representation of all **currently active potentially decision-relevant state** at the end of the lifetime;
- `M` = persistent memory budget in characters.

Do not use total raw transcript length as `L`; filler/noise alone should not define pressure.

`L` should include the active rules, qualifiers, commitments, current exceptions, and other state that an ideal compactor would need to preserve to answer the scored probes correctly.

Use a deterministic canonical representation so `R` is measurable before any model call.

**Critical anti-rigging requirement: future relevance must be hidden at compaction time.**
All generated semantic units in `L` must be plausible future-relevant state. The subset ultimately scored should be selected by a separate fixed holdout seed/procedure that is determined before model execution but not exposed to the subject or compactor. Do not choose probes after seeing what the compactor forgot. This converts the problem into genuine information triage rather than hand-selecting "important" facts.

The raw immutable archive must retain all source records, including units not selected for final scoring.

The old PR #6 environment was approximately `R ~= 0.42`.

Calibrate a small pressure sweep around and beyond the capacity boundary.

Suggested levels:

- `R ~= 0.5`
- `R ~= 1.0`
- `R ~= 2.0`
- `R ~= 4.0`

You may adjust the exact levels slightly if the generator makes those ratios awkward, but preserve the basic sweep from comfortable capacity to severe compression.

Prefer changing **decision-relevant state load** while keeping the same memory budget and compaction policy, rather than shrinking memory arbitrarily.

Possible knobs:

- number of active independent rules;
- number of active qualifiers/exceptions;
- number of unresolved commitments;
- number of interacting rule clauses;
- lifetime length / number of state updates.

Do not create semantic ambiguity merely to increase load.

Do not add adversarially misleading summaries.

---

# 3. Static generator validation — zero model calls

Before any real-model calibration, generate many seeds offline.

For each pressure level, verify:

1. achieved `R` is close to target;
2. ground truth is unambiguous;
3. probe answers are time-invariant after each rule becomes effective;
4. no two generated rules create contradictory truth conditions unless the benchmark explicitly models a deterministic precedence rule;
5. entity/template wording does not create accidental ambiguity like the Brandt Hydraulik case in PR #6;
6. the same generic compaction prompt will be used at every pressure level;
7. no future diagnostic relevance is exposed to the compactor.

Run at least hundreds of offline generator seeds if cheap.

This phase should cost no model calls.

If the generator cannot achieve clean pressure levels without extensive redesign, stop and report that before spending model budget.

---

# 4. Calibration metric

For each baseline trajectory, measure capability on a **fixed small probe battery** at selected checkpoints.

Do not probe every checkpoint if that explodes cost.

We need enough measurements to estimate continuity, not a complete learning curve.

For example:

- pre-first-compaction / early checkpoint;
- middle checkpoint;
- final checkpoint.

The important quantities are:

## Final retention accuracy

[
A_{final}
]

Accuracy on active rule/clause probes at the final state.

## Regression rate

Fraction of probe units for which:

[
A_{earlier} - A_{final} \ge 0.5
]

with `A_final <= 0.5`.

## Compaction distortion rate

Where possible, distinguish:

- information absent from memory;
- information retained but semantically distorted;
- information correctly retained but model applies it incorrectly.

Keep this diagnostic simple; manual inspection of failures is acceptable.

---

# 5. What regime are we looking for?

Do not optimize for maximum failure.

We want the **crossover regime**.

A suitable operating point should roughly satisfy:

- final capability materially below ceiling;
- final capability materially above collapse;
- multiple independent regression units;
- regressions are reproducible;
- regressions are not primarily benchmark ambiguity.

A useful target band is approximately:

[
0.50 \le A_{final} \le 0.80
]

This is a guide, not a magical statistical threshold.

The desired qualitative state is:

> the agent is still competent, but bounded memory has created meaningful continuity failures.

If `A_final > 0.9`, pressure is probably too low.

If `A_final < 0.3`, pressure is probably too high for a useful later diagnostic experiment.

---

# 6. Real-model call budget — strict

This calibration must be cheap.

Hard target:

> **20–40 subject-model calls total across the entire calibration, including compactions, probes, and retrieval sanity checks.**

Before launching each batch, print/record the expected incremental and cumulative call count.

Hard maximum without explicit user authorization:

> **50 subject-model calls total.**

Count compactions, decisions, and probe calls.

If the existing runtime would exceed this, simplify the calibration sampling:

- fewer trajectories;
- fewer probe checkpoints;
- fewer lifetime requests;
- parallelize only where it does not increase calls.

Do not spend hundreds of calls.

Do not use panels of designers/judges unless a deterministic ambiguity check cannot resolve a specific issue.

---

# 7. Efficient staged sweep

Use a coarse-to-fine procedure.

## Stage A — coarse sweep

Use one seed per pressure level, but stop levels as soon as the crossover is bracketed.

Begin approximately at two separated points such as `R ~= 0.75` and `R ~= 2.5`. If both are on the same side of the transition, move one boundary once. If they bracket it, test a midpoint. This adaptive search is preferred to blindly running every level.

A four-point sequence such as `R = 0.5, 1, 2, 4` is a fallback only if the adaptive bracket is unclear.

Measure final capability and inspect failures.

The purpose is to bracket the transition.

Possible outcomes:

### All levels >0.9

The current environment is too easy / the compactor too strong. Increase pressure once using a principled knob and repeat a minimal bracket.

### All levels <0.3

The sweep overshot. Add one or two intermediate levels.

### A crossover appears

Proceed only around the crossover.

Do not keep running the easy and catastrophic regimes.

## Stage B — local replication

Choose at most two neighboring pressure levels around the crossover.

Run 2 additional unseen seeds per chosen level if the remaining call budget permits.

The goal is to determine whether the regime is reproducible rather than a seed artifact.

---

# 8. Manual failure taxonomy before any future A/B/C experiment

For the calibrated candidate regime, inspect a small sample of failures manually.

Classify each into:

- **D1 deletion** — relevant information no longer represented in current memory;
- **D2 distortion** — relevant information represented incorrectly/ambiguously by compaction;
- **D3 stale state** — superseded rule/commitment remains active;
- **D4 interaction loss** — pieces survive individually but their relation/precedence is lost;
- **D5 application error** — state is represented correctly but current model applies it incorrectly;
- **D6 benchmark flaw** — ambiguous wording, contradictory ground truth, probe artifact, evaluator issue.

A future Temporal Multiplicity test is justified only if the candidate regime contains several D1–D5 failures and is not dominated by D6.

Also distinguish whether an earlier checkpoint actually had the capability. A failure is useful for the later experiment only when the same frozen post-hoc probe is answered materially better by at least one earlier checkpoint than by the final compacted state.

We do not require any specific failure type.

---

# 9. Cheap retrieval sanity check

Before declaring a regime suitable, test the strongest obvious simple repair on a **small sample of confirmed failures**.

This is not full condition A.

For perhaps 3–5 failures total:

- formulate a retrieval query from the failed request;
- run the existing strong archive retrieval;
- append/read the top relevant raw record(s);
- re-run the decision once.

Record whether the failure is trivially repaired.

We want a mixture where not every failure disappears after one obvious retrieval.

Do not build new retrieval infrastructure.

Do not run multi-step A/B/C investigations.

---

# 10. Selection rule for the calibrated operating point

Return `CALIBRATED` only if one pressure level (or narrow band) satisfies all of:

1. reproducible non-catastrophic degradation on unseen seeds;
2. at least several confirmed D1–D5 failures;
3. failures not dominated by benchmark ambiguity/evaluator flaws;
4. the agent remains meaningfully competent overall;
5. at least some failures survive one obvious archive-retrieval repair;
6. the result is not dependent on one pathological seed.

Otherwise return `NOT_CALIBRATED`.

If no calibrated regime is found within the 50-call maximum, stop.

Do not keep escalating complexity.

---

# 11. No Temporal Multiplicity treatment in this task

This is strict.

Do not:

- execute historical checkpoints as a contestant;
- run condition B or C;
- compare A/B/C;
- add new branch operators;
- optimize checkpoint inspection;
- test retro-planning;
- test self-ablation;
- test learning attribution.

The output of this task is only:

> **where should the real long-horizon experiment operate?**

If the answer is “nowhere in this environment within the bounded calibration,” that is useful.

---

# 12. Branch / artifact discipline

Create:

`research/temporal-multiplicity-calibration-v1`

from PR #6 head.

Do not modify or reinterpret PR #6 evidence.

Prefer a new draft PR against:

`research/temporal-multiplicity-long-horizon-v1`

Keep raw calibration artifacts compact.

Do not commit tens of thousands of lines of repetitive transcripts if a concise machine-readable summary plus the minimal raw failure examples is sufficient.

The previous PRs became bloated with raw output. Avoid repeating that.

---

# 13. Deliverable

Write one concise note:

`docs/experiments/temporal-multiplicity-long-horizon-calibration-v1.md`

It should contain:

1. pressure definition;
2. generator/static validation;
3. exact model-call count;
4. coarse sweep table;
5. local replication table;
6. final capability by pressure;
7. regression counts;
8. failure taxonomy;
9. retrieval sanity-check results;
10. chosen operating regime, if any;
11. verdict: `CALIBRATED` or `NOT_CALIBRATED`.

Include a compact table like:

| R | seeds | compactions | final accuracy | regression units | retrieval-resistant failures |
|---|---:|---:|---:|---:|---:|
| 0.5 | ... | ... | ... | ... | ... |
| 1.0 | ... | ... | ... | ... | ... |
| 2.0 | ... | ... | ... | ... | ... |
| 4.0 | ... | ... | ... | ... | ... |

If calibrated, end with exactly the parameters that a later frozen A/B/C experiment should use.

Do **not** run that experiment.

---

# 14. Engineering standard

Think like a senior AI systems engineer debugging an operating boundary.

The task is not:

> “How can I make the agent fail?”

It is:

> **“Where does bounded long-horizon memory begin to fail naturally, and is that boundary stable enough to support a causal feature test?”**

Prefer measurement over narrative.

Prefer parameter sweeps over handcrafted traps.

Prefer 30 informative calls over 400 elegant calls.

Stop as soon as the calibration question is answered.
