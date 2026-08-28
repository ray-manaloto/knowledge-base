---
type: "query"
date: "2026-08-28T06:16:27.853759+00:00"
question: "What is the aggregated-research plugin, what shipped in slice 1, and what did the plugin round learn? (2026-08-28)"
contributor: "graphify"
outcome: "useful"
---

# Q: What is the aggregated-research plugin, what shipped in slice 1, and what did the plugin round learn? (2026-08-28)

## Answer

The aggregated-research plugin is a CLI (firecrawl's shape: skills → Bash → a separately installed CLI → file-isolated output under .research/) plus a marketplace plugin that declares firecrawl/exa/context7/last30days, bundles the spine skill, two agents, a SessionStart hook that fetches the pinned CLI release into $CLAUDE_PLUGIN_DATA, .lsp.json entries for ty/pyrefly (only the first .py server starts — Ray's call), and a stdio MCP server 1:1 with the CLI (mcp 2.1.1, spec 2026-07-28, FastMCP→MCPServer). Manifests carry schemastore $schema and are validated (no standalone hooks schema; hooks shape lives in the settings/plugin-manifest schemas; no fixed `version` — it strands users). Definition of done: an autonomous install in a mise-OCI-built Linux container (GHA, mise-action v4.3.0) by a Claude Code agent reading only the published docs, env vars named per dependency. Slice 1 landed as PR #562: `aggregated-research trackers OWNER/REPO <term> --out PATH` (kb_setup.research.cli → kb_setup.cli.main, import boundary held), live-armed against jdx/hk. Lessons: the research should have run THROUGH the plugin (build the named tool first); #559 recurred (n=2) — treat every codex-implementer diff as Claude-authored until PROCESS shows a reaped codex group; `.research/` needed a gitleaks allowlist (the .firecrawl/ class); page corrections on a code branch trip the funnel gate. openai/codex-plugin-cc is the app-server transport in production: no per-turn timeout, shared daemon — recommendation A (codex exec + --output-schema + resume) stands.


## Outcome

- Signal: useful