# Refutation attempt — lane `tooling-gap`: python-heredoc bulk source surgery

CLAIM: "Bulk source-file surgery (read -> str.index/replace slice -> write) is
repeatedly done via throwaway `uv run python - <<'PY'` heredocs instead of the Edit
tool, 20 times in one session, and no guard catches the pattern even though the habit
is already a recorded lesson."

## 1. The count re-derived (and its bound tested)

```
$ SP=/private/tmp/claude-501/-Users-rmanaloto-.../scratchpad
$ grep -c "uv run python - <<" $SP/bash_cmds_52f5798a.txt
20
$ grep -o "uv run python - <<" $SP/bash_cmds_52f5798a.txt | wc -l
20
```
Line-count and occurrence-count agree, so `grep -c` was not undercounting
multi-hit lines. Line numbers: 836, 880, 889, 900, 949, 1132, 1147, 1190, 1287,
1327, 1374, 1473, 1527, 1595, 1772, 1801, 2043, 2060, 2117, 2137.

Token-spelling bound tested — see section 4.

## 2. Are the 20 really "read -> index/replace -> write" surgery? YES, 20/20

Dumped every block with
`awk '/uv run python - <</{inb=1} inb{print} /^PY$/{inb=0}'`. Every one of the 20
opens with `pathlib.Path(...)` + `.read_text()`, mutates by `s.index(...)`/
`s.replace(...)`/slice concatenation, and ends with `.write_text(s)`.

TRACKED files edited this way (not scratch):
- `python/src/kb_setup/graphify_semantic_corpus.py` (block 1)
- `tests/test_graphify_semantic_corpus.py` (block 2)
- `python/src/kb_setup/graphify_semantic_corpus_authority.py` (blocks 5, 11)
- `docs/direction/2026-08-18-ray-directives.md` (blocks 6, 7, 14, 15, 16)
- `.claude/rules/clean-git-state.md` (block 8)
- `.claude/workflows/session-review.js` (blocks 9, 12)
- `tests/test_stage_explicitly.py` (block 13)

Untracked/outside-repo targets: `.agent/kb/arms/corpus-chunk1-findings.toml`
(3, 4, 10), `.agent/plans/session-2026-08-18-a.md` (19, 20), and
`~/.claude/projects/.../memory/MEMORY.md` (17, 18).

=> The finding's descriptive half is CONFIRMED, not refuted.

## 3. "No guard catches the pattern" — armed both directions

CONTROL (a command the guard is known to deny):
```
$ printf '%s' '{"tool_name":"Bash","tool_input":{"command":"git add -A"},"cwd":"<repo>"}' \
  | uv run --project python kb-setup hookguard
{"hookSpecificOutput": {... "permissionDecision": "deny", ... "Do not stage with a blanket `git add`..."}}
rc=0
```
TEST (a heredoc doing exactly the surgery in question, targeting a tracked file):
```
$ printf '%s' '{"tool_name":"Bash","tool_input":{"command":"uv run python - <<PY\nimport pathlib\np = pathlib.Path(\"python/src/kb_setup/arms.py\")\ns = p.read_text()\ns = s.replace(\"foo\",\"bar\")\np.write_text(s)\nPY"},"cwd":"<repo>"}' \
  | uv run --project python kb-setup hookguard
(no output)
rc=0
```
The probe discriminates (control denies, test allows). So the "no guard" half is
also CONFIRMED against the repo's own PreToolUse guard.

## 4. Token-spelling bound — tested, and it goes AGAINST the finding's own number

The offered probe `grep -c "uv run python - <<"` is a spelling bound. Variants,
same file, same command shape (control `grep -c "git "` -> 102, so the probe
discriminates):

| token | hits |
|---|---|
| `uv run python - <<` | 20 |
| `uv run python <<` | 0 |
| `python3 - <<` | **1** |
| `uv run python -c` | 18 |
| `<<'PY'` | 20 |
| `write_text(` | **22** |

`write_text(` at line 78 is OUTSIDE the 20 heredocs (first heredoc is line 836).
The command containing it (`sed -n '60,80p'`) is:

```
python3 - <<'EOF'
import pathlib
p = pathlib.Path("python/src/kb_setup/check_first.py")
s = p.read_text()
s = s.replace("        words = _consume_flags(words[1:])\n...")
p.write_text(s)
EOF
```

A 21st instance, on a TRACKED source file, under a different spelling. The true
count is **>=21, not 20** — the bound understated the finding.

## 5. The advisory detector that DOES exist would stay silent on 17 of the 20

`python/src/kb_setup/session_reflect.py:212-224` defines `mutation-harness` as
`r"(?:read_text|\.replace\(|write_text)"` **with `also=r"pytest|subprocess\.run|rc="`**.
Simulating that `also` clause per block:

```
BLOCK 1..12,16..20: no also-token (detector SILENT)
BLOCK 13,14,15:     ALSO-MATCH (would fire)
```

17 of 20 carry no `pytest`/`subprocess.run`/`rc=` token, so `kb-session-reflect`
would not even flag them advisory-only. (Approximation caveat: I applied the
`also` regex to the block text with awk rather than invoking `session_reflect`;
labelled as such.) This makes "no guard catches the pattern" STRONGER than the
finding states, not weaker.

## 6. What the finding gets WRONG — two material corrections

**(a) It is a DUPLICATE of an already-open ticket, and the lane report explicitly
denies that.** `iter1/tooling-gap.md:122` states "So this is a real enforcement
gap, **not a duplicate of an existing guard**."

```
$ gh issue view 239 --json number,title,state,labels
{"labels":["enhancement"],"number":239,"state":"OPEN",
 "title":"Guard the heredoc-edits-a-source-file shape explicitly, pointing at the Edit tool"}
```
The user memory the finding itself cites names #239 in its own body
(`~/.claude/projects/.../memory/bulk-text-edits-belong-in-the-edit-tool.md`:
"That mis-routing is what **#239** ... is for"). Filing this as a new issue would
duplicate #239.

**(b) An unconsidered confounder: the runtime instruction ACTIVELY ASKS for this
in bypassPermissions mode.** Session `52f5798a` ran 100% in that mode:
```
$ grep -o '"permissionMode":"[a-zA-Z]*"' 52f5798a-...jsonl | sort | uniq -c
  11 "permissionMode":"bypassPermissions"
```
The current runtime injects, verbatim, under that mode: *"While bypass
permissions mode is active: Do your work through the Bash tool wherever it can
accomplish the job: read files with cat, head, or sed -n, search with grep and
find, and **make file changes with sed, heredocs, or short scripts, rather than
using the dedicated Read, Edit, or Write tools.**"* (observed directly in this
verifier's own context, same project, same mode).

Whether 52f5798a received that exact text is NOT provable from the transcript,
and the negative is un-armable: system-reminders are essentially not persisted
(`grep -o "system-reminder" 52f5798a.jsonl` -> 2, and `"Do your work through the
Bash tool"` -> 0 across ALL 236 transcripts, while the control
`"MANDATORY: graphify-out/graph.json exists"` -> 128 files, so grep-over-jsonl
discriminates). The string is also absent from the local binary
(`grep -ac "rather than using the dedicated Read, Edit, or Write tools"
/Users/rmanaloto/.local/share/claude/versions/2.1.234` -> 0, control
`bypassPermissions` -> 139), so it is server-side and unverifiable locally.

Consequence for the REMEDY, not the fact: a #239-style PreToolUse deny pointing
at `Edit` would directly contradict an instruction the platform injects while
bypassPermissions is active. That conflict must be resolved in the ticket, and
neither the finding nor #239 mentions it.

## VERDICT: NOT REFUTED

Every factual element re-derived and held; the one bound I could test (token
spelling) moved the count UP. Two additions the finding owes: it duplicates open
issue **#239**, and its proposed remedy collides with the bypassPermissions
runtime instruction.
