---
name: graphify
description: "Use for any question about a codebase, its architecture, file relationships, or project content — especially when graphify-out/ exists, where the question should be treated as a graphify query first. Turns code and documents into a persistent knowledge graph with community detection and query/path/explain tools."
---

# Graphify

Use Graphify as the first orientation layer for codebase questions. Prefer the
project's pinned mise tasks and interpreter guards over an ambient installation.

## Fast path: query the existing graph

When `graphify-out/graph.json` exists and the request is a question about the
repository, query before reading or searching raw files:

```bash
graphify query "<question>"
```

Use a narrower graph command when the request already names endpoints or a
single concept:

```bash
graphify path "<source>" "<target>"
graphify explain "<concept>"
```

Do not rebuild for an ordinary question. If traversal is broad, narrow the
question or use `--budget`. Cite `source_file` or `source_location` from the
result when making a specific claim. Read
[query.md](references/query.md) for vocabulary expansion, BFS/DFS selection,
the NetworkX fallback, and `save-result` feedback.

## Usage

```text
/graphify
/graphify <path>
/graphify <path> --update
/graphify <path> --mode deep
/graphify <path> --cluster-only
/graphify <path> --directed
/graphify <path> --no-viz
/graphify <path> --wiki
/graphify <path> --obsidian
/graphify <path> --graphml
/graphify <path> --svg
/graphify <path> --neo4j
/graphify <path> --falkordb
/graphify <path> --mcp
/graphify <path> --watch
/graphify https://github.com/<owner>/<repo>
/graphify <url1> <url2>
/graphify add <url>
/graphify query "<question>"
/graphify path "<source>" "<target>"
/graphify explain "<concept>"
```

For `/graphify --help` or `/graphify -h` with no other arguments, return the
usage block and stop.

## Repository workflow

If the project defines Graphify mise tasks, use them. In this knowledge base:

```bash
mise run kb-query -- "<question>"
mise run kb-build
mise run kb-artifacts
mise run kb-graph-integrity
mise run kb-critical-corpus
```

A full build must use the pinned Graphify executable and SDK. Do not accept a
green CLI version while a stale `graphify-out/.graphify_python` points at a
different distribution. The project runner validates both sides.

For a new repository without project tasks:

1. Detect the corpus and report its size and file categories.
2. Extract code structurally with the AST path.
3. Extract documents semantically only when a supported backend or host-agent
   path is available; never invent semantic output.
4. Build, cluster, diagnose, and export the graph.
5. Persist the manifest only for files that actually produced output.
6. Report graph counts, health warnings, token use, and skipped work.

Use the native CLI instead of copying implementation-sized Python blocks into a
session. Read [extraction-spec.md](references/extraction-spec.md) for the schema
and semantic extraction contract.

## Update and source workflows

- GitHub clone, branch, multi-repository merge, and monorepo behavior:
  [github-and-merge.md](references/github-and-merge.md).
- Incremental update and cluster-only behavior:
  [update.md](references/update.md).
- URL ingestion and watch mode:
  [add-watch.md](references/add-watch.md).
- Audio/video transcription:
  [transcribe.md](references/transcribe.md).
- Wiki, HTML, Obsidian, SVG, GraphML, Neo4j, FalkorDB, MCP, and benchmark
  exports: [exports.md](references/exports.md).
- Commit-hook and agent-instruction integration:
  [hooks.md](references/hooks.md).

### Step 5 - Label communities

> **DO NOT RUN STEP 5 IN THIS REPO — use `mise run kb-label`.** Two reasons,
> both verified against the 0.9.34 installer template rather than assumed:
>
> 1. Its block writes `GRAPH_REPORT.md` and `.graphify_labels.json` BEFORE
>    attempting the `graph.json` export, and its final
>    `print('Report updated with community labels')` sits at indent 0 — so a
>    REFUSED export (the #479 shrink guard) prints an error and then reports
>    success, exiting 0 with two sidecars describing a graph that was never
>    written. Step 4 has the correct shape twenty lines earlier and its own
>    comment names the upstream issue this reintroduces (#1392).
> 2. It writes `graph.json` through graphify's bundled interpreter, which
>    bypasses the pinned-version gate every `kb-setup` graph writer pays and
>    is exactly what `kb_setup.hook_guard` denies.
>
> `mise run kb-label` has neither problem and needs no LLM. This note is an
> ADDENDUM, not a hand-edit: the tree is regenerated, so editing the block
> itself would be eaten by the next refresh. (Cold lane on 5204e57, F1/F2.)

Use `mise run kb-build` for aggregate construction. It force-extracts pinned
source checkouts, validates each document merge, composes hyperedges, and stamps
the effective Graphify version. Use `mise run kb-artifacts` only after that
stamp is current.

The focused critical corpus is an evidence gate, not a substitute for the
aggregate build. `BLOCKED_NO_LOCAL_MODEL` describes only its optional local-model
prototype lane. It does not block semantic extraction: use the host-agent path
in `kb-curator` meanwhile. Preserve CLI/SDK parity and report the prototype as
not run rather than converting it into a corpus-wide blocker.

## Honesty rules

- Never invent an edge. Use `AMBIGUOUS` when the evidence is unresolved.
- Never promote a lexical or structural co-occurrence into a semantic relation
  without source-cited evidence.
- Never hide a failed extraction, shrink refusal, missing model, skipped export,
  health warning, or cohesion score.
- Never claim a rebuild from a query result.
- Never claim the pinned version ran until both CLI and SDK resolution agree.
- Keep generated outputs out of source control unless the repository explicitly
  declares them authored artifacts.
