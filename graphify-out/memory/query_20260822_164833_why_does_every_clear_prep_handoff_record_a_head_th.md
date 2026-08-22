---
type: "query"
date: "2026-08-22T16:48:33.358292+00:00"
question: "Why does every clear-prep handoff record a HEAD that is one commit stale?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why does every clear-prep handoff record a HEAD that is one commit stale?

## Answer

BY CONSTRUCTION, every round, and nothing was looking.

`/clear-prep` step 1 reads HEAD, step 4b writes it into the handoff's lead, and
step 5 then commits step 2's `kb-remember` output. So the recorded HEAD is that
commit's PARENT — not occasionally, always. Two handoffs in a row were read
against a repo that had already moved, and `/kb-resume` had to re-derive the
branch state by hand both times.

It survived because it LOOKS like a chicken-and-egg problem. It is not:
`.agent/` is gitignored, so the handoff is never committed and can be corrected
freely after the commit. There was no ordering paradox, only a missing step.

`kb-handoff-check` could not catch it: it had five checks — paths, gates,
receipts, PRs, issues — and none of them was about the handoff's own HEAD.

Fixed in 870c020c: the skill re-pins after committing, and a sixth check grades
the claim. CURRENT -> OK, CLOSING_COMMITS -> AMBIG, STALE -> FAIL,
NOT_ANCESTOR -> UNVER, UNKNOWN_COMMIT -> FAIL, UNREADABLE -> UNVER.

Two judgement calls, stated because a later reader will want to tighten both.
A handoff behind by ONLY `review.EXEMPT_PATHS` is AMBIG rather than FAIL:
blocking a ship over a `kb-remember` file is how a check gets routed around.
Post-squash-merge is UNVER rather than FAIL: that is the healthy end state, and
grading it wrong trains people to ignore the row.

Arms `.agent/kb/arms/handoff-head-claim.toml`: 9/9 died, 1/1 control held.


## Outcome

- Signal: useful