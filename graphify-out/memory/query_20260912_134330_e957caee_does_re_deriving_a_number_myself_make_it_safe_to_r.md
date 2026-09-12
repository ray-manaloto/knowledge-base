---
type: "query"
date: "2026-09-12T13:43:30.341443+00:00"
question: "Does re-deriving a number myself make it safe to report?"
contributor: "graphify"
outcome: "corrected"
correction: "I said \"+1,297 lines is real\" after verifying it myself. The TOTAL was right and\nthe ATTRIBUTION was wrong: version-only is **+1,190**, and **+107** is this\nlaptop's MCP tool inventory. I measured correctly and dropped the CONDITION.\n\nThe rule already existed — `verify-before-advancing.md` § \"Carry a fact's\nCONDITION, not just its source\" — and having re-derived the number myself made me\nMORE confident, not less, because re-derivation feels like the end of the\nchecking rather than the start of it.\n\n**What would have caught it, and cost one command:** ask what ELSE could produce\nthis delta, then vary that thing. One `HOME` swap. I never asked, because the\nnumber agreed with the ticket's, and agreement between two readings of the same\nconfounded setup is not corroboration.\n\nGeneralises: **re-deriving a number confirms the measurement, never the\nattribution.** A figure is only as good as the variable you held fixed, and\n\"I measured it myself\" says nothing about which variables you did not vary.\n"
---

# Q: Does re-deriving a number myself make it safe to report?

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

- Signal: corrected
- Correction: I said "+1,297 lines is real" after verifying it myself. The TOTAL was right and
the ATTRIBUTION was wrong: version-only is **+1,190**, and **+107** is this
laptop's MCP tool inventory. I measured correctly and dropped the CONDITION.

The rule already existed — `verify-before-advancing.md` § "Carry a fact's
CONDITION, not just its source" — and having re-derived the number myself made me
MORE confident, not less, because re-derivation feels like the end of the
checking rather than the start of it.

**What would have caught it, and cost one command:** ask what ELSE could produce
this delta, then vary that thing. One `HOME` swap. I never asked, because the
number agreed with the ticket's, and agreement between two readings of the same
confounded setup is not corroboration.

Generalises: **re-deriving a number confirms the measurement, never the
attribution.** A figure is only as good as the variable you held fixed, and
"I measured it myself" says nothing about which variables you did not vary.
