# Refutation attempt — lane `pending-work`, finding: 4dfa328c orphaned memory files

VERDICT: **NOT REFUTED** (every clause held under an unbounded re-probe).

## Claim under test
`fix-328-extraction-warnings` commit `4dfa328c` added two `graphify-out/memory/*.md`
lesson files that exist on no other branch and are absent from `origin/main`, even
though the sibling code-fix commit on the same branch is superseded by merged PR #338
(different branch, same issue #328).

## The bound in the ORIGINAL probe, and how I removed it
The original evidence only tested `origin/main` (`git show origin/main:<path>`), and
`origin/main` is a *local remote-tracking ref* that can be stale. `git ls-remote --heads origin`
shows **15 live remote heads**, and TWO of them had no local counterpart at all
(`codex/issue-301-complete-graphify-semantics`, `feat/cross-vendor-orchestrator`) —
i.e. the original probe could not have seen them. I fetched every live remote head by
name into FETCH_HEAD and tested all 15 plus all 26 local refs.

## Probe (unbounded, with control arm)
```
P1=graphify-out/memory/query_20260816_194005_what_must_be_checked_before_running_a_large_deep_s.md
P2=graphify-out/memory/query_20260816_194024_is_it_right_for_a_check_to_compare_my_re_derived_n.md
CTRL=graphify-out/memory/query_20260722_172532_does_graphify_reflect_produce_lessons_md__and_what.md
for b in $(git ls-remote --heads origin | awk '{print $2}'); do
  git fetch -q origin "$b"; SHA=$(git rev-parse FETCH_HEAD)
  for f in "$P1" "$P2" "$CTRL"; do git cat-file -e "$SHA:$f" 2>/dev/null && echo PRESENT || echo absent; done
done
```
Result: `absent` for P1/P2 on **all 15 live remote heads** (incl. `main`) and on all
local refs except `fix-328-extraction-warnings`.
**Control:** `CTRL` returned `PRESENT` on all 15 remote heads and all 26 local refs,
so the probe discriminates present from absent.

## Second route (content, not path) — kills the "renamed file" refutation
A `kb-remember` filename is timestamp-derived, so the same lesson could survive under a
different name. Content search across every ref:
```
git grep -l "SHADOW IMPLEMENTATION OF THE TOOL" $(git for-each-ref --format='%(refname)' refs/heads refs/remotes)
  -> refs/heads/fix-328-extraction-warnings:...194024...md   (ONLY)
git grep -l "CHECK THE EXTRACTION CONFIG BEFORE SPENDING" <same refs>
  -> refs/heads/fix-328-extraction-warnings:...194005...md   (ONLY)
Control: git grep -l "graphify reflect produce" <same refs> -> 26 refs
```
Also absent from the working tree (`ls graphify-out/memory/ | grep -E "20260816_1940"` -> rc=1;
control `grep -c "20260722_172532"` -> 3) and from the user auto-memory dir
(`grep -ril "shadow implementation" ~/.claude/projects/.../memory` -> 0; control
`grep -ril mutation` -> 57 files). `git grep -il "shadow implementation" origin/main`
returns only `python/src/kb_setup/graph_size.py` — a code file, not the lesson.

## Clause 2 — "sibling code-fix superseded by merged PR #338"
- `gh pr view 338 --json headRefName,state,mergedAt` -> `fix-328-extraction-warning-accounting`,
  MERGED 2026-08-18T04:33:31Z. Distinct branch from `fix-328-extraction-warnings`. Confirmed.
- `git merge-base --is-ancestor 3d1336dc origin/main` -> **NOT-ANCESTOR**: the sibling
  code commit itself never landed.
- main nevertheless carries the same feature, re-implemented: `origin/main:python/src/kb_setup/graphify_sdk.py`
  line 707 `# Two reviewed CLASSES, applied to vendored third-party clones at any depth.`,
  line 619 `_partial_extraction_is_reviewed`, line 647 approving one reviewed #2551 warning.
- Nuance worth recording (does not refute): main kept `_EXPECTED_PARTIAL_EXTRACTION`
  (graph.py:249, used at :432) but the sibling's helpers `_report_vendored_extract_warnings`
  and `_report_partial_extraction` do NOT exist on main. "Superseded" is accurate in the
  sense of re-implemented, not cherry-picked.

## Contradiction check against the other 28 live findings
None contradicts. #16/#29 (salvage/canonical-worktree-snapshot) are the same *class*
(unmerged branch holding unique work-memory) and corroborate rather than conflict.

## GitHub repos touched
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under test; PR #338 / issue #328 state read via `gh`.
