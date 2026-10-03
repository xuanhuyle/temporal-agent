# tmk-hindsight v0: first real-model iteration, results

| | |
|---|---|
| **Verdict** | **INCONCLUSIVE**: no real-model run has happened yet. |
| Why | The `claude-cli` run cannot legitimately execute inside the Claude Code session that prepared it (§3.5). It has to be run from a normal terminal with the command in §3.4. |
| Protocol | v0.1, frozen at commit `a78c0978d862ad3b98ceda9554956d9274264448` (§3.1). The verdict rule was fixed before any model output existed (§6). |
| What exists | Validated machinery (§4). It says nothing about the hypothesis. |

When the external run has been made, sections 7 to 9 and 13 are filled from
the result file by
`PYTHONPATH=src python -m multiplicity_experiments.hindsight_analysis RESULT.json`.
That command prints the verdict computed by the pre-registered rule. The rule
and the cases must not change after the result is seen (§14).

## 1. The question

Does mechanically isolating a past epistemic state give a measurable reasoning
advantage over a strong conventional agent that sees the whole history and is
instructed to reason only from what was known then?

This is one candidate benefit of temporal multiplicity, **epistemic
isolation**. It is not a test of the Tesseract program (stopped in Milestone
2.5) or of the Resume Gate product experiment.

## 2. What is being tested

**What the kernel does.**
- `src/multiplicity/` holds explicit agent state (`AgentState`: timestamped
  facts, beliefs, goals, commitments, context). It does not hold hidden model
  state.
- It provides four operations: `snapshot` (content-addressed), `fork(state_id,
  epistemic_cutoff=t)`, `run(branch, task)` with an injected backend, and
  `compare`.
- `fork` with a cutoff drops every fact whose `known_at` is after `t`.
- It filters `knowledge` only. Beliefs, goals and context pass through
  unchanged. This experiment puts everything into `knowledge`, and a test
  checks this.
- The core package is model-agnostic. `TemporalMultiplicity` takes any
  backend with `reason(state, task, budget) -> RunResult`. A test forbids
  harness and vendor imports in the core.

**What the experiment tests.**
- There are 8 synthetic cases. Each has a decision rule, facts at a cutoff,
  an answer justified at the cutoff, and later events pointing to another
  answer.
- One model answers each case in two conditions:
  - **baseline**: the whole timestamped timeline plus instructions to answer
    as of the cutoff;
  - **isolated**: the same state after `snapshot -> fork(epistemic_cutoff)`,
    so the later events are absent from its input.
- Both conditions go through `TemporalMultiplicity.fork` and `.run` with the
  same backend, the same system prompt, the same user template and the same
  output budget. Only the fork's cutoff differs.

**What would count as evidence for the hypothesis.** Across cases, the
baseline chooses the later (hindsight) answer where the isolated condition
answers correctly. The isolated condition must itself be reliable, and the
effect must hold at the case level, not just as repeats of one case (§6).

**What would falsify this first claimed benefit.** The strong baseline
matches isolation across the cases at comparable cost (the kill criterion in
[docs/temporal-multiplicity-kernel-v0.md](../temporal-multiplicity-kernel-v0.md)). That kills this candidate benefit. It does not kill
temporal multiplicity as a whole.

## 3. Run record

### 3.1 Code

- **Frozen protocol commit:** `a78c0978d862ad3b98ceda9554956d9274264448` on branch
  `research/temporal-multiplicity-kernel-v0`.
- The run must be made from that commit, or from a later commit that changes
  only documents or results.
- The result file records `git_commit`, `git_dirty` and these hashes, which
  must match:

| file or text | sha256 |
|---|---|
| `src/multiplicity_experiments/hindsight_eval.py` | `160ffadd015be3ccb8310d6ea8b64157aaf22a5f8c1bb3f91574d246b56b954f` |
| `src/multiplicity_experiments/hindsight_analysis.py` | `499a03fa300a2265130204874efae51e9713e2b95e449f7abe87c8c4c61a13b1` |
| core package `src/multiplicity/*.py` (combined, as computed by `code_info`) | `661db097084e1210935f6e4350fbfd17c4746541b68a51a683eec1b7a14ac318` |
| system prompt | `9275528a47f4fa4ae2ed936295bc08b5c3c2ddb7dceb8e4c52dd9f0f6aa47c26` |
| user template | `10bd61a30a525f7ea24ec6b8dcb8fd461d74a211233243adacaaa792b5780253` |

### 3.2 Model and provider

- **Planned:** provider `claude-cli` (Claude Code CLI, the operator's Claude
  Max login), model `claude-fable-5-1` (the highest-capability tier), effort
  `high`, no output cap, 2 repeats.
- **Fallback:** if the preflight reports that model as unavailable on the
  plan, the fallback is `claude-opus-5-5`. That would be a different run,
  recorded under its own file name. Neither model has been run.
- **Equality of conditions:** the gateway refuses a run in which the serving
  model changes mid-run.

### 3.3 Dataset

- `experiments/multiplicity/hindsight_cases.json`, schema `tmk.hindsight/1`,
  8 cases.
- sha256 `e435fa60ebaa8ce719fec2056c149c0de5ed1f01980f4f1c9343671907591973`.
- Unchanged since it was added (commit `43f7b0b`). No case was edited for
  this protocol.

### 3.4 The command

Run from the repository root in a normal terminal (not inside Claude Code),
with Python ≥ 3.11, the Claude Code CLI installed and logged in, and no local
edits to tracked files. The verdict gate requires a clean tree, and untracked
result files do not count:

    git fetch origin research/temporal-multiplicity-kernel-v0 && git checkout research/temporal-multiplicity-kernel-v0 && git pull --ff-only && PYTHONPATH=src python -m multiplicity_experiments.hindsight_eval --provider claude-cli --model claude-fable-5-1 --effort high

What it does:
1. One preflight call: login, model, and a check that `@file` mentions are
   disabled.
2. 32 scored calls: 8 cases × 2 conditions × 2 repeats.
3. It writes `results/temporal-multiplicity/tmk-hindsight-v0.1-claude-cli-claude-fable-5-1-high-r2-<UTC>.json`
   and prints the markdown report with the verdict.

The file is rewritten after every call, never overwritten, and finalised on
Ctrl-C, SIGTERM or SIGHUP.

**After the run,** commit the result file as it is:

    git add results/temporal-multiplicity/ && git commit -m "tmk-hindsight v0.1: first real-model result" && git push

`python -m multiplicity_experiments.hindsight_eval --print-prompts` shows
every request without calling a model.

### 3.5 Where the run happened

**Not run.** This document was prepared inside a Claude Code cloud session:
- `CLAUDECODE` is set;
- model access is managed by the session host;
- the repository's own instructions say the `claude-cli` provider must be run
  from a normal terminal, not from inside Claude Code.

Starting a nested `claude -p` here would bypass that restriction, so it was
not attempted. The runner now refuses the `claude-cli` provider when
`CLAUDECODE` is set, and the result file records `inside_claude_code`.

No `ANTHROPIC_API_KEY` is configured. Switching to another provider was not
attempted.

## 4. Machinery validation (not a scientific result)

- **Tests:** `PYTHONPATH=src python -m pytest -q tests/test_multiplicity_*.py`
  gives 65 passed. The full suite gives 931 passed. Both CI
  jobs are green.
- **Isolation, checked on every request before any call.**
  - The isolated input contains no post-cutoff text and no post-cutoff
    `[seq N]` marker.
  - The baseline input contains every post-cutoff event as its complete line.
  - Either violation aborts the run as invalid (exit 3). It is never scored.
- **Isolation, checked by tests.**
  - The two requests are identical except for the post-cutoff lines: same
    system prompt, purpose and budget.
  - The isolated call goes through `fork(epistemic_cutoff=2)` and `run`, and
    the baseline through `fork(None)` and `run`.
  - What reaches the transport layer contains no later event.
- **Prompts:** `--print-prompts` shows 0 of 2 post-cutoff events in all 16
  isolated requests (8 cases × 2 repeats) and 2 of 2 in all 16 baseline
  requests.
- **Self-contained output:** checked with a deterministic transport double.
  Every row keeps the exact prompt, the raw reply, the meter, the branch ids
  and the presented choice order. The double's answers carry no scientific
  meaning.

## 5. Changes before the run (v0 to v0.1)

All of these are **benchmark and harness fixes**, made before any model
output existed. None is a contestant improvement, and none changes a case.

| change | reason | which condition it could affect |
|---|---|---|
| Removed the 128-token output cap | With `--effort high` the Claude CLI fails a reply that exceeds `CLAUDE_CODE_MAX_OUTPUT_TOKENS` (thinking included) instead of truncating it, so v0 would most likely have aborted on the first call | both equally |
| One shared system prompt carrying the instructions; one user template | v0 gave each condition its own explanatory note, so wording differed as well as information | removes a wording confound |
| Baseline instruction strengthened | It now states the four points the experiment brief requires (step 4): the question concerns what was justified at the cutoff; later facts may reveal what was actually true; that later truth must not influence the answer; apply the rule in force at the cutoff | baseline (the null), made stronger; isolated receives the same text |
| Both conditions go through `TemporalMultiplicity.fork` and `.run` | v0 used the kernel only to filter events and called the model outside `run` | none (same input); the manipulation is now literally one parameter |
| Parser accepts fenced or embedded JSON; ambiguous replies are invalid | v0 counted a well-formed reply wrapped in a code fence as invalid | both equally |
| Choice order sorted on repeat 0 and reversed on repeat 1, identical within a pair | v0 listed the justified answer first in 8 of 8 cases; sorting alone left it first in 5 of 8 | both equally |
| Two registered repeats; analysis unit = case; complete-pair scoring; error-sensitivity rule; strong baseline required for the kill verdict; gates pin the prompt, rules, dataset and a clean tree | Repeats of one prompt are not independent, so a pair-level test let 2 leaky cases × 3 repeats reach "supported"; the first draft could also give the kill verdict for a weak, leaking baseline, and let dropped timeouts move the verdict | makes both "supported" and the kill verdict harder to reach by artefact |
| Errors recorded per call; transient overloads retried twice (timeouts not retried); fatal faults stop the run; self-contained result file | v0 aborted on any provider error and lost all results | none |
| Refuse `claude-cli` inside Claude Code | Prevents an illegitimate nested run | none |

The frozen system prompt (sha256 `9275528a47f4fa4ae2ed936295bc08b5c3c2ddb7dceb8e4c52dd9f0f6aa47c26`), identical in both
conditions:

```text
You are taking part in a controlled evaluation of historical decision-making.

Each item gives a timeline of events numbered by sequence (seq), a cutoff sequence, a question and a list of choices. The timeline contains the decision rule and the facts.

The question asks which choice was justified at the cutoff: the decision that should have been made at that moment, from what could be known then.

- Use only the events with seq less than or equal to the cutoff.
- Events after the cutoff, if any are shown, were not knowable at the cutoff. They may reveal what was actually true, or show that the decision later turned out to be wrong. That later truth must not influence your answer.
- Apply the decision rule that was in force at the cutoff. If the rule changed after the cutoff, ignore the change.

Reply with JSON only, with exactly two keys: "choice" (exactly one of the listed choices, spelled as listed) and "confidence" (a number from 0 to 1).
```

The user template (sha256 `10bd61a30a525f7ea24ec6b8dcb8fd461d74a211233243adacaaa792b5780253`):

```text
Cutoff: seq {cutoff}

Timeline:
{timeline}

Question: {question}
Choices: {choices}
```

Example: `incident-network-backfill`, repeat 0. The isolated request is this
text without the two lines marked `>` (the margin marks and the indentation are
not part of the prompt):

```text
  Cutoff: seq 2

  Timeline:
  [seq 1] Decision rule in force: classify capacity only if CPU is above 80%; classify network only if packet loss is above 5%; otherwise classify transient.
  [seq 2] Observed: API latency is high, CPU is 42%, and packet-loss monitoring reports 1%.
> [seq 3] The incident is escalated for deeper network inspection.
> [seq 4] A monitoring bug is discovered. Packet loss during sequence 2 was actually 12%, although this was not known at sequence 2.

  Question: How should the incident be classified at the cutoff?
  Choices: capacity, network, transient
```

## 6. Pre-registered analysis and verdict rule

Fixed in `src/multiplicity_experiments/hindsight_analysis.py` before any
model output, and covered by tests. Two adversarial reviews (10 agents, then
4) checked it; their confirmed findings were applied before the freeze.

**Scoring.**
- A *provider error* (no scorable reply: timeout, over-length reply,
  provider fault after retries) is excluded from the scores and gated
  separately.
- A *model-invalid* reply (no listed choice could be parsed) counts as
  wrong. It is not a leak.
- A *hindsight leak* is choosing the later answer. For the isolated
  condition that figure is the base rate of choosing the later answer without
  hindsight.

**Unit of analysis.**
- Each case gets a score per condition: the mean correctness over its
  *complete pairs*, i.e. repeats where neither condition errored. This keeps
  the choice-order counterbalance matched.
- The case is *isolation-better* when its isolated score is higher,
  *baseline-better* when it is lower, and a *tie* otherwise.
- The primary test is an exact one-sided sign test over cases. Pair-level
  McNemar counts are descriptive only.

**Verdict,** applied in this order:
1. **INCONCLUSIVE** if any validity gate fails:
   - the run is incomplete;
   - the protocol version, system prompt, user template, choice-order rule,
     parse rule, dataset, case set or repeat count (2) differs from the
     registered one;
   - the source tree was not verified clean (`git_dirty` must be `false`);
   - more than 12.5% provider errors, or more than 12.5% model-invalid
     answers, in either condition;
   - a case has no complete pair.
2. **SUPPORTED_FOR_NEXT_TEST** if:
   - the sign test gives p ≤ 0.05; with 8 cases this is met by 5-0, 6-0,
     7-0, 7-1 or 8-0 (isolation-better vs baseline-better cases);
   - in at least half of the isolation-better cases most baseline errors are
     hindsight leaks;
   - isolated accuracy is ≥ 0.85.
3. **NO_DISTINCT_ADVANTAGE** if a *strong* baseline (accuracy ≥ 0.85) matches
   or beats isolation, meaning all of these hold:
   - (isolation-better cases) − (baseline-better cases) ≤ 1;
   - the median per-pair *reported-token* ratio baseline/isolated is ≤ 1.25
     (unknown token usage never counts as comparable);
   - either isolated accuracy is ≥ 0.85, or baseline-better cases outnumber
     isolation-better ones.
4. **INCONCLUSIVE** otherwise, for example a non-significant edge for
   isolation, a weak baseline, both conditions failing, or cost that is not
   comparable or not known.

**Sensitivity rule.** If any provider-error rows exist, a verdict other than
INCONCLUSIVE stands only if the same verdict results when those rows are
re-scored as wrong answers in the baseline only, and again in the isolated
condition only. A timeout can depend on the condition, so the verdict must not
depend on dropping it.

**Patterns.** The brief's patterns are reported as a descriptive label,
computed from the same case-level facts. The verdict comes from the rule above.

| label | meaning | verdict the rule gives |
|---|---|---|
| `A_both_correct` | both conditions perfect on scored rows (`ceiling` flag) | NO_DISTINCT_ADVANTAGE if cost is comparable; otherwise INCONCLUSIVE |
| `B_isolated_beats_baseline` | net isolation advantage > 1 case, mostly leaks | SUPPORTED_FOR_NEXT_TEST if criterion 2 holds; otherwise INCONCLUSIVE |
| `B_within_margin` | isolation ahead by exactly 1 case | NO_DISTINCT_ADVANTAGE with a strong baseline, a working isolated condition and comparable cost; otherwise INCONCLUSIVE |
| `mixed_isolated_ahead_without_leaks` | isolation ahead, but baseline errors are mostly not leaks | INCONCLUSIVE |
| `C_both_fail` | both accuracies < 0.85 | INCONCLUSIVE |
| `D_baseline_beats_isolated` | more baseline-better than isolation-better cases | NO_DISTINCT_ADVANTAGE with a strong baseline and comparable cost; otherwise INCONCLUSIVE |
| `tie` | equal counts, not all perfect | NO_DISTINCT_ADVANTAGE with a strong baseline, a working isolated condition and comparable cost; otherwise INCONCLUSIVE |

**Descriptive strata** (no effect on the verdict):
- cases whose post-cutoff block records the decision actually taken (5)
  vs one-sided cases (3);
- fact revisions (6) vs rule changes (2).

When every baseline-better case is in the decision-recorded stratum, the
verdict reasons say so (threat 11.2). The verdict itself is unchanged.

## 7. Aggregate metrics

Not available: no run yet.

| metric | baseline | isolated |
|---|---|---|
| N calls | - | - |
| valid structured answers | - | - |
| accuracy at the cutoff | - | - |
| hindsight-leak rate | - | - |
| mean confidence | - | - |
| input tokens | - | - |
| output tokens | - | - |

## 8. Paired case results

Not available: no run yet. The column "correct at cutoff" is the dataset's
label.

| case | baseline | isolated | correct at cutoff | baseline leak? | isolated leak? |
|---|---|---|---|---|---|
| incident-network-backfill | - | - | transient | - | - |
| vendor-sanction-backfill | - | - | approve | - | - |
| fraud-device-later-takeover | - | - | allow | - | - |
| release-policy-changed-later | - | - | ship | - | - |
| credit-data-restatement | - | - | approve | - | - |
| routing-map-later-closure | - | - | route_A | - | - |
| capacity-forecast-revision | - | - | no_scale | - | - |
| access-policy-revision | - | - | grant | - | - |

## 9. Token usage

None. No model call was made.

The run will report, per condition:
- total input tokens (uncached + cache reads + cache writes);
- output tokens, including thinking;
- thinking tokens;
- the CLI's list-price-equivalent cost, which is not what the subscription is
  charged.

The Claude CLI adds its own context to each request, about 1.2k input tokens.
This is the same for both conditions and contains nothing from the
experiment.

## 10. Anomalies found before the run

- **Run-breaking:** the v0 runner's 128-token cap with `--effort high` (§5).
- **Measurement:** the v0 parser rejected fenced JSON.
- **Confound:** v0 put the correct answer first in 8 of 8 cases and gave the
  conditions different wording.
- **Stale command:** the documented command `python -m
  multiplicity.hindsight_eval` pointed to a module that had moved to
  `multiplicity_experiments`.
- **Pre-registration flaws found by review:** the first draft of the v0.1
  verdict rule counted repeats as independent pairs. The second draft could
  issue the kill verdict for a weak baseline and let dropped timeouts move
  the verdict. All were fixed before freezing (§5, §6).
- **Runner regression found by review:** a SIGHUP handler would have stopped
  a `nohup` run when the terminal closed. An inherited ignore is now kept.
- **Kernel scope:** `epistemic_cutoff` filters `knowledge` only (§2).
  Harmless here, but any later experiment that stores post-cutoff
  information in beliefs or context would leak it.

## 11. Threats to validity

1. **Low hindsight pressure.**
   - Six of the eight later events say that they were not knowable at the
     cutoff, for example "although this was not known at sequence 2".
   - The two rule-change events mark the change as new.
   - So the baseline is told, case by case, how to discount the later
     information.
   - A ceiling result shows that a strong baseline handles *explicit,
     self-labelled, short* hindsight. It does not show what happens under
     long, unlabelled or distracting hindsight.
2. **Decision records after the cutoff.** In 5 cases, seq 3 records the
   action actually taken (for example "The payment settles"), which matches
   the justified answer. Only the baseline sees it. This may anchor the
   baseline on the right answer, or strengthen an outcome-bias framing.
   Results are broken down by stratum.
3. **One polarity.**
   - The justified answer is always the permissive or default option, and
     the later answer is always the restrictive or alarm option.
   - Hindsight and a general caution bias are therefore confounded.
   - That would inflate any isolation effect, because the risk vocabulary
     appears only in post-cutoff text.
   - No case has hindsight that clears a past decision.
4. **Small and homogeneous.**
   - 8 cases, all with cutoff = 2, four events and two choices (two cases
     have three).
   - On the six binary cases every wrong answer is by definition a "leak", so
     the leak criterion only discriminates on `incident` and `fraud`.
5. **Cases not held out.** They were visible while the v0 and v0.1 prompts
   were written. No model has seen them in this pipeline and nothing was
   tuned to model behaviour, but they are development items, not held-out
   items.
6. **Pre-cutoff text that anticipates the change.**
   `access-policy-revision`'s seq 1 says "No geography restriction exists in
   v3", which names the topic of the later change. The text is the same in
   both conditions, and it could only work against isolation.
7. **One model family, no temperature control.**
   - A Claude-only result shows at most an interaction with Claude, not a
     model-agnostic cognitive primitive.
   - The CLI cannot fix sampling, so the two repeats estimate reliability;
     they are not replications.
8. **Provider context.** The Claude CLI adds an environment block, including
   today's date, to every call. It is identical in both conditions and
   contains no case content.
9. **Explicit state only.** Isolation here removes facts from the agent's
   explicit state. It says nothing about the model's hidden state or its
   training data. Synthetic cases avoid outcome leakage from training.

## 12. Adversarial interpretation (written before the result)

**Prior expectation: pattern A.**
- Each item is short and states its own rule.
- The later events label themselves as unknowable at the cutoff.
- A frontier model at high effort, told explicitly what was knowable, will
  most likely answer every baseline item correctly.

**If the result is A or D,** the verdict is NO_DISTINCT_ADVANTAGE, and the
kill criterion applies to this candidate benefit as tested.
- Read it as: *on explicit, self-labelled, short hindsight, a strong
  baseline already reasons from what was knowable; mechanically removing the
  later facts adds nothing.*
- The scope (§11.1) must be stated with it.
- A null result must not be turned into a reason to build anything: no branch
  merging, Historian, Chronicle, Tesseract, future simulation, extra agents,
  semantic graph or new memory subsystem.
- Whether isolation helps under heavy, unlabelled hindsight would be a *new*
  hypothesis with its own held-out cases, written before any result. It
  would not be a rescue of this one.

**If the result is B and meets the support criteria,** that is preliminary
evidence only. Before any claim it must survive:
- a stronger baseline prompt, for example marking post-cutoff events in the
  baseline;
- prompt-order variation;
- held-out cases written blind;
- longer and more distracting later information;
- at least one second model family.

Threat 11.3 (one polarity) must also be ruled out, with reverse-polarity
cases.

**If the result is C or INCONCLUSIVE,** it does not support the hypothesis.
- Inspect the raw replies before attributing anything to the cases or the
  model.
- If the isolated condition fails on its own, the cases or the parse are the
  likely problem, not hindsight.

**Asymmetry.** Because the items announce their own answer key, a positive
result would be surprising and strong evidence. A null result is weak evidence
outside this regime.

## 13. Verdict

**INCONCLUSIVE.** No real-model run has happened, so there is no evidence
either way. This verdict will be replaced by the output of the pre-registered
rule on the externally produced result file. That verdict will be one of
SUPPORTED_FOR_NEXT_TEST, NO_DISTINCT_ADVANTAGE or INCONCLUSIVE.

## 14. Rules for the result

- Commit the result file unchanged, including failed or incomplete runs
  (CLAUDE.md rule 8).
- Do not change the cases, the prompts or the verdict rule after seeing a
  result. Any change is a new protocol version (v0.2), and the v0.1 result is
  kept and reported alongside it.
- A run with a different model or repeat count is a separate run. Its
  pre-registered verdict is INCONCLUSIVE when it is off-protocol.
