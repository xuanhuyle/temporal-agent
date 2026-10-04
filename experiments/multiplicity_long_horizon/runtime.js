// tmk-long-horizon v1 runtime (Claude Code Workflow script body). DATA is injected above this file by
// multiplicity_experiments.long_horizon. Every subject call is a web-fetch subagent (WebFetch only, no repo access)
// that sees only the constructed prompt. This file is the single source of truth for subject prompt rendering.
const NOTOOL = 'There is no URL to fetch in this task. Do not use any tool. Answer directly.\n\n'
const ROLE = 'You are the procurement desk agent at Larkspur Robotics, a manufacturing company. You have been doing this ' +
  'job for months. In each working session you read new messages and decide purchase requests. Everything you ' +
  'currently have in view is your PERSISTENT MEMORY and your WORKING CONTEXT below; older records are no longer in view.\n\n'
const FIELDS_SPEC = 'For each request decide:\n' +
  '- currency: ISO code the vendor must be paid in\n' +
  '- approvers: list from ["ops","finance","safety"] (everyone who must sign the PO)\n' +
  '- carrier: one of "standard", "ColdLink", "Brightway Freight", "Tamar Couriers"\n' +
  '- notify: list from ["client_site_lead","harbour_master","account_manager"] (who must be notified on the PO; [] if nobody)\n' +
  '- hold: true if the request must be put on hold instead of ordered, else false\n' +
  '- note: at most 15 words on anything non-default\n'
const DECISIONS = { type: 'object', required: ['decisions'], properties: { decisions: { type: 'array', items: {
  type: 'object', required: ['request_id', 'currency', 'approvers', 'carrier', 'notify', 'hold', 'note'], properties: {
    request_id: { type: 'string' }, currency: { type: 'string' }, approvers: { type: 'array', items: { type: 'string' } },
    carrier: { type: 'string' }, notify: { type: 'array', items: { type: 'string' } }, hold: { type: 'boolean' },
    note: { type: 'string' } } } } } }
const MEMORY = { type: 'object', required: ['rules', 'commitments', 'open_items', 'notes'], properties: {
  rules: { type: 'array', items: { type: 'string' } }, commitments: { type: 'array', items: { type: 'string' } },
  open_items: { type: 'array', items: { type: 'string' } }, notes: { type: 'array', items: { type: 'string' } } } }
const SECTIONS = [['rules', 'Rules & policies'], ['commitments', 'Commitments'], ['open_items', 'Open items'], ['notes', 'Notes']]

const clone = (x) => JSON.parse(JSON.stringify(x))
const memLen = (m) => SECTIONS.reduce((n, [k]) => n + (m[k] || []).reduce((a, e) => a + e.length, 0), 0)
const ctxLen = (c) => c.reduce((n, r) => n + r.text.length, 0)
const memText = (m) => SECTIONS.map(([k, t]) => t + ':\n' +
  ((m[k] || []).length ? m[k].map((e) => '- ' + e).join('\n') : '- (none)')).join('\n')
const ctxText = (c) => c.length ? c.map((r) => r.text).join('\n\n') : '(empty: your working context was just compacted)'
const stateText = (st) => 'PERSISTENT MEMORY\n' + memText(st.memory) + '\n\nWORKING CONTEXT (recent records, oldest first)\n' + ctxText(st.context)
const fmtDecision = (d) => !d ? '(no decision recorded)' :
  `decided: currency ${d.currency}; approvers ${(d.approvers || []).join('+') || '-'}; carrier ${d.carrier}; ` +
  `notify ${(d.notify || []).join('+') || '-'}; hold ${d.hold ? 'yes' : 'no'}${d.note ? ' (' + d.note + ')' : ''}`
const byId = (out) => Object.fromEntries(((out && out.decisions) || []).map((d) => [String(d.request_id).trim(), d]))

function decidePrompt(st, reqs) {
  return NOTOOL + ROLE + stateText(st) + '\n\nREQUESTS TO DECIDE NOW\n' + reqs.map((r) => r.text).join('\n') +
    '\n\n' + FIELDS_SPEC + 'Return one decision per request, with its request_id.'
}
function compactPrompt(st, extra) {
  return NOTOOL + ROLE + stateText(st) + '\n\nMEMORY MAINTENANCE\nYour working context is full. Rewrite your persistent ' +
    'memory now. Afterwards the working context above is discarded: anything you do not keep in memory will no longer be ' +
    'in view in future sessions (the raw records stay archived, but you do not see them during normal work). The whole ' +
    `memory must fit within ${DATA.mem_max} characters in total. Keep whatever you judge you will need to keep doing this ` +
    'job well. Return the new memory as lists of short entries: rules, commitments, open_items, notes.' + (extra || '')
}

async function callAgent(prompt, schema, label, phase) {
  for (let attempt = 0; attempt < 2; attempt++) {
    const r = await agent(prompt, { label: attempt ? label + ':retry' : label, phase, agentType: 'web-fetch', schema })
    if (r) { const o = clone(r); delete o.webFetchSavedFiles; return o }
  }
  return null
}

async function runTrajectory(ep, evalReps) {
  const st = { memory: clone(DATA.s0_memory), context: [] }
  const cps = [{ id: 'c0', stage: 0, kind: 'start', memory: clone(st.memory), context: [] }]
  const log = [], evals = []
  const evalCp = (cp) => { for (let r = 0; r < evalReps; r++) evals.push(
    callAgent(decidePrompt(cp, ep.dev_probes), DECISIONS, `probe:${ep.id}:${cp.id}:r${r}`, 'Probe checkpoints')
      .then((out) => ({ checkpoint: cp.id, replicate: r, output: out }), () => ({ checkpoint: cp.id, replicate: r, output: null }))) }
  evalCp(cps[0])
  for (const sg of ep.stages) {
    for (const m of sg.messages) st.context.push({ id: m.id, text: m.text })
    const out = await callAgent(decidePrompt(st, sg.requests), DECISIONS, `stage:${ep.id}:${sg.stage}`, 'Lifetime')
    const dm = byId(out)
    for (const r of sg.requests) st.context.push({ id: r.id, text: `[${sg.date}] ${r.text}\n  => ${fmtDecision(dm[r.id])}` })
    log.push({ stage: sg.stage, kind: 'decide', output: out, ctx_chars: ctxLen(st.context) })
    const cp = { id: `c${sg.stage}`, stage: sg.stage, kind: 'stage_end', memory: clone(st.memory), context: clone(st.context) }
    cps.push(cp); evalCp(cp)
    if (ctxLen(st.context) > DATA.ctx_max) {
      let mem = await callAgent(compactPrompt(st), MEMORY, `compact:${ep.id}:${sg.stage}`, 'Lifetime')
      let retried = false
      if (mem && memLen(mem) > DATA.mem_max * 1.1) {
        retried = true
        const again = await callAgent(compactPrompt(st, `\n\nYour previous attempt was ${memLen(mem)} characters, over ` +
          `the ${DATA.mem_max}-character limit. Previous attempt:\n${memText(mem)}\nShorten it to fit.`), MEMORY,
          `compact:${ep.id}:${sg.stage}:shorten`, 'Lifetime')
        if (again) mem = again
      }
      if (!mem) { log.push({ stage: sg.stage, kind: 'compaction_failed' }); break }
      log.push({ stage: sg.stage, kind: 'compact', memory: mem, mem_chars: memLen(mem), retried, ctx_chars_before: ctxLen(st.context) })
      st.memory = mem; st.context = []
      const cpc = { id: `c${sg.stage}c`, stage: sg.stage, kind: 'post_compaction', memory: clone(mem), context: [] }
      cps.push(cpc); evalCp(cpc)
    }
  }
  return { episode: ep.id, checkpoints: cps, log, probe_runs: await Promise.all(evals) }
}
