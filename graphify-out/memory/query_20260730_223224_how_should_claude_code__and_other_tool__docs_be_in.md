---
type: "query"
date: "2026-07-30T22:32:24.873385+00:00"
question: "How should Claude Code (and other tool) docs be ingested so the graph stays current?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["docs/claude-code/goal.md", "docs/claude-code/hooks.md", "docs/claude-code/skills.md"]
---

# Q: How should Claude Code (and other tool) docs be ingested so the graph stays current?

## Answer

Pin an auto-synced docs MIRROR as a kind=docs manifest, not per-page kb-add. MEASURED 2026-07-30: mrkhachaturov/agent-harness-docs and ericbuess/claude-code-docs are BYTE-IDENTICAL to the live code.claude.com pages (verified at the pinned SHA 03853a01 with a bogus-path 404 control arm), and both auto-sync every 3h via GH Actions cron. The payoff is not the ingestion, it is DRIFT DETECTION: kb-update advances the pin and 'git diff <old>..<new>' names the exact changed pages, which is what #76 lacked when three sha256 values moved with no way to read the delta. BLOCKER that shaped the design: kb-build ran 'graphify extract --code-only', which graphify defines as skipping doc/paper/image files, so a markdown mirror yielded ZERO nodes; and manifest 'kind' was never consumed by the build. kind=docs now skips the AST pass and prints the changed-page worklist.

## Outcome

- Signal: useful

## Source Nodes

- docs/claude-code/goal.md
- docs/claude-code/hooks.md
- docs/claude-code/skills.md