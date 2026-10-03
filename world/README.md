# World

This directory contains the evolving software world.

- `seed_repo/`: initial application state ("tasklane", see its README). Every
  agent gets a private copy as its workspace.
- `events/<scenario_id>/`: chronological externally applied events
  (`events.jsonl`, `tab.event/1`) and the payload files they write.
- `ground_truth/<scenario_id>/`: evaluator-only labels, hidden remediation
  tests, reference remediations, the scenario canary, and the scenario's
  generator script. Contestants must never receive access to this directory
  through their tools or prompts; only `src/evaluation/ground_truth.py` reads
  it, and the harness tools and guard refuse any path into it.

The world is deterministic and resettable between contestant runs: a
scenario's manifest pins the content hash of the seed, the events and the
ground truth, plus the workspace tree hash after every event.
