---
type: "query"
date: "2026-09-02T13:22:03.408864+00:00"
question: "Were this repo's own build gates trustworthy while the build was failing?"
contributor: "graphify"
outcome: "corrected"
correction: "A GATE THAT HAS NEVER RUN IS NOT A GATE — it is decoration that reads as coverage.\n\nThree gates in one codebase were wrong simultaneously, and all three had looked green\nfor as long as the build failed upstream of them. `_write_build_receipt` is the\nsharpest: it demanded a JSON key that another module in the same repo states in its own\ncomment does not exist on any graphify graph. It had never once validated anything, and\nits greenness was purely an artefact of never being reached.\n\nThe generalisation: `probes-need-a-control-arm.md` says arm the FAIL direction of any\ngate you add. This round adds the other half — **a gate downstream of a failing step is\nUNARMED IN BOTH DIRECTIONS**, because it has never executed at all. When a long-broken\npipeline is repaired, every check downstream of the old failure point is new code from\nthe perspective of evidence, however old it is in the file. Expect them to fail, and\nread each failure as \"this gate is running for the first time\", not \"the fix broke\nsomething\".\n\nCorollary measured the same round: the harness completion notification reported\n\"exit code 0\" on ELEVEN failing runs. The log is the only honest source.\n"
---

# Q: Were this repo's own build gates trustworthy while the build was failing?

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

- Signal: corrected
- Correction: A GATE THAT HAS NEVER RUN IS NOT A GATE — it is decoration that reads as coverage.

Three gates in one codebase were wrong simultaneously, and all three had looked green
for as long as the build failed upstream of them. `_write_build_receipt` is the
sharpest: it demanded a JSON key that another module in the same repo states in its own
comment does not exist on any graphify graph. It had never once validated anything, and
its greenness was purely an artefact of never being reached.

The generalisation: `probes-need-a-control-arm.md` says arm the FAIL direction of any
gate you add. This round adds the other half — **a gate downstream of a failing step is
UNARMED IN BOTH DIRECTIONS**, because it has never executed at all. When a long-broken
pipeline is repaired, every check downstream of the old failure point is new code from
the perspective of evidence, however old it is in the file. Expect them to fail, and
read each failure as "this gate is running for the first time", not "the fix broke
something".

Corollary measured the same round: the harness completion notification reported
"exit code 0" on ELEVEN failing runs. The log is the only honest source.
