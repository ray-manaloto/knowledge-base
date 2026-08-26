---
type: "query"
date: "2026-08-26T16:30:11.289132+00:00"
question: "How does the graphify fork get onto upstream v0.9.50 with the openai-cli backend working?"
contributor: "graphify"
outcome: "useful"
---

# Q: How does the graphify fork get onto upstream v0.9.50 with the openai-cli backend working?

## Answer

The fork was rebased onto upstream v0.9.50 (43d54acb = v8 HEAD, 17 commits past
our old base), all seven fork commits replayed with ONE conflict in CHANGELOG.md
only, and an eighth commit fixed the defect that made every openai-cli
extraction die in about three seconds.

That defect: `_codex_disable_mcp_args` emitted `-c mcp_servers.<name>.enabled=false`
for every server `codex mcp list --json` reported. A name that resolves to no
config table -- a plugin-provided server -- makes that override create a table
with neither command nor url, and codex rejects its ENTIRE bootstrap
configuration. Neither `disabled_reason` nor `transport.type` discriminates the
two cases; resolvability is a property of the WORKING DIRECTORY (the same
override for the same name exits 0 from a repo whose .codex/config.toml defines
it and 1 from /tmp). The fix asks codex itself, in the cwd the call will run in,
memoizes the answer per process, and validates the assembled survivor set before
emitting it.

The pin then moved across EIGHT surfaces in one commit: pyproject.toml (version
AND rev -- the version had to move because upstream's own bump made the fork
report 0.9.50), uv.lock, sources/graphify.manifest plus six stale prose blocks,
sources/graphify.dispositions.json, the deterministic baseline's accepted
constants and its three re-derived measurements, currency.toml's fork block, and
the generated skill stamp.

Verified by the runtime rather than the config: direct_url.json reports 0.9.50 at
0a2eb5fd from our fork, and the installed package carries 9 openai-cli hits
against a 24-hit claude-cli control.


## Outcome

- Signal: useful