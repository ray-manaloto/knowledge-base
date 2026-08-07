---
type: "query"
date: "2026-08-07T20:13:06.785229+00:00"
question: "What does a cold cross-family review actually catch that my own checks do not?"
contributor: "graphify"
outcome: "useful"
---

# Q: What does a cold cross-family review actually catch that my own checks do not?

## Answer

Semantic edge direction, at scale. The codex lane returned 63 findings on 480 nodes of extraction data - 2 P1 and 61 P2 - split the 11843-line diff into 5 batches, cited file:line on every one, and spot-checked 5 of its own citations. I verified 7 independently and all 7 held. My own part_of inversion sweep over the same 407 edges had reported 0, because it only looked for a _doc node as SOURCE and was structurally blind to plugin part_of skill where neither endpoint is a _doc node. Cost 124665 subagent tokens and about 15 minutes. Route by WHO WROTE THE DIFF, not by habit: the repo declares implementation lane = codex, but that flow is Fable-gated, so an Opus session that wrote the code itself still gets codex as the genuinely cross-family lane.

## Outcome

- Signal: useful