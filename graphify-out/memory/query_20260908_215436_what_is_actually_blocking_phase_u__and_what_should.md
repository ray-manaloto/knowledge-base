---
type: "query"
date: "2026-09-08T21:54:36.184735+00:00"
question: "What is actually blocking Phase U, and what should the .codex/config.toml check assert?"
contributor: "graphify"
outcome: "useful"
---

# Q: What is actually blocking Phase U, and what should the .codex/config.toml check assert?

## Answer

# Round 2026-09-08 — the #710 tripwire, codex 0.153.4, and #668's three doors

## What shipped

Two commits on `feat/codex-config-tripwire-and-phase-u`, gates 8/8 on each.

`b8e1e8e39ad8`
- `kb_setup.codex_config` — a SessionStart tripwire on `.codex/config.toml`,
  diffing the worktree against the committed copy. Advisory, always exits 0, so
  the arm is the OUTPUT not the rc. Three verdicts: CLEAN (silent), CHANGED
  (warn + print the recovery stash command), UNKNOWN (warn, "NOT a pass").
  12 tests; live-armed both directions.
- A binding-note rule in `.claude/rules/clarify-before-acting.md`.
- codex 0.153.1 -> 0.153.4 across the mise pin, `mise.lock` and
  `sources/codex.manifest`; the grafted clone re-fetched to the pinned commit.
- #672 and #701 corrected on the tracker.

`4bc6bc13f69c`
- `default_tools_approval_mode = "approve"` on `[mcp_servers.kb]` in
  `.codex/config.toml`.

## The durable finding: reaching a graph takes THREE doors, not one

#668 was framed as "register the local stdio server in both clients".
Registration is necessary and is nowhere near sufficient. Measured:

1. **Registered?** Both clients already were. Done before this round.
2. **Allowed to ask?** Codex was not. At approval policy `never` — which is what
   `mise run kb-codex` runs at — an MCP tool call is denied BEFORE the server is
   contacted (`sources/codex/codex-rs/core/src/mcp_tool_call.rs:1535`). The lane
   reported `KB-UNREACHABLE`, which reads exactly like a broken server.
   `default_tools_approval_mode = "approve"` short-circuits it, because
   `codex-rs/codex-mcp/src/mcp/mod.rs:95-97` returns auto-approved BEFORE the
   policy test. Read from the pinned source, per Ray's directive 4.
3. **Can it load the graph?** No — the codex-spawned server cannot open the
   529 MB `graphify-out/graph.json`, while the identical command under Claude
   loads it fine (`mcp__kb__graph_stats` -> 359,146 nodes / 807,085 edges).
   OPEN; this is the next session's task.

Doors 2 and 3 print nearly the same thing. Believing door 2's message would have
sent a session hunting a broken server that was working perfectly.

## The probe trap, control-armed

A SINGLE bare pattern passed to `git ls-remote --tags` suppresses the `^{}`
peeled line exactly as `--refs` does:

    git ls-remote --tags <url> rust-v0.153.4       -> ONE line, no ^{}
    git ls-remote --tags <url> | grep rust-v0.153  -> TWO lines, ^{} present

The one-line output is indistinguishable from a lightweight tag, so it reads as
"no peeled line here" rather than "you filtered it out". Following it would have
pinned `042fb41b…` (the tag object) instead of `3d2ee51c…` (the commit).
Control arm: 0.153.1's bare line is `f5c2c463…` while its `^{}` line is
`98564127…` — the value already committed, proving the peeled line existed.
Recorded in `sources/codex.manifest`.


## Outcome

- Signal: useful