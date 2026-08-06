---
type: "query"
date: "2026-08-06T20:06:55.743722+00:00"
question: "Does this repo's ingestion path lose content silently, and can its own checks see it?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does this repo's ingestion path lose content silently, and can its own checks see it?

## Answer

Yes, twice, and each was invisible to the check meant to catch it.

(1) kb-add truncates at markdown[:12000] with no boilerplate removal, exiting 0.
PROVEN casualty: mindstudio-advisor-executor.md, extracted 2026-07-22 -- its 18
nodes reach only 54% of the 17,161-char article, 0 of 17 concepts past the 60%
mark, against 16 real headings there (the four named advisor/executor
anti-patterns, 6 FAQ entries, Key Takeaways). Control row, same batch and path:
linas-fable5-fallback.md is 3,140 chars, under the cap, reaches 94%, CLEAN -- so
the probe discriminates and the 12k cap explains the split. Repaired by
re-extracting under the SAME source_file with a chunk-level supersedes; the merge
replaced exactly 18 nodes and said so.

(2) kb-fetch, the lossless path, drops iframe-embedded code. The datasciencedojo
article renders all five code blocks as lazy-loaded carbon.now.sh iframes with
the payload DOUBLE-URL-encoded in data-lazy-src's code= param. trafilatura
extracts article text and does not decode iframe query strings, so "Paste this
into it:" was followed by nothing -- while the roundtrip check reported "11
tokens sampled, 0 missing". It samples what was KEPT, so it is structurally blind
to what was never extracted. Recovered with two rounds of unquote: 974 chars
containing the per-role model bindings (deep-reasoner=opus, fast-worker=sonnet),
the CLAUDE.md orchestration block, and the run-twice-with-different-framings
technique -- the article's entire point.

The first diagnosis of (2) was WRONG ("trafilatura dropped every code block").
Three control arms found the real cause: another article fetched the same way the
same day kept 4 code fences; the live HTML has 2 <pre> and 0 <code>; no
wp-block-code/hljs markup either.

## Outcome

- Signal: useful