---
type: "query"
date: "2026-08-28T02:08:42.866319+00:00"
question: "Why did a mermaid diagram on a published artifact page fail to render when its label used HTML entities, and what is the fix?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why did a mermaid diagram on a published artifact page fail to render when its label used HTML entities, and what is the fix?

## Answer

An HTML entity inside a `<pre class="mermaid">` node label (`&lt;name&gt;`) is decoded by the BROWSER before mermaid parses, so mermaid sees a literal `<name>` and its flowchart lexer fails with TAGSTART. The page rendered an error bomb for a day while a checklist item in the same commit claimed every block validated. Fix: mermaid's own entity codes (`#lt;name#gt;`), and validate the block through the Mermaid Chart MCP with a 2-line repro (invalid) and the fix (valid) as the two arms. Found by the cold cross-family lane on 8656620cfd77; fixed in 24b760db366d with a CORRECTION note on the page.


## Outcome

- Signal: useful