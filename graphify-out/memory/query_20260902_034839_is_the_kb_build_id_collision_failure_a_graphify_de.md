---
type: "query"
date: "2026-09-02T03:48:39.603327+00:00"
question: "Is the kb-build ID-collision failure a graphify defect that being 3 versions behind explains, so upgrading or rebasing the fork would fix it?"
contributor: "graphify"
outcome: "corrected"
correction: "Being N versions behind is not evidence that N versions forward contains the fix — and\n\"the tool is broken\" is the most expensive wrong first guess for a corpus failure.\n\nThree graphify releases (0.9.51, 0.9.52, 0.9.53) sat between our pin and upstream while\nthe build failed with an ID-collision warning. The natural inference — upgrade, or rebase\nthe fork, and see — was wrong, and cheap to refute: the dedup module, the shared extractor\nID helper and the merge regression test are **byte-identical** across v0.9.50..v0.9.53\n(`git diff --exit-code` rc 0), CONTROL-ARMED because the same probe on `cli.py` returns\nrc 1. The two ID changes in that range are extractor-local (Common Lisp, Robot Framework).\n\nThe real cause was local and free to fix: a stale AST cache directory still stamped\n`v0.9.48-s2` under an installed 0.9.50, holding 1,259 nodes minted under the REPO-ROOT\nanchor instead of the clone-root anchor every other node uses.\n\nTwo transferable rules:\n\n1. **Diff the specific module across the version range before proposing an upgrade as a\n   fix.** It costs one command and it is falsifiable; \"we are behind\" is not a diagnosis.\n2. **A version-stamped cache directory is a dated artifact — read its stamp.**\n   `graphify-out/cache/ast/v0.9.48-s2` under a 0.9.50 install named the whole problem, and\n   nothing was looking at it. When two artifacts disagree about provenance, the one with a\n   version in its NAME is the cheapest place to start.\n\nCorollary on delegation: the lane that did this research was excellent and still ranked\n\"rebase first\" above the local cause, because it was scoped to the release notes. A\nwell-executed lane answers the question asked; the caller still owns whether it was the\nright question.\n"
---

# Q: Is the kb-build ID-collision failure a graphify defect that being 3 versions behind explains, so upgrading or rebasing the fork would fix it?

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

- Signal: corrected
- Correction: Being N versions behind is not evidence that N versions forward contains the fix — and
"the tool is broken" is the most expensive wrong first guess for a corpus failure.

Three graphify releases (0.9.51, 0.9.52, 0.9.53) sat between our pin and upstream while
the build failed with an ID-collision warning. The natural inference — upgrade, or rebase
the fork, and see — was wrong, and cheap to refute: the dedup module, the shared extractor
ID helper and the merge regression test are **byte-identical** across v0.9.50..v0.9.53
(`git diff --exit-code` rc 0), CONTROL-ARMED because the same probe on `cli.py` returns
rc 1. The two ID changes in that range are extractor-local (Common Lisp, Robot Framework).

The real cause was local and free to fix: a stale AST cache directory still stamped
`v0.9.48-s2` under an installed 0.9.50, holding 1,259 nodes minted under the REPO-ROOT
anchor instead of the clone-root anchor every other node uses.

Two transferable rules:

1. **Diff the specific module across the version range before proposing an upgrade as a
   fix.** It costs one command and it is falsifiable; "we are behind" is not a diagnosis.
2. **A version-stamped cache directory is a dated artifact — read its stamp.**
   `graphify-out/cache/ast/v0.9.48-s2` under a 0.9.50 install named the whole problem, and
   nothing was looking at it. When two artifacts disagree about provenance, the one with a
   version in its NAME is the cheapest place to start.

Corollary on delegation: the lane that did this research was excellent and still ranked
"rebase first" above the local cause, because it was scoped to the release notes. A
well-executed lane answers the question asked; the caller still owns whether it was the
right question.
