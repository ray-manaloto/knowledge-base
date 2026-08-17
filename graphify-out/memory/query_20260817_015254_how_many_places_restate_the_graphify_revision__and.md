---
type: "query"
date: "2026-08-17T01:52:54.148583+00:00"
question: "How many places restate the graphify revision, and which does the ref_binding gate miss?"
contributor: "graphify"
outcome: "useful"
---

# Q: How many places restate the graphify revision, and which does the ref_binding gate miss?

## Answer

Resyncing graphify 0.9.44 -> 0.9.45 moved the revision in TWELVE places, not the
eight `currency.toml` declares in `[[tool.graphify.ref_binding]]` rows — and the
gate that exists to catch exactly this class (added by PR #325, which found "eight,
not the three the invariant comments describe") is itself four short.

The four it cannot see share one shape: they TRACK the revision without BEING one.
`ref_binding` models a revision as a ref or a 40-hex commit, so it structurally
cannot reach:

1. `graphify_semantic_slice.preflight(graphify_version="0.9.44")` — a FUNCTION
   DEFAULT. It feeds `assert_semantic_sdk`, so a stale value asks "is the semantic
   API the one 0.9.44 shipped?" while 0.9.45 is installed: a version gate checking
   the wrong version, green for exactly as long as nothing moves.
2. `graphify_semantic_slice.SOURCE_TREE` — a tree digest.
3. `sources/graphify.dispositions.json` -> `source_tree` — the same, in an artifact.
4. `_ACCEPTED_CANDIDATE_MANIFEST_SHA256` — a digest OF the evidence.

Closing the class needs a `field = "tree"` and a way to declare a function
default; adding four rows only patches the instances.

TWO CONSTANTS ARE NOT THE DIGEST THEIR NAME SAYS, and both were computed wrong on
the first attempt as raw file digests:

- `catalog_sha256` is over a CANONICALIZED encoding, not the bytes of
  `sources/graphify.dispositions.json`.
- `source_manifest_sha256` digests the baseline's GENERATED `source-manifest.json`
  member, NOT the committed `sources/graphify.manifest`.

Two plausible readings, two authoritative-looking wrong 64-hex values that would
have survived forever. The fix is to READ them out of the engine's own candidate
(build with the authority comparison neutralized for one run, then read
`manifest.json` and `build-receipt.json`) rather than deriving them independently.

ORDER IS LOAD-BEARING AND THE CODE SAYS SO. `_ACCEPTED_GRAPHIFY_RUNTIME`'s comment
states it "may only advance when the receipt does". Followed literally: pin moved
-> slice re-ran -> produced a 0.9.45 receipt -> `verify` reported
`candidate-authority-mismatch` against the still-0.9.44 constant -> only THEN did
it advance. Advancing it first would have made that check pass by construction and
proved nothing.

THE TRAP I DOCUMENTED AND THEN WALKED INTO. A commit that changed NOTHING BUT A
COMMENT in `graphify_semantic_corpus_run.py` invalidated the corpus authorization
and made `kb-ship` refuse. `runner_sha256` digests the FILE, so a comment moves it,
which moves `execution-config.json`, which `AUTHORITY_JSON` is a digest of. I had
written that mechanism into the previous commit's own body one commit earlier. The
error was reasoning about "no executable line changed" when the predicate is "the
digest did not move" — those are different statements.

The re-plan was the cleanest possible evidence that only CODE identity moved:
`advisories_sha256` (ce1da16e) and `exclusions_sha256` (9aeb4c1b) came back
BYTE-IDENTICAL across both re-plans, so no reviewed decision changed and the
re-record carried the same human judgement rather than asking for a new one.

WHY THE BUMP WAS A PREREQUISITE RATHER THAN HOUSEKEEPING: graphify #2775 in 0.9.45
fixes `attach_hyperedges` raising `KeyError: 'id'` on every incremental re-extract
of a graph containing id-less hyperedges — which upstream's own comment says the
semantic extractor emits. The 58-chunk corpus run produces exactly those, so
running at 0.9.44 would have bought a corpus that poisoned every later incremental
rebuild.


## Outcome

- Signal: useful