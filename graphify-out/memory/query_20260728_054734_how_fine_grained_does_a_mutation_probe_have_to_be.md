---
type: "query"
date: "2026-07-28T05:47:34.537660+00:00"
question: "How fine-grained does a mutation probe have to be to prove a gate's FAIL direction?"
contributor: "graphify"
outcome: "useful"
---

# Q: How fine-grained does a mutation probe have to be to prove a gate's FAIL direction?

## Answer

It must mutate the single LINE the test claims to guard, not the call containing it. Replacing a whole _base_coverage_gap() call killed every branch inside, so a test that only ever reached the 'could not resolve' branch still went red and looked caught; the finer mutation (delete 'if got != want:') showed it could not fail. Two related traps: a test whose tmp_path is not a git repo silently exercises the unresolvable path for anything touching merge-base, and 'uv run --project' can load the INSTALLED package so the mutation is never seen.

## Outcome

- Signal: useful