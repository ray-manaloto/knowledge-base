---
type: "query"
date: "2026-08-28T02:30:03.627234+00:00"
question: "Does a SendMessage resend reliably recover a fable-orchestrator lane's report after it goes idle without delivering it?"
contributor: "graphify"
outcome: "corrected"
correction: "The reliable recovery is the agent's TRANSCRIPT on disk, not a resend: `~/.claude/projects/<project>/<session-id>/subagents/agent-a<name>-<hash>.jsonl` holds every assistant text block; `jq -rs '[.[] | select(.type==\"assistant\") | .message.content[]? | select(.type==\"text\") | .text | select(test(\"<report heading>\"))] | last'` returns the final report verbatim (v4: 20 KB, v5: 31 KB, both intact, both had been written in full). Sequence now: idle notice with no report → look for the transcript FIRST, one resend at most, never wait on a second. Probe trap met on the way: `find -newermt '2026-08-28 01:30'` returned nothing for every file because local time was still 2026-08-27 21:xx CDT — the idle-notice timestamps are UTC; `-mmin -120` worked.\n"
---

# Q: Does a SendMessage resend reliably recover a fable-orchestrator lane's report after it goes idle without delivering it?

## Answer

Belief held at the start of session kb-20260827.07 (from the prior handoff and the auto-memory): when a fable-orchestrator lane goes idle without delivering its report, a `SendMessage("resend your report")` recovers it. It did for `premises-trackers-v2` and `premises-trackers-v3` (and the advisor). It did NOT for `premises-trackers-v4` (two resends, three idle notices) or `premises-trackers-v5` (one resend, two idle notices). The belief was a sample of two.


## Outcome

- Signal: corrected
- Correction: The reliable recovery is the agent's TRANSCRIPT on disk, not a resend: `~/.claude/projects/<project>/<session-id>/subagents/agent-a<name>-<hash>.jsonl` holds every assistant text block; `jq -rs '[.[] | select(.type=="assistant") | .message.content[]? | select(.type=="text") | .text | select(test("<report heading>"))] | last'` returns the final report verbatim (v4: 20 KB, v5: 31 KB, both intact, both had been written in full). Sequence now: idle notice with no report → look for the transcript FIRST, one resend at most, never wait on a second. Probe trap met on the way: `find -newermt '2026-08-28 01:30'` returned nothing for every file because local time was still 2026-08-27 21:xx CDT — the idle-notice timestamps are UTC; `-mmin -120` worked.
