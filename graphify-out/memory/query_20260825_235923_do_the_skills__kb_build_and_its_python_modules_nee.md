---
type: "query"
date: "2026-08-25T23:59:23.846034+00:00"
question: "Do the skills, kb-build and its python modules need changing to run extraction on openai-cli instead of claude-cli?"
contributor: "graphify"
outcome: "useful"
---

# Q: Do the skills, kb-build and its python modules need changing to run extraction on openai-cli instead of claude-cli?

## Answer

The round asked whether switching graphify's extraction backend from claude-cli
to openai-cli required changes to the skills, the kb-build mise task, and the
python modules it calls. The answer is no on all three, and the real blocker was
somewhere else entirely.

kb-build has no LLM backend to switch. Its own task description reads
"deterministic, no LLM": it clones each pinned source, AST-extracts code for
free, and replays the already-committed sources/extractions chunks. grep for
`backend` in its module returns nothing.

There are three separate LLM paths and only one carries a --backend knob. The
host-agent fan-out (kb-add -> subagents -> chunks -> kb-merge) is what actually
produces corpus chunks, and Claude Code itself is the model there, so there is
no provider call to redirect; kb-extract.js has zero backend mentions.
graphify_native_extract already accepts --backend openai-cli with both guards,
shipped in 118032e4 (PR #514, merged, 8/8 arms died). kb-label --claude-cli is
opt-in and already broken upstream with a deterministic fallback.

The actual blocker is at the graphify->codex boundary and is a fork defect.
Before calling codex, graphify disables the caller's MCP servers so extraction
does not boot them. It asks codex for the list (10 on this machine), then sends
one disable-override per name. Only 5 have a real [mcp_servers.NAME] entry in a
config file; the other 5 are registered by codex plugins. An override naming a
server with no entry creates a table carrying neither command nor url, and codex
rejects the entire configuration with "invalid transport". Every prose
extraction therefore dies in about three seconds, before spending anything.

Two-arm split, same flags, same env, same cwd, differing only in the names sent:
the 5 config-defined names returned rc 0; the 5 plugin-only names returned rc 1
with the invalid-transport error. Reproduced outside graphify entirely, driving
codex directly.

A control arm established that the fork itself is healthy: a code-only
extraction through the forked CLI with --backend openai-cli returned rc 0 and
wrote 45 nodes, 67 edges and 12 communities. Code needs no provider, so that run
exercised the fork without touching the broken path.


## Outcome

- Signal: useful