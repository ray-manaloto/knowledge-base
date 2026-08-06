---
type: "query"
date: "2026-08-06T08:23:56.557730+00:00"
question: "Why was a cross-chunk collision gate wrong at the kb-merge door but right at kb-build?"
contributor: "graphify"
outcome: "corrected"
---

# Q: Why was a cross-chunk collision gate wrong at the kb-merge door but right at kb-build?

## Answer

Ownership at a LONE kb-merge is not ownership at a full replay, and conflating
them made the gate wrong in the destructive direction. build_merge prunes on the
INCOMING chunk's claims unconditionally (build.py:1531-1537), so whatever is
being merged wins regardless of its capture date — while kb-build replays
everything and the last chunk wins. Ranking by replay order at the merge door
reported the exact destructive case as CLEAN: re-merging an OLDER committed
chunk over a newer sibling that had legitimately declared the shared file. 21
mutation arms were green over it, because every one was faithfully mutating a
correct implementation of the WRONG RULE. Mutation arms measure the tests; they
cannot measure the premise. Found by the cold cross-family lane, round 1, P1.

## Outcome

- Signal: corrected