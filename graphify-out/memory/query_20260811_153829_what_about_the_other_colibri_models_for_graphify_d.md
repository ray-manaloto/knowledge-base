---
type: "query"
date: "2026-08-11T15:38:29.551594+00:00"
question: "What about the other Colibri models for Graphify deep extraction?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["colibri.c", "graphify"]
---

# Q: What about the other Colibri models for Graphify deep extraction?

## Answer

Colibri currently exposes five sibling engines. OLMoE is the only one measured locally. GLM-5.2 is the only practical next same-Mac Graphify canary: about 372 GB, 744B total and about 40B active, reference Colibri runtime, macOS support, and richer API/KV/tool/grammar paths. It is not yet measured on this M2 Max. Inkling is technically feasible but about 469 GB and documented as very slow; DeepSeek V4 Flash is about 167 GB but Colibri excludes macOS; Kimi K3 is about 1.6 TB and exceeds local free storage. A real GLM canary requires explicit approval for the large download and must reuse the OLMoE transport/schema/semantic/determinism controls.


## Outcome

- Signal: useful

## Source Nodes

- colibri.c
- graphify