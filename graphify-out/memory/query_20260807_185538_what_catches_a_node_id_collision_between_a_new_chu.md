---
type: "query"
date: "2026-08-07T18:55:38.511435+00:00"
question: "What catches a node-id collision between a new chunk and the committed corpus?"
contributor: "graphify"
outcome: "useful"
---

# Q: What catches a node-id collision between a new chunk and the committed corpus?

## Answer

Nothing in this repo does - filed as issue 231. kb-validate-chunks handed two chunks sharing 8 ids returns rc=0 and two green ticks, because the id check lives inside assemble() and only sees its own batch while the cross-chunk pass checks source_file only. The catch was graphify shrink guard 479, which is COUNT-BASED: 128 replaced, 126 emitted, 8 absorbed by the collisions, so 342322-128+118=342312 and it refused. A LARGER colliding chunk grows the graph and merges silently. Measured over the committed corpus: 25 chunks, 4788 ids, 10 collisions, ALL same-source_file (legitimate re-extraction) and 0 cross-source_file (corrupting) - so the gate can land green with no remediation pass. Until it lands, arm the id check by hand before every merge with a control.

## Outcome

- Signal: useful