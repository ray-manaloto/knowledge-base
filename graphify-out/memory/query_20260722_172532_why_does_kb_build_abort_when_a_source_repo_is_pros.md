---
type: "query"
date: "2026-07-22T17:25:32.436115+00:00"
question: "Why does kb-build abort when a source repo is prose-only, and the fix?"
contributor: "graphify"
outcome: "corrected"
correction: "kb-build must tolerate empty-code sources, not treat a prose-only repo as a fatal error."
source_nodes: ["build", "extract"]
---

# Q: Why does kb-build abort when a source repo is prose-only, and the fix?

## Answer

graphify extract --code-only EXITS NON-ZERO on a repo with no code (empty graph). kb-build used check=True so one prose-only source (e.g. fable-advisor: 2 code files) aborted the whole build after 5 repos had merged. Fix: extract code where present, skip prose-only repos (deferred to the host-agent prose wave), keep their manifest pins.

## Outcome

- Signal: corrected
- Correction: kb-build must tolerate empty-code sources, not treat a prose-only repo as a fatal error.

## Source Nodes

- build
- extract