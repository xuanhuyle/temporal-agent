# Temporal Multiplicity — Existential Experiment 2
## Long-horizon state continuity: does executing historical selves add information beyond memory, retrieval, and inspection?

You are working in the repository:

`xuanhuyle/temporal-agent`

Use the latest `research/temporal-multiplicity-kernel-v0` branch as the source state.

You are running in **Claude Opus 5.5 / Ultracode**. Use that capability for judgment and orchestration, but do not confuse the intelligence of the Claude Code orchestrator with the experimental subject.

Before changing anything, read:

- `docs/temporal-multiplicity-capability-map.md`
- `docs/experiments/temporal-multiplicity-learning-attribution-v1.md`
- PR #5
- `src/multiplicity/`
- only the experiment infrastructure you actually need to reuse

Then create a **fresh experiment branch** from the current head:

`research/temporal-multiplicity-long-horizon-v1`

Do not keep adding implementation churn to PR #5. The previous experiment and its negative result remain immutable evidence.

---

# 0. Why this experiment exists

The previous learning-attribution experiment was valid but was aimed at the wrong regime.

It represented longitudinal development as a short sequence of fully readable knowledge modules:

`S0 -> S1 -> S2 -> S3`

The current model could inspect the entire learning history, read every module semantically, and infer what would happen if knowledge were removed. A single reflection was enough to make the optimal developmental decision.

That result is **NO_MEANINGFUL_SIGNAL** and must not be rescued or reinterpreted away.

It establishes an important negative result:

> When the relevant agent state is compact, fully inspectable, and semantically transparent, a strong LLM can absorb much of the apparent value of temporal multiplicity through ordinary reasoning.

The surviving hypothesis is narrower and more consequential:

> **Temporal multiplicity may matter for genuinely long-running agents whose lifetime exceeds active context, forcing repeated compaction, memory rewriting, retrieval, and loss of cognitive detail.**

This experiment must actually test that regime.

Do not create another short synthetic sequence and call it "long-running."

---

# 1. Existential research question

The question is:

> **After a long-running agent has undergone repeated context turnover and lossy memory compaction, does the ability to execute historical versions of its own state let it diagnose and repair cognitive regressions better than the same model equipped with strong memory, retrieval, and versioned-state inspection but no historical execution?**

This is a direct test of whether executable historical self-state is a distinct cognitive primitive rather than:

- better prompting;
- more reasoning;
- RAG;
- event sourcing;
- versioned memory;
- checkpoint inspection.

The experiment should materially change our belief in the primitive either way.

---

# 2. What “long-running” means here

A long-running agent is not one huge prompt.

Implement a controlled agent lifetime consisting of repeated model calls over multiple stages/epochs.

The agent must have:

- an active working context with a fixed budget;
- a persistent memory/state representation;
- a raw immutable history/archive;
- repeated context turnover;
- model-generated compaction or memory updates;
- information that falls out of active context;
- evolving beliefs, constraints, commitments, or working assumptions;
- enough stages that several compaction cycles occur before the final diagnostic task.

A scaled-down fixed context budget is acceptable. It is preferable to spending enormous tokens merely to hit the model's physical maximum context.

For example, an episode may contain roughly 12–20 stages and 3–6 actual compaction cycles.

The important property is:

> Earlier raw interaction content is no longer present in the current working context after compaction.

Do not merely concatenate all earlier events into the final prompt.

---

# 3. Compaction must be real, not hand-scripted loss

Do **not** manually delete the exact fact needed later.

That would manufacture an advantage.

At compaction boundaries, use a generic compaction/memory-writing procedure that does not know the future diagnostic task.

Prefer model-generated compaction using the same reasoning model or a fixed neutral compactor.

The compactor may preserve:

- important facts;
- beliefs;
- goals;
- commitments;
- plans;
- unresolved questions;
- references to raw source material.

Then discard the pre-compaction active working context from the live agent state.

The immutable raw transcript/archive remains available through retrieval to **all** conditions.

Future-relevant information should often be innocuous or ambiguous when first encountered, so whether compaction preserves its significance is not obvious ex ante.

Do not tell the compactor which facts the final evaluator will care about.

---

# 4. Preserve historical checkpoints

At meaningful state transitions and before/after each compaction, preserve an exact explicit checkpoint of the agent runtime state.

A checkpoint should contain the minimum required to reproduce the agent's explicit cognitive boundary, for example:

- compacted memory;
- recent active context;
- beliefs/assumptions;
- goals;
- commitments;
- current plans;
- references or indexes used for retrieval;
- other explicit state actually available to the agent.

Do **not** claim to snapshot hidden model activations or weights.

The checkpoint is the explicit executable state surrounding the model.

Use the existing `TemporalMultiplicity` primitive where practical:

- `snapshot`
- `fork`
- `run`
- `compare`

Make only the minimal extension required to represent realistic long-running state.

Do not redesign the core ontology.

---

# 5. The key causal event: a cognitive regression

Each episode should contain a long trajectory in which the final agent eventually performs poorly on a behavior that an earlier version could perform correctly.

The regression must emerge from realistic long-horizon state evolution such as:

- compaction dropping a constraint whose future significance was unclear;
- a later summary subtly distorting an earlier commitment;
- a new assumption interacting with an older one;
- a persistent memory edit superseding useful nuance;
- a retrieved summary becoming more salient than an original source;
- a goal or policy change causing an unintended downstream behavior.

Do not stipulate the regression numerically.

It must be demonstrated by actually executing the model at different historical checkpoints on a diagnostic task/probe.

There must be genuine headroom:

[
E(S_{earlier}) > E(S_{current})
]

on at least some relevant diagnostic behavior.

If no meaningful regression emerges naturally, that is important.

See the headroom stop rule below.

---

# 6. Three conditions — this distinction is essential

The previous research risks conflating several technologies.

This experiment must separate them.

## Condition A — Strong long-running baseline

The same model operating as a normal long-running agent with:

- current compacted state;
- current persistent memory;
- the full immutable raw history/archive;
- a strong retrieval/search mechanism over the archive;
- enough matched reasoning/tool-call budget to investigate the failure;
- normal reflection and planning.

It may search and reread old raw material.

It may reason counterfactually.

It may inspect its current memory and compare retrieved historical documents.

Do not make this baseline weak.

## Condition B — Versioned-state inspection baseline

Condition A plus access to historical **checkpoint contents** as inspectable data.

It may:

- retrieve checkpoint summaries;
- inspect state diffs;
- inspect what beliefs/goals/commitments/memory fields existed at a time;
- search checkpoint metadata;
- reason over version history.

But it may **not execute** a historical checkpoint as the agent.

This condition is crucial.

If B matches temporal multiplicity, then the value is versioned memory / event sourcing / state inspection, not executable historical selves.

## Condition C — Temporal multiplicity

Everything available to B, plus the ability to:

- instantiate a historical checkpoint;
- execute that historical self on diagnostic probes;
- compare actual behavior across checkpoints;
- optionally fork a checkpoint with a minimal candidate restoration/repair;
- observe the result before choosing the final repair.

This is the actual treatment.

The only distinctive capability should be **historical state execution/intervention**.

---

# 7. Equal-compute / equal-information principle

Do not give multiplicity a massive hidden inference advantage.

All conditions receive the same:

- raw historical archive;
- current state;
- task statement;
- final repair options, where applicable;
- underlying model.

Conditions A and B should get approximately the same total reasoning/model-call budget that C spends on historical branch executions.

If C executes 6 historical branches, B may spend 6 calls inspecting/checking checkpoint evidence and A may spend 6 calls on archive retrieval/reflection.

Exact token parity is unnecessary for this exploratory experiment.

Record call counts and approximate token use.

What matters is avoiding a comparison of one baseline call against dozens of multiplicity calls.

---

# 8. What the agent must actually do at the end

Do not score only explanatory prose.

The final task must require an **actionable repair**.

At the end of an episode, reveal a current failure/regression and ask the condition to:

1. identify approximately when the relevant capability was lost or distorted;
2. identify the most likely state transition / compaction / memory change responsible;
3. choose a minimal recovery action;
4. apply that recovery action to the current state;
5. execute the repaired current agent on held-out tasks.

Candidate repairs may include things like:

- restore one earlier memory item;
- restore a specific constraint or commitment;
- revert one distorted summary entry;
- reinstate one previous policy/belief field;
- replace one current memory fragment with its historical version.

Do **not** allow a repair that simply restores the entire old context or dumps the entire transcript into the current prompt.

We are testing whether lineage helps identify *what matters*, not whether unlimited context helps.

---

# 9. Primary metric

The primary metric is **post-repair held-out capability**.

For each condition:

[
RecoveryGain = E(S_{repaired}) - E(S_{current})
]

If there are several possible repairs, also compute regret relative to the best minimal repair:

[
RepairRegret = E(S_{best\ repair}) - E(S_{chosen\ repair})
]

Secondary metrics:

- correct regression interval / checkpoint localization;
- correct causal transition;
- size of repair;
- number of archive/checkpoint accesses;
- total model calls/tokens;
- historical-state prediction error, if useful.

Do not make explanation quality the primary result.

---

# 10. A particularly important diagnostic: introspection vs execution

Where practical, before Condition C executes a historical checkpoint, ask the current model to predict what that historical self will do on the probe.

Then actually execute it.

Record:

[
PredictionError = distance(\hat E(S_t), E(S_t))
]

This directly tests the surviving thesis:

> Does executing an alternative self reveal behavior the current LLM cannot reliably predict by reasoning about the stored state?

Do not turn this into a separate giant benchmark.

It is a diagnostic within the same experiment.

---

# 11. Episode design

Use a small number of **long** episodes, not many tiny cases.

A sensible target is:

- 2–3 pilot trajectories;
- then 4–6 final trajectories if the pilot demonstrates headroom.

Prefer multiple task domains if possible without creating bespoke harnesses, for example:

- project / operational planning;
- policy or compliance reasoning;
- investigation / research;
- software maintenance or incident response;
- procurement / commercial decision-making.

However, a single generic environment with varied trajectories is acceptable if it genuinely produces long-horizon state turnover.

Avoid toy arithmetic modules like the previous Orbital Post experiment.

The agent should accumulate real-seeming beliefs, commitments and working context over time.

---

# 12. Hidden future relevance

The experiment should include early information that later matters but whose future relevance is not obvious when encountered.

Examples:

- a minor exception to a policy;
- a stakeholder constraint mentioned once;
- an unresolved anomaly;
- a provisional assumption with a caveat;
- a dependency that appears dormant;
- an early commitment whose downstream consequence appears much later.

However:

- the raw record remains retrievable by every condition;
- the baseline is not forbidden from finding it;
- checkpoint inspection in B may expose it if the state retained it.

If A or B reconstructs the right answer, that is legitimate negative evidence.

---

# 13. Strong retrieval baseline

Do not use naive keyword search and call it RAG.

Reuse or build the smallest strong retrieval mechanism available in the repo/environment.

At minimum, allow semantic or model-assisted retrieval over the raw archive.

The baseline should be able to formulate multiple searches within its matched budget.

If a simple archive search recovers everything and solves the task, record the negative result.

Do not artificially make retrieval fail.

---

# 14. Headroom gate — before spending large compute

This is mandatory.

Pilot 2–3 long trajectories first.

Before scaling, verify all three:

1. the current compacted agent actually shows a meaningful failure/regression;
2. at least one earlier checkpoint genuinely performs better when executed;
3. the problem is not trivially solved by a single obvious archive retrieval.

If these conditions are not met:

- redesign the trajectory generator **once** to create a more authentic long-horizon challenge;
- rerun the pilot;
- if there is still no headroom, stop with `NO_HEADROOM`.

Do not spend hundreds of calls on a benchmark with no discriminatory headroom.

---

# 15. Do not manufacture the effect

The following are invalid ways to make multiplicity win:

- hiding raw historical records from the baseline;
- giving checkpoint contents only to multiplicity;
- hand-deleting the final answer during compaction;
- using opaque random tokens whose meaning is available only to the multiplicity evaluator;
- giving multiplicity more future information;
- letting historical branches see post-checkpoint facts;
- giving multiplicity substantially more model compute;
- making the baseline use naive keyword search when stronger retrieval is available;
- scoring a historical branch against information it could not have known.

If the strong baselines solve the problem, accept the result.

---

# 16. Subject isolation

Experimental subjects must not be able to inspect evaluator ground truth, hidden held-out tasks, or the repository files containing answers.

Separate:

- Claude Code / Ultracode as the **orchestrator/researcher**;
- model calls representing the **agent subject**.

Reuse the previous subject-isolation mechanism if it is sufficient.

Do not spend substantial time building a new agent platform.

---

# 17. Real data before polish

This instruction is strict.

The previous PR spent too much effort on infrastructure before evidence.

For this experiment:

- no second adversarial review before pilot data;
- no elaborate preregistration engine;
- no hundreds of lines of verdict logic;
- no exhaustive provider hardening;
- no architecture expansion not required for the run;
- no large documentation pass before results;
- no test explosion.

Aim for:

> **at least 70% of the effort on producing/interpreting actual long-horizon model behavior, at most 30% on machinery.**

Use existing infrastructure even if imperfect.

Fix only problems that would invalidate the experiment.

---

# 18. Run early

Obtain the first real long-running trajectory as soon as the minimal harness works.

Do not finish the entire benchmark before seeing whether the mechanism actually creates:

- context turnover;
- compaction;
- regression;
- recoverable historical capability.

Inspect the pilot raw states and outputs.

If the setup is not actually long-running in the sense above, stop and fix that before scaling.

---

# 19. Evidence that would support the primitive

A result becomes genuinely interesting only if Condition C materially beats **both** A and B.

For example:

- A can search the raw archive but cannot reliably identify the cognitive transition;
- B can inspect exact versioned state but still predicts the consequence incorrectly;
- C executes historical states, localizes the regression, chooses a minimal repair, and restores held-out performance.

The crucial comparison is:

[
C > B
]

because:

- `A < B` may merely show value from versioned memory/checkpoints;
- `B = C` means historical execution adds no distinct cognitive value.

A positive result should show more than a tiny accuracy difference.

It should show repeated cases where actual historical execution supplies decision-relevant information that inspection/retrieval did not.

---

# 20. Evidence against the primitive

Treat any of the following as substantial negative evidence:

- A matches C: ordinary memory/retrieval/reflection is enough;
- B matches C: versioned state inspection is enough, execution adds nothing;
- current-model predictions of historical behavior are consistently accurate;
- no realistic compaction-induced regressions emerge;
- branch execution mostly adds noise;
- the advantage exists only under an artificially tiny context budget;
- the experiment needs bespoke tricks per trajectory.

Do not rescue a negative result by immediately inventing a new temporal feature.

---

# 21. Verdicts

Use exactly one of:

## `PRIMITIVE_SIGNAL`

Condition C materially and repeatedly improves post-repair held-out capability / repair regret over **both** strong baselines, and the advantage is traceable to information revealed by executing historical state rather than extra context or compute.

## `ABSORBED_BY_BASELINE`

Condition A or B achieves essentially the same recovery decisions/performance. State clearly whether the thesis was absorbed by ordinary memory/retrieval or by versioned state inspection.

## `NO_HEADROOM`

The long-running setup fails to produce meaningful compaction/context-loss regression after the pilot and one allowed redesign.

## `INCONCLUSIVE`

Execution problems, leakage, unstable evaluation, or another fundamental flaw prevents interpretation.

Do not create softer categories.

---

# 22. Stop conditions

Stop when one of these happens.

### A. Clear paired result

Analyze it and stop. Do not immediately add more architecture.

### B. Strong baseline solves it

Record `ABSORBED_BY_BASELINE` and stop.

### C. Versioned inspection solves it

Record that executable historical selves add no distinct value and stop.

### D. No natural regression/headroom

After one redesign, record `NO_HEADROOM` and stop.

### E. Multiplicity wins because of a discovered confound

Fix the confound once and rerun.

### F. Experimental execution is impossible in the current Claude Code environment

Prepare the smallest legitimate external-run command and stop coding.

---

# 23. Deliverables

Keep the implementation and write-up small.

Expected artifacts:

- minimal long-horizon experiment code;
- raw result files;
- one concise research note:
  `docs/experiments/temporal-multiplicity-long-horizon-v1.md`

The note should include:

1. exact research question;
2. what made the trajectories genuinely long-running;
3. context budget and compaction method;
4. checkpoint representation;
5. retrieval mechanism;
6. three conditions;
7. model/call budget;
8. headroom results;
9. paired final repair outcomes;
10. post-repair held-out performance / regret;
11. whether checkpoint execution surprised the current model;
12. confounds;
13. one verdict.

Show raw paired outcomes.

Do not write a long architecture manifesto.

---

# 24. Branch / PR discipline

Create:

`research/temporal-multiplicity-long-horizon-v1`

from the current research head.

Do not rewrite or delete the previous negative result.

Prefer a new draft PR against `research/temporal-multiplicity-kernel-v0` so the diff contains only this existential experiment.

Do not update PR #5 with a large new experiment implementation.

---

# 25. Final research standard

The purpose of this iteration is **not** to prove temporal multiplicity.

It is to answer the question we should have tested earlier:

> **When a real long-running agent has genuinely lost or distorted parts of its historical cognitive context through repeated compaction, does executing an exact historical self provide actionable information that strong retrieval, reflection, and even exact checkpoint inspection cannot provide?**

If yes, we finally have evidence for something the LLM cannot simply reason away.

If no, then a substantial part of the remaining temporal-multiplicity thesis has been absorbed by ordinary long-running-agent memory and reasoning systems.

Get to that answer with the least machinery necessary.
