---
type: "query"
date: "2026-08-06T02:41:11.212679+00:00"
question: "Did graphify 0.9.34 fix the hyperedge losses this repo filed (#2484/#2485), and what happened to kb_setup.hyperedges' carry?"
contributor: "graphify"
outcome: "useful"
---

# Q: Did graphify 0.9.34 fix the hyperedge losses this repo filed (#2484/#2485), and what happened to kb_setup.hyperedges' carry?

## Answer

Verified on the INSTALLED 0.9.34 binary (arms A-E re-run, never the release notes): merge-graphs relabels hyperedge members (3/3 resolve, was 0/3), unions both inputs' sets (2-in-2-out, was 1-clobber), writes both slots; build_from_json reads both slots and a full revalidation wipeout now warns loudly. kb_setup.hyperedges' capture/reattach carry was therefore RETIRED (tool-currency-and-native-first rule 3) - and not just as redundancy: on 0.9.34 the carry was the only writer able to push dangling members PAST upstream's now-loud revalidation, so it had flipped from protective to hazardous. Live-fire proof: kb-merge then kb-label with no carry ended at 11 hyperedges / both slots / 0 dangling on the real aggregate - label was the step that measured 5-to-0 at 0.9.33. Residual risk closed by a writer version gate (cli._GRAPH_WRITERS preflight + graph.update's code branch): graphify_exe's PATH fallback is LIVE-stale on this host (bare graphify = 0.9.32 under the 0.9.34 pin), and a stale writer now refuses, naming both versions, instead of silently destroying data. Upstream #2484/#2485 are [[tool.graphify.watch]] issue refs so their close surfaces as movement.

## Outcome

- Signal: useful