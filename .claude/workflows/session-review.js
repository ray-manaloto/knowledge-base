// session-review — what a round looks like from OUTSIDE the session.
//
// The 2026-08-17 review ran as an inline five-agent fan-out and found things no
// task can see: 10 of 10 sessions over the 200K context target with zero
// compactions, `gh` pinned nowhere while `kb-ship` calls it, a `CLAUDE.md` line
// asserting a policy the repo does not follow, and `docs/direction/**` with no
// reader at all. It was never saved, so it could not be re-run — which is the
// same disease it was written to diagnose. This file is that fix.
//
// WHY A WORKFLOW AND NOT A MISE TASK. `mise-tasks-only.md` wants a task wrapping
// a python module, and this cannot be one: a task is a shell command and only
// the model can spawn Claude agents. Same reason `kb-extract` is a workflow.
// `kb-session-reflect` (the task) counts what a transcript DID; this counts what
// the round should have done and did not, which needs judgement per lane.
//
// WHAT IT IS NOT. It never edits, ships, or files anything. It returns findings.
// The caller — the `kb-session-review` skill — runs the AskUserQuestion preflight
// BEFORE this (a workflow cannot ask), then applies what comes back.
//
// Invoke:
//   Workflow({ name: 'session-review', args: {
//     transcriptDir: '/abs/path/to/projects/<slug>',   // REQUIRED
//     since: '2026-08-15',                             // REQUIRED, no default
//     directive: 'docs/direction/2026-08-17-ray-directives.md',  // newest, read in full
//     handoffs: ['.agent/plans/session-2026-08-17-g.md', ...],   // REQUIRED, see L5
//     reportDir: '.agent/kb/reports/agents',
//     answered: { ... },   // whatever the skill's preflight settled, so no lane re-hunts it
//   }})
//
// `since` has NO DEFAULT on `kb-extract`'s precedent: `Date.now()` and
// `new Date()` THROW inside a Workflow script, so a default would either be a
// hardcoded lie or a crash. Passed in, or it stops here.
//
// ── THE FIVE LESSONS THE LAST RUN OWED ITSELF (its own §7), now enforced ──
//
// L1  ASK FIRST. Two agents spent a full pass each hunting a question one
//     sentence settled. `answered` is threaded into every lane so a settled
//     question is never re-hunted, and the skill refuses to start without it.
// L2  SWEEP ISSUE BODIES, NOT TITLES. The last run swept titles only and said so.
// L3  READ THE HANDOFFS. `.agent/plans/session-*.md` is where a round's real
//     instructions live. REQUIRED rather than discovered, because `.agent/` is
//     gitignored and a glob that matches nothing looks exactly like a clean round.
// L4  RUN THE TOOLS WITH THEIR ARGUMENTS. Two of four "existing tool" outputs
//     last time were window-mismatched or argument artifacts.
// L5  DELEGATE THE TRANSCRIPT READS. 426 MB of `.jsonl`; no agent may read one
//     into context. Every lane greps and counts, and reports figures.
//
// ── WHAT THE 2026-08-17 ROUND ADDED, learned by shipping the error ──
//
// L6  AN INTERRUPTED LANE READS LIKE A FINISHED ONE. A review lane died on a
//     usage limit and another on a content-policy refusal, mid-run, and each
//     returned a confident report about the files it HAD reached. Every lane
//     here must end with an explicit COVERAGE line naming what it did not reach;
//     a lane with no coverage line is treated as partial, never as clean.
// L7  A CLEAN SWEEP IS ABOUT THE TESTS, NOT THE PREMISE. Applies to this
//     workflow too: `NO FINDINGS` from a lane means that lane found nothing,
//     never that the area is sound.
// L8  PROSE DEFENDING A CHOICE IS WHERE DEFECTS HIDE. Two findings this round sat
//     behind a confident, FALSE comment that stopped anyone checking. So one lane
//     reads comments AGAINST the code they sit on, rather than as documentation.
// L9  A NUMBER IS INVALIDATED BY THE COMMIT THAT WRITES IT. Every count a lane
//     reports must name what it counted and when, or it is unusable next round.
// L10 CROSS-CHECK BEFORE REPORTING A SURPRISE. Two lanes disagreeing is a finding
//     — usually about a probe. The `cap` hunt's whole value last time was that
//     two independent routes returned DIFFERENT answers.

export const meta = {
  name: 'session-review',
  description: 'What a round looks like from outside it: circles, forgotten requirements, contradicted instructions, unpinned tools, context blowouts',
  whenToUse: 'End of a multi-session round, or when the user says work is going in circles. Invoked by the kb-session-review skill, which runs the AskUserQuestion preflight first.',
  phases: [
    { title: 'Sweep', detail: 'independent lanes, each blind to the others' },
    { title: 'Cross-check', detail: 'adversarially verify every finding that would change behaviour' },
    { title: 'Synthesise', detail: 'one ranked report; circles at the top, bookkeeping below' },
  ],
}

let cfg = args || {}
if (typeof cfg === 'string') {
  try {
    cfg = JSON.parse(cfg)
  } catch (e) {
    throw new Error('session-review: args arrived as an unparsable string: ' + e.message)
  }
}

for (const required of ['transcriptDir', 'since', 'handoffs']) {
  if (!cfg[required] || (Array.isArray(cfg[required]) && !cfg[required].length)) {
    throw new Error(
      `session-review: '${required}' is REQUIRED and has no default. ` +
        (required === 'handoffs'
          ? 'A glob that matches nothing looks exactly like a round with no handoffs (L3).'
          : 'A computed default would be a hardcoded lie — Date.now() throws in a workflow.'),
    )
  }
}

const reportDir = cfg.reportDir || '.agent/kb/reports/agents'
const answered = JSON.stringify(cfg.answered || {}, null, 1)
const directive = cfg.directive || '(none supplied — say so in your coverage line)'

// Every lane carries this. It is the difference between a report and a claim.
const CONTRACT = `
SCOPE: transcripts in ${cfg.transcriptDir} with mtime >= ${cfg.since}.
Ray's standing directive: ${directive} — read it IN FULL before you conclude anything.
Round handoffs, which are where the real instructions live — read every one:
${(cfg.handoffs || []).map((h) => '  - ' + h).join('\n')}

ALREADY SETTLED BY THE USER — do NOT spend a probe re-deriving any of this:
${answered}

HOW TO WORK:
* NEVER read a .jsonl into context. They total hundreds of MB. grep, count, and
  report figures with the command that produced them.
* Every count you report must name WHAT was counted and WHEN. A bare number is
  unusable next round.
* Control-arm every NEGATIVE. Before reporting "X does not exist" / "nothing
  matched", run the same probe against something you KNOW is present and say so.
  A 0-result grep is not an answer until a control has run. Token SPELLING is a
  bound: grep the variants.
* A bound-limited search (-maxdepth, head -N, --limit, a time window, 2>/dev/null)
  is suspect by construction. Either remove the bound or prove the target is in it.
* Cite file:line or the exact command for every claim, or label it "unverified".

HOW TO FINISH — this is not optional:
End your report with a COVERAGE line naming, explicitly:
  - what you reached and analysed
  - what you OPENED but did not finish analysing
  - what you never reached at all
A lane that is interrupted returns a confident report about the part it reached
and reads exactly like one that finished. That happened twice in the round that
wrote this file. If you are running out of room, write the coverage line FIRST.

Write your findings to ${reportDir}/<your-lane>.md AS YOU GO, not at the end.
An agent that dies holding everything in memory leaves nothing.
`

const LANES = [
  {
    key: 'circles',
    prompt: `Find the CIRCLES: work this round did more than once, abandoned and
restarted, or re-litigated. Rank by cost in tool calls and wall-clock, not by count.
For each: what was re-done, how many times, and what would have stopped it.
This is the most valuable lane — the user's stated complaint is "going in circles
not accomplishing anything", so a circle beats any tidy finding below it.`,
  },
  {
    key: 'forgotten',
    prompt: `Find FORGOTTEN REQUIREMENTS: anything the user asked for that was
acknowledged and then not done, or done and then silently reverted. Sweep the
handoffs, the directive, and the issue tracker — issue BODIES, not just titles
(the last run swept titles only and said so). For each: where it was asked, where
it was dropped, and whether it is still live.`,
  },
  {
    key: 'contradicted',
    prompt: `Find CONTRADICTED INSTRUCTIONS: places where a rule, skill, CLAUDE.md
line or comment says something the repo does not do, or two of them disagree with
each other. Read a comment AGAINST the code it sits on rather than as documentation
— prose defending a choice is where defects hide, and a confident false comment is
what stops the next reader checking. Cite both sides of every contradiction.`,
  },
  {
    key: 'unpinned',
    prompt: `Find UNPINNED or DRIFTING TOOLS: any binary this repo's own code or
tasks invoke that is not pinned in mise.toml, plus any pin that disagrees with what
a shell actually resolves. Check the registry can even express a pin before
reporting one as missing — some tools have no registry entry, which is a different
finding. Run the currency tooling WITH its arguments.`,
  },
  {
    key: 'context',
    prompt: `Find CONTEXT BLOWOUTS: which sessions exceeded the context target, by
how much, and whether they compacted. Then the load-bearing half — for the worst
offenders, say how the work SHOULD have been decomposed (which reads were
delegable to a subagent, which greps should have been one graph query). Report
delegation rate as a share of tool calls.`,
  },
  {
    key: 'tooling-gap',
    prompt: `Find WORK DONE BY HAND THAT A TASK ALREADY OWNS, and recurring shapes
that no task owns yet. For each candidate automation say which layer is EARNED —
skill, mise task, or python module — and what evidence supports it. Be sceptical:
propose nothing that a single existing task already does with the right arguments,
and say plainly which existing tools should be FIXED before anything is added.`,
  },
]

phase('Sweep')
const sweeps = await parallel(
  LANES.map((lane) => () =>
    agent(`${lane.prompt}\n${CONTRACT}\nYour lane key is "${lane.key}".`, {
      label: `sweep:${lane.key}`,
      phase: 'Sweep',
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['lane', 'findings', 'coverage'],
        properties: {
          lane: { type: 'string' },
          coverage: {
            type: 'object',
            additionalProperties: false,
            required: ['reached', 'opened_not_finished', 'never_reached'],
            properties: {
              reached: { type: 'string' },
              opened_not_finished: { type: 'string' },
              never_reached: { type: 'string' },
            },
          },
          findings: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              required: ['claim', 'evidence', 'cost_rank', 'still_live'],
              properties: {
                claim: { type: 'string' },
                evidence: { type: 'string', description: 'file:line or the exact command, or the word unverified' },
                control_arm: { type: 'string', description: 'the probe that proves this probe discriminates' },
                cost_rank: { type: 'integer', description: '1 = most expensive to leave unfixed' },
                still_live: { type: 'boolean' },
                remedy: { type: 'string' },
              },
            },
          },
        },
      },
    }),
  ),
)

const lanes = sweeps.filter(Boolean)

// A lane is COMPLETE only if it says so. Everything else is partial, including
// the two cases the first version of this filter called clean — both found by
// the cold lane on PR #339, in the code whose own L6 says "a lane with no
// coverage line is treated as partial, never as clean":
//
//   * it read `never_reached` and IGNORED `opened_not_finished`, so a lane cut
//     off mid-analysis ("3 items opened", "never_reached: none") reported clean.
//     Read-but-unanalysed is the harder half to spot, which is exactly why L6
//     asks for the field.
//   * `(l.coverage?.never_reached || '')` turned a MISSING coverage object into
//     the empty string, i.e. into "clean" — the default pointing the wrong way
//     on the one lane that told you least.
const SAYS_NOTHING = new Set(['', 'none', 'n/a', 'nothing'])
const stated = (value) => (typeof value === 'string' ? value.trim() : '')
const isPartial = (lane) => {
  if (!lane.coverage) return true // said nothing at all — never clean
  return [lane.coverage.never_reached, lane.coverage.opened_not_finished].some(
    (field) => stated(field) && !SAYS_NOTHING.has(stated(field).toLowerCase()),
  )
}

const interrupted = lanes.filter(isPartial)
// A lane that DIED — usage limit, refusal, exception — returns null and is
// filtered out of `lanes` entirely, so it can never appear in `interrupted`.
// That is the loudest possible partial coverage and it was the quietest.
const missing = LANES.map((l) => l.key).filter((key) => !lanes.some((l) => l.lane === key))

for (const l of interrupted) {
  // Only report a field that SAYS something — `isPartial` already treats "none"
  // as silence, and printing "never reached none" beside a real gap reads as a
  // second gap.
  const says = (v) => stated(v) && !SAYS_NOTHING.has(stated(v).toLowerCase()) && stated(v)
  const why = [
    says(l.coverage?.never_reached) && `never reached ${says(l.coverage.never_reached)}`,
    says(l.coverage?.opened_not_finished) && `opened but unfinished: ${says(l.coverage.opened_not_finished)}`,
  ].filter(Boolean).join('; ')
  log(`PARTIAL COVERAGE — ${l.lane}: ${why || 'returned no coverage statement'}`)
}
for (const key of missing) log(`LANE DID NOT RETURN — ${key}: treat as covering NOTHING`)
log(`${lanes.length}/${LANES.length} lanes returned; ${lanes.reduce((n, l) => n + l.findings.length, 0)} raw findings`)

// A barrier IS correct here: the cross-check needs the whole set, because two
// lanes disagreeing about one fact is itself the highest-value finding — that is
// how the last round's cap hunt earned its keep.
phase('Cross-check')
const behavioural = lanes.flatMap((l) => l.findings.filter((f) => f.still_live).map((f) => ({ ...f, lane: l.lane })))
const verdicts = await parallel(
  behavioural.map((f) => () =>
    agent(
      `Try to REFUTE this finding. Find the probe that produces the OPPOSITE answer.
Default to refuted=true if you cannot confirm it. Check specifically whether the
original probe could only have produced the answer it gave — a bound, a token
spelling, a redirect, a parse error read as a "no".

Also say whether any OTHER finding in the set contradicts it; two probes of one
fact disagreeing is a finding in its own right, and the defect is usually in a probe.

FINDING (lane ${f.lane}): ${f.claim}
EVIDENCE OFFERED: ${f.evidence}
${CONTRACT}`,
      {
        label: `refute:${f.lane}`,
        phase: 'Cross-check',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['refuted', 'why'],
          properties: {
            refuted: { type: 'boolean' },
            why: { type: 'string' },
            contradicts: { type: 'string' },
          },
        },
      },
    ).then((v) => ({ finding: f, verdict: v })),
  ),
)

const checked = verdicts.filter(Boolean)
const confirmed = checked.filter((c) => c.verdict && !c.verdict.refuted).map((c) => c.finding)
const refuted = checked.filter((c) => c.verdict && c.verdict.refuted)
// A cross-check agent that DIED returns a null verdict, which satisfies neither
// filter above — so the finding fell out of `confirmed` AND `refuted` and reached
// the synthesis in neither. Silent loss past the gate, and the same shape as the
// coverage bug this file was already fixed for. An unchecked finding is not a
// refuted one; it is a finding nobody verified, and it is reported as that.
const unverified = checked.filter((c) => !c.verdict).map((c) => c.finding)
for (const f of unverified) log(`CROSS-CHECK DID NOT RETURN — ${f.lane}: "${f.claim}" is UNVERIFIED, not refuted`)
log(`${confirmed.length} confirmed, ${refuted.length} refuted, ${unverified.length} unverified of ${behavioural.length} live findings`)

phase('Synthesise')
const report = await agent(
  `Write ONE ranked review from the material below. Rank by COST OF LEAVING IT
UNFIXED, not by count or by tidiness — the top items must be the circles, and
everything that is bookkeeping must be visibly below them.

State plainly, in the report:
  * which findings were REFUTED during cross-check, and by what. A refuted finding
    is evidence about the probe and belongs in the report, not deleted from it.
  * which lanes had PARTIAL coverage and what they never reached. An interrupted
    lane reads exactly like a finished one; do not let it.
  * what THIS review itself got wrong or could not settle, as its own section.
    Every previous run of this review found defects in its own probes, and that
    section is what made the next run better.

Do not propose an automation that an existing task already does with the right
arguments. Say which existing tools should be FIXED first.

CONFIRMED FINDINGS:
${JSON.stringify(confirmed, null, 1)}

UNVERIFIED — the cross-check agent did not return, so these are NOT refuted and
NOT confirmed. Report them as unverified rather than dropping them:
${JSON.stringify(unverified, null, 1)}

REFUTED, with the refutation:
${JSON.stringify(refuted.map((r) => ({ claim: r.finding.claim, why: r.verdict.why, contradicts: r.verdict.contradicts })), null, 1)}

LANE COVERAGE (partial lanes are listed again below — do not let them read as clean):
${JSON.stringify(lanes.map((l) => ({ lane: l.lane, coverage: l.coverage })), null, 1)}

PARTIAL LANES: ${JSON.stringify(interrupted.map((l) => l.lane))}
LANES THAT DID NOT RETURN AT ALL (they cover NOTHING): ${JSON.stringify(missing)}

Write it to ${reportDir}/session-review-synthesis.md and end with the
"## GitHub repos touched" section this repo's rules require.`,
  { label: 'synthesise', phase: 'Synthesise' },
)

return {
  lanes: lanes.map((l) => ({ lane: l.lane, findings: l.findings.length, coverage: l.coverage })),
  // Both kinds of incomplete, kept apart: a lane that ran and did not finish,
  // and one that never reported. Collapsing them would hide the worse case.
  partial_coverage: interrupted.map((l) => l.lane),
  lanes_that_did_not_return: missing,
  confirmed,
  refuted: refuted.map((r) => ({ claim: r.finding.claim, why: r.verdict.why })),
  unverified,
  report,
}
