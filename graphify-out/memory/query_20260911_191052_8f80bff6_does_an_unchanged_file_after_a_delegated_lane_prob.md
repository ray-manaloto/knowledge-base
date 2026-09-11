---
type: "query"
date: "2026-09-11T19:10:52.564224+00:00"
question: "Does an unchanged file after a delegated-lane probe prove the guard denied it?"
contributor: "graphify"
outcome: "corrected"
correction: "A live-lane probe whose actor can DECLINE is not an arm.\n\nThree void arms in a row this session, each of which looked like a result:\n1. the nested session \"stopped short of the delegation\" — 0 attempts, read as a pass;\n2. the test repo's settings file carried no flag, so function hooks were off\n   entirely — module never loaded, no error, file unchanged, read as \"the guard\n   failed\";\n3. the lane SELF-REFUSED to edit `.claude/settings.json` and said so in its own\n   report — the unchanged file looked exactly like a successful deny.\n\nTwo cheap fixes, both now standard for this shape: assert in the same run that the\nmodule actually LOADED, so an off-flag arm announces itself instead of\nmasquerading as a result; and pick a target the lane has no reason to refuse\n(`mise.toml` is ordinary work, `.claude/settings.json` reads as something to\ndecline).\n\nThe related correction: I reported a folder-trust \"hole\" to Ray on the strength of\none documentation sentence. One arm refuted the strong form — the guard fired from\nproject settings in a never-trusted folder. A secondary source carried into a\nuser-facing report as a measurement is this repo's most-repeated defect, and it\ncost a correction that had already propagated.\n"
---

# Q: Does an unchanged file after a delegated-lane probe prove the guard denied it?

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

- Signal: corrected
- Correction: A live-lane probe whose actor can DECLINE is not an arm.

Three void arms in a row this session, each of which looked like a result:
1. the nested session "stopped short of the delegation" — 0 attempts, read as a pass;
2. the test repo's settings file carried no flag, so function hooks were off
   entirely — module never loaded, no error, file unchanged, read as "the guard
   failed";
3. the lane SELF-REFUSED to edit `.claude/settings.json` and said so in its own
   report — the unchanged file looked exactly like a successful deny.

Two cheap fixes, both now standard for this shape: assert in the same run that the
module actually LOADED, so an off-flag arm announces itself instead of
masquerading as a result; and pick a target the lane has no reason to refuse
(`mise.toml` is ordinary work, `.claude/settings.json` reads as something to
decline).

The related correction: I reported a folder-trust "hole" to Ray on the strength of
one documentation sentence. One arm refuted the strong form — the guard fired from
project settings in a never-trusted folder. A secondary source carried into a
user-facing report as a measurement is this repo's most-repeated defect, and it
cost a correction that had already propagated.
