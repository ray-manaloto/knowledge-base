# Refutation lane: "forgotten" — MEMORY.md compaction (#454)

CLAIM: "#454: Ray's explicit decision ('generate the index from description:
frontmatter') has survived 4+ rounds unbuilt, and the file is now at 95.5% of
its hard read limit (23,864 of 24,985.6 bytes, 1,121 B headroom) after this
session's own kb-reflect grew it further with no compensating compaction."

## Probes run (in order)

1. `wc -c MEMORY.md` = **23864** — CONFIRMED.
2. `gh issue view 454` — OPEN, created **2026-08-22T21:13:57Z (TODAY)**.
   Body states "22.3 KB against a 24.4 KB hard read limit and a 17.1 KB target".
3. Repo-wide grep for `24985|24\.4 KB|24_985|17\.1 KB` (properly quoted, all
   file types, unbounded depth) -> **0 hits outside sources/ and graphify-out/**.
   CONTROL ARM: same grep shape for `kb-review` in .claude/rules/ -> 3+ hits.
   So the probe discriminates; the 24.4 KB figure has no repo-side source.
4. `python/src/kb_setup/md_budget.py:21` -> the corpus DOES carry MEMORY.md's
   cap ("5 for MEMORY.md's cap" over code.claude.com/docs/llms-full.txt).
5. mtimes:
   - MEMORY.md                       2026-08-22 22:28:27
   - graphify-out/reflections/LESSONS.md (kb-reflect output) 2026-08-22 22:26:43
   - a-commit-after-the-handoff-is-invisible-to-the-receipt.md 22:28 (auto-memory)
6. `mise.toml:971-975` `[tasks.kb-reflect]`
   `run = "graphify reflect --graph {{config_root}}/graphify-out/graph.json"`
   -> writes INSIDE THE REPO only. It cannot write ~/.claude/projects/**/memory/.

## Findings so far

- ATTRIBUTION IS WRONG: kb-reflect does not and cannot write MEMORY.md.
  MEMORY.md changed 1m44s AFTER LESSONS.md, in the same minute as a new
  auto-memory lesson file — i.e. the MODEL's auto-memory write, hand-edited.
  Set item #8 says the session "hand-edited MEMORY.md twice" — DIRECT
  CONTRADICTION with #9's "kb-reflect grew it".
- "Ray's explicit decision ... survived 4+ rounds": Ray's GENERATE decision is
  first recorded in `.agent/plans/session-2026-08-22-e.md:165`
  ("Ray's call recorded: GENERATE the index from each memory"), carried in
  `-f.md:50`. That is 2 rounds, not 4+. The 4+ rounds figure belongs to the
  COMPACTION ask (08-20-d, 08-21, 08-22-b/c/d), a different thing.
- "no compensating compaction": #454's own body records "Partial pass done
  today: Compacted 24,535 B -> 22.3 KB".

## PRIMARY SOURCE for the cap — the finding's denominator is WRONG

`sources/claude-code/CHANGELOG.md:3239`:
  "- Memory: `MEMORY.md` index now truncates at 25KB as well as 200 lines"

LIVE binary `/Users/rmanaloto/.local/share/claude/versions/2.1.241` (2.1.241,
the version PATH resolves — `claude --version` = 2.1.241):
  offset 289039316: `Lme=25000`   <- byteCap  (spliceCap)
  offset 289039308: `Une=200`     <- lineCap
  offset 298653589: `function D9i({rawSizeBytes:e,surfaceCap:t,splicedSizeBytes:r,spliceCap:n,spliceActive:o})`
  offset 298653700: `function M9i(e){let t=[{frac:e.sizeBytes/e.byteCap, over:e.sizeBytes>e.byteCap, ...`
  offset 298655400: `label:"memory index",displayPath:vS,...D9i({rawSizeBytes:u.bytesTotal,surfaceCap:l,splicedSizeBytes:d.byteCount,spliceCap:Lme,spliceActive:c}),...c&&{lineCount:d.lineCount,lineCap:Une}`
  `tjT=0.8` (warn threshold), `iHm=0.7` (target ratio)

=> HARD READ LIMIT = **25,000 bytes**, NOT 24,985.6.
   The finding's 24,985.6 is 24.4 x 1024. 24.4 KB is the DISPLAY STRING
   `Ma(25000)` produces; the finding read the display and re-multiplied,
   losing the real constant. Inherited-number failure.
   Correct: 23,864/25,000 = 95.456% ; headroom = **1,136 B**, not 1,121 B.
   MEMORY.md is 104 lines vs the 200-line cap — the second axis, unmeasured
   by the finding, sits at 52%.

## DECISIVE ARM: kb-reflect cannot write MEMORY.md

Installed graphify pkg = `.venv/lib/python3.14/site-packages/graphify`
  CONTROL (known-present): grep 'LESSONS.md|reflections' -> 8 hits
      hooks.py:149,198 · cli.py:1252,1262 · __main__.py:580 · reflect.py:24,137,302
  TEST:                    grep 'MEMORY.md|\.claude/projects' -> **0 hits**
The probe discriminates. `mise.toml:975` confirms the task is
`graphify reflect --graph {{config_root}}/graphify-out/graph.json` — repo-local.
mtimes: LESSONS.md 22:26:43 < MEMORY.md 22:28:27 (104 s later, same minute as
the model-written `a-commit-after-the-handoff-is-invisible-to-the-receipt.md`).
=> MEMORY.md grew by the MODEL's auto-memory write, not by kb-reflect.

CONTRADICTS SET ITEM #8, which says this session "hand-edited MEMORY.md twice".
#8 is right; #9's causal clause is wrong.

## "4+ rounds" is 2, and both are TODAY

- session-2026-08-22-d.md:77-78 — the session PROPOSES the structural option
  ("the real choice in #454 is structural — GENERATE the index from each memory
  file's own `description:` frontmatter"); also "Do not defer this a fifth time",
  which is about the COMPACTION ask, not the generate decision.
- session-2026-08-22-e.md:165 (mtime 2026-08-22 18:55:51) — "Ray's call
  recorded: GENERATE the index from each memory file's `description:`
  frontmatter". FIRST appearance of Ray's decision.
- session-2026-08-22-f.md:50 (mtime 2026-08-22 22:22:13) — carried.
=> Ray's decision is ~3.5 h and 2 handoffs old, both on 2026-08-22. Not 4+ rounds.

## THREE different denominators for ONE constant, none of them right

- session-2026-08-22-e.md:165-167 -> "1,071 B headroom" at 23,329 B  => cap 24,400
- session-2026-08-22-f.md:50      -> "hard limit 24.4 KB"            => cap ambiguous
- this finding                    -> 24,985.6 B                      => 24.4 x 1024
- LIVE claude 2.1.241 `Lme=25000` -> **25,000 B**  (+ `Une=200` lines)

## Verdict: REFUTED as stated

Direction survives (unbuilt, growing, near cap). The stated finding does not:
the mechanism is false, the denominator and headroom are wrong, the round count
is 2x overstated, and the 200-line axis (104/200) was never measured.
