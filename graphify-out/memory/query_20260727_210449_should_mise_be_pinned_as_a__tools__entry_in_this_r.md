---
type: "query"
date: "2026-07-27T21:04:49.607631+00:00"
question: "Should mise be pinned as a [tools] entry in this repo's mise.toml so currency can track it?"
contributor: "graphify"
outcome: "useful"
---

# Q: Should mise be pinned as a [tools] entry in this repo's mise.toml so currency can track it?

## Answer

No. It installs fine (both ubi:jdx/mise and aqua:jdx/mise resolve), but adding it moves which(mise) from ~/.local/bin/mise to the mise install dir — so the currency check then compares the pinned version against itself and reports IN SYNC forever, permanently blind to the drift it exists to catch. Measured, then reverted. mise CAN be a [tools] entry in general; it must not be one HERE, because here it is the tool being audited. What was shipped instead: min_version in mise.toml plus [tool.mise] in currency.toml tracking mise as a SELF-MANAGED tool (new expected + version_pattern fields on ToolSpec). Bumping 'expected' after reading release notes is what records the review. PR #47 (297de40, 5511084).

## Outcome

- Signal: useful