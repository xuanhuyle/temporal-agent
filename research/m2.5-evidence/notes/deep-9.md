# deep-9: Corollary, an agent runtime where state is beliefs (JTMS for LLM agents)

- Work: Corollary, GitHub https://github.com/gabe-santana/corollary (MIT, Python, pre-alpha), PyPI https://pypi.org/project/corollary/ (0.1.0a1 and 0.1.0a2)
- Author: Gabriel Santana (single author, per pyproject `authors` and git log).
- Date: first commit 2026-10-01 ("Initial release of Corollary 0.1.0a1"); HEAD 1ad7230 2026-10-02 ("Release 0.1.0a2"). 52 commits over 2 days. A commit "Publish releases to PyPI and skip the Pages deploy while private" suggests the repo was private before then.
- PyPI JSON (fetched 2026-10-03): 0.1.0a1 uploaded 2026-10-02T22:56; 0.1.0a2 uploaded 2026-10-02T23:54.
- No paper, no preprint, no evaluation beyond unit tests and examples. WebSearch budget was exhausted before this deep-read, so I found no external mentions. GitHub HTML, the API and the docs site (github.io) are blocked.
- Clone: scratchpad/lit/repos/corollary (unshallowed). Probe scripts: scratchpad/lit/repos/cor_probe/probe.py, probe2.py.
- Local verification: `PYTHONPATH=src python3 -m pytest` gives **386 passed in 5.40s** (Python 3.11). `examples/self_repairing_report.py` runs and prints "12 conclusions changed, 7 were untouched, 1 recomputed but unchanged ... Rule evaluations during the repair: 13. Model calls: 0." and "Verification PASSED: 6 checks".

## What it is (verbatim)

README:
- "An agent runtime where the unit of state is a belief, not a message."
- "Corollary replaces the message log with a **belief base**."
- "Underneath sits a **Truth Maintenance System** (Doyle, 1979): every belief records what supports it, and when that support is withdrawn, dependent beliefs are retracted automatically. A message log still exists, but only as a *view* derived from the belief base, never as the source of truth."
- "**Retraction cascades.** A tool returns a corrected figure. Every conclusion derived from the old value is retracted and re-derived, surgically."
- "**Beliefs that expire.** A stock price is valid for a minute; a company's headquarters for a year. Stale beliefs trigger re-verification instead of silent reuse."
- "No re-run. No transcript archaeology. A diff of what changed. During repair, the model sees only the *current* inputs of each belief it re-derives. The retracted figure never reaches it again."
- "The resulting guarantee is **over-retraction, never under-retraction**."
- Roadmap: "[x] Validity windows and automatic re-verification of stale beliefs", "[x] Persistent belief snapshots (JSON)", "[ ] Persistent belief stores (SQLite, Postgres)", "[ ] Assumption-based (ATMS) mode for exploring alternative hypotheses in parallel".
- Open problems: "**Benchmarks.** There is no standard evaluation for how well an agent recovers from a corrected input. We want to build one."

docs/concepts.md:
- "`Belief` objects are immutable. What changes over time is their **status**, which the kernel computes."
- "Each time a key gets a *different* value, the base creates a new **revision** instead of mutating the old one."
- "Revisions are why proofs stay meaningful: a conclusion derived from `revenue:Q2@1` keeps pointing at the value it actually used, even after `revenue:Q2@2` exists."
- "**`unless`**: keys that must *not* be believed for the justification to hold (a default, or an exception)"
- "Nothing is deleted: retracted revisions stay in the base with the reason."
- "if a recomputed value equals the old one, the old revision simply gains a new justification and comes back `IN`. The cascade stops there (**early cutoff**)."
- "A belief base still has a history (`kb.history`, `kb.transcript()`) ... It is a *view* derived from the base, never the source of truth, and it is never shown to the model."

docs/architecture.md (Guarantees):
- "9. **Nothing is deleted.** Retracted and superseded revisions remain, with reasons, so every past conclusion can still be explained."
- "2. **Retracted facts are absent from model contexts.** ... There is no transcript for a wrong fact to leak from."
- Limits: "**Single-process, not thread-safe.** A `BeliefBase` is an in-memory structure."

docs/guides/time.md:
- "Validity belongs to the **evidence** (the premise justification), not to the claim."
- "`kb.stale()  # latest revisions OUT only because all their evidence expired` / `agent.reverify()  # re-run the tool calls behind them, then repair()`"
- "`TemporalCheck` fails a proof when any step relies on evidence that has expired at the check time, or when a justification was recorded before one of its antecedents existed. Check a proof as of another time with `proof.verify(kb, at=...)`."

docs/guides/persistence.md:
- "What is saved: every revision of every belief, including retracted ones and their reasons; every justification ...; the change reasons and the event history; the trust ledger"
- "Labels (`IN` / `OUT`) are **not** stored: they are recomputed on load from the graph"
- Not saved: "**Rules and constraints**, which are Python callables" and "**The trust policy and clock**".

docs/guides/confidence.md:
- "`kb.retract(key)` (default `fault="none"`): the world changed, e.g. a restatement | nothing" vs "`kb.retract(key, fault="source")`: the value was wrong when given | wrong, for every source accountable"
- "`kb.record_outcome("tool:carrier_api", False, reason="ETA missed by 3 days")`"

docs/related-work.md:
- "Corollary doesn't implement an ATMS yet. It is on the roadmap for exploring competing hypotheses."
- Compared with Graphiti: "When a fact is invalidated | That fact is marked invalid | That fact and **everything derived from it** go `OUT`, then are re-derived"
- "A useful one-line description of the project is *incremental recomputation for agent reasoning*."

## Code-level findings (src/corollary)

- kernel.py `_Node`: `belief` is immutable, but `status`, `support`, `retracted`, `retract_reason` and `justifications` are mutable. `restore()` flips `retracted` back to False. A same-source re-assertion calls `_unlink` and deletes the earlier justification ("A source re-asserting a value it already gave replaces its justification instead of adding one", CHANGELOG 0.1.0a2). So revisions are append-only, but justification and label state is overwritten in place.
- `Event(at, action, ref, detail)` history is append-only. Its actions are `assert`, `support`, `renew`, `derive`, `rederive`, `retract`, `restore`, `resolve`. It is persisted in snapshots.
- There is **no `as_of` / `state_at(t)` / fork / branch API**. `dir(BeliefBase)` contains nothing of the kind (probe). Labels are current-only.
- `Proof.diff(other) -> ProofDiff(added, removed, changed, status_changed)` compares two proof snapshots. A caller who kept an earlier `Proof` object gets a diff(t1, t2) over that subgraph.
- `TrustLedger.reliability(source, prior, at=t)` does **not** exclude outcomes recorded after `t`. `_weight` uses `age = max(0.0, (now - outcome.at)...)`, so a future outcome gets full weight. In the probe, an outcome recorded 2026-06-01 lowers reliability "at 2026-01-01" from the prior 0.95 to 0.8636. So `at=` is a decay parameter with no epistemic cutoff. The ledger also has `reset()` and drops history beyond `max_history`.
- agent.py `_ask(mode="rederive")` prompt: "Re-derive the belief `{key}`. It previously held {previous}, but the beliefs it was derived from have changed." The model does see the previous *conclusion* value, but not the retracted inputs.
- agent.py `narrow()`: "For each antecedent in turn, the model is asked to derive `key` again with that belief removed from its context. If the value is unchanged, the belief was not needed." This is counterfactual ablation over evidence, not over actions.
- contract.py: the model may emit only `call_tool`, `cite`, `claim` and `answer`. **No `unless`, no assumption, no plan or forecast fields.** Defeaters (`unless=`) exist only in the programmatic API (`kb.derive` / `kb.justify`).
- Tools are premise sources. There is no notion of an executed decision or side effect that needs remediation, rollback or compensation. `reverify()` re-runs a tool call with its original args.
- Verifier "replay" means re-executing deterministic rules and formulas on the recorded antecedent values (verify.py ArithmeticCheck). It is not execution replay.
- `Report.steps` (StepRecord: prompt, response, accepted, rejected) is an in-memory per-run trace and is not persisted.

## Probe results (cor_probe/probe.py, probe2.py)

```
t1 decision: use-libfoo IN
after unrelated-key CVE fact, decision: use-libfoo IN (no cascade: no dependency/unless declared)
   OUT  libfoo:safe              (retracted: CVE published)
   OUT  decision                 (lost support: libfoo:safe)
   IN   libfoo:safe              (asserted by tool:scanner)
   IN   decision                 (re-derived: 'use-libbar')
revisions(decision): [('decision@1','use-libfoo','OUT','2026-01-01'), ('decision@2','use-libbar','IN','2026-01-12')]
why_out decision@1: lost support: libfoo:safe
proof diff t1->t2: ~ libfoo:safe: True -> False / ~ decision: 'use-libfoo' -> 'use-libbar'
after restore libfoo:safe@1 -> IN conflicts: ['2 incompatible values (True, False)', ...]
ledger reliability at 2026-01-01 (outcome recorded 2026-06-01): 0.8636 prior=0.95   <- hindsight leak
reloaded snapshot: history len 7, both decision revisions present, labels recomputed
probe2 (unless declared up front): decision OUT "defeated by: cve:libfoo"
```

Interpretation:
1. **Explicit correction of a premise reopens and re-derives the earlier decision automatically.** The old decision revision is kept with its decision-time inputs pinned and a reason. This is the project's "reopen" step, done without temporal navigation.
2. **A new, unanticipated later fact on a different key does not reopen anything.** The exception is a defeater declared up front by the programmer (`unless=`), or a registered Constraint. The LLM contract cannot declare defeaters. Under conservative dependencies, a claim depends only on what was visible when it was made. So the case "a later event changes the significance of an earlier decision without contradicting its premises" stays open, unless someone anticipated it.

## Capability ratings (what the work itself provides)

| # | capability | rating | evidence |
|---|---|---|---|
| 1 | immutable_historical_observations | partial | Immutable Belief objects, append-only revisions ("Nothing is deleted") and an append-only Event history, persisted. But the retracted flag, labels and justifications are mutated in place. A same-source re-read replaces its justification. Repeated identical tool results are deduplicated, not logged as raw observations. The ledger can be reset or truncated. |
| 2 | historical_world_state | no | No world-state-at-t reconstruction. Labels are not stored historically. A user could reconstruct this only by hand from the event log. |
| 3 | historical_epistemic_state | partial | Each past conclusion revision keeps pinned antecedent refs (the values it used), created_at, why_out and the retract reason. TemporalCheck rejects a justification that predates its antecedents. No whole-base "what did I believe at t", and the ledger's at= leaks later outcomes. |
| 4 | historical_policy_objective_state | no | Instructions, system prompt, model, trust policy and rules are not versioned. `register_rule(replace=True)` swaps a rule without keeping history. |
| 5 | execution_checkpoints | partial | `save`/`load`/`to_dict` JSON snapshot of the full belief base (the docs say "The belief base *is* the agent"). Snapshots are manual, exclude rules, policy and clock, and do not cover the run loop or Report.steps. |
| 6 | replay | partial | Step-level only: the verifier replays rules and formulas on recorded antecedents, `reverify()` re-runs tool calls with their original args, and `ScriptedModel` replays canned responses. There is no re-execution of an agent run from a historical point. |
| 7 | fork_from_historical_state | no | One labeling, no branches. ATMS is roadmap only. `from_dict` copies exist only as incidental serialization. |
| 8 | counterfactual_action_branches | no | `narrow()` runs counterfactual evidence ablation. There are no alternative actions. |
| 9 | branch_provenance | no | No branches. Strong per-belief derivation provenance, which is not branch provenance. |
| 10 | explicit_current_belief_state | yes | The core design: beliefs with claim, value, confidence, source, validity, justifications, IN/OUT labels, assumptions as a source kind, and conflicts. |
| 11 | uncertainty_representation | yes | Effective confidence (noisy-OR, min-chain, learned reliability, half-life), first-class Conflict objects, pending re-derivations, stale/faded lists, and assumptions flagged as ungrounded. |
| 12 | future_state_rollout | no | none |
| 13 | multiple_prospective_branches | no | none (ATMS for alternative hypotheses is planned and is not about futures) |
| 14 | probability_over_futures | no | none |
| 15 | backward_requirements | no | Constraints are invariants over current beliefs and are not derived from futures. |
| 16 | intervention_aware_forecasting | no | none |
| 17 | prevented_futures_preserved | no | Adjacent only: fault="none" (the world changed) vs fault="source" (the source was wrong) keeps retractions caused by a world change from being scored against the source. |
| 18 | predicted_vs_realized | partial | TrustLedger learns source reliability from realized outcomes (`record_outcome(..., "ETA missed by 3 days")`, human conflict resolutions, verified formulas and citations). It is source-level and manual, with no forecast objects or resolution dates. |
| 19 | cross_time_state_querying | partial | revisions(key) with created_at, history with timestamps, why_out, Proof.diff between two snapshots, proof.verify(at=t) for expiry, and net change logs. No state_at(t) and no diff(t1,t2) over the base. |
| 20 | unified_temporal_abstraction | no | Only current state plus revision history. No counterfactual or prospective states. |

## How it threatens the project's novelty

- **Mechanism pre-empted.** Corollary ships tested code for "premise invalidated -> dependent conclusions (including a final answer or decision) go OUT and are re-derived, the old revision is preserved with its decision-time inputs and a reason, and a diff of what changed is reported". It also covers time-driven invalidation (TTL, half-life, then re-verification). The project's benchmark pivot, "notice that a later event changes the significance of an earlier decision and reopen it", has a classical, non-temporal solution whenever the dependency was recorded and the later event arrives as a correction to that dependency. Reopening is dependency-directed backtracking (Doyle 1979), not temporal navigation.
- **Alternative explanation for any win.** If a temporal agent beats checkpoint+RAG on reopen tasks, a JTMS-style agent (current beliefs + justifications + retraction cascade + expiry) explains the win more cheaply. The project's baseline set should include a dependency-tracking or TMS arm. Otherwise "temporal navigation helps" is confounded with "recorded dependencies help". Corollary's design is explicitly anti-history: the model never sees the history or a transcript, only IN beliefs. So it is a principled strong non-temporal contestant.
- **Benchmark territory.** The author says, verbatim, that they want to build "a standard evaluation for how well an agent recovers from a corrected input". That overlaps the project's benchmark, so a first-mover risk exists.
- **Partial anti-hindsight overlap.** TemporalCheck's "no conclusion predates the beliefs it uses" is a proof-level causal-ordering guard, similar in spirit to a strict epistemic cutoff.

## What it does NOT cover (residual space for the project)

- Noticing **unanticipated** later events that change an earlier decision's significance without retracting its premises. Corollary needs an explicit retract/supersede on the same key, an `unless` defeater declared at derivation time (programmatic API only, not in the LLM contract), or a registered Constraint. The probe shows a CVE on a new key leaves the decision IN.
- **Remediating executed actions or side effects.** Corollary repairs beliefs and answer text. It has no world-changing action model, no compensation, no rollback.
- **As-of reconstruction** of the whole epistemic state with a strict cutoff. There is no state_at(t), labels are current-only, and the ledger's `at=` leaks future outcomes (verified).
- Policy, objective or identity versioning, fork/branch with provenance, counterfactual action branches, prospective futures, backward requirements, intervention-aware or prevented forecasts. None of these exist. ATMS is roadmap only.
- **Any empirical evaluation.** There is none, only 386 unit tests and a deterministic demo.

## Could not verify

- External reception (stars, issues, Discussions, blog or HN posts): GitHub HTML and API are blocked, and the web search budget was exhausted.
- The docs site gabe-santana.github.io/corollary (blocked). I used the repo's docs/ instead.
- Behavior with a real LLM (Claude or OpenAI adapters): not run, no API key. Only the scripted and offline paths were exercised.
- Whether the pre-2026-10-01 private history contained more (for example, a draft evaluation).
- Whether the related repos named in sweep-belief-state.md (benthomasson/ftl-reasons, afogel/lemmalog) predate it. Not checked here.
