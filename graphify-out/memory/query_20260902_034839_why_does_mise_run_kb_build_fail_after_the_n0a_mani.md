---
type: "query"
date: "2026-09-02T03:48:39.302823+00:00"
question: "Why does mise run kb-build fail after the N0a manifest resync, and is it either of the two known causes?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why does mise run kb-build fail after the N0a manifest resync, and is it either of the two known causes?

## Answer

# N0c — why `mise run kb-build` fails, measured 2026-09-01

The build fails rc 1 at source **8 of 88** (`anthropic-sdk-python`),
`failed_at 2026-09-02T03:02:42.976018+00:00`, recorded in
`graphify-out/.build-failure.json`. No currency stamp written — correct fail-closed.
The aggregate was NOT damaged: 499,116 nodes / 1,164,181 edges, unchanged from N0b.

## The cause is a THIRD one, and it is a stale local anchor — not a tool defect

~11,990 `node '<id>' is minted by two different files` warnings, all naming
`anthropic-sdk-python`: keeping `sources/anthropic-sdk-python/<p>`, discarding bare `<p>`.
Unaccounted stderr, so `require_complete` (`python/src/kb_setup/graphify_health.py:500`)
fails the build closed. That fail-closed behaviour is correct and must not be suppressed.

Two anchors coexist:

- the per-source extract is CORRECT — `.graphify_root` = `.../sources/anthropic-sdk-python`,
  cache dir `v0.9.50-s2`, graph holds only BARE paths (543 `src/`, 146 `tests/`,
  2 `examples/`; control 704 values total, 0 prefixed);
- the aggregate is CONTAMINATED — `graphify-out/cache/ast/` holds ONLY `v0.9.48-s2`,
  stamped **0.9.48** while the installed tool is **0.9.50**. Written when this repo ran
  0.9.48 anchored at the REPO ROOT, so those entries read `sources/<name>/...`;
- measured contamination: **1,259 of 1,664,265** aggregate `source_file` values (0.076%)
  are `sources/`-prefixed; every other node is clone-root-anchored.
  Control: the same probe returns the 1,664,265 total, so it fires.

This is the same shape as upstream issue #2259, whose reporter established the cause was
inconsistent working-directory / cache anchors and converged after clearing the stale one.

## What else the run settled

- **#397's stated symptom is RESOLVED.** Its failure was `detect failed closed;
  unclassified-files; unresolved(3)=[Brewfile, examples/.keep, src/anthropic/lib/.keep]`
  under `ref = main`. N0a re-pinned to `ref = v1.3.0` /
  `370ee927ca8a8d3b5d4f907555e890b2df685786`; detect now PASSES. Criteria 4 and 5 met.
  Criteria 1-3 NOT met: re-measured **68 of 97 manifests (70%)** still pin a moving ref,
  against the issue's original 52/73 (71%) — ratio unchanged, corpus grew. Commented and
  RETITLED; stays OPEN.
- **The 2026-08-31 cause was never reached** — `biome` sorts after `anthropic-sdk-python`.
  Untested, neither fixed nor refuted.
- **The aggregate stores clone-root-relative `source_file` with NO source namespace** —
  top prefixes `crates/` 328,891, `codex-rs/` 316,264, `tests/` 218,153, `src/` 193,068.
  Two sources' `tests/x.py` are indistinguishable, so this collision class is latent
  corpus-wide. Confirmed by design: `prefix_graph_for_global()` namespaces node IDs but
  deliberately does not rewrite `source_file`.


## Outcome

- Signal: useful