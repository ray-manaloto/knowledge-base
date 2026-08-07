---
type: "query"
date: "2026-08-07T23:40:35.905593+00:00"
question: "What does kb-manifest-add actually pin when the ref is an annotated git tag?"
contributor: "graphify"
outcome: "useful"
---

# Q: What does kb-manifest-add actually pin when the ref is an annotated git tag?

## Answer

It records the TAG OBJECT, not the commit, whenever the tag is ANNOTATED - and nothing in this repo had exercised that until colibri v1.5.0 on 2026-08-07. kb-manifest-add stores whatever git ls-remote url ref returns. A lightweight tag resolves straight to the commit; an annotated tag resolves to the tag object, and the commit is only on the ^{} dereference line. Measured: colibri v1.5.0 gives 5e4b5c6a for refs/tags/v1.5.0 and 8f512fc8 for refs/tags/v1.5.0^{}, while the CONTROL - claude-code v2.1.222, the only other tag-pinned source here - returns no ^{} line at all because it is lightweight, so its recorded SHA really is the commit. That control is what made the asymmetry legible rather than looking like a one-off oddity. IMPACT IS NOT WHAT IT LOOKS LIKE: cloning is completely unaffected. git fetch --depth 1 origin <tag-object-sha> returns rc=0, git checkout of that sha returns rc=0 because git peels it, HEAD then reads 8f512fc8, and kb-build reproduces normally. So the pin is correct as written and should be LEFT ALONE rather than hand-normalised, because hand-editing it would make the file disagree with what manifest-add would regenerate. What is untested is the COMPARISON path: manifest.latest_commit runs a plain ls-remote with no peeling and is what kb-update uses to decide whether upstream moved, so a tag-object sha compared against a peeled one reports drift that is not drift, or misses drift that is. Filed as issue 235. THE SHAPE IS THE REAL LESSON: manifest.py already knows how to peel - resolve_release filters the ^{} line explicitly and its docstring says so - while its sibling latest_commit does not. Two functions in one module, one rule, only one of them following it. That is the same defect class as the edge-direction union bug fixed in PR 234 the same day: when two functions in a package hold different notions of the same thing, one of them is a bug nobody has found yet.

## Outcome

- Signal: useful