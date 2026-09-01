---
type: "query"
date: "2026-09-01T00:23:55.993119+00:00"
question: "How do you correctly set up codex lanes and the graphify MCP at project level, and what silently fails?"
contributor: "graphify"
outcome: "useful"
---

# Q: How do you correctly set up codex lanes and the graphify MCP at project level, and what silently fails?

## Answer

# Setting up codex lanes correctly at PROJECT level (measured 2026-08-31)

Five facts, each verified this session against a primary source, not inferred.

## 1. Codex does NOT sign in to an MCP server on first use — every other client does

This is the single highest-value fact here. graphify's own setup page states it
outright: "still run `codex mcp login graphify` afterwards -- unlike the other
clients here, Codex does not sign in on first use."

Consequence: a codex `[mcp_servers.<name>]` entry can be perfectly correct and
still fail `AuthRequired` on every launch forever, because nobody ran the
one-time login. That is exactly what happened here — the url was right from the
start and the failure was read for weeks as a config defect.

`codex mcp list` has an **Auth** column and answers this directly:
`Not logged in` vs `OAuth`. Check it before theorising about config.

Control arm when verifying a login: after `codex mcp login graphify`, graphify
read `OAuth` while `exa` and `context7` still read `Not logged in` — the target
moved and the controls did not.

The full correct entry is three lines, not two:

    [mcp_servers.graphify]
    url = "https://api.graphify.com/mcp"
    auth = "oauth"

Auth is an OAuth handshake — there is no key to paste, and nothing goes in a
secret store. On builds before remote MCP was first-class, graphify's page also
notes `[features] experimental_use_rmcp_client = true` above the entry.

## 2. Do NOT pin a model in every agent mirror — codex has a project-level default

`config-file/config-reference/index.md:638,644` (codex-docs):

- `agents.default_subagent_model` — "Default model for spawned agents. An
  explicit spawn model takes precedence."
- `agents.default_subagent_reasoning_effort` — same for effort.

So a repo with N `.codex/agents/*.toml` mirrors needs TWO lines in
`.codex/config.toml`, not N edits, and every mirror stays free to override.
Reaching for N edits here is the `use-tool-builtins.md` failure — the native
mechanism existed and was not being used.

Effort enum, from the sample config: `minimal | low | medium | high | xhigh`,
with `xhigh` noted as model-dependent and Responses API only.

## 3. Project config beats user config — but ONLY for trusted projects

`config-file/config-basic/index.md:35` — the layer order puts project
`.codex/config.toml` at layer 2 and `~/.codex/config.toml` at layer 4, closest
file wins. So project-level pinning genuinely overrides a user config the repo
does not own.

The gate nobody mentions: "Codex loads project `.codex/` layers only when you
trust the project." Verify before relying on ANY project-level codex config —
including hooks — by checking for `[projects."<abs path>"] trust_level =
"trusted"` in the user config. If a project is untrusted, its `.codex/config.toml`,
its hooks and its rules are all silently ignored.

`codex doctor` does NOT surface this; it names only the user config path.

## 4. Codex clamps SessionEnd hook timeouts to 3 seconds, at discovery time

`codex-rs/hooks/src/events/session_end.rs:23` — `SESSION_END_MAX_TIMEOUT_SEC:
u64 = 3`, applied in `engine/discovery.rs:729-751` as
`timeout_sec.unwrap_or(1).clamp(1, 3)` for SessionEnd against `unwrap_or(600)`
for every other event. A declared `"timeout": 60` is discarded before any
process spawns, and codex prints a `warning: clamping SessionEnd hook timeout to
3s in <path>` that nothing reads.

`kill_on_drop(true)` + `process_group(0)` mean a detached spawner does NOT
escape — it would need `setsid` and would still race a 5s app-server teardown.

The fix is to move session-end work to `Stop` (which keeps the 600s default) with
`SessionStart` as a repair sweep. `Stop` fires PER TURN, not per session, so
idempotence and session-keying are load-bearing before any such move.

## 5. A vendored source clone can be STALE under a CORRECT pin

`sources/codex.manifest` pinned `rust-v0.151.0` while `sources/codex/` was checked
out at 0.148.0, because `build = skip` short-circuits before the clone step so
`kb-build` never re-fetches it. The pinned SHA was not even present in the clone.

This is worse than an absent source. An absent source returns nothing and you
look elsewhere; a stale clone answers confidently, with plausible `file:line`
citations, from the wrong version. Three separate readers cited it in one session
before anyone checked which version it was.

Before citing any `sources/<name>/` line number, check
`git -C sources/<name> rev-parse HEAD` against the manifest's `commit`.


## Outcome

- Signal: useful