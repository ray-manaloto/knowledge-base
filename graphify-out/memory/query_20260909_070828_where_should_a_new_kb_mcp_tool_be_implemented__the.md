---
type: "query"
date: "2026-09-09T07:08:28.916801+00:00"
question: "Where should a new kb MCP tool be implemented: the graphify fork, the mcp_serve relay, or a third server?"
contributor: "graphify"
outcome: "useful"
---

# Q: Where should a new kb MCP tool be implemented: the graphify fork, the mcp_serve relay, or a third server?

## Answer

Three options were weighed on #681 and an advisor consult added a fourth, then
ruled it out on its own stated flip condition.

- **A — patch our graphify fork.** Viable, and cheaper to develop against than
  assumed: `sources/graphify/` IS the installed fork rev (`157a957e`,
  `v0.9.53-8-g157a957`), so there is no clone/install skew. It buys the graphify
  circle — 8 pin sites, a bump that is never one line.
- **B — inject through `kb_setup.mcp_serve`'s relay.** IMPOSSIBLE AS BUILT, and
  now probed live rather than read. Three arms: unfiltered -> 10 tools;
  `KB_MCP_TOOLS=query_graph` -> exactly 1, a strict subset; an allowlist naming a
  tool graphify does not serve -> **0 tools, never a new one**. The middle arm is
  the control that makes the third an answer instead of a broken probe. The relay
  only ever narrows an existing `tools/list` and never answers a `tools/call`.
- **C — a third stdio server (CHOSEN).** No fork patch, no pin bump, no permanent
  relay in the data path.
- **D — compose in-process** by importing graphify's `_build_server` and
  appending a tool. Blocked by the pinned **mcp 2.0.0**, which binds handlers in
  the `Server` CONSTRUCTOR rather than by decorator, so they cannot be re-bound
  afterwards. It also reaches a `_private` name, against the standing
  `sdk-over-cli-never-internals` call.

The advisor reached D first and then tested its own flip condition — "flip to C
if even one required behavior needs `_private` access" — against the code.
graphify's public SDK is a 17-name lazy `__getattr__` map at
`graphify/__init__.py:5-22` and **`query` is not in it**; every read-tool is a
closure nested inside `_build_server` over private helpers
(`_query_graph_text:1197`, `_pick_seeds:666`). So D cannot reach parity without
reimplementing ~1,000 lines, and it flipped to C by its own rule.

**Three names is not #668.** That outage was a registration-key COLLISION: a
GLOBAL `mcp_servers.graphify` URL entry against this repo's PROJECT stdio entry
of the same name, which stopped codex booting outright (`url is not supported for
stdio`). Distinct names do not reproduce it.

**What #681 got wrong, and it made the work smaller.** It flagged as unverified
"how a second stdio server wires into `mise run kb-serve`'s task shape". It does
not wire into it at all — both clients spawn the binary directly (`.mcp.json`,
`.codex/config.toml:126-128` both say `uv run kb-setup …`), so `[tasks.kb-serve]`'s
`raw = true` hazard (mise reading stdio BY LINE, the #105 silent-serve bug) is not
on the registration path. The mise task is a convenience for humans.


## Outcome

- Signal: useful