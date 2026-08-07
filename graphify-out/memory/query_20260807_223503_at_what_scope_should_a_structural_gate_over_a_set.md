---
type: "query"
date: "2026-08-07T22:35:03.324705+00:00"
question: "At what scope should a structural gate over a SET of extraction chunks check for contradictions?"
contributor: "graphify"
outcome: "useful"
---

# Q: At what scope should a structural gate over a SET of extraction chunks check for contradictions?

## Answer

Check it at the scope the MERGER merges at, not per file. kb_setup.edge_direction ran its cycle and symmetric-relation checks once per chunk, so a requires b in one chunk and b requires a in another validated clean with rc=0 - neither file alone contains a cycle, and that is exactly the contradiction class the gate exists to catch mechanically. The union is the correct scope because graphify's node identity is the id: two chunks emitting one id emit ONE node in graph.json, so a cross-chunk cycle is a real cycle in the merged graph rather than an artefact of putting the files side by side. chunks.validate_files already resolved endpoints against the union for the same stated reason (matching what graphify does at merge time), so the per-file check was the odd one out, holding a different notion of scope from its own sibling. Unioning cannot invent a contradiction either: the only route to a false cycle is two chunks reusing one id for different concepts, which is the separate id-collision defect. REACHABILITY MATTERS AND IS A SEPARATE QUESTION FROM MECHANISM: the review lane proved the gap with a synthetic two-file fixture, which establishes only that the code CAN miss it. Measuring the real corpus is what graded it - 4788 distinct node ids, 10 of them declared in two different committed chunks (a re-extraction pair), 14 shared edge endpoints, but 0 of those on a checked relation. So the gap was LATENT, not live: the enabling shape is already present and only the relation coincidence was missing, and re-extracting a page under a new chunk name is the routine operation that supplies it. The first version of that probe filtered to the checked relations and returned 0 shared endpoints, which would have read as purely theoretical; dropping the filter was the control arm that found the 10.

## Outcome

- Signal: useful