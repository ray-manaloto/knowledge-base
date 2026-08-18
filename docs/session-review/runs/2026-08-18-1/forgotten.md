# Lane: forgotten — Forgotten Requirements Sweep (iter1)

Scope: transcripts >= 2026-08-18, docs/direction/2026-08-18-ray-directives.md (full),
.agent/plans/session-2026-08-18-a.md, GitHub issue tracker (bodies, not just titles).

Working notes appended as found.

---

## Method

- Read `docs/direction/2026-08-18-ray-directives.md` in full (primary directive
  + addendum + the two rulings-blocks), `.agent/plans/session-2026-08-18-a.md`
  in full, and `docs/direction/2026-08-17-ray-directives.md` (grepped) for
  whether any 08-18 item was already raised and dropped once before.
- Read `.claude/workflows/session-review.js` in full (584 lines) — the
  artifact the current session built IN RESPONSE to this directive — to check
  whether each of the directive's 10 numbered items (plus the addendum's asks)
  actually has a lane, a hard gate, or neither.
- `gh issue list` / `gh issue list --json ...body` searches (bodies, not just
  titles, per the explicit instruction that the last sweep only did titles) for
  each directive item's subject, both as a title-search and as a
  `jq 'select(.body | test(...))'` full-text pass over open issues.
- One filesystem probe (`find ~ -iname '*backup*'`) as the control arm on
  "the backup directory" (finding 4 below).

Control arms run: (a) issue-body search returned real hits for unrelated terms
("20%" matched #207 about carbon.now.sh, confirming the search executes and
isn't silently empty-by-construction); (b) the backup-directory find matched 8
real directories on this machine, confirming the probe isn't bounded to zero
results by construction — the absence of a "knowledge-base"-named one among
them is real signal, not a broken glob.

---

## Findings (ranked by cost of leaving unfixed)

### 1. Ray's #1 complaint's diagnosed root cause has no issue and no lane — cost_rank 1

**Claim**: The opening line of the 2026-08-18 directive is *"you are still not
following instructions and losing requirements/instructions between sessions
[because] /clear-prep is having issues w the handoff files."* The directive's
own status table (row 1) names the root cause: *"The handoff is
`.agent/plans/session-*.md`, which is gitignored — it does not survive a
clone. That is a candidate root cause and is not yet fixed."* This is still
true right now — `.gitignore:143` still ignores `.agent/`, confirmed via
`git check-ignore -v .agent/plans/session-2026-08-18-a.md` →
`.gitignore:143:.agent/	.agent/plans/session-2026-08-18-a.md`. No GitHub
issue exists for it (`gh issue list --search "handoff gitignored OR session
handoff durable OR .agent/plans"` and a full-body `jq` pass for
`handoff.*surviv|commit.*handoff|handoff.*track` both return zero matches —
closest hits are #212 LESSONS.md gitignored [different file], #143 make
clear-prep mechanical [different question], #142 .agents/ vs .agent/ naming
[different question]). And none of the 8 new `session-review.js` lanes checks
it either — I read all 8 lane prompts (`circles`, `forgotten`, `contradicted`,
`unpinned`, `context`, `tooling-gap`, `bot-reviews`, `pending-work`;
`session-review.js:187-297`) and none asks whether the handoff mechanism
itself survives a clone/session boundary. The session's whole redirect for
"durable storage" was "GitHub issues, not handoffs" (Ray's ruling on item 3),
but that only covers *findings* — it does not restore the in-flight
session-state continuity item 1 is actually asking for (what branch, what's
uncommitted, what was mid-task). **Still live: yes.**

**Control arm**: searched for a term I know exists in a different, real issue
(#212's "gitignored" + "LESSONS.md") to confirm the search mechanism itself
returns hits — it does, so the zero-result searches above are a real absence,
not a broken query.

**Remedy**: file a GitHub issue proposing the handoff mechanism itself move to
a tracked location (or a tracked pointer/symlink into `.agent/`), and add a
ninth `session-review.js` lane (or extend `forgotten`) that checks whether the
CURRENT handoff mechanism would survive `git clone` + `git clean -xdf`.

---

### 2. Item 10's currency gate contradicts a standing, written design principle — cost_rank 2

**Claim**: Ray's directive, verbatim: *"we need to enforce not doing any work
until all critical currency dependencies are up to date."* This is stated as a
hard block, not a report. But the root `CLAUDE.md` (this repo's own committed
doctrine, read in full at session start) says the *opposite*, in writing:
*"`mise run kb-currency` always exits 0 and can never serve as a CI gate — an
out-of-date tool is a signal, not a failure. Read the report, not the rc."*
Today `kb-currency-check` is a SessionStart hook that is silent unless
something drifted and **always exits 0** — it cannot block anything by
construction. No GitHub issue tracks reconciling this (searched issue bodies
for `currency.*gate|block.*currency|currency.*block` — the 7 hits are all
either self-extraction specs, the currency-apply redesign (#287, about
atomicity not blocking), or unrelated drift issues; none proposes making
currency-check a hard PreToolUse/gate). **Still live: yes.** This is not a
simple omission — it's a live contradiction between what the user is now
demanding and what the codebase's own written design philosophy forbids, and
nobody has surfaced that tension to Ray for a ruling.

**Remedy**: file an issue naming the contradiction explicitly (item 10 vs.
CLAUDE.md's "kb-currency always exits 0" clause) and ask Ray (via
AskUserQuestion at the next natural checkpoint) whether he wants a genuine
PreToolUse/SessionStart hard-block, and if so, on which of the now-18 tracked
tools, and with what escape hatch for emergency work.

---

### 3. Item 5 ("clear-prep at 20%, both triggers, enforce smaller tasks") — ruled, nothing built, nothing tracked — cost_rank 3

**Claim**: Ray's directive: *"we need to start getting ready to run
`/clear-prep` once the context is at 20% (which right now is 200K tokens) ...
and we need to enforce smaller tasks that can fit into this token budget."*
Ray was asked and ruled explicitly: *"the `/clear-prep` trigger is BOTH,
whichever fires first. The session token budget... AND an estimate of the 1M
context window... Neither may be silently dropped for being harder to
measure."* As of right now, nothing implements either trigger proactively —
the closest thing is `session-review.js`'s `context` lane
(`session-review.js:233-241`), which is explicitly **retrospective**
("Find CONTEXT BLOWOUTS: which sessions exceeded the context target"), runs
only when the whole review workflow is manually invoked, and does not mention
the "both triggers, whichever fires first" ruling at all in its prompt text —
it just says "the context target" generically, singular. No GitHub issue
tracks building a live trigger or a task-size enforcement mechanism (search
for `context 20 percent|clear-prep 20%|both triggers|session token budget` and
a body-text scan for `smaller tasks|task decomposition|task size|bound.*task`
both return zero on-point hits — #218 is about total EAGER CONTEXT budget
[rules/CLAUDE.md loaded at session start], a different quantity from *running*
session token consumption). **Still live: yes.**

**Remedy**: file an issue specifically for a live (not retrospective) 20%
dual-trigger check, referencing the exact ruling text so it isn't re-litigated,
and a second issue (or the same one) for "enforce smaller tasks" — which needs
its own definition of done since "smaller" has no measured target yet.

---

### 4. Item 6's "the backup directory" is unresolved ambiguity nobody has asked Ray to disambiguate — cost_rank 4

**Claim**: Ray's directive: *"we ensure we dont lose any pending work on git
worktrees and/or branches of from the backup directory."* The directive's own
status table treats this as "worktrees + branches, not yet audited" and
silently drops "the backup directory" from its own restatement. `find
/Users/rmanaloto -maxdepth 2 -iname '*backup*'` (control arm: this glob is
NOT bounded to zero by construction — it found 8 real hits) surfaces at least
8 candidate backup locations on this machine unrelated to each other:
`~/backups`, `~/dev/backups`, `~/claude-backups`, `~/Auto-Claude/backups`,
`~/.omx/backups`, `~/.claude/backups`, `~/.claude-settings-backup-20260730-114036`,
`~/.gemini/antigravity-backup`. Spot-checking the two most likely
(`~/backups`, `~/dev/backups`) for anything named `knowledge-base` found
nothing (`find ... -iname '*knowledge-base*'` → empty). So there is no
obvious single "the backup directory" this repo's pending work could be
hiding in, and **nobody has asked Ray which one he means** — a direct miss of
`.claude/rules/clarify-before-acting.md`, which requires `AskUserQuestion` for
exactly this shape (ambiguous, hard-to-verify-you-got-it-right, and the cost of
guessing wrong is silently missed pending work). The new `pending-work` lane's
own prompt (`session-review.js:272-286`) inherits this gap by design: *"the
backup directory if the ALREADY SETTLED block names one"* — since nothing has
ever named one, this half of the lane's brief is structurally guaranteed to
never fire, silently, every run. **Still live: yes.**

**Remedy**: `AskUserQuestion` to Ray, next round: which directory (or is it a
Time Machine / cloud backup, not a local dir at all), and once answered, wire
it into the `pending-work` lane's inputs so it stops being a permanent no-op.

---

### 5. Item 7 (cold-takeover readiness) has zero coverage in the workflow built to answer this directive — cost_rank 5

**Claim**: Ray's directive: *"we need to ensure that all documentation and
code is in a state that if a subscription plan gets depleted a human and/or
another ai llm agent can take over understanding current state, pending
issues/tasks, gotchas, etc."* The directive's status table calls this "partly
true... but the handoff being gitignored directly undermines it" — i.e.
already flagged as incomplete. `grep -n -i "takeover|cold state|another
agent|human takes over|subscription|depleted"` over
`session-review.js` + `kb-session-review/SKILL.md` returns **zero matches** —
none of the 8 lanes' prompts asks anything resembling "would a fresh
human/agent, reading only committed docs, be able to reconstruct current
state, open issues, and known gotchas." This is a directive item that got a
named row in the status table and then no lane, no task, and no issue in the
very workflow purpose-built to turn directive items into checks. **Still
live: yes.**

**Remedy**: either fold this into the `forgotten` lane's own brief (it is, in
a sense, the most durable instance of "forgotten requirement" — a cold reader
losing the plot IS the failure mode this lane exists to catch) or add a ninth
lane whose prompt is literally "assume you are a fresh agent with only
committed files, no `.agent/`, no memory — what would you not be able to
reconstruct."

---

### 6. Item 8's "parallel where conflict-free" has a ranking but no batching input — cost_rank 6 (already partially known — see below)

**Claim**: Ray: *"we need to prioritize what issues to fix right away... if
possible fixing the issues in parallel if the chance of conflict is zero or
can be pre-planned."* The `Synthesise` phase (`session-review.js:459-528`)
does rank by "COST OF LEAVING IT UNFIXED" — the prioritization half is real.
But findings carry no file-path/module field (schema at
`session-review.js:326-350`: `claim`, `evidence`, `control_arm`, `cost_rank`,
`still_live`, `remedy` — no `files` or `touches` array), so "conflict-free
batches by disjoint file sets" literally has no input to compute from. **This
specific gap is already recorded** in the ALREADY_FOUND_DO_NOT_REDERIVE block
as A5 from the prior cold audit, so I am not claiming it as new — restating it
here only because it is the direct, still-unaddressed answer to a directive
line my lane is chartered to sweep, and it has no GitHub issue yet either
(none of the searches above surfaced one, and it is not in the "already a
GH issue" list at the top of this file). **Still live: yes, and untracked as
an issue as of this writing.**

**Remedy**: when A5 is turned into an issue (main agent's job, not mine to
duplicate), make sure the issue text explicitly cites item 8's wording so the
connection to Ray's directive is not lost a third time.

---

## GitHub repos touched

_None._ This lane read only local repo files, local `git`, and this repo's own
issue tracker via `gh`.

---

## COVERAGE

- **Reached and analysed**: `docs/direction/2026-08-18-ray-directives.md` in
  full (primary directive, status table, both rulings blocks, the addendum,
  the kb-arms answer, the clear-prep rulings section); `.agent/plans/session-
  2026-08-18-a.md` in full; `docs/direction/2026-08-17-ray-directives.md`
  (grepped for handoff/bot-review precedent — none found, confirming these are
  new to 08-18); `.claude/workflows/session-review.js` in full (584 lines,
  all 8 lane definitions plus the sweep/cross-check/synthesise phases);
  `.gitignore` (the `.agent/` line); `gh issue list` across ~125 open + ~203
  total issues, with both title-search and full-body `jq` searches for every
  directive item (handoff durability, currency-as-gate, 20%-trigger,
  worktree/backup, cold-takeover, conflict-free batching, rumdl/betterleaks/
  kingfisher/hk-builtin-workflow, bot-review dispositioning); one filesystem
  control-arm probe on candidate backup directories.
- **Opened but not finished analysing**: the addendum's currency-roster items
  (rumdl decision, gitleaks→betterleaks, kingfisher, the hk-builtin-review
  workflow) — confirmed via search that none has a GitHub issue yet, but I did
  NOT deep-dive whether this is itself "forgotten" vs. legitimately queued for
  next-session, because the handoff explicitly lists them under "Owed" and
  Ray's own clear-prep ruling says the CURRENT task is the session-review
  sweep first — so raising them as issues is plan, not omission, as of right
  now. Flagging only that nobody has filed them yet, in case that's still true
  when this report is read.
- **Never reached**: the actual JSONL transcript content of f1d1c0cf (per
  instructions, never read into context) — findings here are sourced entirely
  from durable artifacts (directive doc, handoff doc, workflow source, git,
  issue tracker), not from re-deriving what happened turn-by-turn in the
  session. I did not audit the `.claude/skills/kb-session-review/SKILL.md`
  wrapper file beyond one grep pass (checked it does not mention "20%"
  either) — a full read of that file was not performed. I did not check
  whether any of the OTHER three lane agents running in parallel with me
  (circles-breaker, plan-advisor, plan-auditor, workflow-scoper) are about to
  report the same findings under different names — no de-duplication attempted,
  per instructions to work independently.
