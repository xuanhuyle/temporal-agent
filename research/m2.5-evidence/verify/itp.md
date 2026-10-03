# Verification of the ITP (Imagine-then-Plan, arXiv:2601.08955) analysis

Verifier date: 2026-10-03.
Repo: existing clone `scratchpad/lit/repos/loyiv_ITP`, HEAD d1b55ed5950901c3a0816e8a56e96fc70aab50da (2026-09-29). I re-checked it myself.

Paper body: still unread.
- WebSearch returned "Web search was not performed: this session has used its web search budget (200 of 200)".
- arxiv.org is blocked.
- The local mirror clones (tree_InMatrix_ai-papers-reader, tree_memgrafter_research-digests) have no ITP file (grep for 2601.08955 / Imagine-then-Plan returned nothing).
- I re-fetched the memgrafter LLM digest (saved as `verify/itp_digest.md`). It is low trust, and I used it for nothing load-bearing.

## Outcome

**No ratings changed.** I independently confirmed all 20 ratings against the code. One weak-evidence item and one possible deflation point are noted below.

## Independent code checks (verbatim)

### itp/orchestrator.py:33-40 (ITP-I step)

The step is one decide_k, then one imagine, then one reflect_and_act. There are no candidates and no selection.

```
k, k_raw = self.policy.decide_k(task=task, history=history, max_k=self.max_k)
foresight, foresight_raw = self.world_model.imagine(history=history, k=k)
reflection, thought, action, policy_raw = self.policy.reflect_and_act(task=task, history=history, foresight=foresight, admissible_commands=admissible_actions,)
```

### itp/world_model.py:51-71 (imagine)

- With K<=0 it returns `"<foresight>K = 0, no look-ahead is requested.</foresight>"`.
- Otherwise it makes a single `generate_chat(..., temperature=0.7, do_sample=False)` call, so decoding is greedy and there is no confidence output.

### prompts/imagine.txt

> Given an action/observation history, imagine the next few steps ... Predict the next {k} step(s). Return a concise plan inside <foresight>...</foresight> with numbered steps.

No action is passed in. In ITP-I the WM imagines the actions itself.

### itp/training/train_adaptive_k.py:929-963 (imagine_obs_k)

- The loop is: policy `a_hat` (do_sample=False), then `wm.predict_next_states_batch([sim_state],[a_hat])`.
- It returns only `extract_observation(sim_state)` of the final step.
- **Confirmed:** one greedy policy-conditioned rollout.

### train_adaptive_k.py:631-641 (stage_label obs_list)

- `idx = t + k - 1; obs_list.append(extract_observation(pred_next_states[idx]))`.
- `pred_next_states[i]` is the WM's prediction from expert state i given expert action i (622-629).
- **Confirmed:** the rollout is teacher-forced on expert future states, so the K labels use hindsight.

### train_adaptive_k.py:668-686 (label score)

`val = scores[t,k] - args.lambda_k * k`; argmax over k. **Confirmed.**

### train_adaptive_k.py:1231-1233 and 1302-1306 (RL)

- K is drawn with `Categorical(logits=k_logits).sample()`.
- `r = r_env (+success_bonus if won) - lambda_k*k - step_cost`.
- **Confirmed.**

### train_adaptive_k.py:299-301

`for p in self.model.parameters(): p.requires_grad = False` (WM frozen). **Confirmed.**

### itp/policy.py decide_k

`temperature=0.8, do_sample=True`, with an exception fallback and `torch.clamp(...,0,max_k)`. **Confirmed.**

### eval/foresight_eval/runner.py:245-271

- The per-step record holds `foresight_text` and `obs_next` side by side.
- The history update with use_history adds only `<Thought_t><Action_t><Obs_t>`.
- Otherwise `updated_history = _build_state_text(obs_text, inv_next)`, i.e. the current obs plus inventory only.
- **Confirmed.**

### runner.py:805-832 (per-task log)

- `env.reset()` runs per idx and finished task ids are skipped.
- After the episode: `json.dump(payload, open(out_path, "w"))`. That is one whole-file write per task at episode end. It is not an append-only store.
- `--override` (help: "Ignore done tasks (overwrite output dir).") and `file_mode = "w" if override`. **Confirmed.**

### eval/foresight_eval/models.py:288,295 (regex bug)

I executed the exact source lines with `raw = "<Action> go to desk 1 </Action>\nAction: go to desk 1"`. Both `re.search` calls return `None`. **Confirmed.**

### README.md:182

`--env_split "valid_seen"`. Also README.md:228 `--split seen`, and runner `_map_split_to_data`: seen → valid_seen. **Confirmed** at README level.

### eval/eval_agent/agents/foresight_local_agent.py:65

`foresight = self.world_model.imagine(history_text, k)`. This is a single foresight, the same as above.

### Table 1 (figures/main_table.png, viewed)

- Spot-check: Qwen2.5 ITP_R row is PICK 94.29, CLEAN 88.89, HEAT 87.50, COOL 53.84, LOOK 76.00, PICK2 91.67, Overall 85.07.
- ITP_I's row has COOL=24.00 (6/25) and LOOK=30.77 (4/13). So COOL has 25 games and LOOK has 13.
- ITP_R's 53.84 ≈ 7/13 and 76.00 = 19/25, which means the two columns are swapped.
- The sum is 33+24+14+19+7+22 = 119, and 119/140 = 85.00 ≠ 85.07.
- **The analyst's inconsistency claim is confirmed.** By contrast, the Llama ITP_R row sums to 122/140 = 87.14, which is consistent.

## Capability-by-capability notes (no rating changed)

1. **immutable_historical_observations: partial (kept, weak).**
   - For: with use_history=1 the agent's in-context history is an append-only Thought/Action/Obs transcript within an episode (runner.py:263-268). The full episode is dumped once per task.
   - Against: this is generic ReAct-transcript logging plus a harness dump. It is not immutable (`open(out_path,"w")`, `--override`). ITP-R training truncates history to the last 6 steps (train_adaptive_k.py:1317-1327). The default mode keeps only the current observation.
   - Borderline between partial and no. I kept partial because within-episode append-only context is real.
2. **historical_world_state: no.** Confirmed.
3. **historical_epistemic_state: no.** Confirmed.
4. **historical_policy_objective_state: no.** Confirmed.
5. **execution_checkpoints: no.** Confirmed. The only "checkpointing" hits are model checkpoints and `gradient_checkpointing`, and a grep for deepcopy/snapshot/restore in itp/ and eval/ found nothing in ITP.
6. **replay: no.** Confirmed.
7. **fork_from_historical_state: no.** Confirmed.
8. **counterfactual_action_branches: partial (kept).**
   - For: it is a simulated, uncommitted lookahead, and the policy may deviate from the imagined path after reflecting.
   - Against: exactly one continuation, and alternatives are never enumerated. RAP (baseline) does MCTS.
9. **branch_provenance: no.** Confirmed.
10. **explicit_current_belief_state: no.** Confirmed. Pick2Progress is harness logic.
11. **uncertainty_representation: no.** Confirmed: greedy WM decoding, and the K categorical is over horizons.
12. **future_state_rollout: yes.** Confirmed.
13. **multiple_prospective_branches: no.** Confirmed.
14. **probability_over_futures: no.** Confirmed.
15. **backward_requirements: no** in code.
    - The paper body is unread, but the abstract's "trading off the ultimate goal and task progress" is realised in code only as the K choice.
16. **intervention_aware_forecasting: partial (kept).**
    - For: the ITP-R rollout is explicitly conditioned on policy actions (a_hat → WM).
    - Against: there is no passive or no-op forecast and no reflexive distinction. Any action-conditioned WM would earn this partial.
17. **prevented_futures_preserved: no.** Confirmed.
18. **predicted_vs_realized: no (kept).**
    - Possible deflation point: the ITP-R A2C critic compares its value prediction V(s) against realised r + γV(s') (TD error, train_adaptive_k.py:1331-1336).
    - That is generic actor-critic learning of returns, not comparison of the agent's stored forecasts of future states with outcomes. The imagined futures are never compared.
19. **cross_time_state_querying: no.** Confirmed.
20. **unified_temporal_abstraction: partial (kept, weak).**
    - docs/poimdp.md: "In this release, the POIMDP concept is expressed as a **software boundary**". The observable stream is the present and the imaginable stream is the future.
    - It spans 2 of the 4 required kinds of state (actual and prospective). It has no history, counterfactual past or addressable time axis.
