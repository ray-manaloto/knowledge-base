---
type: "query"
date: "2026-08-07T18:55:15.485093+00:00"
question: "How should a stale doc page be re-extracted so the old nodes are actually replaced?"
contributor: "graphify"
outcome: "useful"
---

# Q: How should a stale doc page be re-extracted so the old nodes are actually replaced?

## Answer

Emit the chunk under the SAME source_file the stale chunk claims (here code.claude.com_docs_en_X.md) and declare it in supersedes. graphify replaces on source_file identity ALONE - it never reads the supersedes key (4 prose-only hits across the pinned 0.9.35 tree vs a control of 1008 for source_file; new_sem_sources comes from chunk nodes only, build.py 1616-1628). A re-extraction under a DIFFERENT spelling replaces nothing and leaves both copies live. Verified on 10 pages: 308 old nodes replaced, 480 new, exact arithmetic on all four merges.

## Outcome

- Signal: useful