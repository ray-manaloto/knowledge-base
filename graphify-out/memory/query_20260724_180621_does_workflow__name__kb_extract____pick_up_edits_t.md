---
type: "query"
date: "2026-07-24T18:06:21.484886+00:00"
question: "Does Workflow({name:'kb-extract'}) pick up edits to knowledge-base/.claude/workflows/kb-extract.js?"
contributor: "graphify"
outcome: "corrected"
correction: "Assumed the kb-curator skill's documented 'invoke the saved workflow by name' picks up repo edits."
source_nodes: ["blog-verification-loops-skills_verification_loop"]
---

# Q: Does Workflow({name:'kb-extract'}) pick up edits to knowledge-base/.claude/workflows/kb-extract.js?

## Answer

NO. Edited the repo file to add a diagnostic to its arg guard, re-invoked by name, and got the OLD error text verbatim -- proving the name resolves to a different cached copy. Invoke with scriptPath pointing at the repo file instead; that worked first try. Also: args can arrive JSON-STRINGIFIED, so the guard fires and its message misleadingly blames the caller's shape. The repo script now parses a string arg and reports typeof/scratchDir/sources in the error.

## Outcome

- Signal: corrected
- Correction: Assumed the kb-curator skill's documented 'invoke the saved workflow by name' picks up repo edits.

## Source Nodes

- blog-verification-loops-skills_verification_loop