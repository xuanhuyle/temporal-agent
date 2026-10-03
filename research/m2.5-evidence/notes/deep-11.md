# deep-11: Memvara (bitemporal memory for AI agents) + its Agent Memory Benchmark

- Repo: https://github.com/memvara/memvara (cloned, HEAD f263e3f "Release 0.19.0 (#451)", 2026-10-01)
- PyPI: https://pypi.org/project/memvara/ (JSON fetched from https://pypi.org/pypi/memvara/json):
  version 0.19.0, license Apache-2.0, 24 releases, first 0.1.0 uploaded 2026-08-14, 0.19.0 uploaded 2026-10-01.
  Summary: "Bitemporal memory for AI agents. Hybrid retrieval, deterministic contradiction resolution, LLM-free write path."
- Local clone: /tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/lit/repos/memvara
- Files read: README.md, docs/benchmarks/agent-memory-benchmark.md, docs/concepts/bitemporal-memory.md,
  docs/INTERNALS.md (section "`ask()` reconstructs an ending the row cannot date"), docs/BENCHMARKS.md
  ("The two clocks, measured"), docs/ROADMAP.md ("Deliberately deferred"), memvara/types.py (Claim, Delta,
  Reading, Answer, Dispute, MemoryType, LinkRelation), memvara/core.py (get_all, since, ask, _read, standing,
  link), memvara/store/sqlite.py (claims/episodes DDL), memvara/integrations/langgraph.py,
  benchmarks/agent_memory/adapters/{base,vector_rag,memvara_adapter}.py, datasets/v1/questions.jsonl.
- WebSearch budget for the session was exhausted (200/200) before this lane could search; all evidence
  below is from the cloned primary source, the PyPI JSON, and my own local runs.

## What it is (verbatim)

README: "Two axes means two clocks, and they move independently:
```
mem.get_all(valid_at=T)   # what we believe TODAY about how the world was at T
mem.get_all(known_at=T)   # what we believed at T, about the world as it is now
mem.get_all(as_of=T)      # both clocks at T — what we believed at T, about T
```"
"Eight reads take all three — `search`, `get_all`, `count`, `history`, `why`, `produced`,
`neighborhood`, `paths_between`."

Claim (types.py): "A bitemporal assertion. ... valid time (valid_from / valid_to) - when the fact was true in
the world; transaction time (recorded_at / invalidated_at) - when *we* believed it".
Columns also include `confidence`, `salience`, `observation_count`, `sources` (episode ids), `derivation`,
`extractor`, `invalidated_by`, `temporal_precision`.

Three states (bitemporal-memory.md): "`live` | open | open | currently believed, currently true";
"`ended` | closed at `valid_to` | open | the world changed"; "`retired` | untouched | closed at
`invalidated_at` | the record was wrong". "Nothing is deleted in any of the three."

ask() / Reading (types.py): "Three populations ... `now` — in force at this moment. `then` — what we believe
**today** was true at the instant asked about. ... `stated` — what this store **would have answered** at that
instant. ... `then` and `stated` disagreeing is the finding, not an inconsistency: it means the record changed
under a decision somebody already made. An agent that acted on 2026-03-15 acted on `stated`, and is being
audited against `then`." `Reading.diverged` = then != stated (by claim id).

ask() narrative (README): "On 2026-03-15 this store would have said Rome, and that is what anyone acting on it
then acted on. The difference was recorded 2026-03-22, 7 days after the instant you asked about." "No model
is consulted; every sentence is rendered from a stored column."

since() (core.py): "What changed in this scope since `when`. The resumed-session read." returns
`Delta(added, gone)`; "A supersession lands in both".

why(): "A claim carries the episodes cited for it and the claim it superseded, and `why()` returns both."

## The benchmark (docs/benchmarks/agent-memory-benchmark.md)

"262 events, 100 questions, 16 scenarios, 66 entities. Entirely synthetic". "Scoring is deterministic. There is
no LLM judge, in any mode." "No system is handed a gold answer. The runner passes adapters an object that has
no field capable of carrying one".

Baseline description: "`vector-rag` | Retrieval over the whole write log, with **one clock**: it keeps every
observation and answers a question about a past instant with the most recent write it had received by then.
The strongest baseline that is not bitemporal." "Neither baseline is built to lose. `vector-rag` is completely
correct on current state, provenance, change time and knowledge time."

Published table (memvara 0.11.3): memvara 92.0% overall, vector-rag 89.0%, naive 50.0%.
By category: historical_state memvara 100.0 / vector-rag 85.2 (n=27); knowledge_time 100/100 (n=7);
change_time 100/100; change_detection 100/100; provenance 100/100; contradiction 100/100; current_state
100/100; multi_hop 16.7 vs 33.3 (memvara loses); negative 50/50.

Interpretation (verbatim): "**Three points separate memvara from a baseline written in numpy in an
afternoon.** That is a narrower margin than the case for bitemporal memory would lead you to expect"
"**The bitemporal advantage is real and it is narrow.** memvara scores 100.0% on the temporal dimension against
`vector-rag`'s 91.5%, and the four questions that separate them are the four delayed-knowledge and correction
scenarios. Everywhere else in the dataset the two clocks coincide, and a single-clock store is exactly right.
**The claim this supports is not "bitemporal memory is better at remembering." It is "when news arrives after
the fact, a single clock has to give one answer to two different questions, and roughly nine per cent of
realistic temporal questions are that case."**"

Limitations (verbatim): "Extraction is out of scope, and this is the largest limitation. Every event carries a
structured triple alongside its sentence"; "The corpus is authored by the maintainers of one of the systems
under test."; "The vector baseline uses hashed TF-IDF, not a neural embedder."; "Answers are values, not prose.
A real agent reads memory and writes a sentence, and nothing here measures that step."

### My reproduction (scratch venv, numpy 2.4.6, HEAD f263e3f / memvara 0.19.0)
`python -m benchmarks.agent_memory --system memvara --system vector-rag --system naive --compare`:
```
memvara     92.0%  current 100  temporal 100.0  knowledge_time 100  contradiction 100  provenance 100  retrieval 64.3  irrelevance 50
vector-rag  89.0%  current 100  temporal  91.5  knowledge_time 100  contradiction 100  provenance 100  retrieval 71.4  irrelevance 50
naive       50.0%  ...          temporal  34.0  knowledge_time 42.9
```
Identical to the published table. `--show-failures` for vector-rag: the 4 historical_state failures are
q-atlas-hist-gap, q-auth-hist (delayed knowledge: valid 2026-02-10, learned 2026-02-24, asked 02-15),
q-dana-hist, q-quotes-hist (same-instant corrections, asked "with today's understanding"). All reason
`answered_other_interval`. 4/47 temporal questions = 8.5% ("roughly nine per cent").

Dataset facts I counted: 83/100 questions carry a `probe` (the slot is handed to the system, so retrieval is
bypassed); 32 carry `at`; only 4 carry `known_at` (the "what would the system have said" audit reading).

Important nuance on the "single-clock" baseline (vector_rag.py): each Record stores BOTH `recorded_at` and
`valid_from`, plus `retracted_at` implementing the published correction rule ("a rule available to one system
and not the others would be the benchmark rigging itself"). It answers change_time from `valid_from` and
knowledge_time from `recorded_at`. What it lacks is a separate world-clock *query cutoff*: "`known_at` is the
belief instant when the question supplies one and the world instant otherwise, which is the collapse a
single-clock store makes". I.e. it is an append-only, time-stamped log + metadata filter, which is essentially
the baseline spec in /home/user/temporal-agent/EXPERIMENT.md §7 ("append-only raw event log ... metadata
filters for time/entity/file").

## Caveats I verified in the code / by running it

1. In-place mutation: INTERNALS.md: "A row's `valid_to` is written **in place** by the write that displaces it.
   So the row carries its own ending but not the instant that ending came to be believed, and any predicate over
   the four columns applies an ending that had not been recorded at `T`" and "`get_all(as_of=T)` is not being
   fixed to match." My run (lives_in, Rome valid 01-01 rec 01-01; Berlin valid 03-01 rec 03-22; T=03-15):
   `valid_at -> ['Berlin']`, `known_at -> []`, `as_of -> []`, `ask().stated -> ['Rome']`, `diverged True`,
   `since(T).added=['Berlin'] gone=[]`. So the generic as-of reads and since() apply a later-recorded ending
   with hindsight (the store DID believe Rome on 03-15); only ask()/history(known_at=) reconstruct correctly.
2. Supersession depends on a declared predicate schema: with undeclared `auth_strategy` both "API keys" and
   "OAuth" stayed `live` (`history -> [('API keys','live'),('OAuth','live')]`). README: "an unknown predicate
   takes the safe default twice over: multi-valued, so nothing supersedes". (The benchmark hands every system
   the predicate schema: "whether a relation holds one value or many is published with the dataset".)
3. Not append-only: `erase()`, `purge()`, `expires_at` delete text ("Only the third deletes anything");
   consolidation mutates salience and retires near-duplicates; `merge_predicate` re-files claims.
4. Decision dependencies: `link(a, b, "derives")` exists, but types.py: "``"derives"`` the first memory was
   inferred from the second ... Nothing in the engine writes one today." No propagation of a retired premise to
   dependents (grep for propagation/stale found nothing in core.py).
5. LangGraph integration is `BaseStore` (long-term store), not a checkpointer: "LangGraph: `BaseStore`,
   implemented on memvara." So memvara + LangGraph checkpointer is a composable off-the-shelf stack:
   execution time-travel (LangGraph) + bitemporal fact memory (memvara).
6. Agent "decisions" are vocabulary only: ROADMAP: "`decision` and `observation` as memory types ... They ship
   as a predicate pack instead — `MEMVARA_PREDICATES=decisions`". Procedural memory = "how the user wants things
   done"; `standing()` is current-only (no time keyword), though get_all(as_of=) over procedural claims works.

## Capability ratings (only what Memvara itself provides)

| # | capability | rating | evidence |
|---|---|---|---|
| 1 | immutable_historical_observations | partial | episodes table keeps raw turns with ts; superseded claims "ended, never deleted"; BUT valid_to/invalidated_at/salience written in place, erase/purge/expiry delete text |
| 2 | historical_world_state | yes | `valid_at=T` "what we believe TODAY about how the world was at T"; `valid_during`; `history()`; scoped to stored (s,p,o) slots |
| 3 | historical_epistemic_state | yes (scoped) | `ask().readings[].stated` "what this store would have answered at that instant"; `history(known_at=)`; knowledge_time 100% in benchmark. Caveat: get_all(as_of)/since() apply later endings in place (verified). Covers stored claims only, not agent context/reasoning |
| 4 | historical_policy_objective_state | partial (weak) | procedural "standing preferences" and arbitrary `goal` predicates are bitemporal claims queryable as_of; no agent policy/model/objective versioning |
| 5 | execution_checkpoints | no | none; LangGraph adapter is BaseStore, not checkpointer |
| 6 | replay | no | only "replays mem0's own mutation log" on import; no agent execution replay |
| 7 | fork_from_historical_state | no | none |
| 8 | counterfactual_action_branches | no | none |
| 9 | branch_provenance | no | claim provenance (sources, superseded, derivation) but no branches |
| 10 | explicit_current_belief_state | yes | `get_all()` live claims per slot with cardinality; `standing()`, `profile()`; decisions pack |
| 11 | uncertainty_representation | partial | per-claim `confidence`, `temporal_precision`, `Dispute` keeps lower-confidence competitor beside incumbent; retired vs ended; no probabilistic/unresolved-question tracking |
| 12 | future_state_rollout | no | none |
| 13 | multiple_prospective_branches | no | none |
| 14 | probability_over_futures | no | none |
| 15 | backward_requirements | no | none |
| 16 | intervention_aware_forecasting | no | none |
| 17 | prevented_futures_preserved | no | none (future `valid_to`/`expires_at` are scheduled endings, not forecasts) |
| 18 | predicted_vs_realized | no | `then` vs `stated` compares past belief vs corrected belief, not predictions vs outcomes |
| 19 | cross_time_state_querying | yes | as_of/valid_at/known_at on 8 reads; `valid_during`; `since(when)` delta vs now; `ask(at=)`; no arbitrary diff(t1,t2) |
| 20 | unified_temporal_abstraction | no | one two-clock interval model unifies historical + current fact state; nothing counterfactual or prospective |

## How this threatens the project's novelty

1. It ships, as a pip-installable Apache-2.0 library with no model calls, the exact triad the project lists as
   "Historical-state fidelity" (EXPERIMENT.md §11): "what was true then; what it knew then; what it knows now
   about then" = Memvara `Reading.then` / `Reading.stated` / `Reading.now`. It also ships "bitemporal facts" and
   "decision provenance" (why(): source episodes + superseded claim), which are listed ingredients of the
   project's temporal contestant (§8). These cannot be claimed as novel parts of "temporal agency".
2. Its benchmark is direct evidence for the project's null hypothesis on the epistemic-cutoff component: an
   append-only, timestamped log with an ingestion-time filter (essentially the project's own §7 baseline) scores
   100% on knowledge_time ("what would we have said that day") and on current state, provenance, change time,
   change detection and contradiction. Two-axis state wins only on 4/47 temporal questions (8.5%), all of them
   delayed-knowledge or same-instant-correction cases = the project's event classes C (delayed evidence) and D
   (retroactive fact). Overall gap: 3 points (92 vs 89). Prediction for the project: on historical-state
   fidelity, a strong baseline should tie except on C/D-type "what we now know about then" questions.
3. `Reading.diverged` + the narrative "that is what anyone acting on it then acted on" is a deterministic
   primitive for step 1 of the project's hypothesis ("detect variance": a later record changed the basis of an
   earlier decision), at the granularity of a fact slot.

## What it does not cover (residual space for the project)

- No link from facts to the agent's assumptions/decisions/artifacts that is written by the engine ("derives"
  exists but "Nothing in the engine writes one today"), no propagation, no trigger: variance is noticed only if
  someone calls ask() on the right slot at the right instant. No reopening, re-deciding or present remediation
  (steps 3-5 of the project's hypothesis) and no measure of them in its benchmark ("Answers are values, not
  prose").
- No execution checkpoints, replay, forking, counterfactual branches, branch provenance.
- Nothing prospective: no rollouts, futures, probabilities, backward requirements, intervention-aware forecasts,
  prevented-future bookkeeping, predicted-vs-realized.
- No agent policy/objective/model versioning beyond storing preferences/goals as generic claims.
- Its own benchmark is self-authored, hands systems structured triples (extraction out of scope), hands the slot
  (`probe`) on 83/100 questions, has only 4 `known_at` questions and 7 knowledge_time questions, and uses a hashed
  TF-IDF retriever for the baseline. It shows nothing about agents acting over long horizons.
- Implementation gaps relevant to the project's "topology integrity" metric: deterministic supersession needs a
  declared predicate schema (undeclared slots never supersede), and the generic as-of reads apply later endings
  with hindsight. Only ask()/history(known_at=) are strict.

## Implication for the project
Do not claim "reconstruct what the agent knew at t with no hindsight" or "two-clock fact state" as novel.
Either add a memvara-style bitemporal store to the baseline as an ablation arm, or expect any Tesseract advantage
on historical-state fidelity to be confined to retroactive/delayed-evidence events and narrow. The surviving
distinct hypothesis must sit in fact-to-decision dependency tracking with automatic reopening and remediation,
execution-level branching, and prospective/counterfactual state. Memvara has none of these.
