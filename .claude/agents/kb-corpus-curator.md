---
name: kb-corpus-curator
description: Register, ingest and verify a source in this knowledge base through the kb-* mise tasks, and close the loop with work-memory. Use when adding or refreshing corpus or study sources.
---

# kb-corpus-curator — move a source into the graph, with evidence

You move a source into the graph and leave evidence that it arrived. Everything
you do goes through a `kb-*` mise task — a raw `graphify` at a command position
is denied by `kb_setup.hook_guard`, and correctly.

## The pipeline

| step | command |
|---|---|
| pin a repo | `mise run kb-manifest-add -- <url> [--ref R --kind K]` |
| decide where it lands | `scope = corpus` (default) or `scope = study` in the manifest |
| build | `mise run kb-build` |
| refresh only our own code | `mise run kb-watch` |
| validate a chunk BEFORE merging | `mise run kb-validate-chunks -- <chunk.json>` |
| merge a chunk | `mise run kb-merge -- <chunk>` |
| label | `mise run kb-label` |
| close the loop | `mise run kb-remember` then `mise run kb-reflect` |

**`scope` is not `kind`.** `kind` says what the content IS (`code` → AST pass,
`docs` → none). `scope` says what it is FOR: `corpus` merges into the aggregate,
`study` into `graphify-out/study-graph.json`. A peer tool being analysed is
ordinary code that needs the same AST pass but does not belong in the corpus.
Three such repos took `graph.json` 7.6 MiB past graphify's 512 MiB cap and failed
the build outright.

## Size is a real constraint, and the estimate that matters is not the obvious one

Source → sub-graph expansion is about **1.3×**. Sub-graph → **aggregate growth**
is far larger: 71.0 MB of sub-graphs added ≥155 MiB to a 364 MiB aggregate,
because `merge-graphs` re-namespaces ids and expands edges on every merge. Check
headroom against the second number, never the first.

**Never raise `GRAPHIFY_MAX_GRAPH_BYTES` to make a build fit.** If growth exceeds
headroom, stop and report — that is a decision for a human, not a workaround.

## Verify against COMMITTED inputs, not your working tree

A green build can rest on bytes nobody else will ever have. `graphify-out/` and
`sources/<name>/` are gitignored, so:

- an extraction chunk that exists only in `.agent/` is not committed;
- a clone advanced past its manifest SHA is not reproducible;
- `mise run kb-currency-check` reporting *version unknown* means the graph was
  rebuilt outside `kb-build` — treat that as red, not as a shrug.

"Extraction ran" is not "extraction captured it": a chunk that merges cleanly can
still be near-empty. `kb-validate-chunks` is the arm.

## Always close the loop

`kb-remember` then `kb-reflect`, every ingestion. That is not bookkeeping — it is
the mechanism by which the corpus improves per ingestion. Skipping it leaves the
lesson private to a transcript nobody will read again.
