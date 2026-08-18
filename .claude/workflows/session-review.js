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
    { title: 'Sweep', detail: 'independent lanes, each blind to the others', model: 'haiku/sonnet/opus per lane' },
    {
      title: 'Cross-check',
      detail: 'adversarially verify the highest-cost findings, budget-capped',
      model: 'kb-adversarial-verifier (opus)',
    },
    {
      title: 'Synthesise',
      detail: 'one ranked report; circles at the top, bookkeeping below',
      model: 'fable, falling back to opus/xhigh',
    },
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

// What a REFUTER gets, and deliberately much less than CONTRACT.
//
// WHY THIS EXISTS. `CONTRACT` orders its reader to open Ray's directive and all
// seven handoffs IN FULL. For a sweep lane that IS the job. For an agent judging
// ONE claim it is a 102,515-byte entry fee — measured, by summing the files the
// contract names — paid before the claim is even read, and paid again by every
// refuter. Across the 69 live findings of run wf_8af76005-9bd that is ~1.8M
// tokens of pure re-reading, and it is most of why 47 of 78 agents were killed by
// the session limit with the report unwritten.
//
// WHAT THE MEASUREMENT IS NOT. Those bytes are NOT prompt bytes. `CONTRACT`
// interpolates PATHS (`${directive}` is `cfg.directive`, a path string), so the
// content arrives as tool-results when the agent reads the files. That distinction
// decides which fix works: the prompt-cache work below cannot touch this cost, and
// only NOT ORDERING THE READ recovers it. A cache-hit metric can therefore go green
// while every one of those tokens is still being spent — so the arm for this change
// is a refuter transcript showing it never opened the directive or the handoffs.
// (Found by the cold audit of this file's own plan; the plan had the mechanism
// wrong while having the number exactly right.)
//
// A refuter that genuinely needs the directive can still read it. It is being
// un-mandated, not hidden.
const REFUTE_CONTRACT = `
HOW TO WORK:
* NEVER read a .jsonl into context. They total hundreds of MB. grep, count, and
  report figures with the command that produced them.
* Control-arm every NEGATIVE. Before concluding "X does not exist" / "nothing
  matched", run the same probe against something you KNOW is present and say so.
  A 0-result grep is not an answer until a control has run. Token SPELLING is a
  bound: grep the variants.
* A bound-limited search (-maxdepth, head -N, --limit, a time window, 2>/dev/null)
  is suspect by construction. A reviewer of this very workflow reported a file
  missing because it sat one level past a -maxdepth 6; it was at depth 7.
* Cite file:line or the exact command for every verdict, or label it unverified.

Write your findings to ${reportDir}/refute-<lane>.md AS YOU GO, not at the end.
An agent that dies holding everything in memory leaves nothing.
`

const LANES = [
  {
    key: 'circles',
    // The round's stated highest-value lane, and the only judgment-heavy sweep:
    // `costs.md` reserves Opus for "multi-step reasoning", which is what tracing
    // re-done work across a round actually is.
    model: 'opus',
    effort: 'high',
    prompt: `Find the CIRCLES: work this round did more than once, abandoned and
restarted, or re-litigated. Rank by cost in tool calls and wall-clock, not by count.
For each: what was re-done, how many times, and what would have stopped it.
This is the most valuable lane — the user's stated complaint is "going in circles
not accomplishing anything", so a circle beats any tidy finding below it.`,
  },
  {
    key: 'forgotten',
    model: 'sonnet',
    effort: 'high',
    prompt: `Find FORGOTTEN REQUIREMENTS: anything the user asked for that was
acknowledged and then not done, or done and then silently reverted. Sweep the
handoffs, the directive, and the issue tracker — issue BODIES, not just titles
(the last run swept titles only and said so). For each: where it was asked, where
it was dropped, and whether it is still live.`,
  },
  {
    key: 'contradicted',
    model: 'sonnet',
    effort: 'high',
    prompt: `Find CONTRADICTED INSTRUCTIONS: places where a rule, skill, CLAUDE.md
line or comment says something the repo does not do, or two of them disagree with
each other. Read a comment AGAINST the code it sits on rather than as documentation
— prose defending a choice is where defects hide, and a confident false comment is
what stops the next reader checking. Cite both sides of every contradiction.`,
  },
  {
    key: 'unpinned',
    // Near-mechanical: registry and pin lookups, `mise`/`uv` output, version
    // string comparisons. `costs.md`: "For simple subagent tasks, specify
    // `model: haiku`".
    model: 'haiku',
    effort: 'medium',
    prompt: `Find UNPINNED or DRIFTING TOOLS: any binary this repo's own code or
tasks invoke that is not pinned in mise.toml, plus any pin that disagrees with what
a shell actually resolves. Check the registry can even express a pin before
reporting one as missing — some tools have no registry entry, which is a different
finding. Run the currency tooling WITH its arguments.`,
  },
  {
    key: 'context',
    // Counting jq over transcripts. Mechanical by construction.
    model: 'haiku',
    effort: 'medium',
    prompt: `Find CONTEXT BLOWOUTS: which sessions exceeded the context target, by
how much, and whether they compacted. Then the load-bearing half — for the worst
offenders, say how the work SHOULD have been decomposed (which reads were
delegable to a subagent, which greps should have been one graph query). Report
delegation rate as a share of tool calls.`,
  },
  {
    key: 'tooling-gap',
    model: 'sonnet',
    effort: 'high',
    prompt: `Find WORK DONE BY HAND THAT A TASK ALREADY OWNS, and recurring shapes
that no task owns yet. For each candidate automation say which layer is EARNED —
skill, mise task, or python module — and what evidence supports it. Be sceptical:
propose nothing that a single existing task already does with the right arguments,
and say plainly which existing tools should be FIXED before anything is added.`,
  },
  {
    key: 'bot-reviews',
    model: 'sonnet',
    effort: 'high',
    prompt: `Find IGNORED BOT REVIEWS — Ray's 2026-08-18 directive (the verbatim
record lives in docs/direction/): enforce reviewing all PR reviews from bots
instead of ignoring them. For every
PR the window touched (merged AND still open), fetch every review and inline
comment left by a bot account (coderabbitai, graphify-labs, any other [bot]) via
gh api repos/{owner}/{repo}/pulls/NUMBER/reviews and .../comments — cite the
exact command per finding. For each bot finding, determine whether it was ever
DISPOSITIONED: fixed by a later commit, filed as an issue, or explicitly
adjudicated false with evidence, anywhere — commits, issues, review reports,
handoffs, the transcripts. An un-dispositioned finding is YOUR finding, with the
bot's severity attached. Also report the inverse so nobody re-verifies: findings
already adjudicated false, with where that was recorded. Note bots whose review
never ran at all (a missing review is not an empty one).`,
  },
  {
    key: 'pending-work',
    model: 'sonnet',
    effort: 'high',
    prompt: `Find PENDING WORK AT RISK — Ray's 2026-08-18 directive (the verbatim
record lives in docs/direction/): ensure no pending work is lost on git
worktrees, branches, or the backup directory.
Enumerate every git worktree (git worktree list), every local branch
with its ahead/behind against origin/main (git for-each-ref with a format naming
upstream and HEAD distance), anything in git stash, and the backup directory if
the ALREADY SETTLED block names one. For each: does its unique work exist on
main, is it superseded (say by what), or is it pending — and if pending, what is
it and how many commits. A branch whose delta is already merged is bookkeeping;
unlanded unique commits are the finding. Work from git commands run inside the
repo — do not walk external directory trees except a backup directory the
settled block names. Cite the exact commands.`,
  },
]

phase('Sweep')
const sweeps = await parallel(
  LANES.map((lane) => () =>
    // CONTRACT FIRST, lane prompt second. The shared part leads so every lane
    // presents the same prefix; with the varying part first (as this was until
    // now) no cache can span two lanes.
    agent(`${CONTRACT}\n${lane.prompt}\nYour lane key is "${lane.key}".`, {
      label: `sweep:${lane.key}`,
      phase: 'Sweep',
      model: lane.model,
      effort: lane.effort,
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['lane', 'findings', 'coverage'],
        properties: {
          // DELIBERATELY NOT `const: lane.key`, which is what this was.
          //
          // `workflows.md:316` makes the OUTPUT SCHEMA part of the cache key:
          // agents share a prefix only when model, effort, agent type, tools,
          // output schema and cwd all match. Pinning the key per lane gave eight
          // lanes eight schemas, so the native fan-out prefix hold (`:318` —
          // hold all but the first, release together once the first response
          // begins) could never engage, and reordering the prompt above would
          // have bought nothing.
          //
          // The typo it guarded against is still CAUGHT: `missing` below
          // compares self-reported keys against LANES. What is lost is
          // ATTRIBUTION — a wrong key surfaces as a missing lane rather than
          // being rejected outright, and its findings ride under that wrong name
          // through `behavioural` and into the report. That is the real trade,
          // and it is made knowingly: a whole-fan-out caching loss every run
          // outweighs a typo that this accounting still reports.
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
// An EXPLICIT "nothing was left unreached". Note what is no longer in this set:
// the empty string. `''` is not a lane saying "none", it is a lane saying
// nothing at all — and treating silence as an all-clear is the same default,
// pointing the same wrong way, that this file already fixed once for a missing
// coverage OBJECT. Fixing it there and leaving it here made the guarantee depend
// on whether a lane omitted the field or emitted it blank.
// (Cold lane, P2, review-2b7bd6ca-cold.md.)
const SAYS_NOTHING = new Set(['none', 'n/a', 'nothing'])
const stated = (value) => (typeof value === 'string' ? value.trim() : '')
const isPartial = (lane) => {
  if (!lane.coverage) return true // said nothing at all — never clean
  return [lane.coverage.never_reached, lane.coverage.opened_not_finished].some(
    (field) => !SAYS_NOTHING.has(stated(field).toLowerCase()),
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
const live = lanes.flatMap((l) => l.findings.filter((f) => f.still_live).map((f) => ({ ...f, lane: l.lane })))

// HOW MANY REFUTERS MAY RUN. Until now: one per live finding, unbounded — 69 of
// them on run wf_8af76005-9bd, which is 88% of that run's 78 agents and the
// direct cause of its death.
//
// `workflows.md:360` warns past 25 agents. This budget keeps the whole run under
// that ceiling: 8 sweeps + MAX_REFUTERS + 1 synthesise <= 25 gives 16; 14 leaves
// margin for a lane that spawns a helper.
//
// This is deliberately the SIMPLEST bound that works — rank by cost_rank, refute
// the top slice, report the rest. Batching several findings into one refuter
// would spend the budget better, and is NOT done here: its mechanics (how to
// split a 12-finding lane, how to label two batches from one lane, how to zip
// verdicts back without silently misattributing all of them) were audited as
// undefined, and a wrong zip corrupts every verdict in a batch instead of losing
// one. Cheap and honest now; batching once it is specified.
const MAX_REFUTERS = 14
const ranked = [...live].sort((a, b) => (a.cost_rank ?? 999) - (b.cost_rank ?? 999))
const behavioural = ranked.slice(0, MAX_REFUTERS)
// NOT dropped silently — that is the failure this whole workflow exists to catch.
// These reach the report as their own state, distinct from `unverified` (nobody
// returned) and `refuted` (checked and killed).
const notTriaged = ranked.slice(MAX_REFUTERS)
for (const f of notTriaged) {
  log(`NOT TRIAGED — ${f.lane}: "${f.claim}" (cost_rank ${f.cost_rank ?? '?'}) — budget spent`)
}
if (notTriaged.length) {
  log(`${notTriaged.length} of ${live.length} live findings were NOT cross-checked (cap ${MAX_REFUTERS})`)
}

// Identical for every refuter in a run, so it sits in the shared prefix rather
// than varying per agent. Claims only — the evidence would multiply the payload
// by the very factor the lean contract just removed.
const otherClaims = live.map((f, i) => `  ${i + 1}. [${f.lane}] ${f.claim}`).join('\n')

const verdicts = await parallel(
  behavioural.map((f) => () =>
    agent(
      // REFUTE_CONTRACT leads: it is identical across every refuter, so it is the
      // shared prefix. The finding follows because it is what varies.
      `${REFUTE_CONTRACT}
Try to REFUTE this finding. Find the probe that produces the OPPOSITE answer.
Default to refuted=true if you cannot confirm it. Check specifically whether the
original probe could only have produced the answer it gave — a bound, a token
spelling, a redirect, a parse error read as a "no".

Say whether any OTHER finding below contradicts this one; two probes of one fact
disagreeing is a finding in its own right, and the defect is usually in a probe.

EVERY OTHER LIVE FINDING THIS ROUND, claim only — this is the "set" above, and it
is listed because instructing you to compare against a set you were never given
is an instruction that cannot be followed:
${otherClaims}

THE FINDING YOU ARE JUDGING (lane ${f.lane}): ${f.claim}
EVIDENCE OFFERED: ${f.evidence}`,
      {
        label: `refute:${f.lane}`,
        phase: 'Cross-check',
        // The roster's own refuter — `kb-adversarial-verifier` (opus/high),
        // described for exactly this job. Routing by agentType rather than a bare
        // model is the house pattern `kb-tool-review.js` already uses, and it
        // takes this phase off whatever model the session happens to be running.
        agentType: 'kb-adversarial-verifier',
        schema: {
          type: 'object',
          additionalProperties: false,
          // `probe` and `control_arm` are here because `additionalProperties:
          // false` with only {refuted, why, contradicts} STRIPPED them —
          // `kb-adversarial-verifier`'s whole method is "restate the claim as a
          // probe that could return either answer, run the control arm first",
          // and the schema was discarding exactly that evidence on the way out.
          //
          // It matters beyond tidiness: one run refuted 13 of 14 findings, and
          // with no probe recorded there is no way to tell a claim that was
          // FALSE from one that was merely hard to re-derive — which is issue
          // #343's open question, unanswerable because of this schema.
          // (Cold lane, P2, review-2b7bd6ca-cold.md.)
          required: ['refuted', 'why', 'probe'],
          properties: {
            refuted: { type: 'boolean' },
            why: { type: 'string' },
            probe: { type: 'string', description: 'the exact command or read that settled it' },
            control_arm: {
              type: 'string',
              description: 'the probe proving the check could have returned the other answer',
            },
            contradicts: { type: 'string' },
          },
        },
      },
    ).then((v) => ({ finding: f, verdict: v })),
  ),
)

// A thunk that THREW — as opposed to an agent that returned null — makes
// `parallel()` substitute a bare `null` for that slot. `filter(Boolean)` then
// dropped it, and the finding vanished from `confirmed`, `refuted` AND
// `unverified` alike: silent loss past the gate, which is this repo's signature
// defect class and the exact thing the comment below congratulates itself on
// having fixed. It fixed the null-VERDICT case and left the null-ENTRY case open.
//
// Re-derive from the index, exactly as `kb-tool-review.js:160-172` already does
// for its own fan-out — the pattern existed in the sibling workflow and not here.
//
// Counted UNVERIFIED, not refuted. That differs from the sibling deliberately:
// it has no unverified bucket, so refuted is its safe default, while here
// "nobody returned an answer" has its own state and using it is the honest read.
// (Cold lane, P1, review-2b7bd6ca-cold.md.)
const threw = verdicts.reduce((n, v) => n + (v ? 0 : 1), 0)
if (threw) log(`WARNING: ${threw} cross-check thunk(s) threw — counted as UNVERIFIED, not dropped`)
const checked = verdicts.map((v, i) => v ?? { finding: behavioural[i], verdict: null })
const confirmed = checked.filter((c) => c.verdict && !c.verdict.refuted).map((c) => c.finding)
const refuted = checked.filter((c) => c.verdict && c.verdict.refuted)
// A cross-check agent that DIED returns a null verdict, which satisfies neither
// filter above — so the finding fell out of `confirmed` AND `refuted` and reached
// the synthesis in neither. Silent loss past the gate, and the same shape as the
// coverage bug this file was already fixed for. An unchecked finding is not a
// refuted one; it is a finding nobody verified, and it is reported as that.
const unverified = checked.filter((c) => !c.verdict).map((c) => c.finding)
for (const f of unverified) log(`CROSS-CHECK DID NOT RETURN — ${f.lane}: "${f.claim}" is UNVERIFIED, not refuted`)
log(
  `${confirmed.length} confirmed, ${refuted.length} refuted, ${unverified.length} unverified, ` +
    `${notTriaged.length} not triaged — of ${live.length} live findings`,
)

// A refuted finding, WHOLE. `{claim, why}` was all that either of the two sites
// below carried, which meant `lane`, `evidence`, `cost_rank`, `control_arm` and
// `remedy` were dropped for every refuted finding — so the synthesiser could
// neither rank them by cost nor say which lane raised them, and the run's own
// state file records the loss (refuted objects carry 2 keys; unverified carry 7).
const refutedWhole = (r) => ({ ...r.finding, why: r.verdict.why, contradicts: r.verdict.contradicts })

// Fable for judgment, Opus if Fable is gone — and never silently.
//
// The caller owns this fallback, per `kb-advisor.md`: "you never silently become a
// different model, and a run that fell back should say so in its output". `agent()`
// returns null when a subagent dies on a terminal error after retries, which is the
// signal to re-dispatch.
//
// `xhigh` on the fallback is deliberately ABOVE doctrine's same-effort rule: this is
// one agent on already-distilled input, so the cost delta is negligible against the
// run, and it is the one output everything else exists to produce.
//
// WHAT THIS DOES NOT HEAL: a session or weekly limit. `costs.md` states those are
// "shared across all models, so switching models with /model doesn't restore access"
// — and that is exactly the death this workflow met. Only spending less, and the
// salvage path, answer that one.
async function judge(prompt, opts) {
  const first = await agent(prompt, { ...opts, model: 'fable', effort: 'high' })
  if (first) return { value: first, ranOn: 'fable/high' }
  log('FABLE UNAVAILABLE — re-dispatching to opus at xhigh. THIS RUN FELL BACK.')
  const second = await agent(prompt, { ...opts, model: 'opus', effort: 'xhigh' })
  if (!second) log('OPUS FALLBACK ALSO FAILED — no synthesis was produced.')
  return { value: second, ranOn: second ? 'opus/xhigh (fallback)' : null }
}

phase('Synthesise')
const synthesised = await judge(
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

REFUTED, with the refutation — WHOLE, so you can rank these by cost and attribute
them to a lane like any other finding:
${JSON.stringify(refuted.map(refutedWhole), null, 1)}

NOT TRIAGED — the cross-check budget ran out before these were reached. They are
NOT refuted, NOT confirmed, and nobody looked at them. Report them as their own
category and say plainly that the review did not reach them:
${JSON.stringify(notTriaged, null, 1)}

LANE COVERAGE (partial lanes are listed again below — do not let them read as clean):
${JSON.stringify(lanes.map((l) => ({ lane: l.lane, coverage: l.coverage })), null, 1)}

PARTIAL LANES: ${JSON.stringify(interrupted.map((l) => l.lane))}
LANES THAT DID NOT RETURN AT ALL (they cover NOTHING): ${JSON.stringify(missing)}

Write it to ${reportDir}/session-review-synthesis.md and end with the
"## GitHub repos touched" section this repo's rules require.`,
  { label: 'synthesise', phase: 'Synthesise', agentType: 'kb-synthesist' },
)

return {
  lanes: lanes.map((l) => ({ lane: l.lane, findings: l.findings.length, coverage: l.coverage })),
  // Both kinds of incomplete, kept apart: a lane that ran and did not finish,
  // and one that never reported. Collapsing them would hide the worse case.
  partial_coverage: interrupted.map((l) => l.lane),
  lanes_that_did_not_return: missing,
  confirmed,
  // WHOLE, for the same reason the synthesis prompt gets them whole: this return
  // value is the salvage surface. A killed run is resumed from it, and the run
  // that motivated this change left its 8 refuted findings stripped to
  // {claim, why} with no way to recover lane or evidence from the state file.
  refuted: refuted.map(refutedWhole),
  unverified,
  // The budget ran out before these; nobody checked them. Distinct from
  // `unverified`, where an agent was dispatched and did not come back.
  not_triaged: notTriaged,
  report: synthesised.value,
  // Which model actually produced the report. A fallback that nothing records is
  // a fallback nobody can audit afterwards.
  synthesis_ran_on: synthesised.ranOn,
}
