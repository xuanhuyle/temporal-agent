# Temporal Multiplicity, long-horizon calibration (v1)

| | |
|---|---|
| **Verdict** | **NOT_CALIBRATED.** No reachable pressure level produced any degradation. That holds for the four tested levels, which span R ≈ 0.76–5.9 and use two independent knobs. Every one of 40 scored units was right at the final state (A_final = 1.00 everywhere), and there were 0 regressions. No crossover exists to replicate, classify, or test against retrieval. |
| Subject-model calls | **28 of 50** (target 20–40). The calls were 4 lifetimes × (3 compactions + 4 probe calls). There were 0 shorten-retries, 0 retrieval calls and 0 WebFetch calls. Every call used the same model and the same harness prompts. Ledger: `results/temporal-multiplicity/calibration-v1/call_ledger.json`. |
| Brief | `docs/prompts/temporal-multiplicity-long-horizon-calibration-v1.md`. A/B/C was not run, and no historical self was executed. |
| Code | `src/multiplicity_experiments/long_horizon_calibration.py`. `runtime.js` gets an opt-in `probe_policy` flag; the PR #6 default is unchanged. |
| Tests | `tests/test_multiplicity_long_horizon_calibration.py` |
| Raw data | `results/temporal-multiplicity/calibration-v1/`: compact trajectories (every compacted memory, every probe decision), analyses and static validation. The analyses re-derive byte-identically from these files together with the regenerated episodes. |

## 1. Pressure definition

**R = L / M.**
- **M** is the persistent-memory budget: 1,500 characters, unchanged from PR #6.
- **L** is the length of a deterministic, canonical, lossless representation of all active decision-relevant state at the end of the lifetime. It is one line for the defaults plus one canonical line per active rule, for example `Venables Pneumatics: pay in GBP (PO >= EUR 6,100)`.
- Filler and noise are not counted.

**Two knobs.** Both add load rather than shrinking memory:

| knob | what it varies | brief §2 wording | when used |
|---|---|---|---|
| **Knob 1** | number of independent rules n | "number of active independent rules" | Stage A |
| **Knob 2** | fraction q of rules carrying their own amount threshold, stated in the rule's own sentence ("…, if the PO is EUR 7,800 or more"). Thresholds are EUR 2,000–12,000 in steps of 100. | "number of active qualifiers/exceptions" | Used once, after every knob-1 level sat at ceiling (brief §7, "All levels >0.9") |

Knob 2 was pre-registered in `a890f30` before any call on it.

**Fixed across all levels.** These are the same as PR #6:
- the runtime: working context 7,000 chars, model-written compaction, the same generic compaction prompt;
- the model, the domain, and the six rule kinds (vendor currency, client carrier clause, client substitution notice, harbour-master site, cold-chain category, safety co-sign categories).

## 2. Generator and static validation (0 calls)

**Lifetimes.** Each lifetime is 12 message-only weekly stages, each sized to about 1,800–2,300 characters. That fixes exactly 3 compactions, at stages 4, 8 and 12, at every pressure level.
- New rules arrive at a balanced rate, about n/12 per stage, one bundled notice per rule kind per stage.
- Static PR #6 noise fills each stage up to the volume window.

**Scored subset.** A separate holdout seed (7919) chooses 10 scored rules before any call, and the subject never sees which ones they are. Every rule uses the same sentence templates.

**Probes.** Each scored rule gets 2 probe requests.
- Knob 1: both probes trigger the rule.
- Knob 2: one probe is at ≥ 1.3× the rule's threshold and one at ≤ 0.75×. All probe amounts are below the Finance threshold of EUR 20,000.

**`validate()` checks every episode for:**
- the exact compaction schedule;
- unique entities, with unique first words that are disjoint from the noise;
- no blanket or contradicting wording ("all other", "no longer", "instead of", "except", "unless": the Brandt failure mode from PR #6);
- each probe is time-invariant from the rule's stage onwards;
- each probe triggers exactly one rule;
- each probe's answer differs from the default; for knob 2, each probe is sensitive to its threshold;
- no `rule`, `scored` or `thr` field appears in the subject view.

| knob | levels × seeds | rejected | R range per level |
|---|---|---|---|
| 1 | n = 17, 27, 37, 57, 76, 95, 153 × 200 seeds | 0 | 0.47–0.50, 0.75–0.78, 1.00–1.05, 1.51–1.56, 2.01–2.07, 2.48–2.55, 3.98–4.05 |
| 2 (q = 1) | n = 100, 140, 153 × 200 seeds | 0 / 0 / 15 | 3.82–3.89, 5.35–5.41, 5.84–5.92 |

The 15 rejected seeds at n = 153, q = 1 miss the 3-compaction schedule. The pre-registered rule was "first schedule-feasible seed ≥ 1004", and it selected seed 1004.

Entity pools cap the generator at n = 162, which means R ≈ 4.25 for knob 1 and R ≈ 6.2 for knob 2. For knob 2, the stage-volume window rejects a growing share of seeds above n ≈ 155.

## 3. Exact model-call count

| batch | what | expected | actual | cumulative |
|---|---|---|---|---|
| A1 | knob 1, R 0.76, seed 1001 | 7 (max 10) | 7 | 7 |
| A2 | knob 1, R 2.54, seed 1002 | 7 (max 10) | 7 | 14 |
| A3 | knob 1, boundary moved once to R 4.02, seed 1003 | 7 (max 10) | 7 | 21 |
| Q1 | knob 2 (q = 1) at the A3 load, R 5.87, seed 1004 | 7 (max 10) | 7 | **28** |
| Stage B, retrieval | not run: no crossover and no failure | – | 0 | 28 |

Each lifetime made 7 calls:
- **3 compactions.** The compactor sees the current memory plus the working context.
- **4 probe calls.** These ran at the 3 pre-compaction checkpoints (c4, c8, c12, where the raw rule messages are still in context) and at the final compacted state (c12c, memory only). Each call is one batch of the 20 probe requests.

## 4. Coarse sweep (Stage A, adaptive)

The adaptive procedure was the brief's: start at R ≈ 0.75 and R ≈ 2.5. Both were above 0.9, so the upper boundary was moved once, to R ≈ 4. That level was also above 0.9, so pressure was raised once with a new principled knob (knob 2).

| R | knob | seeds | compactions | final accuracy | regression units | retrieval-resistant failures |
|---|---|---:|---:|---:|---:|---:|
| 0.5 | 1 | not run (below a level already at ceiling) | | | | |
| 0.76 | 1 (n = 27) | 1 | 3 | 1.00 (10/10) | 0 / 10 | – (no failure) |
| 1.0, 2.0 | 1 | not run (bracketed by levels at ceiling) | | | | |
| 2.54 | 1 (n = 95) | 1 | 3 | 1.00 (10/10) | 0 / 10 | – |
| 4.02 | 1 (n = 153) | 1 | 3 | 1.00 (10/10) | 0 / 10 | – |
| 5.87 | 2 (n = 153, q = 1) | 1 | 3 | 1.00 (10/10) | 0 / 10 | – |

Scores at every earlier probed checkpoint were also 1.00 for every unit. For Q1, the brief's probe-mean metric gives the same result as the primary all-or-nothing score: 1.00, with 0 regressions.

## 5. Local replication (Stage B)

Not run. The brief replicates only "around the crossover", and none was found. Running the easy regime again was not allowed ("Do not keep running the easy … regimes").

## 6. Final capability by pressure, and what the compactor did

Compression here means the canonical state length L divided by the final memory length.

| R | L (chars) | final memory (chars) | compression | final memory encoding |
|---|---:|---:|---:|---|
| 0.76 | 1,140 | 1,470 | 0.8× | prose, one rule per line |
| 2.54 | 3,807 | 1,491 | 2.6× | grouped by kind, names merged with slashes ("Lighthouse/Spinnaker/Starboard Berth") |
| 4.02 | 6,028 | 1,485 | 4.1× | invented legend "Names = 5-letter prefixes" ("Brightway:SiskiPetreMerli…") |
| 5.87 | 8,798 | 1,465 | 6.0× | legend "Name35 = applies if PO ≥ EUR 3,500"; 4-letter prefixes with thresholds in hundreds of EUR ("Moor116Waxw75"); categories factored by noun ("adh(knurl49mach105…)") |

The compactor used the full budget at every level and never needed a shorten-retry. As load rose, it invented progressively denser lossless encodings, and the decider read them back correctly.

**Retention beyond the scored rules.** A string check on the final memories, followed by manual inspection of every miss, found every one of the 153 rules represented in both A3 and Q1. All of the string check's misses were abbreviations it doesn't recognise ("alu panel", "c-fibre lining", "fibgl sleeve"). The one blemish is in Q1, on an unscored vendor: "Eskildsen Drives" was written as "Eske43", with the prefix misspelt. It is still unique.

## 7. Regression counts

| | all levels |
|---|---|
| (lifetime, scored unit) pairs | 40 |
| regressions, primary score | 0 |
| regressions, brief's probe-mean criterion (earlier − final ≥ 0.5 and final ≤ 0.5) | 0 |

The regression rate is therefore 0 at every level.

## 8. Failure taxonomy

There were no failures among scored units, so no D1–D5 sample exists.

Benchmark-flaw (D6) audit: nothing ambiguous showed up in the scored probes or in the memories.

The only distortion observed anywhere is the unscored "Eske" prefix. It would be a D2 candidate only if a request ever named Eskildsen, and none did.

## 9. Retrieval sanity check

Not run, at 0 calls. There was no confirmed failure to test.

The procedure was committed in `11a78f4`, before any failure could have been observed:
- **Selection:** regression units in holdout order, round-robin across lifetimes, k = 3.
- **Retrieval:** the query is the failed request text, run through the existing model-ranked `search()` over the raw archive.
- **Repair:** the top-1 record is appended to memory and the decision is re-run once.

It remains available for a future calibration.

## 10. Chosen operating regime

None.

## 11. Verdict: NOT_CALIBRATED

Brief §10 requires reproducible non-catastrophic degradation, several D1–D5 failures, and failures that survive retrieval. None of these can hold, because no degradation occurred at any pressure this generator can reach.

**What raising pressure would require.** Going further means redesigning the environment, which the brief rules out ("do not keep escalating complexity"; "if the generator cannot achieve clean pressure levels without extensive redesign, stop and report"). Concretely:
- **Bigger pools and longer lifetimes.** Entity pools cap n at 162, and the 12-stage schedule limits it further for knob 2. More stages mean more compactions and probes per lifetime (9–13 calls instead of 7).
- **Higher-entropy state.** At the knob-2 point the compactor stored about 9.6 characters per thresholded rule. It had not run out of tricks: shorter prefixes and further factoring were still available.

**What this adds to PR #6.** PR #6 found NO_HEADROOM at R ≈ 0.42. This calibration extends that result to:
- 14× PR #6's pressure, and 6× the memory budget in canonical terms;
- dense, dormant, never-repeated rules;
- per-rule numeric clauses.

With the same strong model as its own compactor, bounded memory did not fail naturally on this kind of state. On this kind of state, the canonical length L overstates the effective load by about 4–6×. Each rule here is a short unique key with a templated consequence, so a capable compactor can encode the set almost losslessly.

**Untested hypotheses for a possible future brief.** These are not recommendations and were not run. A crossover may require:
- state whose items are individually high-entropy (free-text commitments, heterogeneous multi-field exceptions);
- entity names that share prefixes, as real ones do. The validator here forces unique first words to rule out ambiguity, and that is exactly what made prefix abbreviation lossless;
- many more items than the generator supports;
- a weaker compactor than the decider. That last option would change the brief's same-model premise.

## Deviations and assumptions

1. **Knob 2 was the single allowed pressure increase.** It was pre-registered: generator, probe design and scoring were committed before its call. It was run near its feasible maximum: n = 153 against a cap of 162. That n was chosen to equal the A3 load and so isolate the knob. Any lower knob-2 level would sit even further below the compactor's demonstrated capacity, so the bracket could not form within the feasible range.
2. **Primary unit score is all-or-nothing:** 1 only if both probes are right. Under the probe mean, a thresholded rule that was dropped entirely still scores 0.5, because the below-threshold probe matches the default. The brief's probe-mean criterion is reported alongside and agrees at every level.
3. **One replicate per probe; probes only at pre-compaction checkpoints and the final state.** This was for cost. Fresh replicates would have been spent only on candidate failures, and there were none.
4. **The string retention check in `analyse` is a heuristic.** It gives false negatives under the compactor's abbreviations. Section 6 reports the manual inspection.
5. **One seed per level, as Stage A prescribes.** A single seed cannot show reproducibility, but none of the four levels moved off ceiling.
6. **Subject isolation.** Subjects are `web-fetch` subagents that receive only the episode messages, memory and requests. Tests enforce that ground truth (`rules`, `scored`, `thr`, answers) never appears in a workflow script.

## Reproduce

```
PYTHONPATH=src python -m multiplicity_experiments.long_horizon_calibration validate              # knob 1, 0 calls
PYTHONPATH=src python -m multiplicity_experiments.long_horizon_calibration episode --id A1 --seed 1001 --n-rules 27 --out wf
#   A2 --seed 1002 --n-rules 95;  A3 --seed 1003 --n-rules 153;  Q1 --seed 1004 --n-rules 153 --q 1.0
#   (each also writes wf/trajectory_<id>.js, the workflow that ran the lifetime)
PYTHONPATH=src python -m multiplicity_experiments.long_horizon_calibration analyse \
  --episodes wf/episode_A1.json wf/episode_A2.json wf/episode_A3.json \
  --trajectories results/temporal-multiplicity/calibration-v1/stage-a/trajectory_A*.json
```
