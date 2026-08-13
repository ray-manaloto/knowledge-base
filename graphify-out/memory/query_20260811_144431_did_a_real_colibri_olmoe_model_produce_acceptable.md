---
type: "query"
date: "2026-08-11T14:44:31.193899+00:00"
question: "Did a real Colibri OLMoE model produce acceptable Graphify 0.9.39 deep extraction?"
contributor: "graphify"
outcome: "corrected"
correction: "Prior rejection was speculation because no model had run. Real testing now rejects only this OLMoE configuration for critical extraction, not Colibri as a runtime."
source_nodes: ["colibri.c", "olmoe.c", "graphify"]
---

# Q: Did a real Colibri OLMoE model produce acceptable Graphify 0.9.39 deep extraction?

## Answer

The pinned Colibri dev server and real OLMoE weights passed transport and Graphify completed in about 49 seconds, but the result failed quality: four missing source_file schema warnings, 5 of 8 required concepts, and 0 of 4 correct source-relation-target triples.

## Outcome

- Signal: corrected
- Correction: Prior rejection was speculation because no model had run. Real testing now rejects only this OLMoE configuration for critical extraction, not Colibri as a runtime.

## Source Nodes

- colibri.c
- olmoe.c
- graphify