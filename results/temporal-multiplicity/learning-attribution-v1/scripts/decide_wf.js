export const meta = {
  name: 'tmk-learning-decisions',
  description: 'Real-model developmental decisions: multiplicity (ablation results) vs equal-call reflective baseline',
  phases: [{ title: 'Decide' }],
}
const DECISION = {
  type: 'object',
  properties: {
    attribution: { type: 'array', items: { type: 'object', properties: {
      module: { type: 'string' }, effect: { type: 'string', enum: ['essential', 'helpful', 'no_effect', 'harmful'] } },
      required: ['module', 'effect'] } },
    gaps: { type: 'string' },
    ranking: { type: 'array', items: { type: 'string' } },
    choice: { type: 'string' },
    rationale: { type: 'string' },
  },
  required: ['attribution', 'gaps', 'ranking', 'choice', 'rationale'],
}
const SUFFIX = '\n\nTWO INDEPENDENT ANALYSES YOU WROTE EARLIER ABOUT THIS SAME SITUATION:\n'
const END = '\n\nWeigh them critically and give your final answers.'
// args: {jobs: [{key, episode, repeat, multi, base}]}  (multi/base = full decision prompts)
const out = await parallel(args.jobs.map(j => async () => {
  const opts = (label) => ({ label, phase: 'Decide', agentType: 'web-fetch', schema: DECISION })
  const multi = agent(j.multi, opts(`multi:${j.key}`))
  const refl = await parallel([0, 1].map(i => () => agent(j.base + '\n\nAnalyse this independently.', opts(`reflect${i}:${j.key}`))))
  const analyses = refl.filter(Boolean).map((r, i) => `Analysis ${i + 1}: ` + JSON.stringify(r)).join('\n')
  const base = await agent(j.base + SUFFIX + analyses + END, opts(`synth:${j.key}`))
  return { key: j.key, episode: j.episode, repeat: j.repeat, multiplicity: await multi, baseline: base, reflections: refl }
}))
return out.filter(Boolean)
