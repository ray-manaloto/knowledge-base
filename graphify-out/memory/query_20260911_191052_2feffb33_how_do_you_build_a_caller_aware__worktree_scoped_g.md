---
type: "query"
date: "2026-09-11T19:10:52.165421+00:00"
question: "How do you build a caller-aware, worktree-scoped guard on Claude Code function hooks, and what are the real constraints?"
contributor: "graphify"
outcome: "useful"
---

# Q: How do you build a caller-aware, worktree-scoped guard on Claude Code function hooks, and what are the real constraints?

## Answer

Claude Code function hooks (the experimental `mods` surface) are usable today on
2.1.268 and can express caller-aware policy that no classic hook or native
`permissions.deny` rule can. Everything below was measured this session, both arms.

ENABLEMENT. The gate is four terms, not one:
`CLAUDE_CODE_ENABLE_FUNCTION_HOOKS ?? growthbook "tengu_plugin_hooks_modules"`
(default FALSE) `&& !shouldDisableAllHooksIncludingManaged() &&
!isCustomizationDisabled("hooks") && !shouldAllowManagedHooksOnly()`. A project
`.claude/settings.json` `env` block DOES set it in time — armed with the variable
absent from the process. The debug log's `sec-default@builtin` seat line is the
status probe: "hooks modules are off in this process" when off, a seating reason
when on.

THE LANE DISCRIMINATOR is `e.agentId` (camelCase) on a function-hook event. The
CLASSIC hook spells the same concept `agent_id` (snake_case) and that is what the
public docs show. A guard written from those docs reads the wrong field, gets
undefined on every call, concludes "main thread", and allows everything silently.
Absence is the ALLOW signal, so such a guard cannot fail closed.

LOADER CONSTRAINTS. Imports are relative paths plus "claude-code" only; a `.json`
import fails because every import is compiled as TypeScript, while a relative
`.ts` import works. `$` may not be READ as a value, though passing it to a local
function does work — the loader's error text overstates its own check.

A FAILED MODULE LOAD IS LOGGED AT ERROR, but only to the debug log; without
`--debug-file` the engine surfaces it via `$.ui.log`, which in `-p` mode goes
nowhere. That is why a prior session read this as a silent skip.

`{ deny: "<reason>" }` blocks a call even under `--dangerously-skip-permissions`,
and the reason reaches the model. But `tool.call` also fires for the assistant's
own outgoing message (tool `SendUserMessage`), so matching a pattern against the
serialized event blocks Claude's reply when the reply quotes the token. Dispatch
on `e.tool` and match one named field.

`$.process.run(argv, {cwd, stdin})` works, reaches mise-installed `uv`, costs
~175 ms for a real `kb-setup` call, and does NOT re-enter the hook chain. The
`stdin` option is decisive: every existing python guard reads its payload from
stdin, so a thin-shell hook passes it through unchanged.

WORKTREE SCOPING is implementable and implemented: `$.session.cwd()` plus
`$.fs.list()` (which reports `kind: "dir"|"file"`). A linked worktree's `.git` is
a FILE, a main checkout's a DIRECTORY.

THE STRUCTURAL LIMIT: function hooks are Claude-only. Codex runs its own classic
stack from `.codex/hooks.json`. So rewriting guards in TypeScript duplicates them
rather than moving them, and the policy must stay python if it is to bind both.

COLD START: on a cold plugin cache the marketplace installs AFTER the
plugin-loading pass, so a fresh clone yields one silently unguarded session.


## Outcome

- Signal: useful