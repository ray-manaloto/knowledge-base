---
type: "query"
date: "2026-08-23T17:52:20.973604+00:00"
question: "2026-08-23: run the corpus deep extraction and work the tracked directive plan — what did the round establish?"
contributor: "graphify"
outcome: "useful"
---

# Q: 2026-08-23: run the corpus deep extraction and work the tracked directive plan — what did the round establish?

## Answer

The 2026-08-23 execution round: run the corpus deep extraction, then work the
tracked directive plan.

WHAT SHIPPED (10 commits on `claude-resync-2.1.241`)

- U0 `8f285ce0` — the reviewed-zero-node approver now mirrors graphify's own
  `is_package_manifest_path` dispatch, so a TOML package manifest holding only
  tool configuration can be reviewed and registered. 19 files across 8 sources.
  Verified end to end: `kb-build` previously died at the 3rd source and now
  reaches 52.
- U8b0 `e4d3d27a` — a transform-then-lint gate for `.claude/workflows/*.js`,
  after the lane DISSENTED and proved the pinned mechanism impossible.
- corpus `17623a32` — out-of-scope nodes are excluded on the way into assembly
  and RECORDED, rather than the whole chunk being refused.
- U4b `b9ce6e0a` — a receipt from a reviewer CLI that disagrees with its pin is
  refused.
- plus the pin bump, the lint unblock, the review fixes, and the corpus evidence
  now tracked.

THE CORPUS RUN, MEASURED

26 chunks planned. Pass 1: 20 completed, 6 failed, $20.86. Pass 2 (resume): 4
completed, **18 REPAID**, 4 failed, $20.91. Cumulative **45 charges / $41.78**
against a $63 cap for a 26-chunk corpus — 1.73x. All 26 are now staged and
tracked.

Final measured rate **$0.948/chunk**, against an inherited $1.32 that had been
flagged as possibly a floor. It is lower, and the early-stop measurement Ray
ruled for is what produced it, at the live config, for free. Zero
`record --accept` this round.

THE REVIEW

One cold lane, `antigravity:review --adversarial` — genuinely cross-family,
because three of the four feature commits were codex-authored and routing to
`codex-reviewer` would have recorded a cross-family claim that was not true.
Five findings: two changed code, one was refuted, one is by design, and one was
deliberately NOT fixed because it lives in a file the corpus plan digests.


## Outcome

- Signal: useful