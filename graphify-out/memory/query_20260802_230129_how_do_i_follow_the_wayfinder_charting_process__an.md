---
type: "query"
date: "2026-08-02T23:01:29.553236+00:00"
question: "How do I follow the wayfinder charting process, and does this corpus hold it?"
contributor: "graphify"
outcome: "useful"
---

# Q: How do I follow the wayfinder charting process, and does this corpus hold it?

## Answer

Yes — kb-query --prose --idf returns the wayfinder process densely (top 20.09, 289 nodes >0, all on-topic, sources: mattpocock SKILL.md/CHANGELOG.md/CONTEXT.md and aihero-skills-wayfinder.md). Control arm: an unrelated kubernetes/sidecar query with the same command shape topped at 12.98 with 31 nodes and zero wayfinder content, so the probe discriminates. BUT the graph returns POINTERS, not content (lexical.py Hit = source_file/node_id/label/score), so charting still required reading the SKILL.md itself. And the skill is absent from the model's listing because of disable-model-invocation:true, not any context budget.

## Outcome

- Signal: useful