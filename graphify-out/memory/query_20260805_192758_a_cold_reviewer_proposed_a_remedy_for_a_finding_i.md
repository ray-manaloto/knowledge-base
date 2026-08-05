---
type: "query"
date: "2026-08-05T19:27:58.810699+00:00"
question: "A cold reviewer proposed a remedy for a finding I confirmed. Do I implement it?"
contributor: "graphify"
outcome: "useful"
---

# Q: A cold reviewer proposed a remedy for a finding I confirmed. Do I implement it?

## Answer

A reviewer can be right about the finding and wrong about the fix, and the remedy needs its own arm. The cold lane on #176 argued the kb-label restamp consumes the only drift signal for graph.graphml and wiki, and proposed narrowing the restamp to spec.artifact. Measured against the real currency.sync in three arms: no restamp gives graph.json DRIFT and graphml OK; the shipped full restamp gives both OK; the proposed narrow restamp gives both OK. Identical to the shipped code, because graphml bytes never move, so it is OK in every arm. The finding underneath was real and is now #182: the derived views are semantically stale and a size-mtime fingerprint cannot see it. What was actually lost was a FALSE POSITIVE about graph.json doing accidental duty as a reminder to run kb-artifacts. A signal that only works by accident is not a check, so the answer is a real staleness comparison rather than keeping the false positive. Two arms show a difference; the third shows whether the proposed change is that difference.

## Outcome

- Signal: useful