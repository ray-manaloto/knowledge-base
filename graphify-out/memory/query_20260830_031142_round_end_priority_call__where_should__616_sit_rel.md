---
type: "query"
date: "2026-08-30T03:11:42.770852+00:00"
question: "Round-end priority call: where should #616 sit relative to the aggregated-research build chain?"
contributor: "graphify"
outcome: "useful"
---

# Q: Round-end priority call: where should #616 sit relative to the aggregated-research build chain?

## Answer

Ray deprioritized #616 (the cold-review CLI invocation wrapper + its
unresolved 3-way deny-hook-scope fork) below the entire aggregated-research
build chain (#578 links -> #579 packages -> #580 codesearch -> #581/#582
breadth -> #583 report -> #584 lane contract -> #585/#586 spine -> #587/#588
packaging -> #589 definition of done). Moved the #616 entry from the top of
docs/roadmap/aggregated-research-chain.toml to the bottom, with a dated
comment recording the reason, so next-ticket surfaces #578 next rather than
#616. #616's three-option deny-hook-scope fork (review-only best-effort,
full blanket deny, wrapper-only-hold-the-deny) remains unresolved and
unchosen — it was not decided, only deferred.


## Outcome

- Signal: useful