# Graphiti / Zep temporal context graphs: primary-source notes

Analyst notes, written 2026-10-03. Claims carry one of these tags:
[CODE] = verified by reading the code, [RUN] = verified by executing an isolated piece of the code,
[DOC] = repo documentation (a claim, not verified behavior), [PAPER-ABSTRACT] = arXiv abstract as rendered in a
screenshot that ships in the repo, [UNVERIFIED] = could not be checked.

## Sources and how I obtained them

| Source | How obtained |
|---|---|
| https://github.com/getzep/graphiti (HEAD `3c427640abf909f12f71f963fce15eb514a3c493`, commit date 2026-09-30, `pyproject.toml` version `0.30.2`) | `git clone --depth 1` into `scratchpad/lit/repos/graphiti`. All file:line citations below refer to this commit. |
| Graphiti README.md, CLAUDE.md, .github/copilot-instructions.md, mcp_server/ | Read from the clone |
| arXiv:2501.13956 abstract page (title, authors, submission date, abstract, "12 pages, 3 tables") | `images/arxiv-screenshot.png` in the clone, viewed as an image. This is a screenshot of https://arxiv.org/abs/2501.13956 that the repo ships. |
| Zep paper body (sections, method, tables, limitations) | **NOT OBTAINED.** The WebSearch budget for this session was already used up (200/200), arxiv.org is blocked for curl and WebFetch, and probing mirror hosts was denied by the permission classifier. I did not retry. Every paper-body claim is therefore [UNVERIFIED]. |
| `scratchpad/lit/graphiti_filter_probe.py` | My own script. It loads `graphiti_core/search/search_filters.py` on its own (two imports stubbed) and prints the Cypher WHERE fragments it generates. |

## Paper (abstract only)

Verbatim, from `images/arxiv-screenshot.png` [PAPER-ABSTRACT]:

> [Submitted on 20 Jan 2025]
> Zep: A Temporal Knowledge Graph Architecture for Agent Memory
> Preston Rasmussen, Pavlo Paliychuk, Travis Beauvais, Jack Ryan, Daniel Chalef
> "We introduce Zep, a novel memory layer service for AI agents that outperforms the current state-of-the-art system,
> MemGPT, in the Deep Memory Retrieval (DMR) benchmark. Additionally, Zep excels in more comprehensive and challenging
> evaluations than DMR that better reflect real-world enterprise use cases. While existing retrieval-augmented
> generation (RAG) frameworks for large language model (LLM)-based agents are limited to static document retrieval,
> enterprise applications demand dynamic knowledge integration from diverse sources including ongoing conversations
> and business data. Zep addresses this fundamental limitation through its core component Graphiti -- a
> temporally-aware knowledge graph engine that dynamically synthesizes both unstructured conversational data and
> structured business data while maintaining historical relationships. In the DMR benchmark, which the MemGPT team
> established as their primary evaluation metric, Zep demonstrates superior performance (94.8% vs 93.4%). Beyond DMR,
> Zep's capabilities are further validated through the more challenging LongMemEval benchmark, which better reflects
> enterprise use cases through complex temporal reasoning tasks. In this evaluation, Zep achieves substantial results
> with accuracy improvements of up to 18.5% while simultaneously reducing response latency by 90% compared to baseline
> implementations. These results are particularly pronounced in enterprise-critical tasks such as cross-session
> information synthesis and long-term context maintenance, demonstrating Zep's effectiveness for deployment in
> real-world applications."
> Comments: 12 pages, 3 tables. Subjects: cs.CL; cs.AI; cs.IR.

Affiliation: the authors' affiliation line in the paper is [UNVERIFIED]. The code's license headers say
"Copyright 2024, Zep Software, Inc." (for example `graphiti_core/search/search_filters.py:2`).

## Repo documentation claims [DOC]

- README.md:37-38: "Graphiti's context graphs track how facts change over time, maintain provenance to source data"
- README.md:62-65: "each fact in a context graph has a validity window: when it became true, and when (if ever) it was
  superseded. Entities evolve over time with updated summaries. Everything traces back to **episodes** — the raw data
  that produced it."
- README.md:76: "| **Episodes** (provenance) | Raw data as ingested — the ground truth stream. Every derived fact traces back here |"
- README.md:119-120: "**Temporal Fact Management:** Facts have validity windows. When information changes, old facts are
  invalidated — not deleted. Query what's true now, or what was true at any point in time."
- README.md:145: "| **Temporal Handling** | Basic timestamp tracking | Explicit bi-temporal tracking with automatic fact invalidation |"
- CLAUDE.md:11: "Bi-temporal data model with explicit tracking of event occurrence times"
- .github/copilot-instructions.md:40-41: "A change to the bi-temporal fields (`valid_at`, `invalid_at`, `created_at`,
  `expired_at`) that breaks the ordering rules."
- mcp_server/src/graphiti_mcp_server.py:145-148: "Bi-temporal model: every episode records both when it was ingested and
  when the events it describes actually occurred. Pass reference_time to add_memory to set the event-occurrence time;
  otherwise the current time is used. Facts carry valid_at / invalid_at metadata, so a fact can be superseded by newer
  information while its history is preserved."

## Data model [CODE]

### Edge (fact) temporal fields: `graphiti_core/edges.py`
```
49 class Edge(BaseModel, ABC):
...
54     created_at: datetime
...
263 class EntityEdge(Edge):
264     name: str = Field(description='name of the edge, relation name')
265     fact: str = Field(description='fact representing the edge and nodes that it connects')
...
267     episodes: list[str] = Field(
268         default=[],
269         description='list of episode ids that reference these entity edges',
271     expired_at: datetime | None = Field(
272         default=None, description='datetime of when the node was invalidated'
274     valid_at: datetime | None = Field(
275         default=None, description='datetime of when the fact became true'
277     invalid_at: datetime | None = Field(
278         default=None, description='datetime of when the fact stopped being true'
280     reference_time: datetime | None = Field(
281         default=None, description='reference timestamp from the episode that produced this edge'
283     attributes: dict[str, Any] = Field(
```
Reading: there are two time axes on facts.
- Valid time is `valid_at`/`invalid_at`. An LLM extracts these, relative to the episode's reference time.
- Transaction (system) time is `created_at`/`expired_at`, which the system stamps from the wall clock.

### Episode (raw observation): `graphiti_core/nodes.py`
```
318 class EpisodicNode(Node):
319     source: EpisodeType = Field(description='source type')
320     source_description: str = Field(description='description of the data source')
321     content: str = Field(description='raw episode data')
322     valid_at: datetime = Field(
323         description='datetime of when the original document was created',
325     entity_edges: list[str] = Field(
326         description='list of entity edges referenced in this episode',
```
`Node.created_at` defaults to `utc_now()` (nodes.py:98). `add_episode` builds the episode with
`created_at=now, valid_at=reference_time` (graphiti.py:1167-1168), where `now = utc_now()` (graphiti.py:1131).
`EpisodeType` takes the values message/json/text/fact_triple (nodes.py:54-78). A message episode is written as
"actor: content", for example "assistant: I'm doing well" (nodes.py:64-67).

### Entity node: `graphiti_core/nodes.py:499-504`
```
499 class EntityNode(Node):
500     name_embedding: list[float] | None = ...
501     summary: str = Field(description='regional summary of surrounding edges', default_factory=str)
502     attributes: dict[str, Any] = Field(
```
Entity nodes have only `created_at`. They have no valid/invalid/expired fields.

### Persistence is in-place upsert, not append
- `graphiti_core/models/edges/edge_db_queries.py:69-70` (FalkorDB):
  `MERGE (source)-[e:RELATES_TO {uuid: $edge_data.uuid}]->(target)` / `SET e = $edge_data`
  The Neo4j, Neptune and Kuzu variants follow the same MERGE+SET pattern (lines 74-110). The bulk variant at
  lines 127-146 uses `MERGE ... SET r = edge`.
- Entity nodes: `models/nodes/node_db_queries.py:144-146`: `MERGE (n:Entity {{uuid: $entity_data.uuid}})` ...
  `SET n = $entity_data`
- Episodes: `models/nodes/node_db_queries.py:34-36,41-50`: `MERGE (n:Episodic {uuid: $uuid})` then `SET n = {...}`
- So when an edge is invalidated, the same row is mutated: `invalid_at` and `expired_at` are set on the existing
  edge record, and no new version row is written.

## Invalidation / contradiction handling [CODE]

1. Candidate retrieval: `edge_operations.py:407-415`. Invalidation candidates come from a top-k hybrid search
   (`EDGE_HYBRID_SEARCH_RRF`) with an empty `SearchFilters()`, so the candidates can include edges that are already
   expired. The search is bounded by the config limit (`SearchConfig.limit` defaults to `DEFAULT_SEARCH_LIMIT = 10`,
   search_config.py:29,117), so invalidation is not exhaustive.
2. An LLM judges duplicates and contradictions with `prompts/dedupe_edges.py:43-100`. Verbatim:
   "2. CONTRADICTION DETECTION: - Determine which facts the NEW FACT contradicts from either list." Example (lines 90-92):
   "EXISTING FACT: idx=1, "Alice works at Acme Corp as a software engineer" / NEW FACT: "Alice works at Acme Corp as a
   senior engineer" / Result: duplicate_facts=[], contradicted_facts=[1]"
3. Temporal resolution: `edge_operations.py:538-573` (`resolve_edge_contradictions`):
```
553         if (
554             edge_invalid_at_utc is not None
555             and resolved_edge_valid_at_utc is not None
556             and edge_invalid_at_utc <= resolved_edge_valid_at_utc
557         ) or (
558             edge_valid_at_utc is not None
559             and resolved_edge_invalid_at_utc is not None
560             and resolved_edge_invalid_at_utc <= edge_valid_at_utc
561         ):
562             continue
563         # New edge invalidates edge
564         elif (
565             edge_valid_at_utc is not None
566             and resolved_edge_valid_at_utc is not None
567             and edge_valid_at_utc < resolved_edge_valid_at_utc
568         ):
569             edge.invalid_at = resolved_edge.valid_at
570             edge.expired_at = edge.expired_at if edge.expired_at is not None else utc_now()
571             invalidated_edges.append(edge)
```
   Consequences:
   - (a) If either edge's `valid_at` is null, a contradiction the LLM flagged does not invalidate anything.
   - (b) A previously set `invalid_at` that is later than the new edge's `valid_at` is overwritten with no history.
     `expired_at` keeps its first value.
4. A new edge can be expired on arrival when the graph already holds later information (out-of-order ingestion),
   `edge_operations.py:820-839`:
```
822     if resolved_edge.invalid_at and not resolved_edge.expired_at:
823         resolved_edge.expired_at = now
...
834                 and candidate_valid_at_utc > resolved_edge_valid_at_utc
835             ):
836                 # Expire new edge since we have information about more recent events
837                 resolved_edge.invalid_at = candidate.valid_at
838                 resolved_edge.expired_at = now
```
   Line 822 also sets `expired_at = now` for any fact whose end is already known when it is extracted. A fact like
   "X worked at Y until 2020" is therefore expired at the moment it is created. So `expired_at` means "no longer
   current in the graph's view as of this system time". It does not mean "this record was retracted".
5. Invalidated edges are persisted, not deleted: `graphiti.py:1215` `entity_edges = resolved_edges + invalidated_edges`,
   which `_process_episode_data` then saves.
6. Valid-time extraction prompt, `prompts/extract_edges.py:169-173` (verbatim):
   "- If the fact is ongoing (present tense), set `valid_at` to the timestamp of the episode the fact originates from. If
   no per-episode timestamp is available, use REFERENCE_TIME. - If a change/termination is expressed, set `invalid_at`
   to the relevant timestamp. - Leave both fields `null` if no explicit or resolvable time is stated."
   There is also a fallback LLM call, `_extract_edge_timestamps` (edge_operations.py:576-620), which uses the same
   rules (extract_edges.py:250-258).
7. Transaction timestamps come from the wall clock and cannot be injected. `utils/datetime_utils.py:20-22`
   `return datetime.now(timezone.utc)`. Edge `created_at=utc_now()` (edge_operations.py:306). Edge
   `expired_at = utc_now()` (edge_operations.py:570, 820). Episode `created_at=now` (graphiti.py:1131,1167).
   `add_episode` has no parameter for transaction time.

## Provenance [CODE]

- Each fact keeps a list of episode UUIDs: `EntityEdge.episodes` (edges.py:267-270). A duplicate re-mention appends the
  new episode in place (edge_operations.py:692-694 and 751-752). No timestamp is stored per mention.
- Each episode keeps the list of edges it touched: `EpisodicNode.entity_edges` (nodes.py:325). This is overwritten on
  processing (graphiti.py:748-749: `ep.entity_edges = [edge.uuid for edge in entity_edges]`).
- Episodes link to entities through MENTIONS (`EpisodicEdge`, edges.py:143-160; `build_episodic_edges`,
  edge_operations.py:52-97).
- For batch extraction there is per-fact episode attribution through `episode_indices` (extract_edges.py:48-51;
  edge_operations.py:291-297).
- There is a lookup API: `get_nodes_and_edges_by_episode` (graphiti.py:1690-1702), exposed in MCP as
  `get_episode_entities`.
- Provenance granularity is therefore the whole episode (a message or document). There are no character spans or
  offsets.
- Raw content storage can be switched off: `store_raw_episode_content: bool = True` (graphiti.py:146). When it is
  False, `ep.content = ''` (graphiti.py:750-751).

## Deletion / mutability (against "immutable observations") [CODE]

- `remove_episode` (graphiti.py:1824-1852) hard-deletes the episode, the edges it created first
  (`edge.episodes[0] == episode.uuid`, line 1834), and the nodes mentioned only by that episode.
- MCP tools `delete_entity_edge`, `delete_episode` and `clear_graph` exist (graphiti_mcp_server.py:696, 729, 1102).
- `build_communities` first calls `remove_communities` (graphiti.py:1563), so communities are rebuilt destructively.
- Entity summaries are rewritten in place, for example `node.summary = summary_with_edges`
  (node_operations.py:873-881). No summary history is kept.
- Edge `attributes` are replaced on re-resolution (edge_operations.py:790-805, `merge_mode='replace'`) or cleared
  (`resolved_edge.attributes = {}`, line 809).

## Search / retrieval and as-of filtering [CODE] [RUN]

- `SearchFilters` (search/search_filters.py:55-67) has date filters on exactly the four edge fields:
```
62     valid_at: list[list[DateFilter]] | None = Field(default=None)
63     invalid_at: list[list[DateFilter]] | None = Field(default=None)
64     created_at: list[list[DateFilter]] | None = Field(default=None)
65     expired_at: list[list[DateFilter]] | None = Field(default=None)
```
  The outer list is OR'd and the inner lists are AND'd (lines 149-271). The resulting fragments are ANDed into the edge
  query WHERE clause (search_utils.py:224-234 and similar).
- [RUN] With `scratchpad/lit/graphiti_filter_probe.py`, a bitemporal as-of-t filter can be expressed. Output:
```
['((e.valid_at <= $valid_at_0))', '((e.invalid_at > $invalid_at_0) OR (e.invalid_at IS NULL))',
 '((e.created_at <= $created_at_0))', '((e.expired_at > $expired_at_0) OR (e.expired_at IS NULL))']
```
- [RUN] Bug in parameter naming. Two OR groups that each hold a non-null comparison share the parameter name
  `$valid_at_0`, so the first date is silently replaced:
```
(['((e.valid_at >= $valid_at_0) OR (e.valid_at <= $valid_at_0))'], {'valid_at_0': datetime(2025, 6, 1, ...)})
```
  The repo's own test `tests/test_graphiti_mock.py:983-996` uses exactly this OR shape and still passes.
- Default retrieval does **not** filter to currently valid facts.
  - `Graphiti.search` passes `SearchFilters()` when no filter is given (graphiti.py:1628-1640).
  - A grep for `IS NULL` outside search_filters.py finds no default validity predicate.
  - The docstring says (graphiti.py:1625-1626): "The search is performed using the current date and time as the
    reference point for temporal relevance". I found no code that applies a current-time predicate or a time-based
    reranker. The rerankers are rrf, node_distance, episode_mentions, mmr and cross_encoder (search_config.py:53-58).
  - Invalidated facts therefore come back alongside current ones. The LLM is left to interpret the dates, through
    `search_results_to_context_string` (search/search_helpers.py:56-57): "Facts are considered valid between their
    valid_at and invalid_at dates. Facts with an invalid_at date of "Present" are considered valid."
- Time filters apply only to edges.
  - Node filters accept labels only (search_filters.py:86-104).
  - Episode search ignores the filter: the parameter is named `_search_filter` and is passed only to the optional
    driver delegate (search_utils.py:884-890). The Cypher has only a group filter (lines 898-902).
- `retrieve_episodes(reference_time, last_n)` is a valid-time cutoff on episodes
  (`WHERE e.valid_at <= $reference_time ORDER BY e.valid_at DESC LIMIT $num_episodes`,
  graph_data_operations.py:140-157). Its docstring (line 80-82) says: "This allows for querying the graph's state at a
  specific point in time."
- MCP `search_memory_facts` exposes only `valid_at_after/before` and `invalid_at_after/before`
  (graphiti_mcp_server.py:616-641; type_config.py:163-195). It does **not** expose `created_at`/`expired_at`
  (transaction time). A single range cannot express "invalid_at IS NULL OR invalid_at > t".
- Side effect observed by reading the code, not executed: `Graphiti.search` mutates the shared module-level recipe
  (`search_config = EDGE_HYBRID_SEARCH_RRF ...; search_config.limit = num_results`, graphiti.py:1628-1631).
  Ingestion uses the same `EDGE_HYBRID_SEARCH_RRF` object to find invalidation candidates (edge_operations.py:413),
  so the number of invalidation candidates may depend on the last user search call.
- There are temporal range indexes on edges and episodes (graph_queries.py:74-81), for example
  `CREATE INDEX expired_at_edge_index ... ON (e.expired_at)`.

## Agent beliefs / decisions? [CODE]

- The schema has no belief, decision, plan, goal, policy, confidence or uncertainty type or field.
  - grep for confidence/probabil/uncertain in graphiti_core finds only dedup entropy helpers and reranker code.
  - grep for fork/snapshot/branch/checkpoint/forecast/predict/simulat/counterfactual finds nothing relevant. The only
    hits are DB transaction rollback and a reranker `.predict`.
- An agent's own utterances can be ingested as message episodes. The langgraph example does this
  (`examples/langgraph-agent/agent.ipynb`, cell 20):
  `episode_body=f'{state["user_name"]}: {state["messages"][-1]}\nSalesBot: {response.content}'`.
  The extraction prompt then extracts the speaker as an entity (prompts/extract_nodes.py:130). What the agent says
  becomes generic entity-relation facts. Nothing marks them as the agent's beliefs or decisions.
- `driver.clone(database=...)` (driver/driver.py:131-133) clones a connection handle. It does not copy data. `group_id`
  partitions graphs, but no API copies or forks a partition.

## What the Zep paper body contains: could not verify

All of the following are [UNVERIFIED], because I could not read the paper text in this session:
- whether the paper formalises two timelines (T and T') and the four edge timestamps;
- the episodic, semantic and community subgraph tiers and the community algorithm;
- the LongMemEval per-category table, the models used and the baselines;
- any stated limitations or future work;
- whether the paper describes as-of / point-in-time retrieval or only uses validity in context assembly.

The code facts above stand on their own and do not depend on the paper.

## Things I could not verify (consolidated)

1. The Zep paper body (method, tables, limitations, author affiliations). I have the abstract only (repo screenshot).
2. Whether the managed Zep service (proprietary "Context Graph Engine", README.md:84-87) offers as-of-transaction-time
   queries, versioned edges or retention that differ from OSS Graphiti. The code is not available.
3. Runtime behaviour against a real graph DB. I did not run Neo4j/FalkorDB. The filter probe executed only the pure
   query-string constructor.
4. Whether the `search_config.limit` mutation actually changes invalidation-candidate counts in practice. This comes
   from code reading only.
5. How accurate the LLM-extracted valid_at/invalid_at values are. This depends on the model and was not measured.
