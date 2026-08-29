---
type: "query"
date: "2026-08-29T21:41:27.592247+00:00"
question: "How should #605's codex-docs registration be scoped and verified?"
contributor: "graphify"
outcome: "useful"
---

# Q: How should #605's codex-docs registration be scoped and verified?

## Answer

Registered chenrui333/codex-docs (sources/codex-docs.manifest, pinned a7412e5e868c)
as the replacement for agent-harness-docs's docs/codex/ tier. Confirmed strict
superset via live README comparison. New source clones cleanly at the pinned SHA;
kb-build's aggregate failure was the pre-existing, unrelated #397/#1666 issue.
Cold review (antigravity) found 2 real findings (both provenance/consistency,
not code-correctness): stale "proposed" language in REGISTRY row 152 contradicting
the settled-fact manifests, and an uncitable personal attribution inconsistent
with the sibling manifest's pattern. Both fixed and re-verified. Shipped as PR #612,
landed on main.


## Outcome

- Signal: useful