# Milestone 1 design: world, harness, evaluator

Status: implemented for Milestone 1 (`prompts/01_build_world.md`). No baseline
or Tesseract code is part of this milestone. Everything here is benchmark
infrastructure and must not encode knowledge about how any contestant works.

Examples in this document use synthetic ids (`ADR-9001`, `evt-9001`). Real
scenario answers live only in `world/ground_truth/`.

---

## 1. Directory layout

```
world/
  seed_repo/                      # "tasklane" seed application (copied into each agent workspace)
  events/<scenario_id>/
    events.jsonl                  # tab.event/1, one event per line, chronological
    payloads/<event_id>/...       # file bodies referenced by world_changes[].source
  ground_truth/<scenario_id>/     # EVALUATOR ONLY
    labels.json                   # tab.ground_truth/1
    CANARY                        # per-scenario canary string (also embedded in every commentable GT file)
    hidden_tests/test_*.py        # behavioural remediation tests
    reference/<R-id>/...          # reference remediations (oracle only)
scenarios/<family>/<scenario_id>.json   # tab.scenario/1 manifest (harness-side only)
src/harness/                      # runner, world engine, agent interface, tools, guard, trace, replay, CLI
src/harness/agents/               # non-contestant reference agents: dummy (no-op), keyword
src/evaluation/                   # ground truth, scoring, remediation checks, oracle, scenario validation
runs/<run_id>/                    # generated; never overwritten or deleted by the harness
```

Only `evaluation.ground_truth` reads `world/ground_truth/`. Contestant-facing
modules (`harness.agent`, `harness.tools`, `harness.workspace`,
`harness.canonical`, `harness.agents.*`, `baseline`, `tesseract`) never import
`evaluation`, `harness.runner`, `harness.scenario`, `harness.events`,
`harness.world`, `harness.replay` or `harness.cli` (AST-enforced).

## 2. Seed world: `tasklane`

A standard-library-only Python 3.11 team task tracker with paid plans:
settings (`config/settings.json`), SQLite persistence with ordered SQL
migrations, PBKDF2 auth with sessions and rehash-on-login, plans and
entitlements, a PayGate payment-provider abstraction over a vendored SDK with
an in-memory sandbox, a SQLite-backed job queue with a self-healing
subscription-reconciliation job, platform facts (`infra/platform.json`),
ADRs (`docs/adr/`), and a pytest suite. See `world/seed_repo/README.md`.

Decisions a scenario bears on are world-authored (seed ADRs, or ADRs/tickets
delivered by events), so ground truth never depends on contestant-generated
artifacts.

## 3. Event format `tab.event/1`

`events.jsonl`, one JSON object per line, strict keys:

| key | type | notes |
|---|---|---|
| `schema_version` | `"tab.event/1"` | |
| `event_id` | `evt-NNNN` | unique |
| `seq` | int | 1..N, contiguous, equal to line order |
| `timestamp` | `YYYY-MM-DDTHH:MM:SSZ` | arrival time; non-decreasing |
| `channel` | enum | `ticket`, `chat`, `email`, `commit`, `changelog`, `notice`, `support` |
| `author`, `subject`, `body` | str | natural prose; never "revisit decision X" |
| `world_changes` | list | ordered ops, may be empty |

Ops: `write_file` (`content` or `source` under `payloads/`) and `delete_file`,
each with an optional `expect_sha256` precondition. The world is
authoritative: a failed precondition is applied anyway and recorded as a
conflict. There is deliberately no semantic kind, validity time, or causal
field on events; classification lives only in ground truth.

Contestants receive an `AgentEvent`: the fields above minus `world_changes`,
plus `changed_paths` (sorted `{op, path}` list, like a commit's file list).
World changes are applied to the agent's workspace before delivery.

## 4. Agent interface (`tab.action/1`)

```python
class Agent(ABC):
    def setup(self, context: AgentContext) -> None: ...
    def on_start(self, tools: ToolBox) -> None: ...          # optional seed ingestion (step 0)
    def on_event(self, event: AgentEvent, tools: ToolBox) -> AgentResponse: ...
    def teardown(self) -> None: ...
    def describe(self) -> dict: ...                          # {kind, role, config} -> metadata + run id
```

`AgentContext`: `agent_name`, `seed`, `state_dir` (private, persistent, outside
the workspace and the repository; also the working directory during every
agent call), `budget`, `model` (shared model-settings placeholder),
`instructions` + `instructions_version` (harness-owned task text, identical
for every agent, hashed into run metadata). The scenario's identity is not
exposed.

`ToolBox` (identical for every agent, budgeted per step, every call traced):
`list_files`, `read_file`, `write_file` (atomic, new inode), `delete_file`,
`search` (regex). Arguments must be strings. A ToolBox is closed when its step
ends. There is no command execution in Milestone 1.

Path rules: no absolute paths, `~`, drive letters, NUL, backslashes, or `..`
segments; no symlink anywhere along the path; nothing resolving outside the
workspace or into a protected root (ground truth, events, scenarios, runs);
listing and search never follow links.

**Guard** (`harness.guard`): during every agent call a Python audit hook
refuses direct filesystem access to protected roots, to every workspace (use
the ToolBox) and to other agents' state, and refuses subprocess creation.
This prevents accidental out-of-band access (e.g. an indexer walking the
repository). It is a tripwire, not a sandbox against hostile code in the same
process (see §10).

`AgentResponse`: `actions` + `usage`. Actions:

- `reopen`: `{target, rationale, evidence: [event_id], historical_state?}`.
  `target` is canonicalized (`adr-1` → `ADR-0001`); decisions are `ADR-*`,
  parked or blocked work items `TCK-*`. `historical_state` holds the
  EXPERIMENT.md §11 triple, `known_then`, `true_then` and
  `known_now_about_then`, each a list of event ids or `"seed"`.
- `note`: free text, never scored.

`Usage` (self-reported placeholders in Milestone 1): `model_input_tokens`,
`model_output_tokens`, `retrieval_tokens`, `model_calls`, `cost_usd`.

Failure semantics: if a call raises, the step's actions are lost but tool
edits persist. `BudgetExceeded` is a `BaseException`. If an agent catches it,
the step is still recorded as `budget_exceeded` and the returned actions are
kept.

## 5. Ground truth `tab.ground_truth/1`

```json
{
  "schema_version": "tab.ground_truth/1",
  "scenario_id": "example_v1",
  "canary": "TAB-GT-CANARY-...",
  "targets": {"ADR-9001": {"kind": "decision", "introduced_by": "evt-9002", "decided_on": "2026-01-02", "summary": "..."}},
  "events": {"evt-9001": {"role": "distractor", "should_trigger_reconsideration": false,
                          "near_miss_of": null, "acceptable_reopens": [], "notes": "..."}},
  "reconsiderations": [{
    "id": "R1", "pattern": "C", "trigger_event": "evt-9005",
    "affected_targets": ["ADR-9001"],
    "window": {"from_seq": 5, "to_seq": 7},
    "abstention_acceptable": false,
    "evidence_locus": "workspace",
    "causal_path": [{"ref": "evt-9005", "kind": "event", "note": "..."}, {"ref": "ADR-9001", "kind": "decision", "note": "..."}],
    "historical_state": {"known_then": ["evt-9002"], "true_then": ["evt-9005"], "known_now_about_then": ["evt-9005"]},
    "remediation": {
      "evaluate_at_seq": 7,
      "acceptable": [{"id": "...", "checks": [{"type": "hidden_pytest", "files": ["hidden_tests/test_r1.py"]}]}],
      "reference": [{"op": "write_file", "path": "...", "source": "reference/R1/..."}]
    },
    "difficulty": {"causal_depth": 1, "temporal_lag": "medium", "lag_events": 3, "lag_days": 47, "wording": "natural"}
  }]
}
```

- **Roles:** `distractor`, `decision_setup`, `parked_setup`, `trigger`.
  `should_trigger_reconsideration` is true exactly for triggers.
- **Patterns:** EXPERIMENT.md §4 letters A–G.
- **`acceptable_reopens`:** reopens that are defensible at that event but not required. They are scored `neutral`.
- **`evidence_locus`:** where the decisive premise lives: `workspace`, `event_history` or `mixed`.
- **Difficulty labels are derived and enforced, not trusted:**
  - `causal_depth` is the index of the first affected target in `causal_path`, which must start at the trigger.
  - `lag_events` is the trigger seq minus the seq that introduced the target (seed = 0).
  - `temporal_lag` buckets: near ≤ 2 events, medium ≤ 6, far > 6.
  - `lag_days` is the trigger date minus `decided_on`.
- **`historical_state` rules:**
  - `known_then` items are at or before the decision.
  - `known_now_about_then` items are after the decision and no later than the trigger.
  - `true_then` items are known by the trigger.
- **Checks:** `file_exists`, `file_absent`, `file_regex`, `json_value`, and `hidden_pytest` (§6).

Every ground-truth file referenced by a reconsideration is read into memory
once, when the run starts, right after the content hashes are verified.

## 6. Scoring `tab.scores/1`

The runner reports actions to the evaluator only after every agent has
completed the step. Workspaces due for remediation are snapshotted then,
copying regular files only into evaluator-private storage. **All remediation
checks run after every agent has been torn down.**

Classification of a reopen of `t` at step `s`:

| class | rule | precision | false-intervention rate |
|---|---|---|---|
| `true_positive` | `t` affected by R and `s` in R's window (first match per `(R,t)`) | numerator | no |
| `duplicate` | repeat of a matched `(R,t)` in-window | excluded | no |
| `neutral` | `t` in the event's `acceptable_reopens`, or `t` introduced by this event | excluded | no |
| `late` | `t` affected by an R whose window closed | denominator | no |
| `false` | invalid/unknown target, before the evidence, or unrelated | denominator | yes |

Metrics (each ratio is `{value, numerator, denominator}`, with `value: null` when the denominator is 0):

- **Temporal governance recall:** matched required `(R, t)` pairs over all required pairs. Reconsiderations with `abstention_acceptable` are excluded.
- **Reopening precision:** TP / (TP + late + false).
- **False intervention rate:** negative-control events with at least one `false` reopen, over all negative-control events. Also reported for distractors only.
- **Historical-state fidelity:** for each TP, the mean set-F1 over the three components, where two empty sets count as 1.0. A TP without `historical_state` scores 0. Also reported: coverage, and per-component means when the state is provided.
- **Present remediation success:** required reconsiderations whose remediation passes, over required reconsiderations with checks. Also reported: success given that all targets were reopened, optional successes, and `remediated_without_reopen`.
- **Detection latency:** steps from the trigger to each TP.
- **Efficiency:** summed usage, tool calls and wall-clock (volatile).
- **Hygiene:** whether the agent's own test suite passes on its final workspace. This is reported separately and is not part of remediation.
- **Breakdowns:** by pattern, causal depth, temporal lag, wording and evidence locus. Scenario-level axes are copied from the manifest.
- **Per-item tables:** per reconsideration, per event, and the full reopen log.
- **Reserved, not scored in Milestone 1:** `topology_integrity` and `false_memory_rate`.

**`hidden_pytest`** runs in a fresh interpreter (`python -P -s -B`) with an
environment built from scratch:
- pytest is imported before the snapshot is *appended* to `sys.path`;
- an evaluator-owned ini and `--noconftest` apply;
- plugin autoload is disabled;
- hidden tests are materialized from memory into a directory outside the snapshot.

A check passes only if the JUnit report shows exactly the expected number of
hidden test cases and all of them passed.

## 7. Scenario manifest `tab.scenario/1`

Fields: `scenario_id`, `family`, `version`, `status` (`draft`|`frozen`),
`held_out`, `description`, `base_dir`, paths to the seed, events and ground
truth, `difficulty` (`history_length`, `distractor_density`), `budgets`,
`content_hashes`, and `world_state_hashes`.

`content_hashes` covers:
- the seed tree;
- the events directory;
- the ground-truth directory;
- the manifest itself, minus its status and hash fields, so budgets and labels are frozen too.

`world_state_hashes` is the workspace tree hash after each event of a
world-only replay.

Rules:
- The harness refuses to run a frozen scenario whose hashes differ. It also re-checks them at run end; a change during the run gives status `integrity_failed`.
- Contestants (`role: contestant`) may only run on frozen scenarios.
- `freeze` refuses to re-freeze changed content; a change needs a new scenario id/version.

Tree hashing is sha256 over the sorted `(relative path, sha256(bytes))` pairs.
`__pycache__`, `*.pyc` and `.pytest_cache` are ignored, symlinks hash their
target string, and special files are never opened.

**Validation** (`python -m harness validate`) checks:
- loading and cross-validation;
- the wording lint: no reconsideration verbs next to decision references, no affected target named in a non-explicit trigger, no temporal-contestant vocabulary;
- the canary: present in every commentable ground-truth file and absent everywhere else;
- at least 50% distractors;
- no world change touching a reconsideration's remediation paths inside its window;
- the seed test suite staying green after every event of a world-only replay;
- the oracle scoring perfectly and the dummy passing no remediation.

## 8. Runner and outputs

The protocol, per EXPERIMENT.md §9:
1. `setup`, then `on_start` (step 0).
2. For each event:
   - apply it to every isolated world;
   - deliver it to each agent, in a seeded per-step order that is recorded in the trace;
   - after every agent has finished, classify actions and snapshot due workspaces.
3. `teardown`.
4. Evaluate remediation and score.

Each agent gets its own temporary lane directory (`workspace/`, `state/`)
outside the repository. Absolute host paths in error text are redacted to
placeholders (`<state:NAME>`, `<repo>`, ...).

`run_id = <scenario_id>__<agent names joined by '+'>__<config_hash[:10]>`.

`config_hash` covers:
- scenario content hashes;
- agent descriptions;
- seed, budget and model settings;
- instructions hash;
- harness/evaluator versions and **code hashes**;
- Python and pytest versions.

Existing run directories are never modified. A rerun gets `__2`, `__3`, and so on.

```
runs/<run_id>/
  metadata.json      # status (running|completed|failed|aborted|integrity_failed), last_completed_seq,
                     # versions, code_hashes, environment, scenario hashes, agents, config, fingerprint
  events.jsonl       # per event: the AgentEvent as delivered + world application summary + conflicts
  actions.jsonl      # per (event, agent): actions, tool-call summary, usage (token/cost placeholders), status
  trace.jsonl        # contestant-observable replay trace (tab.trace/1)
  evaluation.jsonl   # evaluator-only: per-step reopen classification and snapshot records
  scores.json        # tab.scores/1
  blobs/<sha256>.json  # content-addressed tool results and delivered events
  final_state/<agent>/{workspace,state}/   # preserved on success *and* failure
  MANIFEST.sha256    # sha256 of every file in the run directory
```

`trace.jsonl` records each carry an `idx`. The record types are:
- `run_start`, `agent_setup` and `agent_start`;
- `world_event_applied` (with tree hashes before and after);
- `out_of_band_mutation`, emitted if a workspace changed outside any step;
- `step_order` and `event_delivered`;
- `tool_call` (full arguments, status and result hash);
- `agent_response` (with `guard_violations`);
- `step_complete` (workspace and state tree hashes), `agent_teardown` and `run_end`.

JSONL records are flushed and fsynced one at a time. JSON files are written
atomically.

`fingerprint` is the sha256 of the canonical content of events, actions,
trace, evaluation and scores, with volatile keys (`wall_clock_ms`,
`started_at`, `finished_at`, `traceback`, `host`, `git`) removed. The same
inputs give the same fingerprint, regardless of temp dirs or hash seed.

`replay <run_dir>` re-runs the scenario with a `ReplayAgent` per agent. Each
one re-issues the recorded tool calls and returns the recorded actions,
reproducing failures. The replay goes to `<run_id>__replay` and is compared
record by record with the original. Private state (`state_tree`) is exempt,
and the report flags differing code hashes.

## 9. Reference agents

- **`dummy`:** no memory and no actions; the null floor.
- **`keyword`:** no memory; reopens any `ADR-NNNN`/`TCK-NNNN` mentioned in the current event. It is a *diagnostic* for ID-level surface matching, reported per scenario, not a gate on scenario wording.
- **Oracle** (`evaluation.oracle`): built from ground truth to prove a scenario is solvable. It is never registered as a contestant.

## 10. Known limitations and deviations (Milestone 1)

- **Process isolation:** contestants run in the harness process. The guard prevents accidental access only. A subprocess or sandbox boundary, enforced wall-clock limits, and protection against deliberate forgery by code under test are prerequisites for real contestants.
- **Command execution:** none in the ToolBox, so agents cannot run tests. Remediation is judged by hidden behavioural tests, and suite health is reported separately as hygiene.
- **Usage metering:** usage is self-reported. A harness-metered model client is deferred to the milestone that adds LLM contestants.
- **VCS history:** no git log/diff tool is offered. This is an open protocol decision, because adding one later changes the shared tool set.
- **Recall granularity:** recall is computed over `(reconsideration, target)` pairs, not over decisions.
- **Historical-state fidelity:** scored at event-id granularity; there is no fact inventory yet.
- **Smoke scenario coverage:** `smoke_v1` is a machinery check (`held_out: false`). Its reconsiderations are all `natural` wording, so the explicit and indirect wording levels are not covered.
- **Lexical shortcuts:** no BM25 shortcut agent exists yet. `keyword` only detects ID matches.
