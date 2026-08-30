# grep.app codesearch feasibility (#576)

Date: 2026-08-29

## Verdict

**FEASIBLE, conditionally.** An unauthenticated headless client can reach
grep.app through its Streamable-HTTP MCP endpoint at `https://mcp.grep.app`.
Each operation can be one JSON-RPC 2.0 HTTP `POST` with
`Content-Type: application/json` and
`Accept: application/json, text/event-stream`. The measured calls needed no
session ID, persistent connection, or MCP client library: a plain HTTP client
speaking the wire protocol was sufficient. That transport is compatible with
#568's existing decision to use `httpx2` for the other adapters.

The direct REST route at `https://grep.app/api/search`, which the website uses,
is not reachable from this client: every bogus, real, and browser-user-agent
attempt met the same HTTP 429 `Vercel Security Checkpoint`. That row is not the
feasibility test because it cannot distinguish a real request from a bogus one.
The feasibility evidence is the MCP `tools/call` pair: `useState(` returned a
real GitHub file, while `zzzqxnotarealidentifier9384756kb` returned the fixed
`No results found for your query.` string.

The split result is evidence of a **per-endpoint WAF rule**, not a network-level
or account-level block. The same unauthenticated client, machine, session, and
few-minute window reached `mcp.grep.app` cleanly while `grep.app/api/search`
blocked every request. Both endpoints are in the same `*.grep.app` host family.

## Method and evidence authority

This is a declared feasibility spike, not an adapter implementation. The live
measurements were made by the architect and persisted in
`.agent/kb/raw/codesearch-probe-2026-08-30.md`; this report transcribes that
session's authoritative readings rather than claiming a second measurement.
The transcript is dated 2026-08-30, while the sandbox-local `date` command
reported `2026-08-29 CDT`, which determines this report's filename and date.

Graph orientation was attempted first but was unavailable as authority. The
first repository-owned query failed before execution because `uv` could not
initialize `/Users/rmanaloto/Library/Caches/uv` and reported `Operation not
permitted (os error 1)`. A retry with an isolated `/tmp` cache reached
`kb-query`, which reported no graph at `graphify-out/graph.json` and directed the
caller to run `mise run kb-build`. No build was authorized for this Markdown-only
spike, so the named repository rules, implementation, generated model, schema,
and architect transcript are the declared fallback sources.

## Acceptance criteria

- [x] **1. The probe is control-armed: a bogus endpoint/query answers
  differently from a real one.** Evidence: the MCP `searchGitHub` call for
  `useState(` returned repository, path, URL, license, and code-snippet content
  from `mifi/lossless-cut`; the same `tools/call` shape with the near-certainly
  absent `zzzqxnotarealidentifier9384756kb` returned only
  `No results found for your query.`. These outcomes differ, so the MCP probe
  discriminates. The REST 429 pair does not satisfy this criterion.

- [x] **2. The bot-challenge behavior observed this session is reproduced or
  refuted, with evidence.** Evidence: it is **reproduced** for the direct REST
  route. A bogus query, real query, and browser-user-agent retry all returned
  HTTP 429, and the response body identified `Vercel Security Checkpoint`.
  Because real and bogus inputs received an identical result, this REST probe is
  non-discriminating by itself. Under
  `.claude/rules/probes-need-a-control-arm.md` Rule 4, **“A
  redirect/timeout/parse-error is not a ‘no’,”** this checkpoint “never asked”
  the reachability question; it did not “answer feasibility no.”

- [x] **3. The report states whether the adapter is feasible, infeasible, or
  feasible only under conditions.** Evidence: the verdict is **FEASIBLE,
  conditionally** through the unauthenticated Streamable-HTTP MCP endpoint, not
  through the bot-challenged REST route. The handshake, tool discovery, and
  discriminating real/bogus tool calls all succeeded without an MCP session ID.

- [x] **4. If infeasible, propose dropping the verb or an alternative source.**
  **Not applicable:** the verdict is not infeasible, because the control-armed
  MCP path returned a real result and a distinct null. There is therefore no
  basis in this spike to drop the future `codesearch` verb or replace grep.app.

- [x] **5. Findings are written to this tracked research report.** Evidence:
  `docs/research/reports/2026-08-29-codesearch-feasibility.md` is the persisted
  artifact and contains the commands and captured output needed to reproduce the
  probe.

## What the probe establishes

The MCP endpoint behaved as a stateless Streamable-HTTP server:

- bare `GET` returned 405;
- `POST` without the SSE-capable `Accept` header returned 406;
- a valid `initialize` request with both required headers returned HTTP 200,
  protocol version `2025-06-18`, and server name
  `mcp-typescript server on vercel`;
- a separate `tools/list` request, without `Mcp-Session-Id`, returned exactly
  one tool, `searchGitHub`; and
- separate `tools/call` requests, also without a session ID, returned the
  discriminating real/null pair.

`searchGitHub` declares required `query: string` plus optional
`matchCase: boolean`, `matchWholeWords: boolean`, `useRegexp: boolean`,
`repo: string`, `path: string`, and `language: string[]` parameters.

This is a one-session, one-machine, one-IP sample of approximately six live
calls. It demonstrates current reachability from that sample; it does not
guarantee indefinite availability, stable wire behavior, universal geographic
reachability, or freedom from future throttling.

## Future adapter requirements

Do not directly reuse the generated tracker `Null`, `Arm`, or `AdapterRecord`
types for a codesearch adapter:

- `Kind` is closed to `issue | pr`
  (`python/src/kb_setup/generated/research_record.py:22-26`, mirrored by
  `schemas/research-record.schema.json:45-48`), and the generated base struct
  forbids unknown fields (`research_record.py:11`).
- `AdapterRecord` requires `has_issues` and `has_discussions`
  (`research_record.py:59-71`), which have no meaning for code search.
- tracker validation hardcodes one arm per tracker channel from `{Kind.pr}` plus
  `Kind.issue` when enabled (`python/src/kb_setup/research/trackers.py:220-245`).
- tracker arm results must match `total_count=<integer>`
  (`trackers.py:22,240-245`), while grep.app returned prose content and a fixed
  prose null.

A future adapter therefore needs its own addition to
`schemas/research-record.schema.json` before it can emit a contract-shaped
record. The project codegen task must regenerate the corresponding model; the
future ticket must not introduce a hand-written struct.

The future implementation should reuse two **patterns**, not the tracker-specific
types:

1. Preserve the test seam used by `trackers.py`: a pure request/search path that
   accepts an injectable transport and clock (`trackers.py:70,154-158`). This
   makes real, null, malformed, and transport-failure arms independently
   testable.
2. Bound untrusted content before it enters a record. `trackers.py:109-113`
   truncates titles to 512 characters and snippets to 600. The observed
   `searchGitHub` response exposed code-snippet text with no endpoint truncation
   visible, so a consumer must treat it as unbounded; arbitrary public
   repositories can contain PII or secrets. A future adapter must apply an
   explicit size bound and safe normalization before persistence or display.

One transport choice remains unresolved for that future ticket:
`.claude/rules/research-doc-sources.md` prefers this repository's pinned
`mcp2cli` over native MCP registration for one-off lookups, but this spike used
raw `curl` and did not verify `mcp2cli` against a remote Streamable-HTTP URL. The
adapter-build ticket must test that path rather than assuming it works or
prematurely committing to raw HTTP.

## Explicitly out of scope

This spike does not build a production adapter. It does not add the `codesearch`
CLI verb, modify `python/src/kb_setup/research/cli.py`'s `_VERBS` tuple, modify
`python/src/kb_setup/cli.py`, change `schemas/research-record.schema.json`, run
code generation, or add generated types. Those actions belong to a future
adapter-build ticket after the schema and transport decisions above are made.

## Evidence appendix: exact curl transcript

The commands and outputs below are copied from the architect's authoritative raw
transcript without rerunning them in this sandbox.

### 1. Direct REST API — bogus vs real vs UA-retry

```
$ curl -sS -o /dev/null -w "http=%{http_code}\n" "https://grep.app/api/search?q=asdkjfhalskjdfhZZZ999notreal" --max-time 10
http=429

$ curl -sS -o /dev/null -w "http=%{http_code}\n" "https://grep.app/api/search?q=useState" --max-time 10
http=429

$ curl -sS -o /dev/null -w "http=%{http_code}\n" -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" "https://grep.app/api/search?q=useState" --max-time 10
http=429
```

All three identical — non-discriminating. Per
`probes-need-a-control-arm.md` rule 4, this is "never asked", not "answered
no".

### 2. Response body on one call (confirms the WAF identity)

```
$ curl -sS -H "Accept: application/json" -H "Referer: https://grep.app/" "https://grep.app/api/search?q=useState" --max-time 10
http=429
<!DOCTYPE html>...<title>Vercel Security Checkpoint</title>...
```

### 3. MCP endpoint — handshake

```
$ curl -sS -o /dev/null -w "http=%{http_code}\n" "https://mcp.grep.app" --max-time 10
http=405   (bare GET)

$ curl -sS -o /dev/null -w "http=%{http_code}\n" -X POST -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"0.1"}}}' \
    "https://mcp.grep.app" --max-time 10
http=406   (POST without the SSE-capable Accept header)

$ curl -sS -w "\nhttp=%{http_code}\n" -X POST \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"0.1"}}}' \
    "https://mcp.grep.app" --max-time 15
event: message
data: {"result":{"protocolVersion":"2025-06-18","capabilities":{"tools":{"listChanged":true}},"serverInfo":{"name":"mcp-typescript server on vercel","version":"0.1.0"}},"jsonrpc":"2.0","id":1}
http=200
```

### 4. tools/list — no session id required

```
$ curl -sS -X POST -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
    -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' "https://mcp.grep.app" --max-time 15
event: message
data: {"result":{"tools":[{"name":"searchGitHub", ... "inputSchema":{"type":"object","properties":{
  "query":{"type":"string"},
  "matchCase":{"type":"boolean","default":false},
  "matchWholeWords":{"type":"boolean","default":false},
  "useRegexp":{"type":"boolean","default":false},
  "repo":{"type":"string"},
  "path":{"type":"string"},
  "language":{"type":"array","items":{"type":"string"}}
},"required":["query"],"additionalProperties":false}}]},"jsonrpc":"2.0","id":2}
```

Full parameter types (per the returned `inputSchema`): `query: string`
(required), `matchCase: boolean`, `matchWholeWords: boolean`,
`useRegexp: boolean`, `repo: string`, `path: string`, `language: string[]`.

### 5. tools/call — the control arm

```
$ curl -sS -X POST -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
    -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"searchGitHub","arguments":{"query":"useState(","language":["TypeScript"]}}}' \
    "https://mcp.grep.app" --max-time 20
event: message
data: {"result":{"content":[{"type":"text","text":"Repository: mifi/lossless-cut\nPath: src/renderer/src/hooks/useUserSettingsRoot.ts\nURL: https://github.com/mifi/lossless-cut/blob/master/src/renderer/src/hooks/useUserSettingsRoot.ts\nLicense: GPL-2.0\n\nSnippets:\n--- Snippet 1 (Line 54) ---\n  const [lastAppVersion, setLastAppVersion] = useState(...)..."}]}}

$ curl -sS -X POST -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
    -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"searchGitHub","arguments":{"query":"zzzqxnotarealidentifier9384756kb"}}}' \
    "https://mcp.grep.app" --max-time 20
event: message
data: {"result":{"content":[{"type":"text","text":"No results found for your query."}],"isError":false},"jsonrpc":"2.0","id":4}
```

Real query returns real content (repo/path/license/snippets, unbounded length);
bogus query returns a fixed "no results" string. Discriminates.

### Disambiguation of REST and MCP outcomes

Both hit the same host family (`*.grep.app`) from the same machine, same session,
within the same few minutes. The REST path was blocked on every attempt; the MCP
path succeeded on every attempt. This is evidence that the block is
endpoint-specific—a WAF rule on the REST route—not network-level: the same
client reached the same provider's other endpoint cleanly.

## GitHub repos touched

- [mifi/lossless-cut](https://github.com/mifi/lossless-cut) — appeared as a real hit in the searchGitHub control-arm probe.
