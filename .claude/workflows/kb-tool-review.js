// kb-tool-review — reusable cross-family peer-tool gap analysis.
//
// Saved so the team is a DELIVERABLE rather than scaffolding for one round
// (Ray, 2026-07-31: "save this agent team for re-use and to improve"). It pairs
// with the four agent definitions in `.claude/agents/`:
//   kb-tool-researcher · kb-adversarial-verifier · kb-synthesist · kb-corpus-curator
//
// Cross-family review deliberately does NOT get its own agent file. The
// `fable-orchestrator` plugin already ships `codex-reviewer` (GPT-5.6 Sol) and
// `antigravity` ships a Gemini lane; writing a third would be reinventing a tool
// feature, which `use-tool-builtins.md` exists to prevent. This script ROUTES to
// them instead, and that is the only place the routing lives.
//
// Invoke (from a Claude session):
//   Workflow({
//     name: 'kb-tool-review',
//     args: {
//       reportDir: 'docs/research/reports',
//       tools: [
//         { key: 'codebase-memory-mcp', source: 'sources/codebase-memory-mcp',
//           lens: 'retrieval', note: 'C, 158 languages, sub-ms claims' },
//         { key: 'mindwalk', source: 'sources/mindwalk',
//           lens: 'observability', note: 'reads session logs; does NOT index code' },
//       ],
//     },
//   })
//
// Returns { tools, verified, refuted, unverified, reports:[...] }.

export const meta = {
  name: 'kb-tool-review',
  description: 'Cross-family peer-tool gap analysis: research, adversarially verify, review, synthesize',
  phases: [
    { title: 'Research', detail: 'one researcher per tool; graph-first, both directions' },
    { title: 'Verify', detail: 'every NEGATIVE claim refuted or armed, one agent per claim' },
    { title: 'Review', detail: 'cross-family reviewer, never the author’s own family' },
    { title: 'Synthesize', detail: 'cross-tool comparison + consolidated gap list' },
  ],
}

// Same defensive parse as kb-extract.js: args has been observed arriving as a
// JSON string rather than an object, which makes `cfg.tools` undefined and the
// guard below blame the caller for a shape they actually passed correctly.
let cfg = args || {}
if (typeof cfg === 'string') {
  try { cfg = JSON.parse(cfg) } catch { cfg = {} }
}
const tools = cfg.tools || []
const reportDir = cfg.reportDir || 'docs/research/reports'
if (!tools.length) throw new Error('kb-tool-review: args.tools is required and must be non-empty')

const CLAIMS_SCHEMA = {
  type: 'object',
  required: ['tool', 'claims'],
  properties: {
    tool: { type: 'string' },
    reportPath: { type: 'string' },
    claims: {
      type: 'array',
      items: {
        type: 'object',
        required: ['text', 'direction', 'negative'],
        properties: {
          text: { type: 'string' },
          // Both directions are mandatory per Ray: a gap analysis naming only
          // what graphify lacks is advocacy, not analysis.
          direction: { enum: ['tool_lacks', 'graphify_lacks', 'not_comparable'] },
          // Only NEGATIVE claims go to the verifier. Verifying "it has feature X"
          // that you just read is cheap agreement; the claims that have actually
          // been wrong here are all absences.
          negative: { type: 'boolean' },
          evidence: { type: 'string' },
        },
      },
    },
  },
}

const VERDICT_SCHEMA = {
  type: 'object',
  required: ['refuted', 'probe', 'control'],
  properties: {
    refuted: { type: 'boolean' },
    probe: { type: 'string' },
    control: { type: 'string' },
    evidence: { type: 'string' },
  },
}

const orientation = `
Read the graph BEFORE any file: \`mise run kb-query -- "<q>" --prose --idf\`.
The tool's own nodes are in graphify-out/study-graph.json (the STUDY graph, not
the aggregate): \`graphify query "…" --graph graphify-out/study-graph.json\`.
Control-arm every empty result against a term you KNOW is present.
Write your report to .agent/kb/reports/agents/ INCREMENTALLY — update it as you
go, never at the end. Agents that batched to the end have died holding everything.
`.trim()

// pipeline, not parallel: a tool whose research finishes first should start
// verifying while a slower tool is still being read. There is no cross-tool
// dependency until synthesis, so a barrier here would only waste wall-clock.
const perTool = await pipeline(
  tools,
  (t) =>
    agent(
      `${orientation}\n\nResearch the tool at ${t.source} (key: ${t.key}, lens: ${t.lens}).` +
        `${t.note ? ` Context: ${t.note}.` : ''}\n` +
        `Produce gap claims in BOTH directions. Mark every claim that asserts an ` +
        `ABSENCE as negative:true — those are the ones that have been wrong before.`,
      { agentType: 'kb-tool-researcher', label: `research:${t.key}`, phase: 'Research', schema: CLAIMS_SCHEMA },
    ),
  (res, t) => {
    if (!res) return null
    const negatives = (res.claims || []).filter((c) => c.negative)
    log(`${t.key}: ${res.claims.length} claims, ${negatives.length} negative -> verifier`)
    return parallel(
      negatives.map((c) => () =>
        agent(
          `Refute this claim about ${t.key}. Default to refuted:true if you cannot ` +
            `establish it.\n\nCLAIM: ${c.text}\nSTATED EVIDENCE: ${c.evidence || '(none given)'}`,
          { agentType: 'kb-adversarial-verifier', label: `verify:${t.key}`, phase: 'Verify', schema: VERDICT_SCHEMA },
        ).then((v) => ({ ...c, verdict: v })),
      ),
    ).then((verdicts) => ({ tool: t, res, verdicts: verdicts.filter(Boolean) }))
  },
  // Cross-family review: the reviewer must NOT be the family that wrote the doc.
  // Every researcher above is Claude, so this is always codex here. If a future
  // caller routes research to a non-Claude lane, change THIS line — the
  // constraint is "different family", not "always codex".
  (out, t) => {
    if (!out) return null
    const surviving = out.verdicts.filter((v) => !v.verdict?.refuted)
    return agent(
      `Cold review of the ${t.key} gap analysis at ${reportDir}. You have NOT been ` +
        `told what it is supposed to conclude, deliberately. ${surviving.length} claims ` +
        `survived adversarial verification. Report findings as severity + one-line ` +
        `claim + file:line; cite every claim or label it unverified.`,
      { agentType: 'fable-orchestrator:codex-reviewer', label: `review:${t.key}`, phase: 'Review' },
    ).then((review) => ({ ...out, review, surviving }))
  },
)

const done = perTool.filter(Boolean)
const verified = done.reduce((n, d) => n + d.surviving.length, 0)
const refuted = done.reduce((n, d) => n + d.verdicts.filter((v) => v.verdict?.refuted).length, 0)

// A barrier IS correct here: synthesis compares tools against each other, so it
// genuinely needs every result at once.
const synthesis = await agent(
  `Combine these verified single-tool gap analyses into one cross-tool comparison ` +
    `and a consolidated capability gap list.\n\n${JSON.stringify(
      done.map((d) => ({ tool: d.tool.key, lens: d.tool.lens, surviving: d.surviving, review: d.review })),
    )}`,
  { agentType: 'kb-synthesist', label: 'synthesize', phase: 'Synthesize' },
)

// Reported, never silently dropped: a zero here means the verifier did not run,
// which is a finding about the process rather than a clean result.
if (refuted === 0) log('WARNING: 0 claims refuted across all tools — the verifier did not do its job')

return { tools: done.length, verified, refuted, synthesis }
