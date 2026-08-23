
# Lane: extraction-readiness — 2026-08-23

HEAD at report time: 272d14bc3785e07bf935bb356d63af427354eba1 (branch claude-resync-2.1.241)
Dirty: docs/direction/2026-08-22-ray-directives.md (M), graphify-out/memory/query_20260823_032615_*.md (??)

## Sweep bound proof
`gh issue list --state open --limit 1000 --json number --jq length` -> 229 (2026-08-23).
229 != 1000, so not truncated at the limit.

## OBSERVED state at 272d14bc (all commands run 2026-08-23)

- `uv run kb-setup graphify-semantic-corpus verify` -> rc=0
  `{"execution_authorized":true,"reasons":[],"state":"complete","structural_complete":true}`
- `uv run kb-setup graphify-semantic-corpus record` (dry) -> rc=2,
  `moved=none; decision_moved=none; recordable=false; accepted=false`
  26 chunks / 170 units / 466,590 admitted tokens; 28 dup groups, 305 units dropped (55.1%).
- Plan member digests all match manifest.json (5/5, shasum -a 256).
- `claude --version` = **2.1.241**; `graphify_semantic_slice.py:561 _CURRENT_CLAUDE_VERSION = "2.1.240"`;
  `execution-config.json claude_version = "2.1.240"`.

## RE-DERIVED, CONTRADICTS INHERITED CLAIMS

1. #452 / #426 premise "_ACCEPTED_GRAPHIFY_RUNTIME still 0.9.47" is **FALSE at this SHA**:
   `graphify_semantic_slice.py:340-357` reads version/cli/sdk = "0.9.48".
   `_CURRENT_GRAPHIFY_RUNTIME` :446-455 = 0.9.48. Both agree with the plan.
2. Brief's claim "`--effort` appears only as a flag NAME ... its VALUE is in no field at all"
   is **FALSE at this SHA**: `execution-config.json` has top-level `"effort":"high"`.
   The remaining #411 gap is PER-FILE/PER-SOURCE granularity, not the value's absence.

## A-CLASS / B-CLASS BLOCKER (NEW, UNFILED)

**The plan->preflight Claude identity window is unchecked, so the run spends the full
cap and stages every chunk FAILED.**
- `graphify_semantic_corpus_run.py:1029-1060 _assert_graphify_runtime_unchanged_since_plan`
  compares ONLY graphify fields. Its own docstring cites #426 and says it "mirrors
  `_adapter_overlay`'s Claude check ... for the Graphify half rather than the Claude half" —
  but `_adapter_overlay` (:438-447) compares preflight->use, NOT plan->preflight.
- `graphify_semantic_slice.py:655-681 current_claude()` returns three LITERALS
  (`_CURRENT_CLAUDE_VERSION` etc). It is a declaration, never a measurement.
  Proof: the record dry-run reports `moved=none` while the live binary is 2.1.241.
- `preflight()` (:1014-1085) DOES measure the live binary (`--version`, `sha256_file`)
  but never compares it to the plan.
- The only comparison is POST-HOC: `graphify_semantic_corpus.py:2334-2360
  _provider_runtime_reasons` -> `provider-version-identity-mismatch` +
  `provider-executable-identity-mismatch`, reached from `stage_chunk` (:2649+) AFTER
  the provider produced that chunk's evidence.
- `execute`'s `_dispose` (:1213-1223) appends a failed outcome and does NOT raise, so
  the loop continues through all 26 chunks.
=> Run today: ~$63 spent, 26/26 chunks staged `failed`. Same failure shape as #426,
left open for the Claude half. STATUS: UNFILED (partial: #426 fixed the graphify half only).

## L7 HONEST BOUND (control-armed)
No corpus run has ever reached a provider. `find graphify-out/cache graphify-out/graphify-semantic-corpus*`
returns ONLY the 6 plan files + an AST cache; no staged chunk dir, no receipt, no provider-boundary log.
CONTROL: the same probe finds the SLICE's real provider evidence —
`graphify-out/graphify-semantic-slice/{receipt.json,provider-boundary-start.json,adapter-metadata.json,semantic-fragment.json}`
(mtime 2026-08-22 22:23). So the probe discriminates.
=> Every claim below about what the run WOULD do is INFERENCE FROM SOURCE, not observation.
The only OBSERVATIONS are: the verify/record rc and JSON above, the file digests, and `claude --version`.

## COVERAGE-DEBT ITEMS (all reached)
- `_receipt_reasons` HEAD:1588, `_runtime_reasons` HEAD:1495 (found by name via
  `git grep -n 'def _receipt_reasons' HEAD -- ...`). READ. They are SLICE-ONLY: the only
  callers are graphify_semantic_slice.py:1638 and :1723. The corpus path uses its own
  `_provider_receipt_reasons`/`_provider_runtime_reasons`. So they do NOT gate the corpus run.
  Control arm: the same grep DID find the corpus's own callers, so it discriminates.
- `_runtime_reasons` hard-compares `runtime.required_flags == (*_REQUIRED_CLAUDE_FLAGS,"--max-turns")`
  — no `--effort`. The corpus profile appends `--effort`, so this verifier could never accept a
  corpus receipt. Harmless today only because nothing routes a corpus receipt through it.

## CLASS D — the operator surface lies about the corpus commands (UNFILED)
`cli.py` carries TWO hand-maintained usage literals, neither generated from the dispatch table:
- no-args usage (cli.py:61-99): 11 of 59 dispatched subcommands absent.
- unknown-command usage (cli.py:520-538): **27 of 59 absent**, including
  `graphify-semantic-corpus`, `-corpus-merge`, `-slice`, `graphify-baseline`, `graphify-contract`.
Measured with `uv run python` over cli.py at HEAD; CONTROL: "build" IS found in the same block,
"graphify-semantic-corpus" is not. So an operator who mistypes the corpus verb is told it does not exist.
PARTIAL: same class as #412 (generated enums not string literals), filed for manifest kind/scope/build.

## CLASS B — the $63 cap is derived from a rate the codebase itself superseded (UNFILED)
- `graphify_semantic_corpus.py:92-103` derives `_MAX_TOTAL_COST_USD = 63.0` (2026-08-21) as
  `26 x 1.12 = 29.12; x2 restart = 58.24; +8% -> 63.0`.
- `graphify_semantic_corpus_authority.py:343-349` (entry "RE-RECORDED 2026-08-18 (g), after the
  FIRST REAL CHUNK RAN") records the measured `spend-ledger.json` `{"total_usd":1.3249605,"charges":1}`
  and calls it "the first time this corpus has been able to say what a chunk cost" — i.e. the
  1.12 the cap rests on was an ESTIMATE from before any chunk completed, superseded 3 days earlier.
- Re-derived with the SAME rule Ray set, at the measured rate:
  26 x 1.3249605 = 34.449; x2 = 68.898; +8% = **74.41**, not 63.
- At cap 63 the pre-restart spend may be at most 63 - 34.449 = 28.55 USD = **21.5 chunks**.
  An interruption past chunk ~21 leaves the run UNCOMPLETABLE inside its own cap — the exact
  failure the 2026-08-21 ruling raised 100 -> 140 to remove ("100.0 left an interrupted run past
  chunk ~31 uncompletable").
- 1.12 is restated in THREE places (corpus.py:92, :102, :541; authority.py:155) against ONE for 1.32.
STATUS: UNFILED. PARTIAL against #456 (restart trap / cap refuses past a chunk) — #456 names the
mechanism, not this arithmetic; and against #377 (duplicated literals).

## CLASS C — the 900s justification cites token counts the current ledger does not have
`graphify_semantic_corpus.py:56-61` says chunk 1 = "7 members, 18,218 estimated tokens ... median 18,569".
Re-derived from `chunk-ledger.json` at HEAD (jq over .chunks): n=26, min=12,912, max=19,979,
**median 18,664**, chunk ordinal 1 = 7 members / **17,562** tokens, sum 466,590.
Member count and min/max agree; the two token figures do not. #458 (FILED, still live) is
therefore understated: the 659.5s measurement was on a chunk 13.8% SMALLER than the largest
planned chunk, before `--effort high` and `--max-turns 3` are added.

## SWEEP INTEGRITY
`gh issue list --state open --limit 1000 --json number --jq length` -> **229** at first read
(2026-08-23 ~03:31Z); the body fetch with the same limit also returned **229**. A later
re-read returned **228** consistently across four field sets. `comm` on the two number sets
names the difference: **#452 closed at 2026-08-23T03:29:12Z**. Neither number equals the
limit, so the sweep was NOT truncated. Filtering was on TITLE+BODY (164 candidates of 229);
title-only would have been a spelling bound — measured live: `deep extraction` -> 7 issues,
`deep-extraction` -> 0.
Authorship: 228/228 by `sortakool` (the repo owner).
PROMPT INJECTION: scanned all 229 bodies for imperative-override shapes. ONE hit, benign —
issue text quoting `kb-land`'s own output ("You are now on `main`"). CONTROL: the same grep
form matched "control arm" in 42 bodies, so it discriminates. **No issue body attempted to
instruct me.**

## RE-DERIVED ISSUE STATUS (code at 272d14bc, not the issue text)
| # | claim | status now |
|---|---|---|
| 452 | `_ACCEPTED_GRAPHIFY_RUNTIME` at 0.9.47 | **FIXED** — slice.py:340-357 reads 0.9.48. Closed 03:29Z; my re-derivation agrees independently. |
| 426 | plan authorized while runtime frozen; 58/58 fail | **HALF-FIXED** — the graphify half is guarded (`_assert_graphify_runtime_unchanged_since_plan`); the CLAUDE half is not (see the A/B blocker above). |
| 457 | slice `receipt-semantic-fingerprint-mismatch` every run | **FIXED** — live fingerprint `6047cf0e…` == `_ACCEPTED_SEMANTIC_FINGERPRINT_SHA256` == plan. Measured via `graphify_sdk.semantic_api_fingerprint()`. STALE-OPEN. |
| 334 | operator must scrub `AWS_*` by hand | **MOSTLY FIXED** — `scrub_route_overrides()` runs first in `execute`. RESIDUAL, UNFILED: the 4 proxy names are in the 37-name REFUSAL set but deliberately excluded from the SCRUB. Armed: `route_override_names({'HTTPS_PROXY':…})` -> `('HTTPS_PROXY',)` while `scrub_route_overrides({'HTTPS_PROXY':…,'AWS_REGION':…})` -> `('AWS_REGION',)`. On a proxied host the run refuses at preflight with no mechanism. |
| 456 | restart trap; cap refuses past chunk 31; no timeout | **PARTLY** — the timeout half is fixed (`mise.toml:719 timeout="16h"`). The cap half is LIVE and its arithmetic has moved: past chunk **~21.5**, not 31 (see the $63 finding). |
| 458 | 900s ceiling, 1.36x headroom, measured without `--effort high` | **LIVE and understated** — `_INFERENCE_TIMEOUT_SECONDS=900`, corpus.py:56-61 states the omission itself. |
| 411 | per-file model/effort provenance | **LIVE but narrower than the brief said** — `execution-config.json` DOES carry `"effort":"high"` at top level. What is absent is per-file/per-source attribution. |
| 417 | register of every `build = skip` source | **STALE** — 5 manifests carry `build = skip` today (codegraph, codebase-memory-mcp, codex, colibri, GitNexus); #417's body names only 2 (codebase-memory-mcp, GitNexus). It omits **codegraph, which is `scope = corpus`** — real aggregate loss, and the exact line the issue says to watch in bold. CONTROL: `test()` returns true for the 2 it does name. |
| 409 | reviewed-warning inventories do not scale | **READ. MERGE-SIDE ONLY** — it blocks `kb-build`, which the corpus RUN never touches. |
| 429 | no hook_guard redirect for the corpus/slice verbs | **LIVE** — and compounded by the CLI usage divergence above. |
| 332 | `attempts=provider_calls` unarmed | **LIVE** — unchanged; needs a real staged chunk, which cannot exist until a run happens. |

## RUN vs MERGE — settled
- The RUN needs ONLY `sources/graphify`. Verified present, CLEAN, at exactly the pinned
  `commit b2cd3626…` and `tree be863673…` that `manifest.json` records.
- `graphify_semantic_corpus_run.py` and `_merge.py` contain **0** references to `graph.json`.
  CONTROL: `graphify_ops.py` -> 22, so the grep discriminates. The 6 hits in
  `graphify_semantic_corpus.py` are all `worked/rsl-siege-manager/graph.json` inside the
  graphify SOURCE tree, plus the run's own output file.
- The MERGE writes `sources/extractions/<name>-docs.json`; `mise run kb-merge` then writes
  the aggregate.
=> **#397 / #409 / #417 (kb-build RED) do NOT block the run. They block the rebuild.**

## PRIVATE-API COUPLING — pinned and VERIFIED
`graphify_semantic_corpus.py:29-38` imports four PRIVATE graphify symbols
(`_estimate_file_tokens`, `_extraction_system`, `_pack_chunks_by_tokens`, `_read_files`) —
these produce the chunk ledger, the token estimates and the prompt contract.
Mitigated: `execution-config.json graphify_llm_sha256 = 5321f6a6…`; I hashed the installed
`.venv/lib/python3.14/site-packages/graphify/llm.py` and it MATCHES exactly. So drift is
detectable at plan time. `graphify_semantic_corpus_prototype.py:16-20` imports two of the
same private names and is reachable from tests only (no CLI verb, no mise task).

## THE A/B BLOCKER, SHARPENED (and one self-correction)
SELF-CORRECTION: `graphify_semantic_adapter._real_executable` (adapter.py:302-308) DOES
re-verify the claude sha256 on EVERY invocation, against the PREFLIGHT value — so a
MID-RUN self-update is caught per chunk. My earlier reading that it was checked once was
wrong. What remains open is only the **plan -> preflight** window, and that is the one
that matters, because nothing in it is checked at all.

WHY THE DOCUMENTED REMEDY DOES NOT REMEDIATE: the handoff's procedure is
"bump the constant -> `record --accept` -> run". But `record` compares the plan against
`current_claude()`, which returns LITERALS. Proven today: live claude is 2.1.241, the plan
says 2.1.240, and `record` reports `moved=none; recordable=false`. So re-recording
immediately before the run cannot close the window either.

MEASURED RECURRENCE RISK: `~/.local/share/claude/versions/` holds 2.1.239 (Aug 21 14:57),
2.1.240 (Aug 22 10:13), 2.1.241 (Aug 22 20:11) — **3 self-updates in 29h, mean ~14.6h**.
The run is projected at ~4.8h. The ledger records 3 more moves (233->234, 235->236,
236->238) plus 238->240. So this is not a one-off to patch; it is a ~1-in-3 recurrence.

MECHANICAL REMEDY (not "remember"): add `_assert_claude_unchanged_since_plan(preflight_receipt,
config)` beside the graphify one at `graphify_semantic_corpus_run.py:1094`, comparing
`preflight_receipt.{version,executable_sha256,help_sha256,required_flags}` against
`config.claude_{version,executable_sha256,help_sha256,required_flags}`, BEFORE anything
that spends. And make `current_claude()` MEASURE the installed binary (or have `plan`/
`record` cross-check the literal against it) so a stale constant is a plan-time refusal
instead of a post-payment one.

## COVERAGE
REACHED AND ANALYSED: all 229 open issue bodies (filtered title+body -> 164 candidates;
read in full: #332 #334 #389 #397 #409 #417 #426 #429 #452 #455 #456 #457 #464);
`graphify_semantic_corpus.py` (constants, verify_plan, `_provider_*` validators, stage_chunk,
cost/timeout rationale), `graphify_semantic_corpus_run.py` (execute, the two identity
assertions, the chunk loop, spend cap), `graphify_semantic_slice.py` (`current_claude`,
`preflight`, `_runtime_reasons`, `_receipt_reasons`, the runtime/claude constants,
`scrub_route_overrides`), `graphify_semantic_corpus_record.py` (via the live dry run),
`graphify_semantic_corpus_merge.py` (module docstring + graph.json probe),
`graphify_semantic_corpus_authority.py` (entry index, the cost and effort entries),
`graphify_semantic_corpus_prototype.py` (header + reachability), `graphify_semantic_adapter.py`
(`_real_executable`), `cli.py` (both usage literals + dispatch), `mise.toml` corpus tasks,
all six plan artifacts + the slice's real provider evidence, and the pinned `sources/graphify`
clone. Ran live: corpus `verify`, corpus `record` (dry), `claude --version`, the semantic
fingerprint, `route_override_names`/`scrub_route_overrides` both arms.

OPENED BUT NOT FINISHED: `graphify_semantic_corpus_authority.py` — I read its entry INDEX
(19 dated entries) and 4 entries in full; I did NOT read the other 15, so an authorization
condition recorded only in one of those is unaudited. `graphify_semantic_corpus.py` is 3,693
lines; I read ~600 of them targeted at the run path — the exclusion/inventory/dedupe logic
(#414's dup-grouping, `_INTENTIONAL_EXCLUSIONS`) is UNREAD. `graphify_semantic_corpus_prototype.py`
— header and reachability only, its 465 lines of launcher logic unread.

NEVER REACHED: `graphify_semantic_corpus_merge.py` beyond its docstring (its refusal
conditions are unverified, so I cannot say the merge step would accept a good run's output);
the test suite (I ran no tests, so every "unarmed" claim about #332/#464 is inherited, not
re-derived); `graphify_baseline.py` (76 KB) and `graphify_sdk.py` (54 KB); the 65 candidate
issues I filtered in but did not open; the 65 open issues outside the candidate filter.

CLAIMS I COULD NOT ARM: (1) that the run WOULD stage 26/26 failed — no corpus run has ever
reached a provider (control-armed against the slice's real evidence), so this is INFERENCE
from `_provider_runtime_reasons` + `_dispose`, not observation. (2) The $74.41 re-derived cap —
arithmetic on a rate measured ONCE (n=1, `charges:1`), so it has no noise floor. (3) The
proxy-refusal blocker — armed on synthetic dicts, not on a proxied host. (4) Whether the
merge step would accept a good run's output — unread.
