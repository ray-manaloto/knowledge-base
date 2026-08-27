---
type: "query"
date: "2026-08-27T17:06:34.201877+00:00"
question: "What is true at the end of round 2026-08-27d, and how does the next session retrieve it?"
contributor: "graphify"
outcome: "useful"
---

# Q: What is true at the end of round 2026-08-27d, and how does the next session retrieve it?

## Answer

HOW TO RETRIEVE THIS — READ FIRST, because the obvious way does not work.

`graphify-out/memory/` is WRITE-ONLY (#540): 280 files, ZERO of them reachable
from `mise run kb-query`. Querying the graph for anything in this file returns
nothing, and that absence is the storage layer, not the world. Retrieve these
points by READING FILES:

    ls -t graphify-out/memory/ | head -20          # newest first
    grep -rl "<term>" graphify-out/memory/          # find by content
    cat graphify-out/reflections/LESSONS.md         # the aggregated view

`/kb-resume` reads the newest `.agent/plans/session-*.md`, which points here.
That handoff is the entry point; this file is the detail behind it.

================================================================================
ROUND 2026-08-27d — WHAT IS TRUE AT THE END OF IT
================================================================================

## 1. #397's blocker is FIXED. #397 is NOT closed.

MEASURED, `mise run kb-build`, file-based rc both ways:
    before  11 sources fail; {timeout: 1, unclassified-files: 10}; 56 paths
    after    0 preflight failures across 85 built sources

The fix is in `kb_setup.graphify_sdk.classify_unclassified` — this repo's own
absorption layer, NOT the fork. Ray reopened the settled `.graphifyignore`
mechanism once it was clear the rejected alternative had been mislabelled "the
fork's classifier".

`kb-build` STILL EXITS 1. It now dies in EXTRACTION on `ast-grep` (Cargo.toml
zero nodes, upstream graphify #1666). That is #417's family. #397's acceptance
criterion 3 stays open behind it. A green preflight is not a green build.

## 2. THE FINDING OF THE ROUND — #551. The graph cannot see our own code.

    kb_setup modules on disk        77
    kb_setup modules in the graph   61
    ABSENT from the graph           25  (32%)  <- includes BOTH files this PR changed
    in graph but not on disk         9  (stale)

Control-armed: `grep -o -m 40 'kb_setup/hook_guard\.py'` -> 40 hits;
the same grep for `graphify_sdk.py` -> 0. Same directory, same build.

Worse than absence: `graphify affected "assess()"` does not miss, it ANSWERS —
with a Swift function in a DIFFERENT ingested repo. Pre-#1504 node IDs collide
same-name symbols across 85 sources and the tool resolves rather than refuses.
`affected "classify_unclassified()"` returns "No unique node match", which
conflates ZERO matches with SEVERAL.

Not explained by staleness alone: `classify_unclassified` was added 2026-08-16,
FIVE DAYS BEFORE the graph was built, and is still missing.

## 3. Why the tool's own features were invisible — and it was not the graph

`graphify prs` and `callflow-html` both EXIST in installed 0.9.50 and are both
ABSENT from `graphify --help` — 18 verbs are. Ray had asked for both BY NAME.

The graph knew. One query — `kb-query -- "graphify prs PR dashboard review queue
worktree mapping"` — returns `graphify/prs.py` as the THIRD result with its own
description. It was never a corpus gap. Two derived sources were consulted
(`--help`, and the `/graphify` skill's Usage block, which is generated and
auto-loaded every session) and the live one was not.

LESSON, and it generalises: a tool's `--help` is a SECONDARY artifact about
itself and it ages. Before driving a pinned tool in a new way, query the graph
about the TOOL, not just about the code being changed.

`graph_first` is satisfied ONCE PER SESSION, so six graph queries about the code
bought a whole day of never querying about the tool. graphify's own guard is
better here: `GRAPHIFY_HOOK_STRICT_TTL` (default 1800s) RE-ARMS.

## 4. graphify ships its own enforcement, it is installed, and the deny is DEAD

`.claude/settings.json` already runs two graphify PreToolUse hooks
(`hook-guard search`, `hook-guard read`). `GRAPHIFY_HOOK_STRICT=1` turns the read
one into a blocker with no reinstall.

DO NOT SET IT YET. Armed all five gate conditions directly:
    1 strict_enabled      : True     <- the env var IS read
    2 tool_name ok        : True
    3 not stamp_fresh     : True
    4 target_is_indexed   : False    <- DEAD HERE
    5 mark_session_denied : True
`_target_is_indexed` reads `graphify-out/manifest.json`, which does not list our
files. Setting the flag today gives a config line that looks like enforcement and
blocks nothing. It is downstream of #417, not a config knob.

Also: `mise.toml` `[env]` is the WRONG transport — `MISE_PROJECT_ROOT` is absent
from the shell Claude Code's hooks inherit. The right place is `--strict` on the
hook command in `.claude/settings.json`.

## 5. Open tickets this round created or touched

    #397  blocker fixed, criteria 1/2/3/5 open, blocked behind #417
    #417  the extraction tail — depth UNKNOWN, one rebuild per source to find out
    #549  three CLI under-reporting bounds (12-extension tally cap, 128-entry
          census cap, raw tracebacks) — filed this round
    #551  the graph-blindness finding above — filed this round, P1
    #541  kb-ship refuses on untracked docs/artifacts — THE UNCOMMITTED-FILES
          COMPLAINT. Live example this round: an artifact published mid-round sat
          untracked until clear-prep swept it.
    #546  52 of 73 manifests pin `ref = main` — the next task
    #491  ffmpeg is now `build = defer` citing it
    #540  graphify-out/memory/ is write-only — why the retrieval note above exists

## 6. Process lessons that cost time THIS round

- PROSE TO A CLI GOES VIA A FILE. Backticks in a `--correction` string and again
  in a `gh issue create --title` were EXECUTED by zsh. Both writes exited 0 and
  both landed with a HOLE where the word should be. Caught only by reading back
  what was written. Use `--correction-file`; stat what you wrote.
- `ruff format` MOVES MUTATION ANCHORS. A `kb-arms` arm came back PROBE BROKEN
  because the formatter reflowed the guard after the arm was written. A broken
  probe reads exactly like a survivor if you only read the summary line.
- `… | tail -N; echo "rc=$?"` reports TAIL's status. Done during /verify, on the
  very probe checking exit codes.
- A `cd` in one Bash call PERSISTS into the next.
- A PATH PREFIX IS AN IDENTITY CLAIM, again: grepping `sources/graphify/README.md`
  returned 0 and nearly became "the README is not ingested". The graph stores it
  relativized as `graphify/README.md`. #551 survived re-probing without the
  prefix assumption; that one did not.


## Outcome

- Signal: useful