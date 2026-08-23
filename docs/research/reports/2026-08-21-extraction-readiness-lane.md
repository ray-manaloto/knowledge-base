# lane: extraction-readiness — working notes (2026-08-21)

## F1 RESUME IS NOT FREE — confirmed at 0.9.48 (re-derived, not inherited)
- `graphify_semantic_corpus_run.py:882-893` claims (citing pinned **0.9.45**) that
  `extract_corpus_parallel`'s chain has no cache read, so every already-staged chunk
  is paid for again.
- Re-derived against INSTALLED 0.9.48 (`importlib.metadata.version('graphifyy')` -> 0.9.48):
  - `load_cached` call sites: `cache.py:1236`, `cache.py:1519`, `extract.py:5279`, `extract.py:5575` — none in `llm.py`.
  - CONTROL ARM (writer, known present on that path): `_checkpoint_chunk` at `llm.py:2571` def, called `llm.py:2628` and `llm.py:2653`.
  - `save_semantic_cache` is imported inside `extract_corpus_parallel` (llm.py ~2573+); `check_semantic_cache` (cache.py:1187) is NOT called there.
- => write-only checkpointing. A restarted 58-chunk run re-buys all 58.
- Driver does not filter either: `execute` passes `admitted_paths(inventory, source_root)` (all paths) — `_dispose` classes an already-staged chunk `repaid`, i.e. paid twice.

## F2 HARD BLOCKER — plan verifies AUTHORIZED but every chunk will FAIL to stage
- `mise run kb-graphify-semantic-corpus verify` -> rc=0, `state=complete`, `execution_authorized=true` (run 2026-08-21).
- BUT: `graphify_semantic_corpus.py:185-194` `_ACCEPTED_GRAPHIFY_RUNTIME` still declares
  version/cli/sdk **0.9.47** (+ wheel_sha 2a8b13cc…, sdist_sha 26e5766f…).
  Installed is **0.9.48** (`importlib.metadata.version('graphifyy')`).
- Measured, both sides:
  - `graphify_baseline.runtime_identity(Path('.'))` -> 0.9.48 / wheel 4f745d72… / sdist 14eaac83…
  - `graphify_semantic_slice.preflight(...)` (the receipt every chunk carries) -> `graphify_version='0.9.48'`
  - committed `execution-config.json` -> `graphify_version = 0.9.47`
- `_provider_runtime_reasons` (corpus.py:1916-1917) compares BOTH for equality ->
  `provider-graphify-runtime-mismatch` + `provider-graphify-version-mismatch`.
- Consumed by `stage_chunk` (corpus.py:2225) -> `status="failed"` for EVERY chunk.
- Net: the run spends real money per chunk (chunk 1 measured 1.12 USD per the code
  comment at corpus.py:421-425) and stages 58 failures. `completeness_rc` -> 1.
- Re-planning does NOT fix it: `_effective_config` reads the same hardcoded constant
  (corpus.py:746-747). It is a SOURCE edit at corpus.py:185-194.
- NOT stale: `_ACCEPTED_GRAPHIFY_DETECT_OBJECT = d16b5800…` is correct — the blob is
  IDENTICAL at v0.9.47 and v0.9.48 (`git -C sources/graphify rev-parse v0.9.47:graphify/detect.py`
  and `HEAD:graphify/detect.py` both d16b5800…). Advisory calibration survives the bump.
- ALSO NOT a blocker (contra the handoff): `claude_version` now records 2.1.238 = running
  2.1.238; and `review_status="provisional"` is REQUIRED by `_advisory_reasons` (corpus.py:1504),
  not a defect.

## F3 SECOND stale pin site — kb-currency-check names it
`mise run kb-currency-check`:
  graphify: ref-binding — `python/src/kb_setup/graphify_semantic_slice.py` reads **v0.9.45 /
  0738af373af9cf5c95f862cc5f3327fd96b4ea23** but `sources/graphify.manifest` pins v0.9.48 /
  b2cd3626…. Two independent stale sites for one bump (memory: "the graphify bump is not one line").

## F4 kb-build RAN AND FAILED, and the aggregate graph is 9 days old + unprovenanced
- `graphify-out/.build-failure.json` (mtime Aug 20 16:20) / currency: build FAILED
  2026-08-20T21:20:51Z — `IncompleteGraphifyOperationError: Graphify extract failed closed
  (incomplete): stderr; 11 file(s) had syntax errors … c/backend_cuda.cu …`
- That source is **colibri** (`sources/colibri/c/backend_cuda.cu`; control arm: the same
  `find` locates `sources/graphify/graphify/detect.py`). NOT the #397 anthropic-sdk-python cause.
- `graphify-out/.currency-stamp.json` DOES NOT EXIST -> no successful build has ever stamped.
- `graphify-out/graph.json` is dated **Aug 12 06:12**, as are graph-prose.json, GRAPH_REPORT.md
  and `.graphify_labels.json`. The graph every consumer queries is 9 days stale and its builder
  version is UNKNOWN — doctrine says treat that as red.

## F5 #417's register is out of date and its own invariant is broken
- 5 manifests now carry `build = skip`: codebase-memory-mcp, GitNexus (both in #417),
  plus **codegraph, codex, colibri** (NOT in #417; all three staged-modified in git status).
- #417 states: *"Every entry below is `scope = study` so far. If that stops being true, the
  entry says so in bold."*
  - `sources/codegraph.manifest`: `scope = corpus` — its own skip_reason says
    *"scope=corpus, so this IS aggregate loss"*.
  - `sources/codex.manifest`: no `scope` line; skip_reason says *"TOOLCHAIN source, so the
    corpus cannot describe a tool we run while this holds"*.
- So real corpus loss is now happening and the register does not say so. UPDATE #417, don't re-file.

## F6 Per-file provenance does NOT exist (#411 unbuilt)
- Control-armed: `ls sources/*.extraction-provenance.json` -> no matches, while
  `ls sources/*.manifest | wc -l` -> 73. `grep -rn "extraction-provenance" python/src/kb_setup/ schemas/`
  -> 0 hits, while the control `grep -rln "cache_namespace_sha256" python/src/kb_setup/` -> 3 files.
- Finest granularity today: model recorded ONCE per plan (`execution-config.json:claude_model`,
  `resolved_model`, `max_turns`, `deep_mode`), and paths recorded per CHUNK
  (`ChunkStageReceipt.source_paths`, corpus.py:491-520). No per-file, no content-hash key.

## F7 Coverage arithmetic of the current plan (no silent loss)
`source-inventory.json`: discovered 479 units, 4 intentional exclusions
(docs/demo-path.svg, docs/graph-hero.png, docs/logo.png, worked/rsl-siege-manager/graph.html),
admitted 475, detected_source_count 374. `chunk-ledger.json`: 58 chunks, 475 members,
**370 distinct paths** (105 units are slices of an already-listed file).

## F8 The `--effort` LEVEL is not recorded anywhere machine-readable
- `CORPUS_PROFILE` sets `effort="high"` (`graphify_semantic_slice.py:551`).
- `CorpusExecutionConfig` (corpus.py:382-441) has NO `effort` field.
- Control-armed on the committed config: `[k for k in json.load(...) if 'effort' in k]` -> `[]`,
  while `deep_mode` and `max_turns` ARE present. The only "effort" string in the file is the
  flag NAME inside `claude_required_flags` — which asserts the flag is SUPPORTED, not its value.
- It is bound only INDIRECTLY, via `semantic_slice_sha256` (a module digest). So it is
  tamper-evident but unreadable — which is exactly what #411 and #301's cache-identity
  criterion ("exact model, prompt, … token and retry bounds") ask for.

## F9 The 10.6-hour task has no timeout, unlike the other 7 slow tasks
`awk '/^\[tasks\./{t=$0} /^timeout/{print t" -> "$0}' mise.toml` -> 8 tasks declare `timeout`
(lint 20m, test 25m, eval 25m, kb-build 180m, kb-transcribe 120m, kb-artifacts 60m,
brain-audit 10m, hk-test 10m). `[tasks.kb-graphify-semantic-corpus]` (mise.toml:669-671)
declares NONE, and its `run` action is the ~10.6 h / 58-chunk provider run.

## F10 Zero derived artifacts exist; the third leg of the goal is unstarted
- Control-armed: `ls graphify-out | grep -iE "wiki|graphml|obsidian|svg|cypher|html"` -> nothing,
  while the control `grep -E "GRAPH_REPORT|graph-prose"` -> both present.
- `graphify-out/reflections/LESSONS.md` exists (Aug 20 23:04) but that is `kb-reflect` over
  work-memory, not reflection over the graphify corpus.
- `sources/extractions/` holds 25 chunks; none is corpus-run derived
  (`graphify-2026-08-06-docs.json` is a host-agent DOCS chunk).

## F11 Ordering: kb-build RED does NOT block the RUN, it blocks the MERGE
The corpus run only needs `sources/graphify` at the pin (present, b2cd3626/tree be863673).
But `graphify_ops.merge_chunk` (graphify_ops.py:207,236) merges INTO
`graphify-out/graph.json` — the Aug 12, unstamped, unprovenanced artifact. Merging the
corpus onto that produces an aggregate no `kb-build` reproduces. So #397 must be green
BEFORE the merge step, not before the run.

## F12 The cap tolerates at most ONE early restart
`max_total_cost_usd = 100.0`; chunk 1 measured 1.12 USD (corpus.py:421-425); 58 x 1.12 = 64.96.
A restart after chunk N costs 1.12N + 64.96, so N > 31 makes the plan UNCOMPLETABLE inside
its own authorized cap (`seeded_spend` refuses before the first call). With no cache read
(F1) and no task timeout (F9), an interruption past chunk 31 requires a NEW authorization.

## F13 LIVE BLOCKER — AWS_* in the ambient env makes `run` refuse at preflight
- `env | grep -c "^AWS_"` -> **4** (AWS_ACCESS_KEY_ID, AWS_DEFAULT_REGION, AWS_REGION,
  AWS_SECRET_ACCESS_KEY). They survive `mise exec -- env` (control arm: `grep -c "^PATH="` -> 1).
- `graphify_semantic_slice.preflight(Path('.'), require_max_turns=True, profile=CORPUS_PROFILE)`
  raises `ValueError: forbidden routing environment names: AWS_ACCESS_KEY_ID,
  AWS_DEFAULT_REGION, AWS_REGION, AWS_SECRET_ACCESS_KEY`.
- ARMED BOTH WAYS: the same call under
  `env -u AWS_ACCESS_KEY_ID -u AWS_DEFAULT_REGION -u AWS_REGION -u AWS_SECRET_ACCESS_KEY …`
  returns a receipt (`graphify_version 0.9.48`). So the probe discriminates.
- `execute()` calls `preflight` as its third statement (corpus_run.py:1034-1036), before the
  tempdir/overlay block — so the whole run dies there. It FAILS CLOSED (nothing is spent),
  which is correct, but it cannot start.
- Control-armed: `grep -n "clean_env"` over graphify_semantic_corpus_run.py,
  graphify_semantic_corpus.py and graphify_semantic_slice.py -> **0 hits**, while the same
  grep shape found `cache_namespace_sha256` in 3 kb_setup files. So `do-not.md` #4's
  `clean_env()` is NOT on this path; the corpus path has its own forbidden-name refusal
  instead, and nothing strips the vars for it.
