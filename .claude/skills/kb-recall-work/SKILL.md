---
name: kb-recall-work
description: "Find what already exists on a topic BEFORE designing anything: tracked files and design pages, local branches and worktrees (with ahead/behind and merged-by-squash), GitHub issues open and closed, every plan (.planning, .agent/plans, ~/.claude/plans) and the work-memory — each with an examined count beside its matches. Use this as phase 0 of any workflow, whenever the user asks to design, plan, build or re-decide something, whenever they say we have worked on this before or ask what prior work exists, and before filing an issue or writing a spec. Never skipped: Ray, 2026-09-09, 'ensure we never forget this'."
---

# Recall work — what already exists, before anything is designed

`mise run kb-recall-work -- "<topic>"` is the search Ray asked for on 2026-09-09
after a design round found, by hand, 13 published pages, ~10 plans, 7 handoffs,
~12 unmerged branches and 199 issues that already existed for its topic. **The
detection is entirely in python** (`kb_setup.recall_work`, #727); this skill says
when to run it and how to read what comes back.

## Run it

```bash
mise run kb-recall-work -- "dependency upgrade"            # the full search
mise run kb-recall-work -- "dependency upgrade" --offline  # no gh: branches read unverified
mise run kb-recall-work -- "dependency upgrade" --json     # the generated contract, for a script
```

Bare words are the topic. `--no-siblings` restricts it to this repo (by default
`../graphify` and `../dotfiles` are examined when present); `--repo PATH` adds a
checkout; `--top N` bounds the memory hits and `--limit N` the rows per probe.
The report is written to `.agent/kb/recall/<slug>.md` and the path is printed.

## Read it as a denominator, never as a list

Seven probes, and each one prints **examined** beside **matched**. That pairing
is the whole design: a `0` next to `4,213 examined` is a finding, a `0` next to
`could_not_ask` is not, and the two never share a column.

| probe | what was searched | the rule |
|---|---|---|
| `tracked_files` | every tracked file, minus `graphify-out/`, `sources/`, `raw/` | a file must contain EVERY stem |
| `artifact_pages` | the `docs/artifacts/*.html` subset, with each page's title | same |
| `branches` | local + origin branches in each repo, ahead/behind its base | a name matches on ANY stem — but EVERY branch is in the census |
| `worktrees` | linked worktrees | listed whatever the topic |
| `issues` | GitHub search, open AND closed, `examined` = every issue in the repo | the topic words; `could_not_ask` on a rate limit, never `0` |
| `plans` | `.planning/*/{task_plan,findings,progress}.md`, `.agent/plans/session-*.md`, `~/.claude/plans/*.md` | EVERY stem |
| `memory` | `kb-recall`'s BM25 over `graphify-out/memory/` | ranked, top N shown |

**The stems are printed on every run** (`dependency upgrade` -> `dependenc,
upgrad`). A topic spelling is a bound: a branch named for its ticket number or
a plan written in synonyms is not found, and the report says so rather than
implying it looked everywhere. Widen the topic and run again.

**The branch census is the hygiene input.** Every branch with unique commits is
listed live-first, with `merged` (no unique commits, or a merged PR found for
that head), `live` (unique commits, GitHub asked, no merged PR), `unverified`
(GitHub could not be asked, or `--offline`) and `current` (checked out in a
worktree — never a deletion candidate from here). Delete only `merged`; read a
`live` one before deciding; re-run online before trusting an `unverified`.

## The two exits that are not "done"

- **rc 127 and no report** — nothing was examined (the root is not a git
  checkout, every probe could not ask). Fix the environment; do not proceed.
- **rc 127 with a report** — something was examined and the topic matched
  nothing; the message names every count and the stems. The branch census is
  still on disk. Decide whether the topic was too narrow BEFORE designing.

A workflow step that consumes this must treat both as a stop, never as "no prior
work, carry on" — that is the mistake the command exists to make impossible.

## Close the loop

A run that changes what you were about to design is a lesson: record it with
`mise run kb-remember` (question: the topic; answer: what existed) so the next
session's `memory` probe finds it at rank 1.

## See also

- `.claude/rules/research-doc-sources.md` step 0 — where this sits in the chain.
- `.claude/skills/kb-session-reflect/SKILL.md` — the sibling that reads the
  previous round instead of the topic.
- `python/src/kb_setup/recall_work.py` — the module; `schemas/recall-work.schema.json`
  — the generated output contract.
