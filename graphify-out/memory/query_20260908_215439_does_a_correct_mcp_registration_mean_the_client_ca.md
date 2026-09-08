---
type: "query"
date: "2026-09-08T21:54:39.571978+00:00"
question: "Does a correct MCP registration mean the client can reach the server, and did #701/#417 block Phase U?"
contributor: "graphify"
outcome: "corrected"
correction: "Two beliefs this round overturned, both inherited from handoffs and both acted\non by several sessions before anyone checked them against the primary source.\n\n1. **The #710 check spec was backwards.** Three handoffs said the check must\n   assert `.codex/config.toml` still HAS `[mcp_servers.kb]` and\n   `[mcp_servers.graphify]`. Measured: `HEAD` carries exactly ONE server section,\n   `kb`. The graphify entry is what the REWRITE ADDS, and this repo's own comment\n   block records that a project-level `graphify` entry colliding with the\n   user-global one broke codex outright. A check built to that spec would have\n   demanded the presence of the outage. It would also have passed on the\n   2026-09-04 damage, because the damage VARIES per occurrence — only \"every\n   comment destroyed\" was constant across all three mornings. The fix was to stop\n   enumerating symptoms and diff against the committed copy.\n\n2. **Phase U's blocker map named two non-blockers and missed the real one.**\n   Handoffs carried \"#701 blocks step 1\" and \"#417 blocks step 2\". #672 does not\n   mention #701 anywhere — not in its body, not in its Related list. #417 is not\n   a wall in front of a step; it IS U4, whose definition is \"unblock #417\". The\n   real blocker is #668, stated by #672 itself — *\"#668 first, or U5 and U7 are\n   wasted\"* — and no handoff had ever named it. Five of seven steps were\n   startable the whole time.\n\nThe shared shape: a claim asserted in one artifact was read as a fact about\nanother. #701 says it blocks Phase U; #672 never agreed. A handoff said the\nconfig file has a graphify entry; the file never did. **A one-directional claim\nis not a relationship, and the cheapest check is to read the OTHER end.**\n\nThe corollary that cost the most time: **\"registered\" is not \"reachable\".** A\ncorrect MCP config, a green unit suite, and a config file that says the right\nthing are each compatible with the mechanism never running. Only a live probe\ntells them apart — and when that probe fails, its message may come from a gate\nthat refused before the thing under test was ever contacted.\n"
---

# Q: Does a correct MCP registration mean the client can reach the server, and did #701/#417 block Phase U?

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

- Signal: corrected
- Correction: Two beliefs this round overturned, both inherited from handoffs and both acted
on by several sessions before anyone checked them against the primary source.

1. **The #710 check spec was backwards.** Three handoffs said the check must
   assert `.codex/config.toml` still HAS `[mcp_servers.kb]` and
   `[mcp_servers.graphify]`. Measured: `HEAD` carries exactly ONE server section,
   `kb`. The graphify entry is what the REWRITE ADDS, and this repo's own comment
   block records that a project-level `graphify` entry colliding with the
   user-global one broke codex outright. A check built to that spec would have
   demanded the presence of the outage. It would also have passed on the
   2026-09-04 damage, because the damage VARIES per occurrence — only "every
   comment destroyed" was constant across all three mornings. The fix was to stop
   enumerating symptoms and diff against the committed copy.

2. **Phase U's blocker map named two non-blockers and missed the real one.**
   Handoffs carried "#701 blocks step 1" and "#417 blocks step 2". #672 does not
   mention #701 anywhere — not in its body, not in its Related list. #417 is not
   a wall in front of a step; it IS U4, whose definition is "unblock #417". The
   real blocker is #668, stated by #672 itself — *"#668 first, or U5 and U7 are
   wasted"* — and no handoff had ever named it. Five of seven steps were
   startable the whole time.

The shared shape: a claim asserted in one artifact was read as a fact about
another. #701 says it blocks Phase U; #672 never agreed. A handoff said the
config file has a graphify entry; the file never did. **A one-directional claim
is not a relationship, and the cheapest check is to read the OTHER end.**

The corollary that cost the most time: **"registered" is not "reachable".** A
correct MCP config, a green unit suite, and a config file that says the right
thing are each compatible with the mechanism never running. Only a live probe
tells them apart — and when that probe fails, its message may come from a gate
that refused before the thing under test was ever contacted.
