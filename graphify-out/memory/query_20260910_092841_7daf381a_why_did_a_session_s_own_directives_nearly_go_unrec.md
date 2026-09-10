---
type: "query"
date: "2026-09-10T09:28:41.579340+00:00"
question: "Why did a session's own directives nearly go unrecorded, and what did a review of it miss?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why did a session's own directives nearly go unrecorded, and what did a review of it miss?

## Answer

Four of nine of Ray's instructions in one session arrived as `queued_command`
attachments, NOT as message content — and a review reading only message text
plus `AskUserQuestion` answers found ZERO of them.

Missed: the `zero agent work / one command` directive, the aitmpl review ask,
`we need to start actually using github as a source of information`, and `file
the graphify issue / only after due dilligence`. Two of those are standing
rulings, not one-off asks. Filed as knowledge-base #747.

It is the same shape as every other finding here — a probe that can only return
one kind of answer — except the bound is the RECORD TYPE rather than a
`-maxdepth` or a token spelling. Both routes are needed; neither is complete.

The consequence nearly cost the whole round: NONE of that day's directives was
recorded anywhere tracked. A grep for "function hooks" across `docs/`,
`.claude/` and `python/` returned 2 hits, both false positives inside vendored
`sources/**` (control arm, same shape: `kb-recall-work` -> 5 tracked files).
Every directive had been ACTED ON and none written down; there was no
`docs/direction/2026-09-10-ray-directives.md` at all until a loss audit asked.

Second-order finding: the scratchpad is SHARED across lanes, not per-lane. One
lane overwrote another's `prompt.md` (31,794 -> 5,552 bytes) and wrote its own
`verdict.md`, which the first lane read as its own for a turn before the
timestamps gave it away. Use lane-unique filenames.

The generalised lesson: when auditing what a session was ASKED, enumerate the
routes an instruction can arrive by and prove each returns rows, before
believing any count of them.


## Outcome

- Signal: useful