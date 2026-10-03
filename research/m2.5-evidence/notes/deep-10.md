# deep-10: Memvara (bitemporal memory for AI agents)

- Repo: https://github.com/memvara/memvara (git clone OK; shallow, single commit
  `f263e3f8abed1c7d7bf285bd4bec2c09cadeb770`, "Release 0.19.0 (#451)", 2026-10-01)
- PyPI: https://pypi.org/project/memvara/ (JSON API fetched: version 0.19.0, summary
  "Bitemporal memory for AI agents. Hybrid retrieval, deterministic contradiction
  resolution, LLM-free write path."; 24 releases, first 0.1.0 uploaded 2026-08-14, 0.19.0
  on 2026-10-01). Apache-2.0. No author field on PyPI or pyproject.
- Not a paper. Software library + MCP server + hosted service (memvara.dev) + a
  self-authored benchmark (`benchmarks/agent_memory`).
- Clone: `scratchpad/lit/repos/memvara`. Probes I ran: `scratchpad/lit/probe_memvara/probe*.py`
  (numpy venv, local source on PYTHONPATH, NullLLM, no network).
- WebSearch budget was exhausted for this session (200/200), so no external search hits
  were added in this pass. All claims below come from the repo source, its docs, PyPI, and
  my own probe runs.

## What it is (verbatim)

README:
> "Bitemporal memory for AI agents. Know what was true. Know when it was true. Know why you believe it."

> "**Bitemporal** | Two time axes that move independently: when a fact was true, and when this store was told."

`docs/concepts/bitemporal-memory.md`:
> ```
> mem.get_all(valid_at=T)   # what we believe TODAY about how the world was at T
> mem.get_all(known_at=T)   # what we believed at T, about the world as it is now
> mem.get_all(as_of=T)      # both clocks at T — what we believed at T, about T
> ```
> "Eight reads take the same three time keywords: `search`, `get_all`, `count`,
> `history`, `why`, `produced`, `neighborhood` and `paths_between`."

Unit of memory: `Claim` (subject, predicate, object) with `valid_from/valid_to`
(world clock) and `recorded_at/invalidated_at` (belief clock), plus `confidence`,
`salience`, `sources` (Episode ids), `derivation`, `extractor`, `invalidated_by`
(`memvara/types.py`, class `Claim`). Raw source turns are `Episode`s:
> "Raw source material. Claims point back at these, so every memory is traceable."

Three closure states (`types.py`, `Closure`):
> "``"ended"``  valid time closes. **The world changed.** ...
> ``"retired"``  transaction time closes. **The record was wrong.**"

Deterministic contradiction resolution (`docs/concepts/contradiction-resolution.md`):
> "normalise the predicate, fold the entity, look up `(subject, predicate)` in an index,
> and if the predicate is `ONE`, close the interval of whatever is there. It is a database
> operation."

Provenance (`docs/concepts/provenance.md`): `why(claim_id)` returns episodes, derivation,
extractor, `superseded` claims and typed links.
> "`p.superseded` The claim this one **replaced**. That is the field that turns a note into a record"

`ask()` (core.py) renders three readings per fact slot:
> "* what is in force **now**;
>  * what we believe **today** was true at `at` ...
>  * what this store **would have answered** at `at`, which is the answer somebody
>    acted on and the one an audit is against."

`Reading.diverged` (types.py):
> "`then` and `stated` disagreeing is the finding, not an inconsistency: it means the
> record changed under a decision somebody already made. An agent that acted on
> 2026-03-15 acted on `stated`, and is being audited against `then`."

`since(when)` returns `Delta(added, gone)`, "What changed in this scope since `when`. The
resumed-session read." (diff from T to now only; there is no diff(t1, t2)).

## The epistemic-cutoff caveat (source and probe)

The row-level `as_of` reads leak hindsight. A row's `valid_to` is stamped in place by the
later write that displaces it. `docs/INTERNALS.md` "`ask()` reconstructs an ending the row
cannot date":
> "A row's `valid_to` is written **in place** by the write that displaces it. So the row
> carries its own ending but not the instant that ending came to be believed, and any
> predicate over the four columns applies an ending that had not been recorded at `T`"
> ```
> get_all(as_of=2026-03-15)         -> []       Rome's ending applied a week early
> ask(..., at=2026-03-15).stated    -> [Rome]   what the store actually held that day
> ```
> "`get_all(as_of=T)` is not being fixed to match."

The authors' own benchmark adapter has to work around it
(`benchmarks/agent_memory/adapters/memvara_adapter.py::_as_of`):
> "`is_live(valid_at=..., known_at=...)` is the wrong read for this question ... a
> superseded row carries a `valid_to` stamped by a successor that the belief clock has not
> yet reached — so the row reads as finished at an instant when the store had not heard it was."

Probe 1 (`probe.py`): Rome (valid and recorded 01-04), then Berlin (valid 03-01, recorded
03-22). Query at t=03-15:
```
valid_at(t): ['Berlin']
known_at(t): []
as_of(t):    []
ask now/then/stated: ['Berlin'] ['Berlin'] ['Rome'] diverged True
search as_of(t): []
since(3/10): <Delta since 2026-03-10T00:00:00+00:00 +1 -0>
```
So `search(as_of=t)`, the read an agent would use to rebuild its context, returns nothing
where the store actually held Rome. `since()` also misses the supersession: it reports
+1 -0, although its docstring says "A supersession lands in both".

Probe 2 (`probe2.py`): Acme recorded 01-04, then today (2026-10-03) `forget(close="ended",
at=03-01)`. `ask(at=03-15).stated` -> `[]`, although on 03-15 the store believed Acme.
The closure witness stores only the landed `valid_to` instant (`{'at': 03-01, 'close':
'ended', 'by': None}`). The wall-clock time the ending was learned is recorded nowhere, so
even `ask()` cannot apply the cutoff. With the successor erased (`erase(berlin_id)`), `stated` at 03-15 ->
`[]` as well (documented: "The case it cannot recover is an ending whose successor has
since been erased"). Side observation: the narration for probe 2 says "Every value ever
recorded for it has been retired" while `state == 'ended'`.

Other in-place mutations (store/sqlite.py): `UPDATE claims SET invalidated_at=?,
invalidated_by=?`, `UPDATE claims SET valid_to=?`, `UPDATE claims SET salience=?,
obs_count=?, sources=?`. `merge_predicate` re-files stored claims under a new predicate
("Ids survive, nothing is deleted, and each moved claim carries a dated
`predicate_rekey` note"). Document update erases dropped chunks' episodes
(`documents/service.py`: `store.erase_episodes(dropped, cited=True)`). `erase`/`purge`/
`expires_at` delete bytes. Tier-0 hash dedupe means repeated identical turns are not kept
("tier-0 dedupe means it is not a faithful transcript either", LIMITATIONS). There is no
append-only mutation/event log table. The tables are documents, document_chunks,
claim_links, predicates, episodes, claims, claim_sources, embeddings, entities, erasures.

## What it does not have (searched)

- No checkpoints, replay, fork, branches or counterfactuals of agent execution. "checkpoint" only
  appears as the `langgraph-checkpoint` package name (the LangGraph BaseStore adapter).
  "replay" means replaying store-operation programs in tests (`tests/adversarial/model/
  test_adv_replay.py`) or mem0's mutation log on import. "counterfactual", "forecast",
  "prospective" and "what if" have zero hits in memvara/, docs/ and public-docs/.
- No truth maintenance. `derives` links exist, but types.py says:
  > "``"derives"``  the first memory was inferred from the second ... Nothing in the engine writes one today."
  When a claim is superseded, nothing propagates to claims or decisions that depend on it.
  No decision is ever flagged for reopening. `ask().diverged` only fires when someone asks a
  question about that slot and instant.
- Future: a claim can carry a future `valid_from` ("stored to begin later, which is
  recorded and believed but not true yet") or a planned `valid_to` with `until_reason`.
  Nothing simulates, branches or assigns probabilities. A scheduled fact that never
  happened can only be `retired` ("the record was wrong") or `ended`, which is clamped to its
  start and so is "true at no instant". There is no "prevented/averted" label.
- Policy/objective: user standing instructions are `procedural` claims, returned by
  `standing()` (no time axes) and versioned like any claim. A `decisions` pack adds
  `decided`/`observed` predicates (cardinality many). The agent's own goals, system prompt,
  model id and policy have no model of their own.

## Its own benchmark: evidence on effect size

`benchmarks/agent_memory` (262 events, 100 questions, 16 scenarios, deterministic scoring)
includes `knowledge_time`: "When did *we* find out — and what would we have said then?"
Results (memvara 0.9.0, self-run, in `docs/benchmarks/agent-memory-benchmark.md`):
memvara 92.0% overall, vector-rag (one clock over the full write log) 89.0%, naive
dict 50.0%. Verbatim:
> "**Three points separate memvara from a baseline built out of numpy in an afternoon**,
> and that is narrower than the pitch for bitemporal memory would suggest."
> "`temporal` is the whole of memvara's lead. 100.0% against `vector-rag`'s 91.5%. The
> four questions `vector-rag` misses are the four delayed-knowledge and correction
> scenarios ... Everywhere else in the dataset the two clocks coincide and a single-clock
> store is exactly right."
> "`vector-rag` gets current state, provenance, change time and knowledge time completely right"

## Prior art it cites (from docs/ROADMAP.md "Related work"; not independently verified, no search budget)

- "A Graph-Native Bitemporal Memory Store for Conversational AI Agents", Niksarli and
  Baheti, arXiv:2607.26520 (cited by memvara as reaching the same thesis independently).
- "Hindsight is 20/20: Building Agent Memory that Retains, Recalls, and Reflects",
  arXiv:2512.12818. Code at github.com/vectorize-io/hindsight (`git ls-remote` returned HEAD
  f7dd3f4f, so the repo exists).

## Threat to the temporal-agency project

1. **Bitemporal fact memory is not novel.** It is a shipped, tested (claims ~10k tests,
   100% statement coverage), Apache-2.0 pip install. This covers valid vs knowledge time,
   as-of reads, "ended vs retired" (world changed vs record wrong), supersession provenance
   (`why().superseded`), and "what we would have said then vs what we now believe about
   then" (`ask()` with `Reading.diverged`). The project cannot claim any of these at the
   memory layer, and `diverged` is a near-verbatim statement of the project's motivating
   failure ("the record changed under a decision somebody already made").
2. **Strong-baseline obligation.** Under the project's own rule 4 (strong, configurable
   baseline), a checkpoint + RAG contestant could reasonably include a bitemporal memory
   like this, or a one-clock full-log RAG, which memvara's own data shows is nearly as good.
   Any temporal-agency advantage has to show up beyond what a memvara-style store gives.
3. **Effect-size warning.** memvara's own benchmark found the bitemporal gain over a one-clock
   full-log RAG to be 3 points overall, concentrated in delayed-knowledge and correction
   items. That is self-authored and small, but it suggests history-reconstruction benefits
   over a strong log+RAG baseline are narrow unless scenarios are built around late-arriving
   knowledge and its effect on earlier decisions.

## What it leaves open (residue for the project)

- Strict, verified, hindsight-free reconstruction. Memvara's general as-of reads leak
  later-recorded endings by design. `ask()` fixes the common case but still leaks for
  backdated endings that have no successor (probe 2) and for erased successors. A system
  that records when every mutation was believed (an append-only log) and is tested for
  leakage would still be a contribution, but only as an engineering correctness one.
- Epistemic state beyond facts: plans, assumptions, rationale, the context window at
  decision time, and which beliefs a decision depended on.
- Decision dependency tracking and automatic reopening or remediation when a later event
  changes an input. There is no truth maintenance, and `derives` is never written.
- Execution checkpoints, replay, forks and counterfactual branches with provenance.
- Everything prospective: rollouts, multiple futures, probabilities, backward requirements,
  intervention-aware forecasts, prevented futures (memvara's ended/retired vocabulary would
  mislabel an averted forecast as "retired = never true"), and predicted-vs-realized
  calibration.
- Agent policy and objective history as first-class state.
- Showing that any of these change downstream decisions. Memvara's evaluation is QA
  accuracy over facts, not agent actions.
