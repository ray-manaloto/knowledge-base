---
type: "query"
date: "2026-07-24T18:06:21.762129+00:00"
question: "Does kb-query surface newly merged PROSE nodes in a graph dominated by code AST?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["cerebras-knowledge-base_hybrid_retrieval", "cerebras-knowledge-base_reranker"]
---

# Q: Does kb-query surface newly merged PROSE nodes in a graph dominated by code AST?

## Answer

NO -- demonstrated. After merging 119 prose nodes (verified 119/119 present in graph.json by exact id), two on-topic queries returned ~43 CODE symbols (distill.py, HybridRetriever, fusion.py from cognee/deerflow/pensyve) and ZERO of the new prose nodes. Ingestion is fine; RETRIEVAL is the bottleneck. The graph is ~128k nodes, overwhelmingly code, and there is no hybrid lexical+vector scoring, no IDF or age-decay weighting, no reciprocal-rank fusion, no reranker, and no source-type or project scoping -- precisely the machinery Cerebras built after finding 'vector search alone was insufficient'.

## Outcome

- Signal: useful

## Source Nodes

- cerebras-knowledge-base_hybrid_retrieval
- cerebras-knowledge-base_reranker