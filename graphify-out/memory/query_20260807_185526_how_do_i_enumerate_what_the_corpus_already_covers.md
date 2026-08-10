---
type: "query"
date: "2026-08-07T18:55:26.042218+00:00"
question: "How do I enumerate what the corpus already covers for a given doc page?"
contributor: "graphify"
outcome: "corrected"
correction: "Matching guessed source_file spellings does not enumerate corpus coverage — NORMALIZE THE IDENTITY AND STATE THE CONTROL. The guessed-spelling probe missed a 54-node goal extraction under claude-code-goal-docs.md, and re-deriving by source_url ALSO failed because the regex excluded the .md suffix while the real URL is /docs/en/goal.md. Control arm: the normalized probe (strip .md, strip trailing slash) finds 19 pages, the bounded one finds 15, and the 4 it adds are exactly the hidden ones. The same spelling-bound failure happened TWICE in one session, the second time while fixing the first."
---

# Q: How do I enumerate what the corpus already covers for a given doc page?

## Answer

Normalize the identity and STATE THE CONTROL. Matching on guessed source_file spellings missed a 54-node goal extraction under claude-code-goal-docs.md. Re-deriving by source_url ALSO failed because the regex excluded the .md suffix while the real URL is /docs/en/goal.md. Control arm: the normalized probe (strip .md, strip trailing slash) finds 19 pages; the bounded one finds 15, and the 4 it adds are exactly the hidden ones. Same spelling-bound failure twice in one session, the second time while fixing the first.

## Outcome

- Signal: corrected
- Correction: Matching guessed source_file spellings does not enumerate corpus coverage — NORMALIZE THE IDENTITY AND STATE THE CONTROL. Re-deriving by source_url also failed because the regex excluded the .md suffix while the real URL is /docs/en/goal.md. Control: the normalized probe finds 19 pages, the bounded one 15, and the 4 it adds are exactly the hidden ones. The same spelling-bound failure happened twice in one session, the second time while fixing the first.