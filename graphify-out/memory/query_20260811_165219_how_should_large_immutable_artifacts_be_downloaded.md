---
type: "query"
date: "2026-08-11T16:52:19.147485+00:00"
question: "How should large immutable artifacts be downloaded reproducibly and quickly?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["ArtifactProvider", "HuggingFaceXetProvider"]
---

# Q: How should large immutable artifacts be downloaded reproducibly and quickly?

## Answer

Use a provider-neutral skill to mise task to typed Python boundary. For Hugging Face, pin huggingface-hub 1.27.0 and hf-xet 1.6.0, default to a zero-payload plan, require explicit --apply, preserve local_dir metadata for resume, validate immutable revisions and disk headroom, and select balanced or high-performance explicitly. Use aria2 only for stable static URLs with hashes and rclone only for verified mirrors.

## Outcome

- Signal: useful

## Source Nodes

- ArtifactProvider
- HuggingFaceXetProvider