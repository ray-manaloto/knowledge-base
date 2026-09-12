---
type: "query"
date: "2026-09-12T12:34:16.119798+00:00"
question: "How do you detect a stale row in the ticket chain, and what must a removal NOT touch?"
contributor: "graphify"
outcome: "useful"
---

# Q: How do you detect a stale row in the ticket chain, and what must a removal NOT touch?

## Answer

A stale row in `docs/roadmap/aggregated-research-chain.toml` is INVISIBLE until
the row above it closes, because `next-ticket` reports the FIRST ticket whose
blockers are all closed and stops there.

#755 closed with #774 and its row was left behind. `next-ticket` kept reporting
`READY — #754` and looked perfectly healthy. The failure was queued, not absent.

**The arm that made it visible: remove the row ABOVE it on a scratch copy.**

  before the fix, #754's row removed -> STALE CHAIN — #755 ... is CLOSED but
                                        still listed; REFUSES to name a next ticket
  after  the fix, #754's row removed -> READY — #758 G05

and #758 is exactly what the stale report itself predicted under "next after
removal". Today, unchanged either way: READY — #754.

Generalises past this file: **for any ordered list whose consumer short-circuits
at the first match, a defect below the match is unobservable.** Reading the file
cannot find it. Deleting the entries above it is the probe.

Second durable half — EDGES ARE NOT THE ROW. Dropping a closed ticket's
`[[ticket]]` block must NOT drop that issue from other rows' `blockers` lists.
The file header permits a blocker with no ticket entry, a CLOSED blocker resolves
as satisfied, and the dependent issues still name it under "Depends on" in their
live bodies. #769's first version deleted the edges and was refuted by cold
review; this change kept all five and said so.

Third: when a ticket's own body contradicts the dependency its content implies
(#773 said "Blocked on: nothing" while every acceptance item needed the mod
registered), encode the SAFE direction in the chain — a wrong blocker only
defers a ticket, whereas a missing one sends a session to acceptance criteria it
cannot exercise — then correct the issue body so the two records agree.


## Outcome

- Signal: useful