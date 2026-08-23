---
type: "query"
date: "2026-08-23T17:52:26.587307+00:00"
question: "Where should a fix land when the obvious site is a file the corpus plan digests, and is a severe review finding necessarily a live bug?"
contributor: "graphify"
outcome: "corrected"
correction: "Three beliefs this round overturned.\n\n1. \"The obvious fix site is the right fix site.\" The functions that reject a\nscope-mismatched chunk live in `graphify_semantic_slice.py`, which\n`execution-config.json` DIGESTS. Editing it would have un-authorized the plan,\nchanged the cache namespace and orphaned 26 staged chunks — re-buying a corpus\nthat had already cost $41.78. The way through was a module deliberately built\nOUTSIDE those digests, whose own docstring says why it exists as a separate\nfile. Check what a plan digests before choosing where to fix.\n\n2. \"A severe review finding is a live bug.\" Both severe findings — the lane's\nand my own inversion of its second — were real defects reading the function in\nisolation and UNREACHABLE end to end, because staging validates node identity\nfirst and emits a reason that is not survivable. That was established by\nCONSTRUCTING both reaching cases and watching them be rejected, not by reasoning\nfrom premises. The fix was kept as a latent-trap removal and labelled as such;\nthe first draft of its comment claimed a live bug and would have misled the next\nreader.\n\n3. \"A resume re-buys only what is missing.\" It re-buys EVERY chunk —\n`repaid: 18` — and that is documented in `graphify_semantic_corpus_authority.py`,\nwhich states outright that `extract_corpus_parallel` never consults the\nincremental cache. The fact was written down in one module's comment and appeared\nin neither the plan, the handoff, nor my own reasoning before $20.91 was spent\ndiscovering it. A cost model recorded in a comment nobody reads is not recorded.\n"
---

# Q: Where should a fix land when the obvious site is a file the corpus plan digests, and is a severe review finding necessarily a live bug?

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

- Signal: corrected
- Correction: Three beliefs this round overturned.

1. "The obvious fix site is the right fix site." The functions that reject a
scope-mismatched chunk live in `graphify_semantic_slice.py`, which
`execution-config.json` DIGESTS. Editing it would have un-authorized the plan,
changed the cache namespace and orphaned 26 staged chunks — re-buying a corpus
that had already cost $41.78. The way through was a module deliberately built
OUTSIDE those digests, whose own docstring says why it exists as a separate
file. Check what a plan digests before choosing where to fix.

2. "A severe review finding is a live bug." Both severe findings — the lane's
and my own inversion of its second — were real defects reading the function in
isolation and UNREACHABLE end to end, because staging validates node identity
first and emits a reason that is not survivable. That was established by
CONSTRUCTING both reaching cases and watching them be rejected, not by reasoning
from premises. The fix was kept as a latent-trap removal and labelled as such;
the first draft of its comment claimed a live bug and would have misled the next
reader.

3. "A resume re-buys only what is missing." It re-buys EVERY chunk —
`repaid: 18` — and that is documented in `graphify_semantic_corpus_authority.py`,
which states outright that `extract_corpus_parallel` never consults the
incremental cache. The fact was written down in one module's comment and appeared
in neither the plan, the handoff, nor my own reasoning before $20.91 was spent
discovering it. A cost model recorded in a comment nobody reads is not recorded.
