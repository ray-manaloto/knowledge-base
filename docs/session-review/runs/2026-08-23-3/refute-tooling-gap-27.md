# Refutation lane — finding 27 (tooling-gap): kb-gates already filters

Judged claim: `mise run kb-gates -- <task>...` already runs a filtered subset
(real rc, live stdio, durable artifact), but the session hand-rolled the
redirect-and-tail wrapper on bare lint/test 6 separate times instead.

## Probes run (as they happen)

### P1 — read the cited source anchor
`sed -n '1000,1060p' python/src/kb_setup/gates.py`
-> line 1037 (NOT 1029): `tasks = tuple(a for a in args if not a.startswith("-")) or GATE_TASKS`
-> line 139: `GATE_TASKS = ("lint", "test", "brain-audit", "eval", "graph-size", "hk-test")` — SIX gates, not four.
Cited line number 1029 is off by 8; the code at 1029 is `_FLAGS = frozenset({"--stop"})`.

### P2 — mise.toml anchor
`sed -n '1160,1185p' mise.toml` -> `[tasks.kb-gates]` block begins at line 1170, `run = "uv run kb-setup gates"` at 1183. Cited range 1170-1176 is the description+comment head, not the run line. Anchor is approximately right.

### P3 — NEGATIVE CONTROL ARM (does the filter arg reach the code at all?)
```
$ mise run kb-gates -- notarealgate
[kb-gates] $ uv run kb-setup gates notarealgate
kb-gates: gate(s) not declared in mise.toml: notarealgate (78 tasks declared)
[kb-gates] ERROR task failed
PIPESTATUS(zsh)=2
```
Args DO pass through the mise task; rc=2 on a bad request. The probe discriminates.

### P4 — transcript recount
`grep -n "mise run lint" allcmds_full.txt` -> lines 132, 370, 466, 615 (4)
`grep -n "mise run test" allcmds_full.txt` -> lines 466, 601, 613 (3)
=> 7 gate invocations across 6 distinct Bash calls. "6 separate times" = 6 CALLS. Consistent.

### P5 — CONTRADICTION FOUND IN THE CLAIM'S WORD "instead"
`grep -n "kb-gates" allcmds_full.txt` -> line 715 (one hit):
`... echo "=== gates on the clean tree ==="; mise run kb-gates > .../gates.log 2>&1; echo "KB-GATES rc=$?"; tail -20 .../gates.log`
The session DID reach for `mise run kb-gates` — once, unfiltered, at call 715 (after all six).
So it is false that the session used the hand-rolled wrapper "instead" of kb-gates throughout;
it used kb-gates for the final full pass and hand-rolled the six intermediate ones.
ALSO: that kb-gates call is itself wrapped in the same redirect-and-tail shape, so the
"redirect-and-tail wrapper" habit is not what kb-gates replaces.

### P6 — was the filter feature even AVAILABLE when those 6 calls happened? (anachronism check)
```
$ git log -S 'or GATE_TASKS' --oneline -- python/src/kb_setup/gates.py | tail -5
77661a36 feat(gates): kb-gates — run the gates and record what actually happened (#146) (#155)
$ git log -1 --format='%ci %s' 77661a36
2026-08-04 01:20:18 -0500 feat(gates): kb-gates ...
```
Shipped 2026-08-04, 18 days before this session. NOT anachronistic. This was my
strongest refutation avenue and it closed.

### P7 — the code's own docstring names the exact form the finding recommends
python/src/kb_setup/gates.py:328 (`_invoke` docstring):
"It stays OFF for a lone gate so `kb-gates -- lint` is byte-identical to what it printed before."
The author documents `kb-gates -- lint` as first-class. Premise (a) is not just
inferable from the code, it is stated by it.

### P8 — POSITIVE CONTROL ARM (does the filtered form actually run only that gate?)
```
$ mise run kb-gates -- brain-audit
[kb-gates] $ uv run kb-setup gates brain-audit
==> gate: brain-audit
[brain-audit] $ uv run kb-setup brain audit
[brain] audit ok: 1 record(s), all closed
PASS  gate brain-audit rc=0
gates at e82708d97826
  brain-audit  PASS
1 passed, 0 failed
recorded: .../\.agent/kb/gates/gates-e82708d9782617cdd5fb132c8ab0033b545fd3ed.json
RC=0
```
Real rc, live inherited stdio, durable artifact. All three claimed properties hold.

### P9 — the finding's own recommendation carries an unstated hazard (NEW)
A second filtered run at the SAME sha REPLACES the record; it does not merge.
```
$ mise run kb-gates -- graph-size   # same HEAD as P8
$ cat .agent/kb/gates/gates-e82708d97826....json
{"sha": "e82708d9...", "recorded_at": "...18:21:39...",
 "gates": [{"task": "graph-size", "rc": 0, ...}]}
```
The brain-audit row from P8 is GONE. So had the session followed the finding
literally — `kb-gates -- lint` then `kb-gates -- test` at one commit — the
durable artifact would record only the LAST gate, and a later full 6-gate record
at that same sha would be destroyed by any subsequent single-gate check.
This does not refute the finding (it never claims accumulation), but it qualifies
the remedy.

### P10 — session's own full kb-gates run, verbatim tail of its log
```
gates at 4f2193e9c846
  lint PASS / test PASS / brain-audit PASS / eval PASS / graph-size PASS / hk-test PASS
6 passed, 0 failed
recorded: .../.agent/kb/gates/gates-4f2193e9c846f0892460dbc68dba4342f2860274.json
```
So the round DID leave a durable gate artifact. "discarding the evidence into an
ephemeral scratchpad EACH TIME" is true of the six, false of the round.

## Cross-finding check
- Finding 5 ("5 lint runs, 4 full test runs") CORROBORATES: 4 bare lint + 1 inside
  kb-gates = 5; 3 bare test + 1 inside = 4. The two findings reconcile exactly.
  (Finding 5's "3 kb-check runs" does NOT: `grep -c "mise run kb-check"` = 5,
  at lines 462, 464, 600, 771, 772. That is a defect in 5, not in 27.)
- Finding 29 ("piped into tail, rc discarded, 2 times") is DISJOINT: all six of
  27's calls use `> log 2>&1; echo rc=$?`, which preserves rc. 29's two are the
  kb-check pipes at lines 771/772 (462 captures ${pipestatus[1]}). No contradiction.

## Verdict
NOT REFUTED. Premise verified by source, by the author's own docstring, and by a
two-arm live probe. Corrections owed: the source anchor is gates.py:**1037**, not
1029 (1029 is `"""`); mise.toml's run line is **1183** (1170 is `[tasks.kb-gates]`);
GATE_TASKS is **six** gates (gates.py:139); and "instead" overstates — kb-gates was
used once, unfiltered, at transcript line 715.

## Cleanup
`.agent/kb/gates/gates-e82708d9782617cdd5fb132c8ab0033b545fd3ed.json` did not exist
before my probes (P8/P9 created it). Removed to restore pre-probe state — it
asserted "gates at e82708d9: graph-size PASS" for a commit nobody actually gated.

## GitHub repos touched

_None._
