---
type: "query"
date: "2026-08-07T21:07:54.470152+00:00"
question: "What happens to graphify-out/graph.json if kb-build is killed mid-merge?"
contributor: "graphify"
outcome: "useful"
---

# Q: What happens to graphify-out/graph.json if kb-build is killed mid-merge?

## Answer

It is left VALID JSON with the nodes present and ZERO edges - measured 2026-08-07: 340,887 nodes, 0 edges, 3 hyperedges, where a complete build of the same inputs gives 342,470 nodes and over 815,000 edges. It parses cleanly, so json.loads succeeds and any consumer that checks only parseability reads it as healthy. This is the silent-loss shape: a total loss of the relationship layer sitting behind a check that passes. kb-reflect reads this file, so running it against a killed build produces a garbage learning overlay with no error. TREATMENT: after any interrupted kb-build, rebuild before running kb-query, kb-reflect or kb-artifacts, and never judge graph health by whether the file parses - read the EDGE count. The cheap probe is one python line reporting len(nodes), len(edges), len(hyperedges) together; edges near zero next to a large node count is the signature.

## Outcome

- Signal: useful