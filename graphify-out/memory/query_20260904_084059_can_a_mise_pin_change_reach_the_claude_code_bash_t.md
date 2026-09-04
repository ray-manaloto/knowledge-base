---
type: "query"
date: "2026-09-04T08:40:59.576895+00:00"
question: "Can a mise pin change reach the Claude Code Bash tool without restarting the terminal?"
contributor: "graphify"
outcome: "useful"
---

# Q: Can a mise pin change reach the Claude Code Bash tool without restarting the terminal?

## Answer

YES — measured, not inferred, and the arm was run before the design was believed.

Every Bash tool call is a fresh `zsh -c` that re-sources
`~/.claude/shell-snapshots/snapshot-zsh-<id>.sh`. That file's LAST line is a
literal `export PATH='...'` captured once at session start (re-derived here:
1825 lines, last line begins `export PATH='`, exactly one `^export PATH=` in the
whole file). So a `mise use` mid-session cannot reach the Bash tool; the snapshot
re-asserts the old install directory before every command.

`CLAUDE_ENV_FILE` runs AFTER that re-source, so a PATH written there WINS.
Armed three ways, reading the result in a LATER Bash call:

  - marker absent                 -> the hook never ran -> conclude NOTHING
  - marker set, sentinel not in PATH -> the snapshot won -> reject
  - sentinel present              -> ship

Measured: `KB_ENV_PROBE=armed`, PATH position 1 = mise's shims dir, position 2 =
the `/__claude_env_probe__` sentinel. End to end, `command -v codex` moved from
`.../installs/npm-openai-codex/0.153.1/bin/codex` to `<shims>/codex` in the same
session with no restart.

THE DESIGN THAT SHIPPED is a SessionStart one-liner putting mise's SHIM directory
first -- not #702's body, which proposed regenerating `mise env` on FileChanged.
A shim is a symlink to the mise binary itself, never to a version-named path, so
one line stays correct across every future bump: nothing to regenerate, no PATH
growth, and no environment values copied into a file.

THE TRIGGER THAT DID NOT WORK, recorded because it cost a probe: wired as
`FileChanged` on a root file and appended to with the Bash tool, the hook did NOT
fire -- marker absent. The same hook as `CwdChanged`, fired with a `cd`, ran
immediately. Suspected cause (a watcher not started for a group added
mid-session) is UNVERIFIED.

The shims path is read from `mise doctor --json .dirs.shims` (0.14 s), never
hardcoded: a wrong hardcoded path writes a PATH entry that resolves nothing,
which looks exactly like a hook that worked.

`CLAUDE_ENV_FILE` is exposed ONLY to SessionStart/Setup/CwdChanged/FileChanged
(hooks.md:1219). On any other event the task exits 127, never 0.


## Outcome

- Signal: useful