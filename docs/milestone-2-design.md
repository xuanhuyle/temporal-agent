# Milestone 2 design: shared contestant runtime and strong conventional baseline

Status: **implemented** (Milestone 2). Protocol: v0.2
(`docs/protocol-amendments.md`). No Tesseract code is part of this milestone.

The milestone exists for falsification. It must produce the strongest *fair*
conventional contestant, the one a later temporal architecture has to beat.
If this baseline reproduces the target behaviour at comparable reliability
and cost, that is evidence against the need for a distinct temporal
architecture (EXPERIMENT.md §2, §13).

---

## 0. Conceptual boundary (read this first)

The current benchmark tests one slice of the north star: **a later event
changes the significance of an earlier decision** (temporal governance:
detect, trace, reconsider, remediate). It does **not** test past-self
dialogue or temporal multiplicity (NORTH_STAR.md §5, §17):

- The decisions that scenarios bear on are **authored by the benchmark world**
  (seed ADRs, ADRs and tickets delivered by events). No contestant made them,
  so there is no decision-time epistemic state of the agent to reconstruct.
- Strong temporal-governance scores are therefore **not** evidence that
  addressing an executable past self helps. They show only that an agent can
  notice and act on changed significance.
- Testing "can present-self gain something by talking to an executable
  past-self that strong retrieval cannot reproduce?" needs a future
  experiment. In it, decisions must be **made by the agent**, and its
  **decision-time epistemic state** (context, beliefs, uncertainties, rejected
  alternatives) must be preserved, so that a reconstruction can be compared
  with retrieval over the same record.

Do not read temporal-governance results as a test of temporal multiplicity.

---

## 1. Module map

Harness side (benchmark infrastructure, runs in the harness process):

| module | role |
|---|---|
| `harness/tools.py` | `ToolBox`: the one tool surface; budgets, metering, recording |
| `harness/tool_specs.py` | declarative tool table (names, families, argument types) |
| `harness/history.py` | `WorldHistory`: the revealed world timeline (A1) |
| `harness/commands.py` | `CommandRunner`: `run_command` (A2) |
| `harness/model/` | `ModelGateway` and backends: fake, claude-cli, anthropic, hash embeddings, recorded (A3) |
| `harness/process.py` | `ProcessAgent`: harness-side proxy for a contestant process (A4) |
| `harness/runner.py`, `replay.py`, `cli.py` | integration |

Shared by both sides (stdlib only, copied into contestant processes):
`harness/agent.py`, `harness/errors.py`, `harness/llm.py`,
`harness/tool_specs.py`, `harness/wire.py`, `harness/tripwire.py`,
`harness/worker.py` (contestant-process main).

Contestant side (contestant code, runs in the contestant process):

| package | role |
|---|---|
| `contestant_runtime/` | shared LLM agent loop, prompt protocol, memory-system interface |
| `baseline/` | the conventional memory system: event log, checkpoints, hybrid retrieval, summaries |

Contestant packages may import only the standard library,
`harness.agent`, `harness.errors`, `harness.llm` and `harness.tool_specs`
(AST-enforced). Everything else in `harness` is benchmark-side.

---

## 2. World history (`harness/history.py`, amendment A1)

```python
class WorldHistory:
    revealed_seq: int                     # -1 before the first reveal
    def reveal(self, seq: int, files: Mapping[str, bytes], *, event_id: str | None,
               timestamp: str | None, changed_paths: Sequence[Mapping[str, str]]) -> str
    def history(self) -> list[dict]
    def list_at(self, seq: int, prefix: str = ".") -> list[str]
    def read_at(self, seq: int, path: str) -> str
    def diff(self, seq_a: int, seq_b: int, path: str | None = None) -> dict
    @staticmethod
    def snapshot_files(root: Path) -> dict[str, bytes]
```

- **Structural future-blindness.** The runner keeps a private world-only copy
  of the repository. It applies each event to that copy at the same moment it
  applies the event to the agents' workspaces, then calls `reveal(seq, ...)`.
  `reveal` accepts only `revealed_seq + 1`. Before event `k` is applied, state
  `k` does not exist in the object, so no argument, path trick or error
  message can produce it.
- `reveal` returns the tree hash, computed the same way as
  `canonical.tree_hash`. The runner checks it against the manifest's
  `world_state_hashes`.
- `history()` returns one entry per state:
  `[{"seq", "event_id", "timestamp", "changed_paths", "tree_sha256"}]`. State 0
  has `event_id: null, timestamp: null, changed_paths: []`.
  - No event prose (subject/body), no labels, no scenario id.
- Paths are validated with `workspace.validate_relpath`; invalid paths raise
  `AccessDenied`.
- An unknown or unrevealed seq raises `ToolError("no repository state at seq N;
  available: 0..R")`. The wording is the same for a negative, a future or an
  absurd seq.
- Missing files raise `ToolError`, and so do non-UTF-8 files.
- `list_at` has the same prefix semantics as `Workspace.list_files`.
- `diff` returns `{"seq_a", "seq_b", "path", "files": [{"path", "status": added|deleted|modified}], "diff": str, "truncated": bool}`.
  `diff` is a deterministic `difflib.unified_diff` with `a/` and `b/` labels,
  capped at `MAX_DIFF_CHARS`. Binary files are listed but not diffed.
- Storage is content-addressed and in memory: digest → bytes, and per state
  path → digest. Byte strings are immutable.
- Caches are excluded (`canonical.IGNORED_*`), as are symlinks and special
  files.

## 3. Commands (`harness/commands.py`, amendment A2)

```python
class CommandRunner:
    def __init__(self, workspace_root: Path, scratch_dir: Path, *, python: str = sys.executable,
                 max_output_chars: int = 20_000, extra_read_roots: Sequence[Path] = ()) -> None
    def run(self, command: str, timeout_s: float) -> dict
    # -> {"argv": [...], "exit_code": int | None, "output": str, "truncated": bool,
    #     "timed_out": bool, "violations": [str], "wall_clock_ms": float}
```

**Grammar** (`shlex.split`, no shell, so `|`, `>`, `;`, `$()` are just arguments):
- `pytest ARGS...` and `python -m pytest ARGS...` become
  `pytest -p no:cacheprovider ARGS...` (`python3` is an alias of `python`);
- `python -m MODULE ARGS...` (dotted identifier);
- `python PATH.py ARGS...`, where the path is workspace-relative, validated,
  and an existing file;
- `python -c CODE ARGS...`;
- any other program, or a Python option other than `-m`/`-c`, raises `ToolError`.

**Execution.**
- Command: `[python, "-s", "-B", <scratch>/tab_cmd_boot.py, <cfg_fd>]`.
  - `cwd` is the workspace and `stdin` is `/dev/null`;
  - stdout and stderr are merged;
  - `start_new_session=True`, and the config arrives over an inherited pipe
    (`pass_fds`), so no paths appear in argv or the environment.
- The bootstrap:
  - reads its config and closes the fd;
  - sets rlimits (no core files, file-size cap);
  - installs `harness.tripwire` (§5): reads allowed under the workspace, the
    interpreter's stdlib and site-packages and `/usr/share/zoneinfo`; writes
    allowed under the workspace and the scratch `tmp` and `home`; no network,
    processes or ctypes, and no exemption for bytecode caches;
  - sets `sys.argv`, puts the workspace first on `sys.path`, and runs the
    target with `runpy`.
- The environment is built from scratch: `PATH=/usr/bin:/bin`, `HOME` and
  `TMPDIR` in scratch, `LANG=C.UTF-8`, `TZ=UTC`, `PYTHONHASHSEED=0`,
  `PYTHONDONTWRITEBYTECODE=1`, `PYTHONNOUSERSITE=1`,
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `NO_COLOR=1`. It carries no
  credentials, no proxies and no `PYTHONPATH`.
- On timeout the whole process group gets `SIGKILL`; `timed_out: true` and
  `exit_code: null`. After every command the group is killed anyway, to reap
  stragglers. The scratch `tmp` and `home` are wiped before and after each
  command.
- **Output** is decoded as UTF-8 with replacement and normalized for
  determinism:
  - the absolute workspace path becomes `.` and the scratch path `<tmp>`;
  - pytest durations become `in <t>s`;
  - memory addresses (`0x7f…`) become `0x<addr>`.

  Above `max_output_chars` the normalized output is truncated (head and tail
  kept, marker between). Normalization happens first, so truncation does not
  depend on how long the host paths are.
- Hidden evaluator tests are never in the workspace, and the tripwire
  allowlist does not cover the repository, so commands cannot reach them.

## 4. Model gateway (`harness/model/`, amendment A3)

```python
class ModelGateway:                                     # one per run
    def __init__(self, settings: ModelSettings, backend: CompletionBackend | None,
                 embedder: EmbeddingBackend | None, pricing: Pricing | None = None) -> None
    def lane(self, name: str) -> "LaneModelService"     # implements tools.ModelService for one agent
    def describe(self) -> dict                          # public config for run metadata (never secrets)

class CompletionBackend(Protocol):
    name: str
    def complete(self, request: ModelRequest, settings: ModelSettings, *, max_output_tokens: int,
                 timeout_s: float | None, lane: str) -> RawCompletion
class EmbeddingBackend(Protocol):
    name: str
    def embed(self, texts: list[str], settings: ModelSettings, *, timeout_s: float | None,
              lane: str) -> RawEmbedding
```

**Metering record.** Every response comes with one. The ToolBox sums it into
the step's meter and writes it to the trace:

```
{"provider", "model", "usage_available", "input_tokens", "output_tokens",
 "cache_read_input_tokens", "cache_creation_input_tokens", "total_input_tokens",
 "auxiliary_input_tokens", "auxiliary_output_tokens", "retrieval_tokens",
 "cost_usd", "cost_basis", "stop_reason", "purpose", "request_sha256",
 "max_output_tokens", "latency_ms", ["provider_meta"]}
```

- **Token fields.**
  - `input_tokens` is the provider's uncached input.
  - The cache fields are its cache reads and cache writes.
  - `total_input_tokens` is their sum, i.e. every prompt token processed.
    Efficiency (`model_input_tokens`) and the input budget use the total.
- **Never invented.** A backend that cannot report usage sets
  `usage_available: false`. Every token field is then `null`, the agent's
  meter gets `tokens_known: false`, and budgets fall back to the
  deterministic estimate.
- **Cost.** `cost_basis` says where `cost_usd` comes from:
  - `price_table`: tokens times the list prices;
  - `provider_reported`: a figure the provider or CLI reported;
  - `null`: the call is unpriced, and `cost_usd` is `null` too.
- **Auxiliary calls.** `auxiliary_*` count a provider's own side calls (the
  Claude CLI makes a small auxiliary model call per invocation). They are
  reported apart from the contestant's call.
- `retrieval_tokens = round(total_input_tokens * retrieval_chars / total_chars)`.
- `latency_ms` (anywhere in the record) is volatile.

- **Token estimator** (`tokens.estimate_tokens`): `ceil(utf8_bytes / 4)`.
  It is deterministic. Budget pre-checks use it, and so does the fake
  backend's usage.
- **Backends.** Pick one per run with `--model-provider`. Each run records
  `provider`, `model` and `transport` in its fingerprinted configuration, and
  facts read from the machine (e.g. the CLI version) in
  `metadata.model_runtime`.

  | provider | what it is | needs | used for |
  |---|---|---|---|
  | `fake` (`fake-v1`) | deterministic test double implementing the agent–LLM protocol (§7) | nothing | CI and machinery checks. **Its scores are meaningless.** |
  | `claude-cli` | the Claude Code CLI, `claude -p --output-format json`, one process per call | an existing Claude login (e.g. a Max subscription); no API key | real model runs without separate API billing |
  | `anthropic` | Messages API via the official `anthropic` SDK (optional dependency, lazy import) | `ANTHROPIC_API_KEY` in the harness environment | later: many repeated controlled runs, exact settings, cleaner metering |
  | `recorded` | serves a run's recorded responses, per lane, in order; a request whose hash differs raises `ToolError` | the original run | replay only |
  | embeddings `hash` (`hash-ngram-v1`) | deterministic feature hashing of word 1–2-grams and character 3–5-grams, L2-normalized, cost 0 | nothing | the baseline's dense channel. It is lexical, **not** a neural semantic embedding. |

  Other providers (OpenAI, local models) are added as one more backend class.
  The protocol, the ToolBox and the contestants do not change.

- **`anthropic` request.**
  - `model=settings.name`, `max_tokens`, `system`, `messages`, `stop_sequences`;
  - `temperature` only if set (sent through `extra_body`, as current SDKs
    require); `output_config.effort` if set; top-level `cache_control` if
    `prompt_caching`;
  - no server-side fallbacks: a fallback would change the model in mid-run
    and break equality. A refusal comes back as `stop_reason: "refusal"`.
- **`claude-cli` call** (`harness/model/claude_cli.py`):
  - **What is sent.**
    - The system prompt goes byte for byte, through `--system-prompt-file`.
    - The conversation goes on stdin. A single user message is sent
      verbatim. A multi-turn request (the runtime's tool loop) is serialized
      in order under `=== user ===` / `=== assistant ===` headers, after a
      fixed one-line preamble, because the CLI takes one prompt per call.
  - **Isolation of the call.**
    - `--tools ""`: the model has no tools, so it cannot run commands, browse
      or call file tools.
    - `CLAUDE_CODE_DISABLE_ATTACHMENTS=1` is always set, and the operator's
      environment cannot unset it. Without it, the CLI expands `@path`
      mentions in the prompt by reading those files with the operator's
      permissions, whatever the tool list or safe mode says. Any text in a
      request could then pull host files, ground truth included, into the
      model's context. This was found in the adversarial review and verified
      with a canary file.
      The preflight check (`claude-cli-check`, run automatically before
      `smoke-baseline-claude`) repeats that test: it mentions a canary file
      outside the CLI's working directory and refuses to start if the
      canary's secret reaches the model.
    - `--safe-mode`: no CLAUDE.md, hooks, skills, plugins or MCP servers.
    - `--strict-mcp-config`, `--disable-slash-commands`,
      `--no-session-persistence`.
    - No `--fallback-model`.
    - It runs in an empty private working directory.
    - `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` are removed from its
      environment, so the subscription login is used. Set
      `TAB_CLAUDE_CLI_KEEP_API_KEY=1` to keep them.
    - `--bare` is *not* used: it ignores OAuth logins.
  - **What is recorded.** Only what the CLI reports:
    - `usage` tokens (or `usage_available: false`);
    - the served model, taken from the `modelUsage` entry whose counts match
      `usage`;
    - the other `modelUsage` entries as `auxiliary_*`;
    - `total_cost_usd` as `cost_usd` with `cost_basis: provider_reported`.
      This is the CLI's list-price equivalent, including its side calls, not
      what a subscription is charged;
    - thinking tokens, turn count and CLI version in `provider_meta`, and the
      CLI's own timings under `provider_meta.latency_ms` (volatile).
  - **Failures.**
    - Not logged in, usage limit reached, executable missing, or an
      unsupported option: `ProviderUnavailable`. The runner then **stops the
      run** (status `failed`, outputs preserved), so the remaining steps are
      not run with degraded conditions that would make them incomparable.
    - Overload, timeout, an over-long reply or a malformed result: an
      ordinary provider error that the agent sees.
    - Failed calls are metered. If the CLI reported usage for a failed call
      (it often retries internally before failing), those tokens and that
      cost are counted. If it could not (a timeout, no JSON), the agent's
      meter turns `tokens_known`/`cost_known` false instead of claiming the
      call was free.
    - **Repeated failures stop the run.** After
      `MAX_CONSECUTIVE_PROVIDER_ERRORS` (3) consecutive provider failures
      across all lanes, the run is stopped. A provider that serves some
      steps and not others would make lanes incomparable.
    - **One model per run.** The first verified served model is pinned; for a
      full model id it must match the configured one. A different model on
      any later call stops the run. An alias such as `opus` is pinned to the
      full id that first serves it. When the CLI's output does not say which
      model served the call, the call is marked `model_verified: false`.
  - **Preflight.** `smoke-baseline-claude` first makes one tiny call
    (`claude-cli-check`) and refuses to start if it fails.
  - **Limitations compared with the API.**
    1. **Added context.** The CLI adds its own text to every request: an
       "Agent SDK" preamble, account reminders, and an environment block with
       the working directory, platform, model identity and **today's real
       date**. That date differs from the scenario's simulated timestamps.
       Measured at about 1.1–1.2k input tokens across probe calls (1,138 in
       the recorded preflight). It is identical for every contestant and
       contains nothing from the benchmark, but the prompt is not exactly the
       harness's.
    2. **No temperature control.** A temperature setting is rejected at
       configuration time.
    3. **No per-call output cap.** `CLAUDE_CODE_MAX_OUTPUT_TOKENS` is set
       only when the run configures `max_output_tokens`. The CLI then retries
       an over-long reply internally for several turns and finally *fails* it
       instead of truncating it. The tokens spent on those turns are metered
       (see Failures). The per-event output budget is enforced after the
       fact, and run records show `max_output_tokens: null`.
    4. **Stop sequences are emulated** by cutting the returned text.
    5. **Internal retries.** The CLI may retry inside one call; the reported
       usage includes the retries.
    6. **Limits and speed.** Subscription usage limits and rate limits apply,
       and the CLI starts one process per call, adding seconds of latency
       each time.
    7. **Approximate cost.** Cost is a list-price equivalent computed by the
       CLI, not a bill.
       - Prompt caching is always on (1-hour cache) and is managed by the
         CLI. `prompt_caching` cannot be set for this provider.
       - The cache is shared across lanes, across runs within the hour, and
         with the operator's other CLI use, so `cost_usd` depends on call
         order and history.
       - Every metering record therefore also carries `uncached_cost_usd`:
         every input token priced at the uncached rate. Use it, and the token
         totals (which include cache reads and writes), for cost comparisons
         between contestants.
       - Step 0 runs lanes in the same seeded order as events, so no lane is
         systematically the one that warms the cache.
    9. **Operator state.** The CLI runs with the operator's real `HOME` (that
       is where the login lives). `--no-session-persistence` and safe mode
       keep transcripts and memory out of it, but the CLI's own bookkeeping
       files may change. Behaviour-relevant environment variables
       (`CLAUDE_*`, `ANTHROPIC_*`, `MAX_THINKING*`, ...) are recorded in
       `metadata.model_runtime.behaviour_env`, with secret values redacted.
    8. **No temperature-0 determinism and no seeds.** Like the API, outputs
       vary between runs; replay uses the recording.

    For many repeated controlled runs, exact settings and cleaner metering,
    use the `anthropic` backend later; the protocol does not change.
- **Pricing.** A small table with a source date covers known model ids, and
  a dated id falls back to its undated entry. It can be overridden with
  `TAB_MODEL_PRICING` (JSON). An unknown model gives `cost_usd: null`.
  CLI-reported costs bypass the table. A replay uses the prices recorded in
  the original run, not the replaying shell's environment.
- **Retrieval tokens** are the contestant-*attributed* share of metered
  input: the gateway applies the request's self-declared `retrieval_chars` to
  the harness-measured total. The total is metered; only the split is
  attributed.
- **Equality.**
  - The gateway is created once per run from the run's `ModelSettings`.
  - A request cannot name a model, a temperature or a provider.
  - Every lane's metering records carry the same provider and requested
    model; the served model is recorded per call.

## 5. Tripwire (`harness/tripwire.py`)

An allowlist audit hook installed in a child process (contestant worker or
command bootstrap) before any untrusted code runs. See the module docstring.
It is a tripwire, not a sandbox.

## 6. Process boundary (`harness/process.py`, `harness/worker.py`, amendment A4)

```python
class ProcessAgent(Agent):
    isolation = "process"
    def __init__(self, name: str, *, kind: str, entry: str, config: dict,
                 packages: Sequence[str | Path], role: str = "contestant") -> None
    def describe(self) -> dict      # spawns a short-lived worker; {kind, role, config, isolation, entry, bundle_sha256}
    def setup(self, ctx) / on_start(self, tools) / on_event(self, event, tools) / teardown(self)
    def drain_notices(self) -> list[dict]   # lifecycle records for the trace (spawn, restart, timeout, exit)
    last_violations: list[str]              # tripwire refusals reported by the child for the last call
class StepTimeout(BaseException)            # the wall-clock budget ran out; the child was killed
class ContestantCrashed(Exception)          # the child exited unexpectedly
```

- **Bundle.** The proxy copies only the contestant-side modules (§1) and the
  contestant's packages into `<lane>/bundle/`, read-only. Their tree hash is
  part of `describe()` and therefore of the run id.
- **Spawn.** `[python, "-S", "-s", "-B", "-P", <bundle>/harness/worker.py, <rfd>, <wfd>]`.
  - `cwd` is the agent's `state_dir`; `start_new_session=True`.
  - stdin is `/dev/null`; stdout and stderr go to `<lane>/logs/` (copied into
    `final_state/<agent>/logs/`).
  - The environment is built from scratch: `HOME`/`TMPDIR`/`XDG_*` inside the
    state dir, `PYTHONHASHSEED=0`, `LANG=C.UTF-8`, `TZ=UTC`. It carries no
    credentials, no proxies and no `PYTHONPATH`.
- **Startup.** The worker does the following, in order:
  1. sets `sys.path` to the bundle plus the stdlib;
  2. reads an `init` message (entry point, name, config, allowlists);
  3. installs the tripwire: reads under the bundle and the stdlib, writes
     under the state dir, no network, processes or ctypes;
  4. imports the entry point, constructs the agent, and sends `ready`.
- **Calls** follow `harness/wire.py`. While a call is in progress the proxy
  services `tool` requests by calling the step's real `ToolBox`, so budgets,
  recording and metering are exactly as for in-process agents.
- **Wall clock.** `on_start`/`on_event` have `budget.wall_clock_s_per_event`
  (the runner gives the ToolBox the same deadline). `setup`/`teardown`/
  `describe` have 120 s.
  - On expiry the process group is killed and `StepTimeout` is raised; the
    step is recorded as `timeout`.
  - On unexpected exit `ContestantCrashed` is raised.
  - Before the next call the proxy spawns a fresh process and re-runs `setup`
    with `restart_count + 1`; the agent resumes from its persistent state.
- **Exceptions** raised in the child come back with their type name, message
  and child traceback. `BudgetExceeded` is re-raised as itself.
- **What it protects**:
  - no shared memory with the harness: ground truth, the evaluator and other
    agents live in another process;
  - no credentials or benchmark paths in the environment, argv or `sys.path`;
  - no benchmark code in the bundle;
  - a tripwire on file, network, process and ctypes access;
  - a hard wall-clock limit enforced from outside.
- **What it does not protect**:
  - It is not an OS sandbox. The child runs as the same user. Code that
    deliberately attacks its own interpreter (patching the hook's closure via
    `gc`, or a C extension that raises no audit events) can read any file the
    user can read and open network connections.
  - There is no memory or CPU isolation beyond rlimits and the wall clock.

  An OS-level sandbox (separate user, container, namespaces or an LSM) is
  needed before running untrusted contestant code.

## 7. Agent–LLM protocol (`tab.llm-protocol/1`, shared runtime)

The shared contestant runtime and the fake backend both implement this
protocol. It is text-only and provider-neutral: no provider tool-use API.

- **System prompt.** The harness instructions, then the runtime's rules, then
  a tool catalogue (one `- name(args): description` line per tool), then
  exactly one line `<<tools: name1, name2, ...>>`.
- **First user message of an event** starts with
  `<<event seq=N id=EVENT_ID>>`, followed by:
  - the event rendering (`Date:`, `Channel:`, `Author:`, `Subject:`,
    `Changed paths:` lines, a blank line, the body);
  - memory sections, each starting with `<<memory TITLE>>`.

  At step 0 the first user message starts with `<<start>>`.
- **Assistant replies** are exactly one JSON object, optionally fenced in
  ```` ```json ````:
  - `{"tool": NAME, "args": {...}}`
  - `{"final": {"actions": [ACTION...], "memory": "text to remember"}}`, where
    `ACTION` is
    `{"type": "reopen", "target", "rationale", "evidence": [ids], "historical_state": {"known_then", "true_then", "known_now_about_then"} | null}`
    or `{"type": "note", "text"}`.
- **Observations** are user messages starting
  `<<observation tool=NAME status=ok|error|denied|budget>>`. Protocol errors use
  `tool=protocol status=error`.
- **Auxiliary calls** set `ModelRequest.purpose`:
  - `query_expansion` expects `{"queries": [str]}`;
  - `summary` expects plain text;
  - the loop uses `purpose="loop"`.
- **Fake backend policy** (deterministic; for machinery checks only). Let `k`
  be the number of assistant turns in the request.
  - `k=0`: `memory_search` with the event's `Subject:` text (if offered).
  - `k=1`: `history` (if offered).
  - `k=2`: `diff(seq-1, seq)` if the event changed paths (if offered).
  - `k=3`: `run_command("pytest -q -x")` when `sha256(event_id) % 4 == 0` (if
    offered).
  - Otherwise `final`. The final answer reopens every `ADR-NNNN`/`TCK-NNNN`
    seen in observations or memory sections for which
    `sha256(f"{id}|{event_id}") % 7 == 0`. It cites the event and adds a
    `note`.

  For `query_expansion` it returns the subject's words. For `summary` it
  returns a deterministic digest. At `<<start>>` it returns `final` with no
  actions.

## 8. Shared contestant runtime (`contestant_runtime/`)

```python
class MemorySystem(ABC):
    def describe(self) -> dict
    def open(self, state_dir: Path, *, restart: bool) -> None
    def ingest_seed(self, tools) -> None
    def record_event(self, event: AgentEvent) -> None          # persists the raw event before anything else
    def observe_world(self, event, tools) -> None              # e.g. re-index changed paths
    def build_context(self, event, tools) -> ContextPack       # sections + retrieval_chars
    def local_tools(self) -> list[LocalTool]                   # memory tools offered to the model
    def after_event(self, event, outcome: EventOutcome, tools) -> None
    def checkpoint(self) -> None

class LLMAgent(Agent):  # memory-agnostic loop; contestants differ only in their MemorySystem
```

The loop gives the model, identically for every contestant:
- the harness instructions;
- the environment tools: workspace, history and `run_command`;
- the memory system's local tools and context;
- a bounded number of turns.

It turns `final` into `ReopenAction`/`NoteAction` and checkpoints after every
event. Model budgets are respected by asking for a final answer when calls
run low.

## 9. Baseline (`baseline/`)

A memory system with no temporal-causal machinery:

- **Raw event memory**: every received event is appended to `events.jsonl`
  before any processing. Nothing is available before it occurs.
- **Checkpoints**: atomic `checkpoint.json` plus append-only stores. On a
  restart the indexes are rebuilt deterministically from the stores.
- **Indexes**: events; workspace documents and code chunks (markdown by
  heading, Python by top-level definition, other files by size), re-indexed
  when an event changes them; the agent's own per-event notes.
- **Hybrid retrieval**: BM25 over code-aware tokens, plus dense vectors
  through `tools.embed`, plus an entity/metadata channel (ADR/TCK ids, file
  paths, versions). The channels are fused with reciprocal rank fusion, with
  a per-source diversity cap. Filters: kind, seq range, path. LLM query
  expansion (one call) generates extra queries.
- **Summary memory**: a rolling summary updated once per event from what was
  known then.
- **Configurations**: `baseline-k8`, `baseline-k32`, `baseline-k64` (top-k of
  the context pack and of `memory_search`), and `baseline-full`, the
  long-context condition with every event and note in context.
- **What it must not get**: ground truth, causal or trigger labels,
  `affected_targets`, future events, temporal fact graphs, or privileged
  mappings from new facts to old decisions. It rediscovers relevance through
  retrieval and reasoning.
