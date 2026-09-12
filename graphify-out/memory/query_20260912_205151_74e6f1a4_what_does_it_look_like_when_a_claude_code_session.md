---
type: "query"
date: "2026-09-12T20:51:51.218677+00:00"
question: "What does it look like when a Claude Code session fills its context window, and what actually fills it?"
contributor: "graphify"
outcome: "useful"
---

# Q: What does it look like when a Claude Code session fills its context window, and what actually fills it?

## Answer

A session that fills its context does not fail loudly — it stops mid-sentence and
leaves no note.

Measured on session `3b921834` (2026-09-12), to the millisecond, from the raw
transcript records:

| time (UTC) | record |
|---|---|
| 19:27:06.000 | its last commit lands clean |
| 19:27:09.678 | the commit's tool_result returns successfully |
| **19:27:09.699** | `{"type":"assistant","content":["Prompt is too long"]}` |
| 19:27:51 | a `/clear`, 42 seconds later |

No further tool calls. No summary. No handoff message. **No code work was lost** —
the commit landed and a handoff file was already on disk. What was lost is the
turn that would have said what happened and what was next, and that cost the NEXT
session seven `/grilling` rounds (27 answers) to reconstruct.

**What filled it was VOLUME, not bloat.** Byte census of the 7,978,235-byte
transcript: assistant 43%, harness attachments 28%, tool results 25%. The largest
single tool result was 166,769 bytes and the next was 52,881 — no smoking gun.
**965 assistant turns and 287 Bash calls** is the whole story: ~3.6 KB per turn,
two to three attachment records per Bash round-trip, over 5h29m.

Two attachment line items are OURS and are pure overhead:
- the output-style reminder, repeated **441 times** (59.5 KB)
- the graph-first hook's "MANDATORY" reminder, **220 times**, attached to nearly
  every Bash call regardless of whether a graph query had already run

**The operational rule this yields:** `mise run kb-context` is a MEASUREMENT and
the standing 20% call is a soft trigger nothing enforces. That session ran its
large self-audit at 19:26 — sixty seconds before it had no room left. The cheap
half of the remedy is to commit the handoff EARLY, which that session did by luck
rather than by design.

`agentsview health` graded this session **`outcome: completed`, `health_score: 92`,
grade A**, with `peak_context_tokens: 975372`. It cannot detect this failure: its
`outcome` keys on ending with an assistant message, and `health_score_basis` has
no term for unfinished work.


## Outcome

- Signal: useful