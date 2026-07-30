---
type: "query"
date: "2026-07-30T01:41:51.747998+00:00"
question: "Is graphify 0.9.26's kb-serve installable from a fresh clone?"
contributor: "graphify"
outcome: "useful"
---

# Q: Is graphify 0.9.26's kb-serve installable from a fresh clone?

## Answer

No. A fresh resolve of graphifyy[all]==0.9.26 picks mcp 2.0.0, which cannot start the MCP server (ImportError: cannot import name 'AnyUrl' from 'mcp.types'). 0.9.30 pins mcp>=1,<2 and starts rc=0. This host's pre-existing 0.9.26 env holds mcp 1.28.1 and works, so it was an invariant-3 reproducibility failure, never a live outage. TWO PROBES THAT LOOK CONCLUSIVE AND ARE NOT: 'import graphify.serve' and '--help' both exit 0 under the broken combination because the mcp imports are lazy (inside _build_server); only actually starting the server fails. And graphify swallows the real error and re-raises 'ImportError: mcp not installed' while mcp IS installed at the wrong major.

## Outcome

- Signal: useful