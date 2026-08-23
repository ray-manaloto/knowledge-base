# Refutation attempt — CodeRabbit Merge Risk verdict on PR #422 never adjudicated

Claim under test (lane bot-reviews): "CodeRabbit's own pre-merge risk verdict
('Merge Risk: Moderate ... merge should wait for correction or explicit owner
acceptance') was never explicitly adjudicated before PR #422 merged, and 2 of its
3 named risks remain live in the committed docs today."

## Established so far (primary artifacts)

- PR #422: MERGED 2026-08-21T06:47:48Z, merge commit 8929d47f (gh pr view 422 --json).
- CodeRabbit walkthrough comment 5364700998: created 03:05:55Z, **updated 06:11:25Z**
  (gh api .../issues/comments/5364700998).
- Verdict text at line 30-32 of the body:
  `**Merge Risk:** _🟡 Moderate_ · up to \`ed7f8\`` and
  "...merge should wait for correction or explicit owner acceptance."
- Three named risks: (1) documentation contains conflicting and overstated
  findings; (2) a test may reject a valid converged state; (3) the required
  extraction ordering remains unresolved.
- PR thread has **zero human comments**: only coderabbitai[bot] and repowise-bot[bot]
  issue comments, and reviews only from graphify-labs[bot] + coderabbitai[bot].
  (gh api issues/422/comments --paginate; gh api pulls/422/reviews --paginate)
