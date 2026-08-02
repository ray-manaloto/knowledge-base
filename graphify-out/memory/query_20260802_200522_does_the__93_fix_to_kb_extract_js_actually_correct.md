---
type: "query"
date: "2026-08-02T20:05:22.453879+00:00"
question: "Does the #93 fix to kb-extract.js actually correct edge direction and captured_at at fan-out scale?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does the #93 fix to kb-extract.js actually correct edge direction and captured_at at fan-out scale?

## Answer

YES, both arms proven 2026-08-02. NEGATIVE arm: a caller omitting args.capturedAt throws with agent_count=0, subagent_tokens=0, in 3ms - it fails CLOSED before spawning anything, so the control arm is free to run. POSITIVE arm: 8 agents, 264 nodes, 402 edges, kb-validate-chunks rc=0 (which covers cross-chunk id collision, the failure mode #93 said had never been exercised - 3 of the 8 files were about wayfinder from different sources precisely to stress it; no collision). part_of came out MEMBER->CONTAINER in every chunk (15 sources->4 targets, 10->5, 6->5, 4->3) against #84s 22-of-22 BACKWARDS. captured_at was 2026-08-02 from args, not the frozen 2026-07-23 literal. The agents own notes cite the two rules I added, so the prompt language took rather than being ignored. This unblocks #82. COST: 1,130,210 subagent tokens for 8 files = ~141k/file - budget any sweep with that number, not with a guess.

## Outcome

- Signal: useful