# Refutation lane: "511 lines stranded on fix-328-extraction-warnings, forgotten"

Status: COMPLETE, 2026-08-18. Verdict: **REFUTED as framed** — the raw git facts
hold; every inference stacked on them ("stranded", "forgotten", "re-litigated",
"will be duplicated") is contradicted by probes the original lane's bounds
excluded.

## What the finding's own probes could and could not see

- `git diff main...fix-328-extraction-warnings --stat` is a THREE-DOT diff: it
  measures the branch's delta from the MERGE-BASE and returns 511 insertions no
  matter what main gained by another route. It is structurally incapable of
  detecting supersession — the probe could only produce the answer it gave.
  (Also: 148 of the 537 changed lines are two `graphify-out/memory/*.md` files,
  so the code at issue is ~389 changed lines, not 511 "lines of work".)
- "No handoff in the window mentions the branch" was window-bounded to exclude
  the two handoffs immediately before it. Unbounded grep
  (`grep -rniE 'fix.?328' .agent/plans/`): **session-2026-08-16-b.md:3**
  "`fix-328-extraction-warnings` — PARKED by Ray's decision"; **:23** Ray's
  verbatim ruling item 3 "**`fix-328-extraction-warnings` stays parked.**";
  **:82** a dedicated "## PARKED" section inventorying everything on the branch;
  **session-2026-08-16-c.md:18** "remains PARKED and untouched"; **:183** work
  accidentally started on it was deliberately MOVED OFF ("#328 is unchanged and
  still parked"). A branch parked by the owner's explicit recorded ruling is not
  a forgotten lane.

## The opposite-answer probes

1. **`gh pr view 338 --json headRefName,state,mergedAt`** →
   `fix-328-extraction-warning-accounting`, MERGED 2026-08-18T04:33:31Z. The
   #328 lane CONTINUED on a successor branch tracked commit-by-commit in four
   in-window handoffs (17-d/e/f/g; 17-g:50 even orders it shipped next) and
   merged the same day. The lane was not forgotten; it shipped.
2. **`gh issue view 328 --json state`** → **CLOSED** (updated 04:33:32Z, one
   second after the merge — closed by it). The branch is partial work toward a
   now-resolved issue.
3. **Supersession, content-level** (`git show main:python/src/kb_setup/…`):
   main has `_EXPECTED_PARTIAL_EXTRACTION` / `ExpectedPartialExtraction`
   (graph.py:249-250) and per-warning accounting with `residual_stderr`
   (graphify_sdk.py:384/408) — the parked branch's headline mechanisms, rebuilt
   better (armed 9/9 by `kb-arms`, per 17-d) and merged. Branch-only residue:
   `approve_vendored_extract_warnings` (graphify_sdk.py:649 on the branch, 0
   hits in main) — the vendored per-source path built from a ONE-SOURCE sample,
   superseded by Ray's 2026-08-17 census-grounded ruling (17-d finding 1:
   2,675 zero-node JSON files across 55/71 sources; "reviewed CLASS with the
   count reported, the #289 shape, not per-file hashes").
4. **In-window transcripts DO name the exact parked branch** (self-contaminated
   files from this workflow excluded): `6b974f05….jsonl` (2026-08-17 21:42) and
   `52f5798a….jsonl` (the session that wrote handoff 18-a, 03:07) — both show
   it in `git branch -v` output beside its tip `4dfa328c`. Control arm: the
   successor name hits 6 round transcripts, so the probe discriminates.
5. **The item-6 audit is not silently missing**: 18-a "Owed" explicitly lists
   the worktree/branch audit (~20 local branches), and this workflow's own
   pending-work lane has now executed it.

## "Re-litigated / re-ruled" is mischaracterised

Ray CHOSE #328 as the next task from a four-way AskUserQuestion (17-c). The
class-vs-per-file question for extract-phase zero-node files was ruled ONCE, on
2026-08-17, against NEW census evidence that refuted the #328 ticket's own
per-file argument (a ticket's argument, not a prior ruling; 17-d calls the
ticket "written from a sample of one"). The parked branch had partially built
BOTH approaches — per-file hashes for Attacca's 8 files AND a class path for
vendored GitNexus — so "reviewed-CLASS, the approach this branch had partially
built" is half-true, and the ruling went AGAINST the branch's per-file half.

## The grain of truth (what survives of the finding)

- The Aug-17 session did RE-DERIVE the >5 truncation defect (same
  `extract.py:5511` anchor 16-b's PARKED section had already recorded) without
  citing the parked branch — one day's real duplicated diagnosis, enabled by
  the park record living only in a two-back handoff and not in issue #328's
  body. That is a knowledge-transport defect worth an issue; it is not "511
  lines stranded".
- The two work-memory files on `4dfa328c`
  (`query_20260816_194005_…`, `query_20260816_194024_…`) ARE absent from main —
  the genuinely unlanded residue (~148 changed lines).

## Contradiction within the finding set

**`pending-work.md` item 3 (same workflow, the dedicated branch-audit lane)
reaches the OPPOSITE disposition on the same branch**: "code superseded by the
#338 lineage (164+/205- rewrite of graphify_sdk.py), issue #328 CLOSED; 2
memory records stranded; remedy: cherry-pick the 2 memory files, then delete
the branch." Two probes of one fact disagree; the broken probe is the forgotten
lane's three-dot diffstat, which cannot see supersession. My independent
content probes side with pending-work.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — PR #338 head/state, issue #328 state

## COVERAGE

- REACHED AND ANALYSED: the branch itself (log, three-dot stat, cherry, both
  contested files at both revs); all 7 mandated handoffs IN FULL plus 16-b and
  16-c; the 2026-08-18 directive IN FULL (item 6 confirmed); PR #338 and issue
  #328 via gh; per-handoff exact-name counts for both branch spellings;
  windowed transcript greps for both spellings with mtimes and a control arm;
  the 2026-08-17 session-review report (0 fix-328 hits, control 'branch'=2/554
  lines); sibling lanes pending-work.md (full) and forgotten.md (the finding's
  own text).
- OPENED BUT NOT FINISHED: transcript CONTENT beyond bounded -o snippets
  (deliberate — jsonl never read into context); forgotten.md read only around
  its item 3.
- NEVER REACHED: issue #328's full comment thread (state and timestamps were
  sufficient); the salvage/* branches (settled block + pending-work lane cover
  them); reflog mining.
