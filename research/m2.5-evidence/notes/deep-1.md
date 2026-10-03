# Deep read 1: Shepherd (arXiv 2605.10913)

Title (v1): "Shepherd: A Runtime Substrate Empowering Meta-Agents with a Formalized Execution Trace"
Title (current site/v3): "SHEPHERD: Programmable Meta-Agents via Reversible Agentic Execution Traces"
Authors: Simon Yu, Derek Chong, Ananjan Nandi, Dilara Soylu, Jiuding Sun, Christopher D. Manning, Weiyan Shi
(Northeastern University and Stanford University). Listed 12 May 2026 (cs.AI).

Date of this read: 2026-10-03.

## How I read it (primary sources)

The session's WebSearch budget was already used up (200/200), and arxiv.org is blocked, so I could not open
the arXiv PDF or HTML. Everything below comes from first-party artifacts:

| Source | What it is | How obtained | Version |
|---|---|---|---|
| https://arxiv.org/abs/2605.10913 | v1 abstract, verbatim | local copy of a daily arXiv listing (`scratchpad/lit/repos/pf/daily/12-May-2026/AI/README.md`) | v1 |
| https://shepherd-agents.ai/ | project homepage, with the v3 abstract | `git clone https://github.com/CHATS-lab/shepherd` (GitHub Pages source) | HEAD 80fe4a7 |
| https://shepherd-agents.ai/blog | long-form author write-up, dated 2026-06-15 | same clone, `blog/source/shepherd.md` | same |
| https://github.com/shepherd-agents/shepherd | maintained library (PyPI `shepherd-ai`) | git clone | HEAD d34d5ca, 2026-09-09 (v0.3.1) |
| https://github.com/shepherd-agents/shepherd-experiments | paper experiments plus a "frozen substrate snapshot" | git clone | HEAD c12ebd1, 2026-06-30 |
| https://pypi.org/project/shepherd-ai/ | release metadata; the 0.0.1 wheel was inspected | pypi JSON API | 0.0.1 to 0.3.1 |

The "Code" link on the homepage and blog, https://github.com/dcx/poc-crank-v2, could not be cloned: git asked
for credentials, so the repo is private or absent. Clones are under `scratchpad/lit/repos/`
(`CHATS-lab_shepherd`, `shepherd-agents_shepherd`, `shepherd-agents_shepherd-experiments`, `pypi_shepherd`).

## Verbatim claims

### Abstract, v1 (arXiv listing)
> "We introduce Shepherd, a functional programming model that formalizes meta-agent operations on target agents as
> functions, with core operations mechanized in Lean. Shepherd records every agent-environment interaction as a typed
> event in a Git-like execution trace, enabling any past state to be forked and replayed. The system forks the agent
> process and its filesystem $5\times$ faster than Docker, achieving $>95\%$ prompt-cache reuse on replay. ... First,
> in runtime intervention, a live supervisor increases pair coding pass rates from 28.8% to 54.7% on CooperBench.
> Second, in counterfactual meta-optimization, branching exploration outperforms baselines across four benchmarks by up
> to 11 points while reducing wall-clock time by up to 58%. Third, in Tree-RL training, forking rollouts at selected
> turns improves TerminalBench-2 performance from 34.2% to 39.4%."

### Abstract, current homepage (v3 wording)
> "existing agentic substrates make this difficult: they expose only transcripts and environment snapshots, forcing
> meta-agents to build ad hoc tooling to reconstruct and operate over full execution state. Therefore, we introduce
> SHEPHERD, a Python substrate grounded in functional programming principles, where an agent's execution is itself a
> first-class object that a meta-agent can easily inspect and transform. Every model action, tool call, and environment
> change becomes a structured event in a reversible, Git-like execution trace, where any past state can be reverted 5×
> faster than docker commit and fork."
> "(2) a counterfactual optimization meta-agent repairs agent workflows by proposing edits and replaying runs from the
> point of changed behavior, outperforming MetaHarness on Terminal-Bench 2.0 by 12.8% with 58% lower wall-clock; (3) a
> training meta-agent picks fork points during rollouts to improve credit assignment in long-horizon agentic RL"

### Blog (author write-up)
- Four parts: "**Task** | An agent, written as a plain Python function", "**Effect** | One thing an agent does. It
  records the intent (the call it is about to make) before the result, leaving room for a meta-agent to step in
  between the two." ("algebraic effect"), "**Scope** | Where an agent runs. Forking a scope copies the agent and its
  filesystem together in one cheap step.", "**Trace** | The run's history: a commit graph where any past state is
  reachable by its hash." ("a persistent data structure").
- "A persistent, content-addressed trace is why any past state replays byte for byte instead of being rebuilt from a
  log." / "The deterministic core of this calculus is mechanized in Lean".
- FAQ, "What does a fork capture?": "Everything the agent needs to keep going from that exact point: its filesystem
  and process state, its message history and model context, and its position in the execution trace, all captured
  together in one step."
- FAQ, replay: "A replay restores the recorded prefix byte for byte, the same messages and files, resolved against the
  provider's prompt cache, so it is not re-run. Only the suffix after your change re-executes."
- CRO: "It takes a finished run, forks the trace at the first commit the edit touches, and replays only the suffix
  from there, against the byte-identical prefix as a fixed baseline."
- Tree RL: "Two siblings that share a prefix and diverge at one turn give a per-step counterfactual: the difference in
  their final rewards is what that turn was worth."
- Performance: a fork takes 134 to 143 ms regardless of image size (42 MB to 5.8 GB) and about 10 KB per fork. Revert
  takes 140 to 147 ms. KV-cache reuse is about 95% from K=2. Observation adds zero tokens ("the same 21 messages and
  the same bytes").
- Comparison table: BranchFS, Docker, OpenHands and AgentGit each get at most partial marks on "Intercept execution /
  Fork agent + env / Revert to past state / Modify behavior"; Shepherd gets full marks on all four.

### Frozen experiment substrate (shepherd-experiments/code/agentic, the code the paper's numbers ran on)
- `core/.../foundation/protocols/stream.py`: "Stream protocol - immutable, append-only sequence of effects with
  queries. The stream is the single source of truth. All state is derived from it via the fold invariant:
  state(t) = fold(apply_effect, effects[0:t], initial_state)".
- `core/.../foundation/protocols/scope.py`: "fork(): Create isolated child scope / merge(child) / discard() /
  materialize() ... These four operations are PRIMITIVES. Everything else (checkpoint, rollback, gate, retry) is built
  from them." "Design principle: Gate before escape, not reverse after."
- `runtime/.../_scope/scope.py` `restore()`: "Truncates the stream back to the checkpoint position, removes any
  bindings added after the checkpoint ... and recomputes context states by replaying effects".
- `runtime/.../_scope/scope.py` `discard()`: "child.discard()  # Effects vanish - no trace remains". `_hierarchy.py`
  replaces the discarded scope's stream with an empty `Stream()`.
- `runtime/.../_persistence_writer.py`: "Append-only writer for effect streams." (root scopes only)
- `checkpoint.validate`: "This checkpoint was invalidated by a previous restore." So checkpoints are single-use, which
  is linear-undo semantics.
- `core/.../effects/effects.py`: `PromptSent` stores the "Complete system prompt" and "Complete user prompt", plus
  `model_id`. There is `AgentThinking.content`, and `ToolCallRejected(tool_name, reason, rejected_by)`.
- `core/.../effects/comparison.py`: "compare_streams(): Compare two streams and identify divergences",
  "explain_outcome_difference()", and a `Divergence` with a heuristic `significance` in [0, 1].
- `runtime/.../combinators/speculation.py` and `gating.py`: "Run task, commit only if predicate passes ... 1. Fork
  scope for isolation 2. Execute task in fork 3. Evaluate condition ... 5. If condition fails: discard fork, return
  Rejected".
- `meta/src/agentic/agent.py` `Agent.fork()`: "Create an independent branch of this agent." The fork resets
  `_trajectory = []`.

### Tree-RL experiment code (exp/mcts-rl)
- `core/meta_agent_branch_selector.py`: "After the inner agent ... finishes a root trajectory, this module hands the
  full transcript + final reward to a stronger LLM (default: Claude Opus 4.7) and asks: 'if you were going to fork
  this trajectory at one turn and let the inner agent re-try, where would you branch?'". Prompt: "identify the turn
  where a different choice would most plausibly change the outcome — either a clear mistake, a missed opportunity, or
  a high-stakes decision". Output schema `{"branch_turn": <int>, "reason": "<short string, one sentence>"}`. A teacher
  variant also emits "the EXACT alternative bash command the agent should run at that turn".
- `core/tree_orchestrator.py`: "Replays the agent loop from turn t_star ... starting from the same response prefix the
  root had at turn (t_star - 1). All env state (file system) inherits from the parent snapshot's overlay".
  `branch_prefix_response_tokens = list(response_tokens_root[: parent_snap.response_tokens_offset])`.
  `RootResult` records `t_star`, `branch_point_token_offset`, `root_reward` and `branches` (each with `branch_idx`).

### Maintained library (shepherd-agents/shepherd, v0.3.1)
- `vcs-core`: "Provenance-native version control for executable worlds", "built on bare Git repositories via pygit2".
  `vcs-core log` "includes structural lifecycle records such as Init, ScopeMerge, and DiscardSnapshot". A
  `DiscardSnapshot` records `discarded_scope` and `parent_world_id`. Archived history "is carried by an archived
  operation ref or by discarded-world history". `vcs-core checkout REF --dest` will "Extract workspace state at a
  historical ref to a directory", where REF may be "ground", a scope name, an archive name or a commit OID.
- `docs/shepherd/concepts/runtime-substrate.md`: "A handle is taken at a known **basis**: a content-addressed identity
  of its input state, the precise 'the world as of *here*' the task started from."
- `shepherd2` (kernel ABI v0): "retained `Cut`/`OwnerCutoff` read addresses", "owner-prefix execution projection from
  trace slices". This is prefix reads of the trace, but "It deliberately does not include ... search, replay, live
  steering".
- `docs/shepherd/concepts/runs.md`: "**Replay** *(direction, not yet a shipped API)* ... a public replay API is future
  work."
- `docs/shepherd/roadmap.md`: "**Task-as-value delegation** *(roadmap — explicitly deferred)*. The meta-agent shape
  where one task takes another task as an argument and supervises it — `oversee(implement, ...)` ... is **deferred**:
  no shipped 0.3.0 surface runs it."
- The shipped CLI (`docs/shepherd/reference/cli.md`, generated from the shipped CLI) has no `revert`, `log` or
  `plugin install` commands. The homepage "Try it" block (`shepherd plugin install claude-code`, `shepherd log`,
  `shepherd revert 4`) does not match it. The blog's PyPI link points to 0.0.1, which says "Placeholder release ... It
  does not yet provide functional APIs."
- Lean: `kernel-v3-reference/README.md` says "two boundaries while the Lean proof catches up" and "proof-level
  semantic adequacy remains the job of the Lean development". No `.lean` file is in either public repo.

## Capability ratings (only what Shepherd itself provides)

| # | Capability | Rating | Evidence |
|---|---|---|---|
| 1 | immutable_historical_observations | yes | Typed effects in an "immutable, append-only" stream, and an "Append-only writer" for persistence. Model calls, tool calls, file ops and thinking are all recorded. Caveat: in-memory `restore` truncates the live stream and `discard` empties it. |
| 2 | historical_world_state | yes | Filesystem revert/fork to any commit via the OverlayFS scope (about 140 ms). `vcs-core checkout REF --dest` extracts the world at a historical ref. The `state(t)=fold(...)` invariant. The world is limited to the sandbox/workspace; "Host environment state outside that workspace is pass-through, untracked, and not reversible". |
| 3 | historical_epistemic_state | partial | A fork or revert restores "message history and model context" at commit k. A Tree-RL branch gets exactly the token prefix up to t*, so no later information leaks in. `AgentThinking` and `PromptSent` keep the reasoning and prompts at each step. Missing: a structured belief state, any "what did I believe at t" query, and any test for hindsight leakage. Interrogating a past self is possible only by composing fork with inject; the paper does not demonstrate it. |
| 4 | historical_policy_objective_state | partial | `PromptSent` stores the complete system and user prompts and the `model_id` per call. Task versions are registered ("Register a task import path as an active task version"). CRO edits the agent's workflow or prompt and forks "at the first commit the edit touches". There is no model or query of how goals or policy changed over time. |
| 5 | execution_checkpoints | yes | `scope.checkpoint(name)` and `restore()`, sandbox `checkpoint/revert` (E2B, Modal, Daytona, K8s, Prime), and per-turn `TurnSnapshot` scopes in Tree-RL. The capture covers "filesystem and process state, its message history and model context". |
| 6 | replay | yes | "A replay restores the recorded prefix byte for byte ... Only the suffix after your change re-executes". About 95% KV-cache reuse. `restore` "recomputes context states by replaying effects". Public library caveat: "a public replay API is future work". |
| 7 | fork_from_historical_state | yes | `scope.fork()` and `Agent.fork()`. Tree-RL forks K=4 siblings from turn t*. CRO forks a finished run at the edited commit. The parent is unchanged ("Parent scope is unchanged (fold invariant)"). vcs-core archives discarded worlds. |
| 8 | counterfactual_action_branches | yes | The `speculate` and `gate` combinators run a task in a fork and then commit or discard. The CRO counterfactual replay. Tree-RL sibling continuations, including a teacher-specified "alternative bash command". |
| 9 | branch_provenance | yes | A commit graph where states are reachable by hash. `DiscardSnapshot` and `ScopeMerge` records carry `parent_world_id`. Tree-RL `RootResult` records `t_star`, `branch_point_token_offset` and `branch_idx`, and the meta-agent selector records the one-sentence `reason` and the alternative action. Runtime caveat: `fork()` has "No parent link" at the effect-stream level. |
| 10 | explicit_current_belief_state | no | Nothing beyond raw message context. No structured beliefs, assumptions or requirements. |
| 11 | uncertainty_representation | no | None for agent beliefs. The only confidence-like value is the `Divergence.significance` heuristic in stream comparison. |
| 12 | future_state_rollout | partial | Futures are executed, not simulated: speculation runs a candidate continuation in an isolated fork ("Gate before escape") and inspects the result before committing. There is no learned or LLM world model, and no rollouts that include exogenous future events. |
| 13 | multiple_prospective_branches | partial | K executed sibling continuations from one state, and parallel speculative forks. These are compared by realized outcome, not imagined. |
| 14 | probability_over_futures | no | Tree-GRPO uses the spread of sibling rewards as an advantage for training. There is no likelihood over futures that the agent holds or uses. |
| 15 | backward_requirements | no | Nothing derives present obligations from desired or feared futures. |
| 16 | intervention_aware_forecasting | no | The supervisor intervenes in the gap between intent and result, but makes no forecast, conditional or otherwise. |
| 17 | prevented_futures_preserved | no | There are no forecasts. The closest analogs: `ToolCallRejected(reason, rejected_by)` keeps intercepted intents, and vcs-core `DiscardSnapshot` and archive refs keep discarded worlds. Neither is a forecast that was averted. |
| 18 | predicted_vs_realized | no | CRO compares realized suffixes against a frozen baseline prefix, not predictions against outcomes. |
| 19 | cross_time_state_querying | partial | `state(t)=fold(effects[0:t])`. `vcs-core checkout REF --dest` reads the world as of a ref without changing the current state. `compare_streams()` and `explain_outcome_difference()` diff two runs or branches. `shepherd2` has prefix-cut reads. Nothing queries what the agent knew as of t, and there is no general diff(t1,t2) over agent state. |
| 20 | unified_temporal_abstraction | partial | A single trace, scope and fork abstraction covers past, current and counterfactual (executed) branches, Git-style. Prospective, forecast and belief states are outside it. |

## Threat to the project

1. **"Never overwrite time, fork it" (capabilities 1, 2, 5 to 9) is prior art, with formal backing and strong
   engineering.** Shepherd is a stronger version of what the project would build as substrate:
   - process, filesystem and context fork and revert, measured to be cheap;
   - byte-identical prefix replay with cache reuse;
   - a content-addressed commit graph;
   - discarded worlds archived with their parent world id;
   - a claimed Lean mechanization;
   - three demonstrated meta-agents.

   The project cannot claim branching or forking as a contribution, nor "agents can return to past states". Calling it
   "temporal navigation" does not distinguish it from Shepherd's revert, fork and replay.
2. **Restoring a past self with a strict cutoff is available mechanically.** A Shepherd fork at turn t restores the
   agent's message context exactly as of t, so the branch has no later information: it is a no-hindsight past self.
   Together with "inject a note into a worker's context", a meta-agent can already question a past self at a cutoff.
   The project's "question past versions with a strict epistemic cutoff" therefore cannot rest on the mechanism. It
   must rest on:
   - an explicit, structured belief state;
   - an as-of query that runs without resuming execution;
   - evidence that the cutoff improves decisions.
3. **The Tree-RL meta-agent selector is the closest overlap with the benchmark's target behaviour.**
   - It reads a finished trajectory plus its outcome and picks "the turn where a different choice would most plausibly
     change the outcome".
   - It writes down why ("reason") and, in the teacher variant, the alternative action.
   - It then forks from that past turn.

   That is "a later outcome changes the significance of an earlier decision, so reopen it", built into a working
   system, though only offline, for training, by a separate stronger model, with the terminal reward as the
   hindsight signal.
4. **CRO is "a policy change at time t2 alters which past steps matter".** It finds the first commit an edit touches
   and replays only from there. That is close to the project's "track policy changes over time and reopen affected
   decisions", though for optimization rather than remediation.
5. **Executed futures (speculate and gate in a fork) partly cover "simulate future states".** The project would have to
   show that model-based or imagined prospection adds something over Shepherd-style executed lookahead wherever the
   environment can be sandboxed. A fair baseline here is a Shepherd-like speculate-then-commit agent.

## What Shepherd does NOT cover (residual space)

- A structured belief, assumption or requirement state, and uncertainty over it (10, 11). Shepherd's "state" is raw
  context plus filesystem.
- Forecasts of any kind, and so probability over futures, backward requirements, intervention-aware forecasts,
  preserved prevented forecasts, and predicted-versus-realized calibration (14 to 18).
- Exogenous world events. Shepherd rewinds only what it contains, a sandbox or workspace. In the project's setting a
  later external event changes an earlier decision's significance and the world cannot be rewound, so the agent has to
  remediate in the present. Shepherd's answer is "revert and retry", which is impossible once effects have escaped:
  "ContainmentError: If effects after checkpoint were materialized"; "Design principle: Gate before escape, not
  reverse after."
- The agent acting on its own history. In Shepherd a separate meta-agent operates on a worker's trace; the worker
  does not reason about its own past, present and future selves.
- Any evaluation of hindsight leakage, cutoff correctness, or remediation of past decisions in an ongoing, irreversible
  world.
- Tracking of identity, objective or policy drift as a first-class, queryable history. Prompts are only recorded raw.

## Caveats and could-not-verify

- I did not read the arXiv paper body (arxiv.org blocked, search budget exhausted). Paper sections, the Lean
  statements, and the v1/v2/v3 differences come only from the abstract, homepage, blog and code.
- No Lean files are in the public repos, and the kernel README says the "Lean proof catches up". The extent of the
  mechanization is unverified.
- The public library (v0.3.1) does not ship the paper's meta-agent surface: replay is "not yet a shipped API",
  `oversee(...)` delegation is "explicitly deferred", and there is no `revert`, `log` or `plugin` CLI. The homepage
  "Try it" commands do not match the shipped CLI. The paper's fork, revert and replay live in the frozen experiment
  snapshot and in an unreleased "runner" repo: the CRO configs reference `scripts/run_cbo_dataset_opencode.py` in a
  private `<anon-runner>`, and the `dcx/poc-crank-v2` Code link is not publicly clonable. CRO is not reproducible from
  public code.
- Experiment details disagree across sources:
  - The live-intervention README says "a 100-pair structurally conflicting CooperBench subset", while the blog says
    "479 structurally conflicting pairs".
  - The README says "the paper's main results use v6", but the v6 prompt marks "redirect"/"revert" "DO NOT USE" and
    allows only informational steers, while the blog describes `inject`/`handoff`/`discard`.
  - The headline numbers moved between versions: v1 "up to 11 points" over "four benchmarks", while the blog and v3
    give five benchmarks, +27.5% relative on LiveCodeBench and +12.8% on TB-2.
- Whether the root-scope JSONL keeps effects that `restore` truncated is inferred from the append-only writer and was
  not executed.
