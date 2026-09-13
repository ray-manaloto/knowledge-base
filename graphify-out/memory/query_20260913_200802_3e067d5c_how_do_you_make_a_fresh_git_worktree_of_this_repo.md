---
type: "query"
date: "2026-09-13T20:08:02.070966+00:00"
question: "How do you make a fresh git worktree of this repo usable, and what did building it reveal about fail-closed checks?"
contributor: "graphify"
outcome: "useful"
---

# Q: How do you make a fresh git worktree of this repo usable, and what did building it reveal about fail-closed checks?

## Answer

# S0 — `kb-worktree-ready`, and what four review lanes found in it

## What shipped

`mise run kb-worktree-ready` (PR #783, branch `feat/worktree-add`, HEAD
`b3aaae788b2f2589e27473614fd020cf9bd693a3`). It makes a fresh `git worktree` of
this repo usable: a fresh worktree has ZERO `sources/*` clones and no
`graphify-out/`, so two end-to-end tests fail there and pass in the main
checkout at the same base, and `kb-query` exits 2.

Measured on the shipped commit, both arms, one variable:

| arm | result |
|---|---|
| unprepared worktree | rc 1 — both tests fail, naming the missing clones |
| after the task | rc 0 — both pass, **2 seconds**, **13,812 KB of real disk** |

`kb-query` in a prepared worktree returns nodes (rc 3, the truncation guard)
against rc 2 `no graph at …` unprepared — the worktree half of #778.

## The mechanism, and why the obvious one was wrong

The DAG unit said *symlink the main checkout's `sources/`*. Symlinks are wrong
at EVERY granularity, and this took an advisor consult to establish:

- whole-`sources/` symlink shadows the worktree's own committed manifests with
  the donor's, and `git status` reports 177 tracked files as DELETED;
- per-clone symlinks preserve the manifests but leave 97 permanently UNTRACKED
  entries: `.gitignore`'s `sources/*/` has a TRAILING SLASH so it matches
  directories only, and a symlink is mode 120000. No per-worktree ignore file
  exists to hide them — both candidate locations were armed and neither works.

The answer is copy-on-write. But NOT `/bin/cp -c`, which is where the first
implementation went wrong.

## The finding that matters most

**`/bin/cp -c` cannot fail closed, so a fail-closed design cannot be built on
it.** Apple's man page: *"if the target filesystem does not support cloning, cp
will fallback to using copyfile(2) instead to ensure the copy still succeeds."*

The first implementation compensated by parsing `mount(8)` and requiring both
sides to report `apfs`. A cold review armed that layer and found it wrong twice
over, **each way resolving toward PERMIT**:

1. a mountpoint containing a SPACE did not match the regex, and the lookup then
   fell through to the longest match that did — always `/`, which is `apfs`.
   A non-clonable volume read as clonable.
2. `apfs AND apfs` is not `same volume`, and `clonefile` is single-volume.
   Measured across two real APFS volumes: `/bin/cp -c` returned rc 0 with empty
   stderr while consuming 62,918,656 bytes — a full physical copy reported as
   success.

Neither function was wrong alone, which is why no arm on either could find it —
two "resolves toward yes" defaults composing into an answer neither would give
(`probes-need-a-control-arm.md` rule 10).

**Calling `clonefile(2)` directly deletes the whole class.** It returns EXDEV
across volumes and ENOTSUP where cloning is unsupported, and never falls back.
Armed: same volume rc 0; two APFS volumes EXDEV; HFS+ EXDEV; existing
destination EEXIST; missing source ENOENT; and a cloned tree's `.git/HEAD`
survives, which `graphify_catalog` requires. The `mount` parser, its regex, its
two helper functions and their two tests are GONE rather than fixed.

## The ratio worth remembering

Four lanes ran. Each refuted something the caller had written:

| lane | what it refuted |
|---|---|
| `kb-codex-advisor` | symlinks at every granularity — including the caller's own per-clone counter-proposal |
| `fable-orchestrator:premise-verifier` | a DROPPED requirement (donor quiescence) and a settings key in a shape that does nothing |
| cold review round 1 (antigravity) | the fail-closed check failed OPEN, two independent ways |
| cold review round 2 (antigravity) | 7 findings, **5 inside round 1's own fixes**, 1 blocking |

Round 2's blocking finding was in the caller's own guard: `Path.exists()`
FOLLOWS symlinks, so a DANGLING symlink read as absent, the guard said "go copy
it", and `clonefile(2)` wrote a whole clone at the link's target OUTSIDE the
worktree — from a guard whose own message reads *"Not touching a path this task
did not create"*. On the graph path it returned `created`, rc 0.


## Outcome

- Signal: useful