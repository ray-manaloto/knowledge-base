# Refutation attempt — [contradicted] kb-check/kb-ship "real exit codes, no pipe"

CLAIM: mise-tasks-only.md:35 and long-running-command-hangs.md:71-74 state that
`mise run kb-check` / `kb-ship` give "real exit codes, no pipe" and were built
specifically to eliminate the anti-pattern of piping a gate into tail/grep and
discarding its rc.

VERDICT: **NOT REFUTED at its core** (kb-check half). Two sub-claims ARE refuted:
the kb-ship attribution, and the 82% figure.

## 1. The cited lines say what the finding says (kb-check only)

`grep -n 'real exit codes\|no pipe\|nothing in between' .claude/rules/*.md python/src/kb_setup/*.py mise.toml CLAUDE.md`

- `.claude/rules/mise-tasks-only.md:35` — "`mise run kb-check -- <paths>` — ruff +
  format + ty + the paths' own tests, **real exit codes, no pipe**. … that vacuum
  was filled 35 times in one session by a pipe that discards the gate's rc"
- `.claude/rules/long-running-command-hangs.md:72-74` — "real exit codes) or
  `mise run kb-gates` … Both are python holding a real `returncode`, with
  nothing in between to discard it."
- `mise.toml:451-458` (the task itself) — "every one of which returns the PIPE's
  exit code and **reports a failed gate as a success**."

Control arm for the grep: the same command returned hits in 4 different files
(mise-tasks-only.md, long-running-command-hangs.md, check_first.py, CLAUDE.md),
so it discriminates present from absent.

## 2. REFUTED sub-claim: kb-ship is not covered by either cited line

`grep -rn 'kb-ship' .claude/rules/long-running-command-hangs.md .claude/rules/mise-tasks-only.md`
→ long-running-command-hangs.md: **0 hits**. mise-tasks-only.md hits are lines
27/33/123/140/142/158 — none of them line 35, none saying "real exit codes".
Neither cited location makes the quoted claim about `kb-ship`.

Worse for the finding: the session's ONE real `kb-ship` invocation
(`git status --porcelain | head -3; mise run kb-ship > /tmp/ship.log 2>&1; echo
"kb-ship rc=$?"; tail -20 /tmp/ship.log`) **preserves** the rc via `echo "rc=$?"`
— it is the redirect form that long-running-command-hangs.md:74-76 explicitly
calls "correct for a command no task owns". It is not an rc-discarding pipe.
Ray's complaint about that line (directive 325-330) is about durable logging and
skill-wrapping, not about a lost exit code.

## 3. REFUTED sub-claim: the numbers. 82% is wrong; the truth is 95%

The offered evidence is a RAW STRING grep over the .jsonl, which counts prose,
the model's own narration, hook denial messages, and the verbatim directive text
stored by a heredoc — not invocations.

Reproduced the finding's probe exactly:
```
grep -o 'mise run kb-check[^"]*' <T> | wc -l        -> 49
grep -o 'mise run kb-check[^"]*' <T> | grep -c '|'  -> 40      (82%)
grep -o 'mise run kb-ship[^"]*'  <T> | wc -l        -> 16
                             ... | grep -c '/tmp/'  -> 3
```
Second route — actual `tool_use` Bash commands, via jq:
```
jq -r 'select(.message.content!=null) | .message.content[]?
       | select(.type=="tool_use" and .name=="Bash") | (.input.command|@json)' <T>
total bash tool_use: 256
containing kb-check: 39
kb-check AND a pipe: 37     (94.9%)
kb-ship invocations:  2  -> 1 real + 1 heredoc storing Ray's directive text
```
Sinks: `| tail` 21, `| grep` 16, `| head` 1. `pipestatus` appears in **0** of the
session's 256 commands, so none of the 37 preserved the rc.

Transcript: `~/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/6697269c-34d2-4355-948e-48b775449a73.jsonl`

## 4. CONTRADICTS finding 26 — and finding 26 is the correct one

Finding 26 states 37 of 39 (95%); this finding states 40 of 49 (82%). My jq probe
returns exactly 37/39. The defect is in THIS finding's probe (string hits, not
invocations). Finding 17 ("two hand-chained commands with pipe sinks") undercounts
the same population by an order of magnitude.

## 5. The structural half is CONFIRMED, control-armed

`uv run python -c "from kb_setup import check_first, hook_guard; ..."`:

| command | check_first.decide | hook_guard.decide |
|---|---|---|
| `mise run kb-check -- …/handoff_reconcile.py … 2>&1 \| tail -25` | None (ALLOW) | None |
| `mise run kb-ship > /tmp/ship.log 2>&1; echo "kb-ship rc=$?"; tail -20 …` | None (ALLOW) | None |
| `uv run ruff check python/src/kb_setup/handoff_reconcile.py` | **DENY** (full remedy text) | None |
| `uv run ty check python/src/kb_setup/x.py 2>&1 \| tail -5` | **DENY** | None |

The control arm proves the probe can return DENY. The guard therefore cannot
structurally prevent a piped `kb-check`, exactly as check_first.py's docstring
("A command containing `mise run kb-` is allowed outright") and
mise-tasks-only.md:87 say.

## GitHub repos touched

_None._
