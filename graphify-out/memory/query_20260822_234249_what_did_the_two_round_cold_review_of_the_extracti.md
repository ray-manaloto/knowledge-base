---
type: "query"
date: "2026-08-22T23:42:49.130826+00:00"
question: "What did the two-round cold review of the extraction-readiness lane brief (PR #459) find, and where were round 2's findings?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did the two-round cold review of the extraction-readiness lane brief (PR #459) find, and where were round 2's findings?

## Answer

The kb-review of the `extraction-readiness` lane brief (branch `extraction-readiness-sweep`,
PR #459, cold:codex, 2 rounds) returned FIVE findings and zero blocking — every one of
them PROSE inside the lane's brief, i.e. text the lane would have acted on:

Round 1 (on b23bc7e5b9e1):
1. A line-range citation had already drifted off its target: the brief sent the lane to
   `graphify_semantic_slice.py:1356-1410` for "the receipt-verification path"; at that
   SHA `_receipt_reasons` sat at :1461-1528 and `_runtime_reasons` at :1368-1436, so a
   lane reading only the cited range could close the coverage debt without opening the
   verifier. Fix: name the FUNCTIONS, record the drift.
2. "Nobody has ever OBSERVED this run reach a provider" was a premise the lane was told
   to RESTATE, four lines under the brief's own RE-DERIVE rule, in a lane that stays in
   HANDOFF_LANES while a run is pending. Fix: an instruction to CHECK for a run artifact
   under the pinned version and control-arm the absence.
3. `gh issue list --state open --limit 300` under "Sweep EVERY open issue" — a silent
   bound the same file names as suspect-by-construction (225 open that day). Fix:
   count-then-fetch at 1000, report both numbers, either equalling the limit = truncated.

Round 2 (on 7b94cdd933748a) confirmed all three resolved and found two more — BOTH inside
round 1's fix lines:
4. The by-name replacement was a bare `grep -n` over the WORKING TREE while the brief's
   own standard is "the code at the CURRENT sha" and a dirty tracked file is protected
   evidence here. Fix: `git grep -n 'def _receipt_reasons' HEAD -- <file>`.
5. "`graphify_semantic_corpus_authority.py` and `_prototype.py`" read as an elision to a
   file that does not exist; the real module is `graphify_semantic_corpus_prototype.py`.
   Fix: spell it in full.

Both fixed in 587c57361e63; no third lane round (kb-review §4); verification = the header's
syntax wrapping armed both ways + kb-gates 6/6 at that SHA + an honest fix-round report
naming all three SHAs.

Why it matters beyond this PR: a lane BRIEF is a prompt, and a prompt's defects are the
same classes as code's — stale anchors, inherited premises, silent bounds — but no linter
reads them. The cold lane is currently the only thing that does. And round 2's two
findings sat in round 1's own fix, which is the fourth time here that the fix was the
least-reviewed text in the diff.


## Outcome

- Signal: useful