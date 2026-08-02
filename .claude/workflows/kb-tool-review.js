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
// Invoke (from a Claude session) — by scriptPath, NEVER by name. A `name:`
// resolves to a STALE CACHED COPY (#13, measured: kb-extract.js was edited,
// re-invoked by name, and returned the old error text verbatim), so a by-name
// run of this file would exercise a pre-patch script while reporting on the
// committed one. This example said `name:` until 2026-08-02, which is the
// documentation equivalent of the same bug.
//   Workflow({
//     scriptPath: '.claude/workflows/kb-tool-review.js',
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
Write your report to BOTH, INCREMENTALLY — update as you go, never at the end.
Agents that batched to the end have died holding everything.
  1. .agent/kb/reports/agents/  — scratch, survives your death mid-run
  2. ${reportDir}/<key>-retrieval-gap.md — TRACKED, survives a fresh clone
Path 2 is not optional. On 2026-08-02 this workflow completed 31 agents and left
NOTHING in ${reportDir}: only path 1 was named here, .agent/ is gitignored, and
the script itself cannot write files (workflow scripts have no filesystem access
— which is why this is an instruction to you rather than a write in the script).
The 16,249-character synthesis existed solely in the run result and had to be
extracted by hand from the task output before it was lost.
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
        ).then((v) => ({
          // A dead or skipped verifier resolves to NULL per the agent() contract,
          // and `{...c, verdict: null}` is TRUTHY — so `filter(Boolean)` keeps it
          // and `!v.verdict?.refuted` reads TRUE, silently counting an unrun
          // verification as "the claim survived". That inverts the fail-safe the
          // verifier's own definition spends a paragraph establishing. Synthesize
          // the refutation instead, so a lane that dies costs a claim rather than
          // laundering one. (Cold lane, 04312f3.)
          ...c,
          verdict: v ?? {
            refuted: true,
            probe: 'none — the verifier agent died or was skipped',
            control: 'none',
            evidence: 'No verdict was returned. Defaulting to refuted per the fail-safe.',
          },
        })),
      ),
    ).then((verdicts) => {
      // `??` above only covers agent() FULFILLING with null. A thunk that
      // THROWS bypasses .then entirely and parallel() substitutes a bare null
      // for the whole entry — which `filter(Boolean)` then drops silently, so
      // the claim is neither refuted nor surviving, just gone. The "0 refuted"
      // warning cannot see it either, since it only fires on a total zero.
      // parallel() preserves order, so index i recovers the claim the null was
      // standing in for. (Cold lane round 2 — the residual gap it carried over.)
      const repaired = verdicts.map((v, i) =>
        v ?? {
          ...negatives[i],
          verdict: {
            refuted: true,
            probe: 'none — the verification thunk threw',
            control: 'none',
            evidence: 'parallel() substituted null for this entry. Defaulting to refuted.',
          },
        },
      )
      const lost = verdicts.filter((v) => !v).length
      if (lost) log(`WARNING: ${lost} verification(s) threw for ${t.key} — counted as refuted, not dropped`)
      return { tool: t, res, verdicts: repaired }
    })
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

// PERSIST. A workflow script has no filesystem access, so the only way this run
// leaves a tracked artifact is an agent that writes one. Without this step the
// synthesis — the single most expensive thing the run produces — exists only in
// the returned object, which dies with the session (measured 2026-08-02: 31
// agents, 4.59M tokens, zero files in reportDir).
const reports = await agent(
  `Write these artifacts to disk, VERBATIM, then return their paths as a JSON ` +
    `array of strings. Do not summarise, trim, or reformat any of it.\n\n` +
    `1. ${reportDir}/peer-tool-synthesis-${done.map((d) => d.tool.key).join('-')}.md ` +
    `— the synthesis below, under a provenance header naming the tool keys, their ` +
    `pinned commits, and the counts (${verified} verified, ${refuted} refuted).\n` +
    `2. For each tool, confirm ${reportDir}/<key>-retrieval-gap.md exists and is ` +
    `non-empty; if a researcher failed to write it, reconstruct it from that ` +
    `tool's claims and say so in the file.\n\n` +
    `SYNTHESIS:\n${synthesis}\n\nPER-TOOL:\n${JSON.stringify(
      done.map((d) => ({ tool: d.tool.key, surviving: d.surviving, review: d.review })),
    )}`,
  {
    label: 'persist',
    phase: 'Synthesize',
    // SCHEMA, not bare text. Without it `agent()` returns the subagent's final
    // MESSAGE as a string, so `reports` would be raw prose — and any caller
    // trusting the `reports:[...]` in this file's header comment and calling
    // `.map`/`.forEach` on it gets a TypeError, while a caller that just pastes
    // it gets "Here are the paths: …" instead of a path list. Found by the cold
    // lane on d713eb1: the contract was documented as an array and returned as
    // text, one commit after this file was fixed for a different contract lie.
    schema: { type: 'array', items: { type: 'string' } },
  },
)

// `unverified` is the claims that never reached the verifier: only NEGATIVE
// claims are sent, so a positive claim is unchallenged rather than confirmed.
// It was in this file's documented contract and missing from the return for as
// long as the file has existed — the run that found that is the run that first
// executed it.
// `d.res.claims`, NOT `d.claims`: stage 2 returns `{tool, res, verdicts}`, so the
// claim list is one level down. `d.claims` would be undefined, silently fall back
// to `verdicts.length` (negatives only), and report unverified as 0 — the exact
// shape of under-reporting this field was added to end.
const claimed = done.reduce((n, d) => n + (d.res?.claims?.length ?? d.verdicts.length), 0)
const unverified = Math.max(0, claimed - verified - refuted)

return { tools: done.length, verified, refuted, unverified, synthesis, reports }
