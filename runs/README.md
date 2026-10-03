# runs/

Generated experiment outputs, one directory per run (`runs/<run_id>/`). Not a
source of truth and not committed (see `.gitignore`).

The harness never overwrites or deletes a run directory: a repeated run with the
same configuration gets a `__2`, `__3`, ... suffix, and replays are written to
`<run_id>__replay`. Failed runs keep their partial `trace.jsonl`,
`events.jsonl`, `actions.jsonl` and a `metadata.json` with `status: failed`.

See `docs/milestone-1-design.md` §8 for the file formats.
