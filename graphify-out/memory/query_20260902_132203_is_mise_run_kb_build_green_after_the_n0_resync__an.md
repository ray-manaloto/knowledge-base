---
type: "query"
date: "2026-09-02T13:22:03.118067+00:00"
question: "Is mise run kb-build green after the N0 resync, and what did it take?"
contributor: "graphify"
outcome: "useful"
---

# Q: Is mise run kb-build green after the N0 resync, and what did it take?

## Answer

`mise run kb-build` is GREEN as of 2026-09-02: rc=0, 359,026 nodes / 806,869 edges /
484 hyperedges, 0 dangling, 0 malformed, stamped `built by graphify 0.9.53`, receipt
written. First green build in weeks. It took ELEVEN runs, and the composition of those
eleven is the finding.

FOUR were genuine problems: 12 clones holding root-anchored stale sub-graphs; `--force`
silently going incremental on 64 warm sub-graphs (upstream, fixed by 0.9.51 `ae074b2`);
8 sources with real properties that cannot be ingested today; 3 registerable or
mislabelled ones.

THREE were OUR OWN GATES BEING WRONG, and none was findable until the build got far
enough to execute them:

1. `graph._run` refused routine merge narration (`Replaced N node(s) from re-extracted
   source file(s)`) that `graphify_health._ROUTINE_MERGE_PROGRESS` had classified as
   routine since 2026-08-27. The same line was approved on one path and fatal on
   another; on a COLD rebuild every source is re-extracted, so the fatal path is the
   one that fires.
2. `graphify_ops.label` refused `no LLM backend configured` — the configuration
   `do-not.md` #4 REQUIRES, and which the function's own comment two lines below calls
   "the clean default". The build failed for being configured correctly.
3. `_write_build_receipt` demanded a top-level `edges` key. `graph_counts.py`'s own
   comment states "there is no `edges` key on any graphify graph" — the format is
   node-link JSON, so edges are `links` and hyperedges sit under `graph`. **It could
   never have passed and never had.**

All three now share one filter / one accessor rather than each carrying its own copy,
and each is armed in both directions.

Also filed #655: `kb-artifacts`' callflow generator writes its 486 KB HTML and THEN
exits non-zero — reproduced in isolation, and checked (not assumed) to be a different
class from the three above: `assess` recorded `nonzero-returncode`, not a stderr
complaint.


## Outcome

- Signal: useful