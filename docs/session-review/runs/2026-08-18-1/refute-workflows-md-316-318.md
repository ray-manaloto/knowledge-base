# REFUTED — `workflows.md:316` / `:318` cache-key + prefix-hold citation is EXACT upstream

Commit under review: f772f5eb (`perf(session-review): tier every agent…`).
Comment: `.claude/workflows/session-review.js:308` (and `:409`).

## Verdict

**refuted = true.** The finding is a WRONG-ARTIFACT probe. It read
`sources/agent-harness-docs/docs/claude-code/workflows.md` — a third-party
mirror repo (`mrkhachaturov/agent-harness-docs`) pinned at commit
`33aef930acb2e56154a056dd7e1dfd08b9a3cf3e`, 404 lines — and concluded the
mechanism "does not appear … at all". The comment cites the CANONICAL doc,
`https://code.claude.com/docs/en/workflows.md` (411 lines), where both line
numbers land **exactly**.

## Probe (live, primary artifact)

```
curl -sS https://code.claude.com/docs/en/workflows.md -o live-workflows.md
# http=200 bytes=32787 ; 411 lines
grep -n -iE "cach|prefix|hold all|release together|output schema" live-workflows.md
```

Verbatim:

```
314:### Prompt caching in a fan-out
316:Agents in the same run can read each other's [prompt cache](/docs/en/prompt-caching#subagents-and-the-cache). Two agents that run with the same model, effort level, agent type, tools, output schema, and working directory build the same tools-and-system-prompt prefix, so an agent that starts after a matching sibling's response has begun reads that sibling's cache on its first request.
318:When a fan-out starts several matching agents at once, Claude Code holds all but the first until the first agent's response begins, then releases the held agents together so their first requests read the shared prefix instead of each processing it uncached. Claude Code caps the hold at [`CLAUDE_CODE_WORKFLOW_PREFIX_STAGGER_MS`](/docs/en/env-vars) milliseconds, `5000` by default. Set it to `0` to disable the hold.
```

- `:316` = "same model, effort level, agent type, tools, **output schema**, and
  working directory" → the comment's "makes the OUTPUT SCHEMA part of the cache
  key: agents share a prefix only when model, effort, agent type, tools, output
  schema and cwd all match" is a faithful paraphrase, same line.
- `:318` = "**holds all but the first** until the first agent's response begins,
  then **releases the held agents together**" → the comment's "hold all but the
  first, release together once the first response begins" is near-verbatim, same line.

## Control arm (the probe discriminates)

Same command shape, two artifacts:

```
sed -n '316p' sources/agent-harness-docs/docs/claude-code/workflows.md
  -> The runtime applies the following constraints:            (mirror, stale)
sed -n '316p' live-workflows.md
  -> Agents in the same run can read each other's [prompt cache]…   (canonical)
```

So `sed -n '316p'` can return either answer; the original probe's "no" was an
artifact of which file it was pointed at.

## Cross-check that settles it: the OFFSET is exactly the new section

The same commit's other citation, `session-review.js:409` → `workflows.md:360`
("warns past 25 agents"):

```
mirror: 353:Claude Code also flags a run that grows unusually large. When a workflow schedules more than 25 agents, …
live:   360:Claude Code also flags a run that grows unusually large. When a workflow schedules more than 25 agents, …
```

353 + 7 = 360, and the live file is 411 − 404 = 7 lines longer — exactly the
7 lines of the new `### Prompt caching in a fan-out` section (313–319). Both
citations in the commit are internally consistent with the live doc and both are
off by the same 7 on the mirror. A single author reading the live doc explains
every number; nothing else does.

## Is the mirror "this repo's only ingested copy"? No — and the second one also
## predates the section

`mise run kb-query -- "workflow agents prompt cache prefix output schema cache key" --prose --idf`
surfaces `[src=code.claude.com_docs_en_workflows.md]` nodes — a SECOND ingested
representation, via `sources/extractions/claude-docs-docs.json` (captured
2026-07-22) and `sources/extractions/claude-docs-refresh-2026-08-07-part2-docs.json`
(2026-08-07). Both hold only the `resume`/cached-results nodes
(`cc_workflows_resume`, `ccworkflows_resume_replay_order`), no fan-out prefix
node — consistent with the section being newer than 2026-08-07, i.e. newer than
every ingested snapshot. `raw/` holds no copy (`ls raw | grep -i workflow` → rc 1).

So the finding's "only ingested copy" is also inaccurate, and its 3 `cach` hits
in the "Resume after a pause" section are precisely what BOTH stale snapshots
contain — the corroborating detail that they are snapshots of the pre-section doc.

## What the finding got right, narrowly

The corpus is stale on this page. That is a corpus-freshness item (re-ingest
`code.claude.com/docs/en/workflows`), not a defect in `session-review.js`. The
comment is correct as written and its line numbers resolve on the doc it names.

## GitHub repos touched

- [mrkhachaturov/agent-harness-docs](https://github.com/mrkhachaturov/agent-harness-docs) — the pinned mirror the original probe read (commit 33aef930…)
