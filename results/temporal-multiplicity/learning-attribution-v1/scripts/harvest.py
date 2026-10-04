"""Merge executor results from every v2 workflow journal into {job_id: {answers}} (first result per job wins)."""
import json, sys
from pathlib import Path
W = Path('/root/.claude/projects/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/subagents/workflows')
RUNS = ['wf_16cebc6d-c83', 'wf_58ba3ad4-888', 'wf_a9954017-664', 'wf_73705db5-258', 'wf_1732d8ba-68e']
out, src, nulls = {}, {}, []
for run in RUNS:
    j = W / run / 'journal.jsonl'
    if not j.exists():
        continue
    lab = {}
    for line in j.open():
        r = json.loads(line)
        if r['type'] == 'started':
            lab[r['key']] = r['label'].removeprefix('exec:')
        elif r['type'] == 'result':
            k = lab[r['key']]
            ans = (r.get('result') or {}).get('answers')
            if ans is None:
                nulls.append((run, k))
            if k not in out:
                out[k] = {'answers': ans}
                src[k] = run
json.dump(out, open(sys.argv[1], 'w'), indent=1)
json.dump(src, open(sys.argv[1].replace('.json', '_source_runs.json'), 'w'), indent=1)
print(len(out), 'results;', len(nulls), 'null results', nulls[:5])
