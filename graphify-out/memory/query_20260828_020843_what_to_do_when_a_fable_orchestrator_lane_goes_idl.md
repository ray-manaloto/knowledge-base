---
type: "query"
date: "2026-08-28T02:08:43.200489+00:00"
question: "What to do when a fable-orchestrator lane goes idle without delivering its report, and why a background task notification's exit code cannot be trusted?"
contributor: "graphify"
outcome: "useful"
---

# Q: What to do when a fable-orchestrator lane goes idle without delivering its report, and why a background task notification's exit code cannot be trusted?

## Answer

Three lanes in one session (premise-verifier ×2, advisor — all fable-orchestrator plugin agents) went idle with NO report delivered; each `SendMessage("please resend your complete report")` recovered it within a minute. The report file on disk is the first check (read-only lanes have no Write, so absence proves nothing); the resend is the remedy. Also: a background Bash task's completion notification said `exit code 0` while the output FILE ended `rc=1` — the notification reports the last pipe stage. Read the file, never the notification. Both bit in session kb-20260827.07 on branch round/2026-08-27-aggregated-research-eval.


## Outcome

- Signal: useful