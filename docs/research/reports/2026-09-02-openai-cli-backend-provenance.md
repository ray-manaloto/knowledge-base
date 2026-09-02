# OpenAI CLI backend switching, semantic-cache identity, and provenance

- **Date:** 2026-09-02
- **Branch under study:** `kb-pin/openai-cli-backend-v0.9.53` at `157a957e89a16246bba3a078de2777711ee85e31` (`v0.9.53-8-g157a957`)
- **Author lane:** consolidated research synthesis
- **Scope:** `ray-manaloto/knowledge-base` and its pinned Graphify fork
- **Status:** advisory only — no code changed
- **Network:** no network; live upstream state COULD NOT CHECK (no network)
- **How this was produced:** five lane reports on disk (session review, agentsview status, goal reconstruction, corpus provenance, fork-vs-upstream) plus a cached 200-issue / 80-upstream-title GitHub snapshot, resolved against each other and against a fresh read of the fork clone. The synthesis reasoning ran in `codex exec` (`gpt-5.6-sol`, `xhigh`, `--sandbox read-only`, rc 0, session `01a06310-ffb3-7871-9ef0-c8486363ccea`); the evidence was gathered and control-armed in the repo shell before the consult. Working notes: `.agent/kb/reports/agents/lane-i-consolidation.md`.

## 1. THE GOAL

Owner-supplied goal, verbatim:

> “the goal was to be able to switch backends from claude-cli or openai-cli with the ability to track which agent model created graphify data so we can reliably understand what is happening and verify and validate if we can switch the backends even on existing extractions. for example switching from claude-cli backend to openai-cli backend on graphify sources that were already extracted (and vice versa)”

That goal has four separable parts:

| Part | Required outcome | Current blocker |
|---|---|---|
| Select either backend | A run can explicitly select `claude-cli` or `openai-cli`. | Primary routing exists: `corpus_kwargs` receives `backend` and a primary-only `model` at `graphify/cli.py:3977-3983`. Reliable switching is blocked by the backend-blind cache, whose read key is only kind, prompt fingerprint, and content hash at `graphify/cache.py:926`, `graphify/cache.py:958`, and `graphify/cache.py:1000`. |
| Attribute produced data | Persist the actual backend and model responsible for each semantic result. | Export persists only `built_at_commit` at `graphify/export.py:405-407`; `graphify/export.py` contains zero `backend` and zero whole-word `model` occurrences, control: `built_at_commit` occurs three times. The actual execution backend is assigned to `_last_backend` at `graphify/cli.py:4030` and `graphify/cli.py:4043`, then used only in an error message at `graphify/cli.py:4052`. |
| Switch on already-extracted sources | A second backend can produce a separate variant, and switching back can reuse the first backend’s variant. | The cache can hold only one unattributed semantic entry for a given kind, prompt fingerprint, and content hash (`graphify/cache.py:940-945`, `graphify/cache.py:1000`, `graphify/cache.py:1117`). `--force` skips the read but overwrites that same entry at `graphify/cli.py:3941-3946`; it cannot preserve an A/B baseline. |
| Verify and validate the switch | Evidence must distinguish cache reuse, primary execution, and fallback execution, including the resolved model. | `check_semantic_cache` and `save_semantic_cache` accept no backend or model at `graphify/cache.py:1233-1240` and `graphify/cache.py:1379-1391`. Fallback deliberately does not reuse the primary `--model` and instead runs its own default at `graphify/cli.py:3979-3982`, while no artifact records that model. |

The current composed corpus is not evidence that backend switching has worked. INHERITED measurement: zero of 359,026 nodes came from Graphify semantic `--backend` extraction; 347,696 came from AST extraction and 11,330 came from the separate Claude host-agent `kb-extract` fan-out (`graphify-out/.compose-manifest.json`, `graphify-out/build-receipt.json`). The feature is therefore a future-facing correctness blocker here, not a demonstrated corruption of the current composed graph.

## 2. WHAT IS ALREADY TRUE

### Works

| Capability or fact | Evidence |
|---|---|
| The pinned fork contains an explicit `openai-cli` backend and is based on Graphify 0.9.53. | Git ref `kb-pin/openai-cli-backend-v0.9.53@157a957e89a16246bba3a078de2777711ee85e31`; `git describe --tags HEAD` → `v0.9.53-8-g157a957`. |
| Primary backend selection reaches semantic corpus extraction. | `graphify/cli.py:3977-3983` constructs `corpus_kwargs` with `backend`, primary `model`, `root`, and `cache_root`. |
| A second backend can be attempted after a total zero-success primary pass. | `graphify/cli.py:4024-4043`; fork commits `a4842b4` and `025a24f`. Runtime use in this repository is UNVERIFIED because the wrapper cannot forward the flag. |
| Semantic caching already separates shallow/deep kinds and prompt variants. | Kind namespace at `graphify/cache.py:926`; prompt fingerprint at `graphify/cache.py:100`, `graphify/cache.py:123`, and `graphify/cache.py:1117`; content SHA256 at `graphify/cache.py:958`. |
| `built_at_commit` is anchored to the repository receiving `graphify-out`, not the shell’s current directory. | `graphify/export.py:400-407`. This corrects the older diagnosis associated with upstream #2081/#2534 on the 0.9.53 base. |
| The composed corpus has a reproducible green receipt on 0.9.53. | `graphify-out/.compose-manifest.json`; `graphify-out/build-receipt.json`, dated 2026-09-02. |
| The graph query discriminates and returns documentation about backends and semantic caching. | `mise run kb-query -- "graphify openai-cli backend semantic cache key provenance which model produced extraction" --prose --idf` → 11,330 indexed nodes and 3,524 scoring above zero. The result is documentation-level evidence, not execution provenance. |
| Actual primary-versus-fallback backend identity is already known transiently after execution. | `_last_backend = backend` at `graphify/cli.py:4030`; `_last_backend = fallback_backend` at `graphify/cli.py:4043`. |

### Missing

| Missing capability | Evidence |
|---|---|
| Backend-aware cache identity | `grep -c backend graphify/cache.py` → 0; control: `grep -c hashlib graphify/cache.py` → 3. The key paths are `graphify/cache.py:926`, `graphify/cache.py:958`, `graphify/cache.py:1000`, and `graphify/cache.py:1117`. |
| A cache API through which a caller can provide producer identity | `check_semantic_cache(...)` has no backend/model parameter at `graphify/cache.py:1233-1240`; `save_semantic_cache(...)` has none at `graphify/cache.py:1379-1391`. |
| Backend and model in `graph.json` | `graphify/export.py` has zero `backend` and zero whole-word `model` occurrences; its sole provenance stamp is `built_at_commit` at `graphify/export.py:405-407`. |
| Requested-versus-actual execution identity | The actual backend is discarded after `graphify/cli.py:4030-4052`; fallback uses a different default model at `graphify/cli.py:3979-3982`. |
| Multiple backend/model variants for one source and prompt | Both reads and writes resolve to the same backend-blind path at `graphify/cache.py:1000` and `graphify/cache.py:1117`. |
| Wrapper support for `--fallback-backend` | The closed `_VALUE_FLAGS` allowlist contains only six value flags at `python/src/kb_setup/graphify_native_extract.py:409-416`; `--fallback-backend` is absent. INHERITED census: zero operational occurrences of `fallback.backend|fallback_backend`, control: 26 `--backend` occurrences across `python/` and `mise.toml`. |
| An explicit openai-cli model at the repo boundary | The fork has a model setting, but application through `kb_setup` was not confirmed; `python/src/kb_setup/graphify_native_extract.py:409-416` only establishes that `--model` can be forwarded. |
| Durable per-call execution receipts | The former receipts survive only in gitignored scratch under `graphify-out/graphify-semantic-slice/` and `graphify-out/graphify-semantic-corpus/`; the layer was removed through `docs/archive/README.md`, `do-not.md` #5. |
| Historical model attribution for the 29 committed host-agent chunks | `sources/extractions/` records token counts but no model. Its measured key vocabulary contains no backend/model field. Per-node attribution is permanently lost; session-level inference remains UNVERIFIED/INHERITED. |
| Queryable provenance through memory | `graphify-out/memory/` contains 271 committed files but contributes zero prose-graph nodes; issue #540. |

### Silently wrong

These are successful operations or artifacts whose apparent meaning differs from their actual meaning.

| Behavior | Why the successful result is misleading | Evidence |
|---|---|---|
| Selecting backend B after backend A has cached the same source | A successful cache hit can be presented as backend B’s result even though backend B never ran. The entry contains no producer identity. Whether upstream #2314 makes this latent in this configuration is UNVERIFIED. | `graphify/cache.py:958`, `graphify/cache.py:1000`, `graphify/cache.py:1117`; issue #518. |
| Using `--force` as the backend-switch escape hatch | The requested backend does run, but its result replaces backend A’s cache entry in place. The command destroys the comparison baseline and forces another paid extraction to switch back. | Verbatim behavior comment at `graphify/cli.py:3941-3946`; common write target at `graphify/cache.py:1117`. |
| Falling back after the primary backend produces zero successes | The successful result was produced by `fallback_backend` using that backend’s default model, but neither actual backend nor model is persisted. A stamp copied from the requested backend would lie. | `graphify/cli.py:3979-3982`, `graphify/cli.py:4030-4052`; `graphify/export.py:405-407`. |
| Reading `_origin: "semantic"` as producer provenance | `_origin` names the extraction kind, not the backend. Claude CLI, OpenAI CLI, and fallback output receive the same value. | The 374 entries under `.agent/kb/native-extract/graphify-out/cache/semantic-deep/pd68e17f4cee0/`; their keys are exactly `edges`, `hyperedges`, and `nodes`. |
| Reading `author` or `contributor` as model identity | `author` is a source-document byline; `contributor` is a sparsely populated pipeline tag. Neither identifies the executing model. | `sources/extractions/`; INHERITED measurement: `contributor` appears on 431 of 11,330 nodes, and `Claude Sonnet 4.6` appears 60 times as a document byline. |
| Running the plan's own "cheapest rung first" openai-cli smoke test | The plan step reads "ONE raw file through `--backend openai-cli`, validated with `mise run kb-validate-chunks`". If that file was ever extracted under another backend, the cache serves the old result, the step prints success, and openai-cli never runs. It is a probe that cannot fail. No plan item currently tracks the two prerequisite fork patches. | `graphify/cache.py:1000`; `graphify/cli.py:3941-3946`; the plan step itself is INHERITED from the session-review lane. |

## 3. THE DECISION #518 NEEDS

### Option 1 — Namespace only by backend

Use `(backend, kind, prompt-fingerprint, content-hash)`.

- **What it costs:** The first run on each backend requires separate LLM work and storage. That directly opposes the deliberate cost position in `graphify/cache.py:940-945`, which says semantic entries are not version-namespaced because re-extraction costs LLM calls, referencing #1252.
- **What it makes possible:** Claude and OpenAI results can coexist, switching back can reuse the prior backend’s variant, and a cache hit cannot cross backend names (`graphify/cache.py:1000`, `graphify/cache.py:1117`).
- **What it forecloses:** It cannot distinguish two models or efforts on the same backend. It also cannot safely classify fallback output unless the cache receives the actual backend rather than the requested backend (`graphify/cli.py:3979-3982`, `graphify/cli.py:4030-4043`).

### Option 2 — Keep the key blind; record backend on the entry

Attach producer metadata to the existing entry but continue using `(kind, prompt-fingerprint, content-hash)`.

- **What it costs:** This is the smallest storage/API expansion, but execution identity still must be plumbed through APIs that currently accept none at `graphify/cache.py:1233-1240` and `graphify/cache.py:1379-1391`.
- **What it makes possible:** Cross-backend reuse becomes visible and reportable instead of invisible; the operator could be told that the selected backend did not produce a hit.
- **What it forecloses:** It does not preserve two variants, does not make A/B comparison possible, and does not stop `--force` from overwriting the baseline at `graphify/cli.py:3941-3946`. It satisfies observability, not reliable switching.

### Option 3 — Add a per-backend partition flag

Retain cross-backend reuse by default and isolate entries only when explicitly requested.

- **What it costs:** It adds a user-facing policy surface and two cache semantics that every wrapper, fallback path, receipt, and test must explain; the current wrapper already has a closed flag surface at `python/src/kb_setup/graphify_native_extract.py:409-416`.
- **What it makes possible:** Operators can choose cheap reuse for ordinary runs and isolated variants for deliberate comparisons.
- **What it forecloses:** Correct attribution is no longer an invariant. Omitting the flag preserves silent cross-backend hits, and backend-only partitioning still does not distinguish model/effort or requested-versus-actual fallback execution (`graphify/cli.py:3979-3982`, `graphify/cli.py:4030-4043`).

### Option 4 — Namespace by the actual execution profile

Add an orthogonal execution-profile namespace beside `prompt_fp`, derived from the actual backend, resolved model, and output-affecting settings such as effort. Store requested backend separately as run intent; store fallback output under the fallback producer’s profile; classify existing unattributed entries as `legacy/unknown`.

- **What it costs:** This is the largest internal change. Execution identity must cross `graphify/cli.py:4030-4052`, both cache APIs at `graphify/cache.py:1233-1240` and `graphify/cache.py:1379-1391`, and export/receipt boundaries at `graphify/export.py:266` and `graphify/export.py:405-407`. It multiplies LLM work and storage for profiles actually used and therefore argues directly against the #1252 cost rationale recorded at `graphify/cache.py:940-945`.
- **What it makes possible:** Claude and OpenAI variants can coexist; switching back reuses the matching prior profile; model/effort changes cannot impersonate one another; fallback output is attributed to the backend/model that ran; legacy entries remain usable only under an explicit legacy policy. This addresses N1, N2, N3, and N5 together.
- **What it forecloses:** Automatic reuse across profiles is no longer treated as semantically safe. Implicit or unresolvable model defaults cannot participate honestly in a stable profile; the model must be resolved or recorded as unknown before reuse can be claimed.

**RECOMMENDATION: choose Option 4, the actual execution-profile namespace.** Backend-only partitioning is insufficient because fallback makes requested and actual backend differ, and because model/effort changes can alter output within one backend (`graphify/cli.py:3979-3982`, `graphify/cli.py:4030-4043`). Record-only metadata leaves the destructive single-slot cache unchanged (`graphify/cache.py:1000`, `graphify/cache.py:1117`).

Execution-identity plumbing must land before either cache partitioning or provenance stamping. The cheapest correct first step is to carry the actual backend and resolved model from the completed primary/fallback path at `graphify/cli.py:4030-4052` into a structured execution identity, without yet changing cache-hit behavior. Requested backend remains intent; actual backend/model remains producer identity. Only after that distinction exists can a cache namespace or `graph.json` stamp avoid lying.

The response to #1252 is bounded duplication: do not namespace by every Graphify version; namespace only by a producer profile that can change semantic output. A second profile pays once, while switching back reuses its existing variant. That cost is required by the owner’s A/B and reversibility goal.

**The single risk that decides it:** an imminent upstream public execution-profile/cache contract, potentially through #1999 or #2140, could make a fork-specific schema incompatible and strand the patch. Those items are TITLE-ONLY and live status COULD NOT CHECK (no network). A confirmed upstream contract would change the decision from designing locally to porting that contract; absent that confirmation, Option 4 is the only option that fulfills the stated goal.

## 4. WHAT UPSTREAM IS ALREADY DOING

**All upstream evidence in this section is TITLE-ONLY unless a local file or git ref is cited. No PR body, issue body, or diff was checked in this lane. Live state COULD NOT CHECK (no network).**

| Upstream item | Title-only signal | Interaction with the fork |
|---|---|---|
| #2077 issue, OPEN in cached slice | “Record the backend and model in graph.json — a graph currently cannot be attributed to what produced it” | Names the same export-provenance gap measured at `graphify/export.py:405-407`. |
| #2140 PR, OPEN in cached slice | “feat(export): record extractor backend/model in graph.json (#2077)” | Claims to address export provenance. It predates fork commit `a4842b4`, so support for requested-versus-actual fallback identity is UNVERIFIED. It must be inspected before designing the export schema. |
| #2314 issue, OPEN in cached slice | “Semantic cache never hits: `save_semantic_cache` silently drops entries when `source_file` is corpus-root-relative” | Names a correctness defect in the exact API at `graphify/cache.py:1379-1391`. If the title reflects this configuration, cross-backend contamination may be latent rather than currently reachable; the key design remains wrong. |
| #3279 PR, OPEN in cached slice | “feat(extract): scope AST symbol inventory for semantic extraction (#3253)” | A prompt-content change can move `prompt_fp` at `graphify/cache.py:100-123`, showing that prompt fingerprinting is upstream’s existing invalidation lever. Invalidation breadth is UNVERIFIED. |
| #1252 | Referenced by the local cache docstring as the LLM-cost reason for avoiding semantic version namespaces. | The proposed execution profile contradicts that cost preference and must justify why producer identity is a correctness boundary rather than ordinary version churn (`graphify/cache.py:940-945`). |
| #3255 PR and #2513 issue, OPEN in cached slice | Defer semantic backend selection to `detect_backend()`. | This is a regression vector against `do-not.md` #4, which requires explicit `--backend`. The fork’s `detect_backend()` does not auto-select `claude-cli` or `openai-cli` at `graphify/llm.py:3535`; no current leak is established. |
| #1999 PR and #2735 PR, OPEN in cached slice | Generic ACP and governed-gateway routing. | This alternative architecture could make per-CLI backend patches obsolete and is the main upstream design capable of stranding a local execution-profile contract. |
| #2981 PR, CLOSED in cached slice | OpenAI CLI backend. | Not the transport source of this fork’s patches. `currency.toml:212` still names it as the upstream PR. |
| #3073 PR, OPEN in cached slice | Byte-identical OpenAI CLI backend title, same author as #2981. | The live successor named by the supplied title slice. The fork is diverged: equivalent backend registration and credential gate, stronger MCP resolvability handling in `157a957`, but UNVERIFIED parity in community labelling. |
| #3069 PR, OPEN in cached slice | Convergent, batched graph-database push. | Overlaps fork commit `72e33a5` on `graphify/exporters/graphdb.py`; this is a merge-collision risk, not cache provenance work. |
| #2081 issue OPEN and #2534 issue CLOSED in cached slice | `built_at_commit` anchored to cwd. | Stale with respect to this fork’s 0.9.53 export path, which anchors to `Path(output_path).resolve().parent` at `graphify/export.py:400-407`. |
| #2861 issue OPEN in cached slice | `GRAPHIFY_CLAUDE_CLI_MODEL` documentation gap. | Adjacent to model attribution: configuration cannot substitute for recording the resolved producer model. |
| #2786 issue OPEN in cached slice | Unknown Codex subagent token usage must not be reported as zero. | Reinforces the same provenance rule: unknown is not zero and legacy/unresolved identity must not impersonate a known producer. |

The cached slice also shows a busy backend surface through #976, #975, #1342, #1963, #2208, and #2389. That makes a backend-specific fork patch integration-sensitive, but the bodies and current dispositions are UNVERIFIED.

Upstream v8 integration debt is locally zero: `upstream/v8@33362d969292b57eda82f3fbd9eb5f3f5bc9bbc2` equals `v0.9.53^{commit}`, and `git rev-list --count HEAD..upstream/v8` → 0. The apparent 36-commit debt against `upstream/main` is invalid because `upstream/main@91f4d12` is not an ancestor of v0.9.53 and belongs to the abandoned v0.1.x line. Zero rebase debt does not resolve open-PR integration debt from #3073, #3069, #2140, #3255, or #3279.

## 5. THE ORIGINATION RECORD

The eight fork commits did not arrive from upstream PR #2981 or #3073. Their supported transport path is a TelB-io fork lineage, with later local work by Ray.

The transport record on `origin/kb-pin/openai-cli-backend@1d0a933` is:

```text
243280a Merge branch 'v8' into feat/openai-cli-backend
7538bd8 Merge pull request #4 from TelB-io/feat/batched-db-push
7f13af8 Merge pull request #3 from TelB-io/feat/watch-semantic
dedb7ff Merge pull request #2 from TelB-io/feat/fallback-backend
2373895 Merge pull request #1 from TelB-io/feat/extract-lock
```

Those commits are authored by `Azeem <allagawadfamily@gmail.com>`, matching the identity associated in the supplied evidence with upstream author `Azeem1985`. Matching identity supports a shared author lineage; it does not prove exact commit ancestry.

Three surviving vendor markers establish that the implementation passed through TelB-io and is absent from upstream tag v0.9.53:

- `graphify/llm.py:222` — `PATCHED FOR TELB-COCKPIT`
- `graphify/llm.py:2020` — `PATCHED FOR TELB-COCKPIT`
- `graphify/__main__.py:577` — `PATCHED FOR TELB-COCKPIT`

Control: `git grep -c claude-cli v0.9.53 -- graphify/llm.py` → 23, so the tag-scoped grep can find content; the same command finds zero `openai-cli` and zero `TELB`, while HEAD has nine `openai-cli` occurrences in `graphify/llm.py`.

### Per-commit ledger

| Fork commit | Origin and upstream relationship |
|---|---|
| `57245ec` — OpenAI CLI semantic backend | Transported through the TelB-io lineage. Content is related to closed #2981 and superseded upstream by open #3073, but exact #2981 ancestry is UNVERIFIED. INHERITED comparison: ours has the August 23 `llm.py` +257/test +75 shape; #3073 is an August 25 rework with `llm.py` +286/test +219 and a folded credential gate. |
| `7e2f389` — credential gate | TelB-io lineage; folded into #3073’s single commit rather than separate upstream. INHERITED comparison: `graphify/cli.py:3769-3774` and the prior lane’s `pr3073:graphify/cli.py:3530-3535` carry identical gate wording. |
| `b34f386` — per-call MCP disabling | TelB-io lineage; converged with #3073 on the finding that `mcp_servers={}` is ineffective. Exact patch ancestry is UNVERIFIED. |
| `a4842b4` — zero-success fallback backend | Fork-only in the cached 80-title upstream slice; transported through TelB-io `feat/fallback-backend`. Runtime behavior is at `graphify/cli.py:4024-4043`. |
| `025a24f` — partial success must not trigger fallback | Fork-only in the cached slice; companion test to `a4842b4`. |
| `2819120` — semantic watch mode | Fork-only in the cached slice; transported through TelB-io `feat/watch-semantic`. |
| `72e33a5` — batched UNWIND graph-DB export | Transported through TelB-io `feat/batched-db-push`; overlaps title-only upstream #3069 on `graphify/exporters/graphdb.py`. |
| `157a957` — disable only MCP servers Codex can resolve | Ray-authored after the transported series. Fork-specific `_codex_resolvable_disable_args()` begins at `graphify/llm.py:1906`; it adds memoized name/resolution probes and excludes unresolved names instead of aborting the call. INHERITED comparison says #3073 lacks this behavior. |

Ray’s commit `4e986d3` on `origin/kb-pin/openai-cli-backend-v0.9.49-tests` explicitly says it ports ten failure-path tests from upstream PR #3073. The fork therefore knowingly tracked #3073 after arriving through TelB-io; that later test port does not rewrite the transport history.

### Current parity record

- **Backend registration:** INHERITED SAME — `GRAPHIFY_OPENAI_CLI_MODEL`, default `gpt-5.6-sol`, default effort `ultra`, and serial execution unless `GRAPHIFY_OPENAI_CLI_PARALLEL=1`; ours begins at `graphify/llm.py:226`, prior-lane #3073 reference `graphify/llm.py:222`.
- **Credential gate:** INHERITED SAME — both require `codex` on `$PATH` and exempt `openai-cli` from the API-key gate; ours at `graphify/cli.py:3769-3774`.
- **MCP handling:** fork superset in one area — `157a957` probes resolvable MCP names at `graphify/llm.py:1906` and memoizes probes.
- **Community labelling:** fork deficit is UNVERIFIED — prior-lane #3073 references `graphify/llm.py:3145-3201` and allowlist `graphify/llm.py:3408`; the fork’s corresponding call-site parity was not re-derived.
- **Tests:** INHERITED — both have 15 tests; #3073’s file was 219 lines and the fork’s was 322. The fork dropped five vendor-detail/turn-usage tests and added ten resolvability/memoization tests.

The durable conclusion is: **the fork is diverged, a superset in MCP resolvability, and potentially behind in community labelling. It is not simply “ahead.”**

The tracked currency record does not yet express that conclusion. `currency.toml:212` names closed #2981 but not live-title successor #3073. `currency.toml:213` repeats a v0.9.50 zero-occurrence measurement under a v0.9.53 base; issue #658 already tracks that stale sentence. The base ref and base commit remain correct.

## 6. WHAT IS UNVERIFIED

- COULD NOT CHECK (no network): bodies and diffs for #2140, #3073, #3255, #3279, #3069, and #2981; bodies for #2077 and #2314. All upstream descriptions are TITLE-ONLY.
- UNVERIFIED: community-labelling parity with prior-lane #3073 references `graphify/llm.py:3145-3201` and `graphify/llm.py:3408`.
- UNVERIFIED: exact code ancestry from #2981 to `57245ec`. TelB-io transport is supported by `origin/kb-pin/openai-cli-backend@1d0a933` and vendor markers; it does not establish commit identity.
- UNVERIFIED: all 29 host-agent chunks used the same backend or model. `sources/extractions/` did not record either.
- UNVERIFIED: backend or model for any semantic node in the current graph.
- UNVERIFIED: #2314 applies to this repository’s configuration. If it does, the backend-blind hit is latent rather than live here.
- UNVERIFIED: breadth of #3279’s prompt-fingerprint invalidation.
- COULD NOT CHECK (no network): live upstream state. `upstream/v8` reflects only this clone’s last fetch.
- UNVERIFIED: the trade-off behind the Phase N0b choice to use Claude `kb-extract` fan-out instead of `kb-graphify-native-extract --backend openai-cli`.
- INHERITED, not re-derived: #3073 line numbers, diffstats, and test counts in the origination record.
- INHERITED, not re-derived: 347,696 AST nodes, 11,330 host-agent nodes, and the percentage split. The total 359,026 nodes / 806,869 edges is corroborated by `graphify-out/build-receipt.json`.
- UNVERIFIED: explicit `--model gpt-5.6-sol` or `GRAPHIFY_OPENAI_CLI_MODEL` application in `kb_setup`.
- UNVERIFIED: fork-only fallback behavior under a real repository invocation; `--fallback-backend` is unreachable through `python/src/kb_setup/graphify_native_extract.py:409-416`.
- UNVERIFIED: the 80-title slice represents the full upstream tracker.
- UNVERIFIED: long-term survival of `docs/artifacts/the-backend-switch-that-doesnt.html`; it is currently untracked and therefore vulnerable to removal.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the target repository: issues #518, #540, #658, `currency.toml:212-213`, `python/src/kb_setup/graphify_native_extract.py:409-416`, `python/src/kb_setup/graphify_ops.py:527`, and the `graphify-out/` artifacts.
- [ray-manaloto/graphify](https://github.com/ray-manaloto/graphify) — the pinned fork, read at `/Users/rmanaloto/dev/github/ray-manaloto/graphify`, branch `kb-pin/openai-cli-backend-v0.9.53`, HEAD `157a957e89a16246bba3a078de2777711ee85e31`. Every `graphify/…` file:line in this report was read there.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — upstream, named by `currency.toml`'s `[tool.graphify.fork] upstream` field. Source of tag `v0.9.53` / `upstream/v8@33362d969292b57eda82f3fbd9eb5f3f5bc9bbc2` and of the cached title slice containing #2077, #2140, #2314, #2981, #3073, #3069, #3255, #3279. Live state COULD NOT CHECK (no network).
- TelB-io's graphify fork — the transport source, evidenced by `origin/kb-pin/openai-cli-backend@1d0a933`'s `Merge pull request #1..#4 from TelB-io/feat/*` commits and the three surviving `PATCHED FOR TELB-COCKPIT` markers. **No URL is asserted**: the exact GitHub slug COULD NOT CHECK (no network), and guessing a plausible one would be a probe with no control arm.

## ISSUE BODY — UPDATE #518

Update measured 2026-09-02 against the installed fork at Graphify 0.9.53 (`kb-pin/openai-cli-backend-v0.9.53@157a957`): **the issue is still true, and the existing escape hatch is more destructive than the original body recorded.**

### Still backend-blind at 0.9.53

`graphify/cache.py` contains zero occurrences of `backend`. Control: it contains three occurrences of `hashlib`, so the zero is a measurement.

The semantic key remains only:

- kind, `semantic` or `semantic-deep` (`graphify/cache.py:926`);
- prompt fingerprint (`graphify/cache.py:100`, `graphify/cache.py:123`);
- file-content SHA256 (`graphify/cache.py:958`);
- read path at `graphify/cache.py:1000`;
- write path at `graphify/cache.py:1117`.

This is deliberate upstream policy, not an accidental omission. `graphify/cache.py:940-945` says semantic entries are not version-namespaced because re-extraction costs LLM calls, referencing #1252.

### New findings

1. **`--force` is destructive, not merely wasteful.**  
   `graphify/cli.py:3941-3946` says `--force` skips the cache read but still saves the fresh result. Because the save target remains backend-blind at `graphify/cache.py:1117`, `--force --backend openai-cli` overwrites the existing Claude entry in place. It destroys the A/B baseline and requires another paid extraction to switch back.

2. **The actual execution backend is already computed and discarded.**  
   `_last_backend = backend` at `graphify/cli.py:4030`; `_last_backend = fallback_backend` at `graphify/cli.py:4043`. The value is used only in an error message at `graphify/cli.py:4052`. This is the actual producer identity a cache entry or export stamp needs.

3. **The blindness is in the public cache API, not only the directory key.**  
   `check_semantic_cache(...)` accepts no backend/model at `graphify/cache.py:1233-1240`. `save_semantic_cache(...)` accepts none at `graphify/cache.py:1379-1391`. Callers cannot supply producer identity today.

4. **Fallback can run a different, unrecorded model.**  
   `graphify/cli.py:3979-3982` explicitly avoids applying the primary `--model` to the fallback because it may be invalid there; the fallback uses its own default. A run can therefore request backend/model A but produce output using backend/default-model B. Neither is persisted: `graphify/export.py` records only `built_at_commit` at `graphify/export.py:405-407`.

5. **This repository is not currently backend-mixed.**  
   INHERITED corpus measurement: zero of 359,026 composed nodes came from Graphify semantic `--backend` extraction. The composition is 347,696 AST nodes plus 11,330 nodes from the separate Claude host-agent `kb-extract` fan-out (`graphify-out/.compose-manifest.json`, `graphify-out/build-receipt.json`). The one 374-entry semantic cache lives in gitignored scratch at `.agent/kb/native-extract/graphify-out/cache/semantic-deep/pd68e17f4cee0/` and is absent from the compose manifest. This issue is a future-facing blocker here, not evidence of live corruption in the current composed graph.

6. **`--fallback-backend` is not operationally reachable here.**  
   The wrapper’s closed allowlist at `python/src/kb_setup/graphify_native_extract.py:409-416` omits it. INHERITED census: zero operational fallback occurrences; control: 26 `--backend` occurrences across `python/` and `mise.toml`.

### Upstream signals

These are TITLE-ONLY from a cached slice; bodies, diffs, and live state COULD NOT CHECK (no network):

- #2077 asks to record backend/model in `graph.json`.
- #2140 claims to implement #2077, but predates this fork’s fallback and therefore does not establish requested-versus-actual identity.
- #2314 names a correctness bug in `save_semantic_cache`; if applicable here, the cross-backend hit may be latent rather than live.
- #3279 changes semantic prompt input; prompt changes already invalidate through `prompt_fp`, but invalidation breadth is UNVERIFIED.

### Decision still required

The original three options remain:

1. Namespace by backend.
2. Keep the key blind and record backend on the entry.
3. Add a per-backend partition flag.

Today’s evidence adds a fourth:

4. **Namespace by the actual execution profile:** actual backend + resolved model + output-affecting settings such as effort, beside `prompt_fp`. Record requested backend separately as intent. Store fallback output under the fallback producer’s profile. Keep existing unattributed entries explicitly `legacy/unknown`.

Recommendation: choose option 4. Backend-only partitioning cannot distinguish model changes and can still lie under fallback. Record-only metadata leaves one destructive cache slot. A flag leaves correctness optional.

Execution-identity plumbing must land first: carry the actual backend and resolved model out of `graphify/cli.py:4030-4052`, then use that identity for both provenance and cache partitioning. The cost response to #1252 is that variants are paid once per execution profile, while switching back reuses the previously created variant.

The single deciding risk is an imminent incompatible upstream execution-profile/cache contract, potentially through title-only #1999 or #2140. Live upstream state COULD NOT CHECK (no network).

## ISSUE BODY — NEW ISSUE

**Title:** Restore per-call Graphify execution receipts without importing private internals

**Body:**

### Problem

This repository previously recorded enough metadata to identify and reproduce individual Graphify semantic calls:

- `graphify-out/graphify-semantic-slice/receipt.json` recorded backend plus per-chunk prompt/source hashes.
- `graphify-out/graphify-semantic-corpus/execution-config.json` recorded backend, canonical model, auth route, adapter hash, executable hash, and cache policy.
- `graphify-out/graphify-semantic-slice/adapter-metadata.json` recorded exact argv, model, schema, and budget.

Issue #317 settled the policy in favor of tracking this evidence. The implementation was removed on 2026-08-24 because it recreated Graphify CLI behavior using private functions such as `_estimate_file_tokens`, `_extraction_system`, `_pack_chunks_by_tokens`, and `_read_files` (`docs/archive/README.md`, `do-not.md` #5).

The removal was correct; losing the execution record was not. The owner’s recorded follow-up in `docs/archive/README.md` was to retain metadata and arguments for every Graphify call.

Current Graphify output records only `built_at_commit` at `graphify/export.py:405-407`. It does not record backend or model. The actual primary/fallback backend is computed at `graphify/cli.py:4030-4043` and discarded at `graphify/cli.py:4052`.

This is distinct from #518:

- #518 decides semantic-cache identity and coexistence of backend variants.
- This issue restores the repository-side execution receipt for every Graphify call, including cache hits, failures, and non-semantic verbs.

### Required record

Define one structured receipt/event per Graphify invocation containing, where applicable:

- requested backend and model;
- actual backend and resolved model after fallback;
- output-affecting settings such as effort;
- normalized argv, with secrets excluded;
- auth route and adapter/executable identity without credentials;
- prompt and source hashes;
- cache outcome: hit, miss, forced replacement, legacy reuse, or save failure;
- token/cost fields with unavailable values recorded as unknown, not zero;
- start/end timestamps, return status, warnings, omissions, and truncation;
- produced artifact paths and the target repository commit.

Use the existing structured event boundary in `python/src/kb_setup/events.py`, already consumed by `python/src/kb_setup/graphify_native_extract.py`. Do not import Graphify private functions. Follow the repository’s standing ranking: public SDK matching the CLI verb first, shelling out to a public CLI second, private internals never.

Do not use `kb-remember` as the durable destination: `graphify-out/memory/` is write-only with respect to the prose graph in this repository; issue #540.

### Acceptance evidence

- A real isolated primary-backend run emits one receipt with requested and actual backend/model.
- A real isolated fallback run records the fallback producer rather than copying primary intent.
- A cache-hit control records that no backend executed and identifies the cached producer or `legacy/unknown`.
- A `--force` control records replacement of the prior cache slot until #518 changes the cache design.
- A failing call retains stderr, warnings, truncation, omissions, and the non-zero result.
- No receipt contains credentials or secret environment values.
- No implementation imports a private Graphify symbol.
- The receipt is stored in a tracked or otherwise durably published artifact path, not only in gitignored scratch.

Related: #317, #518, #540. Live status of #317 COULD NOT CHECK (no network).
