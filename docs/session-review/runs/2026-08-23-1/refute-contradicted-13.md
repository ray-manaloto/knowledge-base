# Refutation attempt — finding [contradicted] #13 (comment vs `_ACCEPTED_CLAUDE_VERSION`)

CLAIM: `graphify_semantic_slice.py:468-471` asserts `_ACCEPTED_CLAUDE_VERSION`
"now equals `_CURRENT_CLAUDE_VERSION` below", but the constants disagree
(2.1.238 vs 2.1.240) at scope HEAD `272d14bc3785`.

VERDICT: **NOT REFUTED — confirmed, and UNDERSTATED.**

## Probes

1. `grep -n '_ACCEPTED_CLAUDE_VERSION\|_CURRENT_CLAUDE_VERSION\|now equals' python/src/kb_setup/graphify_semantic_slice.py`
   ```
   471:# part of the graphify 0.9.48 re-attest. It now equals `_CURRENT_CLAUDE_VERSION`
   475:_ACCEPTED_CLAUDE_VERSION = "2.1.238"
   561:_CURRENT_CLAUDE_VERSION = "2.1.240"
   ```
   Anchors are exact. Claim is literally true.

2. Right artifact? `git diff 272d14bc3785 HEAD -- python/src/kb_setup/graphify_semantic_slice.py`
   → **empty**. File is byte-identical at the cited SHA and at current HEAD
   (`cbf7229b`). Not a stale-scope artefact.

3. STRONGEST result — the sentence was false ON ARRIVAL.
   `git diff 272d14bc3785^ 272d14bc3785 -- python/src/kb_setup/graphify_semantic_slice.py`
   ```
   -_ACCEPTED_CLAUDE_VERSION = "2.1.233"
   +# part of the graphify 0.9.48 re-attest. It now equals `_CURRENT_CLAUDE_VERSION`
   +_ACCEPTED_CLAUDE_VERSION = "2.1.238"
   ```
   The diff contains **no** `+/-_CURRENT_CLAUDE_VERSION` line — so `_CURRENT`
   was already `2.1.240` in the parent tree. Confirmed by ancestry/timestamps:
   `cc2651012` ("repowise mcp 0821 (#453)", 2026-08-22 16:07:13 -0500) set
   `_CURRENT_CLAUDE_VERSION = "2.1.240"` and IS an ancestor of `272d14bc3785`
   ("corpus gate bundle rebased (#463)", 2026-08-22 22:23:28 -0500), which ADDED
   the "now equals" sentence 6h16m later. Not drift; false when written.

4. SECOND SITE the finding misses — same stale claim in a test docstring:
   `tests/test_graphify_semantic_slice.py:1106-1107`
   "Re-derived after the graphify 0.9.48 re-attest: the slice was re-run at
   2.1.238 in this same change, so ACCEPTED and CURRENT now hold the SAME value".
   Present tense, no date qualifier, and false at this SHA. The test's own
   assertion is unaffected (it monkeypatches `_CURRENT` to `9.9.9-not-accepted`
   at :1117), so no test can fail on either stale sentence — nothing gates this.

## Control arm (the probe CAN return "matches")

Same probe shape — read a comment's asserted identity, compare to the constants
it names — on the sibling pair in the SAME file:
`_ACCEPTED_GRAPHIFY_RUNTIME` (:340) comment says "ADVANCED 0.9.45 -> 0.9.48",
`version="0.9.48"`; `_CURRENT_GRAPHIFY_RUNTIME` (:446) `version="0.9.48"`.
→ **agrees**. Tighter second control 4 lines from the finding: the comment at
:558 "THE `--help` DIGEST DID NOT MOVE — still 71ad650f…" vs
`_ACCEPTED_CLAUDE_HELP_SHA256 = "71ad650f59e08ae4…"` (:479) and
`_CURRENT_CLAUDE_HELP_SHA256 = _ACCEPTED_CLAUDE_HELP_SHA256` (:565)
→ **agrees**. So the probe discriminates; it is not a one-faced coin.

## The one honest narrowing

The divergence is NOT a behavioural defect. Line 1535 uses `_ACCEPTED_*` for the
committed receipt; line 678 uses `_CURRENT_*` for the plan. The design REQUIRES
them to be able to differ ("Two constants, because there are two questions",
:467). The defect is purely that the prose asserts a transient coincidence in
the present tense — and the comment itself even disclaims it ("evidence
converging with intent, not the two questions collapsing", :472), which is what
makes the remedy a one-word edit rather than a constant change.

## Contradiction with other live findings

None. Finding 30 (preflight identity window: plan pinned 2.1.240, host at
2.1.241) is CONSISTENT: it is the same `_CURRENT_*`-vs-world axis one step
further along, and independently corroborates that `_CURRENT` = 2.1.240 while
`_ACCEPTED` stays at 2.1.238.

## GitHub repos touched

_None._
