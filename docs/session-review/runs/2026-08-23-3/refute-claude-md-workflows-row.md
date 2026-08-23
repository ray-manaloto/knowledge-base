# Refutation attempt: CLAUDE.md workflows row lists 1 of 3 workflows

Lane: refute-claude-md-workflows-row · 2026-08-18 · branch docs-directive-addendum (clean, HEAD 022e88f4)

## VERDICT: NOT REFUTED — CONFIRMED on every count, and SHARPENED

FINDING under test: CLAUDE.md:174 names only `kb-extract.js` while `.claude/workflows/`
holds kb-extract.js, kb-tool-review.js AND session-review.js; session-review.js is the
NEXT TASK's tool and is invisible to a reader orienting from the Layout table.

## Probes run (all 2026-08-18)

1. `sed -n '168,180p' CLAUDE.md` + `grep -n "workflows" CLAUDE.md` → line **174**
   verbatim: `| .claude/workflows/ | Saved Claude workflows the skills compose —
   kb-extract.js (host-agent extraction fan-out). |` — one name. Line number EXACT.
2. `ls -la .claude/workflows/` → exactly 3 files, no hidden entries:
   kb-extract.js (16389 B, Aug 13), kb-tool-review.js (13956 B, Aug 13),
   session-review.js (20954 B, Aug 18 03:30).
3. `git show main:CLAUDE.md | grep -n "workflows/"` → same text, same line 174 on
   main (2b364443). Not a branch artifact.
4. History: row authored 2026-07-23 (f7a99804), the ONLY commit
   `git log -S "Saved Claude workflows" -- CLAUDE.md` returns — never edited since.
   kb-tool-review.js added 2026-08-01 (43a6b468, #102) → the row has been incomplete
   for ~17 days independent of session-review.js. session-review.js added 2026-08-18
   (2b364443, #339; amended 022e88f4).
5. **Sharpening fact**: PR #336 (merged 2026-08-17, handoff g line 36) EDITED the same
   Layout table — added the `docs/direction/**` row — and left the workflows row
   untouched. The table was current-reviewed the day before and the omission survived.

## Control arms

- NEGATIVE armed: `grep -rn` for kb-tool-review / session-review / tool-review /
  session_review / sessionreview across CLAUDE.md + .claude/CLAUDE.md + AGENTS.md →
  0 hits (rc=1). Control: same shape for `kb-extract` in CLAUDE.md → 2 hits. Probe
  discriminates; the two other workflows are absent from ALL auto-loaded docs.
- Original probe one-sidedness: both sides are positive observations (an `ls` that
  could return 1 and a line read that could show 3 names). No bound, no spelling
  bound, no redirect/parse-error read as a no.
- Graph-first toll paid: `mise run kb-query --prose` (TRUNCATED, corpus covers
  ingested sources, not this repo's own CLAUDE.md — no contradiction from the graph).

## Refutation angles tested — all dead

- "Line number wrong" — no, exact (:174, branch AND main).
- "Mentioned elsewhere in auto-loaded docs" — no, 0 hits with variants (armed).
- "More/fewer than 3 files" — no, exactly 3, no hidden files.
- "'Workflows the skills compose' deliberately scopes the row" — dead:
  `.claude/skills/kb-session-review/SKILL.md:23` and `:122` explicitly compose
  `.claude/workflows/session-review.js`, so the row's own scope covers it and still
  omits it. (kb-tool-review.js has no composing skill under `.claude/skills/` —
  grep hit only kb-session-review and kb-curator SKILL.md files — but one covered
  omission suffices, and the row describes the directory either way.)
- "session-review.js is not the NEXT TASK's tool" — dead, three independent sources:
  docs/direction/2026-08-18-ray-directives.md:76 ("The workflow was rebuilt and
  committed this session (`.claude/workflows/session-review.js` + `kb-session-review`
  skill). It has **not been run** yet") and :214-216 (first task = improve + run it);
  .agent/plans/session-2026-08-18-a.md:17-31 (NEXT TASK names the same file);
  MEMORY.md READ-FIRST bullet.

## The lane contradiction — mechanism located, defect is in the OTHER probe

All four knowledge-base worktrees are checked out at pre-#339 codex-branch commits and
hold only **2** workflow files (kb-extract.js, kb-tool-review.js — no session-review.js):
`worktrees/knowledge-base-{299,300,301,graphify-0942}` (git worktree list + per-dir ls,
2026-08-18). A lane that ran `ls .claude/workflows/` in any worktree gets a different
count and could report the finding's "3 files" as wrong. That is a stale-checkout probe
defect, not a fact about the primary checkout — and note even there the row is
incomplete (1 of 2), so no checkout on this machine makes the row accurate.

## Mandated reading — done in full

- docs/direction/2026-08-18-ray-directives.md (234 lines, in full). Corroborates the
  finding; nothing contradicts it. (The directive itself names session-review.js at
  :76, but the finding is scoped to "orienting from the Layout table", and the
  directive is not the Layout table — not a contradiction.)
- All 7 handoffs (2026-08-17 b,c,d,e,f,g + 2026-08-18 a), each in full. None mentions
  the workflows row; f/g supply the #336-edited-the-table sharpening fact; 08-18-a
  confirms the NEXT TASK tool.

## COVERAGE

- REACHED AND ANALYSED: CLAUDE.md:168-180 + full grep; .claude/CLAUDE.md and AGENTS.md
  (variant greps); `.claude/workflows/` (ls -la); main:CLAUDE.md; git history of the
  row and of all 3 workflow files; `.claude/skills/**` grep for composers; the
  2026-08-18 directive IN FULL; all 7 handoffs IN FULL; all 4 kb worktrees' workflow
  dirs; one kb-query (truncated, non-contradicting).
- OPENED BUT NOT FINISHED: the truncated kb-query result (249 nodes cut) — not
  pursued; it indexes ingested sources, not this repo's own CLAUDE.md rows.
- NEVER REACHED: the .jsonl transcripts (not needed — the finding is about the
  working tree, not transcript behaviour); other lanes' reports (not visible to
  this lane); kb-tool-review.js's composing skill beyond `.claude/skills/` (e.g.
  `.agents/skills/**` was not grepped — irrelevant to the verdict since
  session-review.js alone defeats the scoping defense).

## GitHub repos touched

_None._ (local repo probes only)
