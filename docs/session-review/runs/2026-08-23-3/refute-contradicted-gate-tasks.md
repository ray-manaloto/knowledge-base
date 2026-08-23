# Refutation attempt — "GATE_TASKS says four, tuple has six"

Commit under review: HEAD = 24d11e49c946e13a9ff1f610d3ab1ac7f8d3abd4 (tree clean on both cited files).

## Probe 1 — runtime count, from the module the repo actually imports
```
$ uv run python -c "import kb_setup.gates as g; print(g.__file__)"
/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/python/src/kb_setup/gates.py
$ uv run python -c "from kb_setup.gates import GATE_TASKS, CONCURRENT_SAFE; ..."
GATE_TASKS len= 6 ('lint', 'test', 'brain-audit', 'eval', 'graph-size', 'hk-test')
CONCURRENT_SAFE len= 4 ['brain-audit', 'graph-size', 'lint', 'test']
docstring says four: True
```
Right-artifact check: the imported path IS the repo file, not a site-packages copy.

## Probe 2 — the two cited prose sites, verbatim
gates.py:419 (inside the docstring of `_run_batch`, which begins at :405):
    "It is reachable on the ship path, since all four `GATE_TASKS` are one batch."
.claude/rules/verify-before-advancing.md:22:
    "**Always (any code/config/docs change):** `mise run kb-gates` runs all four and"
followed by four bullets naming only lint / test / brain-audit / eval.

## Control arm (proves the probe can return AGREE)
Same check shape — prose number vs the tuple it names — applied to the OTHER
number in the same file: gates.py:146 and :171 say "the four" about
`CONCURRENT_SAFE`, and `len(CONCURRENT_SAFE) == 4`. AGREE. So the
number-vs-tuple probe discriminates; it is not a one-faced coin.
Second control: `grep -rn "brain-audit" .claude/rules/` -> 9 hits, while
`graph-size|hk-test` -> 0 hits in the same directory with the same command shape.

## Cross-route corroboration
- docs/session-review/runs/2026-08-23-1/refute-circles-biggest-circle.md:13
  "both list exactly 6 tasks: lint, test, brain-audit, eval, graph-size, hk-test"
- docs/session-review/runs/2026-08-23-2/handoff.md:7 records a real kb-gates
  artifact with SIX rc rows.

## VERDICT: could not refute. The finding UNDERSTATES the defect.
`_run_batch`'s sentence is wrong TWICE: GATE_TASKS is six, and since
CONCURRENT_SAFE is a strict subset (4 of 6), `eval` and `hk-test` each form
their OWN batch — so "GATE_TASKS are one batch" is false independent of the
count. The docstring's reachability argument for the defect it documents rests
on that false premise.

## Additional probes (run after the verdict, all corroborating)

### Empirical batching — "one batch" is false independently of the count
```
$ uv run python -c "from kb_setup.gates import GATE_TASKS, _batches; print(list(_batches(GATE_TASKS)))"
[('lint', 'test', 'brain-audit'), ('eval',), ('graph-size',), ('hk-test',)]
```
FOUR batches, largest = 3. `graph-size` is IN `CONCURRENT_SAFE` yet still runs
alone, because `eval` sits between it and the others in GATE_TASKS order and
flushes the batch at gates.py:398-400.

### The real artifact at HEAD carries six rows
`.agent/kb/gates/gates-24d11e49c946e13a9ff1f610d3ab1ac7f8d3abd4.json` ->
[('lint',0),('test',0),('brain-audit',0),('eval',0),('graph-size',0),('hk-test',0)]

### A THIRD stale site the finding does not name
python/src/kb_setup/pr.py:21-22:
    "``ship`` then runs every gate in :data:`gates.GATE_TASKS` (``lint``, ``test``,
     ``brain-audit``, ``eval``) BEFORE the branch is pushed"
Four enumerated, six real — and this is the SHIP path, so it is the
highest-consequence of the three. Weaker fourth site:
.claude/skills/goal-engineering/references/rubric.md:90 uses "all four of PASS
gate lint/test/brain-audit/eval" as its worked GOOD example of a named
denominator — a denominator rubric whose own example has the wrong denominator.

### A rule file already CONTRADICTS the docstring
.claude/rules/ci-local-parity.md:70-72: "with `eval` in its own batch,
`stop_on_failure=True` **can** skip it on the ship path ... it is no longer true
that the ship path [runs one batch]". So the repo already recorded that the
_run_batch premise went stale, and gates.py:419 was never updated.

### Staleness dating (git blame)
- gates.py:419 written 2026-08-08 (e53409ed6) — correct then.
- verify-before-advancing.md:22 written 2026-08-04 (77661a36b) — correct then.
- `graph-size` entered GATE_TASKS in 37f6a1c5 (#336); `hk-test` in afb4ad3d (#406).
Both prose sites predate both additions: classic stale-restatement, not an error
of authorship.

### No other live finding contradicts this one
Finding 6 asserts kb-gates "does not stop at the first failure" — confirmed
compatible: gates.py:1038 `stop_on_failure="--stop" in args` (default False),
while pr.run_gates (gates.py:156 of pr.py) passes True on the ship path.
Different call sites, no disagreement with this finding.
