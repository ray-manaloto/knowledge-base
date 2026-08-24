---
type: "query"
date: "2026-08-24T18:04:30.181182+00:00"
question: "Can graphify's graph be traversed to verify that documentation matches the code?"
contributor: "graphify"
outcome: "corrected"
correction: "The belief was that graphify's knowledge graph could be the fact registry for\ndocumentation currency — \"map it to graphify so it can be traversed to verify\".\n\nIt cannot, and the reason is structural rather than incidental: the prose layer\nand the AST layer are built by different extractors and share no node identity,\nso there is no edge for a traversal to follow. This repo had already recorded\n\"the prose and code layers never touch\"; what was new this round is the live\ncount (CROSS = 0 of 1,155,720 links) and the second, independent disqualifier —\nquery latency past 10 minutes on the aggregate, which rules it out as a gate\nregardless of topology.\n\nThe durable lesson is narrower than \"graphify can't do this\": a graph that\nINDEXES two things does not RELATE them. Before proposing a graph traversal as a\nverification mechanism, count the edges between the two node classes the\ntraversal would have to cross. If that count is zero, the traversal does not\nexist no matter how good the index is.\n"
---

# Q: Can graphify's graph be traversed to verify that documentation matches the code?

## Answer

The graph CANNOT verify a documentation claim against the code constant that
would falsify it. Measured live over the 492,654-node aggregate:

  links 1,155,720   ast-ast 1,149,288   prose-prose 6,432   CROSS = 0

Zero edges between the prose and code layers. The graph can FIND where a fact is
restated (it indexes prose); it cannot check the restatement, because a doc node
and a code node are never connected. A single `kb-query` against that graph also
exceeded 10 minutes, so it could not serve as a gate even if the edges existed.

The mechanism that DOES verify is already in this repo: `currency.toml`'s
`ref_binding` — declare a fact once with where it is derived from and every doc
that states it, offline, ~10ms, and its rule that a pattern matching NOTHING is
DRIFT rather than a pass is what stops it decaying into a check that can only
pass. Generalising that beyond version refs is the documentation-currency gate.


## Outcome

- Signal: corrected
- Correction: The belief was that graphify's knowledge graph could be the fact registry for
documentation currency — "map it to graphify so it can be traversed to verify".

It cannot, and the reason is structural rather than incidental: the prose layer
and the AST layer are built by different extractors and share no node identity,
so there is no edge for a traversal to follow. This repo had already recorded
"the prose and code layers never touch"; what was new this round is the live
count (CROSS = 0 of 1,155,720 links) and the second, independent disqualifier —
query latency past 10 minutes on the aggregate, which rules it out as a gate
regardless of topology.

The durable lesson is narrower than "graphify can't do this": a graph that
INDEXES two things does not RELATE them. Before proposing a graph traversal as a
verification mechanism, count the edges between the two node classes the
traversal would have to cross. If that count is zero, the traversal does not
exist no matter how good the index is.
