---
type: "query"
date: "2026-08-27T08:12:28.354591+00:00"
question: "What do Ray's five PART TWO directives of 2026-08-26 actually resolve to when measured against the code and the disk?"
contributor: "graphify"
outcome: "useful"
---

# Q: What do Ray's five PART TWO directives of 2026-08-26 actually resolve to when measured against the code and the disk?

## Answer

# PART TWO of the 2026-08-26 directives, measured

Ray's five PART TWO directives were filed verbatim on 2026-08-26 with an explicit
instruction not to act on them, only to analyse them in the next session. This
round did that, then grilled the analysis to fifteen settled decisions.

## The five, and what measurement said

1. **Lift the graphify ban for one global source tree?** No — but the goal is
   right and they do not conflict. `cli.py:4256` shows `extract --global` writes
   the project's own `graph.json` and then calls the identical `_global_add` on
   it: global is strictly ADDITIVE, never a replacement for per-project trees.
   Its merge is wrapped in `except Exception: print(..., file=sys.stderr)` and
   then exits 0 — a silent-loss path. What delivers the actual goal is #130's
   federated retrieval plus #109, both ticketed since August, neither built.

2. **Every function a generated wrapper type?** Half. The generator is pinned at
   `pyproject.toml:88` and has never produced a file. "Every function" is 1,310
   `def`s. Adopt at the SEAM layer: `kb_setup.result.Rc` already exists
   (`result.py:57`, an IntEnum imported by 23 modules), and `result.py:184`
   records that a payload was deliberately not attached — that is the gap.

3. **Stop typing the /orchestration + /graphify prefix?** One
   `UserPromptSubmit` hook. This repo declares ZERO of them; every hook is
   PreToolUse, SessionStart or SessionEnd, so nothing can speak before the model
   reads a prompt. `/graphify` is already redundant with the graph-first DENY.

4. **Context at 20% before the first prompt — is MEMORY.md the cause?** Wrong
   culprit. The index is 24,308 B over 106 lines, INSIDE the documented cap, and
   costs ONE load in the main thread only — `sub-agents.md:935` states auto
   memory is not loaded into non-fork subagents, and 0 of the 6 roster agents
   declare `memory:`. The structured-output half is a TRANSPORT problem: 32
   paths already emit JSON and `mise run` re-flattens them.

5. **Honest adversarial read.** Every one of the four above was already decided,
   written down, and never consumed. Five instances in one session: #490 had the
   memory cap right; #540 answered the exact ingestion question; #130 had the
   federation answer; #120 is fixed and stale-open; and a 2026-08-05 research
   report named the `graphify clone --out` fix while 4.5 GB accumulated for three
   more weeks.

## Outcome

Fifteen decisions settled across four `/grilling` rounds, all filed: issues #546,
#547, #548 created; #130, #397, #454, #491, #525 commented. Two artifacts
committed (`7f7090ca`, `3ff01837`). Ray overrode one recommendation (`.graphifyignore`
over the fork classifier) and verifying that override produced a decision nobody
had chosen: the ignore's walk ceiling is the nearest VCS root, every clone has
its own `.git`, so the exclusion must be a committed manifest field written into
the clone after fetch.

Separately, `~/.graphify/repos` — 79 clones, 88,551 files, 4.5 GB, only 11
overlapping this corpus's 92 manifests — was archived and removed, reclaiming
4.52 GiB. Tracked in #544 and #545.


## Outcome

- Signal: useful