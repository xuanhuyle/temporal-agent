"""Workflow decision result -> score_decisions input. Keeps reflections for the raw record."""
import json, sys
res = json.load(open(sys.argv[1]))
res = res.get('result', res) if isinstance(res, dict) else res
dec = []
def norm(o):
    if not o:
        return {}
    o = dict(o)
    o['attribution'] = {a['module']: a['effect'] for a in o.get('attribution') or []}
    return o
for r in res:
    for cond in ('multiplicity', 'baseline'):
        dec.append({'episode': r['episode'], 'condition': cond, 'repeat': r['repeat'], 'output': norm(r[cond])})
    for i, refl in enumerate(r.get('reflections') or []):
        dec.append({'episode': r['episode'], 'condition': f'reflection{i}', 'repeat': r['repeat'], 'output': norm(refl)})
json.dump(dec, open(sys.argv[2], 'w'), indent=1)
print(len(dec), 'decision records')
