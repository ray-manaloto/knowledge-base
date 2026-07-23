---
type: "query"
date: "2026-07-23T20:27:52.344467+00:00"
question: "How to ingest docs graphify's fetcher can't get (auth walls, JS SPAs, 12k-char truncation)?"
contributor: "graphify"
outcome: "useful"
source_nodes: ["Repository knowledge as system of record", "Graph (map of who does what next)"]
---

# Q: How to ingest docs graphify's fetcher can't get (auth walls, JS SPAs, 12k-char truncation)?

## Answer

graphify's add fetcher caps at ~12000 chars and returns nav-chrome stubs for JS-rendered/auth-walled pages (LinkedIn login wall, antigravity SPA, X auth wall, openai TOC-only). Recover full text via logged-in Chrome (claude-in-chrome get_page_text), vendor to sources/media or raw, then host-agent extract like any prose. The mintlify .md URL suffix also bypasses nav-chrome truncation for docs.

## Outcome

- Signal: useful

## Source Nodes

- Repository knowledge as system of record
- Graph (map of who does what next)