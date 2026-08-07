---
type: "query"
date: "2026-08-07T21:07:54.470152+00:00"
question: "What happens to graphify-out/graph.json if kb-build is killed mid-merge?"
contributor: "graphify"
outcome: "useful"
---

# Q: What happens to graphify-out/graph.json if kb-build is killed mid-merge?

## Answer

CORRECTED 2026-08-07 by re-measuring the same bytes. It is left VALID JSON that is INCOMPLETE but whose relationship layer is INTACT - measured 340,887 nodes, 835,940 links, 3 hyperedges, against a complete build of the same inputs (rebuilt immediately afterwards on the same commit) at 342,541 nodes, 838,196 links and 122 hyperedges. So a killed build is short 1,654 nodes and 119 hyperedges, having been stopped partway through the doc-chunk merge, and it writes NO graphify-out/.currency-stamp.json because kb-build writes that last. The absent stamp is the honest completeness signal. THE ORIGINAL ANSWER HERE SAID ZERO EDGES AND WAS A PROBE DEFECT: graph.json is networkx node-link JSON whose relationship array is named links, and there is no edges key on ANY graphify graph - the control arm is graph-prose.json, a healthy separately-written graph, which reports nodes 4443, links 5898, has_edges_key False. The probe carried the CHUNK spelling (chunks under sources/extractions do use edges) across to the graph, so it reported zero on a healthy graph too and never discriminated. This repo's own graph_checks.py already reads data.get("links") or data.get("edges"). TREATMENT: probe with links, print the key set beside the counts so a spelling mismatch is visible, and after any interrupted kb-build still rebuild before kb-query, kb-reflect or kb-artifacts - the graph is genuinely incomplete even though nothing was lost.

## Outcome

- Signal: useful
