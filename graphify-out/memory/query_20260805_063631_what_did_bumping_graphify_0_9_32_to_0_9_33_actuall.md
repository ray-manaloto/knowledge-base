---
type: "query"
date: "2026-08-05T06:36:31.631336+00:00"
question: "What did bumping graphify 0.9.32 to 0.9.33 actually repair in the corpus?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did bumping graphify 0.9.32 to 0.9.33 actually repair in the corpus?

## Answer

Nothing, and the claim that it would was wrong. Nodes moved 334,486 to 335,812, but 1,259 of that +1,326 is .self-graph - our own python and tests growing - and the corpus proper moved about 67 nodes, essentially all graphify 9,812 to 9,878 from the source pin advancing. The reason: kb-build runs extract --force, a full re-scan, every time, so the 2437/2438 update fix was never in play on that path. The bump protects FUTURE kb-update runs, which are the incremental path. Its other real value is that a whole-pass AST failure now exits non-zero instead of writing a zero-node graph - which is how ruff root cause finally surfaced: AST extraction failed: PosixPath("/") has an empty name. But graph.py:87-92 runs extract with check=False and throws that signal away, so a crashed extraction still reports identically to a legitimately empty one and the build printed "prose-only" about a repo with 5,507 code files.

## Outcome

- Signal: useful