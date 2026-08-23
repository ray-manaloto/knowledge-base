# Refutation lane — finding [context] #25 (58-chunk extraction ~350k tokens)

CLAIM: "Scoped deep-extraction work (58 graphify chunks) will require ~350k tokens at
Phase 2's observed burn rate (3,482 tok/min), indicating need for explicit staging plan
and /clear-prep checkpoints"

## Probe 1 — the repo ALREADY holds a deterministic per-chunk token ledger

    uv run python -c "...json chunk-ledger.json..."
    chunks: 58 token_budget: 20000 unit_count: 475
    SUM estimated_tokens (INPUT) = 1038052
    min/max per chunk: 12912 19985
    max_output_tokens per chunk: 64000  -> worst-case output total 3,712,000

File: graphify-out/graphify-semantic-corpus/chunk-ledger.json
=> INPUT alone is 1.04M tokens, ~3x the claimed "~350k total".

## Probe 2 — the backend is a SUBPROCESS, not the session context window

    graphify-out/graphify-semantic-corpus/execution-config.json
    backend = claude-cli
    auth_route = claude.ai:firstParty:max
    claude_model = claude-opus-5
    cache_policy = checkpoint-write-atomic-per-chunk

=> the units differ: "Phase 2 burn rate" measures MAIN-THREAD context growth
   (driven per finding #23 by 58x hook_guard searches + 5x hook_guard reads);
   the 58-chunk run spends tokens in a claude-cli subprocess.
   Also: cache_policy is ALREADY per-chunk atomic checkpointing.

## Probe 3 — cross-check by a SECOND route (two routes agree)

    route A (sum chunk.estimated_tokens): 1038052
    route B (sum of 475 member estimates): 1038052   AGREE: True
    members total 475 == ledger unit_count 475

## Probe 4 — CONTROL ARM (the probe can return the OTHER answer)

    CONTROL: the same probe returns ~350k at chunk 20 -> 356758 (20/58 = 34% of corpus)
    full 58: 1038052
    CONTROL(2): wrong key spelling 'token_estimate' -> silently 0 (my own first probe);
                right key 'estimated_tokens' -> 1038052; nonexistent key -> KeyError.
=> the probe discriminates. ~350k is what 34% of the corpus costs.

## Probe 5 — the claim's own rate, against the run's own documented duration

    python/src/kb_setup/graphify_semantic_corpus_authority.py:270
      "at ~11 minutes a chunk and `concurrency = 1`, 58 chunks is **~10.6 h**.
       Chunking differently does not change that total; only concurrency would."
    also graphify_semantic_corpus_run.py:199-200, graphify_semantic_corpus.py:72

    3,482 tok/min x 636 min = 2,214,552 tokens   (6.3x the claimed ~350k)
    350,000 / 3,482 = 100.5 min  <- a duration nothing in the repo supports

=> the ~350k figure is NOT derived from the cited rate. The rate is decorative.

## Probe 6 — the remedy the finding "indicates a need for" is ALREADY BUILT

* staging plan: chunk-ledger.json (58 chunks, 475 units) + execution-config.json
  (43 fields) + the committed authority record in graphify_semantic_corpus_authority.py
* checkpoints: cache_policy = checkpoint-write-atomic-per-chunk;
  SPEND_LEDGER = "spend-ledger.json" (run.py:141) persists BETWEEN runs;
  resumption = verified per-chunk skip (run.py:22-40)
* cost governance: _Spend, a cumulative provider-spend cap Ray ruled 2026-08-17
  (graphify-out/memory/query_20260818_002641_*.md)

## Probe 7 — the instrument itself: the burn rate does not reproduce

Session under review = 5ec8da38 (16:57:19Z -> 18:17:09Z).
Re-derived from the SAME reminders:
    PHASE2 (>=17:18:24Z): 240,168 tokens over 58.8 min = 4,088 tok/min  (n=194)
    PHASE1:                22,674 tokens over 14.6 min = 1,551 tok/min  (n=14)
    whole session delta 121,245 < PHASE2 delta 240,168  -> IMPOSSIBLE
Cause: the counter is NON-MONOTONIC. At 2026-08-22T17:15:02.857Z it RESET
    14,858,403 -> 15,000,000 (+141,597).
`<total_tokens>N tokens left</total_tokens>` is a remaining-ALLOWANCE countdown,
not a cost meter, and it spans two series here.
`isCompactSummary` count in this transcript = 0 (control: 'timestamp' = 1289 hits,
'compact' any-case = 6). No compaction record exists; the 17:15:02 reset does.

## VERDICT: REFUTED
