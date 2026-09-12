---
type: "query"
date: "2026-09-12T20:52:10.058325+00:00"
question: "When a round's claims turn out false, where in its lifecycle did they actually break?"
contributor: "graphify"
outcome: "useful"
---

# Q: When a round's claims turn out false, where in its lifecycle did they actually break?

## Answer

A round can be scrupulously honest about its own limits and still ship false
statements — because the two happen at different moments.

Measured by a 7-lane cold review of session `3b921834` (2026-09-12). **38 of 41
re-derived truth claims held: 92.7%.** The interesting part is the split:

- **4 of 4 self-reported gaps were ACCURATE under cold re-test.** Where the round
  said "UNVERIFIED", "not re-run", "PARTIAL", it was telling the truth. Its
  handoff even hedged its own gate claim — *"treat as UNVERIFIED at HEAD, not as
  11/11"* — and that hedge was correct.
- **All 3 failed claims were TRUE WHEN WRITTEN** and became false, or lost their
  caveat, on the way into a summary.

The three, each a different shape of the same failure:

1. **An inherited number.** *"3 commits ahead of main"* was true at `cbd8827d` in
   the previous handoff and copied forward verbatim after two more commits landed.
   It was 5. Then 7. Then 9. Three wrong commit-distance numbers in one day.
2. **A dropped qualifier.** `next.origin` is "host-set and **unforgeable**" in the
   round's README; the lane that measured it had already written *"no adversarial
   transport-forgery arm was run, so 'unforgeable' remains UNVERIFIABLE beyond the
   exposed contract."* The caveat did not survive the trip into the summary.
3. **A caveat recorded everywhere except where it is read.** `session-audit-d-vague.md`
   died at a 2,400 s bound; three OTHER files say so and the file itself did not.

**The remedy is not more rigour at measurement time — measurement was fine.** It
is re-deriving a number or a qualifier AT THE MOMENT IT IS COPIED, not inheriting
it. A summary is where facts go to lose their conditions.

The sharpest instance is its inverse. The review lane hunting wrong facts graded a
citation `claude-code.d.ts:3841-3846` as "wrong by ~500 lines" and queued a
correction against FOUR tracked files. The citation was correct: the lane measured
the VENDORED 7,966-line file, the citation was to the GENERATED 9,156-line one,
and the +505-line offset it found is the distance between two files — the
signature of a correct citation to the other one. **A bare basename resolving
silently to the wrong copy**, committed by the lane whose whole job was catching
exactly that. A false correction applied to four correct citations costs more than
the uncorrected claim would have.


## Outcome

- Signal: useful