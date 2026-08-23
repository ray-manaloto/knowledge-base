# pending-work lane

Scope: transcript `096161cc-...jsonl` (started 2026-08-23T02:54Z). Working tree
`claude-resync-2.1.241` @ `272d14bc3785` == `origin/main` == `main` (verified via
`git rev-parse HEAD / origin/main`).

## Repeat-finding alert

This exact inventory (worktrees, branches, stash) was already produced by a
pending-work lane on **2026-08-18**, committed at
`docs/session-review/runs/2026-08-18-1/pending-work.md` (on `origin/main` today).
Every branch/worktree flagged there is **still present, unchanged**, 5 days and
one landed round later. Nothing here is new except that it has now gone
un-acted-on twice.

## 1. Four worktrees hold ALREADY-MERGED work (safe to remove, verified)

`git worktree list`:
- `../worktrees/knowledge-base-299` → `codex/issue-299-graphify-ast-baseline` @ `3018dff3`
- `../worktrees/knowledge-base-300` → `codex/issue-300-claude-semantic-slice` @ `4cd58d0a`
- `../worktrees/knowledge-base-301` → `codex/issue-301-graphify-0943-no-provider` @ `8ace6198`
- `../worktrees/knowledge-base-graphify-0942` → `codex/graphify-0942` @ `5eda1525`

For each, `git cherry origin/main <branch>` reports every commit as `+` (not
patch-equivalent) — but that's the expected *squash-merge* signature, not
evidence of unlanded work. Verified directly via `gh pr view` + `git merge-base
--is-ancestor`:
- PR #307 (299) mergeCommit `67f7ef0b` — `git merge-base --is-ancestor 67f7ef0b origin/main` → **true**
- PR #308 (300) mergeCommit `cc6e226b` → **true**
- PR #312 (301) mergeCommit `0c15267e` → **true**
- PR #291 (0942) mergeCommit `c70f0f81` → **true**

Control arm: `git status --short` in worktrees -299/-300/-301 is empty (0 lines) —
genuinely clean. Worktree `-graphify-0942` has 9 untracked entries
(`.agents/skills/{clear-prep,goal-engineering,kb-curator,kb-reclaim,kb-review,
orchestrator-routing,tool-currency}/`, `.codex/`) — these are codex-CLI-generated
skill mirrors, not authored content; low-value, not "pending work".

**Verdict: all four worktrees are pure disk/attention cost. `git worktree remove`
each, then `git branch -D` the four branches — their unique commits are already
ancestors of `origin/main`.**

## 2. Branches with zero unique commits (pure bookkeeping)

`codex/graphify-0.9.39-kb`, `codex/kb-codex-migration`,
`codex/migration-source-sync`, `feat/lessons-tracked-and-gated` — each
`git merge-base --is-ancestor <branch> origin/main` → **true**. Zero risk, delete
freely.

## 3. Branches whose unique commits are content-verified LANDED (safe to delete)

- `codex/archive/issue-301-pr311-reviewed-fd7343e` (2 commits, "normalize parser
  error offsets" / "add sanitized parser diagnostics"). The specific fix
  (`byte_offset = len(text[:exc.pos].encode("utf-8"))`) is present in
  `origin/main:python/src/kb_setup/graphify_semantic_adapter.py:401,420` today.
  Landed (matches PR #311, merged 2026-08-14T19:21:06Z).
- `chore/skills-1.2.2-sync` (2 commits, codex/antigravity-cli bumps to
  0.146.1/1.1.10 + wayfinder docs). `origin/main:mise.toml:142-143` now pins
  codex=0.149.0, antigravity-cli=1.1.17 (newer); `docs/issue-tracker.md` already
  carries the wayfinder decision-ticket language. Superseded by later work.
- `close-2026-08-20-round` (1 commit, CLAUDE.md edit +
  `graphify-out/memory/query_20260820_094115_...406_cost.md`). Both paths exist
  verbatim in `origin/main` (`git cat-file -e origin/main:<path>` → exists for
  both). Duplicate of what actually shipped.
- `salvage/doppler-critical-kb` (3 commits, 2026-08-12 Doppler source tracking +
  offline-receipt fix). `origin/main` now carries a far more developed Doppler
  surface: `sources/doppler*.md` (12 files), `sources/doppler.manifest`,
  `docs/currency/runs/2026-08-{14,16,18}-doppler.md`,
  `docs/currency/doppler-watch-state.json`. Superseded by a later, larger effort.
- `salvage/skillopt-heldout-evaluation` + `-v2` (3 commits total, "stage/bind
  SkillOpt mock evaluator"). `origin/main` has NO
  `python/src/kb_setup/skillopt_eval.py` (the file this WIP built) — instead it
  has `skillopt_contract.py` + `skillopt_reviewed.py` + their tests, a different
  design (matches MEMORY.md: "SkillOpt is not a marketplace plugin" / "immutable
  VCS revision" note). This WIP approach was abandoned in favor of a different
  one, not merged. Dead-end, safe to drop.
- `salvage/canonical-worktree-snapshot`, `salvage/graphify-ecosystem-wip` — both
  "Codex Recovery" crash-preservation snapshots from 2026-08-13 of skills
  (`clear-prep`, `goal-engineering`, etc.) that are now core, far-more-developed
  parts of `origin/main`. Superseded.
- `salvage/stash-0`, `salvage/stash-1` — literal materializations of the two
  `git stash list` entries (currency reports pre-Graphify-0.9.42, 2026-08-13).
  Content-diffed: adds nothing beyond currency logs already superseded by the
  many currency cycles since. **`git stash list` still shows both stash@{0} and
  stash@{1} live** — redundant with the branches (same content, not
  independently at additional risk), but worth `git stash drop` once the
  branches are kept/archived, to stop carrying it twice.

## 4. Real, small, still-unlanded work (the only genuine "pending work at risk")

- **`codex/gh-stack-skill`** (1 commit, `9a3cab2a`, 2026-08-11, 142 lines) — adds
  `.claude/skills/gh-stack/SKILL.md` + `.agents/skills/gh-stack/SKILL.md`
  ("project-scoped gh-stack" skill). Confirmed absent from `origin/main` under
  either path (`git cat-file -e` fails both). Confirmed no PR ever opened
  (`gh pr list --search "head:codex/gh-stack-skill" --state all` → `[]`; control
  arm: the same search shape returns non-empty for `head:codex/graphify-0942`,
  so the search itself works). **This is the one branch in the whole inventory
  carrying real, never-landed, never-reviewed content**, unchanged since
  2026-08-11 and already flagged once before (2026-08-18) with no action taken.
- **`chore/round-close-2026-08-09b`** (1 commit, `c8b821ca`, 2026-08-09) — a
  work-memory file (49 lines, "did this round's defects actually live in
  explanatory prose"). `git cat-file -e origin/main:<path>` → **fails, MISSING**.
  A genuine unlanded lesson, small but real.
- **`chore/session-work-memory`** (1 commit, `771f022e`, 2026-08-08) — a
  work-memory file (17 lines, kb-reclaim / macOS disk reclamation lesson).
  Confirmed MISSING from `origin/main` the same way.
- **`fix-328-extraction-warnings`** (2 commits, 2026-08-16) — the code half
  (`3d1336dc`, adds `_report_vendored_extract_warnings` /
  `_report_partial_extraction` to `graph.py`) is explicitly marked
  `PARTIAL: kb-build still exits 1 on OpenSymphony` in its own commit body, and
  neither function name exists in `origin/main:python/src/kb_setup/graph.py`
  today — issue #328 (CLOSED 2026-08-18) was actually closed by a *different*,
  larger PR #338 (`fix-328-extraction-warning-accounting`, 13+ files including
  `chunks.py`/`cli.py`/`graphify_baseline.py`, not just `graph.py`), which fully
  supersedes this branch's code. The memory half (`4dfa328c`, 2 lesson files)
  is confirmed MISSING from `origin/main` — same pattern as the two memory-only
  branches above: the technical need was met elsewhere, but this specific
  lesson text was never folded in anywhere else I could find (not proven
  absent-in-substance, only absent-by-path).

## 5. This session's own working tree — NOT at risk (checked because the handoff claimed otherwise)

The ALREADY-SETTLED block for this session states `claude-resync-2.1.241` "has
UNCOMMITTED: docs/direction/2026-08-22-ray-directives.md (addendum) +
graphify-out/memory/query_20260823_032615_*.md + …LESSONS.md regen". Verified
directly: `git status --short` and `git status` both report **clean, nothing to
commit**, and `git ls-tree HEAD` confirms all three artifacts (the addendum text,
`query_20260823_032615_...md`, and `query_20260823_023011/023012_...md`) are
already committed at HEAD `272d14bc`, which is also `origin/main`. The
handoff's claim was accurate for the state at the moment it was written but is
now stale — the commit already happened (before this transcript started) and
nothing is at risk here. Recording this so the next session doesn't re-open a
non-issue.

## Coverage

**Reached and analysed:** every `git worktree list` entry (4), every local
branch (25, full `for-each-ref` enumeration, all ahead/behind + cherry +
content-verified for anything with `ahead>0`), both `git stash list` entries
(both are also materialized branches, covered under §3), and this session's own
working-tree cleanliness claim from the handoff.

**Opened but not fully verified:** whether `fix-328-extraction-warnings`'s two
*memory* lesson files (as opposed to its code, which is clearly superseded) were
folded into any other committed memory file under a different name/hash — I
checked path-exact absence only, not semantic-duplicate presence.

**Never reached:** no other backup directory was named in this session's
ALREADY-SETTLED block or the two round handoffs, so none was walked beyond the
worktrees explicitly listed by `git worktree list` (per the task's own scoping
rule — external directory trees are out of scope without a named backup path).
I did not open `docs/session-review/runs/2026-08-18-2/` (a second iteration of
that same prior round) — only `-1`, which already fully corroborated this run's
own findings.
