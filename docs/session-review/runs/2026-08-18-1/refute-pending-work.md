# Refutation lane: pending-work "backup directory" finding

CLAIM: Ray's directive (docs/direction/2026-08-18-ray-directives.md:36,79) says
"don't lose pending work ... on the backup directory" but no artifact in this
session or the prior round names which directory that is; the only external
_backups/ dir found belongs to an unrelated project.

## Probe 1 — primary artifact, directive lines (CONFIRMS half of the claim)

    grep -n -i 'backup' docs/direction/2026-08-18-ray-directives.md
    36:> and we ensure we dont lose any pending work on git worktrees and/or branches of from the backup directory
    79:| 6 | Lose no pending work on worktrees / branches / the backup directory | Three worktrees exist under `../worktrees/`, plus ~20 local branches. Not audited this session. |

Two hits, 233-line file, no path in either. That sub-claim holds.
Note line 79 DOES name `../worktrees/` for the worktrees half.

## Attack vectors on the second half
1. token spelling: `backup` only. Variants: backups, _backups, bak, .bak, archive, snapshot, stash.
2. bound: ONE path probed (`/Users/rmanaloto/dev/github/ray-manaloto/_backups/`).

## VERDICT: REFUTED

### Probe A — an artifact in THIS session names the directory (3.5h before the finding)

    grep -rn -i -E 'repo-recovery|\.codex/archives|backup director' --include='*.md' .agent/
    .agent/kb/reports/agents/pending-work.md:23:backup directory Ray references EXISTS at `~/.codex/archives/repo-recovery/` —
    .agent/kb/reports/agents/pending-work.md:168:**It exists: `~/.codex/archives/repo-recovery/`** — `20260813T195951Z/`

    stat -f '%Sm %N' -t '%Y-%m-%d %H:%M:%S' ...
    2026-08-18 06:27:09 .agent/kb/reports/agents/pending-work.md      <- prior run of THE SAME LANE
    2026-08-18 09:56:52 .agent/kb/reports/agents/iter1/pending-work.md <- the finding under test

The prior run even diagnoses the exact failure the iter1 run then repeated,
verbatim (pending-work.md:172-174):
    "The earlier settled-block hunt bounded itself to `~/dev` and so could not
     have found it."

CONTROL for this grep: same command shape, `-i worktree` over the same 153
`.agent/**/*.md` files -> 24 files. The probe discriminates.

### Probe B — TWO COMMITTED corpus artifacts name the exact path

    git grep -n 'repo-recovery'
    graphify-out/memory/query_20260815_235045_did_the_codex_repo_recovery_archive_preserve_every.md:18:`~/.codex/archives/repo-recovery/20260813T195951Z` archive preserve everything, and
    graphify-out/memory/query_20260815_235053_was_hk_s_typos_step_failing_on_committed_work_memo.md:19:`~/.codex/archives/repo-recovery/20260813T195951Z` archive preserve everything, and

    git log -1 --format='%H %ad %s' --date=short -- graphify-out/memory/query_20260815_235045_*.md
    98b116fd24512ad8893261359d647fc96bb83103 2026-08-15 feat(graphify): resync every pin to 0.9.44 ... (#325)

Committed, tracked, survives a clone. That memory note enumerates precisely the
directive's subject: "6 of 15 local branches absent", "Both stashes ... absent",
"2 dirty worktrees". Plus untracked auto-memory
`~/.claude/projects/-Users-.../memory/a-backup-stops-at-its-timestamp.md:11`.

### Probe C — the directory is REAL and holds knowledge-base work

    ls /Users/rmanaloto/.codex/archives/repo-recovery/20260813T195951Z/bundles
    knowledge-base-66c77cc80f8e.bundle
    knowledge-base-6f548c5b2a30.bundle
    knowledge-base-b99ee895b5c4.bundle
    knowledge-base-df09dbfa4f56.bundle
    (+ dotfiles-*.bundle, preservation-vault.bundle, 24 total)
    FREEZE-STATUS.md: "Created and verified 23 Git-store bundles", "Imported and
    verified 217 local branch/tag refs in the independent bare preservation vault",
    "11 dirty-worktree WIP snapshot commits".

So "the only external _backups/ dir found belongs to an unrelated project" is
false: the relevant one is not spelled `_backups` and is not under `~/dev`.

### Why the original probe COULD ONLY have said no

Two bounds, both self-declared in the finding's own report
(.agent/kb/reports/agents/iter1/pending-work.md:245-248):
  "Per the task scope I was given, I did not walk further external directories"
and one hard-coded path spelled `_backups`.

TOKEN SPELLING is the bound: the directory is `archives/repo-recovery`, containing
no substring "backup" at all. Control arm proving the search space was never
exhausted:
    cd /Users/rmanaloto/dev && find . -maxdepth 6 -iname '*backup*' ... -> 50+ hits
    find /Users/rmanaloto -maxdepth 2 -iname '*backup*' -> 10 hits incl.
      /Users/rmanaloto/backups, /Users/rmanaloto/claude-backups, ~/.claude/backups
None of which the original probe asked about — and none of which is the answer
either, because the answer is spelled differently.

### Contradiction with another finding in the set

`.agent/kb/reports/agents/iter1/forgotten.md:132` states the same claim
("Item 6's 'the backup directory' is unresolved ambiguity nobody has asked Ray to
disambiguate"). Both are refuted by the SAME prior artifact. Two lanes in this
iteration reached the same wrong answer from the same bound — a correlated probe
defect, not two independent confirmations.

What survives: the directive lines 36/79 genuinely name no path (probe 1), and
the prior report's own residual finding stands — the archive's identity is
recorded only in untracked auto-memory + committed work-memory, never in a
tracked doc/issue. That is a real gap, but it is "under-published", not "unknown".
