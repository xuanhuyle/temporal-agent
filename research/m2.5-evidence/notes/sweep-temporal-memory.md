# Sweep: temporal-memory lane

Scope: temporal and versioned memory for agents, and its database foundations: bitemporal databases, event sourcing,
Git-for-data, and W3C PROV.
Date of sweep: 2026-10-03.

## Method and evidence caveats (read first)

- **WebSearch was unavailable.** The session-wide budget (200/200) was already used up by sibling lanes. My first 3
  WebSearch calls returned "Web search was not performed". Nothing below comes from WebSearch run by this lane.
- **Other search routes were blocked:**
  - GitHub MCP `search_repositories`: 502, twice.
  - api.github.com search: "sessions are bound to their configured repositories".
  - PyPI search: JavaScript client challenge.
  - Most other hosts (w3.org, docs.xtdb.com, docs.datomic.com, wikipedia, dblp, crossref, openalex): no connection.
- **What worked:** raw.githubusercontent.com, `git clone` from github.com, and PyPI per-package JSON. The substitute
  search corpus was 17 curated "awesome" paper and tool lists, fetched raw. The main one is
  **IAAR-Shanghai/Awesome-AI-Memory** (https://github.com/IAAR-Shanghai/Awesome-AI-Memory, README fetched 2026-10-03,
  1,085 dated entries, 928 of them from 2026; each entry has an arXiv link and a 3-bullet Chinese summary). I parsed it to
  `verify/awesome/iaar.tsv` and ran local regex queries over titles and summaries.
- **Evidence grades:**
  - [repo-verbatim]: text copied from a cloned or raw-fetched primary repository. This is the strongest evidence here.
  - [list-verbatim-zh] + [my translation]: the curated list's Chinese summary of an arXiv paper, followed by my English
    translation. I did NOT read these papers' abstracts. Numbers come from the list summary and may contain list errors.
    Treat them as secondary and re-verify against arXiv before quoting them in any document.
  - [sibling-search]: a URL recorded by another lane's WebSearch in `notes/sweep-belief-state.md` or
    `notes/sweep-exec-state.md`. Cited only as context, not re-verified.
- **Raw evidence files:** `scratchpad/lit/verify/readmes/*.md` (READMEs), `scratchpad/lit/verify/awesome/*.md` (lists),
  `verify/awesome/selected_summaries.tsv`.
- **Clones:** `scratchpad/lit/repos/{xtdb (docs sparse), day-of-datomic, eventsourcing (docs sparse), prov, memvara}`.

---

## Ranked works

### 1. Memvara: bitemporal memory for AI agents, plus its cross-system Agent Memory Benchmark. Threat: HIGH
- Links: https://github.com/memvara/memvara ; https://pypi.org/project/memvara/ ; clone at commit f263e3f
  (2026-10-01, "Release 0.19.0").
- Found by: the belief-state lane found it first. I re-read the README and `docs/benchmarks/agent-memory-benchmark.md`
  for new evidence.
- [repo-verbatim]
  - `mem.get_all(valid_at=T)   # what we believe TODAY about how the world was at T`
  - `mem.get_all(known_at=T)   # what we believed at T, about the world as it is now`
  - `mem.get_all(as_of=T)      # both clocks at T — what we believed at T, about T`
- [repo-verbatim] "| **Historical** | `search`, `get_all`, `history` and five more reads take `as_of=`, `valid_at=` or
  `known_at=`, so *what was true then* is a query rather than a reconstruction. |"
- [repo-verbatim, benchmark doc] The systems compared:
  - "`vector-rag` | Retrieval over the whole write log, with **one clock**: it keeps every observation and answers a
    question about a past instant with the most recent write it had received by then. The strongest baseline that is
    not bitemporal."
  - "Neither baseline is built to lose. `vector-rag` is completely correct on current state, provenance, change time
    and knowledge time."
- [repo-verbatim, results by category]
  - historical_state: memvara 100.0%, vector-rag 85.2%, naive 33.3% (n=27).
  - knowledge_time: 100.0 / 100.0 / 42.9 (n=7).
  - multi_hop: memvara 16.7%, vector-rag 33.3%.
- [repo-verbatim] "**The claim this supports is not "bitemporal memory is better at remembering." It is "when news
  arrives after the fact, a single clock has to give one answer to two different questions, and roughly nine per cent
  of realistic temporal questions are that case."**"
- [repo-verbatim, on mem0 2.x] "2.x's add path emits only `ADD` events, and its prompt says "Your sole operation is
  ADD". Conflicting values are **linked**, never retired." Also: "**There is no time.** One `updated_at` column can't
  answer "where did she live in March?""
- Why it matters:
  - It provides the transaction-time vs valid-time as-of API for agent memory, in shipping code.
  - Its benchmark is the closest existing analogue of "temporal memory vs strong RAG". It reports that an append-only,
    timestamped, single-clock RAG over the write log already answers "what did we know at T" (knowledge_time 100%).
    Bitemporality only separates the systems on late-arriving or corrected facts, about 9% of temporal questions.
  - This directly undermines the idea that explicit temporal navigation beats a strong checkpoint+RAG baseline, unless
    the scenarios are dominated by late or retroactive information.
  - Caveat: the corpus was authored by the Memvara maintainers, and the README says so.
- Capabilities: 1, 2, 3, 10, 19.

### 2. MemStrata: "Temporal Validity in Retrieval Memory: Eliminating Stale-Fact Errors for AI Agents over Evolving Knowledge" (arXiv 2606.26511, 2026-06-25). Threat: HIGH
- URL: https://arxiv.org/pdf/2606.26511v1
- Found by: IAAR list, query `tempor|time|...` on titles.
- [list-verbatim-zh] "MemStrata 通过在双时态账本中的确定性（主语、关系、宾语）取代规则来维护时效性——无需相似度阈值、读取路径上无需调用
  LLM 即可淘汰陈旧事实——并有一个证明支撑：余弦相似度无法区分矛盾与重复（AUROC 0.59）。"
  "在演化知识（代码重命名、配置/依赖/API 变更）下保持智能体记忆最新" "在静态知识上与 RAG 打平，但在演化知识上达到
  0.95–1.00 准确率，而 RAG 仅为 0.20–0.47（2–5× 提升），将陈旧事实错误率从 15–40% 降至约 0%"
- [my translation]
  - MemStrata keeps memory current with deterministic (subject, relation, object) supersession rules in a
    **bitemporal ledger**. Stale facts are retired with no similarity threshold and no LLM call on the read path.
  - The authors prove that cosine similarity cannot separate contradiction from duplication (AUROC 0.59).
  - The target is evolving software knowledge: code renames, config, dependency and API changes.
  - It ties RAG on static knowledge. On evolving knowledge it scores 0.95-1.00 vs RAG 0.20-0.47, and cuts stale-fact
    errors from 15-40% to about 0%.
- Why it matters:
  - This is a temporal-validity memory vs RAG comparison in the project's own domain, a software world with evolving
    facts.
  - It has already reported the "temporal beats RAG" result, for fact QA and not for decision reopening.
  - The RAG baseline appears to be similarity-only, so it is not the strong as-of-filtered baseline that Memvara's
    benchmark uses.
- Capabilities: 1, 2, 10, 19. Code: unknown.

### 3. XTDB: general-purpose bitemporal database (open source; docs in repo). Threat: HIGH (foundational abstraction)
- Links: https://github.com/xtdb/xtdb ; docs source `docs/src/content/docs/about/time-in-xtdb.md` (sparse clone, commit
  af3e974, 2026-09-30).
- [repo-verbatim, README] "XTDB is a general purpose database with bitemporal indexes." "assembled from decoupled
  components through the use of an immutable log and document store at the core of its design."
- [repo-verbatim, time-in-xtdb.md] "You might also hear system-time referred to 'transaction time' or 'processing
  time'." "In short, any time you hear the phrase 'as of' or 'with effect from' in a requirement, the answer is
  probably 'valid time'."
- [repo-verbatim] "When you are looking to query back in time, consider: 'do I want to see corrections?'. ... Some use
  cases (e.g. auditing) will need to see the data 'as we knew it at the time', _without_ subsequent corrections - this
  is the use case for `FOR SYSTEM_TIME AS OF ...`, to see the immutable system-time timeline."
- [repo-verbatim, worked example] "1. The first row shows that, until 13th August, we believed that Mike's address was
  going to be 123 London Road until further notice. 2. From 13th August, we knew that ..."
- [repo-verbatim, point-in-time-feature-extraction.md] "description: Build leakage-free training matrices with one
  bitemporal SQL query." and "The `FOR VALID_TIME` clause picks the right version *in the timeline*;
  `SETTING DEFAULT SYSTEM_TIME` picks the right *timeline*."
- [repo-verbatim, backtesting.mdx] "The backtesting processes are able to simulate querying as-of successive moments in
  time by efficiently querying the entire database without the need for explicit snapshots"
- [repo-verbatim] Henderson's Tenth Law: "Any sufficiently complicated data system contains an ad-hoc,
  informally-specified, bug-ridden, slow implementation of half of a bitemporal database."
- Why it matters:
  - Two of the project's notions are XTDB's system-time vs valid-time distinction: "historical epistemic state with a
    strict cutoff (no hindsight)" and "reconstruct world state at t".
  - XTDB names the leakage-free / backtesting use case explicitly. That is the same no-hindsight requirement in
    database form.
- Capabilities: 1, 2, 3, 19.

### 4. Datomic: as-of / since / history database values, speculative `d/with`, transaction provenance. Threat: MEDIUM (foundational)
- Links: https://github.com/Datomic/day-of-datomic (official tutorial code, clone at daa457f, 2024-06-04) ;
  https://github.com/Datomic/mbrainz-sample
- [repo-verbatim, mbrainz README] "Datomic is a database of flexible, time-based facts, supporting queries and joins
  with elastic scalability, and ACID transactions."
- [repo-verbatim, tutorial/filters.clj]
  `(def as-of-eoy-2013 (d/as-of db #inst "2014-01-01"))` `(def since-2014 (d/since db #inst "2014-01-01"))`
  `(def history (d/history db))`. It also filters out error transactions:
  `(def corrected (d/filter history correct?))`.
- [repo-verbatim, tutorial/provenance.clj] ";; what was the title as of earlier point in time?
  (:story/title (d/entity (d/as-of db tx) story))" ";; who changed the title, and when?" (transaction entity carries
  `:source/user`).
- [repo-verbatim, tutorial/constructor.clj] ";; another database *value*
  (def db-with-jdoe (:db-after (d/with db [construct-jdoe])))". `d/with` applies a transaction speculatively, giving a
  hypothetical database value without committing it.
- Why it matters:
  - Datomic offers database-as-an-immutable-value, as-of a past transaction, and provenance attached to transactions.
  - It also offers speculative "what-if" database values that are never committed. That is a counterfactual branch at
    the storage level.
  - I did not verify how Datomic handles valid time this session. The tutorial's as-of is keyed by transaction
    instant/txid.
- Capabilities: 1, 2, 3, 8, 9, 19.

### 5. Event sourcing (Python `eventsourcing` library as the reference implementation). Threat: MEDIUM (foundational)
- Links: https://github.com/pyeventsourcing/eventsourcing ; https://pypi.org/project/eventsourcing/ ; docs sparse clone.
- [repo-verbatim, docs/topics/application.rst] "The ``version`` argument is optional, and represents the required
  version of the aggregate." `dog_v1: Dog = dog_school.repository.get(dog_id, version=1)`
- [repo-verbatim, docs/topics/introduction.rst:365] "event sourcing is simply a left-fold over a stream of events"
- [repo-verbatim, README] "**Snapshotting** — reduces access-time for aggregates that have many events."
- The docs cite Martin Fowler (domain.rst: "Martin Fowler's 2005 ...").
- Related agent-side adoption ([sibling-search], exec-state lane): the OpenHands SDK states "every interaction ... as
  an immutable event appended to a log" and "reconstruct the state at any time by replaying the event log"
  (https://arxiv.org/pdf/2511.03690). ActiveGraph (2605.21997) makes "the append-only event log ... the source of
  truth".
- Why it matters:
  - Append-only observations, replay, and state-at-version reconstruction are the standard event-sourcing pattern.
    Snapshots are a cache over the log.
  - Checkpoints-plus-log is the canonical design, not a strawman.
- Capabilities: 1, 2, 5, 6, 19.

### 6. W3C PROV data model (via the `prov` Python reference implementation). Threat: LOW (foundational vocabulary)
- Links: https://github.com/trungdong/prov ; https://pypi.org/project/prov/ ; spec link in README
  https://www.w3.org/TR/prov-dm/ (w3.org itself unreachable from sandbox).
- [repo-verbatim, README] "A Python implementation of the [W3C PROV Data Model](https://www.w3.org/TR/prov-dm/)" and
  "In-memory classes for every PROV-DM record type".
- [repo-verbatim, src/prov/model/records.py] `def wasInvalidatedBy(` (line 1169), `def wasRevisionOf(` (line 1275),
  `PROV_INVALIDATION`, and `def bundle(self) -> ProvBundle`.
- Why it matters: the standard already covers
  - provenance of derivations (wasDerivedFrom/wasRevisionOf),
  - invalidation of entities by activities (wasInvalidatedBy),
  - attribution, and
  - bundles (provenance of provenance).

  So "branch provenance: parent, reason, action" is expressible in a 2013 W3C vocabulary. The project would need to
  justify any bespoke provenance schema against it.
- Capabilities: 9.

### 7. Dolt (and lakeFS): Git-for-data, with fork/branch/merge/diff of database state. Threat: MEDIUM (foundational)
- Links: https://github.com/dolthub/dolt ; https://github.com/treeverse/lakeFS
- [repo-verbatim, Dolt README] "Dolt is a SQL database that you can fork, clone, branch, merge, push and pull just like
  a Git repository." "A Dolt commit allows you to time travel and see lineage." And
  `select * from dolt_diff('main', 'modifications', 'employees');`
- [repo-verbatim, lakeFS README] "lakeFS exposes a Git-like interface to data that allows keeping track of more than just
  the current state of data. This makes reproducing its state at any point in time straightforward." "With lakeFS you can
  create branches, and get a copy of the full production data, without copying anything."
- Why it matters:
  - The slogan's "fork it, never overwrite" half is Git semantics applied to state, productized for databases and data
    lakes: branch from a commit, diff two branches, merge, keep lineage.
  - Agent-side versions exist ([sibling-search]): AgentGit "Non-Destructive Branching: Rollbacks create new branches,
    preserving all timelines"; GCC COMMIT/BRANCH/MERGE; ActiveGraph fork-at-event.
- Capabilities: 1, 5, 6, 7, 9, 19.

### 8. "From Faulty Memories to Corrected Actions: Dependency-Guided Rollback Repair for Memory-Augmented Agents" (arXiv 2608.10502, 2026-08-11). Threat: HIGH (for the benchmark behaviour)
- URL: https://arxiv.org/pdf/2608.10502
- Found by: IAAR list, query `version|history|snapshot|rollback|...` on titles.
- [list-verbatim-zh] "在诊断记忆故障后修复回答及持久状态。 依赖图使无依据的后继失效，并选择性回放受影响计算。
  受控及轨迹派生测试改善恢复，同时保留正常记忆。"
- [my translation] After a memory fault is diagnosed, it repairs both answers and persistent state. A dependency graph
  invalidates successors that lost their support and selectively replays the affected computations. Controlled and
  trajectory-derived tests show better recovery while normal memories are preserved.
- Why it matters: "a later finding invalidates an earlier memory -> reopen and remediate downstream outputs and state"
  is the project benchmark's target behaviour. Here it is already a method with an evaluation.
- Same family:
  - StateGuard (2609.34134, https://arxiv.org/pdf/2609.34134): "显式维护长程分析状态的有效性 ... 用图表示依赖，并从反事实轨迹学习核验与修复
    ... 减少陈旧分析产物向下游传播" (explicitly maintains validity of analysis state; dependency graph; learns
    verification/repair from counterfactual trajectories; reduces propagation of stale analysis artifacts).
  - Execution-State Unlearning (2609.04875, https://arxiv.org/pdf/2609.04875): "根据来源恢复检查点，并通过净化回放重建受影响的后续过程"
    (restores the checkpoint by provenance and rebuilds affected later steps via sanitized replay).
- Capabilities: 5, 6, 10.

### 9. "Impact Is Not Invalidation: Ask About the Claim, Not the Diff" (arXiv 2609.25130, 2026-09-20). Threat: MEDIUM
- URL: https://arxiv.org/pdf/2609.25130
- Found by: IAAR list, query `stale|...|invalidat|...`.
- [list-verbatim-zh] "该研究评估仓库变化后，编码智能体存储的记忆断言何时失效。 通过执行验证断言翻转，将针对具体断言的失效判断与一般行为变化检测区分开。
  基于 23 个 Python 库的 10,369 条断言，针对断言提问的精确率为 0.705–0.974，针对差异整体判断则为 0.291–0.329。"
- [my translation]
  - It evaluates when a coding agent's stored memory assertions become invalid after repository changes.
  - Claim flips are verified by execution, which separates per-claim invalidation from general behaviour-change
    detection.
  - Across 10,369 assertions from 23 Python libraries, asking about the specific claim reaches precision 0.705-0.974.
    Judging the whole diff reaches only 0.291-0.329.
- Why it matters:
  - The setting is a software world where a later change alters the validity of an earlier stored belief, with
    execution-verified ground truth. It is close to the project's benchmark premise.
  - It suggests the winning mechanism is claim-targeted re-checking, not temporal navigation per se.
- Capabilities: 10, 19.

### 10. GitHarness: "Git Init Your Harness Working Memory for Perpetual User Requirements" (arXiv 2609.36789, 2026-09-29). Threat: MEDIUM
- URL: https://arxiv.org/pdf/2609.36789
- Found by: IAAR summaries, query `版本|快照|...` and `分支|...`.
- [list-verbatim-zh] "把需求及对应工作状态组织为可分支的版本记忆，保留仍有效的历史成果。 Git Agent 学习识别变化并选兼容历史状态，通过统一恢复与分支接口排除旧信息。
  MTAgentBench 跨五类任务报告效果、有效工作保留和执行效率改善；摘要未给统一数值。"
- [my translation]
  - Requirements and their work state are organized as branchable, versioned memory, and still-valid historical results
    are kept.
  - A Git Agent learns to recognize requirement changes and pick a compatible historical state. A unified restore/branch
    interface excludes stale information.
  - MTAgentBench reports gains across five task types; no unified numbers in the summary.
- Why it matters: when requirements change, the agent navigates to a compatible past state and forks from it. That is
  temporal navigation driven by a later event, with a benchmark.
- Capabilities: 5, 6, 7, 9, 19.

### 11. Mem++: "Non-Destructive Memory for Long-Term Organizational LLM Agents" (arXiv 2610.02002, 2026-10-01). Threat: MEDIUM
- URL: https://arxiv.org/pdf/2610.02002
- Found by: IAAR summaries, query `版本|...`.
- [list-verbatim-zh] "完整保留含作者和日期的组织文档及旧版本，将选择推迟到查询时。 Mem++ 写入不调用生成模型，读取时按问题时间过滤并融合词法、语义排名，由回答模型判断有效版本。
  OrgMemBench 上比最强记忆基线高 8.0–13.1 分；其他会话基准排名随变体和回答模型变化。"
- [my translation]
  - It keeps organizational documents and their old versions in full, with author and date, and defers selection to
    query time.
  - No generative model is called on write. Reads filter by the question's time, fuse lexical and semantic ranks, and
    let the answer model decide which version is valid.
  - It scores +8.0-13.1 over the strongest memory baseline on OrgMemBench. On other conversational benchmarks, rankings
    vary with the variant and the answer model.
- Why it matters:
  - "Never overwrite; resolve at query time by time" is the memory half of the slogan, published as a system with an
    evaluation.
  - Its advantage is benchmark-dependent. That is a caution for the project's comparative hypothesis.
- Capabilities: 1, 2, 19.

### 12. TOKI: "A Bitemporal Operator Algebra for Contradiction Resolution in LLM-Agent Persistent Memory" (arXiv 2606.06240, 2026-06-04). Threat: MEDIUM
- URL: https://arxiv.org/abs/2606.06240
- Found by: IAAR list (bitemporal grep). The belief-state lane also hit it via WebSearch.
- [list-verbatim-zh] "将持久化智能体记忆中的矛盾解决视为写入时一致性问题。 定义双时态操作代数，显式给出隔离假设、来源标注和审计行。
  明确生产级记忆系统在信念演化或冲突时所需的正确性契约。"
- [my translation] It treats contradiction resolution in persistent agent memory as a write-time consistency problem. It
  defines a bitemporal operator algebra with explicit isolation assumptions, provenance annotation and audit rows. It
  states the correctness contract that production memory needs when beliefs evolve or conflict.
- [sibling-search extract] "provenance annotation that preserves the losing fact in an audit row"; it names anomalies
  "replay inconsistency, belief-drift skew, and audit erasure".
- Why it matters: it is a formal semantics for belief evolution over two time axes in agent memory. Any "temporal
  agency" formalism would be compared with it.
- Capabilities: 1, 3, 19.

### 13. kaeru (and Talamus): bitemporal agent-memory tools with as-of reads. Threat: LOW (existence proof, pre-1.0)
- Links: https://github.com/LamantinAI/kaeru ; https://github.com/ampres-ai/talamus
- Found by: TsinghuaC3I/Awesome-Memory-for-Agents and TeleAI-UAGI/Awesome-Agent-Memory (bitemporal grep).
- [repo-verbatim, kaeru] "Every node and edge is **bi-temporal** — the substrate stores assertion / retraction history
  natively, so time-travel queries are out of the box and conflict resolution is non-destructive (the old version is
  invalidated, not deleted)."
- [repo-verbatim, kaeru] "`at` reads a node in full as it is now or as-of any past moment"
- [repo-verbatim, kaeru] "**`audit_event` is a first-class node type** — every mutation writes an audit node, so changes
  to memory themselves become reasoning surface for the agent."
- [repo-verbatim, kaeru] "Substrate is CozoDB with RocksDB backend; bi-temporal `Validity` is native to the substrate"
- [repo-verbatim, Talamus] "**TIME**: notes have version history, facts have valid-time windows, and
  `talamus ask --as-of 2026-01` answers from the brain as it was."
- Why it matters: as-of memory reads for coding agents over MCP are a commodity feature in 2026. Kaeru also exposes the
  memory's own mutation history to the agent as a reasoning surface.
- Capabilities: 1, 2, 3, 9, 19.

### 14. "The Immutable Past: Formalizing State Mutability and Conflict Resolution in Mutable RAG" (GC-Mem; arXiv 2609.16073, 2026-09-13). Threat: MEDIUM
- URL: https://arxiv.org/pdf/2609.16073
- Found by: IAAR list, queries `provenan|...|immutable|...` and `conflict|...`.
- [list-verbatim-zh] "GC-Mem 处理追加式智能体记忆中旧事实压过当前状态的问题。 利用时间支配关系与矛盾检测，移除已被取代的证据，同时保留无关但仍有效的长期记录。
  作者在其累积式基准上报告超过 90% 的冲突解决准确率，并给出部署所需的精确率与召回率条件。"
- [my translation] It addresses old facts overpowering current state in **append-only** agent memory. It uses temporal
  dominance and contradiction detection to remove superseded evidence from use while keeping unrelated valid long-term
  records. It reports more than 90% conflict-resolution accuracy on its cumulative benchmark, plus precision/recall
  conditions needed for deployment.
- Why it matters:
  - It formalizes the downside of "never overwrite": append-only memory without supersession semantics hurts current
    answers.
  - The fix is temporal dominance, which is a valid-time / transaction-time rule.
- Capabilities: 1, 10.

### 15. "Correct Now, Insufficient Later: Auditing Update Sufficiency in Context Compression" (arXiv 2609.20045, 2026-09-17). Threat: MEDIUM
- URL: https://arxiv.org/pdf/2609.20045
- Found by: IAAR list, query `provenan|audit|...`.
- [list-verbatim-zh] "提出更新充分性：即使压缩记忆能正确回答当前问题，也应保留未来更新所需的历史差异。
  构造当前答案相同、后续更新相同但未来正确答案不同的成对历史，开展小规模合成审计。 发现当前回答正确仍可能掩盖更新证据丢失，并识别标识符捷径；尚未验证在自然任务上的泛化。"
- [my translation]
  - It proposes "update sufficiency": even when compressed memory answers the current question correctly, it should
    keep the historical differences that future updates will need.
  - It builds paired histories with the same current answer and the same later update but different future correct
    answers, in a small synthetic audit.
  - Finding: correct current answers can mask lost update evidence. It also identifies identifier shortcuts.
    Generalization to natural tasks is not yet verified.
- Why it matters:
  - This is the strongest prior statement of the project's core intuition: a checkpoint or summary that is right now
    can be wrong for a later event that changes what the earlier history means.
  - Its paired-history design is a ready-made template for a leakage-controlled benchmark.
  - It pre-empts that argument as novel.
- Capabilities: 1, 18 (partial: later-correctness audit of earlier compression).

---

## Also seen (lower relevance or secondary); URLs from the fetched lists
- Supersede (2606.27472) https://arxiv.org/pdf/2606.27472v1. [zh summary, translated] "bounded memory drops gpt-5.4
  knowledge-update accuracy from 92% to 77% (p=0.0033)". RL environment rewarding fact timeliness on the LongMemEval
  knowledge-update subset.
- TARL: Transaction-Aware Reliable Ledgers (2608.03699) https://arxiv.org/pdf/2608.03699. Five executable memory-update
  actions. "时间范围和来源可靠性决定声明进入接受、待定或拒绝记录" (time range and source reliability route claims to
  accepted / pending / rejected ledgers).
- TEPA: Revoking Stale Memories (2608.07429) https://arxiv.org/pdf/2608.07429. "同键矛盾使过时先例失效，同时保留审计历史"
  (a same-key contradiction invalidates the stale precedent while audit history is kept).
- SodaMem (2608.08055) https://arxiv.org/pdf/2608.08055. Graph memory that tracks evidence source and temporal validity.
- REAL (2606.10694) https://arxiv.org/pdf/2606.10694. "非破坏性更新机制，允许同一事实的多版本并存" (non-destructive
  updates; multiple versions of a fact coexist).
- Memanto (2604.22085) https://arxiv.org/abs/2604.22085. "时间版本控制机制 ... supersede 机制保留历史状态" (temporal
  versioning; supersede keeps historical state).
- Tenure (2605.11325) https://arxiv.org/abs/2605.11325. Typed belief schema with epistemic status and "版本化的取代机制"
  (versioned supersession); BM25 1.0 vs dense 0.12 on a 72-case suite.
- Don't Ask the LLM to Track Freshness (2606.01435) https://arxiv.org/abs/2606.01435. Version-aware deterministic
  aggregation.
- LSREP longitudinal state-replay protocol (2609.16730) https://arxiv.org/pdf/2609.16730. "ICE v2 在公开诊断中落后于向量
  RAG" (the audited local-first architecture lags vector RAG on the public diagnostic). This is another data point
  where structured memory does not beat RAG.
- MemRiskBench (2609.14976) https://arxiv.org/pdf/2609.14976. Deterministic checks for stale facts, conflicts, leakage,
  revocation and constraint decay over memory traces.
- HINDSIGHT is 20/20 (2512.12818) https://arxiv.org/abs/2512.12818. Four networks including "不断演化的信念"
  (evolving beliefs); TEMPR temporal entity memory.
- ForeDreamer (2608.20920) https://arxiv.org/pdf/2608.20920. Future-event prediction with memory over "受时间截点约束的网页证据"
  (time-cutoff-constrained web evidence); Brier scores on Prophet Arena. Relevant to forecasting under a cutoff.
- Mem0 (2504.19413) https://arxiv.org/abs/2504.19413 ; README [repo-verbatim, April 2026 algorithm]:
  - "**Single-pass ADD-only extraction** -- one LLM call, no UPDATE/DELETE. Memories accumulate; nothing is
    overwritten."
  - "**Temporal Reasoning** -- time-aware retrieval that ranks the right dated instance for queries about current
    state, past events, and upcoming plans."
- A-MEM (2502.12110) https://github.com/agiresearch/A-mem ; README [repo-verbatim] "Enables dynamic memory evolution and
  updates", "Updates tags and context based on related memories", `memory_system.update(memory_id, content=...)`,
  "Timestamp tracking". This is in-place evolution; the README shows no as-of API.
- MemoryOS (2506.06326) https://github.com/BAI-LAB/MemoryOS ; README [repo-verbatim] "User profile insights are extracted
  and used to update the long-term user profile." Hierarchical with heat-based promotion; no as-of API in README.
- MemOS (2507.03724, 2505.22101) https://github.com/MemTensor/MemOS ; README [repo-verbatim] "Memory Feedback &
  Correction: Refine memory with natural-language feedback—correcting, supplementing, or replacing existing memories
  over time."
- Letta / MemGPT (2310.08560) https://github.com/letta-ai/letta ; README [repo-verbatim] "Build stateful agents with
  memory that can learn and improve over time." The README is minimal; temporal features were not verified.
- MIRIX (2507.07957) https://github.com/Mirix-AI/MIRIX ; README [repo-verbatim] "Auto-dream reviews existing memories,
  merges duplicates, resolves stale/conflicting entries where possible, and writes the result back through the memory
  tools."
- LangMem https://github.com/langchain-ai/langmem ; [repo-verbatim] "Background memory manager that automatically
  extracts, consolidates, and updates agent knowledge".
- Memory-R1 (2508.19828) https://arxiv.org/abs/2508.19828. Title and authors confirmed via 5 lists. Its memory
  operation set was NOT verified this session.
- LongMemEval (2410.10813) https://github.com/xiaowu0162/LongMemEval ; [repo-verbatim] five abilities include "Knowledge
  Updates" and "Temporal Reasoning"; question types `knowledge-update` and `temporal-reasoning`.
- TReMu (2502.01630) https://arxiv.org/pdf/2502.01630. Neuro-symbolic temporal reasoning over multi-session memory.
- MemoTime (2510.13614) https://arxiv.org/abs/2510.13614. Memory-augmented temporal KG reasoning.
- Timeline-based memory management (NAACL 2025) https://aclanthology.org/2025.naacl-long.435.pdf
- TimeChara (2405.18027) https://arxiv.org/abs/2405.18027. Point-in-time character hallucination in role-play: an
  epistemic-cutoff evaluation in another domain.
- Sibling-lane hits in the same lane, not re-verified:
  - TGMS bi-temporal graph management system (2607.10265); correction probes 0.897 vs 0 latest-state vs 0.154
    vector-RAG.
  - Graph-Native Bitemporal Memory Store (2607.26520).
  - ChronoMem (2607.27773), also in the IAAR list: "通过完整记忆快照和混合检索将自然语言撤销请求映射至版本".
  - Kumiho (2603.17244).

---

## Lane questions

### Q1. Which existing systems support querying memory as-of a past transaction time ("what the agent knew then") vs valid time?

**Databases (both axes, decades-old abstraction)**
- XTDB is bitemporal by default. `FOR SYSTEM_TIME AS OF` gives "as we knew it at the time, without subsequent
  corrections". `FOR VALID_TIME AS OF` gives the corrected world timeline. The docs separate auditing/backtesting
  (system time) from "as best known" (valid time) and sell "leakage-free training matrices".
- Datomic: `d/as-of` on a transaction instant/txid, `d/since`, `d/history`, and transaction-level provenance attributes.
  `d/with` gives a speculative, uncommitted database value. Its valid-time story was not verified here.
- Event-sourced stores give transaction-time reconstruction (`repository.get(id, version=N)`) and no valid time unless
  it is modelled.
- Dolt and lakeFS give commit-level time travel plus branch/diff/merge. Their history is transaction-time.

**Agent memory with an explicit transaction-time ("known at") axis**
- Memvara: `known_at=`, `valid_at=`, `as_of=` on every read.
- kaeru: native assertion/retraction `Validity`; `at` reads as-of any past moment.
- Talamus: `--as-of`, plus valid-time windows on facts.
- TOKI: bitemporal operator algebra with audit rows.
- MemStrata: bitemporal ledger, judging from the list summary.
- Covered by sibling lanes or elsewhere: Graphiti/Zep (bitemporal edges, analyzed separately), TGMS (2607.10265:
  "reconstruction of prior belief states", 0.897 vs 0.154 for vector-RAG), Graph-Native Bitemporal Memory Store
  (2607.26520).
- Version-snapshot rather than true bitemporal (transaction time only): ChronoMem (whole-memory snapshots per write,
  post-exposure "as if future updates never occurred" test), GitHarness, AgentGit, ActiveGraph fork-at-event.
- Mem++ keeps every dated version and filters "按问题时间" (by the question's time). That is document/valid time. Its
  transaction axis is unclear.

**Mainstream memory without as-of querying (by README evidence)**
- Mem0 2.x: ADD-only, "nothing is overwritten", time-aware ranking. Per Memvara, Mem0 has no as-of and "One `updated_at`
  column".
- A-MEM: in-place "memory evolution" with `update()`/`delete()`.
- MemoryOS: profile updated in place.
- MemOS: correct/replace via feedback.
- MIRIX: auto-dream "writes the result back".
- LangMem: "consolidates, and updates".
- Letta: not verified.
- Memory-R1: operation set not verified.

**Key empirical point against the project's comparative thesis**
- In Memvara's cross-system benchmark, the single-clock vector-RAG answers past-instant questions with "the most recent
  write it had received by then". It scores **100% on knowledge_time**, current state, change time and provenance.
- Bitemporal memory wins only on historical_state (100 vs 85.2), driven by four delayed-knowledge/correction
  questions, about 9% of temporal questions.
- So "what the agent knew then" is already delivered by any append-only, timestamped log with an ingestion-time filter.
  That is exactly what a strong checkpoint+RAG baseline should have.
- Explicit two-axis temporal navigation pays off only when valid time and transaction time diverge: late news,
  retroactive corrections, or scheduled future-effective facts.

### Q2. Is "never overwrite time, fork it" just event sourcing + bitemporality?

**Substantially yes, at the storage and query layer.** The pieces map one-to-one onto existing, productized
abstractions:

| Project piece | Existing abstraction |
|---|---|
| "Never overwrite" | Event sourcing's append-only log ("a left-fold over a stream of events"), XTDB's "immutable log", Datomic's history database, and Mem0 2.x's ADD-only store. |
| "Time as an addressable dimension", "historical epistemic state with strict cutoff" vs "historical world state" | Bitemporality: system/transaction time vs valid time (XTDB's `FOR SYSTEM_TIME AS OF` vs `FOR VALID_TIME AS OF`; Memvara's `known_at` vs `valid_at`). |
| "Fork it", diff | Git-for-data: Dolt "fork, clone, branch, merge", `dolt_diff('main','modifications',...)`; lakeFS zero-copy branches. Datomic `d/with` for speculative, uncommitted what-if values. AgentGit / ActiveGraph / GCC on the agent side. |
| Branch provenance | W3C PROV `wasDerivedFrom` / `wasRevisionOf` / `wasInvalidatedBy` / bundles, plus Datomic transaction attributes. |
| Policy/objective change over time | Any bitemporal store can hold the policy as an entity with its own timeline. Nothing new is needed at the data layer. |

**What event sourcing + bitemporality do not by themselves provide:**
- (a) A modelled prospective/possible-world axis. Branches exist mechanically (Dolt, `d/with`), but nothing gives
  semantics for imagined futures with likelihoods, conditioned on the agent's own interventions.
- (b) A "prevented future" status. A forecast that was averted would be labelled as such, not scored as wrong.
- (c) Predicted-vs-realized bookkeeping tied to the branch that was actually taken.
- (d) The behavioural claim: an agent will query its own past state and notice that a later event changes the
  significance of an earlier decision.

(a)-(c) are thin schema additions on top of a bitemporal + branching store: a forecasts table keyed by branch, with
valid-time ranges and a status column. They are unlikely to count as a novel abstraction. (d) is already attacked
directly by:
- Dependency-Guided Rollback Repair (2608.10502)
- StateGuard (2609.34134)
- Execution-State Unlearning (2609.04875)
- Impact Is Not Invalidation (2609.25130)
- Correct Now, Insufficient Later (2609.20045)
- From the belief lane: MemTX, PlanFence, STALE

So the slogan is event sourcing + bitemporality + Git-style branching + PROV-style provenance. Any residual novelty must
be the behavioural/evaluation claim, tested against a baseline that already has an append-only, timestamped,
as-of-filterable log.

## Lane verdict

This lane is saturated at the substrate level and crowded at the agent-memory level.

- **The substrate is old.** Transaction-time vs valid-time querying ("as we knew it at the time" vs "as best known") is
  textbook bitemporal-database practice, productized in XTDB and Datomic. Append-only replay and state-at-version are
  event sourcing. Fork/branch/diff/merge of state is Git-for-data (Dolt, lakeFS). Revision and invalidation provenance
  is W3C PROV.
- **The agent-memory ports are already built.** In 2025-2026 these abstractions were ported into agent memory several
  times over: Memvara (`known_at`/`valid_at`/`as_of`), kaeru, Talamus, TOKI, MemStrata, Mem++, TGMS, Graphiti/Zep,
  ChronoMem, GitHarness. Mem0 itself switched to ADD-only, "nothing is overwritten".
- **The evidence on "temporal beats RAG" is mixed and partly against the project.**
  - For the project: MemStrata reports large gains over RAG on evolving software facts.
  - Against: Memvara's benchmark shows that a strong single-clock RAG over the full write log already answers "what did
    we know at T". Bitemporal structure helps only on late or corrected facts (about 9% of temporal questions). LSREP
    reports a structured memory architecture lagging vector RAG, and GitOfThoughts (sibling lane) found accuracy
    parity.
- **"Never overwrite time, fork it" is event sourcing + bitemporality + branching + provenance. It is not a new
  computational abstraction.**
- **What remains is narrow:**
  1. One store that also holds intervention-conditioned prospective branches, with "prevented" vs "wrong" forecast
     status and predicted-vs-realized links. This is cheap schema work on existing substrates.
  2. The behavioural hypothesis that exposing as-of/diff/fork tools makes agents reopen and remediate past decisions
     more often than a strong append-only, timestamped, as-of-filterable RAG baseline would. Even this behaviour already
     has dedicated methods (dependency-guided rollback repair, StateGuard) and benchmarks (Impact Is Not Invalidation,
     STALE, StateMemBench).
- **Implication for the benchmark:** the checkpoint+RAG contestant must get ingestion timestamps and as-of filtering.
  Otherwise the comparison measures a strawman. The scenarios should include a declared share of valid-time /
  transaction-time divergence (late or retroactive events), because that is the only regime where prior evidence says
  two-axis temporal state matters.

## Queries run (this lane)

Attempted but not executed (budget or blocked):
1. WebSearch "bitemporal memory LLM agent valid time transaction time knowledge graph 2025" (budget exhausted)
2. WebSearch [arxiv] "Mem0 graph memory temporal conflict resolution invalidate edges" (budget exhausted)
3. WebSearch [arxiv] "A-MEM agentic memory Zettelkasten memory evolution" (budget exhausted)
4. GitHub MCP search_repositories "bitemporal agent memory" (502)
5. GitHub MCP search_repositories "bitemporal memory llm" (502)
6. PyPI search "bitemporal" (JS challenge)

Executed: local regex queries over 17 fetched curated lists. The IAAR list has 1,085 dated entries, 928 from 2026.

7. lists: `bitemporal|bi-temporal|valid[- ]time|transaction[- ]time|point-in-time|as-of|time[- ]travel`
8. lists: link titles matching `temporal|time-aware|timeline|chrono|versioned|version`
9. IAAR titles: `tempor|time|chrono|timeline|bitemporal|bi-temporal`
10. IAAR titles: `version|history|snapshot|rollback|rewind|time travel|as-of`
11. IAAR titles: `stale|outdated|knowledge update|conflict|contradict|supersed|invalidat|obsolete|evolv|drift`
12. IAAR titles: `provenan|audit|event[- ]sourc|ledger|append-only|immutable|lineage|traceab`
13. IAAR zh summaries: `双时态|有效时间|事务时间|时间点|版本|快照|as-of|时间旅行`
14. IAAR zh summaries: `回放|重放|分支|反事实|分叉`
15. IAAR titles: `future|forecast|predict|prospect|foresight|anticipat|simulat|counterfactual|what-if|imagin`
16. IAAR titles: `commitment|obligation|intention|prospective memory|goal drift|identity|self-model|reopen|revisit|retrospect`
17. IAAR summaries: `后见|事后|截点|截止|泄漏|未来信息|look-ahead|hindsight|cutoff`
18. IAAR summaries: decision-revision zh patterns (0 hits)
19. all lists: `Memory-R1`, `A-MEM`, `MemoryOS`, `MemGPT`, `Mem0`, `LongMemEval`, `MemOS`, `Letta`,
    `time-aware|time-sensitive|TimeRAG|TempRALM|TimeR4|temporal RAG|ChroKnow|temporal question`
20. other lists: 2025-26 arXiv IDs with `tempor|time|version|rollback|supersed|stale|update|conflict|timeline|provenance|valid`

Executed: primary-source greps.

21. XTDB docs: `bitemporal|valid time|system time`; backtesting / point-in-time / late-trade guides
22. Datomic day-of-datomic: `as-of|d/since|d/history|d/with`
23. eventsourcing docs: `fowler|version=|reconstruct`
24. prov source: `wasInvalidatedBy|wasRevisionOf|bundle`
25. Memvara README + benchmark doc: `known_at|as_of|valid_at`, systems, results
26. README sweeps: mem0, A-mem, MemoryOS, MemOS, letta, cognee, MIRIX, langmem, zep, LongMemEval, dolt, lakeFS, kaeru,
    talamus, Lians
