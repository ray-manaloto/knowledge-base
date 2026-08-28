---
type: "query"
date: "2026-08-28T16:19:39.666331+00:00"
question: "slice 3b: how does the marketplace acceptance test prove an agent can install the aggregated-research plugin from the READMEs alone, and what did the round teach?"
contributor: "graphify"
outcome: "useful"
---

# Q: slice 3b: how does the marketplace acceptance test prove an agent can install the aggregated-research plugin from the READMEs alone, and what did the round teach?

## Answer

Slice 3b (marketplace issue #2, PR #3 → eb3ba05, 2026-08-28): a Claude agent given only the marketplace and plugin READMEs installs the marketplace, its four dependency marketplaces and the plugin inside one mise-OCI container; a second fresh `claude -p` fires the plugin's SessionStart hook cold and the script asserts `hook_response.outcome == success` and `init.plugins` from the stream-json output. Session-2 wall clock 20–22 s (four green runs); the hook never approached the 600 s command-hook default.

Lessons, each measured this round:
1. A scoped Bash allowlist `Bash(claude *)` DENIES the command form both READMEs teach (`VAR=value claude …`, `cd … && claude …`) — permission rules match each subcommand independently with no assignment stripping; in `-p` mode nobody can approve. Fix = prompt constraint (bare commands), never a looser allowlist.
2. A NEGATIVE gate on an undocumented schema (`has("repo")|not`) fails OPEN — five jq fixtures showed a nested GitHub marker passing. Gate on the positive marker you observed (`.source == "directory"`, `.path == "/work"`), or on bytes on disk.
3. Three vacuous-pass gates the premise-verifier found before dispatch: steps b/c must not run in the token path; the PR-vs-main distinction needs its own assertion; the README prints the hook command, so the data dir must be asserted EMPTY before the "cold" session.
4. My own addendum premise was wrong once: I read `init.plugins[].path` (`/work/aggregated-research`) and cited it as `installPath`, which is always a `plugins/cache/…` copy — the check could never pass and cost one red run. Two fields, one look-alike value, one run eyeballed.
5. The codex-implementer lane reports as plain messages (no CODEX REPORT block, #559 n=6), its sandbox refused `.git/` writes, and it acted on my auto-memory file instead of a mailbox message once.


## Outcome

- Signal: useful