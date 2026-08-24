---
type: "query"
date: "2026-08-24T07:20:40.968196+00:00"
question: "Is graphify's claude-cli backend broken, did the corpus cost $41.78, and does parallel claude-cli corrupt session state?"
contributor: "graphify"
outcome: "corrected"
correction: "THREE beliefs this round overturned, each held with confidence and each wrong.\n\n1. \"graphify's claude-cli backend is broken (#2076).\" TRUE of an older version;\n   FALSE of the pinned 0.9.48, which passes `--json-schema` when the CLI supports\n   it, prefers the envelope's `structured_output`, and carries a prose-tolerant\n   parser. 19/19 chunks extracted clean on it. The rule \"source beats issue\n   tracker\" was applied to the tracker but never to our own restatement of it,\n   which had frozen at the version that was true when written.\n\n2. \"The corpus run cost $41.78.\" It was never money. The receipts record\n   `auth_method: claude.ai`, `subscription_type: max`, and graphify prices this\n   backend at zero because it bills the plan. Every \"we cannot afford another\n   pass\" conclusion — including a whole advisory round and a needle-search for\n   one corrupted byte — rested on reading a valuation as a charge. Check the UNIT\n   before optimising against a number.\n\n3. \"Parallel claude-cli risks session-state corruption\" (graphify's own clamp\n   comment). Its stated mechanism is contradicted by the argv graphify itself\n   builds: `--no-session-persistence` is passed on every call, so there is no\n   persisted session state to contend over. The neighbouring `ollama` clamp cites\n   a real bug (#798); the claude-cli clamp cites nothing. Measured: 19 chunks at\n   concurrency 4, clean. A comment is a claim, not evidence — and reaching for an\n   ADJACENT case's evidence to shore up an unevidenced one is borrowing\n   credibility, which is how the wrong call nearly stood.\n"
---

# Q: Is graphify's claude-cli backend broken, did the corpus cost $41.78, and does parallel claude-cli corrupt session state?

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

- Signal: corrected
- Correction: THREE beliefs this round overturned, each held with confidence and each wrong.

1. "graphify's claude-cli backend is broken (#2076)." TRUE of an older version;
   FALSE of the pinned 0.9.48, which passes `--json-schema` when the CLI supports
   it, prefers the envelope's `structured_output`, and carries a prose-tolerant
   parser. 19/19 chunks extracted clean on it. The rule "source beats issue
   tracker" was applied to the tracker but never to our own restatement of it,
   which had frozen at the version that was true when written.

2. "The corpus run cost $41.78." It was never money. The receipts record
   `auth_method: claude.ai`, `subscription_type: max`, and graphify prices this
   backend at zero because it bills the plan. Every "we cannot afford another
   pass" conclusion — including a whole advisory round and a needle-search for
   one corrupted byte — rested on reading a valuation as a charge. Check the UNIT
   before optimising against a number.

3. "Parallel claude-cli risks session-state corruption" (graphify's own clamp
   comment). Its stated mechanism is contradicted by the argv graphify itself
   builds: `--no-session-persistence` is passed on every call, so there is no
   persisted session state to contend over. The neighbouring `ollama` clamp cites
   a real bug (#798); the claude-cli clamp cites nothing. Measured: 19 chunks at
   concurrency 4, clean. A comment is a claim, not evidence — and reaching for an
   ADJACENT case's evidence to shore up an unevidenced one is borrowing
   credibility, which is how the wrong call nearly stood.
