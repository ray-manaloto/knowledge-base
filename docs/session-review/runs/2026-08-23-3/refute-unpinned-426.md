# Refute lane: "#426 P0 blocker: _ACCEPTED_GRAPHIFY_RUNTIME frozen at 0.9.47 while 0.9.48 installed"

Branch at probe time: corpus-gate-bundle-0821, HEAD b30a80c9.

## Probe 1 — grep the constant (primary artifact)

`grep -rn "_ACCEPTED_GRAPHIFY_RUNTIME|ACCEPTED_GRAPHIFY|accepted_graphify" --include=*.py --include=*.md --include=*.toml --include=*.json .`

- `python/src/kb_setup/graphify_semantic_corpus.py:147` -> `_ACCEPTED_GRAPHIFY_REF = "v0.9.48"`
- `python/src/kb_setup/graphify_baseline.py:227` -> `_ACCEPTED_GRAPHIFY_VERSION = "0.9.48"`
- `_ACCEPTED_GRAPHIFY_RUNTIME` does NOT exist in graphify_semantic_corpus.py at all; it lives at
  `graphify_semantic_slice.py:340`.

## Probe 2 — the cited lines 185-194 of graphify_semantic_corpus.py

Those lines are now a comment block about the v0.9.47 detect-object diff, and `_measured_runtime()`
(line ~218) whose own docstring says verbatim:

    A frozen `_ACCEPTED_GRAPHIFY_RUNTIME` literal used to stand where this
    function's result now flows: ... It went stale exactly once — 0.9.48 installed
    against a 0.9.47 literal — before anything caught it, because nothing ever
    recomputed it.

=> the finding describes a defect the repo ALREADY FIXED (d8114ab1 "derive the plan's Graphify
runtime instead of freezing it (#426)").

(in progress)

## VERDICT: REFUTED

### Probe 3 — control-armed grep for a LIVE 0.9.47 assignment
```
grep -rnE '^[^#]*(=|:)\s*"v?0\.9\.47"' python/     -> 0 hits
grep -rnE '^[^#]*(=|:)\s*"v?0\.9\.48"' python/     -> 10 hits (CONTROL: probe discriminates)
```
All 28 `0.9.47` occurrences in `python/` are comments/history, none an assignment.

### Probe 4 — run the thing (the strongest arm)
```
$ mise run kb-graphify-semantic-corpus -- verify
{"execution_authorized":false,"reasons":["typed-member-invalid"],"state":"failed","structural_complete":false}
```
The claim's harm chain requires "verify passes". It does not pass. `execution_authorized:false`.

### Probe 5 — the ORIGINAL probe, re-pointed: it can only have returned its answer
```
$ git show d8114ab1^:python/src/kb_setup/graphify_semantic_corpus.py | sed -n '180,200p'
185:_ACCEPTED_GRAPHIFY_RUNTIME = graphify_baseline.RuntimeIdentity(
186:    version="0.9.47",
```
Byte-exact match for the cited "graphify_semantic_corpus.py:185-194 declares version 0.9.47".
The finding read the PARENT of the fix. `origin/main` (8929d47f) still carries it at line 185:
```
$ git show origin/main:python/src/kb_setup/graphify_semantic_corpus.py | grep -n '_ACCEPTED_GRAPHIFY_RUNTIME'
185:_ACCEPTED_GRAPHIFY_RUNTIME = graphify_baseline.RuntimeIdentity(
```
=> WRONG ARTIFACT. `git merge-base --is-ancestor d8114ab1 HEAD` -> "d8114ab1 IS an ancestor of HEAD",
and HEAD's branch corpus-gate-bundle-0821 is this round's own branch (finding 43).

### Probe 6 — SECONDARY SOURCE trap
`gh issue view 426` -> state OPEN, title still says "frozen at 0.9.47 ... would burn ~$65 and stage
58/58 chunks failed". Issue open != unfixed; d8114ab1's message names (#426) and describes the
defect in the past tense.

### Probe 7 — MUTATION ARM (is the fix vacuous?)
Reintroduced the exact original defect: replaced `_measured_runtime`'s body
(`return graphify_baseline.runtime_identity(repo_root)`) with the verbatim frozen 0.9.47
`RuntimeIdentity` from d8114ab1^. Bytes confirmed changed at that line (`git diff --stat` -> 9 ins/1 del).

- MUTANT: `tests/test_graphify_semantic_corpus.py::test_plan_records_the_measured_graphify_runtime_not_a_frozen_literal` FAILED
  (`assert config.graphify_runtime == measured`; 0.9.47 vs 0.9.48)
- RESTORED (tree clean, `git status --short` empty): same test PASSED.

The test binds to an EXTERNAL anchor (`graphify_baseline.runtime_identity` + uv.lock), not a
pasted copy — so it is not the self-consistency shape that survived a revert in a past round.

## RESIDUAL (true, but not the claim)
`graphify-out/graphify-semantic-corpus/execution-config.json` (mtime 2026-08-20 22:23, i.e. PRE-fix)
still records `"graphify_version":"0.9.47"` and `"graphify_runtime":{"cli_version":"0.9.47"...}`
against `"graphify_ref":"v0.9.48"`. That is a stale PLAN ARTIFACT — but it is now DETECTED
(`plan-graphify-runtime-mismatch`, graphify_semantic_corpus.py:1962) rather than silently accepted,
and verify refuses anyway. Re-plan is required before execution; that is finding 10's deferral,
not a live P0 spend risk.

## BONUS DEFECT (unrelated to the claim, found while arming)
`tests/test_graphify_semantic_corpus.py::test_recorded_authority_authorizes_this_plan_and_only_this_plan`
FAILS at CLEAN HEAD b30a80c9 (tree verified clean):
`reasons=('plan-authority-mismatch','cost-advisory-review-required','provisional-input-decisions')`.
No runtime reason among them. Not caused by my mutation; pre-existing.

## Contradictions with the finding set
- Finding 35 corroborates the refutation half-way: it calls the "~$65 / 10.6h / 58 chunks"
  figure "a prediction ... stated as accomplished fact though the run never executed". The finding
  under judgment restates that same unverified prediction as the P0's cost.
- Finding 43 confirms corpus-gate-bundle-0821 is this round's branch with 7 unlanded commits — the
  branch that CARRIES the fix. Reading the constant off `main` while the round works on that branch
  is the artifact mismatch.
- No finding in the set asserts the freeze is still live.

## GitHub repos touched
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under review; issue #426.
