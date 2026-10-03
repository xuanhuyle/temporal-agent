# Temporal Multiplicity Kernel v0

Date: 2026-10-03

## Research question

What can an agent do once versions of its own explicit executable state become
copyable, mutable, independently executable and comparable?

This branch is a fresh research program. It does not continue the stopped
Tesseract architecture program and it does not continue the Resume Gate product
experiment.

## v0 primitive

The kernel implements only four operations:

1. snapshot(state)
2. fork(state_id, epistemic_cutoff=?, mutations=?)
3. run(branch_id, task, runner, budget)
4. compare(branch_a, branch_b, ...)

The state is explicit agent-level state, not model hidden activations. It can
contain knowledge, beliefs, goals, commitments, context and metadata.

## Core invariant: epistemic isolation

A historical fork created with epistemic_cutoff=t does not merely receive a
prompt saying "ignore what happened later."

Facts acquired after t are physically absent from the branch.

This is the key property needed before any serious past-self experiment. If
later facts remain in context, an apparent historical-self result can always be
contaminated by hindsight.

The deterministic example at
examples/multiplicity/hindsight_demo.py proves this state-isolation property.

It does not prove an intelligence advantage.

## First falsification experiment: hindsight leakage

The first model-backed experiment is deliberately narrower than the full
temporal-multiplicity thesis.

Each case has:

- an explicit decision rule;
- evidence available before a cutoff;
- a historically justified answer at the cutoff;
- later information that strongly points to a different answer.

The same model is run in two conditions.

### Baseline

The model receives the entire timestamped timeline, including post-cutoff
events, plus a strong explicit instruction to answer using only information
available at the cutoff.

### Isolated fork

The model receives the same task and decision rule, but the state has been
mechanically truncated. Post-cutoff events do not exist in its input.

### Primary metrics

- cutoff-decision accuracy;
- hindsight-leak rate: choosing the later answer instead of the historically
  justified answer.

Secondary metrics:

- valid structured-answer rate;
- confidence;
- input/output token usage.

The current dataset contains eight synthetic cases spanning incident response,
procurement, fraud, software release, credit, routing, capacity and access
policy.

These are controlled evaluator cases, not evidence that the same effect occurs
in open-ended real-world reasoning.

## Running the experiment

After installing the package:

    tmk-hindsight --provider claude-cli --model <model> --effort high

or:

    PYTHONPATH=src python -m multiplicity_experiments.hindsight_eval \
      --provider claude-cli \
      --model <model> \
      --effort high

The command uses the repository's existing metered model gateway, so both
conditions are served by the same configured model.

Run the `claude-cli` provider from a normal terminal: the runner refuses to
start inside a Claude Code session (`CLAUDECODE` set). The frozen protocol
(v0.1), the exact command, the pre-registered verdict rule and the results are
in [experiments/tmk-hindsight-v0-results.md](experiments/tmk-hindsight-v0-results.md).
Re-analyse a result file with
`PYTHONPATH=src python -m multiplicity_experiments.hindsight_analysis RESULT.json`.

An Anthropic API run is also supported through provider=anthropic when the
environment is configured for the existing harness.

## Kill criterion

If a strong full-history baseline with explicit timestamps and careful
instructions matches the mechanically isolated condition across held-out cases
at similar cost, then epistemic forking has not demonstrated a distinctive
capability.

That would not kill all forms of temporal multiplicity. It would kill the first
candidate advantage: mechanically enforced hindsight-free historical reasoning.

## What comes only after a positive result

Do not build branch merging, future-self planning or a large temporal
architecture yet.

If epistemic isolation shows a robust advantage, the next candidate operations
to test are:

1. competing epistemic selves that maintain incompatible hypotheses;
2. prevented-future learning, where the agent's action changes the outcome it
   later learns from;
3. branch-forward planning over alternative agent states;
4. self-revision after a foundational belief changes;
5. safe self-modification by fork, evaluate and commit.

Each should be a separate falsifiable experiment.


## Product interpretation: a cognitive capability, not a model

The product hypothesis is deliberately model-agnostic.

Temporal multiplicity should be something an agent runtime can **gain** without
requiring a specific foundation model:

    ordinary agent
        +
    TemporalMultiplicity capability
        =
    agent that can snapshot, fork, execute and compare versions of its own
    explicit state

The model remains the reasoning engine. The multiplicity layer changes the
operations available to that reasoning engine.

The core package therefore defines only a generic `CognitiveBackend` contract:

    reason(state, task, budget) -> RunResult

A backend may wrap:

- Claude;
- GPT;
- Gemini;
- a local/open-weight model;
- a symbolic reasoner;
- a human or hybrid workflow;
- another agent runtime.

The core `multiplicity` package has an explicit test forbidding imports from
the benchmark harness and from model-vendor SDKs. Provider-specific evaluation
code now lives in `multiplicity_experiments`.

This separation matters scientifically too. If a capability gain only appears
with one model family, that is evidence for an interaction effect, not a general
cognitive primitive.

A mature claim would therefore require replication across multiple reasoning
backends.
