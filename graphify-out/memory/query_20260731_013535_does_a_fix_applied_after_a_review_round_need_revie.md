---
type: "query"
date: "2026-07-31T01:35:35.754320+00:00"
question: "Does a fix applied after a review round need reviewing as hard as the original code?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does a fix applied after a review round need reviewing as hard as the original code?

## Answer

Yes — measured on PR #91. Round 1 flagged an unserialized claim step; my fix said 're-read the assignees and stand down if someone else is on it'. Round 2 found that fix is a no-op: a solo repo resolves every session's @me to the SAME account, so the field looks identical whether or not a race happened. The mitigation READ like a control and could not discriminate. Same round, a second case: round 1 fixed a silent truncation at gh's default 30 by passing --limit 200, which truncates silently at 200 — raising a bound is not removing it. Both defects were introduced BY the fix round, in code that then passed lint/test/lint-docs green. Corollary for kb-review's two-round bound: round 2 earns its place precisely because it reads the fixes, not the original.

## Outcome

- Signal: useful