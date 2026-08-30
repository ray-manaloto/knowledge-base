---
type: "query"
date: "2026-08-30T17:29:29.822751+00:00"
question: "#580 codesearch verb — what shipped and what the round learned"
contributor: "graphify"
outcome: "useful"
---

# Q: #580 codesearch verb — what shipped and what the round learned

## Answer

#580 (codesearch verb) shipped as PR #631 (988afa02 -> 327cd9dc -> 2d105bc4,
merged 25cd404c). Codex-implementer built the adapter across a spec + one
fix round; two premise-verifier passes (pre-dispatch, then a fix-round pass)
caught 3 blocking premise errors before implementation and, critically, ran
7 LIVE queries against the real grep.app endpoint discovering it never
returns more than one hit per query — a fact the original ticket's
prototype spike never verified, which let the P0 fix land smaller and
strictly safer (anchor-at-position-0 parse) than the first proposed fix
(structural-template + consistency-check).

Two cold review rounds (Opus fallback both times — antigravity:review hit
a headless permission wall trying to invoke a command tool without
--yolo). Round 1 found 7 real, execution-confirmed defects including a
provenance-spoofing P0 whose own "safety net" comment was flatly false.
Round 2 found the P0 fix held up under adversarial testing, plus 2 more
blocking issues and 4 minor ones. One of round 2's SUGGESTED fixes (reject
a hit whose snippet contains a second URL: line) was tried by the
architect and reverted after it was found to break an already-accepted,
already-tested design decision (E1's documented residual) — a reviewer's
suggested mitigation is a claim to refute, not an instruction to implement
blindly, even in a fix round.

Lesson for future rounds: a suggested mitigation from a cold review still
needs the same refutation-pass discipline as a finding itself. This one
would have shipped a heuristic that fires identically on the exact
scenario the P0 redesign was built to accept safely, discovered only by
actually running the existing test suite against the new code before
committing.


## Outcome

- Signal: useful