# Refutation probe — "four advisory detectors ran 0x" (lane: circles)

## Claim
kb-distill / kb-session-reflect / kb-insights / kb-skill-lint are "four advisory
detectors" invoked ZERO times in 22h; gates ran 54x. Root cause of circles 2-6.

## Findings so far (as of first pass)

1. **kb-skill-lint is NOT advisory. It is an hk lint step, enforced.**
   `hk.pkl:346-348`:
   ```
   ["skill_lint"] = new Step {
     check = "uv run kb-setup skill-lint"
   }
   ```
   It lives in `lintSteps`, and `hooks["check"].steps = lintSteps` /
   `hooks["pre-commit"]` also use it (hk.pkl ~L350-360). `mise.toml [tasks.lint]
   run = "hk run check --all"`. So every `mise run lint` and every `git commit`
   executes it. In the round's own command log: `mise run lint` = 14,
   `mise run kb-gates` = 30 (gates.py:131 GATE_TASKS includes "lint"),
   `git commit` = 23.

2. **The claim's supporting grep named a FILE THAT DOES NOT EXIST.**
   Evidence offered: `grep -n "distill|session-reflect|insights|skill-lint"
   python/src/kb_setup/gates.py python/src/kb_setup/ship.py -> no matches`.
   There is no `python/src/kb_setup/ship.py` (ls of the package below); ship
   lives in `pr.py`. Half that probe could only ever return nothing.

3. **Token spelling.** gates.py DOES contain `skill_lint` (underscore),
   gates.py:989, invisible to a `skill-lint` (hyphen) grep. (Docstring
   reference only — not wiring — but it shows the probe's spelling bound.)

## Decisive probes (run 2026-08-19)

### A. The detector RAN — `mise run lint` executes it
```
$ mise run lint   # rc=0
❯ skill_lint
  skill_lint – 821 files –  – uv run kb-setup skill-lint
  skill_lint – skill-lint: 24 skill(s) checked; every instructed command is a
               mise task or allowed read-only
✔ skill_lint
```
Control arm on the SAME output: `grep -ci "distill\|insights\|session.reflect"
lintout.txt` -> **0** (21 `✔` steps total). So the probe discriminates: it shows
skill_lint present and the other three absent from the lint suite.

### B. mise.toml says so in its own comment — mise.toml:349-356
```
[tasks.kb-skill-lint]
description = "Check every SKILL.md instructs mise tasks, not raw commands (#128)"
# ...
# Also an hk step, so `mise run lint` covers it; this task is the direct handle
# for working on a skill without running the whole suite.
run = "uv run kb-setup skill-lint"
```
A 0-count of the *convenience handle* is not a 0-count of the *detector*.

### C. How many times it ran in the window
`.agent/kb/gates/*.json` with an Aug 18/19 mtime carry **26** rows
`{"task":"lint","rc":0,...}` (control: `select(.task=="test")` -> 26,
`select(.task=="lintX")` -> 0). Plus 14 direct `mise run lint` and 23
`git commit` (pre-commit hook = `mise x -- hk run pre-commit`,
`.git/hooks/pre-commit`, installed, mtime Aug 19 12:30) in the round's own
command log. Floor: >=26 executions, not 0.

### D. The causal claim is contradicted by the round's OWN issue #349
`gh issue view 349` body, verbatim:
> **`mise run kb-session-reflect` RAN the same morning** (07:59:43Z, session
> `52f5798a`) ... **The root cause is therefore NOT non-execution — the tool
> ran, was right, and nobody read it.**

The finding cites #349 as support while asserting the opposite root cause.

### E. The offered grep named a file that does not exist
`python/src/kb_setup/ship.py` is absent (ship logic is `pr.py`); `ls
python/src/kb_setup/` confirms. ugrep prints
`warning: python/src/kb_setup/ship.py: No such file or directory` to stderr and
matches nothing. Half that probe could only return "no matches".
Spelling bound too: gates.py:989 contains `skill_lint` (underscore), invisible
to a `skill-lint` (hyphen) grep.

## What SURVIVES
kb-distill, kb-session-reflect and kb-insights are genuinely absent from the
lint suite and from gates (control-armed in A), and their 0-counts in the window
stand. The 3/4 core is fine; the 4/4 headline, the "advisory" classification of
kb-skill-lint, and the non-execution root cause are not.

## Probe hygiene note
My own first sweep (`for t in ...; do grep -l -- "$t" $F; done`) returned 0 for
ALL ten tokens including the known-positive control `kb-gates`; a direct
`grep -c "kb-gates" <file>` returned 48. One broken probe, ten false zeros.

## Contradiction with another live finding
Finding 2 states "18 gate runs" for the round; finding 1 states `mise run
kb-gates` = 28. My independent count: 28 `.agent/kb/gates/*.json` files with an
Aug 18/19 mtime, 26 carrying a `lint` row. Reconcilable (files are keyed by SHA
and overwritten, so invocations >= distinct-SHA artifacts), but the two numbers
are not the same measurement and neither says which it is.

VERDICT: refuted = true (the 4/4 count, the classification and the causal claim).
