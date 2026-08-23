# Lane: extraction-readiness — 2026-08-23 session review

Reporting at **HEAD `24d11e49c946e13a9ff1f610d3ab1ac7f8d3abd4`**, branch
`claude-resync-2.1.241`, tree clean at lane start (`git status --short` empty).

## Sweep completeness (proved, not asserted)

- `gh issue list --state open --limit 1000 --json number --jq length` -> **231**
- `gh issue list --state open --limit 1000 --json number,title,body | jq length` -> **231**
- Neither equals the bound (1000). Sweep is WHOLE. Filtering is done on BODIES.

## THE HEADLINE — the L7 honest bound has FLIPPED

The 2026-08-21/22 lanes had to say "no artifact exists; every claim is inference
from source". **That is no longer true.** A run reached a provider under the
CURRENT pin and left artifacts on disk:

- `graphify-out/graphify-semantic-corpus-chunks/9e1adc3b.../spend-ledger.json`
  -> `jq '.charges|length'` = **45 charges**, `total_usd` (below).
- 26 chunk dirs `chunks/0001..0026`, each with
  `adapter-metadata.json`, `provider-receipt.json`, `receipt.json`,
  `semantic-fragment.json` (105 files total, `find ... -type f | wc -l`).

So this lane's findings split into OBSERVATION (read off the run's own
artifacts) and INFERENCE (read off source for the NEXT run). Each is labelled.

## A. Can the run start / does it produce nothing?

### A1 (OBSERVED, UNFILED, cost_rank 1) — a third pass is arithmetically capped out before it can reach chunk 0026

Measured, all four numbers re-derived at HEAD `24d11e49c946`:

| fact | command / file |
|---|---|
| cumulative spend on this plan | `jq .total_usd .../spend-ledger.json` = **41.77706500000001** |
| charges | `jq .charges` = **45** |
| the cap | `jq -r .max_total_cost_usd graphify-out/graphify-semantic-corpus/execution-config.json` = **63.0** |
| chunks staged complete / failed | 24 complete, **0012 + 0026 failed** (per-chunk `receipt.json .status`) |

The cap is **cumulative and durable**: `_Spend.__init__`
(`graphify_semantic_corpus_run.py:204-217`) seeds `total_usd` from the on-disk
ledger via `read_spend_ledger_record`, and `seeded_spend`
(`:247-272`) refuses only when `carried_usd > limit`. Headroom is therefore
**$63.00 − $41.78 = $21.22**.

A resumed pass does NOT get the already-staged chunks for free.
`RunSummary.repaid` (`:98-107`) says so in its own comment — *"Staged by an
earlier run, verified as that chunk's real evidence, and **PAID FOR AGAIN** this
pass"* — because the skip happens in `on_chunk_done`, downstream of the provider
call (`:22-33`), and `extract_corpus_parallel` performs **no cache read** at the
pin (`graphify_semantic_corpus.py:915-926`).

So a third pass re-buys all 26 chunks. At this run's own measured rate
($41.777 / 44 charges ≈ $0.95/charge; the round's stated $0.948/chunk agrees),
26 chunks ≈ **$24.7 > $21.22**. The cap fires *after* the chunk that crossed it
(`:1244`), so the run aborts around chunk **~22 of 26** — it WOULD retry chunk
0012 (reached at ≈ $11.4 into the pass), and would **never reach chunk 0026**,
the other failure. Net effect of a third pass on the same plan: ~$21 spent,
0 new chunks published, one of the two known failures still unattempted.

**This is the finding that decides scheduling**, and it is not in any issue.
#456 ("restart path is a trap") is the nearest, but it is written about a cap
that *refuses past chunk 31* on the pre-dedupe 58-chunk plan — a different
arithmetic and a different plan. PARTIAL at best.

Remedy (mechanical, not "remember"): the run needs a **pre-flight cost
projection** — `remaining_chunks × observed_mean_charge` vs `limit − carried`,
printed and *refused* before the first provider call, the same shape
`seeded_spend`'s already-exceeded refusal has. Today the only guard is the
already-exceeded one, which cannot see a pass that will exceed.

### A2 (OBSERVED) — `verify` now returns authorized, and the Claude-identity window IS closed

`uv run kb-setup graphify-semantic-corpus verify` -> rc=0,
`{"execution_authorized":true,"reasons":[],"state":"complete","structural_complete":true}`.

The 2026-08-22 P1 (Claude identity compared post-hoc per chunk, so a run would
spend the cap staging 26/26 failed) is **closed in code**:
`graphify_semantic_corpus_run.py:1164-1165` calls
`_assert_graphify_runtime_unchanged_since_plan` AND
`_assert_claude_identity_matches_plan` under the comment *"BEFORE anything that
spends. BOTH halves"*. Control arm for the probe: the same grep finds only ONE
call site each, and the file's own line 1162 records that the Claude half "was
post-hoc until #426's other half closed it".

Digest cross-check (observation, re-derived not inherited):
`sha256(python/src/kb_setup/graphify_semantic_slice.py)` =
`76a0aa8731a1da66a34cb452cc4a5f1a4c55c02cb448a7988c84377c50206cd3`, which is
byte-identical to `execution-config.json.semantic_slice_sha256`. The plan on
disk describes the code on disk.

## C. Provenance — what the run records about ITSELF

### C1 (OBSERVED, CLOSED) — the `--effort` gap the brief names is FIXED. Do not re-report it.

Re-derived at HEAD, not inherited. `execution-config.json` carries a top-level
**`"effort":"high"`** field (`jq -r '.effort'` -> `high`), and every chunk's
`adapter-metadata.json.argv` ends `... --max-turns 3 --effort high`.
Control arm: `jq -r '.no_such_field_xyz // "ABSENT"'` on the same file returns
ABSENT, so the probe discriminates between present and missing.

The 2026-08-21/22 statement *"`--effort` appears only as a flag NAME in
`claude_required_flags`, while its VALUE is in no field at all"* is **stale**.
Any lane repeating it is repeating an inherited number.

Also recorded per chunk and re-derived: `claude_version` = `2.1.241 (Claude Code)`
on all 26, `model_usage[0].canonical_model` = `claude-opus-5`,
`provider` = `firstParty`, plus cache-creation/read token counts.

### C2 (OBSERVED, ~UNFILED, cost_rank 2) — 40.7% of the run's money has no surviving artifact

| measure | value | how |
|---|---|---|
| sum of the 26 chunks' `adapter-metadata.json.total_cost_usd` | **$24.756518** | python sum over `chunks/*/adapter-metadata.json` |
| `spend-ledger.json.total_usd` | **$41.777065** | `jq .total_usd` |
| **unattributed** | **$17.020547 (40.7%)** | difference |
| charges with no surviving adapter-metadata | **19 of 45** | `charges - 26` |

Two mechanisms, both in the code:

1. `stage_chunk` refuses an occupied destination
   (`graphify_semantic_corpus_run.py:22-27`), so a **repaid** chunk's second
   provider call is charged and then writes nothing — its metadata never lands.
2. `SpendLedger` is `{total_usd, charges, schema_version}` only
   (`:143-152`; confirmed on disk: `jq keys` -> `["charges","schema_version","total_usd"]`).
   **There are no per-charge rows.** Cost cannot be attributed to a chunk, a
   source file, a pass, or a retry.

Consequence for the next round: the round's own cost narrative ("Pass 1: 20/6,
$20.86; Pass 2: 4/18/4, $20.91") exists ONLY in the transcript. Nothing on disk
can reproduce it. That is exactly the class this repo calls an inherited number.

Also: **every chunk records `attempt: 1`**, including both failures — so the
retry history is invisible in the artifacts too.

Nearest ticket: **#411** ("extraction provenance: record model/effort per FILE
per source, keyed on content hash") — but #411 is about model/effort, which C1
shows is now recorded. **Spend attribution is a DIFFERENT gap and is UNFILED.**

Remedy: make `SpendLedger.charges` a list of records
(`{ordinal, pass, attempt, usd, at, staged: bool}`) appended per charge, not a
counter. It is the same file, the same `_persist()` call site
(`graphify_semantic_corpus_run.py:224-240`) — one struct change.

### C3 (OBSERVED, UNFILED, cost_rank 3) — there is no verb that reports how a RUN went

`corpus_main` accepts exactly `{plan, run, verify}`
(`graphify_semantic_corpus.py:3635`), plus `record` routed separately at
`cli.py:251-255`. `verify` calls **`verify_plan`**, whose docstring says
*"Rehash and cross-check a **plan**"* (`:2117-2137`) — it never looks at the
staged chunks.

So after a run in which 2 of 26 chunks FAILED, `verify` prints
`{"execution_authorized":true,"state":"complete","structural_complete":true}`
and exits 0. A reader reasonably takes "complete" as "the run completed". It
means "the plan is completely authorized".

I had to reconstruct 24-complete/2-failed by walking
`chunks/*/receipt.json` by hand. Remedy: a `status` verb over the run namespace
printing completed / repaid / failed / never-attempted plus per-chunk reasons —
`verify_staged_chunk` (`:2809`) already does every check it would need; nothing
calls it from a reporting path.

## B. It completes, but the result is wrong / lossy / unresumable

### B1 (OBSERVED) — the plan on disk IS the recorded authority, digest for digest

`shasum -a 256` over the four plan members vs
`python/src/kb_setup/graphify_semantic_corpus_authority.json`:

| member | on disk | recorded |
|---|---|---|
| manifest.json | 2c3c4b18bb3f… | 2c3c4b18bb3f… |
| execution-config.json | ae739131018c… | ae739131018c… |
| advisories.json | ff7323b19217… | ff7323b19217… |
| exclusions.json | 1a63e48336f7… | 1a63e48336f7… |

All four match. There is no pending re-record. (Closes the "ninth record" item.)

### B2 (OBSERVED, refutes #458's premise) — the 900s ceiling has **2.54x** headroom at effort high, not 1.36x

#458 is OPEN and says *"only 1.36x headroom over a measurement taken WITHOUT
`--effort high`"*. Measured from the 26 real chunks' `adapter-metadata.json`:

- ceiling `execution-config.json.timeout_seconds` = **900**
- worst chunk = **0005, elapsed 354.4 s** (turns 2, 44,241 output tokens)
- **headroom = 900 / 354.4 = 2.54x**
- mean 214.8 s; total serial provider wall = **1.55 h** (the plan projected ~4.8 h)

No chunk came near the ceiling and none failed on time. **#458's specific
worry is refuted by observation** and the issue should be re-scoped or closed
with this data attached rather than carried a seventh round.

### B3 (OBSERVED, refutes #426) — the 0.9.47/58-chunk P0 no longer describes anything

#426 is OPEN and predicts *"the run would burn ~$65 and stage 58/58 chunks
failed"*. The run staged **24/26 complete** at graphify **0.9.48**
(`execution-config.json.graphify_version`, `graphify_runtime.cli_version`) for
$41.78. Stale-open. Close it with the artifact.

### B4 (OBSERVED, LIVE) — the two failures are content-shaped and will recur on re-run

Chunks 0012 and 0026 both failed with
`["fragment-source-scope-mismatch","fragment-source-coverage-mismatch"]`
(`jq .reasons chunks/0012/receipt.json`). Both spent full price
($0.6134 and $0.6450 — `adapter-metadata.json.total_cost_usd`) and both record
`attempt: 1`.

A retry runs the **same prompt over the same bytes**, so nothing about a third
pass makes them more likely to pass. The round's own fix (17623a32, merge-module
only) bins-and-records them at MERGE time instead — which is the correct layer,
and it means **there is no reason to run a third pass at all**. Combined with
A1 (a third pass is capped out anyway), the schedule should be:
`kb-graphify-semantic-corpus-merge -- <name> --partial`, never `run` again.

`--partial` is required: `assemble` refuses `len(accepted) != planned_total`
unless `allow_partial` (`graphify_semantic_corpus_merge.py:567`).

### B5 (INFERENCE from code, NOT run) — the ASSEMBLE step is not blocked by `kb-build` being red

The two are commonly scheduled as one and are not one:

- `assemble` writes **`sources/extractions/<name>-docs.json`**
  (`graphify_semantic_corpus_merge.py:9`) — a tracked file. It reads staged
  chunks and the plan. It never touches `graphify-out/graph.json`.
- `mise run kb-merge -- <chunk>` merges that chunk **into the existing
  `graph.json`** (`graphify_ops.py:207-237`) and re-derives the prose graph. It
  does **not** require a `kb-build`.
- `mise run kb-build` is what is RED, and it blocks **reproducing the graph from
  committed inputs** — the `verify-before-advancing.md` reproducibility gate —
  not the merge.

I did NOT execute the merge (a review lane must not mutate the corpus), so B5 is
inference from those file:line anchors, not observation.

### B6 (OBSERVED, re-derived) — the CURRENT `kb-build` blocker is a ONE-ENTRY fix, not #409's scaling problem

`graphify-out/.build-failure.json` (failed_at 2026-08-23T16:13:45Z):
`unaccounted_stderr='warning: 1 file(s) had syntax errors ... .agent/skills/blocking-io-guard/templates/anchor.template.py (first error at line 1, no symbols extracted)'`.

Re-derived, all three legs:

1. The file is **`sources/deer-flow/.agent/skills/blocking-io-guard/templates/anchor.template.py`**
   (`find sources -path '*blocking-io-guard*' -name anchor.template.py`). It is
   NOT this repo's `.agent/` — `ls .agent/skills/` -> *No such file or directory*.
2. graphify's *"first error at line 1"* is **wrong**. `ast.parse` gives
   `SyntaxError lineno=23 msg="expected '('"`; line 23 is
   `async def test_<entry_point>_offloads_blocking_io_on_<branch>(...)`. The file
   is a template, invalid Python by design.
3. It is **not yet registered**. `git grep -c 'anchor.template' -- python/src/kb_setup/graph.py` -> 0.
   Control arm: the same grep for `malformed.py` (a file I know IS registered) -> **5**.
   The probe discriminates.

Re-derived inventory sizes at HEAD (both are inherited numbers in #409's body,
and both are stale): `_EXPECTED_PARTIAL_EXTRACTION` now holds **5** entries,
not 1; the metadata-only inventory holds **13**, not 12
(`grep -c 'ExpectedPartialExtraction(' / 'MetadataOnlyFile('` in `graph.py`).

So this blocker is one `ExpectedPartialExtraction` entry — expressible today,
because it is the SINGLE-file form. #409's real problem (the comma-joined
multi-file form, GitNexus's 94 entries) is a **different** source and does not
gate this one. **#409: read in full, still LIVE, but it does not block the
current build failure.**

## A (continued) — a run-cannot-START condition that is UNFILED

### A3 (OBSERVED, UNFILED, cost_rank 4) — a proxied shell refuses the run, and the automatic scrub deliberately will not clear it

Armed both directions in-process:

```
route_override_names({"HTTPS_PROXY":..,"AWS_REGION":..,"PATH":..})
  -> ('AWS_REGION', 'HTTPS_PROXY')
scrub_route_overrides(same)          -> removed ('AWS_REGION',)
route_override_names(after scrub)    -> ('HTTPS_PROXY',)     # SURVIVES
CONTROL ARM, clean env {"PATH":..}   -> present () / removed ()
```

`preflight` then raises
`ValueError("forbidden routing environment names: …")`
(`graphify_semantic_slice.py:1056-1058`) on **all 37** names, proxies included,
while `scrub_route_overrides` excludes the four proxy names by design
(`:889`, `_ROUTE_OVERRIDE_PROXY_NAMES`, cold-review P2-4 — stripping them from
the parent would change what `git` and the graphify SDK's `trust_env=True`
httpx client do).

So on any host carrying `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` / **`NO_PROXY`**
— the last is set by Docker, corporate VPNs and many shells as a matter of
course — **`run` refuses before the first chunk**, and the mechanism #334 built
to stop the operator hand-scrubbing does not apply. It fails SAFE (no money
lost), but it is a start-blocker with a hand remedy.

`.agent/plans/session-2026-08-23-c.md:95` records this as
*"The proxy refusal, unfiled … **CARRIED, still unfiled**"*. **This is a
deferral inside the reviewed window, so it is my scope, and it is still open.**

Remedy: `preflight` should either (a) accept the four proxy names it knows the
scrub will never remove, or (b) refuse with a message that names `env -u` and
the four exact variables. Today it names all 37 in one string with no hint that
four of them are unremovable by the tool.

## D. Scope and follow-on

### D1 (OBSERVED, #429 LIVE, cost_rank 5) — the corpus verbs have no hook redirect, and the bypass loses the 16h leash

Control-armed with `kb_setup.hook_guard.decide`:

| command | verdict |
|---|---|
| `uv run kb-setup graphify-semantic-corpus run` | **None** (allowed) |
| `uv run kb-setup graphify-semantic-corpus-merge foo` | **None** |
| `uv run kb-setup graphify-semantic-slice verify` | **None** |
| `graphify extract .` *(control)* | redirected to `mise run kb-build` |
| `graphify path A B` *(control)* | None — correctly allowed |

The probe discriminates. **#429 is LIVE.**

The cost is concrete and composes with `long-running-command-hangs.md`:
`mise.toml:713-729` puts `timeout = "16h"` on `[tasks.kb-graphify-semantic-corpus]`
and says in its own comment that it is *"a wall-clock hang guard"*. The bare
`uv run kb-setup graphify-semantic-corpus run` form has **no leash at all**, and
nothing stops anyone typing it. **I typed it myself this lane** (for `verify`,
which is provider-free) without any guard objecting — which is the lived
instance of the gap, not a hypothetical.

### D2 — issues that are STALE-OPEN and should be closed with this run's artifacts

| # | claim | status re-derived at HEAD |
|---|---|---|
| **#426** | *"P0 … would burn ~$65 and stage 58/58 chunks failed"* | **REFUTED.** 24/26 staged at 0.9.48 for $41.78 |
| **#458** | *"only 1.36x headroom … WITHOUT `--effort high`"* | **REFUTED.** 2.54x measured AT effort high (max chunk 354.4 s / 900 s) |
| **#334** | *"requires the operator to scrub ambient `AWS_*` by hand"* | **FIXED in code** — `scrub_route_overrides` is called on the execute path at `graphify_semantic_corpus_run.py:1154`. Stale-open. But see **A3**: the proxy family it excludes is a NEW, unfiled instance of the same complaint |
| **#411** | *"record model/effort per FILE per source"* | **PARTLY FIXED** — `effort`, `claude_model`, `claude_version`, `model_usage[].canonical_model` all now recorded per chunk (C1). What is still missing is the FILE-level keying and **spend attribution (C2)** |
| **#332** | *"arm the `attempts=provider_calls` wiring with a real staged chunk"* | **NOW ARMABLE, and the data looks wrong**: all 26 chunks record `attempt: 1`, including the two that failed and the ones re-bought on pass 2 |

### D3 — carried deferrals inside the window that are MINE, not out of scope

From `.agent/plans/session-2026-08-23-c.md`:

- **`#417` register (sources set to `build = skip`)** — `:81` *"CARRIED, untouched"*. Still open. Re-measured: **5 of 73** manifests carry `build = skip` (`codex`, `codegraph`, `colibri`, `codebase-memory-mcp`, `GitNexus`). Control arm: only 5 manifests have a `build` key at all, so the probe found every one.
- **The proxy refusal** — `:95` *"CARRIED, still unfiled"* -> now armed as **A3** above.
- **`#464`'s graphify-half message nit** — `:94` *"CARRIED"*, run-module still prints structs rather than version strings.

### D4 — #409 read in full (coverage debt closed)

Read end to end. It is the primary ticket for **GitNexus** (`scope = study`,
79 zero-node + 15 partially-extracted files) and proposes three unchosen
options, of which *"give `kb-build` a `--group`/`--scope` flag"* is the one that
would stop one study repo blocking all 73 sources. **Still LIVE.** But it does
NOT gate today's build failure (B6), and it does not gate the corpus run at all
— the corpus run reads only the pinned graphify clone.

## Coverage debt inherited from 2026-08-21 — each one, explicitly

- **`graphify_semantic_corpus_authority.py`** — **REACHED AND READ.** 663 lines,
  of which the executable surface is 4 lines: two `PROTOTYPE_*` digests, a
  `Path(__file__).with_name(...)`, and a `read_bytes()` that raises
  `RuntimeError` if the sibling JSON is missing (`:660-663`). Everything else is
  the review narrative. The four authority digests live in
  `graphify_semantic_corpus_authority.json` and **match the plan on disk
  byte-for-byte** (B1).
- **`graphify_semantic_corpus_prototype.py`** — **REACHED AND READ.** 465 lines.
  Control-armed reachability: `git grep graphify_semantic_corpus_prototype`
  finds **zero** references in `cli.py`, in the run driver, or in any mise task
  (control: the same grep for `graphify_semantic_corpus_merge` in `cli.py` -> 2).
  Its only non-test consumer is a COMMENT at
  `graphify_semantic_corpus.py:2123`. It is reachable **only from
  `tests/test_graphify_semantic_corpus.py`**, it is not digested into
  `execution-config.json`, and it imports graphify PRIVATES
  (`from graphify.llm import FileSlice, _extraction_system, _read_files`).
  Finding: 465 lines of #301 prototype launcher that no operator path can
  invoke — dead-by-construction relative to the run, and unpinned by the plan
  that pins everything else. UNFILED.
- **`_receipt_reasons` / `_runtime_reasons`** — **REACHED AND READ.**
  Found by NAME at the reported sha:
  `git grep -n 'def _receipt_reasons\|def _runtime_reasons' HEAD -- python/src/kb_setup/graphify_semantic_slice.py`
  -> `_runtime_reasons` at **:1509**, `_receipt_reasons` at **:1602**. The
  brief's own carried range (`:1461` / `:1368`, and before that `:1356-1410`)
  has drifted a THIRD time, and the two functions have swapped order. Tree was
  clean on that file (`git status --short python/src/kb_setup/` -> empty), so
  HEAD and the worktree agree. Audit: `_receipt_reasons` runs 18 equality
  checks then delegates to `_runtime_reasons`' 10 more; the version half of the
  graphify pair is DERIVED from the runtime half (`:1541-1546`) rather than
  restated, which is the fix for the twice-recurring literal drift the comment
  documents. No defect found in either. **One structural note:** every check is
  an EQUALITY against a module-level frozen constant, so #455's complaint
  (`backend == "claude-cli"` is exact) is the general shape of this whole
  verifier, not one line.
- **Issue #409** — **READ IN FULL** (D4).

## Untrusted input — what the issue bodies actually tried

231 open issue bodies scanned mechanically for injection shapes
(`ignore (previous|prior|your) instructions`, `disregard`, `you are now`,
`system prompt`, `new instructions`, `curl … | sh`, `exfiltrat`,
`send the results to`). **Two hits, both benign false positives:**

- **#213** — `"[kb-land] merged. You are now on \`main\`"` — quoted CLI output.
- **#118** — `"some subagent cost is fixed per file (system prompt, …)"` — a cost model.

Control arm: the same `jq test()` shape for `mise run kb-build` returns **9**
issues, so the scan discriminates.

**No issue body attempted to instruct me.** Note the reason, because it is not a
property of the control: `gh issue list --json author` shows all **231** open
issues authored by a single account (`sortakool`). The repo is public, so the
surface is real and **#460 stays LIVE** — today's clean result is an accident of
authorship, not evidence the control is unnecessary.

## Observation vs inference — the honest bound (L7)

**OBSERVED** (read off artifacts produced by a real run at the current pin):
A1's four numbers, A2's `verify` output, A3's env probe, B1's digest table,
B2's timings, B3's outcome, B4's failure reasons, B6's syntax-error line,
C1, C2, D1's guard verdicts, and every issue-state re-derivation.

**INFERENCE from source, not run:** B5 (that assemble/merge are unblocked by the
red build) — I read `graphify_semantic_corpus_merge.py:9` and
`graphify_ops.py:207-237` but did NOT execute either, because a review lane must
not mutate the corpus. A1's *projection* of where a third pass aborts (~chunk 22)
is arithmetic over observed numbers, not an observation.

**What I did NOT establish:** that fixing A1/A3 makes a re-run succeed.
Establishing that a run will fail is not establishing that the fixes are
sufficient. B4 in particular says the two failing chunks fail on CONTENT, which
no scheduling fix touches.

## COVERAGE

**Reached and analysed.** All 231 open issues enumerated and body-filtered
(count 231 == fetch 231, neither at the 1000 bound; title-only would have given
35 vs 112 on the body filter — L2 re-confirmed). Read in full: #409, #426, #455,
#456, #457, #458, #334, #332, #429, #417, #464, #460 (titles + relevant bodies).
Ray's directive `docs/direction/2026-08-22-ray-directives.md` read in full.
`.agent/plans/session-2026-08-23-c.md` read for carried items. Modules read:
`graphify_semantic_corpus_authority.py` (all), `graphify_semantic_corpus_prototype.py`
(head + reachability), `graphify_semantic_slice.py` `_runtime_reasons`/`_receipt_reasons`
/`_chunk_reasons`/`scrub_route_overrides`/`route_override_names`,
`graphify_semantic_corpus.py` `verify_plan`/`corpus_main`/`_effective_config`/
the graphify import block, `graphify_semantic_corpus_run.py` `_Spend`/`seeded_spend`/
`_verified_stages`/`_run_namespace`/`RunSummary`/`execute`'s preflight block,
`graphify_semantic_corpus_merge.py` `merge_main`/`assemble` gating,
`graphify_ops.py` `merge_chunk`, `graph.py` `_EXPECTED_PARTIAL_EXTRACTION`,
`hook_guard.decide` (via live probe), `mise.toml:695-735`, `cli.py:251-262`.
Artifacts read: all 26 chunks' `receipt.json` + `adapter-metadata.json`,
`spend-ledger.json`, `execution-config.json`, `graphify_semantic_corpus_authority.json`,
`.build-failure.json`. Commands run: `verify` (rc 0), `kb-currency-check`,
one `kb-query --prose`.

**Opened but NOT finished analysing.**
`graphify_semantic_corpus_prototype.py` — read its docstring, imports and
reachability, NOT its 465 lines of logic; I can say nothing about whether its
`prepare_authorized_prototype` / `_probe_runtime` paths are correct.
`graphify_semantic_corpus.py` — 3,693 lines; I read ~6 functions. `_cross_reasons`,
`_source_reasons`, `_advisory_reasons`, `verify_staged_chunk`, `stage_chunk` and
the whole dedupe/#414 path are **unread**. `graphify_semantic_adapter.py` (1,058
lines) — **entirely unread**. `graphify_semantic_corpus_record.py` (690 lines) —
**entirely unread**. `graphify_semantic_corpus_merge.py` — only `merge_main` and
the `allow_partial` gate; the scope-sanitisation code the round shipped as
17623a32 is **unread**, so I cannot confirm it bins chunks 0012/0026 correctly.

**Never reached at all.** The 119 open issues outside the 112-issue body filter
were never opened individually (their titles were listed by the sweep, nothing
more). Of the 112, I opened ~12. `tests/test_graphify_semantic_corpus.py` — not
opened, so every "no defect found" above is unarmed by its own test suite. I ran
NO mutation arm on anything. `sources/graphify/` — the actual corpus source tree
— was never inspected, so I cannot speak to whether the 24 staged fragments are
semantically good, only that they verified structurally.

**Claims I could not arm.** B5 (merge/assemble unblocked) — inference only.
A1's abort point (~chunk 22 of 26) — arithmetic, never executed. The claim that
chunks 0012/0026 fail on content and would fail again — reasoned from the
identical `reasons` pair on two independent chunks plus the round's own diagnosis;
I did not re-run either chunk. Whether `attempt: 1` on a re-bought chunk is a
DEFECT or correct-by-definition (#332) — I found the data, not the intended
semantics.
