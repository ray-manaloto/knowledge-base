---
type: "query"
date: "2026-09-03T05:44:38.904498+00:00"
question: "How many tools does the hosted graphify MCP advertise, now that we can authenticate to it?"
contributor: "graphify"
outcome: "useful"
---

# Q: How many tools does the hosted graphify MCP advertise, now that we can authenticate to it?

## Answer

# Hosted graphify's MCP surface, measured authenticated (2026-09-03)

24 tools, not the 23 that every record carried from 2026-08-17.

    ADDED since 2026-08-17: graphify_render_subgraph, memories_about
    REMOVED:                ingest_turns

`memories_about` had been recorded as proposed-but-unverified, absent from every
evidence set the August lane could reach — and that lane's control arm was
correct (`ingest_turns` returned hits from the same corpus). It was an honest
bounded negative, and it is now retired by evidence rather than by argument.
The bound was not the search; it was authentication.

HOW IT WAS MEASURED, and why a tool count needs two arms.

There is no CLI that prints a hosted tool count. The number comes from the
client's own registry after its `tools/list` handshake, so you ask the client,
not the network: list the `mcp__graphify__*` names and the `mcp__kb__*` names,
sort each, `comm` them.

CONTROL ARM — the same session listing reports `kb` at exactly 10, which matches
the count fixed independently by the pinned source
(`python/src/kb_setup/mcp_serve.py:4`, "10 tools + 6 resources
unconditionally"). A listing that agrees with an independent count on one server
is not silently truncating the other. Without this arm the 24 would be a number
read off a list with no way to know the list was complete.

LIVENESS ARM — `mcp__graphify__list_workspaces` answered: workspace
`ray-manaloto`, plan Pro, role owner, `boundVia: token_claim`. Then
`mcp__graphify__list_repositories` returned 15 repositories, among them
`ray-manaloto/knowledge-base` at `status: ready`, `queryable: true`, 13,152
nodes. A registration that exists is not a server that answers, and the August
attempt failed at exactly that point (HTTP 401).

TWO FURTHER FIGURES MOVED, both recorded as moving rather than re-pinned:

- Hosted's corpus is not "this repo's own files" in the singular. It holds 15
  indexed repositories for this workspace; this repo is one of them.
- Hosted's index for this repo was 13,126 nodes at commit `295955dbeb84` and is
  13,152 today. It re-indexes, so any single figure goes stale by design.

WHY THIS TOOK TWO ROUNDS TO ANSWER. The August lane could not authenticate; its
own session's `graph_stats` was refused by approval policy; and its second
attempt was blocked by that same round's newly added `codex_lane` guard, which
denied raw `codex exec` and routed to `mise run kb-codex`, whose project config
pointed at the local server. Three independent blocks, none of them the question
being unanswerable.


## Outcome

- Signal: useful