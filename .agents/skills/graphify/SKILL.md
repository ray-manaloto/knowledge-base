---
name: graphify
description: Query and maintain this repository's provenance-bound Graphify knowledge graph.
---

# Graphify in knowledge-base

Use the repository's reviewed tasks. Do not invoke a global Graphify binary, the
upstream installer, or a raw source search before attempting the graph.

## Before reading source

1. Run `mise run kb-query -- "<question>"`.
2. Treat missing, stale, corrupt, warning-bearing, or truncated graph evidence as
   unavailable, never as an empty or complete answer.
3. If the graph is unavailable, say so and use source only as the fallback
   authority. Use `mise run kb-build` to reproduce the graph when the task
   authorizes a build.

## Supported operations

- Query: `mise run kb-query -- "<question>"`
- Reverse impact: `mise run kb-affected -- "<symbol>"`
- Rebuild committed inputs: `mise run kb-build`
- Advance one reviewed source: `mise run kb-update -- <source>`
- Verify the installed SDK boundary: `mise run kb-graphify-contract`
- Refresh Graphify skills after a version change: `mise run kb-skill-refresh`

Never hide Graphify stderr, warnings, truncation, source omissions, or receipt
failures. Never treat a queued build or an existing `graphify-out/graph.json` as
proof that the graph is current. Cite graph source locations when an answer uses
graph evidence.

Detailed upstream workflows remain in the generated Claude reference tree under
`.claude/skills/graphify/references/`; repository tasks and rules take precedence.
