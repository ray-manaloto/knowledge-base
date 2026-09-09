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

  ⚠️ **AND THAT LAST CLAUSE CUTS BOTH WAYS — "narrow" means ADVERTISE, not
  forbid.** Because `tools/call` is never intercepted, a tool hidden from
  `tools/list` still EXECUTES when called by name: measured 2026-09-09 with
  `KB_MCP_TOOLS="query_graph,get_node"`, `graph_stats` was absent from the
  advertised 2 and `tools/call graph_stats` still returned
  `Nodes: 359146 / Edges: 807085`. The allowlist is a context-cost and
  model-steering measure, never access control. It does not change the verdict —
  B is still impossible, for the same reason — but the `narrowed to N` banner
  reads like a capability boundary and is not one.
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
`graphify/__init__.py:6-24` (the entries themselves run `:7-23`) and **`query` is
not in it**. `_build_server` (`serve.py:1543`) registers TOOL HANDLERS that are
closures nested inside it, and those handlers call MODULE-LEVEL private helpers —
`_query_graph_text` (`serve.py:1197`) and `_pick_seeds` (`serve.py:666`), both
defined at column 0 and both ABOVE `_build_server`. So D cannot reach parity
without reimplementing ~1,000 lines, and it flipped to C by its own rule.

⚠️ **Both citations in the previous sentence were corrected by a cold review of
the commit that recorded them** (2026-09-09, two P3s). The map was cited as
`:5-22`, which lands mid-dict; and the helpers were described as *"a closure
nested inside `_build_server`"*, which they are not — the closures are the
handlers, the helpers are module-level functions those closures call. The
CONCLUSION is unchanged, because what makes D unreachable is that the helpers are
`_private` and absent from the public map, not where they sit in the file. Kept
verbatim rather than silently rewritten: the argument was right and two of its
three supporting details were wrong, which is the shape worth remembering.

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