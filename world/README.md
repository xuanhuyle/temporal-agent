# World

This directory contains the evolving software world.

- `seed_repo/`: initial application state.
- `events/`: chronological externally applied events.
- `ground_truth/`: evaluator-only labels. Contestants must never receive access to this directory through their tools or prompts.

The world should be deterministic and resettable between contestant runs.
