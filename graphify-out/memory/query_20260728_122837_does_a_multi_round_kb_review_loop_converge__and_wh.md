---
type: "query"
date: "2026-07-28T12:28:37.948371+00:00"
question: "Does a multi-round kb-review loop converge, and what makes it stop?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does a multi-round kb-review loop converge, and what makes it stop?

## Answer

It converged this time: 19 findings / 4 blocking in round 1, 9 / 0 in round 2, 3 / 0 in round 3, 1 / 0 on the closing verification pass. The prior branch ran five rounds with a blocking gate hole in four of them. Two things differed. First, an agreed stop rule set BEFORE round 1 (full round 2, cold-only round 3, hard stop, non-blocking findings become issues) — without it the tail is unbounded, because a fix breeds the next round's finding almost every time. Second, mutating my OWN fixes each round rather than only running the lanes: that found two tests of mine that could not fail (a (+N more) bound test that agreed with rev-list order whether or not the sort existed, and a UnicodeDecodeError catch with no test at all) which no lane reported. The stop rule then has a cost that must be named rather than hidden: fixing round 3's findings moves HEAD past the reviewed SHA, so the receipt records less than full coverage and the skip reasons must say exactly which SHA each lane last read.

## Outcome

- Signal: useful