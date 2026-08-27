---
type: "query"
date: "2026-08-27T08:12:28.944067+00:00"
question: "Is ingesting the 346 auto-memory topic files the first move for shrinking MEMORY.md?"
contributor: "graphify"
outcome: "corrected"
correction: "The belief: **the way to shrink `MEMORY.md` is to ingest its 346 auto-memory\ntopic files into the graph as a corpus source.** I proposed that as the one\nunblocked path, and it was wrong about ORDER in a way that hid a much larger\ndefect.\n\n**The probe that refuted it.** Before ingesting anything, ask whether the graph\nalready covers the material. Three questions whose answers live only in this\nproject's history, plus one control:\n\n| asked | top score | what came back |\n|---|---|---|\n| annotated tag pins the tag object | 13.19 | a YouTube transcript on SHA-256 |\n| a review round finds defects in the last fix | 14.56 | an anthropic.com migration blog |\n| compliance is a rate, not a yes | 12.82 | the Claude Code glossary |\n| **CONTROL** — graphify god nodes | **18.56** | graphify's own analyze / AGENTS.md / how-it-works |\n\nThe control outscores every miss and returns three correct sources, so the probe\ndiscriminates. Three for three, the graph knows other people's writing about a\ntopic and nothing about this repo's own experience of it.\n\n**The cause, measured:** `CLAUDE.md` contributes **0** nodes. `.claude/rules/**`\nand `.claude/skills/**` contribute **0** — the 92 `.claude/` nodes are `.py`,\n`.json` and `.js` only. Meanwhile `python/src/kb_setup` contributes **2,386** via\nfree AST extraction, and external docs and blogs are **3,647 prose nodes, 74.9%\nof the prose graph**.\n\n**The lesson: the knowledge base contains its own code and none of its own\ndoctrine.** Every rule the agents are instructed to obey, every skill, every\ndirective, is absent from the graph those same agents are hook-DENIED from\nbypassing. So the first ingestion move is not personal memory at all — it is this\nrepo's own tracked prose: already committed, no privacy decision, ~30 markdown\nfiles, and it would have turned all three probe misses into hits. The 346\npersonal topic files are move three.\n\n**The generalisable habit:** before proposing to ingest anything, run the recall\nprobe with a control arm. It costs four queries and it re-ordered a plan that\nlooked settled. A corpus that has never been asked what it does NOT know will\nalways look adequate.\n\n**Second correction in the same round, same shape:** my first attempt to measure\nthis bucketed nodes by path prefix and reported \"79,186 own-repo nodes\". Wrong —\n`docs/registry.data.ts` and `tests/main/jsonschema/` belong to INGESTED sources\nwhose own trees carry those directory names. A path prefix is an identity claim,\nand it needs the same control arm as any other probe.\n"
---

# Q: Is ingesting the 346 auto-memory topic files the first move for shrinking MEMORY.md?

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

- Signal: corrected
- Correction: The belief: **the way to shrink `MEMORY.md` is to ingest its 346 auto-memory
topic files into the graph as a corpus source.** I proposed that as the one
unblocked path, and it was wrong about ORDER in a way that hid a much larger
defect.

**The probe that refuted it.** Before ingesting anything, ask whether the graph
already covers the material. Three questions whose answers live only in this
project's history, plus one control:

| asked | top score | what came back |
|---|---|---|
| annotated tag pins the tag object | 13.19 | a YouTube transcript on SHA-256 |
| a review round finds defects in the last fix | 14.56 | an anthropic.com migration blog |
| compliance is a rate, not a yes | 12.82 | the Claude Code glossary |
| **CONTROL** — graphify god nodes | **18.56** | graphify's own analyze / AGENTS.md / how-it-works |

The control outscores every miss and returns three correct sources, so the probe
discriminates. Three for three, the graph knows other people's writing about a
topic and nothing about this repo's own experience of it.

**The cause, measured:** `CLAUDE.md` contributes **0** nodes. `.claude/rules/**`
and `.claude/skills/**` contribute **0** — the 92 `.claude/` nodes are `.py`,
`.json` and `.js` only. Meanwhile `python/src/kb_setup` contributes **2,386** via
free AST extraction, and external docs and blogs are **3,647 prose nodes, 74.9%
of the prose graph**.

**The lesson: the knowledge base contains its own code and none of its own
doctrine.** Every rule the agents are instructed to obey, every skill, every
directive, is absent from the graph those same agents are hook-DENIED from
bypassing. So the first ingestion move is not personal memory at all — it is this
repo's own tracked prose: already committed, no privacy decision, ~30 markdown
files, and it would have turned all three probe misses into hits. The 346
personal topic files are move three.

**The generalisable habit:** before proposing to ingest anything, run the recall
probe with a control arm. It costs four queries and it re-ordered a plan that
looked settled. A corpus that has never been asked what it does NOT know will
always look adequate.

**Second correction in the same round, same shape:** my first attempt to measure
this bucketed nodes by path prefix and reported "79,186 own-repo nodes". Wrong —
`docs/registry.data.ts` and `tests/main/jsonschema/` belong to INGESTED sources
whose own trees carry those directory names. A path prefix is an identity claim,
and it needs the same control arm as any other probe.
