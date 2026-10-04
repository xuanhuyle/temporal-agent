// tmk-long-horizon v1: regression investigation + repair (conditions A, B, C). Appended after runtime.js.
// DATA.cases[i] = {id, cond, steps, max_exec, current, failing, archive, checkpoints, stages, truth}
// A: current state + raw archive (model-ranked semantic search + read).  B: A + inspect/diff exact checkpoints.
// C: B + execute a historical checkpoint on the rejected requests (must predict its decisions first).
const STEP = { type: 'object', required: ['reasoning', 'actions'], properties: {
  reasoning: { type: 'string' },
  actions: { type: 'array', items: { type: 'object', required: ['tool'], properties: {
    tool: { type: 'string', enum: ['search', 'read', 'inspect', 'diff', 'execute'] }, query: { type: 'string' },
    ids: { type: 'array', items: { type: 'string' } }, checkpoint: { type: 'string' }, from: { type: 'string' },
    to: { type: 'string' }, predictions: { type: 'array', items: { type: 'object', properties: {
      request_id: { type: 'string' }, currency: { type: 'string' }, approvers: { type: 'array', items: { type: 'string' } },
      carrier: { type: 'string' }, notify: { type: 'array', items: { type: 'string' } }, hold: { type: 'boolean' } } } } } } },
  final: { type: 'object', properties: { lost_after: { type: 'string' }, cause: { type: 'string' }, repair: {
    type: 'object', required: ['source'], properties: { source: { type: 'string', enum: ['archive', 'checkpoint'] },
      id: { type: 'string' }, checkpoint: { type: 'string' }, section: { type: 'string' }, index: { type: 'integer' },
      replace: { type: 'string' } } } } } } }
const RANK = { type: 'object', required: ['ids'], properties: { ids: { type: 'array', items: { type: 'string' } } } }

function archiveText(c) { return c.archive.map((r) => `<<${r.id}>>\n${r.text}`).join('\n\n') }
async function search(c, query, label) {
  const out = await callAgent(NOTOOL + 'You are a semantic search engine over the archive below (messages, purchase ' +
    'requests and the decisions taken on them). Return the ids of the records most relevant to the query, most relevant ' +
    `first, at most 5.\n\nQUERY: ${query}\n\nARCHIVE\n${archiveText(c)}`, RANK, label, 'Retrieval')
  const known = new Set(c.archive.map((r) => r.id))
  return ((out && out.ids) || []).filter((i) => known.has(i)).slice(0, 5)
}
const recText = (c, id) => { const r = c.archive.find((x) => x.id === id); return r ? `<<${id}>>\n${r.text}` : `<<${id}>> (no such record)` }
const cpById = (c, id) => c.checkpoints.find((x) => x.id === id)
function inspectText(cp) {
  return `Checkpoint ${cp.id} (session ${cp.stage}, ${cp.kind})\nPERSISTENT MEMORY\n` + SECTIONS.map(([k, t]) => t + ':\n' +
    ((cp.memory[k] || []).length ? cp.memory[k].map((e, i) => `  [${k}:${i}] ${e}`).join('\n') : '  (none)')).join('\n') +
    `\nWORKING CONTEXT record ids: ${cp.context.map((r) => r.id).join(', ') || '(empty)'}`
}
function diffText(a, b) {
  const ea = new Set(SECTIONS.flatMap(([k]) => (a.memory[k] || []).map((e) => k + ': ' + e)))
  const eb = new Set(SECTIONS.flatMap(([k]) => (b.memory[k] || []).map((e) => k + ': ' + e)))
  const rem = [...ea].filter((e) => !eb.has(e)), add = [...eb].filter((e) => !ea.has(e))
  return `Memory diff ${a.id} -> ${b.id}\nREMOVED:\n${rem.map((e) => '- ' + e).join('\n') || '(none)'}\nADDED:\n` +
    `${add.map((e) => '- ' + e).join('\n') || '(none)'}`
}
const decLine = (d) => !d ? '(no decision)' : `currency ${d.currency}; approvers ${(d.approvers || []).join('+') || '-'}; carrier ` +
  `${d.carrier}; notify ${(d.notify || []).join('+') || '-'}; hold ${d.hold ? 'yes' : 'no'}`

function casePrompt(c, transcript, k) {
  const B = c.cond !== 'A', C = c.cond === 'C'
  const ncomp = c.checkpoints.filter((x) => x.kind === 'post_compaction').length
  const tools = ['- search {"tool":"search","query":"..."}: semantic search over the raw archive; returns the 5 most relevant records (max 2 searches per step)',
    '- read {"tool":"read","ids":[...]}: read archive records by id (max 6 per step)']
  if (B) tools.push('- inspect {"tool":"inspect","checkpoint":"<id>"}: see the exact persistent memory (with entry indexes) and working-context record ids of a checkpoint',
    '- diff {"tool":"diff","from":"<id>","to":"<id>"}: memory entries removed/added between two checkpoints')
  if (C) tools.push(`- execute {"tool":"execute","checkpoint":"<id>","predictions":[...]}: actually run your historical self at that checkpoint on the rejected requests and see its decisions and the reviewer's verdict on each. In "predictions" you must first write the decisions you expect that historical self to make (one per rejected request). At most ${c.max_exec} executions in total, at most 2 per step.`)
  const repair = ['- {"source":"archive","id":"<record id>"}: copy one raw archive record into your persistent memory']
  if (B) repair.push('- {"source":"checkpoint","checkpoint":"<id>","section":"rules|commitments|open_items|notes","index":<n>}: copy one memory entry from a checkpoint into your persistent memory')
  const cps = B ? '\nCHECKPOINTS of your exact state (id: session, kind):\n' + c.checkpoints.map((x) => `${x.id}: session ${x.stage}, ${x.kind}`).join('\n') + '\n' : ''
  return NOTOOL + 'You are the procurement desk agent at Larkspur Robotics. A quality review found a regression in your ' +
    'work: the decisions below were rejected by the reviewer (the reviewer does not say what was wrong). Requests like ' +
    'these used to be handled correctly. Find out what you lost or distorted over time, and repair your current state ' +
    'with ONE minimal restoration so that you handle such requests correctly again. Restoring whole old contexts is not ' +
    'allowed; exactly one item is restored.\n\nYOUR CURRENT STATE\n' + stateText(c.current) +
    '\n\nREJECTED DECISIONS\n' + c.failing.map((f) => `${f.text}\n  your decision: ${decLine(f.current_decision)}  -> REJECTED`).join('\n') +
    `\n\nYOUR HISTORY\nYou worked ${c.stages} weekly sessions. Your working context was compacted ${ncomp} times; after each ` +
    'compaction only your persistent memory was carried forward. The raw archive keeps every message, request and decision ' +
    'you ever saw (record ids like M-012, REQ-0451).\n' + cps + '\nTOOLS (several per step allowed)\n' + tools.join('\n') +
    '\n\nREPAIR OPTIONS (choose exactly one in "final"; optionally add "replace":"<section>:<index>" naming an entry of ' +
    'your CURRENT memory that the restored item supersedes)\n' + repair.join('\n') +
    '\n\nINVESTIGATION SO FAR\n' + (transcript.length ? transcript.join('\n\n') : '(nothing yet)') +
    `\n\nThis is step ${k} of ${c.steps}. Respond with {"reasoning", "actions", "final"}. Give "final" ` +
    '{"lost_after": "<checkpoint id or session number after which the capability was lost>", "cause": "<which state ' +
    'transition / compaction / memory change caused it>", "repair": {...}} as soon as you are confident' +
    (k === c.steps ? '. THIS IS YOUR LAST STEP: you must give "final" now with no further actions.' : ', otherwise leave it out and request actions.')
}

async function runCase(c) {
  const transcript = [], trace = { case: c.id, cond: c.cond, steps: [], executions: [], searches: 0 }
  let execLeft = c.max_exec, final = null
  for (let k = 1; k <= c.steps && !final; k++) {
    const out = await callAgent(casePrompt(c, transcript, k), STEP, `${c.cond}:${c.id}:step${k}`, 'Investigate')
    if (!out) { trace.steps.push({ k, output: null }); continue }
    const results = []
    let nsearch = 0, nexec = 0
    for (const a of (k === c.steps ? [] : out.actions || []).slice(0, 8)) {
      if (a.tool === 'search' && nsearch < 2 && a.query) {
        nsearch++; trace.searches++
        const ids = await search(c, a.query, `${c.cond}:${c.id}:search${k}.${nsearch}`)
        results.push(`search "${a.query}" ->\n` + (ids.map((i) => recText(c, i)).join('\n\n') || '(no results)'))
      } else if (a.tool === 'read') {
        results.push((a.ids || []).slice(0, 6).map((i) => recText(c, i)).join('\n\n'))
      } else if (a.tool === 'inspect' && c.cond !== 'A') {
        const cp = cpById(c, a.checkpoint); results.push(cp ? inspectText(cp) : `inspect ${a.checkpoint}: no such checkpoint`)
      } else if (a.tool === 'diff' && c.cond !== 'A') {
        const x = cpById(c, a.from), y = cpById(c, a.to); results.push(x && y ? diffText(x, y) : 'diff: unknown checkpoint')
      } else if (a.tool === 'execute' && c.cond === 'C' && execLeft > 0 && nexec < 2) {
        const cp = cpById(c, a.checkpoint)
        if (!cp) { results.push(`execute ${a.checkpoint}: no such checkpoint`); continue }
        execLeft--; nexec++
        const run = await callAgent(decidePrompt(cp, c.failing), DECISIONS, `C:${c.id}:exec:${cp.id}`, 'Execute history')
        const dm = byId(run)
        const lines = c.failing.map((f) => `${f.id}: ${decLine(dm[f.id])}  -> ${verdictOf(c, cp, f, dm[f.id])}`)
        trace.executions.push({ checkpoint: cp.id, predictions: a.predictions || [], output: run })
        results.push(`execute ${cp.id} (your predictions were recorded) ->\n` + lines.join('\n'))
      } else results.push(`${a.tool}: not available`)
    }
    trace.steps.push({ k, output: out, results })
    transcript.push(`STEP ${k}\nyour reasoning: ${out.reasoning}\nyour actions: ${JSON.stringify(out.actions || [])}\nresults:\n` +
      (results.join('\n---\n') || '(none)'))
    if (out.final && out.final.repair) final = out.final
  }
  trace.final = final
  return trace
}
// verdicts are precomputed by the evaluator for every (checkpoint, request, decision-signature) the subject could see:
// the reviewer accepts a decision iff every field matches the ground truth at that checkpoint's own time.
function verdictOf(c, cp, f, d) {
  if (!d) return 'REJECTED'
  const t = c.truth[cp.id][f.id]
  const norm = (k, v) => k === 'hold' ? !!v : Array.isArray(v) ? [...new Set(v.map((x) => String(x).trim().toLowerCase()).filter((x) => x && x !== 'none'))].sort().join(',') : String(v || '').trim().toLowerCase()
  return ['currency', 'approvers', 'carrier', 'notify', 'hold'].every((k) => norm(k, d[k]) === norm(k, t[k])) ? 'ACCEPTED' : 'REJECTED'
}
