# Cold review — commit 04312f3

Reviewed `git diff origin/main...HEAD -- . ':(exclude)docs/research/**'`
(origin/main = `1ec72c4bea2d85602bf68c239148e777145ca36c`, HEAD = `04312f3`), cold —
no design context was given beforehand.

Method: read, then mutated real code paths (via monkeypatched pytest
reproductions run against the actual `graph.py` functions, not hypothetical
mutants) to test suspicions about ordering, idempotence, and partial-failure
state. Two of three suspicions confirmed by a failing assertion; one was
disproved by reading the installed graphify 0.9.31 source directly (see
"Ruled out" below) rather than assumed.

## Findings, worst first

### 1. [CONFIRMED, HIGH] `kb-watch` silently reverts any `kb-merge`/`kb-label` content that landed after the last `kb-build`, then reports the corrupted graph as verified

**File:** `python/src/kb_setup/graph.py:217` (`refresh_self`), interacting with
`BASE_GRAPH_NAME` written only at `graph.py:408-410`.

**Claim:** `refresh_self()` (the new `kb-watch` task, `mise.toml:978-985`)
unconditionally does `shutil.copy(base, out)` before re-merging the two self
trees. `.base-graph.json` is written **only** inside `build()` — grep of
`python/src/kb_setup/` confirms no other writer touches it, and neither
`_merge_docs.py` (backing `kb-merge`) nor the `graphify cluster`/`label` call
backing `kb-label` update it either. Both of those tasks write
`graphify-out/graph.json` directly and are documented elsewhere in this repo
as legitimate, frequent, no-LLM operations that happen *between* builds.

So: run `kb-build`, then `kb-merge` (adds a doc chunk to `graph.json`), then
`kb-watch` — and `kb-watch`'s first line discards the merged content, because
it restarts from the pre-merge `.base-graph.json` snapshot. `kb-watch` then
calls `_restamp_self` (`graph.py:242`), which updates the currency stamp's
fingerprint to match the *new* (content-losing) `graph.json` — so
`kb-currency-check` reports this corrupted graph as in sync. This is a false
green, not merely a stale-content bug: the one mechanism that could have
caught it (the fingerprint check) is exactly the mechanism `_restamp_self`
launders.

**Failure scenario:** `mise run kb-build` → `mise run kb-merge -- some-chunk.json`
(adds real doc nodes) → `mise run kb-watch` (meant only to refresh
`python/`+`tests/`) → the doc-merge's nodes are gone from `graphify-out/graph.json`,
`graph-prose.json` is re-derived from the now-smaller graph, and
`kb-currency-check` reports clean.

**Verified by mutation**, not just reading: reproduced against the real
`graph.refresh_self` with `_run`/`prose.derive_for` stubbed (the same stubbing
shape the new test suite uses) and real `sync.write_stamp`/`restamp_artifacts`.
Simulated a `kb-merge` by rewriting `graph.json` in place (exactly what
`_merge_docs.py` does) between the stamp and the `kb-watch` call:

```
graph.json before kb-watch: {"nodes": ["ORIGINAL_BUILD_CONTENT", "NEW_DOC_CHUNK_FROM_KB_MERGE"]}
graph.watch runs -> stdout: "[kb-watch] restamped .currency-stamp.json"
                             "[kb-watch] refreshed python/ + tests/ into graphify-out/graph.json"
graph.json after:  {"nodes": ["ORIGINAL_BUILD_CONTENT"], "base": true}
AssertionError: kb-watch silently discarded a kb-merge that ran after the last
kb-build; graph.json now holds '{"nodes": ["ORIGINAL_BUILD_CONTENT"], "base": true}'
```

**Why the new tests don't catch it:** every fixture in `tests/test_graph_self_index.py`
treats `.base-graph.json` as either "doesn't exist yet" or "exists, matches
what `build()` would have written" — none simulates a `kb-merge`/`kb-label`
running in the window between a `kb-build` and a `kb-watch`. That's the "what
can a stub not exhibit" gap the brief asked about: the stub for `_run` records
argv, but nothing in the suite models a *second, independent writer* of
`graph.json` touching the file between build and watch — which is precisely
the real-world case `kb-watch` is meant to be safe to run in (it's pitched as
a one-shot incremental refresh you run "between builds").

### 2. [CONFIRMED, MEDIUM] `refresh_self` is non-atomic: a mid-loop failure leaves `graph.json` in a state strictly worse than before the refresh started, with no rollback

**File:** `python/src/kb_setup/graph.py:217-235`.

**Claim:** `shutil.copy(base, out)` runs first (wiping ALL self-content
immediately, before any new extraction has succeeded), then the loop over
`_SELF_TREES` extracts+merges tree-by-tree directly into `out` on disk. If the
second tree's extract or merge raises (network hiccup, graphify crash,
Ctrl-C — exactly the class of failure `long-running-command-hangs.md` and
`persistence-gate-retry.md` say to expect from these very operations), the
exception propagates out of `refresh_self` before `_restamp_self` runs. What's
left on disk is `base + tree[0]-only`, even though the graph on disk *before*
the refresh had both trees merged and was fully queryable via `affected`.

**Verified by mutation:** stubbed `_run` to write fresh `python` content then
raise on the `tests` merge, starting from a fixture that already had both
`PYTHON_SELF`/`TESTS_SELF` present (a realistic "already built once" state):

```
before: {"nodes": ["BASE", "PYTHON_SELF", "TESTS_SELF"]}
graph.refresh_self(root) raises RuntimeError (simulated crash on the tests merge)
after:  {"nodes": ["BASE", "PYTHON_SELF_FRESH"]}
AssertionError: a mid-refresh failure destroyed previously-working self-index
content with no rollback
```

**Mitigating factor, stated for balance:** the stamp is not rewritten in this
path (the crash happens before `_restamp_self`), so `kb-currency-check` will
correctly report drift rather than a false green — this is the inverse of
finding 1, where the corruption is silent. But `affected` on a `tests/` symbol
goes back to "No unique node match" — the exact regression P1 exists to fix —
until someone notices and re-runs `kb-build` or a successful `kb-watch`.

## Lower-confidence / process notes

### 3. [PLAUSIBLE, MEDIUM] `kb-tool-review.js` treats a dead/skipped verifier agent as "claim survives verification", inverting the documented fail-safe

**File:** `.claude/workflows/kb-tool-review.js:117-124` (verify stage) and
`:132` (review stage).

```js
negatives.map((c) => () =>
  agent(..., { agentType: 'kb-adversarial-verifier', ... })
    .then((v) => ({ ...c, verdict: v })),
),
).then((verdicts) => ({ tool: t, res, verdicts: verdicts.filter(Boolean) }))
...
const surviving = out.verdicts.filter((v) => !v.verdict?.refuted)
```

Per this tool's own documented `agent()` contract, `agent()` **resolves to
`null`** (does not throw) "if the user skips the agent mid-run or the subagent
dies on a terminal API error after retries." When that happens here, `v` is
`null`, `.then(v => ({...c, verdict: v}))` still runs (the promise resolved,
it didn't reject), and the result is `{...c, verdict: null}` — a **truthy
object**. `parallel()`'s own null-collapsing only fires for a thunk that
*throws*; a thunk that resolves to an object containing `verdict: null` is
unaffected, so `verdicts.filter(Boolean)` at line 124 does not remove it.

Then at line 132, `v.verdict?.refuted` on `{verdict: null}` is
`undefined`, so `!undefined` is `true` — the claim is counted as
**surviving**, and it is *not* counted toward `refuted` at line 145 either.

This is the opposite of the stated design: every adjacent doc in this same
diff (`kb-adversarial-verifier.md:16-18`, the workflow's own prompt at
`kb-tool-review.js:443-444`) says "Default to `refuted: true` when you cannot
establish the claim" specifically because unrefuted absence-claims have been
wrong before in this repo. But that default is written into the *agent's own
reasoning*; the orchestrating script has no equivalent default for the case
where the agent process itself never produced a verdict at all. A verifier
that dies is silently treated as a verifier that agreed.

I could not execute this script (Workflow scripts aren't unit-testable via
pytest and I was not asked to invoke the real Workflow tool), so this rests on
reading the documented `agent()`/`parallel()` contract rather than an observed
failure — hence PLAUSIBLE rather than CONFIRMED. The failure mode is real
infrastructure behavior (agent timeouts / terminal API errors happen), and the
consequence — a false-negative on exactly the claim class this repo has been
burned by twice before (LM Studio, graphify #959) — is high enough to flag
even unverified.

## Ruled out (checked, not a bug)

- **`except OSError, json.JSONDecodeError:`** at `graph.py:97` (pre-existing,
  not touched by this diff — confirmed against `origin/main`'s copy of the
  same line). Looks like Python-2-style multi-except syntax at a glance, but
  `ast.parse` confirms Python 3 parses a bare comma there as a tuple literal,
  making this equivalent to `except (OSError, json.JSONDecodeError):`. Not a
  defect; flagging only because it's easy to mis-flag on a skim.
- **`_extract_self`'s "emptiness is not tolerated" claim** (`graph.py:157-163`):
  verified against the installed, pinned 0.9.31 `graphify/cli.py` — the
  clustered extract path (no `--no-gitignore`/`--no-cluster` involved here)
  does `sys.exit(1)` before writing `graph.json` when the merged graph has 0
  nodes (`cli.py:3558-3565`), and does not write the file in that case. So
  `_run`'s `check=True` genuinely does catch an empty self-extraction, as
  claimed. This also means `_extract_code`'s separate manual node-count check
  is defensive-but-consistent, not evidence the exit code is unreliable.
- **`kb-manifest-add` has no `--scope` flag** (`manifest.py`'s `NewSource`/`add()`):
  real gap (the three new peer-tool manifests could not have been created with
  `scope = study` via that task alone; the field must be added by hand after
  `kb-manifest-add`, or the manifest hand-written), but it matches how the new
  `kb-corpus-curator.md` agent already documents the workflow ("`scope = corpus`
  … or `scope = study` **in the manifest**" — i.e., an edit-the-file step, not
  a flag). Not reported as a finding since it's a documented two-step process,
  not a break; noting it here so it isn't rediscovered as a surprise.
- **Build-time ordering** (`build()`, `graph.py:370-419`): the study/corpus
  partition happens before the seed is chosen (so a study repo can never seed
  the aggregate by sorting first), and the base snapshot is taken after every
  external contribution and before the self-merge. Both invariants hold by
  inspection and match the new tests in `test_graph_study_scope.py` /
  `test_graph_self_index.py`, which do exercise these specific orderings
  (`test_a_study_source_never_seeds_the_corpus_graph`,
  `test_build_snapshots_a_base_that_excludes_our_own_code`).

## Total

**3 findings: 1 CONFIRMED-HIGH, 1 CONFIRMED-MEDIUM, 1 PLAUSIBLE-MEDIUM.**
Worst: finding 1 (`kb-watch` silently reverts `kb-merge`/`kb-label` content and
restamps the corrupted graph as verified) — it defeats the exact safety
mechanism (`kb-currency-check`) this repo relies on to catch this class of
problem, and the round's own memory entries (proving 3 flat `kb-watch` runs
with identical node counts) never exercised the interleaving that triggers it.
