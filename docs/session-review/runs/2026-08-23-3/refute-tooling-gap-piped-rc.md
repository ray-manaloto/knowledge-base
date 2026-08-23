# Refutation lane — tooling-gap #22: "36 of 39 piped `mise run` invocations discard the rc"

**Verdict: NOT REFUTED in substance. The two numbers are wrong and the corrected
figures are WORSE for the session, not better.** Corrected: **37 of 40**
tail/head-terminated `mise run` invocations discard the rc (38 of 41 if the one
`| grep | sed`-terminated mise pipeline is counted), 2 recover it correctly via
`${pipestatus[1]}`, 1 reads the wrong process via bare `$?`. **All 3
`mise run kb-ship` calls are in the discarded-rc group — confirmed by a second,
independent route.**

## Artifacts

- Primary (derived): `…/scratchpad/bash-cmds.jsonl` — 264 lines, one JSON object
  per Bash call.
- Primary (raw): `/Users/rmanaloto/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/f74823ff-3ee4-4b02-a2af-11106a762c9f.jsonl`
  (4.5 MB session transcript, never read into context — only grepped/jq'd).

**Completeness arm (the artifact is not bounded).** `jq` over the raw transcript
counts **264** `tool_use` blocks with `name == "Bash"`, all `isSidechain == false`
— exactly the 264 lines in `bash-cmds.jsonl`, and exactly the 264 `Bash` rows in
`tools.tsv`. Window `2026-08-23T09:43:28Z → 18:05:17Z`, the whole 8h22m session.
So the denominator is the session, not a slice of it.

## The offered evidence reproduces — and it reproduces two defects

```
$ grep -Ec 'mise run [a-z-]+.*\| ?(tail|head)' bash-cmds.jsonl      -> 39
$ grep -Fc pipestatus  <that 39-line subset>                        -> 2
$ grep -Fc '$?'        <that 39-line subset>                        -> 1
```
(Whole-file `pipestatus` = 9 lines and `$?` = 8 lines; the offered 2/1 are within
the 39-line subset. That reconciles — not a defect.)

### Defect 1 — the greedy `.*` matched heredoc PROSE (overcount, +2)

`bash-cmds.jsonl` stores each command as a JSON string, so an embedded newline is
the two characters `\n`. To `grep`, a 140-line heredoc command is **one line**, and
`mise run [a-z-]+.*\| ?(tail|head)` therefore matches when `mise run …` appears
*anywhere* — including inside prose being written to a file — and a `| tail`
appears anywhere later, on a **different** command.

Exactly two of the 39 are this:

| line | desc | what actually holds the pipe |
|---|---|---|
| 71 | "Prepend provenance annotation and re-lint" | `rumdl check … 2>&1 \| tail -4`; the `mise run kb-attribute-write` token is inside a `cat > /tmp/hdr.md <<'HDREOF'` prose block |
| 90 | "Append the execution log to the tracked plan" | `rumdl check … 2>&1 \| tail -5` — grepping that command's body shows the **only** `\| tail` occurrence is that line; every `mise run …` token is inside the `<<'PLANEOF'` prose |

This is the "a guard's false positives are text about the guard" class already in
MEMORY.md, arriving in a measurement instead of a guard.

### Defect 2 — LINES were counted as INVOCATIONS (undercount, −3)

`grep -c` counts matching lines. Three real invocations are invisible because they
share a line with another one:

- line 173 holds **2** (`kb-currency-check … | grep -i antigravity | head -3` and
  `kb-currency-check … | tail -6`)
- line 254 holds **3** (`kb-remember --question…`, `kb-reflect … | tail -4`,
  `kb-remember -- --audit … | tail -3`)

The two defects partially cancel: 39 stated ≈ 37 true lines / 40 true invocations.

## The corrected measurement

A heredoc-aware classifier (strip `<<'TAG'` bodies, split on `;`/`&&`/`||`/newline,
keep segments whose first command word chain is `mise run`, inspect the LAST pipe
stage) over the same 264 calls:

```
greedy-regex matching LINES (python, `.` not spanning \n): 37
true mise|tail/head LINES:        37
true mise|tail/head INVOCATIONS:  40
false positives (grep-only):      [71, 90]
missed by grep (true-only):       []          <- the regex missed nothing
other-piped mise invocations:     1   [line 259: … | grep -E … | sed …]
unpiped mise invocations:         7   [15, 27, 86, 114, 140, 151, 157]
captured via ${pipestatus[1]}:    2   [6 kb-currency-check, 252 kb-context]
captured (wrongly) via bare $?:   1   [5 kb-handoff-check]
discarded entirely:               37
kb-ship invocations:              3   [237 | tail -25, 245 | tail -30, 262 | tail -20]
```

**The `unpiped: 7` row is the negative control on the classifier** — it can and does
return "this one keeps its rc" (`mise run kb-build`, `mise run lint` ×3,
`kb-graphify-semantic-corpus -- run` ×2). A classifier that had only ever said
"discarded" would be a coin with one face.

## The kb-ship clause — confirmed by a second, independent route

Route 2 does not touch `bash-cmds.jsonl` at all:

```
$ jq -rc 'select(.type=="assistant") | .message.content[]?
          | select(.type=="tool_use" and .name=="Bash") | .input.command' <transcript> \
  | grep -n 'mise run kb-ship'
1263:mise run kb-ship 2>&1 | tail -25
1339:mise run kb-ship 2>&1 | tail -30
1660:mise run kb-ship 2>&1 | tail -20
```

Three, all piped to `tail`, none with a `pipestatus`/`$?` companion on the line.
**Control arm for this grep:** the same transcript greps to **67** hits for
`kb-check` and **49** for `kb-ship` (prose + commands), so the probe is not blind;
and the raw `"command":"…"` extraction independently returned the same three plus
five unrelated heredoc commands, so it discriminates command-position from prose.

## The mechanism is armed both directions (zsh 5.9, this shell)

```
false;            echo rc=$?                       -> rc=1
false | tail -1;  echo rc=$?                       -> rc=0        (tail's — discarded)
false | tail -1;  echo pipestatus[1]=${pipestatus[1]} -> 1        (recovered)
true  | tail -1;  echo rc=$? ps1=${pipestatus[1]}  -> rc=0 ps1=0  (control: not stuck at 1)
```

So `… | tail -N` really does erase the task's rc here, `${pipestatus[1]}`
really does recover it, and bare `$?` after a pipeline really is the LAST stage's
status — which makes line 5's `mise run kb-handoff-check 2>&1 | tail -30;
echo "=== rc=$? ==="` a reading of `tail`, exactly as the finding says.

## The claim is not vacuous — there is a real rc to discard

`python/src/kb_setup/pr.py:528 ship_main()` returns `1` on **9** distinct refusal
paths (`pr.py:532,539,543,554,616,625,656,687,703`; plus `363,389,396,116` in its
helpers). `mise run kb-ship` can and does exit non-zero; the pipe is what throws it
away. (Contrast `kb-currency`, which CLAUDE.md states always exits 0 — for that one
the pipe would cost nothing.)

## Contradiction check against the other 54 findings

- **#6** ("kb-ship refused twice on two different preconditions, discovered one at a
  time") is *consistent* with 3 kb-ship calls = 2 refusals + 1 success, and it also
  shows the discarded rc did not cause a false green: the refusals were read out of
  the tailed TEXT. Worth stating as a bound on #22's harm — what was lost was the
  machine-readable verdict, not the human-readable one.
- **#3** uses the same 264 denominator; consistent.
- **#11** (`python3 … 2>/dev/null || uv run python …` is hook-denied outright) was
  reproduced live in this lane — my first classifier run was DENIED by
  `kb_setup.hook_guard` with the bare-interpreter message, costing one call. Third
  occurrence of that shape, now including a verifier.
- Nothing in the set contradicts #22.

## What should change in the finding

Replace "36 of 39" with "**37 of 40**" (or 38 of 41 counting the `| grep | sed`
one at line 259), and note that the original figure came from a line-count of a
greedy regex over JSON-escaped newlines. The direction, the `$?` clause, and the
kb-ship clause all stand.

## GitHub repos touched

_None._
