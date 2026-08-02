---
type: "query"
date: "2026-08-02T16:03:26.272417+00:00"
question: "Does mise run kb-serve actually serve MCP, and can the advertised tool surface be narrowed?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does mise run kb-serve actually serve MCP, and can the advertised tool surface be narrowed?

## Answer

NO — it served nothing until 2026-08-02. mise reads a task's stdio BY LINE rather than connecting it, so the stdio MCP server hit EOF on its first read and exited rc=0 with empty stderr. Control matrix on the same 393MB graph: mise run kb-serve = no reply/exit 10.4s; graphify-mcp on the 3.4MB prose graph = 0.6s/10 tools; graphify-mcp on the 393MB graph = 9.8s/10 tools; mise run --raw kb-serve = 10.8s/10 tools. The 3.4MB-vs-393MB pair prices the graph load at ~9.2s, which is why the broken arm's 10.4s exit read as a slow start rather than a dead server. Fix is the mise builtin task property raw = true. Nothing caught it because every existing check asks whether the TASK is defined and a task exiting 0 passes them all. Narrowing: no --tools flag or env gate in graphify 0.9.31 or 0.9.32 (control-armed), and Claude Code has NO client-side per-tool filter — only server-level toggles — so a server-side allowlist is the only lever. Surface is 10 tools + 6 resources, 5828 B of schema vs 118 B of names; under Claude Code's DEFAULT deferred tool search only names load (~30 tokens), but ENABLE_TOOL_SEARCH=false, a custom ANTHROPIC_BASE_URL, Bedrock, Google Cloud Agent Platform and Microsoft Foundry all load schemas upfront and pay the full 5828 B.

## Outcome

- Signal: useful