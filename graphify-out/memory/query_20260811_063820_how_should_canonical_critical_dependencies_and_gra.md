---
type: "query"
date: "2026-08-11T06:38:20.893115+00:00"
question: "How should canonical critical dependencies and Graphify query limits be represented and audited?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["GRAPHIFY_MAX_OUTPUT_TOKENS", "god_nodes"]
---

# Q: How should canonical critical dependencies and Graphify query limits be represented and audited?

## Answer

Canonical dependencies are typed canonical_dependency anchors ranked by graph coverage, unique source-file receipts, and cross-dependency project reach; they are explicitly excluded from Graphify god_nodes because god_nodes is a structural degree measurement. The live audit found 12 anchors, missing coverage for ruff, claude-code, and chezmoi, and zero cross-dependency edges, so status is RED. Query display truncation is controlled by graphify query --budget; GRAPHIFY_MAX_OUTPUT_TOKENS controls semantic LLM output, GRAPHIFY_MAX_GRAPH_BYTES controls graph-load safety, and GRAPHIFY_MAX_CONTEXTS controls the MCP project-context LRU.

## Outcome

- Signal: useful

## Source Nodes

- GRAPHIFY_MAX_OUTPUT_TOKENS
- god_nodes