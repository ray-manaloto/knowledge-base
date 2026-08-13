---
type: "query"
date: "2026-08-11T06:45:13.480421+00:00"
question: "Did the first canonical-dependency audit represent every approved critical source?"
contributor: "graphify"
outcome: "corrected"
correction: "A critical-source audit must derive source-only anchors from currency.toml and declaratively assign disjoint shared-document prefixes; relying only on repo tags silently omits committed semantic extractions."
source_nodes: ["canonical_dependency", "mattpocock-skills"]
---

# Q: Did the first canonical-dependency audit represent every approved critical source?

## Answer

No. The first pass omitted mattpocock-skills because its existing manifest had no source_only currency declaration, and it counted only repo tags, leaving shared agent-harness-docs Claude and Codex documentation outside their canonical anchors. The corrected declarative configuration adds mattpocock-skills as source_only and assigns disjoint offline-doc prefixes to claude-code and codex. The live rerun reports 13 anchors, mattpocock-skills at 199 nodes and 6 receipts, claude-code at 254 nodes and 4 receipts, missing only ruff and chezmoi, with zero cross-dependency links still honestly RED.

## Outcome

- Signal: corrected
- Correction: A critical-source audit must derive source-only anchors from currency.toml and declaratively assign disjoint shared-document prefixes; relying only on repo tags silently omits committed semantic extractions.

## Source Nodes

- canonical_dependency
- mattpocock-skills