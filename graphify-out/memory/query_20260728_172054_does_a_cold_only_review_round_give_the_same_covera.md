---
type: "query"
date: "2026-07-28T17:20:54.984827+00:00"
question: "Does a cold-only review round give the same coverage as all four lanes?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does a cold-only review round give the same coverage as all four lanes?

## Answer

No, and the gap is blocking-sized. In #67's round 3 the cold lane returned 0 blocking and 0 P1 on d3e054b while standards and silent-failure, run on the SAME SHA purely so the review receipt would be literally true, found TWO blocking defects — both of them round-2 fixes whose tests could not observe them. Cold reviews by reading; the two that found them worked by MUTATING the code and watching whether a test reddened. Across five rounds, three separate tests of mine were weaker than their names claimed, and a lane caught each one by mutation, never by reading. Treat 'cold came back clean' as one lens reporting, not as convergence.

## Outcome

- Signal: useful