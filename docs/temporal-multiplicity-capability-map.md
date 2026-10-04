# Temporal Multiplicity Capability Map

Status: governing research map
Date: 2026-10-04

## 1. Core thesis

Temporal multiplicity is a **model-agnostic cognitive capability** for agents.

The reasoning model can be Claude, GPT, Gemini, an open-weight model, a symbolic
reasoner, a human-in-the-loop system, or some future model.

The new capability does not live in the foundation model. It lives in the agent
runtime.

The primitive is:

> **Versions of an agent's explicit cognitive state can be treated as executable
> objects: snapshotted, instantiated, forked, selectively modified, run
> independently, compared, and eventually selected or recombined.**

If explicit agent state at time t is:

[
S_t = {K_t, B_t, G_t, C_t, M_t, P_t, E_t, ldots}
]

where the terms may include knowledge, beliefs, goals, commitments, memory,
policies, capabilities and environment assumptions, then the primitive provides
operations of the form:

[
snapshot(S_t)
]

[
fork(S_t, Delta)
]

[
run(S)
]

[
compare(S_i, S_j)
]

The research question is not whether these operations can be implemented.
Software can copy and branch explicit state.

The research question is:

> **Does making an agent's own state executable create cognitive capabilities
> that are meaningfully stronger than what the same reasoning model can achieve
> through ordinary sequential context, memory, reflection and planning?**

That is the question this research program exists to answer.

---

## 2. What would make the primitive "real"?

The primitive is not established merely because:

- state can be serialized;
- branches can be created;
- an isolated prompt changes an answer;
- one benchmark improves slightly;
- an architecture looks elegant;
- a capability can be simulated by writing enough bespoke orchestration code.

The primitive becomes scientifically interesting if executable self-state
creates a **reusable class of cognitive operations** that satisfies most of the
following:

1. **Model-independence** — the operation is outside the LLM and can be attached
   to different reasoning backends.
2. **Composability** — the same primitive supports several distinct cognitive
   abilities without bespoke machinery for every task.
3. **Causal manipulability** — the system can intervene on its own prior or
   alternative state, not merely describe it.
4. **Independent execution** — alternative selves can reason or act without
   sharing information that should not be shared.
5. **Observable consequences** — comparing branches reveals information that
   could not be obtained as reliably from one sequential trajectory.
6. **Actionability** — the comparison changes what the current agent does,
   learns, believes or becomes.
7. **Persistence across tasks** — the capability is useful beyond one benchmark
   family.

The strongest possible evidence would therefore not be:

> "Forking improves one historical-reasoning benchmark."

It would be:

> **"The same small state-manipulation primitive enables several distinct forms
> of self-reasoning that a strong sequential agent cannot reproduce reliably at
> comparable cost."**

---

## 3. Direct capabilities entailed by the primitive

These capabilities follow almost directly from snapshot, fork, run and compare.
They require little additional conceptual machinery.

### 3.1 Epistemic rollback

Instantiate the agent as it existed before later information was acquired.

The operation is stronger than asking a current model to pretend not to know
something because the excluded information is absent from the executable
branch.

Potential use:

- hindsight-free reasoning;
- historical decision review;
- forecasting evaluation;
- diagnosis;
- postmortems;
- scientific inference.

Current experiment: **tmk-hindsight v0.1**.

This is only one leaf of the capability map.

### 3.2 Counterfactual self-forking

Create multiple versions of the agent that differ in a controlled feature:

- belief;
- assumption;
- goal;
- memory;
- policy;
- tool access;
- planning strategy;
- acquired knowledge.

Example:

[
S
ightarrow
egin{cases}
S^{A} & 	ext{belief A}\
S^{
eg A} & 	ext{belief not-A}
end{cases}
]

The important point is that the alternatives are **executed**, not merely
mentioned inside one prompt.

### 3.3 Parallel epistemic selves

Maintain incompatible hypotheses as separate reasoning trajectories.

Instead of one model saying:

> fraud 40%, accident 35%, measurement error 25%

the agent can instantiate:

- self F: reason under fraud;
- self A: reason under accident;
- self M: reason under measurement error.

Each self can gather evidence, update internally and make predictions without
prematurely collapsing into a shared narrative.

The parent can later compare them.

### 3.4 Self-comparison

Ask not merely "what changed in my memory?" but:

> **How do two executable versions of me differ in performance, beliefs,
> predictions, plans and actions?**

This is the bridge from state branching to experimental self-knowledge.

---

## 4. Capabilities unlocked by adding an evaluator

Once branches can be evaluated against tasks or outcomes, temporal multiplicity
becomes much more consequential.

Let:

[
E(S, T)
]

measure the capability of state S on task family T.

The agent can now experimentally study its own development.

### 4.1 Learning-curve measurement

Re-run prior selves on the same evaluation suite:

[
E(S_0), E(S_1), E(S_2), ldots, E(S_t)
]

The agent can measure:

- where it improved;
- where it stagnated;
- where it regressed;
- which capabilities appeared at which point.

This turns "I have learned" from a narrative claim into an empirical one.

### 4.2 Cognitive regression detection

A later state is not assumed to be better.

If:

[
E(S_{t+1}, T) < E(S_t, T)
]

the agent can identify capability regression caused by:

- new information;
- changed policy;
- overwritten memory;
- model changes;
- harmful abstractions;
- goal conflicts.

This is potentially important for long-lived agents.

### 4.3 Learning attribution

Suppose knowledge K was acquired between two states.

Construct:

[
S_t^{-K}
]

and compare:

[
Delta_K = E(S_t) - E(S_t^{-K})
]

or construct an earlier state with K added:

[
S_{t-1}^{+K}
]

and compare outcomes.

This begins to answer:

> **What actually made me better?**

rather than:

> What happened before I got better?

That is a causal question about the agent's own learning trajectory.

### 4.4 Marginal value of knowledge

Learning attribution can be generalized into a value function over candidate
knowledge, skills or experiences:

[
V(K) approx E(S^{+K}) - E(S)
]

The agent can distinguish information accumulation from capability gain.

This matters because an agent may ingest millions of tokens while gaining very
little useful ability.

### 4.5 Belief-impact analysis

Change or remove one belief and execute the resulting self.

Observe which:

- conclusions;
- decisions;
- predictions;
- commitments;
- plans

change downstream.

This makes belief revision experimentally traceable rather than merely
editorial.

---

## 5. Capabilities unlocked by prospective branches

The previous capabilities operate mostly on actual or counterfactual past and
present selves.

The next class uses branches as candidate **future selves**.

### 5.1 Prospective selves

From current state S, instantiate alternative developmental trajectories:

[
S_t
ightarrow
egin{cases}
S_{t+n}^{A}\
S_{t+n}^{B}\
S_{t+n}^{C}
end{cases}
]

The branches may differ in:

- what they learn;
- what goals they pursue;
- what tools they acquire;
- what policies they adopt;
- which experiments they run;
- which assumptions they retain.

This extends planning from:

> Which action should I take?

to:

> **Which version of myself should I become?**

### 5.2 Developmental search

Search over agent-state space rather than only action space.

The object being optimized is partly the agent itself.

Examples:

- which expertise to acquire;
- which memory abstraction to adopt;
- which reasoning procedure to internalize;
- which toolset to learn;
- which goals or subgoals to retain.

### 5.3 Retro-planning

Start with a desirable future capability state (S^*).

Ask:

> What had to become true for this future self to exist?

Extract backwards requirements:

[
S^*
ightarrow
R_n
ightarrow
R_{n-1}
ightarrow
ldots
ightarrow
Actions_{now}
]

Example:

Desired future capability:
- solve class X reliably.

Backward requirements:
- understand concept C;
- concept C requires evidence A and experiment B;
- experiment B requires tool D;
- therefore acquire D, gather A, run B, learn C.

The prospective branch sends back **planning information**, not literal future
knowledge.

This is retro-planning over **self-development**, not merely world state.

### 5.4 Curriculum generation

Combine:

- current capability profile;
- observed learning curve;
- marginal value of prior learning;
- prospective future selves;
- retro-planned requirements.

Then choose what to learn next.

The agent can optimize its learning trajectory based on observed capability
gain rather than generic curiosity or static objectives.

---

## 6. Capabilities unlocked by selection and commitment

If branches can be evaluated before the live agent adopts their changes, the
primitive begins to support controlled self-modification.

### 6.1 Safe self-modification

Instead of:

[
modify(S) ightarrow hope
]

use:

[
S
ightarrow
{S'_1, S'_2, S'_3}
ightarrow
evaluate
ightarrow
select
ightarrow
commit
]

Candidate changes may include:

- memory strategy;
- planning procedure;
- tool policy;
- reasoning scaffold;
- learned abstraction;
- goal decomposition;
- model configuration.

This does not solve self-improvement, but it gives self-improvement an
experimental substrate.

### 6.2 Directed self-evolution

Repeatedly:

1. inspect current capability;
2. generate candidate future selves;
3. evaluate them;
4. attribute improvements;
5. adopt the best validated changes;
6. preserve lineage;
7. repeat.

The agent's cognitive trajectory becomes something it can deliberately search
and optimize.

---

## 7. The developmental loop

The strongest integrated consequence of temporal multiplicity is a possible
closed loop:

[
oxed{
egin{array}{c}
	ext{Current self}\
downarrow\
	ext{Measure capability}\
downarrow\
	ext{Compare with earlier / alternative selves}\
downarrow\
	ext{Attribute what caused learning or regression}\
downarrow\
	ext{Generate candidate future selves}\
downarrow\
	ext{Select desired capability profile}\
downarrow\
	ext{Retro-plan what must be learned / changed}\
downarrow\
	ext{Act, learn, experiment}\
downarrow\
	ext{New self}\
circlearrowleft
end{array}
}
]

This is **developmental agency**.

An ordinary agent acts on the world.

A developmental agent also treats its own cognitive trajectory as an object of
measurement, experimentation, planning and optimization.

---

## 8. Capability hierarchy

### Level 0 — Sequential agency

> I observe, reason, act and remember.

No temporal multiplicity is required.

### Level 1 — Temporal self-access

> I can instantiate who I was.

Core capability:
- epistemic rollback.

### Level 2 — Multiplicity

> I can instantiate several versions of myself simultaneously.

Core capabilities:
- counterfactual self-forking;
- competing epistemic selves;
- independent execution;
- comparison.

### Level 3 — Experimental self-knowledge

> I can run controlled experiments on versions of myself.

Core capabilities:
- learning-curve measurement;
- regression detection;
- knowledge ablation;
- learning attribution;
- belief-impact analysis.

### Level 4 — Developmental agency

> I can use experiments on myself to decide how I should change.

Core capabilities:
- capability-gap detection;
- curriculum generation;
- developmental search;
- retro-planning.

### Level 5 — Directed self-evolution

> I can generate, evaluate and selectively adopt candidate future versions of
> myself.

Core capabilities:
- controlled self-modification;
- fork/evaluate/commit;
- iterative self-development.

No claim is made that Level 5 is AGI or sufficient for AGI.

The claim worth investigating is only that these levels may constitute useful
cognitive machinery unavailable, or substantially harder to realize, in a
strictly single-trajectory agent.

---

## 9. What is direct, derived and speculative?

| Capability | Status relative to primitive | Additional dependency |
|---|---|---|
| Epistemic rollback | Direct | Versioned explicit state |
| Hindsight-free replay | Direct | Replayable task |
| Counterfactual self-forking | Direct | Mutable state representation |
| Parallel epistemic selves | Direct | Independent execution |
| Self-comparison | Direct | Comparison function |
| Learning-curve measurement | Derived | Evaluator / stable tasks |
| Regression detection | Derived | Evaluator / stable tasks |
| Learning attribution | Derived | Controlled ablation + evaluator |
| Marginal value of knowledge | Derived | Many controlled interventions |
| Belief-impact analysis | Derived | Mutable beliefs + evaluation |
| Prospective selves | Derived | Environment/world continuation |
| Developmental search | Derived | Search + evaluator |
| Retro-planning | Derived | Candidate future state + requirements extraction |
| Curriculum generation | Derived | Attribution + planning |
| Safe self-modification | Derived | Sandbox + evaluator + commit policy |
| Directed self-evolution | Speculative integration | All of the above |

This table matters.

We should not claim that snapshot/fork alone magically gives the agent
retro-planning or self-improvement.

The primitive makes those capabilities **possible to construct and test**.

---

## 10. The existential research program

The objective is not to individually polish twenty tiny benchmark leaves.

The objective is to answer:

> **Is executable self-state a real cognitive primitive?**

A research iteration is significant only if it tests one of the following
high-level claims.

### Claim A — Alternative selves produce information unavailable from one self

Examples:

- genuinely independent competing hypotheses;
- counterfactual belief ablation;
- hindsight-free historical selves.

### Claim B — An agent can experimentally measure its own development

Examples:

- replay prior selves;
- detect capability changes;
- attribute improvement to specific learned information or procedures.

### Claim C — Self-experimentation improves future learning or planning

Examples:

- choose what to learn next using measured marginal learning value;
- outperform current-self reflection on curriculum selection;
- derive better action plans from desired future selves.

### Claim D — Search over selves produces better agents

Examples:

- fork/evaluate/commit;
- candidate policies or reasoning strategies;
- demonstrated improvement over sequential self-reflection under equal budget.

If the primitive cannot deliver meaningful evidence for at least one of these
claims, the project should stop.

---

## 11. Significance threshold for future Claude Code prompts

Future implementation prompts must not spend substantial effort polishing a
narrow subcomponent unless that work is strictly required to execute a
pre-registered high-level experiment.

Before submitting a Claude Code prompt, it must answer all five questions:

1. **Which high-level claim A-D does this test?**
2. **What behavior would be impossible or materially less reliable without
   executable self-state?**
3. **What is the strongest non-multiplicity baseline?**
4. **What result would make us conclude the primitive is not adding meaningful
   cognition?**
5. **If successful, would the result materially change our belief that temporal
   multiplicity is a real cognitive primitive?**

If question 5 is "no", do not run the experiment.

### Anti-polish rule

Do not spend an iteration on:

- minor prompt optimization;
- more elaborate state schemas;
- adding another framework adapter;
- branch persistence;
- branch visualization;
- generalized merging;
- abstractions whose only purpose is architectural elegance;
- benchmark sophistication that cannot change the existential conclusion.

Engineering work is justified only when it unlocks a decisive test.

---

## 12. Experimental sequence

The current hindsight experiment is Experiment 0 / instrumentation validation.

It tests one direct leaf:

> Can epistemic rollback prevent hindsight contamination?

Its result should be interpreted narrowly.

The next experiments should become progressively more existential.

### Experiment 1 — Experimental self-knowledge

Question:

> **Can executable prior and ablated selves allow an agent to correctly identify
> what caused its own capability improvement better than a strong current-self
> reflection baseline?**

Required operations:

- snapshot;
- fork;
- remove/add learned components;
- run;
- evaluate;
- compare.

This tests Claims A and B simultaneously.

A positive result would show that the primitive lets the agent obtain causal
information about its own learning trajectory.

### Experiment 2 — Developmental agency

Question:

> **Can an agent use experimental knowledge of its own learning trajectory to
> choose what to learn next better than the same model using ordinary reflection
> and planning?**

Required operations:

- learning attribution;
- candidate curriculum branches;
- evaluation;
- selection.

This tests Claim C.

### Experiment 3 — Retro-planning from future selves

Question:

> **Can executing candidate future selves produce backward learning/action
> requirements that improve attainment of a target capability over ordinary
> forward planning?**

This tests Claim C in a prospective setting.

### Experiment 4 — Fork / evaluate / commit

Question:

> **Can search over candidate versions of the agent produce a better agent under
> equal compute than sequential self-reflection / self-modification?**

This tests Claim D.

These experiments matter more than accumulating many narrow temporal tasks.

---

## 13. Kill logic for the overall primitive

Do not keep temporal multiplicity alive indefinitely by moving from one
unfalsified sub-capability to another.

After the significant experiments above, stop the research program if the
evidence converges on the following:

1. strong sequential agents reproduce the same behavior through ordinary
   prompting, memory and planning;
2. branching provides no meaningful accuracy, learning, planning or efficiency
   advantage at comparable compute;
3. benefits arise only from giving branches more context or more inference
   budget;
4. each new use case requires bespoke orchestration rather than the same small
   primitive;
5. the agent cannot use branch comparisons to improve its own subsequent
   decisions or development.

Conversely, the primitive becomes increasingly credible if the same operations
repeatedly enable capabilities across unrelated tasks and reasoning backends.

---

## 14. Product interpretation

If the primitive survives, the potential product is not "a temporal-agent
application."

It is a **cognitive capability layer for agent runtimes**.

Conceptually:

[
Agent = ReasoningBackend + Memory + Tools + TemporalMultiplicity
]

The exposed capability might eventually look like:

    snapshot()
    fork()
    mutate()
    run()
    evaluate()
    compare()
    commit()

The product value would be that an existing agent can gain new cognitive
operations without replacing the model underneath it.

The long-term claim would not be:

> "Our memory is better."

It would be:

> **"Your agent can experimentally reason over versions of itself."**

That claim must be earned experimentally.

---

## 15. North-star statement

> **Temporal multiplicity turns an agent's cognitive trajectory from something
> it merely experiences into something it can inspect, manipulate, experiment
> on, and deliberately optimize.**

The research program exists to determine whether that sentence describes a
real cognitive primitive or merely an elaborate way to orchestrate capabilities
that strong sequential agents already possess.
