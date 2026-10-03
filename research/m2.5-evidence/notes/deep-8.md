# deep-8: ChronoMem (arXiv 2607.27773)

**ChronoMem: Version Control and Semantic Rollback for Large Language Model Agent Memory.**
Yongye Su (Purdue), Wujiang Xu (Rutgers), Chaoji Zuo (Rutgers), Elisa Bertino (Purdue).
arXiv cs.CL. v1 was posted 2026-07-30 and v2 on 2026-08-05; the v2 submitter was Wujiang Xu.
- Canonical: https://arxiv.org/abs/2607.27773
- HTML v2 (cited by readers, not fetched): https://arxiv.org/html/2607.27773v2
- Venue: preprint only. Two independent audits found no peer-reviewed venue: the ChaoYue0307 DBLP/Crossref audit and the mzayan version ledger.

## Access and evidence boundary (read this first)

- WebSearch budget was exhausted at the start of this task (200/200), and arxiv.org is blocked, so **I could not fetch the paper PDF or HTML myself.**
- Primary text I do have:
  - **The full arXiv abstract, verbatim.** Reproduced in several arXiv daily mirrors:
    - local copy `lit/repos/pf/daily/31-Jul-2026/NLP/README.md` (from CSQianDong/Awesome-arXiv-Daily-Reporter);
    - `lit/bo/daily.json`;
    - senna-lang/arxiv-compass `data/20260731.json`;
    - Luvata/arxive RSS. The RSS entries record v1 as "Announce Type: new" and v2 as "replace" on 2026-08-06.
  - **Paper sentences reproduced inside the Black-Lake whitepaper review.** The reviewer scraped the arXiv v1 HTML and PDF and pasted paper prose, including the section inventory and the Figure 1 caption fragment. Source: https://github.com/Delphoa/Black-Lake/blob/HEAD/.lake-data/DEP-A/Series%20002/DEP-A-20260819-ChronoMem%20Version%20Control/2607.27773-whitepaper-review.md
- Secondary full-text readings used for mechanism details and numbers:
  - **jenslaufer/field-notes**, "source: full text, arXiv HTML v2". Has the tables. https://github.com/jenslaufer/field-notes/blob/HEAD/papers/reading-list-2026-08-llm/2607.27773-chronomem.md
  - **mzayan-bit/Evolving-agent-memory** ("targeted primary inspection" of v2). Section pointers S3/S4/S5 and the benchmark row. https://github.com/mzayan-bit/Evolving-agent-memory (`research/literature/master_paper_matrix.md`, `benchmark_matrix.md`, `capability_matrix.md`, `source_manifest.json`)
- Raw copies are in `lit/deep8_raw/`.

**Code.** The abstract claims "the first open-source system and benchmark", but I could not locate a public repository.
- `git ls-remote` against 13 plausible names failed: YongyeSu/ChronoMem, WujiangXu/ChronoMem, chronomem/chronomem and others.
- PyPI has no `chronomem`, `chrono-mem` or `chronomem-adk` (all 404).
- GitHub code search for "semantic commit descriptor" finds only the two reviews.
- `google/adk-python` has no ChronoMem code. Its "rollback" hits are database transaction rollbacks in `sessions/database_session_service.py`.
- GitHub repository search returned 502 three times.
- Black-Lake and mzayan both report the same: "No official code, data, or project repository beyond the canonical paper records was verified" / "No own code/project URL verified in this review".
- "Integrated into ADK" therefore most likely means "built as a layer on ADK's memory interface", not merged upstream. **This is unverified.**

## Verbatim snippets

### Abstract (verbatim; arXiv listing as mirrored in daily digests)

> "existing agent memory systems are designed around forward-only evolution, continuously accumulating, consolidating, and overwriting knowledge, with no principled mechanism to inspect, version, or revert prior states. This makes agents brittle under corrections, concept drift, and memory corruption, particularly after they have already been exposed to subsequent information."

> "We present ChronoMem, a semantic version-control layer for agentic memory integrated into the production-ready, open-source Agent Development Kit by Google. ChronoMem commits whole-memory snapshots at each memory write, maintains structured version histories, and supports natural-language rollback requests by mapping undo intents to concrete historical versions through hybrid lexical and semantic retrieval, rank fusion, and reranking."

> "We further introduce a post-exposure evaluation protocol that tests whether an agent can behave counterfactually after rollback by answering queries and summarizing history as if future updates had never occurred."

> "On long-horizon conversational benchmarks augmented with evolving memory states and rollback tasks, ChronoMem substantially improves rollback-consistent question answering and history summarization relative to prompt-only and retrieval-only baselines, while achieving strong performance in semantic version selection. To our knowledge, ChronoMem is the first open-source system and benchmark for systematic semantic global memory rollback in LLM agents."

### Paper prose reproduced in the Black-Lake review (v1)

These read as verbatim paper text. They were not independently re-checked against arXiv.

> "Right: ChronoMem's memory-level semantic rollback enables a controlled memory state versioning (v_T → v_1), rolling back to previous memory state S(v_1) and enforcing historical consistency in subsequent reads." (Figure 1 caption fragment)

> "We propose the first open-source semantic global rollback mechanism for agent memory that maps natural-language "undo" requests to whole-memory versions, and implement an end-to-end rollback pipeline with verifiable integrity checks. To our knowledge, no existing open-source system offers whole-memory snapshots, commit-level versioning, or natural language driven semantic rollback integrated into a production-ready agent framework"

> "ChronoMem focuses on (i) defining a systems-level abstraction for global memory commits and rollback at the agent memory boundary, and (ii) implementing a semantic control plane that maps natural-language "undo" requests to concrete historical versions."

> "Unlike standard memory-agent evaluations that assume forward-only evolution, our setting introduces a structural state transition prior to task execution; we therefore evaluate ChronoMem along two orthogonal axes: (i) the correctness of semantic version resolution, and (ii) the behavioral correctness of the agent after state restoration."

> "This design reduces natural-language "undo" to a systems problem of NL → version resolution followed by a deterministic restore primitive, rather than relying on prompting or best-effort retrieval to suppress later information. Compared to the strongest baseline without global snapshot restoration, ChronoMem improves rollback-consistent QA and summarization by approximately 10 percentage points on average across datasets and backbone models."

> "Promising future directions include rollback-native benchmarks with more realistic user rollback intents, branching histories beyond linear truncation, and higher-concurrency memory backends with stronger multi-writer transactional semantics."

**Section inventory** (headings reproduced by Black-Lake):
- 3.2 Architecture Overview, including "Interface invariant."
- 3.3 Version Control and Semantic Rollback:
  - "State model: versions, snapshots, and the event log."
  - "Stage (1) Version construction: commit-on-write snapshots."
  - "Stage (2) Version index: semantic commit descriptors."
  - "Stage (3): NL → version mapping via hybrid retrieval."
  - "Stage (4): Version rollback execution (ID-based)."
- 4.1 datasets: LoCoMo; MemoryAgentBench (MAB); "Post-exposure rollback protocol."; "Rollback query construction."
- 4.2 metrics: semantic version selection (RQ1); rollback-consistent QA (RQ2); rollback-consistent summarization (RQ3).
- 4.3 baselines: "Prompt-only rollback."; "Full-history prompt rollback."; "Retrieval-only rollback (vector-db only)."
- Limitations: "Concurrency and transactional semantics."; **"Linear history only (no branching/merging)."**; "Benchmark adaptation and query generation."

### Mechanism details (jenslaufer full-text distillation of v2; paraphrase, not verbatim paper text)

- "**State model**: append-only event log + materialised snapshots + a `HEAD` pointer, in SQLite. Log-plus-snapshot avoids replaying the log on rollback (storage traded for restore speed). Explicit event-sourcing/ARIES lineage."
- "**Interface invariant**: after rollback to `v*`, every subsequent read is scoped to `v*` — no post-`v*` visibility."
- "**Semantic commit descriptor** per version: `{delta, summary, op, labels}`. Retrieval runs over these descriptors, not over snapshots or raw events"
- "**NL → version**: BM25 via SQLite FTS5 ∥ dense retrieval, fused with Reciprocal Rank Fusion (k₀ = 60), then a cross-encoder rerank (Cohere Rerank-3.5)."
- "**Rollback** truncates versions after the target — Git `reset`, not `revert`."
- "**Post-exposure protocol** ...: ingest the full stream to `v_T`, *then* ask to roll back, then run the task. The agent has already seen the later information and must behave as if it never arrived."
- "Limitations conceded: **linear history only** (no branching or merging), SQLite serialises writes and concurrency is never evaluated, and rollback queries are generated from ground-truth anchors so their distribution is not real user intent."
- mzayan adds: "MAB downstream QA restricted to Accurate Retrieval". It also notes as a limitation: "Global restoration does not preserve all independent later work".

### Numbers (jenslaufer, from the paper's tables)

Backbones are Llama-3.1-8B, Qwen2.5-7B and Mistral-7B.

**Version selection, Recall@1 / Recall@5 / Scope@2**

| Method | LoCoMo | MAB |
|---|---|---|
| BM25-only | 9.3 / 22.3 / 13.1 | 14.1 / 44.6 / 23.3 |
| Hybrid (RRF) | 12.0 / 28.1 / 17.9 | 24.3 / 53.8 / 40.5 |
| ChronoMem | 20.5 / 38.9 / 31.2 | 33.4 / 60.2 / 58.0 |

**Rollback-consistent QA F1, LoCoMo** (Llama / Qwen / Mistral)

| Condition | F1 |
|---|---|
| Prompt-only | 2.3 / 2.8 / 0.9 |
| Full-history | 19.3 / 20.6 / 13.5 |
| RAG-only | 28.9 / 27.1 / 19.4 |
| ChronoMem | 36.1 / 38.5 / 31.3 |

On MAB (Accurate Retrieval), ChronoMem scores 53.8 / 55.1 / 44.6.

**Caveats noted by jenslaufer:**
- The §5.1 prose for MAB Recall@1 (39.4) does not match Table 3 (33.4).
- "strong performance in semantic version selection" is relative to weak baselines; Recall@1 is 20.5% on LoCoMo.

## Capability ratings (only what ChronoMem itself provides)

| # | Capability | Rating | Evidence |
|---|---|---|---|
| 1 | immutable_historical_observations | partial | Append-only event log plus a whole-memory snapshot on every write. But rollback "truncates versions after the target — Git reset, not revert". What is versioned is the agent's memory writes, not raw environment observations. |
| 2 | historical_world_state | no | Versions the agent memory store only. No external world or tool-side-effect state. Global restore "does not preserve all independent later work" (mzayan). |
| 3 | historical_epistemic_state | yes (memory layer only) | Restores S(v*), and "every subsequent read is scoped to v*". The post-exposure protocol explicitly measures whether the agent answers "as if future updates had never occurred". The restore is destructive (HEAD moves back) rather than a side query. LLM context and parametric knowledge are not versioned. |
| 4 | historical_policy_objective_state | no | No versioning of goals, instructions, policy or model. |
| 5 | execution_checkpoints | partial | Restorable whole-memory snapshots plus a HEAD pointer. No session, context, tool or environment execution state. |
| 6 | replay | partial | Resumes from a restored memory version. The event log exists, but the design avoids replay ("avoids replaying the log on rollback"). There is no re-execution of the trajectory. |
| 7 | fork_from_historical_state | no | "Linear history only (no branching/merging)". Rollback truncates later versions. Branching is listed as future work. |
| 8 | counterfactual_action_branches | no | Its "counterfactual" means "as if later updates never occurred" (information removal), not alternative actions. |
| 9 | branch_provenance | no | No branches. Linear per-commit descriptors {delta, summary, op, labels} are commit-level provenance, not branch parent or divergence records. |
| 10 | explicit_current_belief_state | no | HEAD memory is whatever ADK memory holds. No structured beliefs, assumptions or requirements. |
| 11 | uncertainty_representation | no | Only reranker scores over candidate versions. No belief uncertainty. |
| 12–17 | prospective capabilities | no | Nothing prospective: no future rollout, branches over futures, probabilities, backward requirements, intervention-aware forecasting, or prevented-futures bookkeeping. |
| 18 | predicted_vs_realized | no | |
| 19 | cross_time_state_querying | partial | Every version's S(v) is materialised, and per-commit delta descriptors exist. NL query → version resolution is a "which version matches this description" query, and the history-summarization task is evaluated. But the exposed primitive is rollback (move HEAD), not a non-destructive state_at(t) or diff(t1,t2) API. Versions are commit-indexed. |
| 20 | unified_temporal_abstraction | no | Historical memory versions only. |

## How it threatens the project's novelty

1. **Strict epistemic cutoff / no-hindsight past self.** ChronoMem is direct, published prior art at the memory layer.
   - It has a hard interface invariant: reads after rollback are scoped to v*.
   - It has a named evaluation protocol, "post-exposure", that measures whether behaviour leaks information from after the cutoff once the agent has already seen it.
   - The project cannot claim either "reconstruct what the agent knew at t, excluding later info" or a "hindsight-leakage metric" as new. It must position against this protocol, and ideally reuse or adapt its metrics (rollback-consistent QA F1, version-selection Recall@k, Scope@2).
2. **The architectural-versus-prompting argument is already made with numbers.** Prompt-only "ignore later info" scores 0.9–2.8 F1 on LoCoMo, against 31–38 F1 for snapshot restore. This is the obvious empirical motivation the project would use for an explicit temporal state, and it is taken.
3. **Same substrate.** ChronoMem already ships the project's foundation: an append-only event log, a materialised snapshot per write, a HEAD pointer, an event-sourcing lineage, and NL-addressable versions.
4. **Baseline implication (CLAUDE.md rule 4).** A ChronoMem-style versioned memory with read-scoping is a natural part of a *strong* "checkpoint + RAG memory" baseline.
   - Suppose the project's temporal contestant beats a baseline that lacks per-write versioning and as-of read scoping.
   - A reviewer can then say the advantage comes from versioned memory, which ChronoMem already provides, not from "temporal agency".
   - The baseline should be configurable to include whole-memory snapshots plus as-of scoping.

## What ChronoMem does NOT cover (residual space)

- **Non-destructive temporal navigation.** Rollback is a Git reset with linear truncation. The agent cannot consult its past self and then return to the present with both kept. "Never overwrite time, fork it" is not covered here, though LangGraph, AgentGit, Shepherd and ActiveGraph cover forking elsewhere.
- **Direction of the benchmark.** ChronoMem *suppresses* later information to behave as of the past. The project's benchmark asks the agent to *use* a later event to re-evaluate the significance of an earlier decision and reopen or remediate it. That is hindsight-driven revision, the opposite operation. ChronoMem's tasks are conversational QA and summarization on LoCoMo and MAB, not agentic decisions with consequences.
- **Who triggers rollback.** It is triggered by an explicit user NL undo request. Rollback queries are generated from ground-truth anchors. There is no agent-initiated detection that something should be revisited.
- **What is versioned.** No world-state vs epistemic-state separation. No policy, objective or identity history. No structured belief, assumption or requirement state. No uncertainty.
- **The prospective half is absent.** No future rollouts, backward requirements, prevented-future bookkeeping, or predicted-vs-realized comparison.
- **Version selection is weak.** Recall@1 is 20.5% on LoCoMo and 33.4% on MAB. Selection is the hard part: an "as-of" interface addressed by exact time or event id avoids it entirely. MidMem and jenslaufer both reject NL rollback for this reason.

## Adjacent work seen in passing (context only, not analyzed)

Same "memory transactions / rollback" cluster. These URLs are as they appear in the secondary sources above and were not deep-read:
- MemTX, transactional belief commit: https://arxiv.org/abs/2607.23929
- MemTxn: https://arxiv.org/abs/2607.27834
- TARL: https://arxiv.org/abs/2608.03699
- Dependency-guided rollback repair: https://arxiv.org/abs/2608.10502
- Execution-state unlearning: https://arxiv.org/abs/2609.04875 ("ChronoMem restores global store snapshots; rollback repair preserves independent descendants under explicit lineage" — mzayan deep read)
- Nocturne Memory, a rollbackable graph memory MCP server: https://github.com/Dataojitori/nocturne_memory

AgentRewind, RIR and DeepRewind are already in `sweep-exec-state.md`.

## Could not verify

- Paper PDF/HTML not fetched (arxiv blocked; search budget exhausted). Mechanism details and numbers come from secondary full-text readers.
- The code repository was not found, so the open-source claim is unverified.
- The exact meaning of "integrated into ADK" is unverified: there is no upstream ADK code.
- Whether truncated versions are physically deleted or only made unreachable from HEAD.
- Whether rollback itself is logged as an event.
- Whether timestamps support wall-clock as-of queries.
- The exact definition of Scope@2.
