---
type: "query"
date: "2026-07-22T17:41:40.220436+00:00"
question: "How should a large graphify graph.json (119MB, >GitHub 100MB limit) be stored and shared?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["push_to_neo4j", "push_to_falkordb", "merge-driver", "kb-build"]
---

# Q: How should a large graphify graph.json (119MB, >GitHub 100MB limit) be stored and shared?

## Answer

graphify's own design answers it: (1) graph.json is REGENERABLE from committed inputs (manifests + extraction chunks) via kb-build, so committing the blob is optional — gitignore it and rebuild. (2) For a large QUERYABLE graph, graphify has native push_to_neo4j()/push_to_falkordb() exporters (graphify/exporters/graphdb.py) + --push <uri>; the DB is the scale query surface (kb-neo4j/kb-falkordb already run), not a git blob. (3) graphify ships a git merge-driver for graph.json (hooks.py) for union-merge on branch merges — intends graph.json in git only at modest sizes. Recommendation: gitignore graph.json (rebuild-from-inputs) + serve via MCP/graph-DB.

## Outcome

- Signal: useful

## Source Nodes

- push_to_neo4j
- push_to_falkordb
- merge-driver
- kb-build