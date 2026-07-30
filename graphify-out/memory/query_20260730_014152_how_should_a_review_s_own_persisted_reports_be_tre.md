---
type: "query"
date: "2026-07-30T01:41:52.228655+00:00"
question: "How should a review's own persisted reports be treated as review input?"
contributor: "graphify"
outcome: "useful"
---

# Q: How should a review's own persisted reports be treated as review input?

## Answer

Excluded. On #67, 2054 of 3651 reviewed lines (56%) were prose under docs/research/ — the persisted lane reports of EARLIER ROUNDS of the same review, re-read 17 lane-runs deep. kb-review now passes ':(exclude)docs/research/**' to every lane, and the exclusion lives in the reference file's literal prompt template too, not only in SKILL.md — describing it in the skill while omitting it from the prompt is how the same class of bug recurred with the codex-reviewer routing.

## Outcome

- Signal: useful