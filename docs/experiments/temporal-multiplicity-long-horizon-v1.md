# Temporal Multiplicity, Existential Experiment 2: long-horizon state continuity (v1)

| | |
|---|---|
| **Verdict** | **NO_HEADROOM** (sub-case ii). After a pilot and the single allowed redesign, real long-running lifetimes with model-written compaction produced one confirmed, non-trivial regression, in only 1 of 3 trajectories. The pre-committed gate needed at least 2 of 3. Conditions A/B/C were therefore not run (brief, stop condition D). |
| Real-model calls | 427 subject calls: 183 in pilot v1, 231 in pilot v2, 13 in the gate. Every call used the same model. 0 WebFetch calls; every tool call was the structured-output return. |
| Raw data | `results/temporal-multiplicity/long-horizon-v1/pilot-v1/`, `.../pilot-v2/`: episodes with ground truth, full trajectories (every checkpoint, compaction and probe output), headroom tables, gate confirmation. |
| Code | `src/multiplicity_experiments/long_horizon.py`, `experiments/multiplicity_long_horizon/{runtime,investigate}.js`. The redesign was frozen at `b336a92`, before any pilot-v2 call. |

## 1. Question

A long-running agent may lose or distort parts of its historical cognitive context through repeated, lossy, model-written compaction. When that happens, does executing exact historical versions of its own state let it diagnose and repair the regression better than two baselines?
- **A:** the same model with strong archive retrieval.
- **B:** A plus exact checkpoint inspection.

This experiment first had to establish that such regressions actually arise. They essentially did not.

## 2. What made the lifetimes long-running

**The world.** A fictional procurement desk ("Larkspur Robotics"), scored exactly. Each lifetime is a sequence of weekly stages: 16 in pilot v1, 20 in pilot v2.
- **Inputs per stage:** 5 inbox messages (rules, procedural distractors, realistic noise) and 2 purchase requests.
- **Decision per request:** 5 fields (currency, approvers, carrier, notify, hold).

**Kinds of rules:**
- **Probe rules** (7 per lifetime in v1, 10 in v2): vendor payment currency, safety co-sign categories, client carrier commitments, a cold-chain category, client substitution notice, harbour-master sites.
- **Rules that change over time** (no probes): a finance-threshold update, a vendor hold on/off, a carrier strike on/off.

**How rules arrive:** often as one-line asides inside unrelated messages, never repeated (reinforcement p = 0.4).

**What carries forward:** the agent decides from its persistent memory plus its working context only. The previous stage's messages are gone after compaction; nothing is re-sent.

## 3. Context budget and compaction

- **Budgets:** working context 7,000 characters; persistent memory 1,500 characters. Both are unchanged across both pilots.
- **Trigger:** when the context overflows, the *subject model itself* rewrites its memory in four sections (rules, commitments, open items, notes) and the context is discarded.
- **The compaction prompt is generic.** It asks the model to keep whatever it needs to keep doing the job well, and says that anything else will no longer be in view. It knows nothing about the probes. No facts were ever hand-deleted.

Compactions that actually happened:

| | compactions | each one, at stages | memory after compaction (chars) |
|---|---|---|---|
| Pilot v1 | 11 (3–4 per lifetime) | every ~4 stages | 1,371–1,528 |
| Pilot v2 | 15 (5 per lifetime) | 4, 8, 12, 16, 20 | 1,222–1,475 |

No shorten-retries were needed.

## 4. Checkpoint representation

A checkpoint is taken at every stage end and right after every compaction: 20–26 per lifetime. It holds the exact memory sections plus the working-context records. That is the agent's whole explicit state.

For forks and repairs it is converted to `AgentState` (memory entries become `knowledge` facts; commitments and open items keep their own fields; the working context becomes `context`). Repairs are `TemporalMultiplicity.fork` mutations. Hidden model state is not claimed.

## 5. Retrieval, and the three conditions (built, not run)

**Retrieval.** A model-ranked semantic search. The search model reads the *entire* raw archive (every message, request and decision) and returns the top 5 record ids for each query.

| condition | tools | budget |
|---|---|---|
| A | search + read over the archive | 8 reasoning steps |
| B | A + inspect any checkpoint's exact memory, and memory diffs | 8 reasoning steps |
| C | B + execute a historical checkpoint on the rejected requests, after first writing a prediction of its decisions | 4 steps + at most 4 executions |

Every condition must repair with exactly one restored item (an archive record, or for B/C a checkpoint memory entry), and is then scored on held-out probes.

This machinery exists in `investigate.js`. It was never run with a real model, because the gate stopped the experiment first.

## 6. Headroom gate results

**Unit of analysis.** A (rule, clause) pair: the target-field accuracy of that rule's dev probes. Probe answers are verified to be time-invariant from the clause's effective stage onwards, so no historical self is scored on information it could not have had.

**Candidate regression.** Best earlier checkpoint minus final checkpoint ≥ 0.5, and final ≤ 0.5. These thresholds were committed before any pilot data.

| pilot | lifetimes | units | candidates | lifetime decision accuracy |
|---|---|---|---|---|
| v1 (16 stages, 7 atomic rules) | P1–P3 | 21 | **0** | 1.00 / 1.00 / 1.00 |
| v2 (20 stages, 10 rules, 4 qualifiers) | P1–P3 | 42 | **1** (P2) | 1.00 / 0.75 / 0.97 |

**Pilot v1.** Every probe rule survived 3–4 real compactions. The compactor kept them in compressed form (for example "EUR default; Lindqvist Tools SEK; Brandt Hydraulik CHF") and still had room for distractors and open items. A lossless rule table needed only about 25% of memory, so headroom gate condition 1 failed.

**The single redesign (pilot v2).** Chosen by a three-designer panel plus a judge that screened proposals for manufacturing the effect.
- Added clause-level nuance: amount-scoped exceptions on 4 of 10 rules (2 stated with the rule, 2 arriving later as "clarification" messages).
- Raised density modestly, under a guard that a perfect compactor could keep every scored rule within ≤ 50% of the unchanged memory (actual: 0.42).
- Rejected as manufacturing the effect: overloading memory, scripted misleading recaps, entity renames, smaller budgets, a different compaction prompt.

**Pilot v2 outcome.**
- All 12 qualifier clauses (4 per lifetime, born and amended alike) survived to the final state: 0 regressions on nuance.
- P3 dipped transiently at c12 during the carrier strike: the agent over-applied "route standard shipments via Tamar" to clients contractually tied to Brightway. It recovered once the strike ended, and it was a working-context interaction rather than a compaction loss.
- The single candidate, P2 R2 (pay Brandt Hydraulik in CHF, an aside at stage 2), was **confirmed** by the gate:

| check | result |
|---|---|
| fresh replicates at the best earlier checkpoint (c4) | 1.00 (8/8 CHF) |
| fresh replicates at the final state | 0.00 (EUR) |
| single top-1 retrieval repair: restore M-009, Brandt's own CHF message | 0.00 |

So this unit is not trivially repaired. Its mechanism matters more than the count, though. It was not loss:
- At c4 both raw messages were in context, and the agent decided CHF.
- At the first compaction, the compactor read a later Finance memo about another vendor ("…All other vendors stay on EUR"). It recorded "Brandt: CHF (Logistics) vs EUR (Finance); using EUR, confirm with Priya".
- Every later self followed that ruling, producing 10 lifetime errors.
- Restoring the raw CHF message does not override the memory's explicit ruling.

The ground truth says CHF, but the generator's formal currency template ("All other vendors stay on EUR") makes the instruction genuinely ambiguous.

## 7. Paired repair outcomes, held-out recovery and regret

Not run. Under the pre-committed gate a single confirmed unit in one trajectory is NO_HEADROOM (brief §14 and stop condition D), and the brief forbids spending the A/B/C budget on a benchmark without discriminatory headroom.

## 8. Did checkpoint execution surprise the model?

Not measured: the prediction-versus-execution diagnostic belongs to condition C.

The only anecdote is the P2 unit. The historical self at c4 behaves differently from the current self (CHF versus EUR) for a reason that is explicitly written in the current memory: the conflict note. So a condition-B agent inspecting memory would have seen the reason too. n = 1, and no claim is made.

## 9. Major confounds

- **One strong model plays every role:** decider, compactor and retriever. Its compactor is very good. A weaker or cheaper compactor, a summariser of a different model family, or production-scale compression ratios (far larger history per memory character) may produce many more regressions. Untested.
- **Scaled-down regime.** 16–20 weekly stages and 3–5 compactions per lifetime, character budgets rather than token budgets, and one synthetic procurement domain. The rules are clean and atomic or clause-level; real knowledge is more entangled.
- **Post-hoc redesign.** The redesign was chosen after seeing pilot-v1 data. It was declared, frozen in one commit before any pilot-v2 call, and applied identically to seeds 101–103. A tooling-only fix (`a14263f`) restored helper functions lost in that commit; the episodes regenerate byte-identically.
- **Ground-truth ambiguity in the only regression.** It comes from a generator wording flaw (the blanket "All other vendors stay on EUR" in the formal currency template). It was not corrected after the fact, because the benchmark was frozen.
- **No feedback during the lifetime.** The agent was never told it was wrong. Real agents often are, which would usually help them correct themselves.
- **Full context reset at compaction**, with no sliding window.
- **Probe battery format.** 14 or 28 requests per call at checkpoints, versus 2 per stage during the lifetime.
- **Subject context.** Claude Code `web-fetch` subagents with a fixed harness prompt, the same for every call.

## 10. Verdict: NO_HEADROOM

The regime the surviving thesis depends on did not show up here: repeated context turnover producing natural, non-trivial cognitive regressions that strong retrieval cannot simply undo.
- 6 real lifetimes, 26 model-written compactions and 63 (rule, clause) units gave 1 confirmed regression, in 1 trajectory.
- That regression arose from the compactor adjudicating an ambiguously worded conflict, not from compaction dropping or blurring knowledge.

With a strong model as its own compactor, memory under a realistic (scaled) budget kept even nuanced, dormant, innocuously introduced instructions. This removes the precondition for executable historical selves to add value in this regime.

Per brief §20 this is substantial negative evidence ("no realistic compaction-induced regressions emerge"), bounded by the confounds above: one model, one domain, scaled budgets.

Re-running the gate from the raw files: `PYTHONPATH=src python -m multiplicity_experiments.long_horizon headroom|gate ...`. See the `--help` of that module, and the commands recorded in the commit messages.
