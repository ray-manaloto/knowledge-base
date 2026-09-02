---
type: "query"
date: "2026-09-02T02:17:31.532448+00:00"
question: "What did N0b cost, what did it ingest, and is the graph actually broken?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did N0b cost, what did it ingest, and is the graph actually broken?

## Answer

N0b ingested 133 Claude Code doc pages (132 from `claude-code-docs` at pinned
commit 1e8a2c48, plus `claude-code`'s CHANGELOG at v2.1.258) as two committed
extraction chunks: 6,462 nodes / 8,478 edges / 344 hyperedges. Both merged rc 0
with conserved arithmetic and 0 replaced. The prose graph went 4,868 -> 11,330
nodes.

Three durable findings.

1. **It was a FIRST extraction, not a re-extraction.** `kb-update`'s worklist
   says "re-extract", but nothing under `sources/extractions/` carried a
   `source_file` under `claude-code-docs/` or `claude-code/` (0 nodes each,
   against a control arm of 274 for `agent-harness-docs`). The chunks NAMED
   `claude-code-docs-*.json` hold `agent-harness-docs/...` identities. Check the
   identities, not the filename, before assuming supersession.

2. **Host-agent extraction cost is per PAGE, not per byte.** 40 pages averaging
   2.6 KB cost 5,118,126 subagent tokens (~128K each) — about what a 16 KB guide
   costs, because the agent's fixed overhead dominates. Price a fan-out by page
   COUNT. Measuring this is what turned a ~60M-token 390-page run into a 22.1M
   133-page one, with essentially no knowledge lost (the pages cut were the same
   snippet in six languages, plus billing FAQs).

3. **`kb-query` rc 3 is a TRUNCATION GUARD, not a broken graph.** Two lanes and
   a handoff recorded the graph as "unusable" on this signal. Control-armed:
   broad query at default budget -> rc 3, with the message itself saying the
   result was truncated and "this prefix is not evidence of absence"; the same
   graph, a narrower query and `--budget 8000` -> rc 0, complete. What actually
   failed on 2026-08-31 was `kb-build` (full rebuild) — a different path from
   merge, which was healthy throughout.


## Outcome

- Signal: useful