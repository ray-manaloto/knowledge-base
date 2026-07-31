---
type: "query"
date: "2026-07-31T02:22:17.901765+00:00"
question: "Does the mirror to graph extraction path actually work (knowledge-base#84)?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does the mirror to graph extraction path actually work (knowledge-base#84)?

## Answer

PROVEN 2026-07-30. One page (docs/claude-code/sub-agents.md, 1,250 lines) read from the PINNED CLONE at 03853a01 by a general-purpose subagent produced 132 nodes / 149 edges (141 EXTRACTED, 8 INFERRED). It validated, assembled, merged (+132 -> 130,668 nodes) and REPRODUCED from committed inputs alone via kb-build rc=0. Scale note: the three previously hand-rolled curl'd pages produced 26 nodes BETWEEN THEM, so the real path yields roughly 15x per page. Three defects were found by RUNNING it that reading it would not have surfaced: (1) kb-merge leaves graph-prose.json stale; (2) kb-extract.js hardcodes captured_at 2026-07-23; (3) the -docs suffix convention mangles a source whose own name ends in -docs — _out_path strips -docs before re-appending, so assemble name 'agent-harness-docs' yields root sources/agent-harness which does not exist. Only 'agent-harness-docs-docs' resolves to the real clone; confirmed in the kb-build log. The pre-existing claude-code-docs-mirror-docs.json has the same defect.

## Outcome

- Signal: useful