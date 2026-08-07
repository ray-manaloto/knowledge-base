---
type: "query"
date: "2026-08-07T18:55:26.042218+00:00"
question: "How do I enumerate what the corpus already covers for a given doc page?"
contributor: "graphify"
outcome: "corrected"
---

# Q: How do I enumerate what the corpus already covers for a given doc page?

## Answer

Normalize the identity and STATE THE CONTROL. Matching on guessed source_file spellings missed a 54-node goal extraction under claude-code-goal-docs.md. Re-deriving by source_url ALSO failed because the regex excluded the .md suffix while the real URL is /docs/en/goal.md. Control arm: the normalized probe (strip .md, strip trailing slash) finds 19 pages; the bounded one finds 15, and the 4 it adds are exactly the hidden ones. Same spelling-bound failure twice in one session, the second time while fixing the first.

## Outcome

- Signal: corrected