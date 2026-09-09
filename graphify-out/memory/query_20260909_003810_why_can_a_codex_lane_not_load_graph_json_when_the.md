---
type: "query"
date: "2026-09-09T00:38:10.170810+00:00"
question: "Why can a codex lane not load graph.json when the identical server under Claude loads it fine?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why can a codex lane not load graph.json when the identical server under Claude loads it fine?

## Answer

# Door 3: a codex-spawned MCP server gets an ELEVEN-NAME env allowlist

`mise run kb-codex` asking the local `kb` server for `graph_stats` answered
`could not load graph.json`, while the IDENTICAL `uv run kb-setup serve` under
Claude loaded it fine. Three sessions attributed this to a timeout, the lane
sandbox, or a memory ceiling. All three were wrong about the first wall.

**A codex stdio MCP server does not inherit the shell environment.** It is built
from a fixed allowlist — HOME, LOGNAME, PATH, SHELL, USER,
__CF_USER_TEXT_ENCODING, LANG, LC_ALL, TERM, TMPDIR, TZ
(`sources/codex/codex-rs/rmcp-client/src/utils.rs:163-175`) — plus whatever the
per-server `env_vars` names and `env` sets (`create_env_for_mcp_server`,
`:16-58`). So `mise.toml`'s `GRAPHIFY_MAX_GRAPH_BYTES = "1GB"` is STRUCTURALLY
unable to reach it, and graphify falls back to its stock 512 MiB cap. This is
independent of `[shell_environment_policy] inherit`, which governs shell calls.

Two-armed on the real function (`graphify.security.check_graph_file_size_cap`):
with the var -> cap 1_073_741_824, PASS; stripped -> cap 536_870_912 and
`ValueError: graph file … is 553_662_506 bytes, exceeds 536_870_912-byte cap`.
Over the stock cap by 16_791_594 bytes.

**Why it stayed hidden for three sessions: the error deletes its own cause.**
`serve.py:80-82` prints that ValueError to the server's STDERR and
`sys.exit(1)`s; `serve.py:130-131` catches the SystemExit and re-raises
`RuntimeError(f"could not load graph.json at {resolved_path}")` — `from exc`, so
the client sees a path and no reason.

**Fixing it revealed a SECOND wall, and that one IS a timeout:** `timed out
handshaking with MCP server after 29.999999917s`. A warm `initialize` +
`tools/list` measured 21.0 s (parse 7.5 + trigram index 13.0 + communities 0.1 =
20.5 s of graph work over 359_146 nodes, peak RSS 2.92 GiB). The server pins its
default graph before answering, so that cost is inside the handshake budget.
`startup_timeout_sec` / `tool_timeout_sec` = 120.

Fixed by passing the NAME through (`env_vars = ["GRAPHIFY_MAX_GRAPH_BYTES"]`),
not by restating "1GB" in a second place — `mise.toml` stays its one owner.

ARM: `mise run kb-codex` -> graph_stats -> 359146. Claude control arm re-run
after the change -> 359146 nodes / 807085 edges. Both sides agree.

**The transferable lesson: a message CHANGING is how you know a fix landed on a
stack of walls; a message REPEATING is how you know it did not.** The first fix
looked like a failure until the two error strings were compared.


## Outcome

- Signal: useful