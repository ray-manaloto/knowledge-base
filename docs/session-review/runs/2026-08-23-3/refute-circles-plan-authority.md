# Refutation attempt — "plan-authority re-recorded SIX times, no task/function exists"

Lane: circles. Judged at HEAD `ff299734` on branch `clear-prep-2026-08-19b`.

## Probe 1 — the offered python grep could only ever return 0 (CONTROL-ARMED)

Offered: `grep -rn "reauthor|record_authority" python/src/kb_setup/*.py` -> 0.

Two independent bounds:
- **basic regex**: `|` is a LITERAL in BRE. Control arm, scratchpad file containing
  `def record_authority():`
  - `grep -rn "reauthor|record_authority" ctl.py` -> rc=1, no output
  - `grep -rEn "reauthor|record_authority" ctl.py` -> rc=0, matches line 1
  So the probe as written cannot match either token, even when both are present.
- **token spelling**: the operation's module is spelled
  `python/src/kb_setup/graphify_semantic_corpus_authority.py` — neither
  `reauthor` nor `record_authority`.

## Probe 2 — what actually exists

`git grep -n "semantic_slice_sha256"` (unbounded, tracked files):
- python/src/kb_setup/graphify_semantic_corpus.py:369, :727
- python/src/kb_setup/graphify_semantic_corpus_authority.py:80,158,413
- tests/test_graphify_semantic_corpus.py:790

`grep -nvE "^\s*#|^\s*$" python/src/kb_setup/graphify_semantic_corpus_authority.py`
-> only 5 code lines in a 428-line file: a docstring, 2 PROTOTYPE_*_SHA256
constants, and `AUTHORITY_JSON` (lines 422-428). **ZERO `def`/`class`**
(`grep -nE "^(def |class |    def )" …` -> rc=1, no output).

So: the module is DATA. The finding's *conclusion* (no function performs the
re-record) survives the broken probe.

## Probe 3 — CONTROL-ARMED search for a task or function (correct spelling, unbounded)

- `grep -cE "^\[tasks\." mise.toml` -> **75**; control `grep -nE "^\[tasks\.(kb-check|kb-arms)\]"`
  -> `427:[tasks.kb-arms]`, `451:[tasks.kb-check]` (probe discriminates).
  All task names matching `corpus|semantic|graphify|authorit|plan`:
  kb-graphify-contract(559), kb-graphify-baseline(563), kb-graphify-semantic-slice(567),
  kb-graphify-semantic-corpus(571), kb-graphify-semantic-corpus-merge(575),
  kb-ecosystem-discovery-plan(600). **None re-records.**
- `python/src/kb_setup/graphify_semantic_corpus.py:3123`:
  `if not args or args[0] not in {"plan", "run", "verify"}` — the CLI has no
  record/authorize action.
- `git grep -nE "graphify_semantic_corpus_authority\.py" -- '*.py'` -> **rc=1, 0 hits**.
  CONTROL: same shape on `graphify_semantic_corpus_run\.py` -> 3 hits. Probe
  discriminates. The only files naming the authority path are 4 markdown/json docs.
- Mechanism confirmed: `semantic_slice_sha256=_module_sha(graphify_semantic_slice)`
  (graphify_semantic_corpus.py:727) -> ExecutionConfig field (:369) ->
  `execution-config.json` -> `execution_config_sha256` (:1737, :2222) ->
  `AUTHORITY_JSON` (authority.py:424).

**The offered probe was broken; the corrected probe reaches the SAME answer.**

## Probe 4 — the count of SIX (three independent routes)

Transcript `773421d1-...jsonl`, tool_use commands touching the authority path or
the plan task (parsed, not grepped):
```
05:27:43Z Edit  graphify_semantic_corpus_authority.py
06:06:16Z heredoc re-record (7s) + 06:07:36Z replan+suite (464s)
06:16:35Z heredoc "re-recorded LAST, after the claude-version fix moved semantic_slice_sha256" (443s)
06:48:19Z heredoc "authority re-recorded (4th time), LAST as the rule now says"  (439s)
15:04:37Z heredoc "authority re-recorded LAST (5th)"                             (488s)
15:30:32Z heredoc "re-recorded: {...}"                                           (500s)
```
Route 2: the session's OWN labels reach "(5th)".
Route 3: `git log -1 a496f153` = 2026-08-19T10:39:08-05:00, message "Sixth re-record".
Route 4: `git log --all -- ...authority.py` shows FIVE commits on 2026-08-19
(48808f80, 74625faa, 3c1ae84b, 19946737, a496f153).
=> **SIX is corroborated. NOT refuted.**

## Probe 5 — "twice just a COMMENT": CONFIRMED, and more precisely than stated

- `git show --stat 87433191` (2026-08-19T15:03:35Z) touches
  `graphify_semantic_slice.py | 14 +++----`; the diff on that file is **comment
  lines only**. Re-record #5 followed **62 seconds later** at 15:04:37Z.
- a496f153's own message: "resolving the rebase conflict edited a COMMENT in
  `graphify_semantic_slice.py`" -> re-record #6.
(The third comment case the module cites, 31c63d4d, is 2026-08-16 — a prior round.)

## TWO EVIDENCE DEFECTS (neither flips the verdict)

1. **One cited timestamp is a false positive.** `16:06:05.668Z` is
   `cd …; cat > docs/direction/2026-08-19-ray-directives.md <<...` (7,145 chars),
   **tool_use -> tool_result delta 0s**. It is the commit of Ray's directive file,
   which QUOTES the heredoc verbatim (docs/direction/2026-08-19-ray-directives.md:68-82).
   It is not an execution. The real sixth event is 05:27:43Z/06:06:16Z, omitted.
   **Finding 6 inherits the same defect**: my `kb-graphify-semantic-corpus plan`
   scan returns exactly **TOTAL 8** — matching finding 6's "8 `plan` invocations"
   — and 3 of those 8 are non-executions (16:06:05 doc-write 0s, 05:37:57 7s,
   07:00:59 a `stat` 3s). Same grep, same over-count, two findings.
2. **"~48 minutes" does not reproduce and overstates by ~23%.** Measured
   tool_use -> tool_result: 464+443+439+488+500 = **2,334s = 38.9 min**; across ALL
   16 authority/replan commands in the round, **2,359s = 39.3 min** (upper bound).
   The finding's four cycles (454/461/514/516 = 32.4 min) match no route I could
   reproduce — the transcript carries no `durationMs` and `sentAt` is null on every
   one of these results.

## Verdict

**refuted: false.** Every load-bearing clause survives a corrected, control-armed
probe. The two defects are in the finding's *evidence rendering*, not its claim:
substitute 05:27:43Z for 16:06:05Z, and state ~39 min measured rather than ~48.
