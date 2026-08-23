# Refute lane: "Session invoked `python3 - <<'PY'` (heredoc file edits) which should have been denied but was not"

## Probe 1 — does the guard deny that shape on current HEAD?

```
uv run python - <<'EOF' ... hook_guard.decide(...)
'TARGET heredoc'             -> DENY   code_only= 'python3 - '
'known-denied control'       -> DENY   code_only= 'python3 -c  '
'known-ALLOWED control'      -> ALLOW  code_only= 'uv run python -c  '
'allowed control'            -> ALLOW  code_only= 'mise run kb-check -- x.py'
```
Guard DENIES. So if the session really ran a bare `python3 - <<`, either the hook
was not wired, or it WAS denied and the finding misread the transcript.

## Probe 2 — what actually happened in the reviewed session

Session `6697269c-34d2-4355-948e-48b775449a73` (the one `unpinned.md` names at
line 3). Parsed with `uv run python` over the jsonl (never read into context):

```
TOTAL Bash tool_use: 256
--- ARM A: bare python at command start (1) ---
"python3 - <<'PY'\nimport re, pathlib\np = pathlib.Path('python" | is_error= True
   | Do not run `python3` directly — use `uv run python …`, or th
--- CONTROL ARM B: uv run python heredoc (23), first 3 ---
'uv run python - <<\'PY\'...' | is_error= False | 7 test rows written
'uv run python - <<\'PY\'...' | is_error= False | inserted before [tasks.kb-session-state]
'uv run python - <<\'PY\'...' | is_error= False | 4 Err narrowings
```

Raw record (transcript line 244):
`"is_error":true`, `"toolDenialKind":"permission-rule"`,
`timestamp":"2026-08-18T17:23:06.332Z"`, content = the verbatim `_REASON_BARE_PY`.
It NEVER RAN. Total bare-python denials in the session: **2**; commands matching
the guard's own command-position pattern that were NOT denied: **0**.

## Probe 3 — the lane's stated root cause is false

`unpinned.md:77-84` claims `_bare_python()` "is only called from `decide()`" and
is "NOT in this chain". `hook_guard.py:162` is the last line OF `decide()`:
`return _bare_python(command)` — the fall-through for every non-graphify command.
`decide()` IS the chain.

Live control arm, unplanned: this lane's own `grep -rln "…python3 - <<'PY'" .`
was itself DENIED by the guard mid-investigation (guard false positive on a
quoted search pattern) — proof the rule is wired and firing at runtime.

## Verdict: REFUTED. Contradicts finding #9 (which is correct: 17:23:06Z denial).
