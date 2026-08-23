# Refutation: "Bare `python3` is NOT denied by the PreToolUse hook"

VERDICT: REFUTED. Bare `python3` IS denied, end-to-end, on current HEAD 6fc28270.

## Probe (live hook entry point, exactly as wired in .claude/settings.json:29)
printf '{"tool_name":"Bash","tool_input":{"command":"python3 -c \"pass\""}}' \
  | uv run --project ./python kb-setup hookguard
-> {"hookSpecificOutput":{"permissionDecision":"deny","permissionDecisionReason":"Do not run `python3` directly — use `uv run python …` ..."}}

Also denied: `python3 foo.py`, `python -V`, `ls && python3 x.py`,
and `python3 - <<'PY' ... PY` (relevant to finding 16).

## Control arm (proves the probe discriminates)
- `ls -la`                 -> empty stdout (ALLOW)
- `uv run python -c "pass"`-> empty stdout (ALLOW)
- `graphify query "x"`     -> deny with a DIFFERENT reason (graphify redirect)

## Why the original probe could only say "not denied"
It read the guard tuple at hook_guard.py:289 literally and stopped there.
`_bare_python` is reached by delegation, not by membership in that tuple:
  hook_guard.py:289 `_graphify_redirect` -> :327 `return decide(command)`
  -> :162 `return _bare_python(command)` (last statement of `decide`, def at :124).
That is a scope bound on the read, the same class as a -maxdepth.

## Second route
tests/test_hook_guard.py:133-147 pins 9 denied bare-interpreter forms
(incl. `python3 - <<PY`, `cat f | python3 -`, newline-separated) and
:172-174 the allowed prose/`/usr/bin/python3` cases.

## Contradicts
Finding 9 records TWO real hook denials of bare `python3` in the reviewed
session (17:23:06Z, 17:47:37Z). MEMORY.md also lists bare `python3` under
"DENIED at the hook". Finding 15 is the broken probe of the pair.
Finding 16 (heredoc python3 "should have been denied but was not") is
likewise contradicted for the plain `python3 - <<TAG` form.
