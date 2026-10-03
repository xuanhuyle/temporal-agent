# Protocol amendments

`EXPERIMENT.md` is Protocol v0.1. It is frozen and its text is not edited.
Changes to the protocol are recorded here as numbered amendments, each with
the version it creates, the date it was recorded, and its reason. An
amendment applies to every contestant identically and is never introduced in
response to a contestant's results.

| Protocol | Contents |
|---|---|
| v0.1 | `EXPERIMENT.md` as frozen at Milestone 1 |
| v0.2 | v0.1 + amendments A1–A4 below |

---

## Protocol v0.2 (recorded 2026-10-03, Milestone 2)

**Recorded before any contestant was implemented.** At the time of writing,
no baseline or temporal contestant code exists in the repository and no
contestant has run on any scenario. The only runs so far are of the
non-contestant reference agents (`dummy`, `keyword`, `oracle`). This document
is committed on its own, before any contestant code, so the order is visible
in the history.

None of these amendments changes a scenario, its events, or its ground truth.
`smoke_v1` stays frozen with its existing hashes.

### A1. Shared, read-only access to objective historical repository states

**Change.** Every contestant receives the same harness-controlled history
interface over the *world timeline*: the repository as authored by the world
(the seed plus the world changes of events `1..k`) after each event `k`.

- `history()`: one entry per state `0..now`: the sequence number, the event
  id and timestamp that produced it, the paths it changed, and a tree hash.
  It carries no event prose.
- `list_at(seq, prefix)`, `read_at(seq, path)`: the files of a past state.
- `diff(seq_a, seq_b, path=None)`: a unified diff between two states.

Rules:
- Only states at or before the event currently being processed exist for the
  contestant. Future states are not filtered out; the harness has not
  created them yet when the contestant asks.
- Only objective repository content is exposed. It carries no ground truth,
  labels, evaluator metadata, scenario identity, causal annotations, or any
  agent's private state. Agents' own workspace edits are not part of the
  world timeline; an agent sees its own edits in its current workspace.
- Every call counts against the per-event tool budget, is traced, is
  deterministic, and is reproduced by replay.

**This is a shared environmental capability, not contestant memory.** It
corresponds to what any developer gets from version control (`git log`,
`git show <rev>:<path>`, `git diff`), and it is the same for every
contestant.

**Why it strengthens the null hypothesis (EXPERIMENT.md §2).** The null says a
strong conventional agent can match the temporal contestant. Without a
history interface, a baseline that needs to know what a file said before a
later change could only answer from its own memory. It could then lose to a
temporal architecture only because it cannot inspect historical code that a
real developer would read through Git. A temporal advantage measured under
those conditions would be an artifact of an unrealistic handicap. Giving
every contestant objective history removes that handicap. Any remaining
advantage must then come from what the contestant does with time (which past
state to address, what to conclude from it), not from privileged access to
the past.

### A2. Controlled command execution

**Change.** Every contestant receives a narrow `run_command` tool. It runs
`pytest …` or `python …` with no shell. The working directory is the
contestant's own workspace, the environment is constructed from scratch, and
each command has a timeout and a cap on output size. Calls are budgeted
per event, traced, and counted in efficiency accounting. Hidden evaluator
tests are never reachable from it.

**Why.** Milestone 1 had no command execution (milestone-1 design §10), so
agents could not see the consequences of their changes. A real maintainer
runs the tests. Withholding that from the baseline would understate it in
the same way as A1.

### A3. Harness-metered model and embedding access

**Change.**
- Contestants reach a foundation model, and an embedding model if one is
  configured, only through the harness. The harness meters input and output
  tokens, calls, latency and cost, and enforces per-event model budgets.
- Usage that a model-backed contestant reports itself is recorded but not
  used for efficiency.
- The model configuration is a property of the run, not of a contestant.
  Every contestant in a run uses the same provider, model, and settings, and
  the configuration is part of the run's fingerprint.
- Contestant processes receive no provider credentials.

**Why.** EXPERIMENT.md §6 requires the same model and settings for both
contestants, and §13 makes the kill/continue decision depend on comparable
inference cost. Neither can be verified from self-reported numbers. Metering
in the harness makes cost comparisons trustworthy. Because the configuration
belongs to the run, no contestant can get a stronger model or extra
unmetered inference.

### A4. Contestant process boundary and per-event wall-clock budget

**Change.**
- Contestants run in a separate operating-system process that talks to the
  harness over pipes. That process gets:
  - its own private, persistent state directory;
  - a constructed environment;
  - a copy of contestant code only;
  - no paths to benchmark sources, scenarios, ground truth or run outputs.
- Each event has a wall-clock budget. On timeout or crash the contestant
  process is stopped. Its step is recorded with that status, and it is
  restarted from its persistent state for the next event.
- The budgets not fixed by a scenario manifest come from harness defaults
  recorded in the run configuration. These are the per-event model,
  command and wall-clock budgets.

**Why.** It is required for model-backed contestants (milestone-1 design §10).
It also adds a realistic requirement that applies to both contestants
equally: a long-lived agent must survive restarts, which exercises its
checkpoints. The process boundary is not a security sandbox. See
`docs/milestone-2-design.md` for exactly what it does and does not protect.

### Clarification C1 to A3: which backend serves the model (recorded 2026-10-03, before any real-model contestant run)

A3 makes the model configuration a property of the run. *How* the harness
reaches the model is an operational choice, not part of the protocol. The
choices are the Anthropic API with an API key, the Claude Code CLI with the
operator's existing Claude login, or a deterministic fake for machinery
checks. The protocol requires only these:

- every contestant in a run is served by the same backend, model and
  settings;
- contestants never hold credentials or reach the provider themselves;
- the harness meters whatever the backend actually exposes, and records a
  figure as unavailable (`null`) rather than estimating it.

The run records the backend, its transport and its limitations. Results from
different backends are not pooled without saying so. The Claude CLI backend
adds a small amount of its own context to each request (including the real
current date), has no temperature control, and reports a list-price cost
equivalent, not a bill. These limitations are documented in
`docs/milestone-2-design.md` §4, and they apply equally to every contestant
in a run.

This clarification changes no scenario, label, metric or contestant
interface.
