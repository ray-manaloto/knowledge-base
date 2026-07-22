---
type: "query"
date: "2026-07-22T17:25:32.322978+00:00"
question: "Does graphify reflect produce LESSONS.md, and what is the work-memory overlay?"
contributor: "graphify"
outcome: "corrected"
correction: "Prior graphify-reference.md said reflect's LESSONS.md artifact was 'unconfirmed / refuted in research'. It is confirmed real on 0.9.23."
source_nodes: ["reflect", "save-result"]
---

# Q: Does graphify reflect produce LESSONS.md, and what is the work-memory overlay?

## Answer

Yes. reflect aggregates graphify-out/memory/ into a DETERMINISTIC (no-LLM) reflections/LESSONS.md. With --graph it groups by community, drops stale nodes, and writes the .graphify_learning.json overlay tagging nodes preferred/tentative/contested (recency-weighted via --half-life-days 30, --min-corroboration 2). Verified on installed 0.9.23. reflect --if-stale and extract --dedup-llm are 0.9.24+ (NOT installed).

## Outcome

- Signal: corrected
- Correction: Prior graphify-reference.md said reflect's LESSONS.md artifact was 'unconfirmed / refuted in research'. It is confirmed real on 0.9.23.

## Source Nodes

- reflect
- save-result