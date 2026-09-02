---
type: "query"
date: "2026-09-02T06:10:05.809732+00:00"
question: "Why does mise run kb-build fail with ~11,990 minted-by-two-different-files warnings, and does upgrading graphify fix it?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why does mise run kb-build fail with ~11,990 minted-by-two-different-files warnings, and does upgrading graphify fix it?

## Answer

The build failed with ~11,990 `node '<id>' is minted by two different files` warnings.

ROOT CAUSE (measured, session kb-20260901.005): twelve source clones carried a stale
sub-graph INSIDE their own `graphify-out/`, written anchored at the REPO ROOT, so ids
from the fresh clone-anchored extract collided with root-anchored survivors. Purging
those twelve took the collision count to 0 and it stayed 0 on a fully cold rebuild.

For `awesome-claude-code` the carrier was a DATED snapshot
(`graphify-out/2026-09-01/graph.json`, 1,283 of 1,307 values root-anchored) while its
top-level `graph.json` was clean — a check that reads only the top-level file misses it.

Why it survived `--force`: on the pinned 0.9.50, `--force --code-only` silently reverts
to incremental when a warm sub-graph is present. Fixed upstream in 0.9.51 (`ae074b2`,
#3125). 64 of 100 clones held such warm sub-graphs, so kb-build's reproducibility
guarantee did not hold for any of them.

The complete remaining failure set, measured in ONE pass by the new
`mise run kb-extract-census`: 76 of 87 sources clean, 11 blocked, 321 syntax-error
files and 71 distinct colliding ids. A collision CANNOT be registered as expected —
only deferred — because the sole collision approver covers same-FILE notes.

Rebasing the fork onto v0.9.53 does NOT shrink that list: across a sample covering 70
of the 71 collisions and 320 of the 321 syntax files, exactly one figure improved
(`nativ` 2 -> 1). The upgrade is still worth taking for `ae074b2`.

Filed: #653 (the stale sub-graphs + a guard), #654 (biome).


## Outcome

- Signal: useful