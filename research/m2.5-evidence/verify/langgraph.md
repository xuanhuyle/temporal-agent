# Verification: LangGraph persistence / time travel (adversarial re-check)

Verifier notes, 2026-10-03. I re-checked the analyst's JSON and notes (`notes/langgraph.md`) against the same clones:
- `repos/langgraph` at 7dc9195e (2026-10-02)
- `repos/langchain-docs` at 6d6080f5 (2026-10-03)

I also ran one independent probe of my own: `verify/langgraph_vprobe.py`, output in `.out`. It used the existing `lgvenv` editable install and InMemorySaver.

## Spot-checked citations (all hold)
- `pregel/_loop.py:316`: `self.is_replaying = CONFIG_KEY_CHECKPOINT_ID in config[CONF]`.
- `_loop.py:662-665`: `if not self.is_replaying and self.checkpoint_pending_writes: self._reapply_writes_to_succeeded_nodes(...)`.
- `_loop.py:850-876`: RESUME writes are dropped when time-traveling.
- `_loop.py:928-947`: `self._put_checkpoint({"source": "fork"})`.
- `_loop.py:1101-1102`: `metadata["parents"] = ...CHECKPOINT_MAP`.
- `pregel/main.py:1980-1986`: `checkpointer.put_writes(checkpoint_config, channel_writes, task_id)`, where `checkpoint_config` is the source checkpoint's config. The new checkpoint is put with parent = the source (2005-2021).
- `checkpoint/base/__init__.py:758-776`: `get_checkpoint_metadata` copies primitive keys from `config["metadata"]` and `config["configurable"]`. Lines 783-785 pop `writes`.
- `memory/__init__.py:450-457` stores the parent id, and `memory/__init__.py:493-503` skips existing writes with idx>=0. Both confirmed.
- `types.py:711-735` StateSnapshot fields: confirmed.
- `store/base/__init__.py`: `Item` has only `value, key, namespace, created_at, updated_at`, and `put` is "Store or update an item in the store." There is no version history.
- Docs `use-time-travel.mdx:129-133`, `358-360`; `persistence.mdx:19`; `checkpointers.mdx:603`: quotes confirmed verbatim.
- Analyst probe outputs `langgraph_probe3.out` and `langgraph_probe4.out` exist and match the quoted results.

Omission (it does not change any rating): `checkpointers.mdx:26` continues past the analyst's quote:
> "In addition, checkpointers make it possible to fork the graph state at arbitrary checkpoints to explore alternative trajectories."

So the docs themselves frame forks as a way to explore alternatives. This supports, but does not raise, the partial rating for counterfactual_action_branches.

## My probe (verify/langgraph_vprobe.out)
```
A head metadata (context= only): {'source': 'loop', 'step': 2, 'parents': {}}
B before tasks (pre-update): [('write', {'joke': 'j:socks'})]
C fork metadata with config metadata: {'source': 'update', 'step': 2, 'parents': {}, 'why': 'ADR-7 reopened', 'actor': 'agent'}
D before tasks (post-update): [('write', {'joke': 'j:socks'})]
D2 before values unchanged: True
E raw pending writes on source: [('joke', 'j:socks'), ('topic', 'chickens'), ('branch:to:write', None)]
F filter by why: ['update']
G copy meta: {'source': 'fork', 'step': 2, 'parents': {}} parent==before.parent: True
```
What the probe shows:
- **(A)** The LangGraph 1.x Runtime `context=` (the recommended replacement for configurable) is NOT recorded in checkpoint metadata. Only legacy `configurable`/`metadata` primitives are copied.
- **(C, F)** The analyst wrote that "update_state forks do not carry those keys" (probe 4). That is an artifact of passing `before.config` without metadata. If the caller passes `config["metadata"]` to `update_state`, arbitrary reason and actor keys are stored on the fork checkpoint (put calls `get_checkpoint_metadata(checkpoint_config, ...)`, `memory/__init__.py:454`) and can be filtered with `get_state_history(filter=...)`. So branch reasons are user-attachable and queryable. They are still not automatic.
- **(D, E)** `update_state` does append writes to the SOURCE checkpoint's pending writes (confirmed). However, the historical snapshot view `get_state(source)` (tasks, results and values) was unchanged in this case. The mutation is additive at the storage level, and the user-visible record was unaffected here.

## Changed rating
### 4 historical_policy_objective_state: no -> partial
Evidence the analyst under-weighted or missed:
1. Automatic per-checkpoint capture of the config that governed the run. `checkpoint/base/__init__.py:766-775` copies every primitive key from `config["metadata"]` and `config["configurable"]` into each checkpoint's metadata. The analyst's own probe 4 recorded `model_name: model-A, system_prompt_version: 3` on loop checkpoints. These keys are queryable with `get_state_history(filter={...})` (probe F).
2. Agent Server assistants are versioned policy/config objects (prompts, LLM selection, tools) with a change history and rollback.
   - `langsmith/assistants.mdx:6`: "allow you to manage configurations (e.g., prompts, LLM selection, tools) separately from your graph's core logic".
   - `assistants.mdx:39`: "Each assistant maintains its own configuration history through versioning. Editing an assistant creates a new version, and you can promote or roll back to any version."
   - `assistants.mdx:115-120`: "All versions remain available for reference and rollback."
   - The OpenAPI (`langsmith/agent-server-openapi.json`) has the path `/assistants/{assistant_id}/versions`.
3. Server checkpoint metadata carries the governing graph/assistant ids.
   - `langsmith/use-threads.mdx` get_state example output shows `"metadata": {..., "graph_id": "agent_with_quite_a_long_name", "source": "update", "step": 1, ...}`.
   - `langsmith/encryption.mdx:156` lists metadata SKIP_FIELDS `"run_id", "thread_id", "graph_id", "assistant_id", ..., "source", "step", "parents", "run_attempt", "langgraph_version", ...`. This is indirect evidence that server metadata includes assistant_id and langgraph_version.

Why it stays partial rather than yes:
- No code or graph-function version is recorded, and replay runs the current code.
- The Runtime `context` is not recorded (probe A).
- Goals and objectives exist only if they are put in state.
- I could not establish that a checkpoint records WHICH assistant version was active. The server is closed source, so that link is unclear.

## Unchanged ratings (reasoning)
- **1 immutable_historical_observations: partial.** Confirmed in both directions. Originals stay unchanged (D2), and writes on the source are additive (E). Upsert, prune and delete are confirmed in code.
- **2 historical_world_state: no.** The Store has no versions (Item fields; put = "Store or update"). Probe 3 confirmed that replay saw v=2 and wrote v=3. If a developer models the world inside graph state it would be checkpointed, but that is a generic container. I treat it the same way as #10.
- **3 historical_epistemic_state: partial.** `get_state(checkpoint_id)` is a naturally cut-off view of in-graph context. There is no enforced cutoff for re-execution.
- **5, 6, 7: yes.** Confirmed by code and both probes.
- **8 counterfactual_action_branches: partial.** Docs (`checkpointers.mdx:26`) frame forks as exploring "alternative trajectories", and `__copy__` and `threads.copy` give copies. However, execution is real: side effects happen and the Store is shared.
- **9 branch_provenance: partial.** There are parent pointers and `source`, and user-attached reason/actor metadata is stored and filterable (probe C, F). There is no automatic reason, no branch id, and no recorded as_node.
- **10, 11: no.** These would need a generic schema only.
- **12-18: no.** A docs grep for forecast, world model, dry-run, what-if, counterfactual and uncertainty in `oss/langgraph` found nothing relevant (only an error page). No code exists for any of them.
- **19 cross_time_state_querying: partial.** Confirmed: there is no `diff`, `as_of` or `state_at`/children function (grep of `def .*(diff|as_of|state_at|children|branch)` found only graph-construction branches). The metadata filter is equality-only.
- **20 unified_temporal_abstraction: partial.** One checkpoint tree spans past, head and executed forks, but there are no prospective states. Partial is the ceiling. I considered "no", since the abstraction lacks one of its four required kinds, but three of the four are covered within one abstraction.

## Corrected claims
- "update_state forks do not carry those keys (probe 4)" is misleading. The fork carries any primitive metadata or configurable keys present in the config passed to update_state (probe C).
- The claim that "Fork metadata has no reason, actor ... field" is true only of automatic fields. A reason and actor can be attached and filtered (probe C, F). The analyst partly acknowledged this.
- The `checkpointers.mdx:26` positioning quote is truncated. The same sentence block also says forks are "to explore alternative trajectories".
