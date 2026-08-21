---
type: "query"
date: "2026-08-21T20:02:34.628970+00:00"
question: "Is a pin bump just a text edit (hand-edit mise.toml/pyproject.toml when the bytes match), and is kb-tool-sync a working task?"
contributor: "graphify"
outcome: "corrected"
correction: "Both were wrong. (1) Ray, verbatim: \"dont hand edit mise.toml and pyproject.toml - use their native commands\" — the bytes were identical (`mise use` / `uv add` reproduced the hand edits exactly) but the PROVENANCE is not: the owning tool validates the version exists, re-resolves, and moves mise.lock / uv.lock in the same step; a hand edit leaves the lockfile behind unless the author remembers. Enforcement is #437 (CLAUDE/AGENTS line, path-scoped rule, PreToolUse DENY, hk lockfile-consistency, session-review lane). Measured caveat: `mise config set` on an EXISTING key deletes the comment above it, so task bodies under comment blocks still need a hand edit, flagged. (2) kb-tool-sync had never passed on this host: its lifecycle refused ANY stderr while `mise lock` prints per-platform progress there and the repo's own `[hooks].postinstall` prints four hk lines there; the tests stubbed `_run` with stderr=\"\" so nothing could see it (#438). A refusal rule that names \"any stderr\" encodes a promise the tool never made; capture the tool's real output as the fixture and make the live task the end-to-end arm.\n"
---

# Q: Is a pin bump just a text edit (hand-edit mise.toml/pyproject.toml when the bytes match), and is kb-tool-sync a working task?

## Answer

Belief held going in: a pin bump is a text edit — editing mise.toml / pyproject.toml by hand is fine when the resulting bytes equal what the tool would write; and kb-tool-sync was a working task this repo could rely on for mise-only pins.


## Outcome

- Signal: corrected
- Correction: Both were wrong. (1) Ray, verbatim: "dont hand edit mise.toml and pyproject.toml - use their native commands" — the bytes were identical (`mise use` / `uv add` reproduced the hand edits exactly) but the PROVENANCE is not: the owning tool validates the version exists, re-resolves, and moves mise.lock / uv.lock in the same step; a hand edit leaves the lockfile behind unless the author remembers. Enforcement is #437 (CLAUDE/AGENTS line, path-scoped rule, PreToolUse DENY, hk lockfile-consistency, session-review lane). Measured caveat: `mise config set` on an EXISTING key deletes the comment above it, so task bodies under comment blocks still need a hand edit, flagged. (2) kb-tool-sync had never passed on this host: its lifecycle refused ANY stderr while `mise lock` prints per-platform progress there and the repo's own `[hooks].postinstall` prints four hk lines there; the tests stubbed `_run` with stderr="" so nothing could see it (#438). A refusal rule that names "any stderr" encodes a promise the tool never made; capture the tool's real output as the fixture and make the live task the end-to-end arm.
