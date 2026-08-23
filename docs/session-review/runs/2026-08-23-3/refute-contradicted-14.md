# Refutation lane — finding 14 (graphify hand-run deny "did not fire" in this session)

## Live control arm (2026-08-21 ~15:5xZ, THIS session 6ae19ff6, Workflow/Agent-spawned
subagent, bypass-permissions mode confirmed active by the harness system prompt)

A `grep` whose *pattern string* contained `&& graphif<y> query` was DENIED at the
PreToolUse hook, output verbatim:

    <error>Do not run `graphify query` by hand. Use the mise task: mise run kb-query --
    "<question>". All graphify work goes through a mise task (KB CLAUDE.md; enforced by
    kb_setup.hook_guard).</error>

=> The guard IS live for a Workflow-spawned subagent under bypass-permissions mode in
this very session. It even fires on a *mention* inside a grep pattern (the known
false-positive class).

## Transcript search so far
- `grep -rc '"command":"graphify ' <session tree>` -> 0 files (control: `mise run
  kb-graphify...` -> 421+133+... hits, so the probe discriminates).
- No `graphify update .` anywhere under this session's tree; the only `"command":"graphify
  update` in ~/.claude/projects is a DOTFILES transcript from 2026-08-05.

## VERDICT: REFUTED — the hook fired; the guard's regex has a NEWLINE hole

### The bytes the lane's own probe dropped

Every one of the four live commands was issued as a MULTI-LINE Bash string with
`cd <repo>` on line 1 and the graphify call at the start of line 2. Extracted from
the lane's own transcript
(`.../6ae19ff6-.../subagents/workflows/wf_96e07424-fdb/agent-a36c04b30cfd1ec4a.jsonl`):

  line  98  2026-08-21T15:45:03.764Z  "cd <repo>\ngraphify query \"test\" 2>&1; echo \"rc=$?\""
  line 110  2026-08-21T15:46:36.513Z  "cd <repo>\ngraphify query \"another test probe\" 2>&1 | head -5; ..."
  line 113  2026-08-21T15:47:38.284Z  "cd <repo>\necho ...\ngraphify label --help 2>&1 | head -3; ..."
  line 126  2026-08-21T15:48:20.551Z  "cd <repo>\ngraphify update . 2>&1 | head -5; echo \"rc=$?\""

The standalone probe the lane calls its "second control arm" fed the guard
`graphify query "test"` WITHOUT the leading `cd <repo>\n`. The two payloads are not
identical, and that difference is the entire outcome.

### hook_guard.py:34 — `_CMD_POS` has no `\n`

  _CMD_POS = r"(?:^|[;&|]|&&|\|\||\bthen\b|\bdo\b)\s*(?:(?:env\s+)?(?:\w+=\S*\s+)*)"
  _GRAPHIFY_CMD = re.compile(_CMD_POS + r"graphify\s+([a-z][a-z-]*)", re.IGNORECASE)   # :38

`^` is not MULTILINE, and the separator class is `[;&|]` only. A graphify call at the
start of any line but the first is therefore NOT "at a command position" as this regex
defines it. (The sibling `_BARE_PYTHON`, :185, DOES carry `\n` — its comment records
the same hole being measured and closed for that class only.)

### Both arms, run against the installed module

`uv run python` over `kb_setup.hook_guard.decide`, exact live strings vs joined forms:

  LIVE-1 'cd <repo>\ngraphify query "test" 2>&1; echo "rc=$?"'   -> None   (ALLOW)
  LIVE-2 'cd <repo>\ngraphify query "another test probe" ...'    -> None   (ALLOW)
  LIVE-3 'cd <repo>\necho ...\ngraphify label --help ...'        -> None   (ALLOW)
  LIVE-4 'cd <repo>\ngraphify update . 2>&1 | head -5; ...'      -> None   (ALLOW)
  CONTROL-A 'graphify query "test"'                              -> 'Do not run `graphify query` by hand...'
  CONTROL-B 'cd <repo>; graphify query "test"'                   -> 'Do not run `graphify query` by hand...'
  CONTROL-C 'cd <repo> && graphify update .'                     -> 'Do not run `graphify update` by hand...'

### Why the sibling guard fired on the same multi-line command

`stage_explicitly.py:74` tokenises with
`shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n")` — **`\n` is in its
punctuation set**. So `cd <repo>\ngit add -A` denies while `cd <repo>\ngraphify update .`
does not. The asymmetry the lane read as "a dispatch-level hole for Workflow subagents"
is one character of difference between two regex/lexer definitions in the same process.

### The hook chain IS live for a Workflow subagent under bypass-permissions

Live, this session, this lane (Workflow-spawned subagent, bypass mode active):
a `grep` whose PATTERN contained `&& graphify query` was DENIED at PreToolUse:

  <error>Do not run `graphify query` by hand. Use the mise task: mise run kb-query --
  "<question>". ... enforced by kb_setup.hook_guard.</error>

(recorded at agent-a327aa075d0c95a85.jsonl line 54, 2026-08-21T15:56:31.231Z).

### What survives

TRUE: the four commands ran. REAL DEFECT: `_CMD_POS` (hook_guard.py:34) treats a
newline as ordinary whitespace, so any `graphify <sub>` on line >= 2 of a multi-line
Bash call is allowed — and multi-line is this repo's ordinary shape.
REFUTED: the stated cause. Nothing about bypassPermissions, subagent dispatch, hook
load, or the two-hook interaction is implicated; the guard was asked and answered
"allow". `mise-tasks-only.md`'s sentence is scoped to "a raw `graphify <sub>` at a
command position", and by the guard's own definition of command position these were
not at one.

### Cross-check against the set
Finding 13 (same lane) already establishes `_GRAPHIFY_CMD` is a bare regex over the raw
string. It PREDICTS this mechanism; joined to finding 14 it yields the newline hole
rather than a bypassPermissions story. No other listed finding contradicts this.
