# Benchmark reuse assessment: is our benchmark redundant?

Status: Milestone 2.5, 2026-10-03. Evidence labels are defined in
[research-landscape-2026-10.md §1](research-landscape-2026-10.md#1-method-and-evidence-limits).
No benchmark file was changed.

The current benchmark tests this: **a later event changes the significance of
an earlier, world-authored decision. Can an agent notice, unprompted, and
reopen it?** It scores:
- governance recall and reopening precision;
- false interventions on negative controls;
- historical-state fidelity (true then / known then / known now about then);
- remediation by hidden tests.

`smoke_v1` has 10 events, 3 reconsiderations and 5 distractors. The protocol
plans 30-50-event families: simple, long_history, high_noise and
deep_causality.

## 1. Answers to the four questions

**Q1. Is `smoke_v1` testing a capability already adequately benchmarked
elsewhere?**
Largely yes for each component, no for the exact combination. That
combination is integration. It is also not what the thesis needs measured.
- Each component has a 2026 benchmark (§2).
- No benchmark found combines all of the following in one software world:
  - unprompted, per-decision reopen recall and precision with negative
    controls;
  - a three-way fidelity probe;
  - executable remediation.
- `smoke_v1` is not a measurement either (§3).

**Q2. Would the planned long_history / high_noise / deep_causality families
add scientific value?**
Low, as specified (§4). None of them varies the conditions under which prior
work shows non-temporal methods fail:
- divergence between valid time and transaction time;
- significance changing with no fact superseded;
- decisions authored by the agent itself.

Each family would mostly re-measure published results, at high authoring
cost.

**Q3. Could the contestant be adapted to an existing benchmark instead of
building our own?**
Yes, partly, and more cheaply. The ranked plan is in §5: PM-Bench,
EvoCode-Bench, MemoryArena or τ²-bench, then MerchantBench.

**Q4. Which capability would need a bespoke benchmark because existing
benchmarks do not measure it?**
Only a narrow residue (§6). Building it is not authorized under disposition
A.
- decisions the agent itself made, with their decision-time state preserved;
- changes of significance with no fact superseded;
- class-D divergence between valid time and transaction time, with
  executable backfill.

## 2. Comparison with existing benchmarks

| benchmark | what it measures | overlap with `smoke_v1` | gap | reusable for | access |
|---|---|---|---|---|---|
| **MemoryArena** (2602.16313) [code] | memory across chains of interdependent subtasks: shopping, travel, progressive search, formal reasoning; pluggable memory (`add_chunk` / `wrap_user_prompt`); about 57 action steps per task | long-lived agent across sessions; a strong-memory baseline set (long-context, BM25, embeddings, Mem0, Letta, MIRIX, MemoRAG, ReasoningBank) | dependencies only run forward; **no task requires noticing that later information invalidates an earlier decision**; feedback modes hand the agent ground truth | no-regression check; comparison point with MAGE and FlowState numbers (different backbones) | code public, **no LICENSE**: run locally, do not redistribute; runners hold ground truth |
| **MAGE evaluation** (2606.06090) [ns abstract; ext] | MemoryArena with Qwen3.6-27B: +7.8-20.4 pp success rate; Revise worth 4.0-5.2 pp | Revise reopens an earlier boundary and keeps the flawed branch | the agent's own subtask summaries within one task; hindsight injected by design; no world artifacts, cutoff or forward remediation | a design for a path-structured baseline arm | no code |
| **FlowState evaluation** (2609.34565) [ext] | MemoryArena subset and τ³-Bench, DeepSeek-V4-Flash: +4.55 / +13.95 pp, about 40% fewer tokens | the D7 → D8 example has the same structure as `smoke_v1`'s premise | D7/D8 was never evaluated in isolation; aggregate metrics only; no cutoff; no remediation | a design for a typed decision/evidence-graph baseline arm | code not released |
| **PM-Bench** (2607.12385) [code] | prospective memory: 83 intentions over a synthetic week; hidden clocks and channels; explicit updates; lures | `smoke_v1`'s parked-work trigger (a ticket parked on a missing SDK capability, unblocked by a version bump) is an event-cued deferred intention | updates are explicit and apply only to pending intentions; no reopening; no fidelity; no remediation | direct external test of pattern F; a typed-intention arm is the bar (PIS 82.9% [abs]) | code and runs released; no LICENSE found; the action menu leaks active intentions |
| **STALE** (2605.06527) [abs] | 400 "implicit conflict" scenarios: state resolution, premise resistance, implicit policy adaptation | `smoke_v1`'s delayed-evidence trigger is an implicit conflict | conversational facts; no reopening of executed decisions; no remediation; over-intervention not priced | implicit policy adaptation as a "notice and act" measure; evidence that the bottleneck is acting, not reaching | access not recorded |
| **StateMemBench** (2608.19652) [abs] | 234 scenarios where "facts, constraints, and decisions are revised"; deterministic event programs; current vs superseded grading | built the same way as `smoke_v1` (event program → ground truth) | revisions are explicit operations; answers graded, not actions; no unprompted reopening | test of an explicit current-state arm; its matched control is the strongest prior that structure carries the gains | access unknown |
| **ClawArena** (2604.04202) [abs] | 64 scenarios, 365 staged updates, hidden truth, workspace files, shell checks | the closest existing harness | revision is probed by questions (prompted); targets are beliefs, not decision artifacts; no three-way probe; no per-decision scoring | the closest adaptation target (5 changes, see §5) | code claimed, URL not captured; license unknown |
| **Impact Is Not Invalidation** (2609.25130) [abs] | which stored claims a repository change falsifies; execution ground truth (10,369 claims, 184 flips) | a software world where a later change alters the validity of an earlier stored item (`smoke_v1` patterns A and F) | claims are test assertions, not decisions; no unprompted reopening; no remediation | a premise-level re-check probe through A1 `read_at` / `diff` | access unknown; trivial if the agent can run the claim's test |
| **TWIST** (2609.28575) [abs] | unprompted tension detection with surface-matched hard negatives; flat RAG detects 0.76-0.97 of contradictions with 16-43% false flags | the same construct as governance recall plus false-intervention rate | conversational; no remediation; "proposed" | metric design: report precision at matched recall | not released |
| **MerchantBench** (2607.28956) [abs] | 365-day e-commerce simulation; delayed order outcomes; agents must "revisit earlier decisions"; scored by net assets | later evidence changes the significance of earlier decisions, and the decisions are the **agent's own** | only net assets scored; no per-decision recall or precision; no negative controls | the only released venue with agent-authored decisions and delayed outcomes | Apache-2.0; expensive (365 steps per run) |
| **FinalityBench** (2609.04706) [abs] | executable financial decisions under delayed and reordered events from a hidden canonical log; 45 twin pairs identical at the decision instant | hidden canonical log ≈ `events.jsonl`; twin pairs are a rigorous form of "what was knowable then" | decisions are made at the instant, not reopened later | twin-pair design as a better fidelity scorer | unknown |
| **Clinical Hindsight Bias** (2609.13454) [abs] | cutoff-truncated vs full timeline; hindsight-trap metrics | historical-state fidelity | QA, not agent decisions | paired-cutoff design; evidence that plain masking suffices | unknown |
| **EvoCode-Bench** (2605.24110) [abs] | 26 stateful coding tasks; persistent workspace; cumulative executable tests over still-active requirements | remediation in a persistent codebase under requirement change | requirement changes are announced (prompted) | remediation and no-regression; cumulative tests as a scorer | data and infrastructure released |
| **DreamBench-SWE** (2608.20664) [abs] | multi-session software tasks with hidden oracles; no memory 21/180, verbatim 82, typed+raw 83, one Mem0 configuration 97 | same research hygiene (software world, frozen scenarios, hidden oracles) | recall of earlier evidence, not reopening decisions | an external venue: a temporal contestant is one more memory condition | unknown |
| **Memvara Agent Memory Benchmark** [code] | deterministic fact QA, 100 questions; Memvara 92.0, one-clock vector-RAG 89.0, naive 50.0 | the fidelity triad maps to now/then/stated | values, not actions; self-authored corpus; hashed TF-IDF baseline | shows fidelity can be met by an ingestion-timestamped log + as-of filter | Apache-2.0 |
| **LongMemEval** (2410.10813) [unv; repo cloned] | 500 questions over timestamped chat; knowledge updates, temporal reasoning | "knowledge update" means the latest value wins | prompted QA | retrieval sanity check only | MIT |
| **MemoryAgentBench** (2507.05257) [abs; code] | accurate retrieval, test-time learning, long-range understanding, conflict resolution | conflict resolution | the prompt tells the model a larger serial number is newer: prompted latest-wins | low | MIT |
| **τ²-bench** (2506.07982) [code] | single-episode, policy-constrained tool use; end-state grading | end-state grading | no multi-event history | no-regression only | MIT |
| **FutureSim** (2605.15188), **Forecast-Dojo** (2609.28876) [abs] | cutoff replay of forecasting; as-of forecast ledgers; Brier feedback | strict-cutoff replay infrastructure; inherited commitments (FutureSim's badWarmup) | forecasts, not executed decisions | design precedents | **do not use with this project's model**: FutureSim's window (Jan-Mar 2026) precedes the model's training cutoff, and the Claude CLI injects the real date; Forecast-Dojo code not located |

## 3. Construct validity of `smoke_v1`

**Answer-key note.** This section deliberately avoids pairing any trigger
event with the decision it affects, by id. `smoke_v1` is not held out, but
the repository rule is that documents do not quote its answer key (enforced
by `tests/test_smoke_scenario.py::test_docs_do_not_quote_smoke_ground_truth`).

**Method.** No ground-truth file was read. The assessment used only:
- the public event stream (`world/events/smoke_v1/events.jsonl` and its
  payloads);
- the seed repository's decision records;
- public run artifacts.

**Finding: every reconsideration trigger shares obvious, specific vocabulary
with the decision it bears on.** The decision is present in the current
workspace, or in a single earlier event.

- **Delayed evidence (pattern C).**
  - The affected decision record states its premise explicitly: the payment
    provider ends a subscription after its last automatic retry, so keeping
    paid features during retries is safe.
  - The trigger is a support event reporting an account still `past_due`
    long after the retries.
  - One read of the current decision record plus the event exposes the
    conflict. This is STALE's "implicit conflict" and PlanFence's
    "derivation currency".
- **Constraint disappears (pattern A).**
  - The affected decision record cites a hosting tier by name and the
    platform facts file.
  - The trigger is a hosting notice that retires that tier by name and
    changes the same file.
  - A near-miss decision also cites the platform facts file, but its premises
    are unchanged. Telling the two apart is premise checking on the current
    files, not temporal reasoning.
- **Parked work (pattern F).**
  - A ticket is parked because the vendored SDK version lacks a capability.
  - The trigger is an SDK version bump whose release notes name that
    capability.
  - This is a lexically matched, event-cued intention, PM-Bench's construct.

**Why nothing in `smoke_v1` forces temporal reasoning:**
- The history is 10 events, so `baseline-full` holds everything in context.
- Lags are a few events.
- Valid time and transaction time diverge in only one case, and there the
  event body itself states the divergence.
- A1 already gives every contestant as-of reads and diffs of world state, so
  those channels cannot separate contestants.
- Decisions are world-authored, so past-self claims are untestable
  (milestone-2 §0).

**Historical-state fidelity may be gameable.** It is scored as set-F1 over
event ids. A rule-based template computed from timestamps might score well
without any reconstruction. This is untested: testing it needs a template
reference agent, and ground truth was not read here.

**What `smoke_v1` predicts.** The literature predicts (unverified) that a
current-state agent with a decision/intention register and per-premise
re-checking saturates recall. Differences between contestants would then
show up as precision on the scenario's surface-matched near-miss controls.
- STALE, KWBench and "When Stale Constraints Go Unchecked" (2608.25553)
  [abs-level] suggest that real models may still miss visible evidence.
- No real-model run exists yet.

**Verdict.** `smoke_v1` is a valid **machinery check**. It is not a test of
temporal navigation, and it should not be extended to become one.

## 4. The planned scenario families

| family | added value | why |
|---|---|---|
| long_history | low, unless the decisive premise *leaves the current workspace* and the history exceeds the context window | Otherwise it measures retrieval capacity. MemoryArena, LongMemEval and MemoryAgentBench already cover that, and the evidence is hostile: DreamBench-SWE shows no separation among memory conditions; MEMTRACK finds Mem0/Zep do not help [3p]; Memvara's one-clock RAG is 100% on `knowledge_time`. The cost-scaling question can be read from the existing presets (k8/k32/k64/full). |
| high_noise | low | More near-miss distractors measure precision at matched recall, which TWIST already characterizes. Precision comes from claim-targeted re-checking (Impact Is Not Invalidation), not from a temporal mechanism. |
| deep_causality | low for this thesis | Fact → assumption → decision → workaround chains are what dependency tracking targets, with measured wins (PlanFence, MemTX, DeepRewind, Dependency-Guided Rollback Repair 2608.10502). With world-authored ADRs the chain is written down in current documents, so a temporal win would be confounded unless a dependency/TMS arm is present. |
| simple | already served by `smoke_v1` | — |

**Statistical power is a further problem.** A 30-50-event scenario with ≥50%
distractors yields about 10-20 required (decision, trigger) pairs, so
per-family confidence intervals need several scenarios per family.

**Recommendation: do not build these families.** If anything is ever built,
it is one small family designed around the three regimes in §6.

## 5. Adapting the contestant to existing benchmarks (Q3)

The shared runtime (`contestant_runtime/` plus a `MemorySystem`) needs four
shims for any external benchmark:

1. **Event shim:** external step → `AgentEvent`.
2. **Action shim:** answers, menu choices and tool actions need an action
   type beyond reopen and note. That is a harness change and must be logged
   as a benchmark change (CLAUDE.md rule 7).
3. **Tool shim:** external tools added to the runtime catalogue, with
   per-event budgets.
4. **Ground-truth firewall:** the external runner stays in the harness
   process, never the contestant process (A4). External runners usually hold
   ground truth next to the environment.

Ranked by value per effort (effort figures are the assessor's estimates):

| rank | benchmark | effort | tests | pitfalls |
|---|---|---|---|---|
| 1 | PM-Bench | ~2-3 days | parked work (pattern F) against published scaffolds; PIS is the bar | the menu leaks active intentions (keep it identical across arms); disable the ground-truth fallback; updates are explicit |
| 2 | EvoCode-Bench | ~3-5 days | remediation and no-regression under requirement change | cumulative tests must stay hidden from `run_command`; prompted |
| 3 | MemoryArena or τ²-bench | ~3-5 days + external environments | no-regression on forward dependencies | no LICENSE (MemoryArena); strip ground truth from runner observations; cross-provider judges break the same-model rule unless kept outside the comparison |
| 4 | MerchantBench | ~1-2 weeks, expensive | agent-authored decisions with delayed evidence | only net assets scored; needs reopen logging and per-decision attribution |
| — | ClawArena, STALE, StateMemBench, DreamBench-SWE, Impact Is Not Invalidation | verify access first | strong conceptual fits | ClawArena's probing questions are hints; Impact Is Not Invalidation is trivial if claim tests can be executed |
| ✗ | FutureSim, Forecast-Dojo | — | — | the replay window precedes the model's training cutoff; real-date injection by the CLI; code not located |

## 6. What would need a bespoke benchmark (Q4)

Only the combination of conditions the sweep could not find, restricted to
regimes where non-temporal methods are predicted to fail:

1. **Agent-authored decisions with preserved decision-time state.** This
   tests whether a cutoff-correct reconstruction of the agent's own context,
   assumptions and rejected alternatives changes reopening and remediation,
   compared with retrieval over the same record. MerchantBench has
   agent-authored decisions but no per-decision labels.
2. **Changes of significance with no fact superseded.** The earlier premise
   stays historically true while a later event changes its implications.
   STALE covers this only partly.
3. **Class-D divergence between valid time and transaction time, with
   executable backfill.** This is H2's regime (residual-hypotheses.md §3.1).

Design rules if one is ever built:
- Keep the decisive premise out of the current workspace and the current
  event.
- Reuse existing designs rather than invent new ones:
  - TWIST hard negatives;
  - StateMemBench event programs;
  - FinalityBench twin pairs;
  - the clinical paired-cutoff design with its hindsight-trap metrics;
  - ChronoMem's post-exposure protocol;
  - EvoCode-Bench cumulative tests.
- Include register, dependency/TMS and explicit-state arms, not only
  checkpoint+RAG.

## 7. Recommendation

1. **Freeze `smoke_v1`** as a machinery check, labelled "not a test of
   temporal navigation".
2. **Build no new scenario families.** Under disposition A, nothing in §6 is
   authorized.
3. **If the harness is reused for another question,** do two things first:
   - run the baseline presets on `smoke_v1` with a real model (the command
     exists: `smoke-baseline-claude`);
   - add a rule-based template reference agent, to test whether fidelity
     scoring can be gamed;

   then port to released benchmarks (§5) rather than author new ones.
4. **If H2 is ever run** (re-open trigger fired), build exactly one small,
   frozen class-D family from the reused designs in §6. Run it against the
   register, TMS and bitemporal-store arms, and accept the null if it comes.
