---
type: "query"
date: "2026-08-06T08:23:56.183307+00:00"
question: "Why did graphify's own #479 shrink guard stay silent while a merge destroyed 72 nodes?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why did graphify's own #479 shrink guard stay silent while a merge destroyed 72 nodes?

## Answer

It cannot see it, structurally. build_merge REASSIGNS existing_nodes to the
post-prune list (build.py:1536) before the #479 guard compares
len(existing_nodes) against the new count (:1650) — so a supersession is
subtracted from BOTH sides of the inequality that exists to catch it. Measured
against 0.9.34 (current on PyPI): a chunk destroyed 72 nodes of an unrelated
source with the guard active and silent. Filed upstream as
Graphify-Labs/graphify#2497. The lesson generalises: when a tool's safety check
has been silent through a real incident, read whether it COULD have fired
before assuming it did not apply.

## Outcome

- Signal: useful