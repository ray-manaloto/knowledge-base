---
type: "query"
date: "2026-08-28T00:47:26.815907+00:00"
question: "what is the aggregated-research plugin for, and what is built first"
contributor: "graphify"
outcome: "useful"
---

# Q: what is the aggregated-research plugin for, and what is built first

## Answer

# What is the aggregated-research plugin FOR? — settled 2026-08-27, session kb-20260827.06

The plugin is THE SPINE: /deep-research's stage shape (scope → parallel search → dedup + budget → fetch/extract → 3-vote verify with a three-outcome tally → synthesize) and /antigravity:research's division of labour (Claude plans, verifies and writes; a cheap lane does the bulk reading), with this repo's source adapters plugged into the search stage and its control-arm discipline as the condition each null must satisfy. Tiered selection (cheap adapters always, expensive by question class). Two entry points: on demand first, a daily brief later — the brief only after a per-run token cap exists. It ships as a plugin for any of Ray's repos; a run produces a report, an artifact when the answer is a decision, graph ingest where a graph exists, a brief on schedule, and machine-readable structured output. Budget: /deep-research's constants as per-call defaults (angles 5, fetch 15, claims 25, votes 3). /deep-research itself is the shape only — it cannot tune model, effort or family. Vote independence is by SOURCE DOMAIN, not model family; agy is never a routine voter. The stage-1 record carries {url, date, snippet, kind, tier, null-with-arm}. Recency rule: prefer actively maintained tools, as a rank term.

Two side decisions: the Python→Rust binding to lychee-lib is to be BUILT (PyO3 0.29 + maturin 1.15, asyncio-native `await check()`, own repo after a declared spike) — second dispatch, with the exit criterion "name what subprocess + --format json cannot do"; and lychee is an hk linter here (`kb-links` network pass behind HK_PROFILE=links; an offline step in check/pre-commit that checks 0 links today).

First build, per the fable-advisor: the adapter contract + the gh-trackers adapter (jdx/hk's issues-disabled zero is the red-able fixture). Pages: docs/artifacts/what-is-aggregated-research-for.html, docs/artifacts/the-research-spine.html. Verbatim rulings: docs/direction/2026-08-27-ray-directives.md. Advisor report: .agent/kb/reports/agents/advisor-spine.md.


## Outcome

- Signal: useful