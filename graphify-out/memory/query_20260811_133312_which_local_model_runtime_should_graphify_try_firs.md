---
type: "query"
date: "2026-08-11T13:33:12.019364+00:00"
question: "Which local model/runtime should Graphify try first for bounded deep extraction on this M2 Max?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["graphify", "Nativ", "TurboFieldfare", "colibri.c"]
---

# Q: Which local model/runtime should Graphify try first for bounded deep extraction on this M2 Max?

## Answer

Use a text-only Muse Glimmer 30B canary through pinned llama.cpp b10360. Colibri OLMoE has only 4096 context; larger Colibri models are impractical. Nativ v0.3.0 has an open launch crash on macOS 26.6.1 and ignores Graphify max_completion_tokens unless server defaults are raised. Turbo Fieldfare is wire-compatible but has an open long structured-generation corruption defect. Before the Muse canary, fix the Knowledge Base localhost OpenAI lane so it restores a non-empty local-only API key after cleaning provider credentials.

## Outcome

- Signal: useful

## Source Nodes

- graphify
- Nativ
- TurboFieldfare
- colibri.c