---
type: "query"
date: "2026-09-12T13:43:29.934155+00:00"
question: "Is a generated declarations file stable enough to hash as a gate?"
contributor: "graphify"
outcome: "useful"
---

# Q: Is a generated declarations file stable enough to hash as a gate?

## Answer

A generated type-declaration file can be ENVIRONMENT-dependent, not just
version-dependent — so no content hash of it can ever be a gate.

Measured twice on 2026-09-12, independently (an advisor lane, then me), same
`claude` 2.1.269 binary, one variable (`HOME`):

              real HOME        empty HOME
  rc          0                0
  claude-code.d.ts   9,263     9,156       (different sha)
  claude-code-mcp.d.ts 2,588   10

The tool's own log explains it: "30 built-in tools / 170 MCP tools from 12
servers" vs "24 built-in tools / no MCP tools connected". The declarations
enumerate the MACHINE's connected tool inventory alongside the version's API.

Two consequences that decided #754's design:

1. **Compare the CONSUMER-REQUIRED SET, never the file.** Every token the mod
   actually reads is environment-STABLE — `tool.call`, `agentId`, `file_path`,
   `notebook_path`, `Edit`/`Write`/`NotebookEdit`, `session.authorize` all
   identical across both arms; two control tokens 0 everywhere. So the small
   extracted set gates cleanly where the whole file cannot.
2. **Extract that set mechanically, never author it.** A hand-written contract
   encodes `agent_id` from the docs, while the runtime field is `agentId` — and
   absence reads as ALLOW, so the guard fails open silently.

Also settled: `/plugin-types` needs **no credentials** (rc 0 with HOME pointed at
an empty temp dir), which is what lets the check sit in the gates at all without
breaking the hermeticity precedent `guard_codegen` set for pytest-reachable work.


## Outcome

- Signal: useful