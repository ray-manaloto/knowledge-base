---
type: "query"
date: "2026-09-09T21:51:44.879521+00:00"
question: "Was the graphify baseline identity check safe to assume would pass because the catalog and manifest agree on source_commit?"
contributor: "graphify"
outcome: "corrected"
correction: "An assertion made of two conjuncts is verified when BOTH are read, not when the\nconvenient one is.\n\nI stated that `build_baseline`'s identity check \"should not raise\" because the\ndisposition catalog and the manifest agree. They do agree — on `source_commit`,\nthe field I had already looked at for another reason. The check at\n`graphify_baseline.py:1988-1993` is `resolved_commit != catalog.source_commit OR\ntree_digest != catalog.source_tree`. I never read the second conjunct, and the\nsecond conjunct was the one that was false. The build failed on exactly it.\n\nThe same shape then repeated one layer down. Having been corrected, I built a\ntable of four \"required\" values and measured two of them against the wrong bytes\n— `sha256(sources/graphify.manifest)` for a field that digests an artifact the\nbuild emits. Both wrong rows read as measurements because they were: real\ncommands, real output, wrong inputs.\n\nThe tell in both cases was available for free: a conjunction has as many premises\nas it has conjuncts, and a field named `<thing>_sha256` does not say WHICH bytes.\nWhen a name is ambiguous, the code that COMPUTES or COMPARES it settles it — and\nthat read is two greps, which is what finally did settle it.\n\nRelated: a harness \"completed (exit code 0)\" notification reported success for a\nbuild whose real rc was 1, because the compound ended in `tail`. The file-based\n`rc=` line is what caught it. `verify-before-advancing.md` already says never\ntrust a notification's exit code; this round is the instance.\n"
---

# Q: Was the graphify baseline identity check safe to assume would pass because the catalog and manifest agree on source_commit?

## Answer

A dependency pin move has TWO kinds of value and only one of them has an owner.

`currency.toml:216-248` declares four `[[tool.graphify.ref_binding]]` rows, every
one `field = ref` or `commit`. On the graphify 0.9.53 -> 0.9.57 bump, exactly the
two kinds with rows advanced and exactly the four DERIVED values without rows did
not: the catalog's `source_tree`, `_ACCEPTED_AUTHORITY.source_tree`,
`.catalog_sha256`, `.source_manifest_sha256`.

Three things make this more than a missed line.

1. `ref_binding` is a read-only equality CHECK (`sync.py:1720`), never a writer.
   A fifth row would not have advanced anything; it would only have gone red.
   Nothing in the repo writes these values: grep for the three field names outside
   `graphify_baseline.py` returns empty, control-armed against
   `manifest.py:418` (`write_pin`), which the same grep shape does find.

2. Only ONE of the four is knowable in advance. `source_tree` is
   `git rev-parse <commit>^{tree}` (`graph.py:1146`). The other two are digests of
   artifacts the BUILD emits — `catalog_sha256` over the msgspec re-encoding
   (`:1960` <- `_write_candidate_inputs:1402`), `source_manifest_sha256` over the
   emitted `source-manifest.json` (`:1218`, built by `source_manifest():583-610`
   from `git ls-tree`). Proven by exact match against the pre-bump snapshot:
   emitted `dispositions.json` -> `2a1f353a...` = `_ACCEPTED_AUTHORITY.catalog_sha256`;
   emitted `source-manifest.json` -> `b1c4aebb...` = `.source_manifest_sha256`.

3. The derivation is ORDERED, and getting the order wrong yields a wrong answer
   that looks right. `DispositionCatalog` contains `source_tree` (`:66`), so fixing
   the tree CHANGES `catalog_sha256`. A hash taken before the fix is, verbatim from
   the cross-family review, "cryptographically valid but semantically stale".

And the tool cannot help: `build_baseline:1990-1993` raises before
`build_from_snapshot` runs, so `_authority_reasons` — the #373 diagnostic built
precisely so the next bump would be one line of reading — is unreachable. The same
guard is duplicated at `certify_baseline_controls:2020-2025`, so `-- controls` is
no second door, and `_MAX_BASELINE_ARGS = 2` leaves no flag slot.

No gate was at fault. `kb-manifest-audit` scopes pin-site completeness out by its
own docstring; the check that owns it, `kb-currency-check`, is not in `GATE_TASKS`
(`gates.py:173`).

The fix shape is constrained by `docs/agents/graphify-deterministic-baseline.md`:
these values are a trust root, so the primitive DERIVES, PRESENTS and requires
EXPLICIT ACCEPTANCE. Never derive-and-write — a machine that fills them in is a
machine that has stopped checking.


## Outcome

- Signal: corrected
- Correction: An assertion made of two conjuncts is verified when BOTH are read, not when the
convenient one is.

I stated that `build_baseline`'s identity check "should not raise" because the
disposition catalog and the manifest agree. They do agree — on `source_commit`,
the field I had already looked at for another reason. The check at
`graphify_baseline.py:1988-1993` is `resolved_commit != catalog.source_commit OR
tree_digest != catalog.source_tree`. I never read the second conjunct, and the
second conjunct was the one that was false. The build failed on exactly it.

The same shape then repeated one layer down. Having been corrected, I built a
table of four "required" values and measured two of them against the wrong bytes
— `sha256(sources/graphify.manifest)` for a field that digests an artifact the
build emits. Both wrong rows read as measurements because they were: real
commands, real output, wrong inputs.

The tell in both cases was available for free: a conjunction has as many premises
as it has conjuncts, and a field named `<thing>_sha256` does not say WHICH bytes.
When a name is ambiguous, the code that COMPUTES or COMPARES it settles it — and
that read is two greps, which is what finally did settle it.

Related: a harness "completed (exit code 0)" notification reported success for a
build whose real rc was 1, because the compound ended in `tail`. The file-based
`rc=` line is what caught it. `verify-before-advancing.md` already says never
trust a notification's exit code; this round is the instance.
