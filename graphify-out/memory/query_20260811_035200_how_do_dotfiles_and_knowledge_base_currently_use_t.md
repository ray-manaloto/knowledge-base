---
type: "query"
date: "2026-08-11T03:52:00.695510+00:00"
question: "How do dotfiles and knowledge-base currently use tree-sitter, Graphify, and ty LSP, and what should produce visual code and change-impact maps?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["graphify", "TreeSitterExtractor", "affected()"]
---

# Q: How do dotfiles and knowledge-base currently use tree-sitter, Graphify, and ty LSP, and what should produce visual code and change-impact maps?

## Answer

Both repositories pin Graphify 0.9.36, which uses tree-sitter 0.25.2 and language grammars for structural extraction. Graphify does not use tree-sitter-graph. It already exposes affected traversal and tree, callflow, GraphML, wiki, Obsidian, and SVG exports. Knowledge-base already wraps these as kb-artifacts; dotfiles should consume the shared knowledge-base plugin instead of duplicating them. Both repositories use ty 0.0.69 only as a batch checker today; neither invokes ty server nor consumes LSP results. Recommended: keep Graphify as the persistent base graph, add a read-only targeted ty-LSP evidence overlay through an existing local adapter such as Serena's python_ty backend, combine it with uv lock deltas, preserve per-edge provenance, and emit deterministic Mermaid plus existing Graphify artifacts through a shared kb_setup code-intelligence module. Evaluate SCIP as an optional persistent cross-language interchange because Graphify ships an unwired simplified SDK ingester. Do not adopt tree-sitter-graph unless an adversarial corpus proves a name-resolution relation Graphify cannot model; if so, prototype Stack Graphs rather than the raw DSL. Gate with known-call, homonym, alias, dependency-upgrade, split-extraction, disabled-LSP, reverse-edge, version-mismatch, determinism, and CLI-versus-SDK control and mutation arms.

## Outcome

- Signal: useful

## Source Nodes

- graphify
- TreeSitterExtractor
- affected()