---
type: "query"
date: "2026-08-17T18:53:25.714838+00:00"
question: "Does a merge path exist for the graphify semantic corpus, and can it be proven on one chunk?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does a merge path exist for the graphify semantic corpus, and can it be proven on one chunk?

## Answer

The 2026-08-17 (e) round set out to prove a merge path for the graphify deep
extraction on ONE chunk before spending on 58. The merge path did not exist, and
three defects sat between the plan and any staged chunk. All three were found
without spending a provider call, by probing the real fragment an earlier
semantic-SLICE run had already left on disk.

1. `chunks.assemble` keyed its cross-chunk id-collision gate on the chunk's
   BASENAME. Every staged corpus chunk is named `semantic-fragment.json`, so all
   58 shared one label and the gate could not fire. Measured on the realistic
   shape (shared node id, different `source_file`s, distinct hyperedge ids):
   identical basenames assembled CLEAN with 26 nodes and 13 unreported duplicate
   ids; distinct basenames were refused with all 13. Fixed by keying on the
   resolved path. 6/6 arms.

2. Nothing in the semantic pipeline emits `_origin`. `normalize_fragment` admits
   `None` and the adapter never sets it, so every staged node would merge as
   `_origin=None`, which graphify 0.9.32+ reads as AST and drops from
   `graph-prose.json` — the 629-lost-nodes class. The new merge step stamps
   `semantic` on nodes only, matching the committed convention (796/796 nodes
   `semantic`, 1099/1099 edges `None`). 14/14 arms.

3. `execute` passed its `tempfile` evidence directory UNRESOLVED. The provider
   boundary marker is opened with `O_NOFOLLOW`, and `$TMPDIR` on macOS is
   `/var/folders/…` where `/var` is a symlink — so the marker was refused and the
   run failed 58 of 58 chunks before any model was called. It cost nothing to
   find because the marker precedes the invocation. Invisible until now because
   the SLICE writes its evidence in-repo, and the slice was the only path that had
   ever run. 6/6 arms.

Then the first real provider call exposed a fourth: `timeout_seconds = 120`
against a measured 659.5 s for one median chunk — off by ~5.5x — AND a hardcoded
`timeout=120` twin in the adapter reachable from no configuration, so raising the
config alone would only have moved which limit killed the call (#335). Collapsed
to one number with two consumers; Ray authorized 900 s.

The corpus run is now blocked on one decision, not on a defect:
`max_output_tokens = 8192` against a measured 31,887-token need, confirmed by the
API's own words: "Claude's response exceeded the 8192 output token maximum."


## Outcome

- Signal: useful