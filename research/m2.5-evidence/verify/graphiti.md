# Graphiti / Zep: adversarial verification notes

Verifier pass, 2026-10-03. The target is the analyst's JSON and `notes/graphiti.md`.
The clone is reused: `scratchpad/lit/repos/graphiti`, HEAD `3c427640abf909f12f71f963fce15eb514a3c493`
(2026-09-30 08:02:28 +0000). All file:line references below are from that commit, read directly by me.

## Source access in this pass
- **Zep paper body:** still NOT obtained. WebSearch returned "this session has used its web search budget
  (200 of 200 WebSearch calls)", and arxiv is blocked.
- **Abstract:** independently confirmed from a second source. `repos/pf/daily/27-Jan-2025/AI/README.md:1615-1617`
  has the arXiv PDF link `https://arxiv.org/pdf/2501.13956` and the full abstract text. It matches the analyst's
  screenshot transcription word for word, including "94.8% vs 93.4%", "up to 18.5%" and "reducing response latency
  by 90%".
- **Paper-body claims remain unverified.** This covers the T/T' formalism, the subgraph tiers, the LongMemEval
  per-category results and the limitations.

## Code claims re-checked (all CONFIRMED)
- **EntityEdge fields** (`graphiti_core/edges.py:263-285`): episodes, expired_at, valid_at, invalid_at,
  reference_time, attributes.
- **EpisodicNode and EntityNode** (`nodes.py:318-335` and `nodes.py:499-504`): the EntityNode has no validity fields.
- **In-place upsert:**
  - FalkorDB edge save is `MERGE (source)-[e:RELATES_TO {uuid: $edge_data.uuid}]->(target)` / `SET e = $edge_data`
    (`models/edges/edge_db_queries.py:67-70`).
  - Episode save is `MERGE (n:Episodic {uuid: $uuid}) SET n = {...}` (`models/nodes/node_db_queries.py:34-50`).
  - Entity save is `MERGE (n:Entity ...) SET n = $entity_data` (`node_db_queries.py:142-146`).
- **Contradiction resolution** (`utils/maintenance/edge_operations.py:538-573`): verbatim as the notes show. In
  particular, `edge.invalid_at = resolved_edge.valid_at` and
  `edge.expired_at = edge.expired_at if edge.expired_at is not None else utc_now()`.
- **Expiry on arrival** (`edge_operations.py:820-839`): `if resolved_edge.invalid_at and not resolved_edge.expired_at:
  resolved_edge.expired_at = now`, plus the "Expire new edge since we have information about more recent events"
  branch.
- **Wall clock:** `utils/datetime_utils.py:20-22` `return datetime.now(timezone.utc)`.
- **Invalidation candidates** come from an unfiltered top-k search (`edge_operations.py:407-415`:
  `config=EDGE_HYBRID_SEARCH_RRF, search_filter=SearchFilters()`).
- **Graphiti.search:**
  - It mutates the shared recipe: `search_config.limit = num_results` (`graphiti.py:1628-1631`).
  - It passes `SearchFilters()` by default (`graphiti.py:1640`).
  - The docstring claims "using the current date and time as the reference point for temporal relevance"
    (`graphiti.py:1625-1626`).
- **remove_episode** hard-deletes the episode, the edges whose `edges[0]` is that episode, and the nodes that only
  episode mentions (`graphiti.py:1824-1852`).
- **driver.clone** is `"""Clone the driver with a different database or graph name.""" return self`
  (`driver/driver.py:131-133`). There is no data copy.
- **Context string to the LLM:** "Facts are considered valid between their valid_at and invalid_at dates. Facts
  with an invalid_at date of "Present" are considered valid." (`search/search_helpers.py:55-56`). Null valid_at
  renders as `"date unknown"` (`search_helpers.py:22-24`).
- **SearchFilters OR-group parameter bug:**
  - [RUN] I re-ran `scratchpad/lit/graphiti_filter_probe.py`. It loads the real `search_filters.py` with only two
    imports stubbed. Output: `(['((e.valid_at >= $valid_at_0) OR (e.valid_at <= $valid_at_0))'], {'valid_at_0':
    datetime(2025, 6, 1, ...)})`.
  - Cause, from the source: `filter_params['valid_at_' + str(j)]` is keyed by the inner index `j` only
    (`search_filters.py:151-158`).
  - The bitemporal as-of filter does produce the expected four WHERE fragments.
- **MCP surface:**
  - `search_memory_facts` exposes valid_at_* and invalid_at_* filters only (`mcp_server/src/graphiti_mcp_server.py:616-626`).
  - `get_episodes` takes only group_ids and max_episodes (`graphiti_mcp_server.py:795-798`), so MCP has no as-of
    parameter for episodes.
- **REST server:** `server/graph_service/routers/retrieve.py:39` calls retrieve_episodes with
  `reference_time=datetime.now(timezone.utc)`. The REST API has no as-of parameter.
- **Ingestion cutoff:** add_episode fetches previous episodes with `retrieve_episodes(reference_time, ...)`
  (`graphiti.py:~1145`). Extraction context is therefore valid-time cut off at the episode's reference_time.
  Dedup and invalidation candidates are NOT time-filtered (see above), so later facts can influence how an earlier
  backdated episode is processed.

## Corrections (deflation found)

### 1. historical_policy_objective_state: no -> partial
The analyst wrote: "There is no representation of agent goals, instructions, policy or model... Prompts or policies
could be ingested as text episodes, but they would just become generic facts." This misses the shipped MCP server's
default typed entities for instructions that govern the agent.

- `mcp_server/src/models/entity_types.py:46-47`: `class Procedure(BaseModel): """A Procedure informing the agent what
  actions to take or how to perform in certain scenarios. Procedures are typically composed of several steps.`
- `mcp_server/config/config.yaml:96-102` enables them by default:
  `entity_types: - name: "Preference" ... - name: "Requirement" description: "Specific needs, features, or functionality
  that must be fulfilled" - name: "Procedure" description: "Standard operating procedures and sequential instructions"`
- `mcp_server/docs/cursor_rules.md` (the agent usage rules shipped for coding agents):
  - line 5: "**Always search first:** Use the `search_nodes` tool to look for relevant preferences and procedures
    before beginning work."
  - line 12: "**Capture requirements and preferences immediately:** When a user expresses a requirement or
    preference, use `add_memory` to store it right away."
  - line 14: "**Be explicit if something is an update to existing knowledge.**"
  - line 22: "**Follow procedures exactly:**"

**Why partial and not yes:**
- Instructions and requirements that govern the agent are recorded as typed nodes, with episode provenance (raw
  episode valid_at) and fact edges that carry validity windows. So "which instructions were in force at t" is
  partly recoverable through the edge validity windows and the episode cutoff.
- However, the node itself (its summary and attributes) is unversioned, and node search has no time filter (label
  filter only).
- Nothing records the agent's model or policy version, and nothing gives first-class "objective changed at t"
  records.

### 2. explicit_current_belief_state: rating unchanged (partial), evidence corrected
The analyst said it "models world facts, not the agent's beliefs, assumptions or requirements". Requirements ARE
modelled, as a default typed entity in the MCP server (see above). Separately, `graphiti_core/prompts/summarize_sagas.py:87-89`
instructs saga summaries to capture "- Decisions and their outcomes / - Preferences and requirements ... / - Plans,
next steps, and commitments".

These summaries are prose and overwritten in place (`graphiti.py:559 saga.summary = summary`). There is still no
"agent believes" vs "source asserted" distinction, and no assumption type. The rating stays partial, but the claim
that "There is no type or field for ... decisions, plans, goals" is overstated:
- decisions and plans are captured in saga summary prose;
- requirements and procedures are captured as MCP default entity types.
It holds only for graphiti_core's built-in schema, without the MCP defaults.

## Ratings confirmed unchanged
- **partial:** immutable_historical_observations, historical_world_state, historical_epistemic_state,
  explicit_current_belief_state, cross_time_state_querying.
- **no:** execution_checkpoints, replay, fork_from_historical_state, counterfactual_action_branches,
  branch_provenance, uncertainty_representation, future_state_rollout, multiple_prospective_branches,
  probability_over_futures, backward_requirements, intervention_aware_forecasting, prevented_futures_preserved,
  predicted_vs_realized, unified_temporal_abstraction.

uncertainty_representation: grep for confidence/uncertain/probab in graphiti_core finds only three things, none an
uncertainty representation in memory state:
- the GLiNER2 client's `include_confidence` option (`llm_client/gliner2_client.py:71`);
- Gemini safety-rating probabilities;
- name-entropy dedup helpers (`dedup_helpers.py:56-74`).
