---
type: "query"
date: "2026-08-29T18:09:39.709425+00:00"
question: "Is sources/agent-harness-docs retired/superseded by claude-code-docs, needing no resync?"
contributor: "graphify"
outcome: "corrected"
correction: "# Correction — agent-harness-docs was NOT retired/superseded\n\nEarlier this round I told Ray that `sources/agent-harness-docs` (the\ncodex/cursor/opencode/pi docs mirror) was \"retired 2026-08-24, superseded by\nclaude-code-docs, a strict superset\" and needed no resync. That was WRONG.\n\n## What was actually true\n\n`sources/agent-harness-docs.manifest` had been ACCIDENTALLY DELETED in an\nunrelated large merge (commit `f3bd4e4e`, \"corpus partial merge 20260823\n(#482)\") with no stated rationale — not a deliberate retirement. The gitignored\nclone at `sources/agent-harness-docs/` was still sitting on disk, untouched, at\nits old pinned commit. This repo's own OPEN issue #82 already tracked exactly\nthis gap (Codex/Cursor/OpenCode/Pi docs with no other source), which I did not\ncheck before making the \"retired\" claim.\n\n`claude-code-docs` (thevibeworks) is a strict superset only for the\n`docs/claude-code/` portion. It has ZERO content for Codex, Cursor, OpenCode,\nor Pi — the exact content the \"retired\" claim implied was safely covered\nelsewhere.\n\nFixed by restoring `sources/agent-harness-docs.manifest` (PR #604, landed) and\ncorrecting the overbroad \"REPLACES... strict superset\" claim inside\n`sources/claude-code-docs.manifest`'s own header comment to name only the\nclaude-code portion.\n\n## Second correction, same round\n\nEven after restoring it, I treated the fix as complete without comparing its\ncoverage against alternatives. Ray pointed out `chenrui333/codex-docs` covers\n6 content categories (dev-blog pages, cookbook/resources, the `openai/codex`\nrepo's own README/CHANGELOG/docs, platform tool guides, CLI-materialized\nsystem skills, a capability inventory) with a 6-hour auto-sync, while the\nrestored `agent-harness-docs` covers only 1 of those 6 (developers.openai.com\npages) as a static snapshot pinned to 2026-08-08. Confirmed correct by reading\nthe actual README. `agent-harness-docs` is a strict SUBSET of\n`chenrui333/codex-docs` for Codex specifically — the restoration was real but\nincomplete.\n\n## The lesson\n\nDeclaring a research question \"settled\" or \"moot\" without running the actual\ncomparison it depends on is a probe with no control arm — I made that claim\ntwice in one round (once calling agent-harness-docs \"retired\", once calling\nthe codex-docs research thread \"moot\") without checking either one against\nthe fact that later refuted it.\n"
---

# Q: Is sources/agent-harness-docs retired/superseded by claude-code-docs, needing no resync?

## Answer

# Correction — agent-harness-docs was NOT retired/superseded

Earlier this round I told Ray that `sources/agent-harness-docs` (the
codex/cursor/opencode/pi docs mirror) was "retired 2026-08-24, superseded by
claude-code-docs, a strict superset" and needed no resync. That was WRONG.

## What was actually true

`sources/agent-harness-docs.manifest` had been ACCIDENTALLY DELETED in an
unrelated large merge (commit `f3bd4e4e`, "corpus partial merge 20260823
(#482)") with no stated rationale — not a deliberate retirement. The gitignored
clone at `sources/agent-harness-docs/` was still sitting on disk, untouched, at
its old pinned commit. This repo's own OPEN issue #82 already tracked exactly
this gap (Codex/Cursor/OpenCode/Pi docs with no other source), which I did not
check before making the "retired" claim.

`claude-code-docs` (thevibeworks) is a strict superset only for the
`docs/claude-code/` portion. It has ZERO content for Codex, Cursor, OpenCode,
or Pi — the exact content the "retired" claim implied was safely covered
elsewhere.

Fixed by restoring `sources/agent-harness-docs.manifest` (PR #604, landed) and
correcting the overbroad "REPLACES... strict superset" claim inside
`sources/claude-code-docs.manifest`'s own header comment to name only the
claude-code portion.

## Second correction, same round

Even after restoring it, I treated the fix as complete without comparing its
coverage against alternatives. Ray pointed out `chenrui333/codex-docs` covers
6 content categories (dev-blog pages, cookbook/resources, the `openai/codex`
repo's own README/CHANGELOG/docs, platform tool guides, CLI-materialized
system skills, a capability inventory) with a 6-hour auto-sync, while the
restored `agent-harness-docs` covers only 1 of those 6 (developers.openai.com
pages) as a static snapshot pinned to 2026-08-08. Confirmed correct by reading
the actual README. `agent-harness-docs` is a strict SUBSET of
`chenrui333/codex-docs` for Codex specifically — the restoration was real but
incomplete.

## The lesson

Declaring a research question "settled" or "moot" without running the actual
comparison it depends on is a probe with no control arm — I made that claim
twice in one round (once calling agent-harness-docs "retired", once calling
the codex-docs research thread "moot") without checking either one against
the fact that later refuted it.


## Outcome

- Signal: corrected
- Correction: # Correction — agent-harness-docs was NOT retired/superseded

Earlier this round I told Ray that `sources/agent-harness-docs` (the
codex/cursor/opencode/pi docs mirror) was "retired 2026-08-24, superseded by
claude-code-docs, a strict superset" and needed no resync. That was WRONG.

## What was actually true

`sources/agent-harness-docs.manifest` had been ACCIDENTALLY DELETED in an
unrelated large merge (commit `f3bd4e4e`, "corpus partial merge 20260823
(#482)") with no stated rationale — not a deliberate retirement. The gitignored
clone at `sources/agent-harness-docs/` was still sitting on disk, untouched, at
its old pinned commit. This repo's own OPEN issue #82 already tracked exactly
this gap (Codex/Cursor/OpenCode/Pi docs with no other source), which I did not
check before making the "retired" claim.

`claude-code-docs` (thevibeworks) is a strict superset only for the
`docs/claude-code/` portion. It has ZERO content for Codex, Cursor, OpenCode,
or Pi — the exact content the "retired" claim implied was safely covered
elsewhere.

Fixed by restoring `sources/agent-harness-docs.manifest` (PR #604, landed) and
correcting the overbroad "REPLACES... strict superset" claim inside
`sources/claude-code-docs.manifest`'s own header comment to name only the
claude-code portion.

## Second correction, same round

Even after restoring it, I treated the fix as complete without comparing its
coverage against alternatives. Ray pointed out `chenrui333/codex-docs` covers
6 content categories (dev-blog pages, cookbook/resources, the `openai/codex`
repo's own README/CHANGELOG/docs, platform tool guides, CLI-materialized
system skills, a capability inventory) with a 6-hour auto-sync, while the
restored `agent-harness-docs` covers only 1 of those 6 (developers.openai.com
pages) as a static snapshot pinned to 2026-08-08. Confirmed correct by reading
the actual README. `agent-harness-docs` is a strict SUBSET of
`chenrui333/codex-docs` for Codex specifically — the restoration was real but
incomplete.

## The lesson

Declaring a research question "settled" or "moot" without running the actual
comparison it depends on is a probe with no control arm — I made that claim
twice in one round (once calling agent-harness-docs "retired", once calling
the codex-docs research thread "moot") without checking either one against
the fact that later refuted it.
