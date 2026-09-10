---
type: "query"
date: "2026-09-09T21:51:44.293256+00:00"
question: "Does anything in this project automate advancing a dependency pin's DERIVED values, and why did the graphify 0.9.53->0.9.57 bump leave four of them stale?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does anything in this project automate advancing a dependency pin's DERIVED values, and why did the graphify 0.9.53->0.9.57 bump leave four of them stale?

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

- Signal: useful