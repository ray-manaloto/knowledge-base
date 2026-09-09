---
type: "query"
date: "2026-09-09T02:46:57.452605+00:00"
question: "Why was kb-session-reflect dropped five rounds running, and what actually fixes it?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why was kb-session-reflect dropped five rounds running, and what actually fixes it?

## Answer

The session self-reflection was never unrun — it was computed and thrown away.

`.claude/settings.json` runs `mise run kb-session-reflect -- --quiet` at
SessionEnd, every session (confirmed by parsing the hook table, not by grep).
`--quiet` computed the FULL report, printed two counts, and discarded it. Every
expensive part already paid for, at the one moment no reader is left. Issue #717
was written as though the step never runs.

FIXED (PR #718, merged as a0b70c71): the report is kept at
`.agent/kb/reflect/<session>.md`, `mise run kb-session-reflect -- --last` prints
the newest, and `/session-resume` reads it as a new step 2a at the START of the
next session on full budget. Removed from `/clear-prep`, which is where it died
five rounds running.

`persist()` REFUSES rather than inventing a filename when no session was
recorded; `--last` says "no kept reflection yet … this is NOT 'the last session
had no findings'" in words rather than printing nothing.

WHY NOT THE TICKET'S OWN FIX. It proposed rendering the report on
`kb-context`'s over-threshold branch. `kb-context` is itself only ever run late.
Measured over 21 days of transcripts via `mise run kb-session-search`, filtered
to `location: tool_input` + `tool_name: Bash` — real invocations, not prose
mentions (control: 102 message-location hits excluded, which include the
session's own prose quoting the command):

  30 real invocations across 18 sessions
  median first invocation ~ ordinal 300
  the two known dropped rounds: 316 and 387
  exactly 1 session of 18 called it before ordinal 100

So that moves which command prints the report, not when anyone reads it.

The advisor's measurement also killed the ticket's other fix on better evidence
than the issue body carries: of the 39 `.agent/plans` ad-hoc scripts, ZERO
compose a new handoff — all 39 patch an existing one, up to six successive
patches of one file in one session, 38/39 via `.replace()`. That is the Edit
tool's exact semantics, already shipped by the harness.

NOT ESTABLISHED: that reading the report at resume time actually changes a
future round's behaviour. That is a claim about people; no mutation settles it.


## Outcome

- Signal: useful