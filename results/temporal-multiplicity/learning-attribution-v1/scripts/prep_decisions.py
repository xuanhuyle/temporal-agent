"""Dev-only scoring -> v2 decision prompts -> workflow args (2 repeats per episode)."""
import json, subprocess, sys
REPO = '/home/user/temporal-agent'
outputs = sys.argv[1]
jobs = json.load(open('v2_eval_jobs.json'))
json.dump([j for j in jobs if j['split'] == 'dev'], open('v2_dev_jobs.json', 'w'))
run = lambda *a: subprocess.run([sys.executable, '-m', 'multiplicity_experiments.learning_attribution', *a],
                                cwd=REPO, check=True, env={'PYTHONPATH': REPO + '/src', 'PATH': '/usr/bin:/bin'})
here = '/tmp/claude-0/-home-user-temporal-agent/45e7646f-fce6-5edf-8cae-b85e30b6afde/scratchpad/learn/'
run('score-evals', '--jobs', here + 'v2_dev_jobs.json', '--outputs', here + outputs, '--out', here + 'v2_dev_evals.json')
run('plan-decisions', '--design', 'v2', '--evals', here + 'v2_dev_evals.json', '--out', here + 'v2_decision_jobs.json')
dj = json.load(open('v2_decision_jobs.json'))
by = {}
for j in dj:
    by.setdefault(j['episode'], {})[j['condition']] = j['prompt']
args = {'jobs': [{'key': f'{ep}#{r}', 'episode': ep, 'repeat': r, 'multi': p['multiplicity'], 'base': p['baseline']}
                 for ep, p in by.items() for r in (0, 1)]}
json.dump(args, open('v2_decision_args.json', 'w'), separators=(',', ':'))
print(len(args['jobs']), 'decision jobs;', len(json.dumps(args)), 'bytes')
