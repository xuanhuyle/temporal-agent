# Imagine-then-Plan (ITP): primary-source notes

Paper: "Imagine-then-Plan: Agent Learning from Adaptive Lookahead with World Models", arXiv:2601.08955 (v1 2026-01-13 per HF metadata; v3 announced as "replace-cross" around 2026-09-04/05 per arXiv RSS mirrors).
Authors: Youwei Liu, Jian Wang (corresponding, marked with a dagger), Hanlin Wang, Beichen Guo, Wenjie Li. Wenjie Li's homepage link is www4.comp.polyu.edu.hk, so the group is probably at PolyU. That affiliation is an inference from README links; the paper header was not seen.
Analyst date: 2026-10-03.

## 0. Sources and how they were obtained

| # | Source | How obtained | Trust |
|---|--------|--------------|-------|
| S1 | https://github.com/loyiv/ITP (HEAD `d1b55ed5950901c3a0816e8a56e96fc70aab50da`, 2026-09-29) | Repo found with the GitHub MCP `search_code` for `"Imagine-then-Plan"`. Cloned with `git clone` into `scratchpad/lit/repos/loyiv_ITP`. | **Verbatim code. This is the official repo.** README author list links loyiv.github.io (Youwei Liu) and iwangjian.github.io (Jian Wang). Commits are by `loyiv` and `iwangjian`. The arXiv abstract (S3) says "Our code and data will be publicly available at https://github.com/loyiv/ITP". ACKNOWLEDGEMENTS.md calls it a "release-oriented, reading-friendly packaging". It is repackaged code, not necessarily the exact experiment code (see §8). |
| S2 | `figures/main_table.png` and `figures/workflow.png` in S1 | Viewed as images with the Read tool | Images of the paper's Table 1 and the method figure. I transcribed the numbers by hand from the image. |
| S3 | arXiv abstract (v3) | Copied verbatim in two independent arXiv-RSS mirrors on GitHub, fetched via raw.githubusercontent.com: `tsingqingyun/paper-daily-robotics/main/daily/2026-09-06/items/Imagine-then-Plan ... .md` and `rxmna8502/vybe-intelligence-vault/main/ai/agents/arxiv-2601-08955.md`. The same text minus the last sentence appears in the HF-papers JSON mirror `R1M1N/research_paper_explainer/main/zenith_output/papers/hf_2601.08955_Imagine-then-Plan__Agent_Learn.json`. | Near-primary. These are verbatim RSS/API copies of the arXiv abstract. |
| S4 | `memgrafter/research-digests/main/ml_research_analysis_2026/2601.08955_...md` | raw.githubusercontent.com | **LLM-generated secondary digest.** Low trust. Used only where code or figures corroborate it. |
| S5 | arxiv.org HTML/PDF | **NOT accessed.** arxiv.org is blocked for curl/WebFetch, and this session's WebSearch budget (200/200) was exhausted on the first call, so no search extracts of the paper body exist. | none |

Consequence: **nothing from the paper body (method equations, ablations, analysis, limitations section) was read first-hand.** Mechanism claims below come from code (S1), the figures (S2) and the abstract (S3).

## 1. Abstract (S3, verbatim from the arXiv RSS mirror)

> arXiv:2601.08955v3 Announce Type: replace-cross Abstract: Recent advances in world models have shown promise for modeling future dynamics of environmental states, enabling agents to reason and act without accessing real environments. Current methods mainly perform single-step or fixed-horizon rollouts, leaving their potential for complex task planning under-exploited. We propose Imagine-then-Plan (\texttt{ITP}), a unified framework for agent learning via lookahead imagination, where an agent's policy model interacts with the learned world model, yielding multi-step ``imagined'' trajectories. Since the imagination horizon may vary by tasks and stages, we introduce a novel adaptive lookahead mechanism by trading off the ultimate goal and task progress. The resulting imagined trajectories provide rich signals about future consequences, such as achieved progress and potential conflicts, which are fused with current observations, formulating a partially \textit{observable} and \textit{imaginable} Markov decision process to guide policy learning. We instantiate \texttt{ITP} with both training-free and reinforcement-trained variants. Extensive experiments across representative agent benchmarks demonstrate that \texttt{ITP} significantly outperforms competitive baselines. Further analyses validate that our adaptive lookahead largely enhances agents' reasoning capability, providing valuable insights into addressing broader, complex tasks. Our code and data will be publicly available at https://github.com/loyiv/ITP.

## 2. README / docs claims (S1, verbatim)

README.md:16
> **Imagine-then-Plan** (**ITP**) addresses this by first using a learned world model to run an adaptive *K*-step imagination rollout, then selecting the action based on both the current state and the predicted future trajectory. This formulates the policy reasoning process as a Partially Observable and Imaginable Markov Decision Process (**POIMDP**).

README.md:59-71
> 1) **Adaptive horizon selection**: decide how many steps to look ahead (*K*) based on the task and current situation.
> 2) **World-model imagination**: roll out *K* steps to obtain a foresight trajectory.
> 3) **Reflect-then-act**: reflect on the foresight (progress, risks, constraints) and then output the real action.
> ...ITP-R learns *when* and *how long* to imagine by adding a lightweight **K-head predictor** on top of the backbone LLM ...
> 1) **Pseudo-labeling horizons**: derive training targets for *K* by selecting the most helpful lookahead depth under a cost trade-off.
> 2) **Warm-up training**: jointly train the action policy (imitation) and the *K*-head predictor.
> 3) **Online A2C optimization**: optimize the action policy + *K*-head predictor + value head online with actor–critic training while the world model is frozen.

docs/poimdp.md:9-14
> - **Observable stream**: task instruction + interaction history (the "present").
> - **Imaginable stream**: \(K\)-step foresight generated by the world model (the "future").
> The key ITP_I orchestration is implemented as: `select K -> imagine -> reflect_and_act`

docs/paper_to_code.md maps paper §3.1 to world-model training, §3.2 to the imagination interface/POIMDP, §3.3 to ITP_I, §3.3.2 to ITP_R and App. B.1 to the prompts.

## 3. The learned world model (code)

**What it predicts.** It predicts the textual next state given (state, action). It is one step and action-conditioned.

world_model/base_tuning/src/fastchat/data_utils.py:28-33 (the FastChat path that docs/training_fastchat.md says was "used in our experiments"):
```python
def _build_world_model_prompt(state_text: str, action_text: str) -> str:
    user = (
        "STATE:\n" + str(state_text) + "\n\n"
        + "ACTION:\n" + str(action_text) + "\n\n"
        + "Please write the NEXT STATE (observation, inventory, brief outcome)."
```
data_utils.py:57-67: target = `next_state` + `<|eot_id|>`. Lines 96-111 mask the prompt tokens, so loss falls on target tokens only. The standalone `world_model/training/train_wm.py:20-36,67-138` has the same scheme with LoRA r=8, alpha=16 (`train_wm.py:181-188`).

**Training data.** The data is (state, action, next_state) JSONL converted from expert SFT conversations.
- `world_model/data_processing/convert_alfworld_sft_to_expert_jsonl.py:59-82`: takes (human turn, gpt turn, human turn) triples from `alfworld_sft.json` and makes them (state, action, next_state).
- `world_model/data_processing/convert_sciworld_sft_to_wm.py:58-79`: state = `Mission/Observation/History`, and target = the same format with the new observation and extended history.
- The figure (S2, workflow.png, "World Model Training" panel) shows WM training on D_exp **and** D_roll, where D_roll is rollouts of the base policy π_θ0. **No code that generates D_roll was found.** `train_wm.py:56` only carries a `traj_type` field that defaults to `"expert"`.

**How it is used at inference.** There are two different usages.
- ITP-I (itp/world_model.py:51-71, eval/foresight_eval/models.py:335-356). It makes **one** greedy generation (`do_sample=False`) with a prompt that is *different* from the training format. No action is given, and the WM is asked for a K-step plan:
  prompts/imagine.txt:2-8
  > You are a world model for the {env_name} environment. Given an action/observation history, imagine the next few steps, describing likely observations and key objects.
  > ...Predict the next {k} step(s). Return a concise plan inside <foresight>...</foresight> with numbered steps.
  If K<=0, it returns `"<foresight>K = 0, no look-ahead is requested.</foresight>"` (world_model.py:53-55).
  Observation: the WM was trained on (STATE, ACTION) → NEXT STATE, but the ITP-I prompt is history → K-step plan. So at inference time the WM must imagine the actions too. The paper figure for ITP-I instead draws π_θ and the WM alternating (â_t, ŝ_t, …, â_{t+K-1}, ŝ_{t+K}). **The figure and the released ITP-I code differ.**
- ITP-R (itp/training/train_adaptive_k.py:929-963, `imagine_obs_k`) alternates properly. The policy greedily proposes `a_hat` from a K=0 prompt, the WM predicts the next state, and this repeats k times. **Only the final observation** is returned:
```python
    sim_state = state_text
    for _ in range(k):
        obs0 = extract_observation(sim_state)
        prompt0 = build_prompt_for_action(sim_state, 0, obs0)
        a_hat = generate_action_text(... do_sample=False, temperature=1.0, top_p=1.0,)
        ...
        pred = wm.predict_next_states_batch([sim_state], [a_hat])[0]
        ...
        sim_state = pred
    return extract_observation(sim_state)
```
  The WM is frozen (`WorldModelWrapper.__init__`, train_adaptive_k.py:299-301 sets `requires_grad = False`) and decodes greedily (329-336). Its ITP-R prompt ("You are a world model for ALFWorld.\nGiven the current state and an action, predict the next state in the same format.\n<STATE>…", 303-313) also differs from the FastChat training template.

## 4. Adaptive lookahead: how K is chosen

**ITP-I** (training-free). The policy LLM is prompted to emit one integer. itp/policy.py:48-69:
```python
        gen = self.llm.generate_chat(... max_new_tokens=self.decision_tokens, temperature=0.8, do_sample=True, stop_strings=["\n"],)
        raw = (gen.text or "").strip()
        try:
            k = int(raw.split()[0])
        except Exception:
            k = min(max_k, 1 if max_k >= 1 else 0)
        k = int(torch.clamp(torch.tensor(k), 0, max_k).item())
```
prompts/decide_k.txt:2-3:
> You are a planning assistant. Your job is to decide how many steps of look-ahead are needed right now.
> Given a task instruction and the interaction history, output a single integer K in the range [0, {kmax}].

The ScienceWorld runner forces K≥1 (eval/foresight_eval/runner_sciworld.py:109-110 `if k == 0 and self.max_k >= 1: k = 1`, plus `--min_k` default 1), so K=0 never occurs there. The ALFWorld runner has `--fixed_k` to bypass decide_k (runner.py:220-226, 673). The README eval uses `--max_k 5` for ALFWorld (README:235) and `--max_k 3` for ScienceWorld (README:264).
No explicit "goal vs progress" computation exists. The abstract's "trading off the ultimate goal and task progress" is delegated to the LLM's judgment in ITP-I.

**ITP-R** (learned). There is a linear K-head over the hidden state at a special `<CTRL>` token, plus a value head (train_adaptive_k.py:219-225):
```python
        self.k_head = nn.Linear(hidden_size, kmax + 1)
        self.v_head = nn.Linear(hidden_size, 1)
```
- Stage I, pseudo-labels (`stage_label`, 565-701). Step 1 (622-629): for each expert step, the WM predicts the next state from the **expert** state and **expert** action. Step 2 (631-641) is the important detail: obs_list[k] for step t is the WM's one-step prediction made from the ground-truth expert state at t+k-1. That makes it a teacher-forced "rollout", not an autoregressive one. Step 3 (668-686) scores each k by the policy's log-likelihood of the expert action given (state, K, Obs@K), minus a cost:
```python
                val = float(scores[t, k].item()) - args.lambda_k * float(k)
                if val > best_val:
                    best_val = val
                    best_k = k
```
  The label therefore uses hindsight from the expert's future trajectory.
- Stage II, warm-up SFT (703-852). The loss is `lm_loss + beta_k * k_loss` (798-803), where k_loss is CE on the pseudo-labels.
- Stage III, online A2C (1113-1414). K is *sampled* from the K-head (1231-1233). The reward is (1302-1306):
```python
                r = float(r_env)
                if won:
                    r += float(args.success_bonus)
                r -= float(args.lambda_k) * float(k)
                r -= float(args.step_cost)
```
  A TD advantage uses the value head on the **real** next state (1331-1336). Losses (1349-1355) are action policy-gradient + K policy-gradient + value MSE + K-entropy.
- **No ITP-R inference/evaluation script is in the repo.** A grep for `k_head|adaptive_heads|ITP_R` outside train_adaptive_k.py found nothing. How K is picked at ITP-R test time (argmax or sample) is therefore unclear.

## 5. How imagined trajectories influence the action

The mechanism is **prompt injection only.** No candidate selection, no value estimate of imagined states, no scoring of trajectories at decision time.
- ITP-I: itp/orchestrator.py:33-40
```python
        k, k_raw = self.policy.decide_k(task=task, history=history, max_k=self.max_k)
        foresight, foresight_raw = self.world_model.imagine(history=history, k=k)
        reflection, thought, action, policy_raw = self.policy.reflect_and_act(
            task=task, history=history, foresight=foresight, admissible_commands=admissible_actions,)
```
  prompts/reflect_and_act.txt:2-3,17
  > You are an agent that first imagines and then acts. At each step, you will be given the task instruction, the current state, and a K-step foresight trajectory imagined by a world model.
  > Use the foresight to reflect on progress and bottlenecks, then decide the next admissible action.
  > K-step foresight trajectory from the world model: {foresight}
- ITP-R: train_adaptive_k.py:55-68. The action prompt carries only K and the final imagined observation:
```python
        "<CTRL>\n"
        "<FORESIGHT>\n"
        f"K={k}\n"
        f"Obs@K: {obs_k}\n"
        "</FORESIGHT>\n"
        "Action:"
```
- **Number of imagined trajectories per step: one.** It is a single greedy generation in both variants. In ITP-R labeling, the only multiplicity is the k+1 horizon prefixes of one teacher-forced trajectory, scored by expert-action likelihood (§4).
- The value head is an A2C critic on real states only.
- The RAP baseline in the repo (eval/foresight_eval/rap.py:224-231, 287-323) does score imagined rollouts with MCTS/UCT and rewards (action logp + self-eval + goal overlap). That is the **baseline**, not ITP.

## 6. Are imagined futures kept? Compared with reality? Backward reasoning?

- **Kept only as evaluation logs.** ALFWorld runner, per-step record (eval/foresight_eval/runner.py:245-259):
```python
        record = {
            "episode_id": episode_id, "t": t, "k": k, "k_raw_output": k_raw,
            "foresight_text": foresight_text, "wm_raw_output": wm_raw,
            "reflection": reflection, "thought": thought, "action": action,
            "policy_raw_output": policy_raw, "obs_next": obs_next, "done": done, "info": info,
        }
```
  This is written to `{idx}.json` as `payload["foresight_steps"]` (runner.py:828-832). The ScienceWorld runner does the same at 317-331 and 350-352, and itp_i_driver.py:30-40 keeps `foresight` in its `traj`.
- **Not kept in the agent's context.** The history update excludes the foresight (runner.py:262-271). With `use_history=1` the history appends `<Thought_t>`, `<Action_t>` and `<Obs_t>` but not the foresight. With the default `use_history=0` (runner.py:675; README eval uses `--use_history 0`), the agent and WM see **only the current observation + inferred inventory** (`_build_state_text`, runner.py:45-48, 356-370). ScienceWorld: the foresight is appended to a *copy* of the messages (runner_sciworld.py:292-303). Only `policy_raw` and the observation persist (333-334), and the WM input is `history_text = obs_text` (288). ITP-R: `obs_k` is not stored at all.
- **Never compared with what actually happened.** `foresight_text` and `obs_next` sit side by side in the log, but no code compares them. A grep for accuracy/calibrat/similarity/compare/hallucin found nothing. The WM is frozen during ITP-R. WM supervised training on real transitions is offline model fitting, not the agent comparing its own past forecasts.
- **No backward reasoning from goal states.** No goal regression, subgoal derivation or precondition extraction exists in ITP code. The only goal-structured logic is an **evaluation-harness heuristic**: runner.py:94-121 parses the task type, object and receptacle from the ALFWorld *gamefile path* (`_parse_goal_from_gamefile`), and `_validate_action_in_runner` (157-190) **overrides the policy's action** in pick-two tasks using a hand-coded `Pick2Progress` tracker (123-155). This is privileged environment metadata steering actions inside the ITP (and RAP) evaluation loop. The paper's reported numbers may or may not have used it (unverified).

## 7. Benchmarks and numbers (S2, Table 1 image, transcribed)

Benchmarks: ALFWorld (PICK/CLEAN/HEAT/COOL/LOOK/PICK2/Overall), ScienceWorld (Seen/Unseen) and WebShop (Total). Metric: "task success rates (%)". Backbones: Qwen2.5-7B, Qwen3-8B and Llama-3.1-8B-Instruct. Baselines: prompting (CoT, ReAct, RAP) and training (SFT, WKM, IWM).

| Backbone | Method | ALFWorld Overall | SciWorld Seen | SciWorld Unseen | WebShop |
|---|---|---|---|---|---|
| Qwen2.5-7B | ReAct | 17.14 | 8.24 | 9.93 | 15.28 |
| Qwen2.5-7B | RAP | 27.86 | 10.30 | 16.55 | 11.28 |
| Qwen2.5-7B | **ITP_I** | **35.71** | 16.49 | 17.88 | 20.10 |
| Qwen2.5-7B | SFT | 67.86 | 55.67 | 49.00 | 51.60 |
| Qwen2.5-7B | WKM | 76.43 | 54.12 | 56.29 | 58.80 |
| Qwen2.5-7B | IWM | 82.80 | 60.82 | 57.61 | 56.20 |
| Qwen2.5-7B | **ITP_R** | **85.07** | 62.58 | 58.94 | 60.20 |
| Qwen3-8B | ReAct | 19.29 | 9.79 | 8.61 | 18.62 |
| Qwen3-8B | RAP | 28.57 | 15.46 | 27.14 | 12.40 |
| Qwen3-8B | **ITP_I** | **41.43** | 20.61 | 19.86 | 25.25 |
| Qwen3-8B | SFT | 70.71 | 56.70 | 49.67 | 52.30 |
| Qwen3-8B | WKM | 79.29 | 60.31 | 47.68 | 61.15 |
| Qwen3-8B | IWM | 82.14 | 59.27 | 54.30 | 57.30 |
| Qwen3-8B | **ITP_R** | **88.57** | 61.85 | 56.95 | 68.10 |
| Llama-3.1-8B | ReAct | 21.43 | 9.27 | 13.24 | 19.32 |
| Llama-3.1-8B | RAP | 22.86 | 11.34 | 17.21 | 16.05 |
| Llama-3.1-8B | **ITP_I** | **37.86** | 19.58 | 19.20 | 24.30 |
| Llama-3.1-8B | SFT | 79.28 | 57.21 | 50.33 | 47.30 |
| Llama-3.1-8B | WKM | 77.86 | 61.34 | 54.96 | 65.58 |
| Llama-3.1-8B | IWM | 85.90 | 57.56 | 56.29 | 58.60 |
| Llama-3.1-8B | **ITP_R** | **87.14** | 63.91 | 57.61 | 67.50 |

Observations from my own arithmetic on the transcribed table (scratchpad check):
- ITP_I Qwen2.5 per-type values imply integer counts 23/35, 7/27, 4/16, 6/25, 4/13 and 6/24. These sum to 50/140 = 35.71%, so the ALFWorld split has 140 games. The README eval uses `--split seen`, which maps to `valid_seen` (runner.py:50-55). Most ITP/ReAct/RAP rows are internally consistent with these denominators.
- **Inconsistency:** in the Qwen2.5 ITP_R row, COOL=53.84 is only possible with /13 and LOOK=76.00 only with /25, so these two columns look swapped. Even after swapping, 119/140 = 85.00 ≠ the reported 85.07.
- IWM rows (e.g. 90.60, 85.20, 88.20) do not fit these denominators, so they are probably copied from another source or setup. Unverified.
- ITP_R is the best entry in every ALFWorld-Overall, SciWorld and WebShop column. Its margin over the best trained baseline is small:
  - Qwen2.5: +2.27 / +1.76 / +1.33 / +1.40
  - Qwen3: +6.43 / +1.54 / +2.65 / +6.95
  - Llama: +1.24 / +2.57 / +1.32 / +1.92
  (columns are ALF-Overall / Seen / Unseen / WebShop)
- ITP_I beats RAP on ALFWorld Overall by +7.85 / +12.86 / +15.00 points. On Qwen3 SciWorld Unseen, RAP (27.14) beats ITP_I (19.86).
- The table shows no variance and no seeds.
- **WebShop:** the repo has `eval/eval_agent/envs/webshop_env.py` but no ITP WebShop runner.
- **Possible train/test overlap (README-level evidence only):** the README Stage-III online A2C command uses `--env_split "valid_seen"` (README:182), and `--env_split` defaults to `valid_seen` (train_adaptive_k.py:1484). The README ALFWorld evaluation also uses `--split seen` → `valid_seen`. If the paper followed the README, ITP-R was RL-tuned online on its ALFWorld evaluation split. I could not check what the paper actually did.

## 8. Code-quality observations that bear on "verified in code"

- **The released ALFWorld ITP-I eval cannot parse actions.** eval/foresight_eval/models.py:288 and 295 use double-escaped regexes inside raw strings (`rf"(?is)<{tag}[^>]*>\\s*(.*?)\\s*</{tag}>"`, `r"(?im)^\\s*Action\\s*:\\s*(.+)$"`). I executed these exact source lines (scratchpad/regex_check.py): they return `None` on well-formed `<Action> go to desk 1 </Action>` and `Action: go to desk 1` outputs. The action becomes "", and `validate_action` falls back to `admissible_commands[0]` (models.py:57-75). The library version in itp/policy.py:124 uses single escapes and works. So the released runner probably is not the exact code behind Table 1.
- `itp/prompting.py:7` imports `from utils.io import read_text`, but the top-level `utils/` directory was deleted (commit a1d2cf5). The file now lives at `itp/utils/io.py`.
- There is no setup.py/pyproject.toml, although the README says `pip install -e .`.
- `eval/foresight_eval/runner_sciworld.py` holds two concatenated copies of the module (classes at lines 42 and 450, `__main__` at 369 and 777).
- `scripts/README.md`: "This directory intentionally does **not** provide 'one-click' commands in this release."

## 9. Capability ratings (summary of evidence)

| # | capability | rating | evidence |
|---|---|---|---|
| 1 | immutable_historical_observations | partial | Per-episode eval logs only: `state.history` is appended per step and dumped once per task JSON (runner.py:345-395, 828-832). Missing: this is not an agent-facing store; there are no immutability guarantees (`--override` rewrites, runner.py:646,692); and the default agent context is the current observation only. |
| 2 | historical_world_state | no | No reconstruction of past environment state; the env is only reset per task. |
| 3 | historical_epistemic_state | no | Nothing reconstructs what the agent believed at t. |
| 4 | historical_policy_objective_state | no | The task is fixed per episode. Per-step k and raw outputs are logged, but no policy, objective or version history exists. |
| 5 | execution_checkpoints | no | Only model-weight checkpoints (train_adaptive_k.py:835-849,1406-1407) and task-level resume that skips finished task JSONs (runner.py:738-752). No restorable agent runtime state. |
| 6 | replay | no | None. |
| 7 | fork_from_historical_state | no | None. |
| 8 | counterfactual_action_branches | partial | Imagines a K-step future before committing (orchestrator.py:33-40; train_adaptive_k.py:929-963). Missing: only one default continuation per step; alternative actions are never branched or compared (RAP baseline does this; ITP does not). |
| 9 | branch_provenance | no | None. |
| 10 | explicit_current_belief_state | no | Reflection/Thought are free text per step. `Pick2Progress` (runner.py:123-155) is a hand-coded harness tracker for one task type, not a belief state. |
| 11 | uncertainty_representation | no | Greedy WM decoding with no confidence. The K-head categorical is over horizons, not world uncertainty. |
| 12 | future_state_rollout | yes | Learned text WM (state, action) → next_state (data_utils.py:28-41,57-117). K-step policy↔WM rollout (train_adaptive_k.py:929-963). ITP-I K-step foresight (world_model.py:51-71). |
| 13 | multiple_prospective_branches | no | One imagined trajectory per step. Horizon candidates in labeling are prefixes of one teacher-forced trajectory (train_adaptive_k.py:631-686). |
| 14 | probability_over_futures | no | No likelihood is assigned to imagined futures. The label score is log p(expert action given imagined obs), not p(future). |
| 15 | backward_requirements | no | No goal regression; the abstract's "goal vs progress" is only about horizon length. |
| 16 | intervention_aware_forecasting | partial | Imagined states are conditioned on the agent's own (imagined) actions: a_hat from the policy, then WM.predict (train_adaptive_k.py:947-959). Missing: no passive vs policy-conditioned vs reflexive distinction, and no comparison of futures with and without intervention. |
| 17 | prevented_futures_preserved | no | Foresight is logged (runner.py:245-259) but never labelled, revisited or treated as prevented. |
| 18 | predicted_vs_realized | no | `foresight_text` and `obs_next` are logged side by side and never compared. The WM is frozen in ITP-R (train_adaptive_k.py:299-301). |
| 19 | cross_time_state_querying | no | None. |
| 20 | unified_temporal_abstraction | partial | POIMDP couples the "observable present" and the "imaginable future" (docs/poimdp.md:9-10; README:16). Missing: historical states, counterfactual pasts, branches and any addressable time axis. |

## 10. Could not verify

- The paper body: §3 equations (POIMDP definition, policy π_θ(a|s_t, τ̂_t), WM loss), ablations (fixed K vs adaptive, K distribution, cost analysis), WM fidelity metrics, the limitations section, compute and token overheads. Reason: arxiv.org blocked and the WebSearch budget exhausted. S4 (LLM digest) claims limitations about multimodal settings, inference overhead and compounding WM error, but these are unverified.
- Whether the paper's WM training used D_roll (the figure says yes; no code generates it).
- How ITP-R picks K at test time, and how ITP-R was evaluated (no script).
- How the WebShop results were produced (no runner).
- Which policy checkpoint ITP-I used (raw backbone or SFT). README uses a placeholder `path/to/policy_checkpoint`.
- Whether the Table 1 numbers came from the released code (the action-parsing bug suggests not), whether the pick-two gamefile heuristic was active, and whether ITP-R online A2C used valid_seen (README suggests it did).
- Whether the paper itself discusses storing foresight, or comparing foresight to outcomes (e.g. as an analysis). The code does neither for learning or decisions.
- Exact affiliation (PolyU inferred from a homepage link).
