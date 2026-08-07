---
type: "query"
date: "2026-08-07T08:26:50.848266+00:00"
question: "What is the complete Claude Code slash-command catalog, and which commands are user-invocable only?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["claude_commands_doc", "insight_orchestration_surface", "insight_user_invocable_only", "insight_command_availability_is_conditional", "cmd_goal", "cmd_loop", "cmd_schedule", "cmd_workflows", "cmd_batch"]
---

# Q: What is the complete Claude Code slash-command catalog, and which commands are user-invocable only?

## Answer

104 commands (13 bundled skills, 1 bundled workflow, 3 removed) now extracted in full — previously only 7 were in the graph: `cmd_clear`, `cmd_compact`, `cmd_branch`, `cmd_fork`, `cmd_subtask`, `cmd_background`, `cmd_resume`.

**7 of the 10 orchestration commands were missing, not all 10** — `/background`, `/fork` and `/subtask` were already present; `/goal`, `/loop`, `/schedule`, `/workflows`, `/tasks`, `/batch` and `/deep-research` were not. (Corrected after cold review round 1, finding 4, which checked the superseded chunk rather than taking the claim: `jq '.nodes[]|select(.id|startswith("cmd_"))|.id' sources/extractions/claude-commands-docs.json` returns seven.) That orchestration set is what a pull-loop scheduler design must reason about.

On user-invocable-only commands, the graph now carries **only what this doc says**: `insight_user_invocable_only` records the doc's own L38 claim that `/verify` and `/code-review` "run only when you invoke them. Before v2.1.215, Claude could also run them on its own."

⚠️ **The supporting BINARY probe is deliberately NOT in this graph.** An external byte-probe of the Claude Code 2.1.224 CLI confirmed `disable-model-invocation` is a real skill frontmatter field the binary reads, and that a per-command determination could NOT be extracted from it. That evidence is not a derivation of `commands.md`, and every node in this chunk declares `commands.md` as its `source_file` — so putting it here would have made the structured provenance contradict the label. Cold review round 2 (finding 1) caught exactly that, and the node was **removed rather than re-tagged**. The probe lives in `ray-manaloto/dotfiles` — see the commit that closed #625 and `.agent/kb/review/reports/review-*-cold.md`.

**The lesson, which is the durable part:** a label that says "not from this source" does not fix a `source_file` that says it is. Provenance is structured or it is decoration.

**Why the gap persisted, and where that is checkable:** background node `fdfdaf90` proposed the full pass in its `suggestedReply` on 2026-07-22, blocked, and nothing surfaced it until `ray-manaloto/dotfiles#602`'s NEEDS_HUMAN projection landed 16 days later. That evidence is in the **dotfiles** repo, not this one — see `ray-manaloto/dotfiles#623` (the escalation comment, payload verbatim) and `ray-manaloto/dotfiles#625` (the resulting ticket). Cold review round 1, finding 5, correctly flagged this as uncitable from inside this repo; the citation is now explicit rather than self-asserting.

## Outcome

- Signal: useful

## Source Nodes

- claude_commands_doc
- insight_orchestration_surface
- insight_user_invocable_only
- insight_command_availability_is_conditional
- cmd_goal
- cmd_loop
- cmd_schedule
- cmd_workflows
- cmd_batch