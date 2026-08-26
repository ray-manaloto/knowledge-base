---
type: "query"
date: "2026-08-26T16:30:16.471559+00:00"
question: "Can a file:line citation be trusted after the pin it was measured against moves?"
contributor: "graphify"
outcome: "corrected"
correction: "A derived fact does not move when its source moves, and this round it bit FOUR\ntimes -- twice caught by review, once by reading a live page, once by round two.\nA version pin is a source: moving it shifted llm.py by ~142 lines and cli.py by\n18, and every file:line citation written against the old pin silently began\npointing somewhere else. Nothing in this repo notices that (#516).\n\nTwo more specific corrections from the same round.\n\nThe handoff proposed keying the MCP fix on `codex mcp list --json`'s\n`disabled_reason` field, described as \"already returned and unused\". REFUTED by\nreading the real output: it is None for all ten servers INCLUDING every one that\nprovokes the failure, so it cannot discriminate. `transport.type` cannot either\n-- both stdio and streamable_http appear on passing and failing names. A fact\nrestated from a report without re-running the probe carries the report's error\nunder the restater's authority, which is the same lesson the previous round\nrecorded and the same one whose own citation had gone stale.\n\nAnd a count stated three times, wrong twice: the pin was described as living in\nthree files (the manifest's own framing), then seven after a survey, and is\neight -- the currency engine found the last one mid-move by refusing with \"the\ntwo halves of one fork pin have separated\". A surface map assembled by reading\nis not a surface map; the thing that knows is the tool that checks.\n"
---

# Q: Can a file:line citation be trusted after the pin it was measured against moves?

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

- Signal: corrected
- Correction: A derived fact does not move when its source moves, and this round it bit FOUR
times -- twice caught by review, once by reading a live page, once by round two.
A version pin is a source: moving it shifted llm.py by ~142 lines and cli.py by
18, and every file:line citation written against the old pin silently began
pointing somewhere else. Nothing in this repo notices that (#516).

Two more specific corrections from the same round.

The handoff proposed keying the MCP fix on `codex mcp list --json`'s
`disabled_reason` field, described as "already returned and unused". REFUTED by
reading the real output: it is None for all ten servers INCLUDING every one that
provokes the failure, so it cannot discriminate. `transport.type` cannot either
-- both stdio and streamable_http appear on passing and failing names. A fact
restated from a report without re-running the probe carries the report's error
under the restater's authority, which is the same lesson the previous round
recorded and the same one whose own citation had gone stale.

And a count stated three times, wrong twice: the pin was described as living in
three files (the manifest's own framing), then seven after a survey, and is
eight -- the currency engine found the last one mid-move by refusing with "the
two halves of one fork pin have separated". A surface map assembled by reading
is not a surface map; the thing that knows is the tool that checks.
