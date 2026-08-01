---
type: "query"
date: "2026-07-31T23:29:08.239013+00:00"
question: "What is the recurring trap when a tracked upstream defect gets fixed?"
contributor: "graphify"
outcome: "useful"
---

# Q: What is the recurring trap when a tracked upstream defect gets fixed?

## Answer

The guard that worked around it starts reading as dead weight, and deleting it is the cheapest-looking move. Hit twice in one round. graphify 0.9.31 landed #2308 so the mcp<2 cap lifted — but the cap was load-bearing on 0.9.30, so the watch item was KEPT with its version condition rather than deleted, since its warning inverted rather than expired. mise 2026.7.18 #11491 added PATH dedup on the same surface as currency.sync.resolve_from_path/_is_mise_shim — but it collapses EXACT duplicates while this engine's founding defect was a DIFFERENT stale directory ordered ahead of the shims, and it explicitly leaves the live shell PATH untouched, which is where step 1 looks. A fix landing near your code is not a fix OF your code: check which mechanism it actually replaces.

## Outcome

- Signal: useful