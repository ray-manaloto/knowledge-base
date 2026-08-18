# pending-work lane — iteration 1

## Raw inventory (commands run, verbatim)

### git worktree list
```
/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base                          f772f5eb [docs-directive-addendum]
/Users/rmanaloto/dev/github/ray-manaloto/worktrees/knowledge-base-299            3018dff3 [codex/issue-299-graphify-ast-baseline]
/Users/rmanaloto/dev/github/ray-manaloto/worktrees/knowledge-base-300            4cd58d0a [codex/issue-300-claude-semantic-slice]
/Users/rmanaloto/dev/github/ray-manaloto/worktrees/knowledge-base-301            8ace6198 [codex/issue-301-graphify-0943-no-provider]
/Users/rmanaloto/dev/github/ray-manaloto/worktrees/knowledge-base-graphify-0942  5eda1525 [codex/graphify-0942]
```

### git branch --show-current
docs-directive-addendum (current session branch)

### git for-each-ref refs/heads (name|upstream|track|HEAD-marker)
```
chore/round-close-2026-08-08g2||| 
chore/round-close-2026-08-09b||| 
chore/session-work-memory||| 
chore/skills-1.2.2-sync||| 
codex/archive/issue-301-pr311-reviewed-fd7343e||| 
codex/gh-stack-skill||| 
codex/graphify-0.9.39-kb||| 
codex/graphify-0942||| 
codex/issue-299-graphify-ast-baseline|origin/codex/issue-299-graphify-ast-baseline|| 
codex/issue-300-claude-semantic-slice||| 
codex/issue-301-graphify-0943-no-provider||| 
codex/kb-codex-migration||| 
codex/migration-source-sync||| 
docs-directive-addendum|||*
feat/lessons-tracked-and-gated||| 
fix-328-extraction-warnings||| 
main|origin/main|| 
salvage/canonical-worktree-snapshot||| 
salvage/doppler-critical-kb||| 
salvage/graphify-ecosystem-wip||| 
salvage/skillopt-heldout-evaluation||| 
salvage/skillopt-heldout-evaluation-v2||| 
salvage/stash-0||| 
salvage/stash-1||| 
```
Only `codex/issue-299-graphify-ast-baseline` and `main` carry an upstream ref at all.
`git fetch origin --quiet` ran clean (no new refs reported) — ref state above is current
against the remote as of this probe.

### git stash list
```
stash@{0}: On codex/graphify-0942: WIP 2026-08-13 all-tools currency reports preserved before Graphify 0.9.42 PR
stash@{1}: On main: WIP Graphify 0.9.42 currency assessment 2026-08-13
```

(continuing — ahead/behind + backup dir check next)

## Per-branch ahead/behind vs origin/main (git rev-list --left-right --count origin/main...<branch>)

Command run for every local branch:
```
git rev-list --left-right --count origin/main..."$b"
```
(behind ahead)

| branch | ahead | behind | `git branch --merged origin/main` |
|---|---|---|---|
| chore/round-close-2026-08-08g2 | 0 | 33 | YES |
| chore/round-close-2026-08-09b | 1 | 31 | no |
| chore/session-work-memory | 1 | 43 | no |
| chore/skills-1.2.2-sync | 2 | 59 | no |
| codex/archive/issue-301-pr311-reviewed-fd7343e | 2 | 10 | no |
| codex/gh-stack-skill | 1 | 24 | no |
| codex/graphify-0.9.39-kb | 0 | 24 | YES |
| codex/graphify-0942 | 2 | 15 | no |
| codex/issue-299-graphify-ast-baseline | 5 | 14 | no |
| codex/issue-300-claude-semantic-slice | 2 | 13 | no |
| codex/issue-301-graphify-0943-no-provider | 2 | 9 | no |
| codex/kb-codex-migration | 0 | 24 | YES |
| codex/migration-source-sync | 0 | 24 | YES |
| docs-directive-addendum (current) | 5 | 0 | no (unlanded round) |
| feat/lessons-tracked-and-gated | 0 | 24 | YES |
| fix-328-extraction-warnings | 2 | 5 | no |
| main | 0 | 0 | YES |
| salvage/canonical-worktree-snapshot | 1 | 24 | no |
| salvage/doppler-critical-kb | 3 | 24 | no |
| salvage/graphify-ecosystem-wip | 1 | 23 | no |
| salvage/skillopt-heldout-evaluation | 1 | 17 | no |
| salvage/skillopt-heldout-evaluation-v2 | 2 | 16 | no |
| salvage/stash-0 | 3 | 15 | no |
| salvage/stash-1 | 3 | 15 | no |

`branch --merged` is a red herring by itself here: this repo squash-merges via `kb-land`, so a
squash-merged branch's tip is NEVER an ancestor of `origin/main` even though its content landed.
Every "no" row below was resolved by content, not by that column alone — either (a) the PR that
merged its commits was found and its commit list diffed 1:1 against the branch's unique commits,
or (b) the branch's changed files were diffed against `origin/main` file-by-file.

## Per-branch disposition (content-verified)

### SUPERSEDED — content already landed on main under different commit hashes (safe, not at risk)

- **codex/issue-299-graphify-ast-baseline** (5 commits) — `gh pr view 307 --json commits` lists
  the exact same 5 commit subjects in the same order as `git log origin/main..codex/issue-299…`.
  PR #307 MERGED. Worktree `../worktrees/knowledge-base-299` has a clean `git status`.
- **codex/issue-300-claude-semantic-slice** (2 commits) — PR #308 commits match 1:1. MERGED.
  Worktree `-300` clean.
- **codex/graphify-0942** (2 commits) — PR #291 commits match 1:1. MERGED. Worktree
  `-graphify-0942` has 9 untracked lines (`.agents/skills/**`, `.codex/`) — regenerated
  local skill-mirror/config dirs, not authored content (verified: these are the same paths
  `.claude/CLAUDE.md`'s "Nine plugins" section and `kb-skill-refresh` generate; nothing under
  them is unique authored prose).
- **codex/issue-301-graphify-0943-no-provider** (2 commits) — PR #312 commits match 1:1.
  MERGED. Worktree `-301` clean. (Issue #301 itself is still OPEN, but that's the *next* scale
  step per the corpus circle already diagnosed — the code this branch/worktree holds already
  shipped in #312, so the worktree itself carries no unlanded risk.)
- **codex/archive/issue-301-pr311-reviewed-fd7343e** (2 commits: `fd7343e5`, `efea294b`) — `gh pr
  view 311` shows headRefName `codex/issue-301-complete-graphify-semantics` (a differently-named
  branch, since deleted/not in `git branch` output), state MERGED, title "feat(graphify): add
  sanitized parser diagnostics" — and `origin/main` carries `ad8f408d feat(graphify): add
  sanitized parser diagnostics (#311)`. Same feature, squashed under a different branch name.
- **fix-328-extraction-warnings** (2 code commits: `3d1336dc`, `4dfa328c`) — file-diffed
  `python/src/kb_setup/{graph.py,graphify_health.py,graphify_sdk.py}` between the branch and
  `origin/main`: main's current `graph.py` already carries the same `_ATTACCA_METADATA_ONLY_PATHS`
  hash-registration concept the branch introduced, reworked and extended (main's version has 8
  hash-pinned paths plus a "closed set, not sampled" derivation comment the branch didn't have;
  `graphify_health.py`/`graphify_sdk.py` differ by 113/454 lines respectively — main is strictly
  further along). Issue #328 is CLOSED, by `791f53c2` = PR **#338** "fix 328 extraction warning
  accounting" (confirmed via `git merge-base --is-ancestor 791f53c2… origin/main` → true, and
  `gh api …/issues/328/timeline` → `event: closed, commit_id: 791f53c2…`).
  **Exception, genuinely unrecovered** — 2 of this branch's files never reached main:
  `graphify-out/memory/query_20260816_194005_what_must_be_checked_before_running_a_large_deep_s.md`
  and `…query_20260816_194024_is_it_right_for_a_check_to_compare_my_re_derived_n.md` (verified
  MISSING via `git cat-file -e origin/main:<path>` on the real filenames from `git show
  fix-328-extraction-warnings --name-only`). The second is the "shadow implementation of the tool
  I was checking" lesson (`outcome: corrected`) — a real, well-written correction that never
  reached `LESSONS.md`. Trivial to recover: `git show fix-328-extraction-warnings:<path> >
  graphify-out/memory/<path>` on current branch, or cherry-pick just those two paths.
- **chore/round-close-2026-08-09b** (`c8b821ca`) and **chore/session-work-memory** (`771f022e`) —
  each adds exactly one `graphify-out/memory/query_*.md` file. Both files **EXIST on
  `origin/main`** today (verified via `git cat-file -e origin/main:<real-filename>`, using the
  actual filenames from `git show <sha> --name-only`, not a truncated `--stat` line — my first
  pass here mis-parsed the `--stat` ellipsis and nearly reported these as lost; see the
  self-correction note below). Superseded/already-present.
- **chore/skills-1.2.2-sync** — `e0eed632` bumps `codex`/`antigravity-cli` to 0.146.1/1.1.10;
  `origin/main`'s `mise.toml` is already AHEAD at 0.147.0/1.1.11. `efe20a23` adds "decision-ticket"
  language to `docs/issue-tracker.md`; `origin/main`'s current `docs/issue-tracker.md` already
  contains `**A wayfinder ticket is a DECISION ticket**` — same concept present (adopted via a
  different commit path). Superseded.
- **salvage/doppler-critical-kb** — adds 13 `sources/doppler-*` files + `doppler.manifest` +
  currency wiring. `origin/main` already tracks all 13 `sources/doppler-*` paths (`git ls-tree -r
  origin/main -- sources/ | grep doppler`) and `docs/currency/README.md` shows live doppler
  currency runs (2026-08-12 through 2026-08-16). Superseded.
- **salvage/skillopt-heldout-evaluation** and **-v2** — build a mock SkillOpt evaluator
  (`skillopt_eval.py`, `neutral-team-workflow` skill, `skillopt/evaluation/*` provenance JSON).
  `origin/main` has NEITHER of those files but instead has `skillopt_contract.py` +
  `skillopt_reviewed.py` — a different, lighter implementation. This matches the standing ruling
  already in `.claude/CLAUDE.md` ("SkillOpt is installed at an immutable VCS revision for the
  read-only `kb-skillopt-contract`; its mutable marketplace plugin is disabled"). Read as a
  **deliberate design pivot**, not lost work — flagging only so it isn't rediscovered as "missing".
- **salvage/stash-0** and **salvage/stash-1** — these ARE `stash@{0}` and `stash@{1}` (same WIP,
  pushed to branches, presumably for extra safety). `git diff --diff-filter=A --name-only
  origin/main <branch>` returns **zero** non-currency-run-log files for both — no unique content
  survives that isn't already superseded stale currency-run artifacts. Safe to drop (both the
  stash entries and these two branches).
- **codex/kb-codex-migration**, **codex/migration-source-sync**, **feat/lessons-tracked-and-gated**,
  **codex/graphify-0.9.39-kb** — `git log origin/main..<branch>` is empty for all four (0 ahead).
  Fully merged, safe to delete.

### GENUINELY UNIQUE, NEVER LANDED — real pending-work-at-risk

1. **`salvage/canonical-worktree-snapshot`** (commit `7dac6e72`, author "Codex Recovery
   <recovery@localhost>", 2026-08-13 20:09:17 +0000 — a crash/interruption recovery snapshot, NOT
   an ordinary feature branch). `git diff --diff-filter=A --name-only origin/main
   salvage/canonical-worktree-snapshot` lists **93 files added** relative to `origin/main` that
   were never confirmed superseded. After excluding 75 that ARE accounted for (stale
   `docs/currency/runs/2026-08-11-*` logs — ephemeral, low value; and
   `.agents/skills/graphify/references/*.md`, confirmed present under `.claude/skills/graphify/
   references/` on main, same content different prefix), **the following remain confirmed absent
   from `origin/main` anywhere in its tree** (checked via `git ls-tree -r --name-only origin/main
   -- python/src/kb_setup/` and `git grep -l "critical.corpus\|colibri" origin/main -- docs/
   python/`):
   - Seven Python modules with **zero trace on main**: `python/src/kb_setup/_render_lessons.py`,
     `codegen.py`, `colibri_canary.py`, `critical_corpus.py`, `extraction_inventory.py`,
     `graph_integrity.py`, `lessons.py`.
   - Their four tests: `tests/test_colibri_canary.py`, `test_critical_corpus.py`,
     `test_extraction_inventory.py`, `test_graph_integrity.py`.
   - 18 `graphify-out/memory/query_20260811_*.md` work-memory notes (critical corpus, colibri
     canary rejection rationale, dependency handling) — none present on main.
   - Research reports `docs/research/reports/2026-08-11-critical-corpus.md`,
     `2026-08-11-graphify-integrity.md`, and 4 `docs/research/runs/research-20260811-colibri-*` /
     `research-20260812-colibri-native-pause` reports.
   - New sources: `sources/chezmoi.manifest`, `sources/llama-cpp.manifest`,
     `sources/critical-corpus.toml`, plus 4 `sources/media/muse-glimmer-*` files and 2
     `sources/media/{claude-code,codex}-llms-full.md`, with matching `.receipts.json`.
   - `graphify-out/dependency-anchors.json`.

   **Why this matters and what it is NOT**: `MEMORY.md` lists "colibri bake-off" as a SPENT round
   ("measurements only ... do not redo") — so the *decision* (colibri rejected for deep
   extraction) is presumably already known to the current round through some other channel. But
   the actual ENGINEERING (7 modules + 4 tests + a `critical-corpus` source-tracking mechanism +
   `graph_integrity`/`extraction_inventory`/`lessons`/`codegen` infrastructure) has **no
   descendant on `origin/main` at all** — not superseded, not reworked, just absent. This sits
   only on a "Codex Recovery" WIP branch with no upstream, last touched 2026-08-13, five days
   stale against a fast-moving `main` (24 commits ahead). If this branch or its worktree is ever
   pruned, this content is gone. **This needs an explicit human decision: recover/rebase and land,
   or explicitly declare abandoned** — it should not be discovered by accident during a branch
   cleanup pass.

2. **`salvage/graphify-ecosystem-wip`** (commit `149c02e1`, same "Codex Recovery" authorship,
   2026-08-13 20:09:29 +0000, sourced from a **tempdir clone**
   `/private/tmp/kb-graphify-ecosystem.bmSQpv/repo` per its own commit message — i.e. this was a
   *second* repo clone's work, salvaged into this repo as a branch). Exactly **one** file is
   genuinely new vs `origin/main`: `docs/research/kb/reports/agents/
   adversarial-critic-graphify-ecosystem.md` (263 lines, dated 2026-08-12, "Durable adversarial
   replay of the Graphify ecosystem implementation proposals" — critiques "Twenty reviewed
   projects ... durably registered without unsafe graph ingestion"). Low-cost to recover (one
   file); unclear if its content is still relevant to the current ecosystem-registration design —
   worth a quick read before deciding to promote or drop.

3. **`codex/gh-stack-skill`** (commit `9a3cab2a feat(skills): add project-scoped gh-stack`, 142
   lines, adds BOTH `.agents/skills/gh-stack/SKILL.md` and `.claude/skills/gh-stack/SKILL.md`).
   Confirmed absent from `origin/main` under either path (`git cat-file -e
   origin/main:.claude/skills/gh-stack/SKILL.md` → fails). No PR found for this branch
   (`gh pr list --search "head:codex/gh-stack-skill" --state all` → empty). This is a small,
   self-contained, never-opened skill addition — real but low-cost, easy to resurrect or
   deliberately drop.

## Stash

`git stash list` shows exactly the 2 entries reported above. Both are **also branches**
(`salvage/stash-0`, `salvage/stash-1`) already covered above — content-diffed and found to add
nothing beyond stale currency logs already superseded on main. Not independently at risk beyond
what's already noted; the branches are the more durable copy of the same WIP.

## Backup directory

The ONLY concrete backup-directory reference in this session's inputs is the directive text
itself (`docs/direction/2026-08-18-ray-directives.md:36,79`, "the backup directory") — it names
no path. This iteration's `ALREADY_SETTLED` block also does not name a path. `_backups/` exists
one level up (`/Users/rmanaloto/dev/github/ray-manaloto/_backups/`) but its 2 files
(`guilde-lite-tdd-sprint-20260122T165903.tar.gz`, `…zip`, both dated 2026-01-22) belong to an
unrelated project (`guilde-lite-tdd-sprint`), not knowledge-base — verified by filename, no
`knowledge-base` string anywhere in that directory's contents. **This is itself a finding**: the
directive references "the backup directory" as if a specific one exists, and no artifact in this
session names which directory that is. Either the phrase is stale (referring to something already
resolved) or the actual backup location needs to be identified before this row of the directive
can be marked complete. Per the task scope I was given, I did not walk further external
directories to hunt for one — flagging the ambiguity for `main`/human resolution rather than
guessing.

## Self-correction logged during this pass

My first read of `chore/round-close-2026-08-09b` and `chore/session-work-memory` used
`git show <sha> --stat --format='' | head -1 | awk '{print $1}'` to get the changed filename —
this truncates any filename `--stat` renders with a leading `...` ellipsis or that contains
internal spaces-after-truncation, and I nearly reported both as "MISSING on main" (a false pending-
work finding) before re-deriving the real filename with `git show <sha> --name-only --format=''`
and finding both files DO exist on `origin/main`. Recorded per `probes-need-a-control-arm.md`:
the first probe was bound-limited (a display truncation) and gave a false negative; the control
was re-running with the unbounded form.

## COVERAGE

**Reached and analysed:** all 4 external `git worktree list` entries (worktree-299/300/301/
graphify-0942 — all confirmed clean or near-clean, all confirmed content-superseded via matching
merged PRs #307/#308/#291/#312); all 23 local branches other than the current
`docs-directive-addendum` (every one content-diffed against `origin/main`, not just
`ahead`/`behind` counts); both `git stash` entries (both shown identical to their branch twins,
already covered); the `_backups/` directory one level up (confirmed unrelated to this repo).
`git fetch origin --quiet` ran clean immediately before the ref enumeration, so the ahead/behind
figures above are current as of this pass, not stale.

**Opened but not fully finished analysing:** `salvage/graphify-ecosystem-wip`'s one unique file
(`adversarial-critic-graphify-ecosystem.md`) — read its title/opening only, did not assess whether
its critique content is still actionable against the current ecosystem-registration design.

**Never reached:** whether the 18 colibri/critical-corpus memory notes on
`salvage/canonical-worktree-snapshot` duplicate content that DID land elsewhere in `LESSONS.md`
or `MEMORY.md` under different wording (I checked file-path existence on `origin/main`'s tree, not
whether the *lessons* were manually re-transcribed into `graphify-out/memory/reflections/
LESSONS.md` by hand under a different filename/date) — worth a targeted `kb-query` before deciding
this content is truly unrecovered, since a lesson can survive in prose even when its file does
not. Did not open or diff the actual `_render_lessons.py`/`codegen.py`/`lessons.py` file CONTENTS
against main's current `python/src/kb_setup/` to check for partial overlap at the function level
(only checked file-path absence) — a function-level dedup pass is still owed before anyone decides
whether this is 7 modules of net-new work or partial duplication of logic that landed under
different filenames.

## Follow-up closure on the "never reached" item above

Checked after writing COVERAGE (upgrading this from "never reached" to "reached"): grepped
`graphify-out/reflections/LESSONS.md` (the current derived aggregate on this branch) for
"colibri" → **0 hits**. Also `git ls-tree -r --name-only origin/main -- graphify-out/memory/ |
grep -i colibri` → **0 of 197** tracked memory files on main mention colibri by filename. Control
arm: the same memory dir on main has 197 files total, so the grep is not failing on an empty
corpus. **The colibri-canary rejection rationale and the entire critical-corpus workstream have no
surviving trace anywhere reachable from `origin/main`** — the only copy is the 18 memory files +
7 modules on `salvage/canonical-worktree-snapshot`. This raises finding #1 above from "possibly
duplicated elsewhere" to "confirmed sole copy, at risk."
