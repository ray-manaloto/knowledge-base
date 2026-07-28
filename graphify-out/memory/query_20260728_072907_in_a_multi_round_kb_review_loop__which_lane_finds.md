---
type: "query"
date: "2026-07-28T07:29:07.415871+00:00"
question: "In a multi-round kb-review loop, which lane finds the defects and does a fix introduce the next one?"
contributor: "graphify"
outcome: "useful"
---

# Q: In a multi-round kb-review loop, which lane finds the defects and does a fix introduce the next one?

## Answer

Measured over three rounds on one branch (PR #61): round 1 = 18 findings / 2 blocking, round 2 = 8 / 2, round 3 (cold only) = 1 / 0. BOTH blocking findings in rounds 1 and 2 came from the two lanes OUTSIDE the Standards/Spec spine — the cold cross-family lane and silent-failure — never from the spine, and always in code whose unit tests were green. A FIX INTRODUCED THE NEXT ROUND'S FINDING EVERY TIME: round 1's render fix left the sibling control-arm states invisible (round 2 F1); round 2's F1 fix left the summary loop unscoped (round 3 P2) and its first attempt dumped a 4KB guard table. Two tests I wrote actively PINNED defects — one asserted a healthy control arm printed nothing, locking in the collapse the next round found. Agree the stop rule BEFORE round 1, not after: the rule used here was full-round-2 then cold-only-round-3, hard stop, non-blocking to issues. Also: two independent agents leaked live credentials to a terminal within minutes of each other by printing the VALUES of three shell variables (an Exa API key and two GitHub PATs) rather than their names, counts and lengths, so constrain that explicitly in lane prompts. The values are deliberately NOT recorded here: an earlier version of this file pasted the probe output verbatim, which put three live secrets into a tracked file in a PUBLIC repo — a note ABOUT a credential leak that was itself one. It was caught pre-push by three review lanes at once, and by no scanner, because .gitleaks.toml allowlisted all of graphify-out/ on the false premise that none of it is committed, so constrain that explicitly in lane prompts.

## Outcome

- Signal: useful