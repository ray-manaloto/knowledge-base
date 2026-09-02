---
type: "query"
date: "2026-09-01T23:59:35.335461+00:00"
question: "What does resyncing 22 Claude/Anthropic/codex manifests after a Claude Code self-update actually require, and what does it reveal?"
contributor: "graphify"
outcome: "useful"
---

# Q: What does resyncing 22 Claude/Anthropic/codex manifests after a Claude Code self-update actually require, and what does it reveal?

## Answer

Round: resync 22 Claude/Anthropic/codex source manifests after Claude Code
self-updated, then review the release notes and hunt the new Fable 5.1 model.

RESULT: 22/22 rc 0 — 15 manifests moved, 7 silent no-ops (reported as distinct
columns, which was the advisor's named "biggest risk"). Fable 5.1 went from 0
files to 133 in sources/claude-code-docs/, control-armed both times against
"Opus 5" (191 -> 194). Fable 5.1 is `claude-fable-5-1`: 1M context, 128K output,
$10/$50 per MTok, and it is now the DEFAULT Fable model — but a Claude apps
gateway session still resolves bare `fable`/`best` to Fable 5.

The round's durable finding is NOT the resync. It is that a codex lane in this
repo has TWO independent sandbox walls, neither documented before today, and
each one produces a failure that reads as something else:

1. writes outside the workspace are refused, so uv cannot open its cache and
   every uv-backed `mise run` exits 2 — fixed by `--add-dir "$HOME/Library/Caches"`;
2. network egress is blocked, so `git ls-remote` returns rc 128
   `Could not resolve host: github.com` — fixed by
   `-c sandbox_workspace_write.network_access=true`.

The second cost four dispatches of one lane, because `Could not resolve host` is
the exact signature this repo's own persistence-gate-retry rule classifies as a
TRANSIENT worth one retry. It is permanent and structural here, so every remedy
that rule prescribes made it worse. The tell was available two dispatches
earlier and unused: the identical command from an ordinary shell returned rc 0.

Also established: `kb-update` resolves the manifest's OWN `ref`, not the newest
tag, so a version-pinned source short-circuits rc 0 "already at latest" — a
SILENT NO-OP that looks like success. Advancing one needs a hand-edited `ref`,
and the `commit` line must be LEFT at the old value or kb-update skips and emits
no changed-page worklist.


## Outcome

- Signal: useful