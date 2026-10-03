# North Star — Temporal Agency as a Computational Model

## Core thesis

Artificial agents should not be forced to experience computational time the way humans experience biological time.

Humans have one continuously evolving self. We cannot instantiate our past selves, fork alternative trajectories, or interact with executable versions of possible future selves.

Software agents potentially can.

The objective is therefore not to give agents “better memory.”

It is to give them:

> **Time as an addressable dimension of state.**

A temporally capable agent should be able to reconstruct and converse with past versions of itself, act from a clearly defined present, simulate and interrogate possible future versions of itself, and maintain causal consistency across all of those temporal states.

---

## 1. The fundamental object: a temporally situated self

Represent an agent at temporal coordinate (t) as:

[
S_t = {W_t, K_t, B_t, G_t, C_t, U_t, D_t, O_t}
]

where:

- (W_t): perceived world state;
- (K_t): knowledge available at (t);
- (B_t): beliefs and assumptions at (t);
- (G_t): objectives at (t);
- (C_t): active context;
- (U_t): uncertainties;
- (D_t): decisions already made;
- (O_t): open obligations, tasks and commitments.

The agent is therefore not one object.

It is potentially a family of temporally situated selves:

[
S_{t_1}, S_{t_2}, ..., S_{now}
]

plus simulated future selves:

[
\hat{S}_{t+\Delta}^{(1)}, \hat{S}_{t+\Delta}^{(2)}, ..., \hat{S}_{t+\Delta}^{(n)}
]

---

## 2. The fundamental asymmetry of time

Past, present and future must have different computational semantics.

### Past — committed

The past contains events that occurred. They cannot be changed. What may change is our interpretation of them.

[
event_{past} = immutable
]

but:

[
interpretation(event_{past}) = revisable
]

The past supports reconstruction, provenance, causal tracing, historical self-instantiation and reinterpretation.

It does not support rewriting.

### Present — actionable

The present is not merely the current timestamp.

It is:

> **The boundary between committed history and open possibility.**

Only the present self can affect the committed world.

The present supports observation, reasoning, decision, action and branch creation.

The present is the control surface of temporal agency.

### Future — conditional

The future has not happened.

It contains forecasts, plans, possible states, promises, risks, scenarios and simulated selves.

Every future state therefore requires:

- branch identity;
- assumptions;
- probability or plausibility;
- generating policy/action;
- horizon.

Future states are simulations, never memories.

---

## 3. The temporal geometry

The agent inhabits a graph rather than a linear memory stream.

[
G = (S,E)
]

Nodes (S) are temporally situated agent/world states.

Edges (E) represent:

- elapsed time;
- observations;
- decisions;
- actions;
- causal dependencies;
- forks;
- simulations;
- supersession;
- information arrival.

Conceptually:

```text
                         distant future
                    ~ probability field ~
                  /    /    |    \    \
                /      possible futures  \
              /                            \
                    PRESENT SELF
                        |
                        |
              committed trajectory
                        |
                   historical selves
                        |
                       PAST
```

The present is the narrow waist between:

> **one increasingly committed history**

and

> **an increasingly branching field of futures.**

---

## 4. The four core systems

### Chronicle — what happened

An immutable append-only record of experience.

Stores observations, messages, tool outputs, decisions, actions, external events, timestamps and provenance.

The Chronicle is never rewritten.

### Historian — what did it mean?

Transforms raw experience into temporal structure.

It infers facts, validity intervals, entities, supersession, beliefs, assumptions, causal dependencies, decision provenance and epistemic state.

The Historian may be wrong.

Therefore its output is versioned and revisable.

### Tesseract — where in time can I go?

Makes temporal states addressable.

Core operations include:

```text
state_at(t)
past_self(t)
diff(t1, t2)
trace(decision)
fork_from(t)
compare(self_t1, self_t2)
```

The Tesseract turns time from metadata into a navigable state space.

### TVA — what transitions are allowed?

The temporal integrity layer.

It enforces:

- branch identity;
- immutable committed history;
- simulated-vs-observed separation;
- causal ancestry;
- provenance;
- no silent timeline rewriting;
- no mixing of future simulation with past fact.

Its foundational rule is:

> **Never overwrite time. Fork it.**

---

## 5. Past selves

A past self is not a summary.

It is an executable reconstruction of:

[
S_t
]

with a strict epistemic cutoff:

[
knowledge(past\_self_t) \le t
]

The present agent can therefore ask:

- Why did you make this decision?
- What did you believe?
- What were you uncertain about?
- Which alternatives had you already rejected?
- What information were you waiting for?

This prevents hindsight contamination.

The present self does not reconstruct what its former self probably thought.

It asks the former self.

---

## 6. Future selves

Future selves are simulated agents instantiated inside possible future states.

For action (a):

[
\hat{S}_{t+\Delta}^{a} = simulate(S_t,a,\Delta)
]

The present can instantiate multiple futures:

```text
             Future-self A
            /
Present-self ─ Future-self B
            \
             Future-self C
```

Then ask:

- What problems do you inherit from me?
- Which decision of mine do you regret?
- What information do you wish I had collected?
- Which option do you wish I had preserved?
- What must I do now for your future to remain reachable?

Future selves therefore provide more than forecasts.

They provide warnings, requirements, regrets, constraints and backward-planned preconditions.

---

## 7. Backward requirements

Forward forecasting asks:

> What happens if I do X?

Temporal agency also asks:

> If I want future state Y, what must already be true before then?

For example:

```text
Desired state at T+90
        |
        ├─ capacity online at T+75
        |      └─ contract signed at T+45
        |             └─ vendor selected at T+30
        |
        └─ financing closed at T+60
               └─ process started at T+20
```

The future sends requirements backward into present action.

Future states can influence current decisions without physically causing the past.

---

## 8. Forecasts must branch, not overwrite

Suppose the agent forecasts:

> If we do nothing, there is a high probability of failure.

It acts.

The failure never occurs.

That does not mean the forecast was wrong.

The system must preserve:

```text
Branch A
Do nothing → failure

Branch B
Forecast warning → intervention → no failure
```

Future A remains a valid prevented future.

This prevents a major learning error:

> successful prevention must not be mistaken for failed prediction.

---

## 9. Reflexivity

Predictions alter behavior.

Behavior alters the world.

Therefore:

[
Forecast_t \rightarrow Action_t \rightarrow World_{t+1}
]

Forecasts should be classified as:

- passive;
- policy-conditioned;
- intervention-aware;
- reflexive.

An agent must know when observing a prediction changes the trajectory being predicted.

---

## 10. Future uncertainty grows with horizon

Near futures can be represented as detailed states.

Distant futures should increasingly become distributions.

Short horizon:

```text
specific future state
```

Medium horizon:

```text
scenario branches
```

Long horizon:

```text
probability distribution over regions of state-space
```

Long-range foresight should increasingly reason over distributions, not pretend to predict one exact world.

---

## 11. Temporal uncertainty exists in the past too

The past is committed, but not always perfectly known.

A system may represent:

```text
certain past
probable past
disputed past
unknown past
```

For example:

> The supplier stopped production sometime between March 3 and March 8.

Temporal coordinates may themselves have confidence intervals.

Therefore Tesseract must represent both uncertainty about future outcomes and uncertainty about historical reconstruction.

---

## 12. Identity across time

State continuity does not imply identity continuity.

Between (S_{t_1}) and (S_{t_2}), an agent may have changed:

- objectives;
- model;
- tools;
- system instructions;
- policies;
- values;
- organizational role.

Therefore the system should distinguish state continuity from identity continuity.

This enables conversations such as:

> Present-self: Why did you optimize for X?

> Past-self: Because X was my objective.

> Present-self: That objective no longer governs me.

Temporal cognition therefore naturally connects with developmental agents.

---

## 13. Irreversibility and optionality

Actions differ in how much future state-space they destroy.

Define conceptually:

[
I(a)=irreversibility(a)
]

A temporally competent agent should reason not only about expected outcome but about:

> **which futures remain reachable after an action.**

This makes optionality a first-class temporal variable.

A future self may therefore warn:

> Do not optimize for my most likely branch yet. Preserve the option to reach several good branches.

---

## 14. The temporal dialogue

The architecture ultimately creates three distinct voices.

### Past selves

Answer:

> Why am I here?

They send explanations forward.

### Future selves

Answer:

> Where might I go, and what do you need to do now for me to exist—or not exist?

They send requirements and warnings backward.

### Present self

Answers:

> Given where I came from and where I might go, what should I do now?

It alone acts.

Conceptually:

```text
                 FUTURE SELVES
          requirements / warnings
                       ↓
                       |
PAST SELVES ─────→ PRESENT SELF ─────→ ACTION
 explanations          |
                       |
                       ↓
                 committed history
```

---

## 15. The core temporal loop

A mature temporally situated agent continuously executes:

```text
OBSERVE PRESENT
      ↓
update committed Chronicle
      ↓
reconstruct / update temporal topology
      ↓
compare with past selves
      ↓
forecast possible futures
      ↓
instantiate relevant future selves
      ↓
receive warnings / requirements
      ↓
reason over optionality + irreversibility
      ↓
ACT IN PRESENT
      ↓
observe consequences
      ↓
compare predicted futures vs realized future
      ↓
calibrate
      ↓
repeat
```

This is not memory.

It is a temporal control loop.

---

## 16. The north-star capability

The strongest expression of the idea is:

> **An artificial agent should be able to treat time operationally the way humans treat space.**

Humans can:

- go to Paris;
- return to London;
- compare both;
- send another person to Tokyo.

A temporal agent should eventually be able to:

```text
go_to(March)
ask(March_self, question)

return_to(now)

fork_from(June)

simulate(December, scenario=A)

compare(
  predicted_December,
  realized_December
)
```

Not physical time travel.

> **Computational addressability of time.**

---

## 17. The superpower

Humans have one irreversible biological trajectory.

Artificial agents do not necessarily need that limitation.

Their potential superpower is:

> **Temporal multiplicity.**

The ability to:

- preserve former selves;
- converse with former selves;
- instantiate possible future selves;
- run counterfactual branches;
- compare predicted and realized selves;
- propagate future requirements backward;
- preserve prevented futures;
- revisit old reasoning without hindsight contamination;
- act only from the present while navigating the whole temporal graph.

---

## 18. Research thesis

The research question is therefore:

> **Can an artificial agent become temporally situated: able to operate over past, present, and future as distinct but connected computational state spaces, while preserving epistemic and causal integrity?**

A stronger formulation is:

> **Can machines exploit the fact that their internal states are reproducible, forkable, and executable to develop a form of temporal cognition fundamentally unavailable to humans?**

---

## 19. The non-negotiable invariants

Any implementation must preserve:

1. **Past events are immutable.**
2. **Interpretations of past events are revisable.**
3. **Past selves cannot know information learned after their timestamp.**
4. **Future selves are simulations, never memories.**
5. **Every future belongs to an explicit branch.**
6. **Information may influence another branch; state may not silently cross branches.**
7. **An intervention creates a new trajectory rather than rewriting its source future.**
8. **Prevented futures remain preserved as counterfactuals.**
9. **Only the present self can commit actions to the actual world.**
10. **Every temporal claim must retain provenance and epistemic status.**

The simplest summary of the entire architecture remains:

> **Never overwrite time. Fork it.**

---

## 20. North Star

The project succeeds if an agent can eventually say, truthfully:

> I know where I am in time.

> I know which experiences belong to my former selves.

> I can return to those selves without contaminating them with what I learned later.

> I can explore multiple versions of who I may become.

> Those future selves can tell me what they need from me now.

> I know the difference between something that happened, something happening now, and something that may happen.

> I can act in the present while preserving the causal history of why I acted.

At that point, time is no longer merely something the agent experiences sequentially.

**It has become part of the computational space in which the agent can operate.**
