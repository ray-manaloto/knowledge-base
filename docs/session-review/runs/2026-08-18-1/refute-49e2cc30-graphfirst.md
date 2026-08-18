# Refutation: "Session 49e2cc30 has 0% graph-first compliance ... zero kb-query calls"

Session file: `/Users/rmanaloto/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/49e2cc30-3352-4cb9-939d-b19f5ce68acb.jsonl`
(4,765,347 bytes = 4.5M, 2,377 lines — matches the finding's size.)

## VERDICT: REFUTED. The session made 1 `mise run kb-query` call.

The original probe was `grep -o '"command":"[^"]*mise run kb-query'` -> 0.
That regex CANNOT match this session's only kb-query call, because the
`[^"]*` character class stops at the first `"` byte, and the real command
contains an escaped quote BEFORE the kb-query token.

Actual command (JSON-decoded from a `tool_use` block, Bash):

    git status --short && git log --oneline -3 && echo "---" && mise run kb-query -- "semantic corpus runner merge chunks into aggregate graph" 2>&1 | head -40

Raw jsonl bytes contain `... && echo \"---\" && mise run kb-query ...`, so
`"command":"[^"]*mise run kb-query` dies at the `\"` of `\"---\"`.
This is the classic bound-in-the-probe failure, not an absence.

## Control arm (proves the original probe discriminates, and undercounts)

Original probe run over ALL sessions in
`/Users/rmanaloto/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/`:

    for f in "$D"/*.jsonl; do n=$(grep -o '"command":"[^"]*mise run kb-query' "$f" | wc -l); ...

returns >0 on many files (e.g. `0397ba62` = 5, `05bb8e33` = 3), so it is not a
dead probe. But the JSON-parsed probe on the SAME files returns higher numbers
(`0397ba62` = 8, `05bb8e33` = 5, `0e0d824b` = 2 vs 1, `30024828` = 1 vs 0),
i.e. the `[^"]*` bound systematically drops any kb-query that follows a quoted
token in the same command. `49e2cc30` is the case where that dropped the ONLY one.

## Second, independent route: the repo's own guard state

`kb_setup.graph_first._state_path` (python/src/kb_setup/graph_first.py:131) writes
`.agent/state/graph-first/<session_id>.queried` when a graph query is issued.

    $ ls -la .agent/state/graph-first/49e2cc30-3352-4cb9-939d-b19f5ce68acb.queried
    -rw-r--r--@ 1 rmanaloto staff 0 Aug 17 11:11 .../49e2cc30-...queried

The marker EXISTS. Control arm: only 13 markers exist in that directory across
hundreds of sessions, so absence is a producible outcome and the probe discriminates.

## The query also SUCCEEDED (not merely issued)

`tool_use id toolu_01N8Hmr6Ff9yJohgV9LYi8ai`, `is_error: False`, result contains:

    [kb-query] $ uv run kb-setup query 'semantic corpus runner merge chunks into ag…
    Traversal: BFS depth=2 | Start: ['aggregate()', 'aggregate', 'Corpus', ...] | 168 nodes found

So "queried the existing graph zero times" is false on both the issue and the
execution reading.

## The subsidiary counts also fail to reproduce

Measured by JSON-parsing every `tool_use` block:
Bash 272 · Edit 69 · SendUserMessage 29 · Read 20 · Write 16 · AskUserQuestion 7 ·
Monitor 4 · ToolSearch 2 · Skill 2 (total 421). Grep tool = 0, Glob tool = 0.

- `Read = 20` reproduces.
- Bash commands containing `grep|rg|find|ls` = **127**, not 104. Total = 147, not 124.

## A committed artifact already contradicts the metric's framing

`docs/research/reports/2026-08-17-session-review.md:175` grades the graph-first
ratio **MISLEADING**: `session_reflect.py:543` "scans **only Bash tool calls**, so
every `mcp__graphify__*` call ... contributes 0 to the numerator while `Read`/`Grep`
still increment the denominator. The ratio is biased by construction."
Line 484 files the fix. A "0% compliance" headline rests on a metric this repo
has already recorded as biased.

## Verdict

REFUTED. The zero was produced by a regex bound (`[^"]*` vs a `\"` earlier in the
command), not by an absence. 1 successful `mise run kb-query` (168 nodes returned),
corroborated by the on-disk graph-first marker.
