export const meta = {
  name: 'tmk-learning-v2-decisions',
  description: 'v2 decisions: multiplicity (1 call + 6 ablation executions) vs baseline (6 reflections + synthesis), WebFetch-only subagents',
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
    forget: { type: 'string' },
    rationale: { type: 'string' },
  },
  required: ['attribution', 'gaps', 'ranking', 'choice', 'forget', 'rationale'],
}
const N_REFLECT = 6
const SUFFIX = `\n\n${N_REFLECT} INDEPENDENT ANALYSES YOU WROTE EARLIER ABOUT THIS SAME SITUATION:\n`
const END = '\n\nWeigh them critically and give your final answers.'
// args: {E: [{ep, P, X, Y, Q, nm, nb}], R}: multiplicity prompt = P+X+Q, baseline prompt = P+Y+Q (Y = 'cannot run evaluations')
const jobs = []
for (const e of args.E) {
  const multi = e.P + e.X + e.Q, base = e.P + e.Y + e.Q
  if (multi.length !== e.nm || base.length !== e.nb) throw new Error(`prompt length mismatch for ${e.ep}`)
  for (let r = 0; r < args.R; r++) jobs.push({ key: `${e.ep}#${r}`, episode: e.ep, repeat: r, multi, base })
}
log(`${jobs.length} decision jobs, ${jobs.length * (N_REFLECT + 2)} calls`)
const out = await parallel(jobs.map(j => async () => {
  const opts = (label) => ({ label, phase: 'Decide', agentType: 'web-fetch', schema: DECISION })
  const multi = agent(j.multi, opts(`multi:${j.key}`))
  const refl = await parallel(Array.from({ length: N_REFLECT }, (_, i) => () =>
    agent(j.base + `\n\nAnalyse this independently. (analysis ${i + 1})`, opts(`reflect${i}:${j.key}`))))
  const analyses = refl.filter(Boolean).map((r, i) => `Analysis ${i + 1}: ` + JSON.stringify(r)).join('\n')
  const base = await agent(j.base + SUFFIX + analyses + END, opts(`synth:${j.key}`))
  return { key: j.key, episode: j.episode, repeat: j.repeat, multiplicity: await multi, baseline: base, reflections: refl }
}))
return out.filter(Boolean)
