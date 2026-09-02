# Graphify 0.9.51-0.9.53 release review against the 2026-09-01 build failure

## Scope and method

This lane is read-only on tracked repository content. It reviews upstream `Graphify-Labs/graphify` release notes, tags, commit diffs, source, pull requests, and issues; local wrapper and pin source; and an isolated disposable rebase for questions 1-5. The measured local failure and aggregate `source_file` facts in the task prompt are treated as inputs, not re-measured here; no `kb-build` or writing Graphify command was run.

Negative tracker and source conclusions are not accepted without a positive control showing that the same probe can find a known matching artifact. Tool or source-access failures are recorded inline.

Graph-first orientation was attempted with `mise run kb-query -- "What changed in upstream Graphify 0.9.51 0.9.52 and 0.9.53 concerning node ID minting duplicate IDs source namespaces merge-graphs and related issues?"`. It failed closed with exit 3 because the answer was **TRUNCATED** (60 of 1,143 nodes), and also emitted `mise WARN tool purgatory cleanup failed: Operation not permitted`. Per the wrapper's own message, that prefix is not evidence of absence. The useful orientation clue was a graph health note saying the graph uses the pre-#1504 node-ID scheme and that a forced rebuild would produce path-qualified IDs; this report does not treat that local graph note as upstream proof and verifies #1504 against GitHub source below.

Tool failure retained: the filtered upstream clone twice emitted a promisor-object fatal during a broad `git grep`/`git blame` (`commit ... is in the commit graph file but not in the object database`; `could not fetch ... from promisor remote`), including once after `git fetch --refetch --tags`. Those failed outputs were discarded. Every finding below was re-established through exact-tag `git show`/`git diff`, official GitHub API data, or stable GitHub source URLs. A recurring `mise WARN tool purgatory cleanup failed: Operation not permitted` also accompanied several successful read-only Git commands; it did not change their exit status or output.

## 1. Release changes in 0.9.51, 0.9.52, and 0.9.53

### Verdict

**No general Python/cross-source collision repair lands in 0.9.51-0.9.53.** The range contains two extractor-local ID changes: Common Lisp in 0.9.51 and the newly added Robot Framework extractor in 0.9.53. The shared ID helpers, duplicate-ID module, and `merge-graphs` regression test are byte-identical at all four tags; the exact warning remains present at 0.9.53. Evidence and controls follow.

The inspected tag boundaries are [`v0.9.50` = `43d54acbfa9e731f7a592bb582c1f4b9d48ed73e`](https://github.com/Graphify-Labs/graphify/commit/43d54acbfa9e731f7a592bb582c1f4b9d48ed73e), [`v0.9.51` = `281ccaa4ff38aaef3f19e823fb7645e19b28f591`](https://github.com/Graphify-Labs/graphify/commit/281ccaa4ff38aaef3f19e823fb7645e19b28f591), [`v0.9.52` = `680e3ed8edd3dc1fa1961050912941880b778207`](https://github.com/Graphify-Labs/graphify/commit/680e3ed8edd3dc1fa1961050912941880b778207), and [`v0.9.53` = `33362d969292b57eda82f3fbd9eb5f3f5bc9bbc2`](https://github.com/Graphify-Labs/graphify/commit/33362d969292b57eda82f3fbd9eb5f3f5bc9bbc2). The complete official comparisons are [0.9.50...0.9.51](https://github.com/Graphify-Labs/graphify/compare/v0.9.50...v0.9.51), [0.9.51...0.9.52](https://github.com/Graphify-Labs/graphify/compare/v0.9.51...v0.9.52), and [0.9.52...0.9.53](https://github.com/Graphify-Labs/graphify/compare/v0.9.52...v0.9.53).

### 0.9.51

The [0.9.51 release notes](https://github.com/Graphify-Labs/graphify/releases/tag/v0.9.51) explicitly say: **“Common Lisp node ids are now derived from the full path stem.”** Commit [`e906227cf65834d5e13008b2ef9f8e38ea85c383`](https://github.com/Graphify-Labs/graphify/commit/e906227cf65834d5e13008b2ef9f8e38ea85c383) changes only the Common Lisp extractor from bare `path.stem` to `_make_id(_file_stem(path))` and adds a two-directory `a/sample.lisp` versus `b/sample.lisp` regression. This is a real node-ID minting fix, but it is language-local, not a Python or general per-source namespace change.

Python already used the generic extractor and `_file_stem(path)` in 0.9.50 ([`engine.py` at 0.9.50](https://github.com/Graphify-Labs/graphify/blob/v0.9.50/graphify/extractors/engine.py#L2910)); the shared helper already preserved all path segments ([`base.py` at 0.9.50](https://github.com/Graphify-Labs/graphify/blob/v0.9.50/graphify/extractors/base.py#L58-L73)). **Inference:** the 0.9.51 Common Lisp repair cannot causally repair one Python source presented under both a source-prefixed and a bare path.

The same release notes also say a carried hyperedge's members are **“routed through the dedup survivor remap.”** Commit [`3378ae8fef0d449b51a386f99759c50ac5df5a67`](https://github.com/Graphify-Labs/graphify/commit/3378ae8fef0d449b51a386f99759c50ac5df5a67) changes incremental `build_merge()` so carried hyperedge member references follow an already-existing node survivor remap. It does not change how node IDs are minted, which duplicate node survives, the collision warning, or CLI `merge-graphs`.

### 0.9.52

The [0.9.52 release notes](https://github.com/Graphify-Labs/graphify/releases/tag/v0.9.52) mention that the Objective-C field-to-type table is **“re-keyed alongside the node-id rewrites.”** Commit [`208d0c1dcc2c790a8fe90707e5470f65948ad8a9`](https://github.com/Graphify-Labs/graphify/commit/208d0c1dcc2c790a8fe90707e5470f65948ad8a9) applies already-computed remaps to an Objective-C auxiliary lookup table; it does not mint a new ID scheme or change duplicate-ID handling.

A provenance change briefly entered the pre-release history in [`b568488cb4dd70fb3ab22e1ad23d794fcf5229b0`](https://github.com/Graphify-Labs/graphify/commit/b568488cb4dd70fb3ab22e1ad23d794fcf5229b0), but was explicitly reverted by [`b88e1640ca9d6ae8ce5acd147344f3bb3f88c787`](https://github.com/Graphify-Labs/graphify/commit/b88e1640ca9d6ae8ce5acd147344f3bb3f88c787) before the `v0.9.52` tag. The final [0.9.51...0.9.52 comparison](https://github.com/Graphify-Labs/graphify/compare/v0.9.51...v0.9.52) therefore contains no general minting, source-namespace, collision-warning, or CLI `merge-graphs` repair.

### 0.9.53

The [0.9.53 release notes](https://github.com/Graphify-Labs/graphify/releases/tag/v0.9.53) introduce Robot Framework extraction. Within that new extractor, commit [`43e63b1c3f6641de6ddd2227337b4c9b1104ee11`](https://github.com/Graphify-Labs/graphify/commit/43e63b1c3f6641de6ddd2227337b4c9b1104ee11) changes an external-library stub from `_make_id(raw)` to `_make_id("robot_library", raw)`, preventing a user keyword with the same name from colliding. That is an extractor-local namespace, not a general per-source namespace or Python fix. The final [0.9.52...0.9.53 comparison](https://github.com/Graphify-Labs/graphify/compare/v0.9.52...v0.9.53) contains no other relevant change.

### Shared-code negative result and control arm

Source inspection at the four exact tags produced the same Git blob for each of the following files ([complete official comparison](https://github.com/Graphify-Labs/graphify/compare/v0.9.50...v0.9.53)):

```text
graphify/extractors/base.py       148fc18c647c2eff1213706a26c6cca57b83e351
graphify/dedup.py                 4816f103b6902be71ec5bc505854f4b6013d4ccc
tests/test_merge_graphs_cli.py    643e29e0a1e997454ee64f7ddab1f2cfa910a279
```

The command `git diff --exit-code v0.9.50..v0.9.53 -- graphify/dedup.py graphify/extractors/base.py tests/test_merge_graphs_cli.py` returned 0. The current warning remains at [`v0.9.53 graphify/dedup.py:424-458`](https://github.com/Graphify-Labs/graphify/blob/v0.9.53/graphify/dedup.py#L424-L458), including the same per-subfolder/`merge-graphs` advice.

The negative probes `git log -G 'minted by two different files' v0.9.50..v0.9.53 -- graphify` and `git log -G 'merge-graphs|merge_graph|merge_graphs' v0.9.50..v0.9.53 -- graphify` returned no commits. **Control:** over the same repository and tag range, `git log -G 'Robot Framework|robot' ... -- graphify` found both [`832256f824efe1b807d592510ae2dbe9e100d4b2`](https://github.com/Graphify-Labs/graphify/commit/832256f824efe1b807d592510ae2dbe9e100d4b2) and [`43e63b1c3f6641de6ddd2227337b4c9b1104ee11`](https://github.com/Graphify-Labs/graphify/commit/43e63b1c3f6641de6ddd2227337b4c9b1104ee11). The probe therefore demonstrably detects changes in this range; the empty generic-warning/merge results are evidence, not an uncontrolled not-found.

`merge-graphs` already prefixes every input graph's IDs before composition at 0.9.53 ([`cli.py:2588-2702`](https://github.com/Graphify-Labs/graphify/blob/v0.9.53/graphify/cli.py#L2588-L2702), [`build.py:2063-2143`](https://github.com/Graphify-Labs/graphify/blob/v0.9.53/graphify/build.py#L2063-L2143)). The implementation and its test were already present at 0.9.50; none of the reviewed releases changes that isolation path ([0.9.50...0.9.53 comparison](https://github.com/Graphify-Labs/graphify/compare/v0.9.50...v0.9.53)).

## 2. Known upstream bug, issue, or fix

### Verdict

**Yes, the collision family is known upstream, and several fixes shipped before 0.9.50; the closest mixed-path-base hardening remains absent in 0.9.53 source.** The exact `anthropic-sdk-python` `sources/<name>/...` versus bare-path instance is not separately filed in the tracker under that path, but [issue #2259](https://github.com/Graphify-Labs/graphify/issues/2259) records the same structural failure: one source represented under inconsistent path bases, followed by hundreds of `node minted by two different files` warnings and graph duplication/loss.

### What is already fixed upstream (and already contained in 0.9.50)

- [Issue #1504](https://github.com/Graphify-Labs/graphify/issues/1504) reported silent data loss when same-named files in different directories minted the same IDs across extraction chunks. Commit [`b46634ef7aeb1668af68e10a1b0f658051bf5ac2`](https://github.com/Graphify-Labs/graphify/commit/b46634ef7aeb1668af68e10a1b0f658051bf5ac2) changed stems to the full repository-relative path for the 0.9.0 ID scheme. This is why an issue's former state is insufficient evidence: the source fix is the decisive artifact.
- [PR #1508](https://github.com/Graphify-Labs/graphify/pull/1508) / commit [`5320aa8eb1e68069314dbf48627a88148d5565d6`](https://github.com/Graphify-Labs/graphify/commit/5320aa8eb1e68069314dbf48627a88148d5565d6) added the stderr warning and the per-subfolder/`merge-graphs` advice for collisions that still reach dedup. This is the ancestry of the exact warning in the measured failure, not a repair that preserves both colliding nodes.
- [Issue #1522](https://github.com/Graphify-Labs/graphify/issues/1522) found a residual: lossy normalization could still make two distinct full paths collide. Commit [`35fb43736555b0e8bf843931e12c8bdaf0483e08`](https://github.com/Graphify-Labs/graphify/commit/35fb43736555b0e8bf843931e12c8bdaf0483e08) adds a stable path hash only when two distinct raw source keys still produce the same normalized salt; it shipped in 0.9.1.
- [Issue #1729](https://github.com/Graphify-Labs/graphify/issues/1729) reported `merge-graphs` collapsing same-stem nodes when two input graphs derived the same repository tag. Commit [`4be0f7b3bfe9ac32f6a8caca5bbd6cac632d20c8`](https://github.com/Graphify-Labs/graphify/commit/4be0f7b3bfe9ac32f6a8caca5bbd6cac632d20c8) made every input tag distinct before composition. Current source still uses that distinct-tag prefixing ([`build.py:2118-2143`](https://github.com/Graphify-Labs/graphify/blob/v0.9.53/graphify/build.py#L2118-L2143)).

`git merge-base --is-ancestor <fix> v0.9.50` returned success for all four fix commits above. Therefore none is newly acquired by moving from 0.9.50 to 0.9.53.

### Closest match: mixed path bases (#2259), and what current source proves

[Issue #2259](https://github.com/Graphify-Labs/graphify/issues/2259) reports absolute and root-relative `source_file` spellings for the same inputs, an 854 to 1,154 node jump, and about 538 instances of the same `node minted by two different files` warning. In a later [correction/comment](https://github.com/Graphify-Labs/graphify/issues/2259#issuecomment-5125001795), the reporter established that a stale installed skill and changing working-directory/cache anchors produced the inconsistent bases; after upgrading and reinstalling the skill, five consecutive 0.9.30 updates converged. The reporter deliberately left the harder question open: whether Graphify should normalize or reject inconsistent path bases before identity/dedup.

The present `v0.9.53` source resolves that ambiguity without relying on the issue's OPEN state:

- `extract()` documents that `root` is the source-file/ID anchor and that `cache_root` is only the fallback anchor ([`graphify/extract.py:5875-5967`](https://github.com/Graphify-Labs/graphify/blob/v0.9.53/graphify/extract.py#L5875-L5967)). Supplying inconsistent anchors can therefore create different stored path keys by contract.
- `build()` runs `deduplicate_entities()` **before** `build_from_json()` ([`graphify/build.py:1350-1390`](https://github.com/Graphify-Labs/graphify/blob/v0.9.53/graphify/build.py#L1350-L1390)). The later builder does normalize `source_file` ([`graphify/build.py:955-976`](https://github.com/Graphify-Labs/graphify/blob/v0.9.53/graphify/build.py#L955-L976)), but that is too late to prevent the collision decision.
- Dedup's survivor ranking can compare absolute and relative forms under a supplied root, but `_same_source_entity()` still requires literal, non-empty string equality ([`graphify/dedup.py:348-402`](https://github.com/Graphify-Labs/graphify/blob/v0.9.53/graphify/dedup.py#L348-L402)). `_report_id_collision()` likewise branches on literal `lose_file == keep_file`, otherwise printing the warning and dropping a node ([`graphify/dedup.py:424-458`](https://github.com/Graphify-Labs/graphify/blob/v0.9.53/graphify/dedup.py#L424-L458)).

**Inference from current source:** 0.9.53 still cannot recognize `sources/anthropic-sdk-python/src/anthropic/_base_client.py` and `src/anthropic/_base_client.py` as the same physical source once both forms reach the dedup batch. It treats them as two different files, selects one survivor, emits the measured warning, and loses the other record. The already-shipped path-ID fixes solve distinct-source collisions and well-anchored extraction; they do not normalize an application-supplied source namespace away at dedup time.

### Tracker not-found and control

The corrected GitHub Search API probe for the exact path `"sources/anthropic-sdk-python/src/anthropic/_base_client.py"` in `repo:Graphify-Labs/graphify` returned `total_count: 0`. **Control:** the same API and repository query for `"source_file written as absolute path"` returned [issue #2259](https://github.com/Graphify-Labs/graphify/issues/2259), and the broader exact-warning query returned #2259 plus an unrelated open PR. The tracker probe can find known matching content; the absence of a separately filed Anthropic-specific issue is therefore controlled.

Tool failure: an initial GitHub Search API probe used `gh api search/issues -f q=...` without `-X GET`; `gh` therefore sent the wrong method and GitHub returned HTTP 404 for all four attempted queries. Those results are discarded. The corrected GET probes and their control are reported above.

### Qualified 0.9.51 trigger-path candidate: `--force --code-only` (#3125)

There is one release-range change that does **not** alter generic ID/dedup code but is directly relevant to this wrapper's exact invocation. The wrapper runs `graphify extract sources/<name> --code-only --force` and reuses the subgraph at `sources/<name>/graphify-out/graph.json` (`python/src/kb_setup/graph.py:754-778`). At `v0.9.50`, when that graph already exists, the CLI explicitly turns `incremental_mode` back on for `--force --code-only`, despite printing “full re-scan” ([`v0.9.50 cli.py:3251-3292`](https://github.com/Graphify-Labs/graphify/blob/v0.9.50/graphify/cli.py#L3251-L3292)).

Commit [`ae074b21226b7e2be163f6407498a9e37a1d25fc`](https://github.com/Graphify-Labs/graphify/commit/ae074b21226b7e2be163f6407498a9e37a1d25fc), shipped in [0.9.51](https://github.com/Graphify-Labs/graphify/releases/tag/v0.9.51), separates scan mode from merge mode: `--force --code-only` now performs a true full AST scan while a separate `merge_existing_graph` gate carries the semantic tier. The 0.9.53 implementation states that setting incremental mode had dropped unchanged code files from the AST pass ([`v0.9.53 cli.py:3385-3405`](https://github.com/Graphify-Labs/graphify/blob/v0.9.53/graphify/cli.py#L3385-L3405)).

**Inference, not causal proof:** #3125 can plausibly prevent the stale/fresh mixed-path batch from being formed on a warm subgraph, so it makes a 0.9.53 rebase the right first discriminating test. It does not canonicalize the two path spellings once both reach dedup, and its regression invokes `extract .` with the subprocess cwd equal to the scan root ([`test_extract_code_only_cli.py:29-35`](https://github.com/Graphify-Labs/graphify/blob/v0.9.53/tests/test_extract_code_only_cli.py#L29-L35)), whereas this wrapper invokes a nested relative target from the knowledge-base root (`python/src/kb_setup/graph.py:764-768`). Therefore neither the release note nor that test proves that #3125 removes this particular warning.

## 3. Are we invoking Graphify incorrectly?

### Verdict

**No: the build already follows the warning's repository-level split-and-merge design.** It extracts each manifest source separately, then merges those per-source graphs in one N-ary `merge-graphs` call. The task's measured collision occurs before that merge because `_extract_code()` requires a complete per-source receipt before `build()` reaches aggregate composition (`python/src/kb_setup/graph.py:790-818,2856-2868`); changing the later merge cannot preserve the record already dropped inside `anthropic-sdk-python`.

The build path is explicit:

- `_extract_code()` sets `source_root = repo_root / "sources" / name`, runs `graphify extract sources/<name> --code-only --force`, and reads that source's own `sources/<name>/graphify-out/graph.json` (`python/src/kb_setup/graph.py:754-786`). It accounts for stderr and calls `require_complete()` before returning (`python/src/kb_setup/graph.py:787-818`).
- `build()` calls `_extract_code(repo_root, name)` once for every askable manifest source (`python/src/kb_setup/graph.py:2822-2843`).
- It then supplies every code-bearing source's individual graph, plus the self graph, to `_merge_sources_into()` (`python/src/kb_setup/graph.py:2856-2868`). That helper deliberately makes one N-ary `merge-graphs` call (`python/src/kb_setup/graph.py:2603-2648`).
- The fail-closed behavior is intentional and correctly retains the unaccounted warning: `require_complete()` includes bounded `unaccounted_stderr` evidence and raises when the receipt is not complete (`python/src/kb_setup/graphify_health.py:473-504`).

The warning's generic advice is for two distinct entities that minted the same local ID in one extraction. The measured failure instead supplies two spellings of the same physical source path inside one source graph. **Inference:** a further per-package-directory split is not the causal repair; it could incidentally change the path/output anchor, but it would also create extra Graphify namespaces and prevent cross-subfolder edges. This repository has already measured that no edge crosses `merge-graphs` namespaces and therefore uses one extraction root when cross-tree edges matter (`python/src/kb_setup/graph.py:1651-1667`). No write probe was run in this read-only lane, so any claim that a narrower split would suppress this warning is **UNVERIFIED**.

The aggregate's unnamespaced `source_file` values are consistent with `merge-graphs`' documented implementation, not evidence that the wrapper skipped merging. `prefix_graph_for_global()` prefixes node IDs, rewrites ID-bearing references, and adds `repo`/`local_id`, but does not rewrite `source_file` ([`v0.9.53 build.py:2063-2115`](https://github.com/Graphify-Labs/graphify/blob/v0.9.53/graphify/build.py#L2063-L2115)); the CLI invokes that function once per input before composition ([`v0.9.53 cli.py:2663-2697`](https://github.com/Graphify-Labs/graphify/blob/v0.9.53/graphify/cli.py#L2663-L2697)). Thus IDs are per-input namespaced while provenance paths remain relative to each clone root. No 0.9.51-0.9.53 release changes that contract (section 1 control arm).

## 4. Cost of rebasing the fork onto 0.9.53

### Measured divergence

The exact common ancestor of fork pin [`0a2eb5fdd3110b821bc4fa2759bc964a8bc0a956`](https://github.com/ray-manaloto/graphify/commit/0a2eb5fdd3110b821bc4fa2759bc964a8bc0a956) and upstream [`v0.9.53` / `33362d969292b57eda82f3fbd9eb5f3f5bc9bbc2`](https://github.com/Graphify-Labs/graphify/commit/33362d969292b57eda82f3fbd9eb5f3f5bc9bbc2) is [`43d54acbfa9e731f7a592bb582c1f4b9d48ed73e`](https://github.com/Graphify-Labs/graphify/commit/43d54acbfa9e731f7a592bb582c1f4b9d48ed73e), the `v0.9.50` tag. The isolated-clone measurement was:

```text
git merge-base 0a2eb5fdd3110b821bc4fa2759bc964a8bc0a956 v0.9.53
43d54acbfa9e731f7a592bb582c1f4b9d48ed73e

git rev-list --left-right --count 0a2eb5fdd3110b821bc4fa2759bc964a8bc0a956...v0.9.53
8  61
```

So upstream has 61 commits absent from the fork pin, and the fork has 8 commits absent from upstream ([upstream range](https://github.com/Graphify-Labs/graphify/compare/v0.9.50...v0.9.53), [fork range](https://github.com/ray-manaloto/graphify/compare/43d54acbfa9e731f7a592bb582c1f4b9d48ed73e...0a2eb5fdd3110b821bc4fa2759bc964a8bc0a956)). The fork-only range is not just the four `openai-cli` commits; it also contains fallback-backend, semantic-watch, and batched GraphDB-push work, visible in that fork comparison.

### Actual rebase and focused-test probe

A disposable clone rebased all eight fork commits with:

```text
git rebase --onto v0.9.53 43d54acbfa9e731f7a592bb582c1f4b9d48ed73e 0a2eb5fdd3110b821bc4fa2759bc964a8bc0a956
```

**MEASURED local probe:** code auto-merged for all eight commits. Git stopped four times, each time only on `CHANGELOG.md`: [`146b6c7`](https://github.com/ray-manaloto/graphify/commit/146b6c706051879e9303c25776b8265f731db38d), [`c9006a0`](https://github.com/ray-manaloto/graphify/commit/c9006a06eaf6a272f17cb9c45098c11236a7df6c), [`69abe3a`](https://github.com/ray-manaloto/graphify/commit/69abe3a7db37e8d74652f5608b3375fbd1cb7284), and [`0a2eb5f`](https://github.com/ray-manaloto/graphify/commit/0a2eb5fdd3110b821bc4fa2759bc964a8bc0a956). For conflict-discovery only, the probe kept the upstream changelog side; a production rebase must integrate the four fork entries rather than repeat that intentionally non-shipping resolution. `git diff --check v0.9.53..HEAD` then returned clean.

After the full rebase, the four focused fork suites passed under the rebased source:

```text
PYTHONPATH=<rebased-clone> uv run --project <knowledge-base> pytest \
  tests/test_openai_cli_backend.py tests/test_fallback_backend.py \
  tests/test_watch_semantic.py tests/test_batched_push.py -q
................................................                         [100%]
48 passed in 2.24s
```

Those suites are the regression files introduced by the fork-only commits ([fork comparison](https://github.com/ray-manaloto/graphify/compare/43d54acbfa9e731f7a592bb582c1f4b9d48ed73e...0a2eb5fdd3110b821bc4fa2759bc964a8bc0a956)). The run emitted two environment warnings that did not affect its zero exit: mise created a temporary `.venv` in the disposable clone and reported `tool purgatory cleanup failed: Operation not permitted`; uv also warned that this temporary `VIRTUAL_ENV` did not match the knowledge-base project environment. No full upstream suite, `mise run check`, `mise run kb-gates`, or `kb-build` was run in this read-only lane.

### Backend-dispatch compatibility

`detect_backend()` was **not restructured** between the common base and 0.9.53. Its body at [`v0.9.50 llm.py:3103-3133`](https://github.com/Graphify-Labs/graphify/blob/v0.9.50/graphify/llm.py#L3103-L3133) is the same logic as [`v0.9.53 llm.py:3111-3141`](https://github.com/Graphify-Labs/graphify/blob/v0.9.53/graphify/llm.py#L3111-L3141); the line shift comes from unrelated pricing/prompt-sentinel edits in the [0.9.50...0.9.53 comparison](https://github.com/Graphify-Labs/graphify/compare/v0.9.50...v0.9.53). The CLI credential gate also retains the same `claude-cli` branch at 0.9.53 ([`cli.py:3605-3694`](https://github.com/Graphify-Labs/graphify/blob/v0.9.53/graphify/cli.py#L3605-L3694)), which is exactly where fork commit [`fcff3e7`](https://github.com/ray-manaloto/graphify/commit/fcff3e7d25a05fb79f53b832a6c7c7ebbb4c66cc) adds the sibling `openai-cli` check. This matches the rebase probe: the backend code applied without a content conflict; only changelog placement conflicted.

### Realistic cost

**Estimate grounded in the completed probe:** the fork rebase itself is low effort, about 30-60 minutes of hands-on work to preserve four changelog entries, verify the new version metadata, and rerun the focused suites. Promoting the rebased SHA into this repository is a separate moderate task, roughly another 1-2 hours of hands-on identity/receipt work before long-running gates: the current version/revision appears in `pyproject.toml:32,257`, `uv.lock:655-658,1071-1075`, `sources/graphify.manifest:88-94`, `python/src/kb_setup/graphify_baseline.py:292-305`, `sources/graphify.dispositions.json:1-6`, and the pinned expected-extraction record at `python/src/kb_setup/graph.py:537-544`. Full gate and build wall time is **UNVERIFIED** because the task forbids the build and this lane did not run repository gates.

## 5. Ranked recommendation

1. **Rebase the fork onto 0.9.53 first, then run a bounded causal reproduction.** This is the best first move because the actual rebase had no code conflicts, the fork's focused suites passed, and 0.9.51 includes the directly relevant `--force --code-only` scan-mode repair [`ae074b2`](https://github.com/Graphify-Labs/graphify/commit/ae074b21226b7e2be163f6407498a9e37a1d25fc). Do not call the rebase the collision fix yet: generic mixed-path dedup remains unchanged in 0.9.53 ([`dedup.py:348-458`](https://github.com/Graphify-Labs/graphify/blob/v0.9.53/graphify/dedup.py#L348-L458)). The discriminating post-rebase arm should hold the Anthropic pin, parent cwd, nested relative target, flags, and warm existing subgraph constant; compare warning count and retained nodes between the pinned 0.9.50 fork and rebased 0.9.53 fork before attempting all 88 sources. That arm was not run here because it would write a graph and the lane is read-only.

2. **If the bounded 0.9.53 arm still reproduces, fix the fork locally and upstream the regression.** The repair boundary is before dedup's literal path equality: canonicalize `source_file` against the scan root before `_same_source_entity()`/`_report_id_collision()`, or make that equivalence root-aware, while preserving genuinely distinct files ([current ordering](https://github.com/Graphify-Labs/graphify/blob/v0.9.53/graphify/build.py#L1350-L1390), [literal comparison](https://github.com/Graphify-Labs/graphify/blob/v0.9.53/graphify/dedup.py#L348-L458)). The regression must use this missing shape: invoke a nested relative target from its parent cwd over an existing graph and prove that one physical Python file cannot enter dedup under both prefixed and bare forms. Do **not** approve/suppress this warning in `graphify_health`: upstream says the loser is lost ([`dedup.py:451-456`](https://github.com/Graphify-Labs/graphify/blob/v0.9.53/graphify/dedup.py#L451-L456)), and the wrapper intentionally rejects residual stderr (`python/src/kb_setup/graphify_health.py:473-504`).

3. **Do not wait for upstream.** Issue [#2259](https://github.com/Graphify-Labs/graphify/issues/2259) remains the closest tracker item, but the recommendation is based on 0.9.53 source, not its OPEN label: current dedup still compares raw path strings before later normalization ([`build.py:1350-1390`](https://github.com/Graphify-Labs/graphify/blob/v0.9.53/graphify/build.py#L1350-L1390), [`dedup.py:348-458`](https://github.com/Graphify-Labs/graphify/blob/v0.9.53/graphify/dedup.py#L348-L458)). Waiting has no identified commit, release, or schedule to wait for and leaves the intentional fail-closed build blocked.

In short: **rebase first as a cheap, evidence-backed discriminator; if the warning survives, make the path-equivalence fix in the fork; waiting ranks last.**

## GitHub repos touched

- [`ray-manaloto/knowledge-base`](https://github.com/ray-manaloto/knowledge-base) — local wrapper, health gate, pins, manifests, and derived graph evidence.
- [`Graphify-Labs/graphify`](https://github.com/Graphify-Labs/graphify) — upstream tags, releases, commits, source, tests, issues, and pull requests.
- [`ray-manaloto/graphify`](https://github.com/ray-manaloto/graphify) — pinned fork commits and rebase source range.
- [`anthropics/anthropic-sdk-python`](https://github.com/anthropics/anthropic-sdk-python) — pinned local source clone and its read-only derived subgraph/manifest artifacts; no upstream page content was needed.
