---
kind: lesson
source: feedback_codex_review_protocol
---

# l-codex-review-no-disk-reads

Prompt-only Codex reviews should explicitly forbid disk reads and require analysis only of supplied code.
In Debate 2, protocol loading and line-by-line file reads consumed the output without producing findings.
Use high reasoning effort for this [[lane-codex]] mode and treat file-dump-only output as provider failure.
Continue the decision through [[cross-family-review]] instead of counting that output as analysis.
