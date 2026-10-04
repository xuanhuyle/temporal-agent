export const meta = {
  name: 'tmk-learning-v2-evals',
  description: 'Real-model execution of v2 agent states, 3 replicates each (restricted WebFetch-only subagents)',
  phases: [{ title: 'Execute states' }],
}
const SCHEMA = { type: 'object', properties: { answers: { type: 'array', items: { type: 'integer' } } }, required: ['answers'] }
const { H, L, P, J, R } = args
const skip = new Set(args.skip || [])
const tasks = []
for (const j of J) {
  const prompt = H + 'REFERENCE MATERIAL:\n' + j.m.split(' ').map(m => '- ' + L[m]).join('\n') + '\n\nPARCELS:\n' + P[j.pk]
  if (prompt.length !== j.n) throw new Error(`prompt length mismatch for ${j.id}: ${prompt.length} vs ${j.n}`)
  for (let r = 0; r < R; r++) if (!skip.has(`${j.id}|r${r}`)) tasks.push({ id: `${j.id}|r${r}`, prompt })
}
log(`${tasks.length} executions`)
const out = await parallel(tasks.map(t => () =>
  agent(t.prompt, { label: `exec:${t.id}`, phase: 'Execute states', agentType: 'web-fetch', schema: SCHEMA })
    .then(r => ({ id: t.id, answers: r ? r.answers : null }))))
const res = {}
for (const r of out.filter(Boolean)) res[r.id] = { answers: r.answers }
return res
