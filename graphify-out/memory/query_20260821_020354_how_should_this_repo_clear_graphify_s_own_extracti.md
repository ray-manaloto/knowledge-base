---
type: "query"
date: "2026-08-21T02:03:54.145732+00:00"
question: "How should this repo clear graphify's own extraction blocker, and does the published self-graph settle it?"
contributor: "graphify"
outcome: "useful"
---

# Q: How should this repo clear graphify's own extraction blocker, and does the published self-graph settle it?

## Answer

Round of 2026-08-20 on `graphify-corpus-0947`.

ASKED: finish the green kb-build, then run the graphify semantic extraction.

WHAT WAS BUILT
A fourth stderr approver for graphify's #1689 "no AST extractor for this
language" warning, with its own `ExpectedUnsupportedLanguage` struct — kept
separate from `ExpectedPartialExtraction` because the two expire on different
events: a partial extraction changes when the FILE or grammar changes, a missing
extractor only when UPSTREAM ships one. Approval requires the reviewed inventory
to account for every counted file exactly (same languages, same per-language
totals, compared as dicts so an over-covering inventory also fails), each path to
still hash as reviewed, and each to still contribute ZERO nodes. That last check
is what expires the approval the day an extractor lands. 7/7 mutation arms died,
1/1 control held.

MEASURED ENTRIES
- code-review-graph tests/fixtures/sample.R + test_sample.R: 0 nodes each,
  7 symbols lost. Control arm: 53 other tests/fixtures files ARE in the sub-graph.
- code-review-graph tests/fixtures/sample.luau: 10 nodes, lost_symbols=2 — NOT 3.
  The control arm changed the number: the sibling sample.lua (same fixture, no
  type annotations) misses `local x = function` too, so graphify's Lua extractor
  never graphs that form and `transform` was never lost to the parse error.
- graphify tests/fixtures/sample.luau: 5 nodes (stub + 4 functions),
  lost_symbols=0, first error line 8 (the `type ServerConfig` alias).

THE SURVEY THAT REPLACED TWENTY BUILDS
`graph.build` fails fast on the first unapproved warning, so each ~15-minute
build cleared exactly one source. A survey calling the same `_extract_code` per
source and catching the refusal named EVERY blocker in one pass: 65 askable,
50 OK, 15 BLOCKED, all `scope = corpus`, in three cause groups.

OUTCOME: useful. The approver, three measured entries and the survey all landed;
the extraction did not run because C4 authority was never given.


## Outcome

- Signal: useful