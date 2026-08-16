---
type: "query"
date: "2026-08-15T23:50:53.787070+00:00"
question: "Was hk's typos step failing on committed work-memory files, and was the earlier green a caching artifact?"
contributor: "graphify"
outcome: "corrected"
correction: "# A probe's output is not the gate's output — attributing mine to hk's cost two wrong claims\n\n## The belief that was wrong\n\n`mise run lint` failed on `typos` with `✗ typos – ERROR` and no diff. I ran `typos`\nby hand over `graphify-out`, saw two committed work-memory files flagged\n(`togglable`, and `PN` inside `PNGs`), and reported to Ray that:\n\n1. hk was failing on those two memory files, and\n2. the EARLIER lint run, which had reported `✔ typos`, was therefore a **false green** —\n   probably hk step caching.\n\nBoth were wrong, and I asked for a suppression decision on the strength of them.\n\n## What was actually true\n\n- **`graphify-out/memory/**` is already in `proseExclude`, and `typos` already uses it**\n  (`hk.pkl:206`). hk never handed those files to `typos`. My manual invocation passed\n  the paths directly, which bypasses hk's exclude entirely. **I read my own probe's\n  output as the gate's.**\n- **There was no false green.** The passing run had **416** files, the failing one\n  **418**. The two extra were `.mcp.json` and `graphify-out/.vocab.txt` — and I had\n  restored `.vocab.txt` *after* the passing run. The first green was correct; I invented\n  a caching theory to explain a delta I had caused.\n- **The real cause** was `graphify-out/.vocab.txt`, an 18,686-line derived word list\n  matching neither `.graphify_*` nor any literal name in `baseExclude`. Untracked, hk\n  hands it to `typos`, which exits **2 with zero bytes on stdout AND stderr** — a step\n  that fails as `ERROR` with nothing to read. Control-armed: that file → rc=2, 0 bytes;\n  `.mcp.json` → rc=0.\n\n## The rule\n\n**When a gate fails, reproduce it through the gate, not around it.** A hand-run of the\nunderlying tool uses different arguments, different excludes and a different working\nset, so its output answers a different question. `long-running-command-hangs.md` rule 6\nsays to run the underlying tool directly when lint *hangs* — that is for locating a\nwedge, and it is not licence to attribute the tool's findings to the step. Here the\nroute back was `hk run check -S <step> -v`, which prints the exact argv and the real\nfile list; it named `.vocab.txt` immediately.\n\n## The second-order damage\n\nBecause I believed the memory files were the cause, I offered Ray two remedies. One of\nthem — \"exclude `graphify-out/memory/` wholesale\" — is the exact thing `hk.pkl:16`\nforbids **by name**, because on 2026-07-28 a `kb-remember` note landed with three live\ntokens in it and gitleaks went green. A wrong diagnosis does not stay contained; it\nproduced a remedy that would have reopened a closed security hole, and Ray approved it\non my framing before I caught it.\n\n**A misdiagnosis is more expensive than a missing diagnosis**, because it arrives with\na recommendation attached.\n"
---

# Q: Was hk's typos step failing on committed work-memory files, and was the earlier green a caching artifact?

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

- Signal: corrected
- Correction: # A probe's output is not the gate's output — attributing mine to hk's cost two wrong claims

## The belief that was wrong

`mise run lint` failed on `typos` with `✗ typos – ERROR` and no diff. I ran `typos`
by hand over `graphify-out`, saw two committed work-memory files flagged
(`togglable`, and `PN` inside `PNGs`), and reported to Ray that:

1. hk was failing on those two memory files, and
2. the EARLIER lint run, which had reported `✔ typos`, was therefore a **false green** —
   probably hk step caching.

Both were wrong, and I asked for a suppression decision on the strength of them.

## What was actually true

- **`graphify-out/memory/**` is already in `proseExclude`, and `typos` already uses it**
  (`hk.pkl:206`). hk never handed those files to `typos`. My manual invocation passed
  the paths directly, which bypasses hk's exclude entirely. **I read my own probe's
  output as the gate's.**
- **There was no false green.** The passing run had **416** files, the failing one
  **418**. The two extra were `.mcp.json` and `graphify-out/.vocab.txt` — and I had
  restored `.vocab.txt` *after* the passing run. The first green was correct; I invented
  a caching theory to explain a delta I had caused.
- **The real cause** was `graphify-out/.vocab.txt`, an 18,686-line derived word list
  matching neither `.graphify_*` nor any literal name in `baseExclude`. Untracked, hk
  hands it to `typos`, which exits **2 with zero bytes on stdout AND stderr** — a step
  that fails as `ERROR` with nothing to read. Control-armed: that file → rc=2, 0 bytes;
  `.mcp.json` → rc=0.

## The rule

**When a gate fails, reproduce it through the gate, not around it.** A hand-run of the
underlying tool uses different arguments, different excludes and a different working
set, so its output answers a different question. `long-running-command-hangs.md` rule 6
says to run the underlying tool directly when lint *hangs* — that is for locating a
wedge, and it is not licence to attribute the tool's findings to the step. Here the
route back was `hk run check -S <step> -v`, which prints the exact argv and the real
file list; it named `.vocab.txt` immediately.

## The second-order damage

Because I believed the memory files were the cause, I offered Ray two remedies. One of
them — "exclude `graphify-out/memory/` wholesale" — is the exact thing `hk.pkl:16`
forbids **by name**, because on 2026-07-28 a `kb-remember` note landed with three live
tokens in it and gitleaks went green. A wrong diagnosis does not stay contained; it
produced a remedy that would have reopened a closed security hole, and Ray approved it
on my framing before I caught it.

**A misdiagnosis is more expensive than a missing diagnosis**, because it arrives with
a recommendation attached.
