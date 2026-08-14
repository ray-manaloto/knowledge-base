---
type: "query"
date: "2026-08-14T10:57:26.635762+00:00"
question: "What must issue 301 prove before scaling Graphify semantic extraction beyond the landed one-document candidate?"
contributor: "graphify"
outcome: "useful"
---

# Q: What must issue 301 prove before scaling Graphify semantic extraction beyond the landed one-document candidate?

## Answer

# Issue #301 running findings

- CRITICAL: Exact Graphify v0.9.42 planning reproduced 372 semantic files, 474
  units before disposition, 470 provisional admitted units, and 57 chunks at a
  20,000-token budget. Largest planned chunk is 19,985 estimated tokens and 27
  units. No provider call has run.
- The four provisional inputs are exact/content-bound: two PNGs require
  Graphify's Claude CLI `Read`-tool seam, while the current accepted adapter
  disables every tool; one 20,623-character SVG and one 1,846,384-character HTML
  file are unsplittable under Graphify 0.9.42 and its reader caps them at 20,000
  characters.
- Claude Code 2.1.232 exposes text or stream-json stdin and a remote file-id
  startup download flag. Official API/session docs support image content blocks,
  but the reviewed Claude Code CLI contract does not establish that its
  stream-json stdin accepts those blocks. Keep image coverage unresolved until
  source review and at most one separately authorized real prototype.
- The plan publishes source inventory, provisional exclusions, chunk ledger,
  exact execution config/cache namespace, and a content-addressed manifest.
  Verification remains `incomplete`, never successful, until independent
  authority binds both source decisions and execution config.
- TDD found a verifier mistake: Graphify groups units by directory when packing,
  so valid chunk order is not global source-inventory ordinal order. Coverage is
  correctly verified as exact set equality plus duplicate rejection.


## Outcome

- Signal: useful