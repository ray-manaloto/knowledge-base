# Archive — where deleted things went

Ray, 2026-08-24: *"zip and backup what is deleted just in case we need to refer
to it / document this somewhere so we know where to look for it right away."*

This file is that documentation. It is tracked, so it survives a fresh clone
even though the archives themselves do not live in the repo.

## Read this first: git history is the real archive

**Every file listed below is recoverable from git with no zip at all**, because
deletion in a commit does not remove content from history:

```bash
git show d2acb5535553:python/src/kb_setup/graphify_semantic_corpus.py
git show d2acb5535553 --stat            # everything as it stood before removal
git checkout d2acb5535553 -- <path>     # restore one file into the working tree
```

`d2acb5535553` is the last commit at which the semantic-corpus layer existed in
full. That is the durable answer and it needs no maintenance.

The zip below exists because a zip is faster to hand to someone, works without
the repo, and survives a repo being re-cloned or rewritten. It is a
**convenience copy, not the system of record.**

## Archives

| what | where | taken at | size | sha256 |
|---|---|---|---|---|
| the semantic-corpus layer + its provider evidence | `~/.local/share/knowledge-base-archives/semantic-corpus-layer-20260824-d2acb5535553.zip` | `d2acb5535553` | 556 K zipped · 2,539,421 bytes raw · 149 files | `9399fe2a49f19d6b7f5f056462dd793aea4d8679fa0d1badb4317d823062f25f` |

**The archive path is machine-local and NOT backed up by this repo.** If the
machine is lost, recover from git history instead — which is why the section
above comes first.

Verify the copy you have is the one this file describes:

```bash
shasum -a 256 ~/.local/share/knowledge-base-archives/semantic-corpus-layer-20260824-d2acb5535553.zip
```

### What is inside

**The 8 modules that re-implemented the graphify CLI's internals**, removed
2026-08-24 on Ray's ruling that all extraction goes through the CLI only:

`graphify_semantic_corpus.py` · `graphify_semantic_corpus_run.py` ·
`graphify_semantic_corpus_merge.py` · `graphify_semantic_corpus_record.py` ·
`graphify_semantic_corpus_prototype.py` · `graphify_semantic_corpus_authority.py`
(+ its `.json`) · `graphify_semantic_slice.py` · `graphify_semantic_adapter.py`

**The integrity gate** `corpus_integrity.py`, and **the provider evidence it
guarded**: `graphify-out/graphify-semantic-corpus-chunks/` — 105 files,
~1.97 MB, representing roughly **$41.78 of paid extraction** that is *not
regenerable at these digests*. This is the part worth knowing exists.

**The five test files** that covered the layer.

### Why it was deleted rather than kept

Two paths reached `graph.json`: one shelled out to the `graphify` CLI, the other
re-implemented what that CLI does inside — its own planning, slicing, provider
calls and receipts. The second drifted every time the CLI changed, and in
August 2026 it did: graphify added `.html` to its splittable set, a 1.85 MB
excluded file went from one unit to ~93, and 24 tests went red on an assumption
that had quietly expired.

The evidence went with it because nothing will ever write to it again — a gate
guarding a museum trains people to ignore gates. See
`docs/artifacts/extraction-architecture.html` (published as **Two Extraction
Paths**) for the diagrams.

## Adding an archive

Keep the shape above: an absolute path, the commit it was taken at, the raw and
zipped sizes, a sha256, and a sentence on what a future reader would want it
for. An archive nobody can verify or date is a directory of mystery zips.

Name archives `<subject>-<YYYYMMDD>-<sha12>.zip` so the commit to `git show`
against is in the filename itself.
