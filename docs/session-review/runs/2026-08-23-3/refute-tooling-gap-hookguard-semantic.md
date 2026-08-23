# Refutation attempt — [tooling-gap] hook_guard has no redirect for graphify-semantic-corpus/slice

CLAIM: hook_guard.py has zero _REDIRECT coverage for 'graphify-semantic-corpus' or
'graphify-semantic-slice', even though matching mise tasks exist and wrap exactly these
`uv run kb-setup` calls; the direct form was used 5 times this session.

VERDICT: **NOT REFUTED** (claim stands, on four independent probes).

## 1. The original probe reproduced, WITH a control arm
$ grep -n "graphify-semantic-corpus\|graphify_semantic_corpus\|semantic-slice\|semantic_slice\|semantic" python/src/kb_setup/hook_guard.py
  rc=1 (0 hits)
CONTROL (same file, same command shape, token known present):
$ grep -n "_REDIRECT\|kb-setup\|kb_setup" python/src/kb_setup/hook_guard.py
  27,28,60,68,106,128,147,152,157,178,191,192,200,243,344,364,386  -> probe discriminates.
Note the grep was widened to the bare token `semantic` (spelling-bound removed): still 0.

## 2. FUNCTIONAL probe — not a grep. The whole hook chain, not just decide()
`uv run python` driving kb_setup.hook_guard.check_hook_call() with a real PreToolUse payload:
  'uv run kb-setup graphify-semantic-corpus'        -> Ok: None      (ALLOWED)
  'uv run kb-setup graphify-semantic-slice'         -> Ok: None      (ALLOWED)
  'uv run kb-setup graphify-semantic-corpus-merge'  -> Ok: None      (ALLOWED)
  'uv run kb-setup graphify-semantic-corpus --dry-run' -> Ok: None   (ALLOWED)
CONTROLS through the SAME entry point:
  'graphify query "x"'      -> Ok: "Do not run `graphify query` by hand. Use the mise task: mise run kb-query …"
  'uv run ruff check python/' -> Ok: "Do not hand-chain the gates. Use `mise run kb-check -- <paths>` …"
  'mise run kb-graphify-semantic-corpus' -> Ok: None (correctly allowed)
So the chain CAN deny a `uv run …` shape (check_first proves it) and does not deny this one.

## 3. The matching tasks exist and are real redirect targets
mise.toml:665-667  [tasks.kb-graphify-semantic-slice]  run = "uv run kb-setup graphify-semantic-slice"   timeout = "30m"
mise.toml:679-681  [tasks.kb-graphify-semantic-corpus] run = "uv run kb-setup graphify-semantic-corpus"  timeout = "16h"
The task accepts the same positional args the direct calls used
(`mise run kb-graphify-semantic-corpus -- plan <path>` observed 2026-08-17T11:29:45Z),
so the redirect target can perform the redirected action — not an "outage" redirect.
STRENGTHENS the finding: the direct form also bypasses the task's wall-clock hang guard
(30m / 16h), which mise.toml documents as sized from measured runs.

## 4. The "5 times this session" count is exact
Scan of ALL 253 transcripts in the project dir (no time bound, no head/limit), counting only
Bash tool_use blocks: 11 direct matches total; 6 in this session's transcript 6ae19ff6, of
which 1 (06:55:21Z) is a `cat >> .agent/notepad.md` heredoc MENTIONING the string, not an
invocation. The 5 real ones are at 06:50:22.750Z, 07:48:44.991Z, 08:28:24.736Z,
12:45:04.856Z, 13:24:41.906Z — byte-identical to the timestamps the finding cites.
Their tool_results show rc=0 real output (preflight JSON, `verify rc=0`, `plan rc=0`,
the dedupe line) — i.e. they EXECUTED; none was denied. Undercount if anything: bash #4 and
#5 each carry TWO direct invocations (plan + verify) in one command.
CONTROL for the same scan shape: `mise run kb-graphify-semantic-*` -> 116 hits. Probe discriminates.

## Only imprecision found (does NOT refute)
"_REDIRECT coverage" names the wrong repair site: `_REDIRECT` is keyed by graphify SUBCOMMAND
and is only consulted after `_GRAPHIFY_CMD` matches `graphify <sub>` at a command position
(hook_guard.py:37,68,145-147). An entry `"graphify-semantic-corpus": …` there could never fire
on `uv run kb-setup graphify-semantic-corpus`. The correct home is a new pattern in the
check_first mould. The ABSENCE the finding asserts is real; the mechanism word is loose.

## Contradiction check against the other 35 findings
None contradicts. #10 (`.venv/bin/python` and `python3 <script>.py` not denied while
`python3 -c/-m` are) is the same guard-coverage-hole class and corroborates: both are
"the guard matches a command WORD, and this invocation shape does not present that word".
#11 independently counts this session's manual command shapes and does not disagree.

## GitHub repos touched
_None._ (all evidence is local: this repo's tree + ~/.claude transcripts)
