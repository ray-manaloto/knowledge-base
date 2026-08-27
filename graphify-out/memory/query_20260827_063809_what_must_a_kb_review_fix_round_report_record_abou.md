---
type: "query"
date: "2026-08-27T06:38:09.025901+00:00"
question: "What must a kb-review fix-round report record about work that was never cold-reviewed, and what happens when a premise-verifier lane never returns?"
contributor: "graphify"
outcome: "useful"
---

# Q: What must a kb-review fix-round report record about work that was never cold-reviewed, and what happens when a premise-verifier lane never returns?

## Answer

A `kb-review` fix-round report must NAME what was never cold-reviewed, not
just what was. Written into
`.agent/kb/review/reports/review-048b6a7215ecefa4ae330fab3113cc47f0df1a89-cold.md`
on 2026-08-27 rather than left implied.

Two gaps existed on that branch and both are the kind that read as covered:

1. TWO COMMITS NO LANE EVER READ. The cold lane (antigravity/Gemini,
   cross-family against codex authors) reviewed `d66b306f` and returned
   3 findings, 0 blocking. The fix for two confirmed findings landed as
   `d135ffbe`, and a `.gitleaksignore` landed as `048b6a72`. Neither was
   cold-reviewed — correct under the skill's two-round bound, where the
   local gates are the verification at that point, but the receipt alone
   cannot express it. Only the report can.

2. THE COLD PREMISE CHECK NEVER HAPPENED. `premise-verifier` was dispatched
   for the `.gitleaksignore` change (a secret-scanner narrowing, so a
   security-tier spec), went idle TWICE without returning, was nudged once
   explicitly, and returned nothing at all. It is a Read/Grep/Glob-only lane,
   so its return value is its ONLY output channel — there is no report file
   to recover, which makes its silence total in a way a writing lane's is
   not. Its eight premise rows were then settled by the architect reading the
   files directly.

The second gap is the dangerous one, and the reason it is written down twice
(in the fix-round report AND at the top of the attestation file the dispatch
pointed at) is that the doctrine's own words explain why: self-audit
structurally cannot find the premises the author did not recognise as
premises. An architect-settled premise block LOOKS identical to a
cold-verified one — same rows, same citations, same `PREMISES-VERIFIED:`
attestation satisfying the same mechanical gate. The gate is presence-based
by design and cannot tell them apart. So the only thing that preserves the
distinction is the record saying so in its own opening line.

THE HABIT: when a lane you dispatched does not report, do not let the work
proceed as though it did. Write the absence down where the next reader will
hit it before they act on the artifact — not in a transcript they will never
open. A gap that is merely unstated reads, to every later reader, as coverage.


## Outcome

- Signal: useful