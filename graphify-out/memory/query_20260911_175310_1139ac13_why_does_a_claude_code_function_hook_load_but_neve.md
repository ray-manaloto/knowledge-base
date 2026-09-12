---
type: "query"
date: "2026-09-11T17:53:10.144522+00:00"
question: "Why does a Claude Code function hook load but never fire, and how is it actually enabled?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why does a Claude Code function hook load but never fire, and how is it actually enabled?

## Answer

Function hooks work on Claude Code 2.1.268. Two facts closed a blocker that had
read as "the hook is skipped silently":

1. A hooks module may import ONLY relative paths and "claude-code". Importing a
   node builtin (`node:fs`) makes the module fail to load. The engine DOES log it
   at ERROR level — `hooks module <name> failed to load: cannot import "node:fs"` —
   but only into the debug log; without `--debug-file <path>` it is surfaced via
   `$.ui.log` and is invisible in `-p` mode. So "no error anywhere" was an
   artifact of not running with a debug file, not a silent-skip behaviour.

2. The enablement gate is four terms, not one, and the binary ships readable
   names: enabled = (CLAUDE_CODE_ENABLE_FUNCTION_HOOKS ?? growthbook
   `tengu_plugin_hooks_modules`, default false) AND NOT
   shouldDisableAllHooksIncludingManaged() AND NOT isCustomizationDisabled("hooks")
   AND NOT shouldAllowManagedHooksOnly().

A project-scoped `.claude/settings.json` `env` block DOES set the flag in time —
armed with the variable absent from the process, 39 hook events still fired. This
refutes the prior research note that the gate might be read from process.env
before project config loads.

The status probe that was said not to exist: the debug log's seat line. With hooks
modules off it reads `sec-default@builtin not seated: hooks modules are off in
this process`; with them on it names a seating reason instead.

A `tool.call` hook returning `{ deny: "<reason>" }` blocks the call even under
--dangerously-skip-permissions, and the reason reaches the model.

TRAP: `tool.call` also fires for the assistant's own outgoing message (keys
message/status/tool/tool_use_id, versus command/description/tool/tool_use_id for
Bash). A substring match over the whole event JSON blocked the model's reply
because the reply quoted the sentinel token. Dispatch on `e.tool` and match the
specific field; never match the serialized event.


## Outcome

- Signal: useful