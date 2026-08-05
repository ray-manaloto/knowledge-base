---
type: "query"
date: "2026-08-05T19:27:58.410859+00:00"
question: "How do I know a surviving mutation arm is a real coverage gap?"
contributor: "graphify"
outcome: "useful"
---

# Q: How do I know a surviving mutation arm is a real coverage gap?

## Answer

Prove the mutation hit the intended LINE before believing a survivor. In round #176 a five-arm sweep reported three arms broken; all three were the probe. The fragment tag="kb-watch" first occurs at graph.py:811 in a _clear_stamp call, not at the assert_composition call 103 lines later; chunks.py holds THREE isinstance(chunk, dict) guards and the eight-space one matched _collect_ids rather than assemble; the third fragment was a guess at code that actually reads malformed.append(repr(m)). Re-pointed, all five were caught. A str.replace on the first match is a bound in the sense of probes-need-a-control-arm rule 3, and a harness that reports SURVIVED without asserting the mutant differs at the intended site manufactures coverage gaps that do not exist. Print the mutated line, or match a fragment unique enough that it cannot land elsewhere.

## Outcome

- Signal: useful