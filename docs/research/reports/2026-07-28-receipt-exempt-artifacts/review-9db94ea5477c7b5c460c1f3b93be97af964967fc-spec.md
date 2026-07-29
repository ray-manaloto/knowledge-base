# Spec review — `f3e233a...HEAD` (9db94ea)

Axis: **Spec**. Sources read: `gh issue view 66` (body + the clear-prep comment),
`.agent/plans/session-2026-07-28-d.md` § "NEXT TASK", the full diff, and the
non-diff call sites (`pr.py`, `cli.py`, `.gitignore`).

## Verified-as-asked (evidence first, so the findings below are scoped)

| Spec line | Verdict |
|---|---|
| Issue option (2): *"Have `kb-ship` accept a receipt whose SHA is an **ancestor** of HEAD **when the only delta is inside an exempt path set**."* | **Genuinely (2), not (1).** `_covering_receipt` returns a *different SHA to validate*; `_base_coverage_gap` and `_all_reasons` then run unchanged against that ancestor (`review.py:767-773`). No path is excused from a review's coverage — a delta containing one reviewed path refuses. The docstring states the distinction explicitly and correctly. |
| Plan: *"**change the check, never remove it**"* | Held. `receipt_state` retains every arm; the only edit to the existing flow is substituting `covering` for `sha` in three already-present checks. Nothing was deleted. |
| Plan: *"Fold these four carried artifacts into that branch's first commit"* | **All four present in `238417c`**, the branch's first commit: `M docs/goals/README.md`, plus the three `graphify-out/memory/query_2026072*` files. The README delta is exactly the one table cell the plan named (`not started` → `achieved`). |
| Issue: exempt set `graphify-out/memory/**`, `graphify-out/reflections/**`, `docs/goals/README.md` | Two of three implemented; the third is a **justified omission** — see below. |
| Plan: *"Both are on the `Legible` rider's preserve list"* — `ship_main`/`land_main` | `pr.py` unchanged, correctly: both already pass `require_base="main"` (`pr.py:343,361,442`), which is the flag that arms the fallback. `cli.py:287` (the writer's read-back) passes no base and keeps strict identity, matching `_covering_receipt`'s docstring. |

### The `graphify-out/reflections/` omission is correct and control-armed

The issue comment asks for it; the code omits it with a written reason
(`review.py`, `EXEMPT_PATHS` docstring): *"it is gitignored (`.gitignore`,
"reflect derived doc"), so it can never appear in a `git diff` and an entry for
it could never fire."* **Verified independently**: `.gitignore:78-79` reads
`# reflect derived doc (regenerable via 'graphify reflect'); memory/ IS tracked
(authored)` / `graphify-out/reflections/`. The claim holds, and the justification
is in the code rather than only in a commit message. Not a finding.

### FAIL-direction probe

Plan: *"Prove the FAIL direction realistically — delete the *wiring line that
calls* the coverage check, not the function definition."* The commit body of
`9db94ea` records: *"Probed by deleting four wiring lines in turn — the exempt
filter, the base-coverage call, the ancestry bound, the opt-in guard. Each was
caught."* That is the shape asked for (call sites, not definitions). I could not
independently re-run the historical probe, but each of the four has a
corresponding test that fails if the line is removed, and
`uv run pytest tests/test_review.py -q` → **56 passed, rc=0** (control arm: the
suite runs, so a green is a real green).

---

## (a) Asked for but missing or partial

**A1 — the gate itself is untested end-to-end (MEDIUM).**
Issue option (2), verbatim: *"Have **`kb-ship`** accept a receipt whose SHA is an
ancestor of HEAD…"*. Plan: *"Tests: `tests/test_review.py`,
`tests/test_review_cli.py`, `tests/test_pr.py`."* Only `tests/test_review.py`
was touched (`git diff --stat`: `test_pr.py`, `test_review_cli.py` unchanged).
Every new test exercises `review.receipt_state` directly; **nothing asserts that
`ship_main` / `land_main` actually accept an ancestor receipt.** The wiring that
makes them do so — `require_base="main"` at `pr.py:343,361,442` — is pre-existing
and correct, so I believe the behaviour holds; but the spec's own sentence is
about `kb-ship`, and the only proof of it is inference from an unchanged file.
One test in `test_pr.py` driving `ship_main`'s receipt arm over a real
exempt-delta branch would close it.

## (b) In the diff but not asked for

**B1 — a prescribed workflow change (LOW).**
`.claude/skills/goal-engineering/SKILL.md` gains: *"**Run it BEFORE `kb-ship`,
then commit what it wrote.**"* Neither the issue nor the plan asked for a
reordering of the round-closing procedure — the plan's instruction was
*"change the check, never remove it"*. The addition follows from the fix and is
arguably mandatory doc-sync, so I am not calling it a defect; flagging it because
it is new prescriptive behaviour for future rounds, not a description of the code
change, and it should be a deliberate decision rather than a side effect.

**B2 — `_MAX_NAMED_PATHS`, and its asymmetry (LOW).**
Not asked for, justified in-code as a self-declaring display bound. The
justification only covers half the code: the **refusal** message is bounded
(`reviewed[:_MAX_NAMED_PATHS]` + `(+N more)`), while the **accepted** note joins
every exempt path unbounded — `covered = ", ".join(paths)`
(`review.py`, `_covering_receipt`). A round that writes ten memory files prints a
ten-path summary line from the very gate that just argued display bounds matter.

## (c) Implemented but the implementation looks wrong

**C1 — "NEAREST" is not what `rev-list` guarantees (LOW, fail-closed).**
`_reviewed_ancestor`'s docstring: *"Return the NEAREST commit on this branch below
`sha` that has a receipt… only one candidate is ever considered, because a
farther ancestor is strictly harder to accept."* The implementation is
`_git_result(repo_root, "rev-list", f"{base}..{sha}", "--")` and takes the first
receipt-bearing entry. `git rev-list` defaults to **reverse-chronological (commit
date) order, not topological distance**. On a linear branch the two coincide; on a
branch containing a merge (which the suite's own
`test_the_walk_does_not_reach_a_receipt_on_main` constructs) the first hit need
not be the topologically nearest. The consequence is safe — a farther ancestor's
delta is a superset, so the walk can only refuse where a nearer one would have
passed — but the docstring states a property the code does not enforce, and the
"strictly harder" argument silently assumes linear history. Fix is either
`--topo-order` / `--first-parent`, or softening the claim to "the first
receipt-bearing ancestor, and a farther one can only refuse more".

**C2 — the exemption is whole-file where the plan described one cell (LOW,
as-specified).**
Plan: *"`docs/goals/README.md`'s change is one table cell: the `Legible` pair's
status, `not started` → `achieved`."* `EXEMPT_PATHS` exempts the **entire file**,
so any post-receipt edit to it — including its prose (`## Why the goal file is
capped at 4,000 characters`) and every other pair's row — now ships with no lane
having read it. The issue asked for the path, so this matches the spec as written
and I am not calling it a defect; recording it because the plan's own description
of the delta is narrower than what was granted, and `goal.py:584-598` shows the
tool only ever rewrites a Status cell, so a narrower rule was available.

## Notes, not findings

- **`brain/graphify-out/memory/**` is a second TRACKED work-memory store** (`git
  ls-files` → present) and is not exempt. Correct: `brain-remember` is a routing
  seam (`mise.toml:334`), not one of P7's three mandated tasks, so the issue and
  plan rightly did not name it. If a future rider mandates it, the same orphan
  returns.
- `graphify-out/reflections/` — omission verified against `.gitignore:78-79`; the
  in-code justification is accurate.
- The exempt-delta check compares **trees**, not touched paths, so a code change
  and its revert between ancestor and HEAD reads as exempt. That is right: the
  reviewed bytes at HEAD are identical to the reviewed bytes at the ancestor.


## Verdict

**No blocking spec finding.** The change is genuinely issue option (2), the
narrower one; the exempt set matches what was named apart from one omission that
is justified and independently verified; all four carried artifacts were folded
into the branch's first commit. Four non-blocking findings: A1 (medium, missing
gate-level test), B1/B2 (low, unrequested workflow prose + an unbounded accepted
note), C1/C2 (low, a docstring claim `rev-list` does not guarantee, and a
whole-file exemption where a cell was described).

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under review; issue #66 read via `gh`.
