---
type: "query"
date: "2026-07-30T17:48:06.782375+00:00"
question: "How do you close a gap that a documented workflow depends on staying open?"
contributor: "graphify"
outcome: "useful"
---

# Q: How do you close a gap that a documented workflow depends on staying open?

## Answer

#56 asked for HEAD-capture at lane dispatch, which would have made the fix-round path impossible — committing the fix IS what moves HEAD, so the workflow the issue protects would be its first casualty. The gap closed instead by making the EVIDENCE self-describing: a lane report must NAME the commit it reviewed. Same threat removed, and the honest fix-round report passes because it already names both commits. Generalisation: when a fix would break a path the same system documents, look for a check on what the artifact SAYS rather than on when it was produced — a timing check forbids legitimate sequences, a content check only forbids silence. Also: 12 chars is the floor for a sha match, 7 (git default abbrev) is refused because a 7-hex run matches ordinary prose by accident, and a check that can pass by coincidence has checked nothing.

## Outcome

- Signal: useful