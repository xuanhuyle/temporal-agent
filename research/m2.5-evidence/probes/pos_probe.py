"""Probe PoS BeliefManager: is the committed belief overwritten, and what history survives?"""
import json, sys
sys.path.insert(0, sys.argv[1])
from belief.manager import BeliefManager

class Rec:
    def __init__(self): self.events = []
    def log(self, event, **d): self.events.append({"event": event, **d})

initial = {
  "goal_specification": "Mug 1 must be clean.",
  "entities": [{"entity_id": "e1", "entity_type": "mug", "name": "mug 1"}],
  "states": [{"state_id": "s1", "entity_id": "e1", "description": "Mug 1 is dirty.",
              "source_type": "observed", "probability": 1.0}],
  "relations": [],
  "epistemic_gaps": [{"target": "Is the sink working", "reason": "unknown"}],
  "achievement_gaps": [{"target": "Mug 1 must be clean", "reason": "Mug 1 is dirty."}],
  "frontier": {"gap_type": "achievement", "target": "Mug 1 must be clean"},
}
delta_clean = {
  "remove_state_ids": [], "remove_relation_ids": [], "upsert_entities": [],
  "upsert_states": [{"state_id": "s1", "entity_id": "e1", "description": "Mug 1 is clean.",
                     "source_type": "observed", "probability": 1.0}],
  "upsert_relations": [], "epistemic_gaps": [], "achievement_gaps": [], "frontier": None,
}
def call(messages):
    c = messages[-1]["content"]
    if "coherent current-world description" in messages[0]["content"]:
        return '{"belief_text": "text"}'
    return json.dumps(initial if "Initial observation:" in c else delta_clean)

cfg = {"context": {"task_mode": "execution", "agent_view": "hybrid", "update_every_steps": 1,
                   "model": {"max_json_retries": 0},
                   "sentinel": {"enabled": False}, "trapping": {"enabled": False},
                   "recovery": {"enabled": False}}}
log = Rec()
m = BeliefManager(cfg, call, log)
st = {"case_id": "c", "task": "Clean mug 1.", "observation": "Mug 1 is dirty.",
      "actions": ["clean"], "done": False, "success": False, "score": 0.0}
m.reset(st)
st2 = dict(st, observation="You clean mug 1.")
m.update({"thought": "", "action": "clean", "observation": "You clean mug 1."}, st2, 0)
ctx = m.get_context(); res = m.get_result()
print("CURRENT s1:", ctx["world"]["states"]["s1"]["description"])
print("CURRENT gaps:", ctx["epistemic_gaps"], ctx["achievement_gaps"])
print("HISTORY steps/status:", [(h["step"], h["status"]) for h in res["belief_update_history"]])
print("HISTORY[0] final s1:", res["belief_update_history"][0]["final_belief"]["world"]["states"]["s1"]["description"])
print("HISTORY[0] final gaps:", res["belief_update_history"][0]["final_belief"]["achievement_gaps"])
print("SNAPSHOT keys:", list(m.belief_snapshots[0].keys()))
print("SNAPSHOT steps:", [s["step"] for s in m.belief_snapshots])
print("State record fields:", list(ctx["world"]["states"]["s1"].keys()))
print("Public methods:", [n for n in dir(m) if not n.startswith("_")])
print("raw_trajectory steps:", [r["step"] for r in res["raw_trajectory"]])
print("result keys:", sorted(res.keys()))
