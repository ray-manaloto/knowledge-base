---
type: "query"
date: "2026-08-11T15:58:58.362389+00:00"
question: "How is the real GLM-5.2 Colibri Graphify canary being run and validated?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["colibri.c", "graphify"]
---

# Q: How is the real GLM-5.2 Colibri Graphify canary being run and validated?

## Answer

The GLM-5.2 canary is implemented as a parameterized `kb-colibri-canary` mise task backed by `kb_setup.colibri_canary`. It pins Colibri commit 2c8ce27d27537f54a1fbdafdbeee45b57bd2c71b and the recommended g64/int8-MTP model container revision fd9b461ac7cae4b921470d0db12230c6505bd03c. The run is CPU-only, MTP-off, single-slot, loopback-only, and performs a raw transport probe plus two Graphify deep extractions with schema, semantic, and SHA-256 determinism gates. The live model download is still in progress, so no GLM quality conclusion exists yet. A validation run exposed and fixed the Unix Makefile alias warning by using the `glm` target rather than the self-referential `colibri` target.


## Outcome

- Signal: useful

## Source Nodes

- colibri.c
- graphify