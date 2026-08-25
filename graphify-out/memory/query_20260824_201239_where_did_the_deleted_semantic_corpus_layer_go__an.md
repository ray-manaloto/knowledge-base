---
type: "query"
date: "2026-08-24T20:12:39.824286+00:00"
question: "Where did the deleted semantic-corpus layer go, and how do I get it back?"
contributor: "graphify"
outcome: "useful"
---

# Q: Where did the deleted semantic-corpus layer go, and how do I get it back?

## Answer

# Where did the deleted semantic-corpus layer go, and how do I get it back?

Ray ruled on 2026-08-24 that all extraction goes through the graphify CLI only,
and that the layer re-implementing the CLI's internals is removed — receipts and
integrity gate included — but ARCHIVED first and documented so it can be found
immediately.

## The answer, shortest first

1. **git history is the archive.** Deletion in a commit does not remove content.
   `d2acb5535553` is the last commit where the layer existed in full:

       git show d2acb5535553:python/src/kb_setup/graphify_semantic_corpus.py
       git checkout d2acb5535553 -- <path>

   This needs no maintenance and cannot rot.

2. **A convenience zip exists**, machine-local and NOT backed up by the repo:

       ~/.local/share/knowledge-base-archives/semantic-corpus-layer-20260824-d2acb5535553.zip
       sha256 9399fe2a49f19d6b7f5f056462dd793aea4d8679fa0d1badb4317d823062f25f
       556 K zipped · 2,539,421 bytes raw · 149 files

3. **The tracked pointer is `docs/archive/README.md`** — that is the file to open
   first, because it survives a fresh clone while the zip does not.

## What is inside

- The 8 modules that re-implemented graphify's extraction internals
  (corpus planner/runner/merge/record/prototype/authority, slice, adapter).
- `corpus_integrity.py`, the ship gate.
- `graphify-out/graphify-semantic-corpus-chunks/` — 105 files, ~1.97 MB,
  roughly **$41.78 of paid provider extraction, NOT regenerable at these
  digests**. This is the part that actually cost money.
- The 5 test files covering the layer.

## Why it was removed

Two routes reached graph.json: one shelled out to the CLI, the other re-typed
what the CLI does inside. The second drifts whenever the CLI changes, and it
did — graphify #2900 added `.html` to `_SPLITTABLE_TEXT_SUFFIXES`, a 1.85 MB
excluded file went from ONE unit to ~93, and 24 tests went red on an assumption
that had silently expired.

The evidence and its gate went too, on Ray's explicit choice: nothing will ever
write those files again, and a gate guarding a museum trains people to ignore
gates. The archive is what makes that safe.

## The naming rule, so the next archive is findable

`<subject>-<YYYYMMDD>-<sha12>.zip` — the commit to `git show` against is in the
filename, so a stray zip is self-describing even with no README beside it.


## Outcome

- Signal: useful