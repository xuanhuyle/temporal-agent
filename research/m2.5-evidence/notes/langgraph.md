# LangGraph persistence / time travel: primary-source notes

Analyst notes, 2026-10-03. Scope: LangGraph checkpointing, state history, replay, `update_state`, forks and subgraph checkpointing, rated against the temporal-agency capability list.

## 0. Sources and how I got them

| Source | How obtained | Version |
|---|---|---|
| `langchain-ai/langgraph` | `git clone --depth 1 https://github.com/langchain-ai/langgraph.git` into `scratchpad/lit/repos/langgraph` | commit `7dc9195e4141c8fbd8118581b3dd61d158628aa8` (2026-10-02). `libs/langgraph/pyproject.toml:7` gives `version = "1.2.12"`. Installed `langgraph-checkpoint` reports 4.2.0. |
| `langchain-ai/docs` | `git clone --depth 1 https://github.com/langchain-ai/docs.git` into `scratchpad/lit/repos/langchain-docs` | commit `6d6080f536bb0c2885a7cfa44abf0933cdb85b4c` (2026-10-03) |
| Empirical probes | Editable install of the cloned libs (`libs/checkpoint`, `libs/prebuilt`, `libs/langgraph`) into a venv at `scratchpad/lit/lgvenv` with Python 3.11. I ran four scripts. | Scripts and outputs are in `scratchpad/lit/verify/langgraph_probe{,2,3,4}.py` and `.out`. |

I did not use WebSearch or any paper. LangGraph has no paper; its primary sources are the code and the docs. docs.langchain.com is blocked, so all doc quotes come from the docs git repo (`src/...mdx`).

In this file, paths shortened as `pregel/...` are relative to `repos/langgraph/libs/langgraph/langgraph/`. Paths shortened as `checkpoint/base/...` are relative to `repos/langgraph/libs/checkpoint/langgraph/`. Doc paths are relative to `repos/langchain-docs/src/`.

---

## 1. What a checkpoint contains

### 1.1 The `Checkpoint` TypedDict (`checkpoint/base/__init__.py:93-124`)
```python
class Checkpoint(TypedDict):
    """State snapshot at a given point in time."""
    v: int
    id: str
    """The ID of the checkpoint.
    This is both unique and monotonically increasing, so can be used for sorting
    checkpoints from first to last."""
    ts: str
    channel_values: dict[str, Any]
    """The values of the channels at the time of the checkpoint. ..."""
    channel_versions: ChannelVersions
    """... monotonically increasing version strings for each channel."""
    versions_seen: dict[str, ChannelVersions]
    """Map from node ID to map from channel name to version seen.
    This keeps track of the versions of the channels that each node has seen.
    Used to determine which nodes to execute next."""
    updated_channels: list[str] | None
```
- `pending_sends` is no longer a field. In format v4 (`pregel/_checkpoint.py:23`, `LATEST_VERSION = 4`), pending sends are migrated into the `TASKS` channel (`pregel/main.py:1194-1201`, `_migrate_checkpoint`).
- `create_checkpoint` (`pregel/_checkpoint.py:149-214`) builds each checkpoint from live channels using `ch.checkpoint()`. It assigns a new id with `uuid6(clock_seq=step)` (line 209).
- The checkpoint id is the sort key for "latest" and for history order.

### 1.2 `CheckpointMetadata` (`checkpoint/base/__init__.py:39-87`)
```python
source: Literal["input", "loop", "update", "fork"]
    - "input": The checkpoint was created from an input to invoke/stream/batch.
    - "loop": The checkpoint was created from inside the pregel loop.
    - "update": The checkpoint was created from a manual state update.
    - "fork": The checkpoint was created as a copy of another checkpoint.
step: int   # -1 for the first "input" checkpoint, 0 for the first "loop" checkpoint
parents: dict[str, str]
    """The IDs of the parent checkpoints. Mapping from checkpoint namespace to checkpoint ID."""
run_id: str
counters_since_delta_snapshot: dict[str, tuple[int, int]]   # Beta, DeltaChannel
```
- **`parents` is not the same-thread parent.** In the loop it is set to the config's `checkpoint_map` (`pregel/_loop.py:1101-1102`): `metadata["step"] = self.step` and `metadata["parents"] = self.config[CONF].get(CONFIG_KEY_CHECKPOINT_MAP, {})`. That map holds the checkpoint ids of the enclosing graphs, keyed by namespace. Root-graph checkpoints showed `parents={}` in probe 1. Subgraph checkpoints showed `parents {'': '<parent-graph checkpoint id>'}` in probe 1.
- **The same-namespace parent is stored separately**, as `parent_checkpoint_id`. `InMemorySaver.put` stores `config["configurable"].get("checkpoint_id"),  # parent` (`checkpoint/memory/__init__.py:450-457`). The Postgres schema has a `parent_checkpoint_id TEXT` column (`checkpoint-postgres/.../base.py:47-56`). It is exposed as `CheckpointTuple.parent_config` (`checkpoint/base/__init__.py:140-147`) and as `StateSnapshot.parent_config`.
- **Extra metadata comes from the config.** `get_checkpoint_metadata` (`checkpoint/base/__init__.py:758-776`) copies every str/int/bool/float key from `config["metadata"]` and `config["configurable"]` into the metadata. Keys starting with `__` and the keys in `EXCLUDED_METADATA_KEYS` (lines 798-808) are skipped. Probe 4: `configurable={"model_name": "model-A", "system_prompt_version": 3}` produced head metadata `{'source': 'loop', 'step': 2, 'parents': {}, 'model_name': 'model-A', 'system_prompt_version': 3}`. The fork checkpoint created by `update_state` did **not** carry those keys: `{'source': 'update', 'step': 2, 'parents': {}}`.
- **`run_id`** only appears when `config["metadata"]["run_id"]` is set. A plain `invoke(..., {"run_id": uuid})` did not record it (probe 2).
- **`writes` is not in the metadata.** The docs examples still show it (`oss/langgraph/checkpointers.mdx:244, 293, 345`), but `get_serializable_checkpoint_metadata` pops `"writes"` (`checkpoint/base/__init__.py:784-785`). Probe 1 shows `meta_keys=['parents', 'source', 'step']`. **This doc/code discrepancy is resolved in favour of the code.**
- The docs' StateSnapshot table lists `source` as `"input"`, `"loop"`, or `"update"` and omits `"fork"` (`checkpointers.mdx:293`). The code and probe 1 both produce `"fork"`.

### 1.3 Pending writes and the tuple (`checkpoint/base/__init__.py:32, 140-147, 301-319, 796`)
```python
PendingWrite = tuple[str, str, Any]
class CheckpointTuple(NamedTuple):
    config: RunnableConfig
    checkpoint: Checkpoint
    metadata: CheckpointMetadata
    parent_config: RunnableConfig | None = None
    pending_writes: list[PendingWrite] | None = None
...
WRITES_IDX_MAP = {ERROR: -1, SCHEDULED: -2, INTERRUPT: -3, RESUME: -4}
```
Docs (`oss/langgraph/checkpointers.mdx:67`):
> "As each node within a super-step finishes, its outputs are written to the checkpointer's `checkpoint_writes` table as task entries linked to the in-progress checkpoint. These per-task writes are what enable pending writes recovery ... The full state snapshot is then committed once the super-step completes."

Docs (`checkpointers.mdx:735-736`):
> "**Checkpoints table** — one row per superstep; stores the serialized graph state (`channel_values`, `channel_versions`, `versions_seen`) and links to its parent checkpoint. **Writes table** — one row per node output within a superstep; stores `(task_id, channel, value)` tuples linked to a checkpoint."

Probe 1 shows the raw contents of the checkpoint taken before node `act`:
```
RAW checkpoint keys: ['channel_values', 'channel_versions', 'id', 'ts', 'updated_channels', 'v', 'versions_seen']
RAW channel_values: {'goal': 'g', 'log': ['plan'], 'plan': 'plan-609912', 'branch:to:act': None}
RAW versions_seen: {'__input__': {}, '__start__': {...}, 'plan': {'branch:to:plan': '...2...'}}
RAW metadata: {'source': 'loop', 'step': 1, 'parents': {}}
RAW pending_writes: [('61d368d9-...', 'log', ['act:plan-609912'])]   # output of the NEXT step's task (act)
```
So the pending writes stored on checkpoint *k* are the task outputs of the super-step that started from *k*. Pending writes do **not** record the node name; tuples are `(task_id, channel, value)`. Task ids are deterministic hashes of the checkpoint id, namespace, step, node name and triggers (`pregel/_algo.py:615-624`).

### 1.4 StateSnapshot, the user-facing view (`pregel/../types.py:711-735`, `pregel/main.py:1203-1326`)
Fields: `values, next, config, metadata, created_at, parent_config, tasks, interrupts`. `PregelTask` (`types.py:665-674`) holds `id, name, path, error, interrupts, state, result`.

The `_prepare_state_snapshot` docstring (`main.py:1212-1218`):
> "With `live=True` the snapshot shows current status ... Otherwise the snapshot is a record of the step: values as of the start of the step, every task in the step, and the interrupts they raised."

`live` is True only when no `checkpoint_id` is given (`main.py:1476`).

### 1.5 Granularity
Docs (`checkpointers.mdx:65`):
> "LangGraph creates a checkpoint at each **super-step** boundary ... you can only resume execution from a checkpoint (i.e., a super-step boundary)."

Docs (`checkpointers.mdx:69`):
> "These task writes are not full `StateSnapshot` checkpoints, so time travel resumes from full checkpoints at super-step boundaries."

Durability modes (`checkpointers.mdx:603`):
> "`"exit"`: LangGraph persists changes only when graph execution exits ... intermediate state is not saved"

---

## 2. Replay (invoke with a past `checkpoint_id`)

### Docs
`oss/langgraph/use-time-travel.mdx:14`:
> "Both work by resuming from a prior checkpoint. Nodes before the checkpoint are not re-executed (results are already saved). Nodes after the checkpoint re-execute, including any LLM calls, API requests, and interrupts (which may produce different results)."

`use-time-travel.mdx:20-24`:
> "Replay re-executes nodes—it doesn't just read from cache. LLM calls, API requests, and interrupts fire again and may return different results. Replaying from the final checkpoint (no `next` nodes) is a no-op."

`use-time-travel.mdx:216`:
> "interrupts are always re-triggered during time travel. The node containing the interrupt re-executes, and `interrupt()` pauses for a new `Command(resume=...)`."

`langsmith/human-in-the-loop-time-travel.mdx:6`:
> "In all cases, resuming past execution produces a new fork in the history."

### Code
- `pregel/_loop.py:316`: `self.is_replaying = CONFIG_KEY_CHECKPOINT_ID in config[CONF]`
- `_loop.py:1609-1613` (in `__enter__`): `elif self.checkpoint_config[CONF].get(CONFIG_KEY_CHECKPOINT_ID): # Explicit checkpoint_id requested — fetch that exact checkpoint.` followed by `saved = self.checkpointer.get_tuple(self.checkpoint_config)`
- `_loop.py:662-665` (`tick`): `if not self.is_replaying and self.checkpoint_pending_writes: self._reapply_writes_to_succeeded_nodes(self.tasks)`. While replaying, writes already stored for completed tasks are **not** reused, so those tasks run again.
- `_loop.py:716-717` (`after_tick`): `# only replay (re-execute) done tasks on the first tick` followed by `self.is_replaying = False`
- `_loop.py:850-876`: time travel drops cached RESUME writes.
  ```python
  # When replaying from a specific checkpoint, drop cached RESUME
  # writes so that interrupt() calls re-fire instead of returning
  # stale values. ...
  if is_time_traveling:
      self.checkpoint_pending_writes = [w for w in self.checkpoint_pending_writes if w[1] != RESUME]
  ```
- `_loop.py:928-947`: time travel first writes a fork checkpoint.
  ```python
  # When time-traveling (replaying from a specific checkpoint),
  # save a fork checkpoint so the replayed execution creates a
  # new branch. ...
  if is_time_traveling and self.checkpoint_metadata.get("source") not in ("update","fork"):
      self.checkpoint_pending_writes = [w for w in self.checkpoint_pending_writes if w[1] != INTERRUPT]
      self._put_checkpoint({"source": "fork"})
  ```
- **Optional node cache.** Cache keys are computed from the node *input* through `cache_policy.key_func(val)` (`pregel/_algo.py:668-687`). `match_cached_writes` runs on every tick, replay included (`main.py:2911-2913`). So with `CachePolicy` and a `cache=` configured, a replayed node whose input is unchanged returns the cached output.

### Probe evidence (probe 1 and probe 2 outputs)
```
CALLS after run {'plan': 1, 'act': 1} EXTERNAL {'file_written': ['plan-609912']}
CALLS after replay-before-act {'plan': 1, 'act': 2} EXTERNAL {'file_written': ['plan-609912', 'plan-609912']}   # side effect duplicated
CALLS after replay-before-plan {'plan': 2, 'act': 3} ...  replay2 plan: plan-32779 original plan: plan-609912     # nondeterministic output NOT reused
history: ... id=..27fa59 parent=..c5056b src=fork step=2 next=('act',) ...   # replay starts with a src=fork checkpoint whose parent is the replayed checkpoint
original before_act values unchanged: True
interrupt replay output: {'v': [], '__interrupt__': [Interrupt(value='name?', ...)]} ask calls: 3   # interrupt re-fired
with node cache: calls {'llm': 1} same answer on replay: True    # opt-in cache short-circuits re-execution
```
The repo's own tests encode the same contract: `libs/langgraph/tests/test_time_travel.py` (3966 lines). Examples are `test_replay_reruns_nodes_after_checkpoint` (line 69), `test_replay_from_final_checkpoint_is_noop` (line 112), `test_multiple_forks_from_same_checkpoint` (line 182) and `test_replay_from_before_interrupt_refires` (line 226).

### "Replay" means two different things in LangGraph
- **Resume** continues the same branch after an interrupt or failure. It *does* reuse stored results: pending writes of tasks that succeeded, and completed Functional-API `@task` results.
  - `functional-api.mdx:793`: "replay starts at the beginning of the entrypoint while LangGraph restores completed task and subgraph results from the checkpointer instead of recomputing them."
  - `checkpointers.mdx:29`: "When you resume graph execution from that super-step you don't re-run the successful nodes."
- **Time-travel replay** (an explicit past `checkpoint_id`) re-executes.
- Inside a node, both kinds re-run the node from its start. `graph-api.mdx:772`: "the affected node runs again from the start of its function. Code and side effects before the pause run again."

---

## 3. `update_state` and fork semantics

### Docs
`use-time-travel.mdx:125`:
> "Fork creates a new branch from a past checkpoint with modified state. Call `update_state` on a prior checkpoint to create the fork, then `invoke` with `None` to continue execution."

`use-time-travel.mdx:129-133`:
> "`update_state` does **not** roll back a thread. It creates a new checkpoint that branches from the specified point. The original execution history remains intact."

`use-time-travel.mdx:176-184`:
> "When you call `update_state`, values are applied using the specified node's writers (including reducers). The checkpoint records that node as having produced the update, and execution resumes from that node's successors. By default, LangGraph infers `as_node` from the checkpoint's version history ... Specify `as_node` explicitly when: Parallel branches ... (`InvalidUpdateError`) ... No execution history ... Skipping nodes: Set `as_node` to a later node to make the graph think that node already ran."

`checkpointers.mdx:566`:
> "This creates a new checkpoint with the updated values — it does not modify the original checkpoint. The update is treated the same as a node update: values are passed through reducer functions when defined"

### Code (`pregel/main.py`)
- `update_state` (2473-2484) wraps `bulk_update_state(config, [[StateUpdate(values, as_node, task_id)]])`.
- `perform_superstep` (1621-2026) does the following:
  - It loads the saved checkpoint for the given config and copies it (1628-1636).
  - It sets `checkpoint_config = patch_configurable(config, saved.config[CONF])` (1647-1648), so the new checkpoint's parent is the *source* checkpoint.
  - It infers `as_node` (1884-1917): `last_seen_by_node = sorted((v, n) for n, seen in checkpoint["versions_seen"].items() ...)`. If two nodes tie, it raises `InvalidUpdateError("Ambiguous update, specify as_node")`.
  - It runs the chosen node's **writers** (not the node function) on the supplied values (1932-1978).
  - **It writes the update's task writes onto the SOURCE checkpoint** (1980-1986):
    ```python
    if saved is not None:
        for task_id, task in zip(run_task_ids, run_tasks):
            channel_writes = [w for w in task.writes if w[0] != PUSH]
            if channel_writes:
                checkpointer.put_writes(checkpoint_config, channel_writes, task_id)
    ```
  - It saves the new checkpoint with metadata from `create_checkpoint_plan_for_update_state_api`: `{"source": "update", "step": step + 1, "parents": ...}` (2014-2021, `_checkpoint.py:127-131`).
- Special `as_node` values:
  - `as_node == END` with `values=None` clears all pending tasks (1657-1723).
  - `as_node == INPUT` acts as a new input and gets `source="input"` (1726-1776).
  - `as_node == "__copy__"` copies the checkpoint with `source="fork"` and puts it under `saved.parent_config`, which makes it a *sibling* (1778-1857). Probe 2 output: `copy src {'source': 'fork', 'step': 1, 'parents': {}} copy parent 0d647b mid parent 0d647b`.
- After a fork, the next run with `checkpoint_id` (`invoke(None, fork_config)`) uses `ReplayState(prev_checkpoint_id)` for subgraphs (`_loop.py:1029-1050`).

### Probe evidence (probe 1)
```
--- fork checkpoint
id=..b2970d parent=..c5056b src=update step=2 next=('act',) plan=HUMAN-EDITED
fork parent == before_act: True
latest == fork: True                         # the fork becomes the thread head
pending writes on SOURCE checkpoint before/after update_state: 1 3 [ ..., ('7e3aa248-...', 'plan', 'HUMAN-EDITED'), ('7e3aa248-...', 'branch:to:act', None)]
fork metadata: {'source': 'update', 'step': 2, 'parents': {}}   # no explicit as_node, no reason
```
Probe 4: after `update_state(..., as_node="gen")`, `versions_seen` was identical on the fork and the original. The `as_node` choice is not recorded as an explicit field anywhere in the new checkpoint's metadata. It survives only implicitly, through which channels the node's writers wrote (for example `branch:to:write`) and through the task writes appended to the source checkpoint.

---

## 4. History listing and querying

- `get_state_history` (`main.py:1504-1542`) calls `checkpointer.list(config, before=before, limit=limit, filter=filter)` and yields a `StateSnapshot` for each result.
- `InMemorySaver.list` (`checkpoint/memory/__init__.py:347-374`) sorts by checkpoint_id in descending order. `before` is a checkpoint-id comparison (`checkpoint_id >= before_checkpoint_id` → skip). `filter` is equality on metadata keys.
- Docs (`checkpointers.mdx:926`): "Return checkpoints for a thread, newest first. Respect `before` ... and `limit`."
- **History is not branch-scoped.** All checkpoints in a (thread, namespace) are interleaved by id across branches. Probe 1, after two replays, listed nine checkpoints from three branches mixed together. To follow one lineage you have to walk `parent_config` yourself.
- SDK `threads.get_history(thread_id, limit, before, metadata, checkpoint)` (`libs/sdk-py/langgraph_sdk/_async/threads.py:687-735`) has the same shape.
- No API exists for state diffs, wall-clock "as-of" queries, or listing children/branches. `grep` for `def .*diff|as_of|state_at|children|branches` in langgraph, checkpoint and sdk-py returned nothing relevant.
- Docs recipes (`checkpointers.mdx:513-528`) filter by `next`, by `metadata["step"]`, by `metadata["source"] == "update"`, and by tasks carrying interrupts.

---

## 5. Subgraph checkpoints

Docs (`checkpointers.mdx:169-172`):
> "`""` (empty string): The checkpoint belongs to the parent (root) graph. `"node_name:uuid"`: The checkpoint belongs to a subgraph invoked as the given node. For nested subgraphs, namespaces are joined with `|` separators (e.g., `"outer_node:uuid|inner_node:uuid"`)."

Code:
- The task namespace is `f"{checkpoint_ns}{NS_END}{task_id}"` (`pregel/_algo.py:615-624`). The task id is a hash of the parent checkpoint id, the namespace, the step, the name and the triggers.
- Subtasks receive `CONFIG_KEY_CHECKPOINT_MAP: {**configurable.get(CONFIG_KEY_CHECKPOINT_MAP, {}), parent_ns: checkpoint["id"]}`, with `CONFIG_KEY_CHECKPOINT_ID: None` and `CONFIG_KEY_CHECKPOINT_NS: task_checkpoint_ns` (`_algo.py:741-746`). That map becomes the subgraph checkpoint's `metadata["parents"]`.
- `get_state(config, subgraphs=True)` recurses into subgraph tasks of the current step (`main.py:1258-1289`). With `subgraphs=False`, each subgraph task's `state` field holds only `{"thread_id", "checkpoint_ns"}` "as signal that subgraph checkpoints exist" (1269-1277).
- A namespaced config is routed to the subgraph by `_subgraph_for_namespace` (`main.py:880-894`), which requires static discovery: `raise ValueError(f"Subgraph {recast} not found")`.
- A `checkpointer=True` (per-thread) subgraph strips task ids out of its namespace, giving one history per thread (`main.py:863-878`): `"A checkpointer=True subgraph keeps one history per thread, stored under its namespace with the task ids removed."`
- Replay into subgraphs is handled by `ReplayState` (`_internal/_replay.py:14-73`): `"On the first call for a given subgraph namespace, returns the latest checkpoint created *before* the replay point. On subsequent calls ... falls back to normal latest-checkpoint loading."`

Docs (`use-time-travel.mdx:358-360`):
> "By default, a subgraph inherits the parent's checkpointer. The parent treats the entire subgraph as a **single super-step** ... Time traveling from before the subgraph re-executes it from scratch. You cannot time travel to a point *between* nodes in a default subgraph"

Docs (`use-time-travel.mdx:436`):
> "Set `checkpointer=True` on the subgraph to give it its own checkpoint history. This creates checkpoints at each step **within** the subgraph"

Docs (`use-subgraphs.mdx:1261` tooltip):
> "State inspection with per-invocation persistence is available for the current invocation only (while interrupted). Each invocation starts fresh, so there is no accumulated state to inspect after the invocation completes."

Docs (`use-subgraphs.mdx:1274`):
> "Viewing subgraph state requires that LangGraph can **statically discover** the subgraph ... It does not work when a subgraph is called inside a tool function or other indirection"

Probe 1: after a default (per-invocation) subgraph finished, its four checkpoints were **still in storage** under `subnode:<task_id>`, with metadata `parents {'': '<parent ckpt id>'}`. The docs say inspection only works while the subgraph is interrupted. That is a discoverability limit through `get_state`, not deletion. I found no deletion code in `pregel/_loop.py` or `main.py`.

---

## 6. What is NOT preserved or controlled

1. **External side effects.** These are re-executed on replay or fork. Probe 1 shows `EXTERNAL file_written` gaining duplicate entries on every replay. Docs: `graph-api.mdx:772-774` ("Code and side effects before the pause run again ... Use idempotency keys, upserts, or read-before-write checks") and `interrupts.mdx:1352-1354`. There is no undo or compensation.
2. **Nondeterministic model or tool outputs.** These are not reused on time-travel replay. Probe 1 shows plan-609912 becoming plan-32779; see also `use-time-travel.mdx:20-24`. The exception is an opt-in input-keyed node cache (probe 2). The original outputs remain readable in the original branch's checkpoints and pending writes.
3. **World and environment state.** Checkpoints contain graph channel values only. The long-term **Store** sits outside graph state (`persistence.mdx:19`: "Stores persist application-defined data outside the graph state") and `put` overwrites in place ("Store or update an item", `checkpoint/langgraph/store/base/__init__.py`, with `Item` keeping only `created_at`/`updated_at`). Probe 3: the store held v=2 after two runs. Replaying the first run's pre-node checkpoint read v=2 and wrote v=3, so `state n: 3 | store now: {'v': 3}`. **Time travel does not roll back the store, and replayed nodes see present-day store contents. That is hindsight leakage for anything outside the checkpointed state.**
4. **Code, prompt and model version.** Replay runs the *current* node functions; nothing records the graph code version. Primitive `configurable` and `metadata` keys are copied into metadata incidentally (probe 4), but not on `update_state` forks.
5. **The reasoning behind a decision.** It is preserved only if the developer put it in state (for example the messages list). There is no dedicated field. Fork metadata has no reason or actor field (probe 1, probe 4), though custom metadata can be passed in through `config["metadata"]` (probe 1: `'why': 'testing-reason'`).
6. **Beliefs and uncertainty.** No such concept exists. State is an arbitrary developer-defined schema.
7. **Immutability is not absolute.**
   - `update_state` appends writes to the source checkpoint (probe 1: 1 → 3 writes).
   - Special writes (error, interrupt, resume, scheduled) are upserted: Postgres `UPSERT_CHECKPOINT_WRITES_SQL ... ON CONFLICT ... DO UPDATE` (`checkpoint-postgres/.../base.py:146-153`, used when `all(w[0] in WRITES_IDX_MAP ...)` at `postgres/__init__.py:363-367`). `InMemorySaver.put_writes` only skips existing keys with `idx >= 0` (`memory/__init__.py:493-503`).
   - Checkpoint rows are UPSERT on the same id (`base.py:137-144`). Exit durability re-puts with the same id (`_loop.py:1123`).
   - `delete_thread`, `delete_for_runs` and `prune(strategy="keep_latest"|"delete")` exist (`checkpoint/base/__init__.py:321-416`). The docs recommend pruning (`persistence.mdx:101-114`).
   - `durability="exit"` saves no intermediate checkpoints (`checkpointers.mdx:603`).
8. **Branch identity.** There is no branch id or name. After a fork or replay the new checkpoint becomes the thread head (probe 1: `latest == fork: True`). Earlier branches are reachable only by checkpoint id.
9. **Per-invocation subgraph internals.** These cannot be time-travelled to (`use-time-travel.mdx:360`) unless the subgraph uses `checkpointer=True`.

---

## 7. Capability ratings (summary; detailed evidence above)

| # | Capability | Rating | Key evidence |
|---|---|---|---|
| 1 | immutable_historical_observations | partial | Append-only new checkpoints, originals unchanged (probe 1). But only graph state is kept, the source checkpoint's writes are mutated by `update_state`, special writes are upserted, and prune/delete exist. |
| 2 | historical_world_state | no | Store and external world are not versioned or rolled back (probe 3, `persistence.mdx:19`). |
| 3 | historical_epistemic_state | partial | `get_state(checkpoint_id)` returns graph state as of that super-step. No cutoff is enforced on replay: present-day store, tools and LLM are visible (probe 3). No belief or knowledge labelling. |
| 4 | historical_policy_objective_state | no | No code, prompt or model version is recorded. Replay uses current code. Primitive configurable keys are copied incidentally (probe 4), not as policy tracking. |
| 5 | execution_checkpoints | yes | Checkpoint per super-step plus per-task pending writes; resume after interrupt or failure. |
| 6 | replay | yes | `invoke(None, past_config)` re-executes nodes after the checkpoint. This is re-execution, not deterministic replay. |
| 7 | fork_from_historical_state | yes | `update_state(past_config, values, as_node)` creates a new `source=update` checkpoint whose parent is the source. The original is intact (probe 1). |
| 8 | counterfactual_action_branches | partial | Forks run for real: side effects occur, the fork becomes the head, and nothing is simulated or uncommitted. |
| 9 | branch_provenance | partial | `parent_checkpoint_id`, `source`, `step`, `ts`, `parents`(ns). No reason, actor, explicit `as_node` or branch id. History interleaves branches. |
| 10 | explicit_current_belief_state | no | Generic typed state only. |
| 11 | uncertainty_representation | no | None. |
| 12 | future_state_rollout | no | None. Forks are real executions, not simulations. |
| 13 | multiple_prospective_branches | no | Multiple executed forks can coexist (`test_multiple_forks_from_same_checkpoint`), but nothing is prospective and there is no comparison. |
| 14 | probability_over_futures | no | None. |
| 15 | backward_requirements | no | None. |
| 16 | intervention_aware_forecasting | no | None. |
| 17 | prevented_futures_preserved | no | None. |
| 18 | predicted_vs_realized | no | None. |
| 19 | cross_time_state_querying | partial | `get_state(checkpoint_id)` and `get_state_history(before, limit, filter)`. No diff, no wall-clock as-of, no branch-scoped lineage query. |
| 20 | unified_temporal_abstraction | partial | One (thread, ns, checkpoint_id, parent) tree spans past, head and executed forks. No prospective states. |

---

## 8. Relation to the smoke_v1 benchmark

LangGraph's checkpoint plus time-travel mechanism is roughly a **superset of the baseline's "checkpoints" component** (restorable execution state with replay and fork). It is **not** a mechanism for reopening a world-authored decision such as an ADR or ticket. Those live in the external world, the repo or the tracker, and LangGraph neither versions nor rolls them back (probe 3, item 6.3).

For an agent, `get_state(checkpoint_id)` can answer "what was in my graph state at step k". That is a partial form of "known then", and only for knowledge the agent kept in state. It cannot answer:
- "what was true then" in the world;
- "known now about then" beyond comparing the old state with the head.

Replaying with present-day tools and store leaks hindsight. The specific cutoff discipline in the north star is therefore not provided.

Time travel is designed as a developer and HITL debugging feature (`checkpointers.mdx:26`: "allowing users to replay prior graph executions to review and / or debug specific graph steps"). It is not an agent-facing cognitive operation. Nothing in the docs or code exposes it to the agent as a tool.

---

## 9. Could not verify / caveats

- I did not run the Postgres or SQLite savers. My Postgres semantics come from reading the SQL constants (`checkpoint-postgres/.../base.py:131-159`) and `put_writes` (`postgres/__init__.py:363-367`); I did not execute them.
- The Agent Server / LangSmith server (closed source) has `threads.copy`, `get_history` and `update_state` over REST. I read only the docs (`langsmith/use-threads.mdx:122-144`, `langsmith/human-in-the-loop-time-travel.mdx`) and the SDK client signatures (`libs/sdk-py/langgraph_sdk/_async/threads.py:410-440, 687-735`). I cannot see server-side behaviour. In particular I could not check whether the server adds `run_id`, an assistant config or a graph version to checkpoint metadata.
- I did not test the JS implementation (`@langchain/langgraph`). Everything here is Python.
- The DeltaChannel beta (incremental storage) can make history reconstruction depend on ancestor writes. I did not probe its failure modes beyond reading the docstrings (`checkpoint/base/__init__.py:388-416`).
- No published evaluation or paper exists for LangGraph time travel. The only "evaluation" is the repo's unit tests (`libs/langgraph/tests/test_time_travel.py`, `test_time_travel_async.py`).
- My probes ran with Python 3.11 and InMemorySaver only. Exact numbers (ids, random values) differ per run, but the counts and structure do not.
