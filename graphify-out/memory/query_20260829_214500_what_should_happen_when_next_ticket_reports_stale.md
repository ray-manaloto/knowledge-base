---
type: "query"
date: "2026-08-29T21:45:00.281284+00:00"
question: "What should happen when next-ticket reports STALE CHAIN?"
contributor: "graphify"
outcome: "useful"
---

# Q: What should happen when next-ticket reports STALE CHAIN?

## Answer

next-ticket reported STALE CHAIN: #605 was closed on GitHub (auto-closed via
the Closes trailer on PR #612) but still listed in
docs/roadmap/aggregated-research-chain.toml. Removed the [[ticket]] block per
the tool's documented contract (done tickets are removed in the closing
commit, not inferred from tracker state). Re-run confirmed #573 is next,
READY, no blockers. Cold review (codex) found nothing wrong with the TOML
edit — array-of-tables boundary intact, no dangling references to 605.


## Outcome

- Signal: useful