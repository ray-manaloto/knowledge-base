---
type: "query"
date: "2026-07-28T12:28:29.229210+00:00"
question: "When a review lane's findings are exempted from lane coverage, what else must cover those paths?"
contributor: "graphify"
outcome: "useful"
---

# Q: When a review lane's findings are exempted from lane coverage, what else must cover those paths?

## Answer

Scanner coverage becomes a PRECONDITION, not a follow-up. kb_setup.review.EXEMPT_PATHS lets a commit whose whole delta is graphify-out/memory/** ship on an ancestor's receipt, so no review lane reads those files. On 2026-07-28 one of them arrived carrying three live credentials and gitleaks went green over it — because .gitleaks.toml allowlisted ^graphify-out/ AND hk.pkl's global exclude carried graphify-out/**, which strips those files from {{files}} for every builtin. gitleaks only scanned them by accident: gitleaks dir IGNORES its path args once there is more than one (1 arg = 5.01KB scanned, 2 args = 8.62MB). Fixing one half leaves the coverage resting on that accident. Neither obvious glob works: !(memory) is not extglob in hk, and hk's * CROSSES / so graphify-out/*.* hid all 38 committed work-memory files. The split that works is a per-step exclude: formatters off the generated records, scanners on them.

## Outcome

- Signal: useful