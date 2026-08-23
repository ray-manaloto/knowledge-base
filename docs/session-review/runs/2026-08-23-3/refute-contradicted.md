# Refutation lane — finding [contradicted] #13 (hook_guard "tokenises")

CLAIM: mise-tasks-only.md claims the graphify-command guard "tokenises (shlex)...
a quoted message is one token and can never sit at a command position," but
hook_guard.py's _GRAPHIFY_CMD/_CMD_POS is a bare regex; a literal `|` inside a
quoted grep alternation is read as a separator, causing a false deny.

VERDICT: **REFUTED as stated** (the doc-vs-code contradiction is a misattribution),
while the BEHAVIOUR half is true and reproduced. The real contradiction is with a
CODE COMMENT, not with mise-tasks-only.md.

## 1. The doc never makes that claim about the graphify guard

`.claude/rules/mise-tasks-only.md`:
- Enforcement layer **1** (lines 50-55) = the graphify guard. Text: "A raw
  `graphify <sub>` at a command position ... is DENIED". No tokenise/shlex claim.
- The "tokenises (`shlex`)" sentence is at **line 92**, inside **item 2a**, whose
  first line (line 76) is: "**The SAME hook also denies a HAND-CHAINED GATE**
  (`kb_setup.check_first`, Ray's ruling 2026-08-17)." The whole paragraph is
  scoped to check_first, and its justification names ruff: "because a regex sees
  `ruff check` inside `git commit -m ...`".
- The only other hit, line 119, is item **2c** (`absent_binary`) saying it
  "Shares `check_first`'s tokeniser".
- `grep -rn "tokenis\|shlex" .claude/ CLAUDE.md AGENTS.md docs/` returns exactly
  those 4 lines in rules (rest are 2026-08-18 session-review artefacts).

The finding's own evidence sentence ("shlex is used only in check_first.py") is
what the doc already says. No contradiction.

## 2. The doc's claim about check_first is TRUE — probed, same alternation shape

    check_first.decide('git commit -m "fixed ruff check here"')   -> None
    check_first.decide('grep -n "foo\|ruff check" x.txt')          -> None   <-- the exact shape
    check_first.decide('uv run ruff check python/')                -> "Do not hand-chain the gates..."

So the guard the sentence describes does not have the defect the finding
attributes to that sentence. Control arm present (real gate denies).

## 3. The BEHAVIOUR half is real — armed both directions, live and in-process

In-process (`uv run python`, kb_setup resolved from
/Users/rmanaloto/.../python/src/kb_setup/hook_guard.py — verified via `__file__`):

    hook_guard.decide('git log --follow -p -- .claude/settings.json | grep -n "hook-guard search\|graphify hook-guard" | head -20')
      -> 'Do not run `graphify hook-guard` by hand — drive graphify through a mise task...'
    hook_guard.decide('git log --follow -p -- .claude/settings.json | grep -n "hook-guard search" | head -20')
      -> None                          # CONTROL: same command, alternation removed
    hook_guard.decide('echo "run graphify query later"')            -> None   # CONTROL
    hook_guard.decide('grep -n "foo\|graphify query" file.txt')     -> deny (kb-query)
    hook_guard.decide('graphify add https://example.com')           -> deny   # CONTROL true-positive
    hook_guard.decide('graphify explain "foo"')                     -> None   # CONTROL allowed

Live through the real PreToolUse hook, this session:

    $ printf 'x\n' | grep -c "foo\|graphify query"
    <DENIED> Do not run `graphify query` by hand. Use the mise task: mise run kb-query ...
    $ printf 'x\n' | grep -c "foo graphify query"      # CONTROL, no pipe
    0        (rc=1, i.e. it EXECUTED)

## 4. Where the contradiction actually is (re-file here)

- `python/src/kb_setup/hook_guard.py:36-37` — comment: "`graphify` as a command
  word, **not the substring inside a URL/arg or a quoted mention**." Line 38 is
  `_GRAPHIFY_CMD = re.compile(_CMD_POS + r"graphify\s+([a-z][a-z-]*)", ...)`,
  which is refuted by the probe above. A comment defending the line below it.
- `_code_only()` (strips heredocs + quoted spans, written after "four measured
  false positives in five minutes") is applied **only** in `_bare_python`
  (`_BARE_PYTHON.search(_code_only(command))`, ~line 246); `decide()` runs
  `_GRAPHIFY_CMD.search(command)` on the RAW string.
- `tests/test_hook_guard.py:61` asserts the quoted-mention exemption with
  `'grep -r "graphify label" .'` — a fixture with no `|`, so it cannot exhibit
  the bug. Bounded fixture, probes-need-a-control-arm.md rule 3.

## 5. Cross-finding contradiction

**Contradicts finding 14** ("three denied-by-design graphify commands executed
uncontested ... under confirmed-active bypass-permissions mode"). This agent is a
Workflow-spawned subagent under bypass permissions and the graphify deny fired
live (§3), blocking the Bash call outright. Whatever happened in finding 14, the
guard is not globally inert here.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under review.
