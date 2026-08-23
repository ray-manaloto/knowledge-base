# Refute lane: "graphify semantic-corpus campaign is a 5-day circle with ZERO output"

## Reproduced (claim's own numbers hold)
- `git log --format='%h %ad' --date=short -- 'python/src/kb_setup/graphify_semantic*'` -> 10 commits, 2026-08-14(5)/15(1)/17(3)/18(1). MATCHES.
- `wc -l python/src/kb_setup/graphify_semantic*.py python/src/kb_setup/graphify_baseline.py` -> 10343 total. MATCHES.
- `ls sources/extractions/*.json | wc -l` -> 25; `ls sources/extractions/ | grep -c corpus` -> 0. MATCHES.
- Session 52f5798a: first ts 2026-08-18T03:12:34.315Z, last 08:07:48.759Z = 4h55m14s. MATCHES "4h55m".
- 4 full `kb-arms -- .agent/kb/arms/corpus-chunk1-findings.toml` runs at 04:57:39, 05:26:21, 06:15:28, 07:05:27Z (+ a --dry-run 05:26:16). Span 2h07m48s. MATCHES "4 times" / "2h08m" as a WINDOW.

## The defect: wrong artifact + elapsed-as-spent
1. `sources/extractions/` is NOT where the corpus campaign writes. Its output goes to
   `graphify-out/graphify-semantic-corpus-chunks/<run>/chunks/NNNN/receipt.json` (untracked by design,
   `.claude/rules/clean-git-state.md`: "retained provider evidence for a run that cost real tokens ... #317").
   The probe `ls sources/extractions/ | grep -c corpus` could ONLY return 0.
2. Real provider chunks WERE produced inside this very window (transcript 05:59:59 / 06:01:01 poll on
   `graphify-out/graphify-semantic-corpus-chunks/*/chunks/0001/receipt.json`; 06:00:36 `find ... -maxdepth 1 -type d`).
3. The 2h08m window is not 2h08m of arms: 06:38-06:47 authored `docs/direction/2026-08-18-ray-directives.md`,
   `python/src/kb_setup/stage_explicitly.py` + `tests/test_stage_explicitly.py` + hook_guard wiring — a shipped
   feature unrelated to the arms spec.

## VERDICT: REFUTED (the headline "zero output" is false; the durable core survives)

### 1. Real corpus output WAS produced, in this very round — it was REJECTED, not absent
Transcript 52f5798a, tool_result 2026-08-18T06:06:53.198Z, verbatim:
`namespace: becea9584e02cc92 (new plan = 5ca6c19b56d7c7ee) | status: failed | nodes: 119 edges: 221 hyper: 3 |
 reasons: ['provider-prompt-bytes-mismatch'] | IN-SCOPE: 119 | OUT-OF-SCOPE: 0 | planned covered:
 ['.pre-commit-config.yaml','AGENTS.md','ARCHITECTURE.md','BENCHMARKS.md','CHANGELOG.md'] | missing: [] |
 === SPEND LEDGER: graphify-out/graphify-semantic-corpus-chunks/becea9584e.../spend-ledger.json:
 {"total_usd":1.3249605000000002,"charges":1,"schema_version":1}`
Prior run, 06:00:20.929Z: `status: failed | nodes: 109 | edges: 151 | hyper: 3 |
 reasons: ['fragment-source-scope-mismatch','fragment-source-coverage-mismatch']`.
Cross-check (second route, committed artifact): `graphify-out/memory/query_20260818_075913_*.md:57`
 "chunk 1 cost **$1.32**, recorded, so 58 chunks projects to ~$77" and `:41` "Chunk 1 attributed 61 of 109 nodes".
=> The campaign is not spinning with nothing to show. It produced real, paid-for semantic extraction that its OWN
   authority gate refused to authorize. Different diagnosis, different remedy.

### 2. "25 committed chunks, ZERO corpus-derived" asks the wrong artifact (vacuously true)
`git log -1 --format='%ad' --date=iso -- sources/extractions/` -> **2026-08-07 17:43:15 -0500**.
Campaign's first commit: 2026-08-14 (67f7ef0b). All 25 predate the campaign by 7 days; none COULD be corpus-derived.
CONTROL ARM on the probe shape: `ls sources/extractions/ | grep -c docs` -> 25 (non-zero), `grep -c corpus` -> 0.
Every file there is `<name>-docs.json`; the campaign writes to `graphify-out/graphify-semantic-corpus-chunks/`,
and only a merge step that never ran would land anything in `sources/extractions/`.

### 3. "spent 2h08m ... re-running one kb-arms spec 4 times" = elapsed window, not spent time
04:57:39 -> 07:05:27 is the window. Inside it, unrelated to the arms spec:
 06:41:16 Write `docs/direction/2026-08-18-ray-directives.md`; 06:44:12 Write
 `python/src/kb_setup/stage_explicitly.py`; 06:44:48 Write `tests/test_stage_explicitly.py`;
 06:44:20/06:44:26/06:45:24 Edit `python/src/kb_setup/hook_guard.py` — a shipped guard feature.
 Plus AskUserQuestion at 06:38:44 and 06:42:11, two commits (05:58:56, 06:37:53), and the two paid corpus runs above.

### 4. Scope mismatch inside the evidence
`graphify_baseline.py` = 1,865 of the 10,343 lines (18%) but is NOT matched by the `graphify_semantic*` glob that
produced "10 commits". Widened glob (`graphify_semantic*` + `graphify_baseline*` + `tests/test_graphify_semantic*`)
-> 11 commits. Two different scopes reported as one measurement.

### What SURVIVES (do not discard)
- 10,343 lines / ~11 commits / 2026-08-14..18: reproduces exactly.
- ZERO merged: `graphify-out/graph.json` mtime **Aug 12 06:12**, campaign output Aug 17-18 -> the graph predates
  every artifact the campaign produced. Nothing is in the corpus.
- 4 full runs of ONE spec `.agent/kb/arms/corpus-chunk1-findings.toml` at 04:57:39/05:26:21/06:15:28/07:05:27Z.
- Session 52f5798a = 03:12:34.315Z -> 08:07:48.759Z = 4h55m14s.

### Contradictions with the rest of the set
None contradicts. #23 (`_result_envelope` dead in graphify_semantic_adapter.py, flagged on two PRs, never removed)
CORROBORATES the machinery-accretion half. Note a method inconsistency in the same lane: #5 carefully separates
blocked time from elapsed ("nothing dispatched in the background"); #3 does not, and reports a window as spend.
