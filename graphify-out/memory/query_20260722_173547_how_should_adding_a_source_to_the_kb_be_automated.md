---
type: "query"
date: "2026-07-22T17:35:47.561321+00:00"
question: "How should adding a source to the KB be automated so the corpus self-improves each time?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["kb-curator", "save-result", "reflect"]
---

# Q: How should adding a source to the KB be automated so the corpus self-improves each time?

## Answer

Use the kb-curator skill (.claude/skills/kb-curator): register in sources/REGISTRY.md -> ingest (repo=manifest+kb-build AST free; prose=host-agent extraction chunk) -> merge+recluster -> label --missing-only -> ALWAYS kb-remember (save-result) + kb-reflect. The mandatory save-result/reflect step is what makes it self-improving: every ingestion records a lesson to memory/ and regenerates reflections/LESSONS.md + the .graphify_learning.json overlay. Authored via the skill-creator methodology; evals in evals/evals.json.

## Outcome

- Signal: useful

## Source Nodes

- kb-curator
- save-result
- reflect