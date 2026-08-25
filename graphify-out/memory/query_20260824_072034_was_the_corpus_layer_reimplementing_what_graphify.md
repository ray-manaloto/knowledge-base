---
type: "query"
date: "2026-08-24T07:20:34.351093+00:00"
question: "Was the corpus layer reimplementing what graphify already ships?"
contributor: "graphify"
outcome: "useful"
---

# Q: Was the corpus layer reimplementing what graphify already ships?

## Answer

The corpus's own eight-module semantic-extraction layer was reimplementing what
graphify ships. A native `graphify extract --mode deep --backend claude-cli` over
the pinned graphify clone produced 13,442 nodes / 26,791 edges / 692 communities
in two runs, cost $0.0000 (Max-plan billed), and populated the semantic cache so
the second run replayed 241 of 374 units and paid only for 133.

Mechanism: the corpus layer imported four PRIVATE helpers from `graphify.llm`
(`_pack_chunks_by_tokens`, `_read_files`, `_estimate_file_tokens`,
`_extraction_system`) and rebuilt the loop around `extract_corpus_parallel`,
which calls `save_semantic_cache` and never `load_cached`. The public
`extract` path DOES read the cache (`cli.py:3549`). That single missing edge is
the entire re-buy problem: 45 provider charges for 26 chunks, $17.06 of rework,
an aborted third pass, and the standing "never run again" rule.

Native also supersedes the control plane built around it: six fail-closed hash
gates (plan digest, execution-config digest over seven of our own source files,
source digests, two per-chunk fragment digests, spend ledger) against graphify's
one content hash. graphify's own graph names the redundancy: `check_semantic_cache()`
--conceptually_related_to--> `SHA256 content-hash cache`.

Now driven by `mise run kb-graphify-native-extract` (+ `--cluster`, `--artifacts`),
scoped outside the pinned clone, refusing loudly rather than silently.


## Outcome

- Signal: useful