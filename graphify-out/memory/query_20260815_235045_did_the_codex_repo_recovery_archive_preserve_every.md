---
type: "query"
date: "2026-08-15T23:50:45.340396+00:00"
question: "Did the codex repo-recovery archive preserve everything, and what state was the repo left in?"
contributor: "graphify"
outcome: "useful"
---

# Q: Did the codex repo-recovery archive preserve everything, and what state was the repo left in?

## Answer

# Catching up after codex: what the backup covered, and what it did not

## The question

Codex worked here 2026-08-12 → 08-14 while the Claude budget was empty. Did the
`~/.codex/archives/repo-recovery/20260813T195951Z` archive preserve everything, and
what state was the repo actually left in?

## What the backup DID cover

- **228 preservation refs**, fetchable — the vault is a bare git repo, so
  `git fetch <vault> 'refs/preservation/*:refs/salvage/*'` recovers everything in one
  command.
- All 24 bundles verify `rc=0` — **but only when run as `git -C <repo> bundle verify
  <abs-path>`**. From a non-repo cwd every bundle fails with `need a repository to
  verify a bundle`, which reads as total data loss and is a false negative.
- Snapshot `149c02e1` is a real commit (parent `dffe600`, ref-reachable, 725 files)
  that reconstructs the `/private/tmp/kb-graphify-ecosystem` working tree exactly:
  compared file by file, **29 identical, 0 differ, 0 present only in tmp**.
- Snapshot `7dac6e72` (831 files) holds **16 work-memory records that reached no
  branch and are not on main** — including a 51,875-byte colibri evaluation. They were
  never committed, not deleted.

## What the backup did NOT cover

**The archive is a point-in-time snapshot and stops at 2026-08-13T19:59:51Z.**
Codex kept working through the 14th, so everything after that is outside it:

- **6 of 15 local branches** absent from the vault, all dated 08-13/08-14.
- **Both stashes** — `900dd46c` and `d1b658d8`, holding `docs/currency/*` deltas —
  absent from the vault and reachable only from `refs/stash`.
- **2 dirty worktrees** (main: 10 changed, graphify-0942: 9 changed).

Mitigation: most post-freeze branch content squash-landed via merged PRs, and
`codex/issue-301-graphify-0943-no-provider` shows literally **0 files differing** from
`origin/main`. But the stashes and dirty trees are genuinely uncovered.

## The repo state codex left

- **No graph at all.** `graphify-out/graph.json` absent; `mise run kb-query` exited 2.
  A complete 771 MB / **492,229-node** graph was sitting in `frozen-originals`,
  stamped at `e4142de`. Restoring it makes queries work again.
- **The graphify version is split five ways**: `pyproject.toml` and the manifest say
  0.9.43, while `graphify_baseline.py:221` `_ACCEPTED_GRAPHIFY_REF`, the dispositions
  file, the `sources/graphify` clone, and the skill stamp all say 0.9.42.
- **Nothing reports skill-stamp drift.** `currency/skill.py` is a writer reachable only
  from `apply`; `grep skill python/src/kb_setup/currency/sync.py` returns nothing.
- **`tool_sync.eligible_tools()` returns `('ffmpeg',)`** — 1 of 12 tools. Five are
  refused by one line (`tool_sync.py:181`) for a provenance lane that does not exist.

## The design behaviours worth keeping

- **A restored graph must not be stamped.** The stamp records what ACTUALLY RAN; a copy
  is not a build. Verified the repo reports this honestly with no help: *"artifacts have
  never been stamped"* and *"no graph has been built here yet"*. Its own test says it —
  `test_build_stamp_records_a_stale_binary_honestly`: *"the stamp reports what happened,
  it does not assert what should have happened."*
- **`kb-query` exits 3 on the restored graph**, because graphify emits a `pre-#1504
  node-ID scheme` warning and the zero-skip gate refuses a result with unread stderr.
  Reading works; gating does not.

## What is now true

13 branches pushed to origin (6 `salvage/*`, 5 post-freeze `codex/*`, plus
`salvage/canonical-worktree-snapshot`). Nothing unique remains only on this machine.


## Outcome

- Signal: useful