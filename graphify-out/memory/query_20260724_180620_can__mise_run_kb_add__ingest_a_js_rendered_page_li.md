---
type: "query"
date: "2026-07-24T18:06:20.913147+00:00"
question: "Can 'mise run kb-add' ingest a JS-rendered page like claude.com or cerebras.ai?"
contributor: "graphify"
outcome: "corrected"
correction: "Earlier belief that a non-zero kb-add exit code plus a saved .md meant successful ingestion."
source_nodes: ["blog-context-engineering-claude5_context_engineering", "cerebras-knowledge-base_one_embeddings_table"]
---

# Q: Can 'mise run kb-add' ingest a JS-rendered page like claude.com or cerebras.ai?

## Answer

NO, and the failure is silent. Root cause read from graphify 0.9.25 source: _fetch_webpage -> safe_fetch_text is plain urllib (no JS execution); _html_to_markdown markdownifies the WHOLE document (no readability/article extraction); the result is hard-truncated at markdown[:12000]. On a SPA whose DOM leads with nav, the entire 12k budget is spent on chrome, producing a ~12.4KB file that LOOKS like a successful fetch. Tell: uniform ~12.4KB size across unrelated pages. Detect by grepping the fetch for article-specific terms; 0 hits for terms the article is ABOUT means a shell. Fix: capture via claude-in-chrome get_page_text and vendor under sources/media/. There is no --render/--readability flag.

## Outcome

- Signal: corrected
- Correction: Earlier belief that a non-zero kb-add exit code plus a saved .md meant successful ingestion.

## Source Nodes

- blog-context-engineering-claude5_context_engineering
- cerebras-knowledge-base_one_embeddings_table