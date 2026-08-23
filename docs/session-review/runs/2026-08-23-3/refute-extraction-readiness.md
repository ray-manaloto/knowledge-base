# Refutation lane: extraction-readiness finding #40 (third corpus pass capped out)

HEAD at start: 24d11e49 (tree state recorded below)

## Claim under test
"A THIRD corpus pass is arithmetically capped out before it can reach chunk 0026.
Cumulative durable spend $41.777065 of $63.00 cap ($21.22 headroom); a resumed pass
re-buys EVERY chunk at full price; 26 chunks x $0.952 = ~$24.7 > $21.22, so the run
aborts around chunk ~22, retries 0012, never reaches 0026, publishes zero new work for ~$21."

## Probes run (appended as I go)

### P0 graph query (hook-mandated, control not applicable — orientation only)
`mise run kb-query -- "how does the corpus run resume skip already-paid chunks and enforce the spend cap?"`
-> TRUNCATED, 572 nodes, all vendored-source noise (uv/pytest/codex crates). Our own
modules did not surface. Not evidence either way; proceeded to primary source.

### P1 pin vs docstring version — POSSIBLE WRONG-ARTIFACT
- `grep -n graphifyy pyproject.toml` -> line 32: `"graphifyy[all]==0.9.48"`
- `mise exec -- graphify --version` -> `graphify 0.9.48`
- `.venv/lib/python3.14/site-packages/graphifyy-0.9.48.dist-info`
- BUT graphify_semantic_corpus_run.py docstring says "at the pinned 0.9.45" (twice).
  The no-cache-read premise the finding inherits was measured against 0.9.45.
  -> must re-measure against INSTALLED 0.9.48.

### P2 THE PREMISE ON THE RIGHT ARTIFACT — "no cache read on extract_corpus_parallel's chain"
The module comments (graphify_semantic_corpus.py:914-925 and
graphify_semantic_corpus_run.py:~888) both state this "at the pinned 0.9.45".
The pin is 0.9.48. Re-measured against the INSTALLED 0.9.48:

- `grep -rn "def extract_corpus_parallel" .venv/.../graphify/` -> llm.py:2461 (only definition)
- `grep -rn "save_semantic_cache\|load_semantic_cache\|semantic_cache" .../graphify/llm.py`
  -> 2 hits, both `save_semantic_cache` (2160 docstring, 2581 the write in
  `_checkpoint_chunk`). ZERO reads. **Control arm: the write-side spelling DID
  hit**, so the grep discriminates.
- TOKEN-SPELLING BOUND CHECKED. The reader is not spelled `load_semantic_cache`;
  it is `check_semantic_cache` (cache.py:1187). Its only CODE callers are
  `graphify/cli.py:3549` and `graphify/cli.py:4180` — the CLI layer this driver
  never enters. Every other hit is a `skill-*.md` doc.
- `load_cached` (cache.py:924) callers: `extract.py:16,5279,5575` only. In llm.py
  it appears once, at :2161, inside a DOCSTRING — not a call.
- `grep -n "from .cache import" llm.py` -> ONE line (2581, the writer).
  Control: same grep on extract.py -> `from .cache import load_cached, save_cached`.

=> Premise HOLDS on 0.9.48, not merely on the 0.9.45 the comment cites.

### P3 the resumed pass really does dispatch the WHOLE corpus (no upstream filter)
- `admitted_paths` (run.py:401-422) returns every admitted inventory file,
  deduplicated; no staged/complete filter anywhere in it.
- `execute` (run.py:1293) calls `_extract_corpus(admitted_paths(inventory, source_root), ...)`.
- The skip is in `_dispose` (run.py:1280-1291), called from `on_chunk_done`
  (run.py:1225-1246) AFTER `spend.charge(...)`. Charge is outside every branch.

### P4 the cap IS enforced mid-run (not only at seed)
- run.py:1242-1246: `if spend.exceeded: raise _SpendCapError(... after chunk {index+1})`
- `exceeded` is `total_usd > limit_usd` (run.py:243-244)
- `seeded_spend` (run.py:247-273) refuses only when carried > limit. 41.78 < 63,
  so a third pass is NOT refused up front — it starts, and it spends.
- Accounting is a DELTA per chunk, not cumulative-over-boundary-dir:
  `clear_stale_evidence` removes `provider-spend-*.json` on BOTH dispositions
  (run.py:911 repaid path, run.py:950 failure path), so no double count.

### P5 the ledger namespace is STABLE at HEAD (the resume really does carry $41.78)
`_run_namespace` = sha256(cache_namespace_sha256 + sha256(manifest.json)) (run.py:524-536);
`cache_namespace_for` = sha256 of the whole execution config minus its own field
(graphify_semantic_corpus.py:822-829), which INCLUDES runner/planner/adapter digests.
So an edit to any of those would give a FRESH ledger and refute the finding. Checked:

  stored runner_sha256  ee9a1c00...0ff908c == shasum graphify_semantic_corpus_run.py
  stored planner_sha256 2a53fa4a...d62256  == shasum graphify_semantic_corpus.py
  stored adapter_sha256 23c8d3cd...b008e9  == shasum graphify_semantic_adapter.py

All three MATCH at HEAD 24d11e49. Namespace is stable -> the resume carries the ledger.
(The round's merge fix 17623a32 touched graphify_semantic_corpus_merge.py, which is
not one of the config's digested modules — consistent.)

### P6 the arithmetic, re-derived from the artifacts (not inherited)
- ledger: `{"total_usd":41.77706500000001,"charges":45,"schema_version":1}`
- cap:    `max_total_cost_usd: 63.0` in graphify-out/graphify-semantic-corpus/execution-config.json
- per-chunk `total_cost_usd` from all 26 `chunks/NNNN/adapter-metadata.json`,
  summed = 24.756518, mean 0.952174 (matches the finding's $0.952)
- Cumulative simulation in ledger order, carried = 41.777065, cap 63.0:
    chunk 22 -> ledger_total 62.017320  (under)
    chunk 23 -> ledger_total 63.169416  <<< FIRST CROSSING -> _SpendCapError
  chunk 0012 is re-bought at $0.613447 en route (reached, position 12).
  chunks 24, 25, 26 are NEVER REACHED. Spend for the pass: $21.392351.
- CONTROL ARM on that same simulation with carried = 0.0 (i.e. a re-planned,
  fresh namespace): "reached chunk 26, final ledger 24.756518, aborted=0".
  The probe can return the opposite answer, so its positive result is evidence.

### P7 "publishes zero new work" — checked
- 24 chunks have `receipt.json` status `complete` -> `_dispose` routes them to
  `_resolve_existing_stage` -> `repaid`, no publication.
- 0012 and 0026 both `"status":"failed"`, reasons
  ["fragment-source-scope-mismatch","fragment-source-coverage-mismatch"], and both
  chunk dirs are OCCUPIED (4 files each), which `stage_chunk` refuses. So even a
  lucky re-run cannot publish them without the operator emptying the directory.

## VERDICT: NOT REFUTED (refuted = false)

Every load-bearing sub-claim survived a probe that could have gone the other way.
Two precisions the finding should carry:

1. The abort is after chunk **23**, not "~22". The finding hedged ("around ~22"),
   and the consequential parts (0012 re-bought, 0026 unreached, ~$21 for nothing)
   are exactly right ($21.392351). Off-by-one on a hedged figure, not a refutation.
2. The finding's CONDITION, which it does not state: this holds for a RESUME of
   THIS authorized plan. Any change to runner/planner/adapter/config (including
   raising the cap, which lives in the digested config) mints a new
   cache_namespace -> new run namespace -> carried spend $0 AND zero staged
   chunks, and the control arm above shows that pass completes all 26 for $24.76
   under a fresh $63. That is a different (more expensive, fully re-buying) pass,
   not the one the finding describes — so it does not contradict it, but the
   finding reads as "no third pass is possible" and the accurate statement is
   "no third pass ON THIS LEDGER is possible."

## Cross-finding contradiction check
- #47 (same lane) is consistent and mutually reinforcing.
- #41 says $17.020547 / 19 of 45 charges are unattributable. I can now attribute
  them ARITHMETICALLY: 41.777065 - 24.756518 = 17.020547 EXACTLY, i.e. the
  residual is precisely "every charge with no surviving adapter-metadata".
  That does not refute #41 (the per-charge rows still do not exist) but it does
  bound the mystery to one pass's worth of calls.
- #2 [circles] says "the resume re-bought 18 chunks... $17.06 of $41.78". That
  disagrees with #41's $17.020547 / 19 charges on BOTH numbers (18 vs 19,
  $17.06 vs $17.0205). Two probes of one fact disagreeing is a finding in its own
  right — but it lives in #2/#41, not here: either decomposition leaves the
  ledger at $41.777065 and the headroom at $21.22, which is all #40 depends on.

## GitHub repos touched
_None._ (all evidence is local: the installed graphify wheel in .venv, this repo's
python/src/kb_setup/, and graphify-out/graphify-semantic-corpus{,-chunks}/)
