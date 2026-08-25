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

It imported graphify's **private** internals — `_estimate_file_tokens`,
`_extraction_system`, `_pack_chunks_by_tokens` and `_read_files` from
`graphify.llm` — and re-implemented planning, slicing and provider calls around
them. That is the rule it broke, and the rule is worth stating in full because
the first write-up of this removal got it backwards:

1. **Best — call graphify's PUBLIC SDK directly**, 1:1 with the CLI verb
   (`kb_setup.graphify_sdk`, which pins that surface via
   `public_api_fingerprint()`). This is the destination.
2. **Fallback — shell out to the CLI** for verbs with no public SDK method yet.
3. **Never — import graphify's private internals.**

"Extraction through the CLI only" was a lossy paraphrase of that: the CLI is the
*stopgap*, the SDK is the goal, and the ban is on **re-implementation**, not on
in-process calls. `graphify_baseline.py` was kept because it sits at rule 1.

Depending on private functions is also why the layer drifted. graphify added
`.html` to its splittable set, a 1.85 MB excluded file went from one unit to
~93, and 24 tests went red on an assumption copied out of internals that nobody
promised would hold.

The evidence went with it because nothing will ever write to it again — a gate
guarding a museum trains people to ignore gates. See
`docs/artifacts/extraction-architecture.html` (published as **Two Extraction
Paths**) for the diagrams.

## ⚠️ The call-boundary telemetry is in here, and Ray wants it BACK

Ray, 2026-08-24, after the removal: *"we want to keep all the code that tracked
every graphify call being made with all metadata and arguments passed into it."*

The deleted `graphify_semantic_adapter.py` wrote an `adapter-metadata.json`
beside every chunk, and it is the richest record this repo has ever had of a
model call. Recovered from `d2acb5535553`, one real file contains:

| field | example |
|---|---|
| `argv` | the full command line, including `--model claude-opus-5 --effort high` |
| `model_usage` | input / output / `cache_creation` / `cache_read` tokens |
| `total_cost_usd` | `0.92874` |
| `duration_ms` · `duration_api_ms` · `elapsed_ms` | `196045` · `195253` · `197542` |
| identity | `claude_version`, executable `sha256`, auth method, subscription type |
| integrity | `prompt_sha256` / `response_sha256` + sizes, `returncode`, `stop_reason` |

**Two caveats before anyone rebuilds it.** It instrumented the **Claude CLI**
(graphify's provider backend), not graphify itself — so it is a template, not a
drop-in. And the mechanism to hang it on survives: `python/src/kb_setup/events.py`
is the structured event stream, and `graphify_native_extract.py` already imports it.

Recover the reference implementation with:

```bash
git show d2acb5535553:python/src/kb_setup/graphify_semantic_adapter.py
git show d2acb5535553:graphify-out/graphify-semantic-corpus-chunks/9e1adc3b7df53844cdc50f4a69f801ef329a47df0d96b7f2f229e5423b1797ad/chunks/0001/adapter-metadata.json
```

Both were verified to round-trip out of git history on 2026-08-24 — that is a
run, not an assumption.

## Adding an archive

Keep the shape above: an absolute path, the commit it was taken at, the raw and
zipped sizes, a sha256, and a sentence on what a future reader would want it
for. An archive nobody can verify or date is a directory of mystery zips.

Name archives `<subject>-<YYYYMMDD>-<sha12>.zip` so the commit to `git show`
against is in the filename itself.
