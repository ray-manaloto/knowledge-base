---
type: "query"
date: "2026-08-18T20:06:04.304919+00:00"
question: "What did the 2026-08-18 session-review seam round establish?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did the 2026-08-18 session-review seam round establish?

## Answer

The session-review seam was completed and shipped as PR #347 (21 commits).

WHAT WAS BUILT: `mise run kb-session-select` (--current | --sessions | --last N |
--since..--until) resolving to a codegen'd JSON contract; the workflow now takes
`sessions` instead of transcriptDir+since, and `mode` split into `output` +
`lanes` with both THROWING on an unknown value; a `reconcile` check in
`kb-handoff-check` that FAILS a handoff dropping the previous handoff's owed
commitments, wired into BOTH the CLI and kb-ship's path; a PreToolUse deny for
probes whose command word is not installed (`timeout` on macOS).

THE MEASUREMENT THAT JUSTIFIED IT: `mtime` is not when a session ran. 20 of 238
transcripts carry a birth-to-mtime gap over 24h, worst 119.6h; a session-review
run EXCLUDED session 6b974f05 — 675 of the round's 1,693 tool calls — because
its UTC records and local mtime straddle midnight. started_at is now birthtime
cross-checked against each transcript's own first record, and 3 of 238 come back
time_source=content.

#344 IS SATISFIED: the composer fix (bc02fc96) made handoff-mode carry the
previous backlog; run 4's generated handoff passed kb-handoff-check at 50 OK / 0
broken. The defect it fixed: `cfg.handoffs` reached the SWEEP lanes and stopped
there, and a lane returns FINDINGS — so an item merely STILL OWED was nobody's
finding and had no route to the composer. It dropped 7 of 9 items under
handoff-b's own "Owed, unchanged" heading.

THREE CONFIDENT WRONG CLAIMS IN ONE CHAIN, all mine, all about mechanisms:
(1) "only the model can spawn Claude agents" — false, the Agent SDK does;
(2) its correction, "an SDK fan-out must be separately billed" — false,
CLAUDE_CODE_OAUTH_TOKEN authenticates against the subscription;
(3) "the reconcile gate blocks kb-ship" — false, kb-ship gates through
check_for_branch and the gate was wired only into check_handoff.
Each was written at the moment of building the thing it described, with no probe
between the belief and the sentence.

THE COLD LANE PAID FOR ITSELF: 3 P1s on one commit, the worst being a refactor
that dropped a `.lower()` so every camelCase identifier was reported DROPPED
forever — while the test asserting that outcome kept PASSING, because the bug and
the assertion agreed. No mutation arm can see that class.

UNUSED SURFACE FOUND: graphify's MCP already ships ingest_turns / recall — 0 hits
across kb_setup vs 19 for save-result. This repo hand-built a memory pipeline on
the tool that already had one.


## Outcome

- Signal: useful