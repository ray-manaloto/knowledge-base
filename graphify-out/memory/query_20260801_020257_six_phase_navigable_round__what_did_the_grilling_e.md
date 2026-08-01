---
type: "query"
date: "2026-08-01T02:02:57.114460+00:00"
question: "Six-phase Navigable round: what did the grilling establish about graphify navigation before any work started?"
contributor: "graphify"
outcome: "useful"
---

# Q: Six-phase Navigable round: what did the grilling establish about graphify navigation before any work started?

## Answer

Three opening findings died under cross-check and the survivors reframed the brief. DEAD: (1) 'affected is broken by our directed=False' -- affected.load_graph forces directed:True itself (#1174); end-to-end arm returned 165 correct nodes on a seed with 156 counted callers. (2) 'multigraph:false collapses edges' -- diagnose says 307,101 in, 307,101 out, 0 collapsed. (3) 'graphify has no LSP anything' -- scip_ingest.py ships a simplified SCIP subset; the first probe grepped lsp|pylsp|pyright and missed it on SPELLING. SURVIVES: python/src/kb_setup is 0 of 37 files in the graph (control-armed: graphify/extractors 429, cognee/api 793, bogus 0); repo attribution collapses 127,929/130,844 nodes to repo=knowledge-base; scip_ingest is unwired by its own docstring (scip in cli.py 0 vs affected 6). Ingest cost measured, not guessed: graphify's own source 4.7MB .py -> ~6MB graph = 1.3x, so all three tools ~55MB against 167MB headroom under a 512MiB cap.

## Outcome

- Signal: useful