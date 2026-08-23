# Refutation attempt — finding 33 (lane pending-work), SHA c720f1c9

CLAIM: "Uncommitted changes to python/src/kb_setup/graphify_semantic_corpus.py (+206)
and tests/test_graphify_semantic_corpus.py (+273) sit only in the working tree — not on
any branch, not stashed, not committed. This is the real content of the sixth
'Lane 3 round 2, in flight at review time' commit."

## Probes run (all in /Users/rmanaloto/dev/github/ray-manaloto/knowledge-base, HEAD c720f1c9)

1. `git status --short` -> 9 modified files, including both named files. (2 of 9)
2. `git diff --numstat`:
   163  43  python/src/kb_setup/graphify_semantic_corpus.py
   270   3  tests/test_graphify_semantic_corpus.py
   total: 9 files changed, 542 insertions(+), 71 deletions(-)
   => the claim's "+206"/"+273" are NOT insertions. 163+43=206, 270+3=273: those are
   `git diff --stat` TOTAL-CHANGED-LINES columns, reported with a "+" sign. Real
   insertions are 163 and 270.
3. `git diff --cached --numstat` -> EMPTY. Index == HEAD, so nothing is staged.
4. `git ls-files -s` blob == `git rev-parse HEAD:<path>` blob for both -> index clean.
   worktree `git hash-object` = 7b50dfaf... vs HEAD 45c39800... => genuinely dirty.
5. NOT COMMITTED ANYWHERE — control-armed:
   `git log --all --reflog --oneline -S 'DuplicateGroupMismatchError' | wc -l` -> 0
   control `git log --all --reflog --oneline -S '_MAX_TOTAL_COST_USD' | wc -l` -> 3
   (d8114ab1, 37f6a1c5, + reflog). The -S probe discriminates.
6. NOT STASHED: `git stash list` -> 2 entries, both dated 2026-08-13 on other branches;
   `git show --stat <stash> -- <both paths>` -> empty for both.
7. Evidence claims verified verbatim in the diff:
   `-_MAX_TOTAL_COST_USD = 140.0` / `+_MAX_TOTAL_COST_USD = 63.0`
   (HEAD line 93 = 140.0; worktree line 107 = 63.0); DuplicateGroupMismatch appears
   5 times in the diff hunks and 0 times in all of git history.

## The surprise: the only copy was stashed and popped WHILE I MEASURED

First probe (15:29:5x UTC) returned `git hash-object` == the HEAD blob for BOTH files
simultaneously; 60s later it returned the dirty blob. A partial write cannot reproduce
HEAD's exact hash for two files at once, so the cause is a concurrent git operation:
  .git/ORIG_HEAD    mtime 15:30:42Z
  .git/logs/refs/stash mtime 15:30:52Z  (content still only the two 08-13 entries)
  both source files mtime 15:30:52Z
  .git/index        mtime 15:32:19Z
i.e. a `git stash` (ORIG_HEAD + reflog write, worktree reverted to HEAD) followed by a
`git stash pop` (reflog entry removed, files restored) inside a 10-second window, by the
still-running agent of finding 9. That STRENGTHENS the finding: the single copy of 479
changed lines was destroyed and restored while unobserved.

## Verdict: NOT REFUTED on substance; one figure mislabelled, one clause overreaching.

## REFUTED — the opposite answer, three ways

### 1. The work IS committed. Commit 964fb112, 2026-08-21T10:33:16-05:00 (15:33:16Z)
`git show --stat --format='%H %cI %s' 964fb112`:
    964fb112d0dfcaf9c8c4af83326f5957c59ecbc7 2026-08-21T10:33:16-05:00
    fix(corpus): answer cold review of #414 - remove a dead assert, arm the
    untested reasons, re-derive the cap post-dedupe
     docs/agents/graphify-semantic-corpus.md            |  16 +-
     .../2026-08-21-414-content-dedupe-arms.toml        |  46 +++-
     .../2026-08-21-426-runtime-derive-arms.toml        |  14 +-
     mise.toml                                          |  11 +-
     python/src/kb_setup/graphify_semantic_corpus.py    | 206 ++++++++++++----
     .../src/kb_setup/graphify_semantic_corpus_run.py   |  10 +-
     tests/test_graphify_semantic_corpus.py             | 273 ++++++++++++++++++++-
     7 files changed, 505 insertions(+), 71 deletions(-)
`git rev-parse 964fb112:<both paths>` -> 7b50dfaf… / 8225654d… == the exact blobs
the finding measured. `git diff --numstat HEAD -- <both>` -> EMPTY.
CONTROL (same probe, both directions): `git log --all --reflog -S
'DuplicateGroupMismatchError' | wc -l` = 0 at 15:30Z, = 1 at 15:35Z; the known-present
control token `_MAX_TOTAL_COST_USD` = 3 at 15:30Z. The probe discriminates.

### 2. "sit ONLY in the working tree" was already false at 15:30:42Z
A dangling STASH COMMIT holds the identical blobs:
`git fsck --dangling` -> `dangling commit 82cad32f1ebfafc9c7ce746b03e8c3e4e96b2ce7`
`git log -1 --format='%ci %s' 82cad32f` -> `2026-08-21 10:30:42 -0500 WIP on
corpus-gate-bundle-0821: c720f1c9 …`
`git rev-parse 82cad32f:python/src/kb_setup/graphify_semantic_corpus.py` -> 7b50dfaf…
(identical to worktree). A `git stash` + `git stash pop` ran at 15:30:42–15:30:52Z
(.git/ORIG_HEAD 15:30:42Z, .git/logs/refs/stash 15:30:52Z, both source files 15:30:52Z),
which is why my first `git hash-object` read returned the HEAD blobs for both files.
So the work was recoverable from the object DB (`git fsck --lost-found`) even before
964fb112 — "not stashed" is true only of `git stash list`, not of the object store.

### 3. The two figures are mislabelled and the scope is wrong
- "+206" / "+273" are the `git diff --stat` TOTAL-CHANGED columns (163+43=206,
  270+3=273). Real insertions: 163 and 270. The sibling lane report
  (.agent/kb/reports/agents/pending-work.md:26) says "206 + 273 lines changed",
  correctly; the "+" was added downstream.
- "This is the real content of the sixth commit": the sixth commit is SEVEN files /
  505 insertions / 71 deletions. The two named files are 479 of 576 changed lines.
  .codex/config.toml was NOT part of it (correctly — it is the #399 drift) and
  docs/direction/2026-08-21-ray-directives.md is still uncommitted.

## Cross-finding
- Finding 9 measured the same tree (9 files, +542/−71) — I reproduce it exactly. It
  contradicts 33's 2-file scoping; 9 is the accurate one.
- Findings 13 / 35 (.codex/config.toml "remains dirty right now") are ALSO now stale:
  `git status --short .codex/config.toml` empty, worktree OTEL count 0, mtime 15:35:18Z.
- Only remaining dirty path at 15:35:29Z: `docs/direction/2026-08-21-ray-directives.md`
  (finding 9's live half — still true).
