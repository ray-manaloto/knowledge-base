---
type: "query"
date: "2026-07-22T18:21:37.641179+00:00"
question: "Are /subtask and /fork real Claude Code commands, and do they reset context like /clear?"
contributor: "graphify"
outcome: "corrected"
correction: "I and the claude-code-guide agent wrongly said /subtask and /fork don't exist. They ARE real v2.1.212+ commands; both INHERIT context (not a reset). The guide agent read stale docs."
source_nodes: ["cmd_subtask", "cmd_fork", "cmd_clear", "insight_command_context_inheritance"]
---

# Q: Are /subtask and /fork real Claude Code commands, and do they reset context like /clear?

## Answer

YES, both are real (v2.1.212+). /subtask <task> = a forked subagent that INHERITS the full conversation, runs in the background, and reports its result back. /fork [prompt] = copies the conversation into an independent background session (inherits everything up to now). BOTH inherit context — neither resets like /clear (empty context). /branch = foreground branch you switch into. Authoritative source: code.claude.com/docs/en/commands (now in the KB graph).

## Outcome

- Signal: corrected
- Correction: I and the claude-code-guide agent wrongly said /subtask and /fork don't exist. They ARE real v2.1.212+ commands; both INHERIT context (not a reset). The guide agent read stale docs.

## Source Nodes

- cmd_subtask
- cmd_fork
- cmd_clear
- insight_command_context_inheritance