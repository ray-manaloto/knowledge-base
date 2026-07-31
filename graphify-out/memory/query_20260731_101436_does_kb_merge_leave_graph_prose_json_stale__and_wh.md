---
type: "query"
date: "2026-07-31T10:14:36.059410+00:00"
question: "Does kb-merge leave graph-prose.json stale, and which other tasks write graph.json?"
contributor: "graphify"
outcome: "corrected"
correction: "The earlier entry said the fix was 'make kb-merge call prose.derive_for like build() does'. That was necessary and not sufficient — it named one of two writers."
---

# Q: Does kb-merge leave graph-prose.json stale, and which other tasks write graph.json?

## Answer

FIXED 2026-07-31 (PR #95). kb-merge left graph-prose.json stale — but so did kb-label, and that half was the one that mattered: graphify label is NOT a sidecar-only write. Verified in installed 0.9.30: graphify/cli.py:1546 selects the label branch and it runs unbroken (no intervening elif cmd) to to_json(G, communities, str(out/'graph.json')) at :1830. The documented ingestion order is merge -> label, so fixing merge alone would have been undone by the very next workflow step, invisibly. Every task that writes graph.json now re-derives the prose graph (kb-build already did; kb-merge and kb-label now do), each gated on its own rc so a failed operation cannot replace a valid prose graph. prose.derive also went atomic: unlink first (fail-closed, unchanged) then mkstemp + replace, because kb-query --prose checks only .is_file() before handing the path to graphify. The temp name must be mkstemp and not <out>.tmp — a fixed name is the same path for every caller, trading a torn read for a torn write.

## Outcome

- Signal: corrected
- Correction: The earlier entry said the fix was 'make kb-merge call prose.derive_for like build() does'. That was necessary and not sufficient — it named one of two writers.