---
type: "query"
date: "2026-09-10T09:28:13.111895+00:00"
question: "What does a pin move leave behind, and why did naming the class not close it?"
contributor: "graphify"
outcome: "useful"
---

# Q: What does a pin move leave behind, and why did naming the class not close it?

## Answer

A pin move strands its DERIVED values, and naming the class does not close it.

The graphify 0.9.57 bump left SIX values describing v0.9.53: the catalog's
`source_tree`, the `uv.lock` row's sha256 and size, and
`_ACCEPTED_AUTHORITY`'s `source_tree`, `catalog_sha256` and
`source_manifest_sha256`. `catalog_sha256` is ORDER-DEPENDENT — fixing a catalog
entry moves it again (`a52e4f6e…` before the uv.lock row was corrected,
`0444f055…` after) — so a fix applied in the wrong order trades one drift for
another and both gates stay green.

Two more remain uncovered and cannot be derived offline: `detected_count` (471)
and `extracted_count` (463). The census PREDICTS 490/482; that is a prediction.

THE LESSON THAT COST THE MOST: I reported FIVE by reading my own gate's output
instead of deriving the set. That is the third time this exact error has been
made here — #728 called it 2, one round found 6, another found 7. The primitive
must DERIVE the set, never read a list, including a list it just printed.

And ONE COMMIT LATER, in the same branch, the antigravity bump moved
`mise.toml`, `currency.toml` and the source manifest and left `mise.lock` at the
old version. All nine gates — the new one included — went green and it MERGED
(`6b3ab427`). A second, weeks-old instance sat beside it: a `[[tools.codex]]`
lock entry on the `aqua:` backend that `mise.toml` had moved to `npm:`.

`mise run kb-lock-drift` now closes that, natively: `mise lock --dry-run`
previews without writing, but returns **rc 0 whether the lock is in sync or five
versions stale**, so the gate reads the report and not the exit code.


## Outcome

- Signal: useful