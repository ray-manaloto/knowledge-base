---
type: "query"
date: "2026-08-03T19:22:03.699197+00:00"
question: "After mise run kb-land, what branch am I on — and what breaks if I do not check?"
contributor: "graphify"
outcome: "useful"
---

# Q: After mise run kb-land, what branch am I on — and what breaks if I do not check?

## Answer

MAIN. kb-land squash-merges and then SYNCS MAIN, so it leaves the session checked out on main. Any work continuing after a land commits there. Happened 2026-08-03: three commits went straight onto main after PR #136 merged, violating do-not.md #7 ('Do NOT commit onto the default branch — branch FIRST'), recovered only because nothing was pushed — the exact caveat that rule already records from the sibling repo's 34-file incident. Fix is lossless: git branch <new> HEAD; git checkout <new>; git branch -f main origin/main. THE RULE DID NOT PREVENT IT because nothing asked the question — do-not.md #7 was eagerly in context the whole time, but I never re-read the branch after kb-land so it had no trigger. Same shape as a-validator-nothing-calls-is-not-a-gate: the mechanism existed and nothing exercised it. This is a SEAM defect in the land->next-task transition, not a slip: every session that lands a PR and keeps working walks into it. A kb-land that printed 'you are on main — branch before continuing' would close it.

## Outcome

- Signal: useful