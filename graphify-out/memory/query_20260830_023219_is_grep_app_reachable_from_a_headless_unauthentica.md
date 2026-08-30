---
type: "query"
date: "2026-08-30T02:32:19.921654+00:00"
question: "Is grep.app reachable from a headless unauthenticated client, for the future codesearch adapter (#576/#568)?"
contributor: "graphify"
outcome: "useful"
---

# Q: Is grep.app reachable from a headless unauthenticated client, for the future codesearch adapter (#576/#568)?

## Answer

FEASIBLE, conditionally. grep.app is reachable from a headless, unauthenticated
client via its MCP endpoint (https://mcp.grep.app, plain JSON-RPC 2.0 HTTP POST,
no auth, no session ID) — confirmed with a discriminating control arm
(real query -> real GitHub content, bogus query -> fixed null string). The
direct REST API (grep.app/api/search) is blocked by a per-endpoint bot-challenge
WAF that returns an identical 429 for real and bogus queries alike — reproduced,
but explicitly labeled non-discriminating rather than as an answer, per
probes-need-a-control-arm.md rule 4. A future codesearch adapter cannot reuse
trackers.py's generated Null/Arm/AdapterRecord types directly (Kind is closed to
issue|pr, required has_issues/has_discussions fields don't apply, arm shape is
tracker-specific) -- it needs its own schema addition. Recorded in
docs/research/reports/2026-08-29-codesearch-feasibility.md (PR #621), with the
chain updated in PR #622.


## Outcome

- Signal: useful