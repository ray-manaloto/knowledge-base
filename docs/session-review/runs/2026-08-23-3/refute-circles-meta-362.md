# refute — lane `circles`, finding 1 ("THE META-CIRCLE: #362")

Verdict: **REFUTED (partially — the causal core and the trend predicate fail;
a narrower residue survives).**

## What holds up

| sub-claim | probe | result |
|---|---|---|
| #362 OPEN, filed 2026-08-18, 0 comments, P1/directive/circle | `gh issue view 362 --json ...` | `{"c":"2026-08-18T21:02:19Z","l":["P1","directive","circle"],"n":362,"nc":0,"s":"OPEN"}` — TRUE |
| named in exactly ONE handoff | `grep -n '362' .agent/plans/*.md` | one real hit: `session-2026-08-21.md:165`. The other two hits (`21-b:148`, `21-c:5`) are substrings of a SHA and a URL. Control `grep -c '#397'` fires in 11 files — probe discriminates |
| the reconcile module has no age/consecutive counting | `grep -n -i -E 'carried\|consecutive\|\bage\b\|round' handoff_reconcile.py` | zero `consecutive`, zero standalone `age`; control `grep -c 'def '` = 14 — TRUE |
| `pinact` / `advisor-strategy` in 5 of 6 in-scope handoffs | per-file `grep -c -i` | 20-d/21/21-b/21-c/22 = 1,1,2,1,1; **22-b = 0**; control `zebra` = 0 in all six |
| the CARRIED table | reproduced ONLY as `grep -oi carried` | 15, 7, 24, 21, 51, 19 — matches the lane exactly. `grep -c CARRIED` (case-sensitive, lines) gives 13, 3, 16, 14, 25, 11 |

## What does not

**1. "the problem it describes got worse in every round after it" is refuted by
the lane's own numbers.** 15 -> 7 -> 24 -> 21 -> 51 -> 19. It falls in three of
the five transitions, and the newest round is **63 % BELOW** the prior one. No
monotone worsening exists in the offered evidence.

**2. The metric is confounded and points the wrong way.** `grep -oi carried`
counts the English word — including prose ("carried unfixed from earlier",
"seven real losses carried one") and the reconcile VERDICT token. It measures
how much a handoff USES reconciliation vocabulary, not how many items are
stale. A handoff that silently dropped its whole backlog scores **zero**.
Demonstration inside the lane's own six: `session-2026-08-21.md` scores the
LOWEST (7) and is the ONLY handoff that names #362 at all.

**3. The named mechanism is wrong for the three named exemplars.** `pinact`,
`advisor-strategy` and `SIXTH ADDENDUM` are absent from `session-2026-08-22-b.md`
entirely (`grep -ci` = 0 for all three) — they were not "carried"; they were
silently DROPPED. And the gate is silent about them for a different reason than
the one given: in `session-2026-08-22.md` they sit under `## 6. RECONCILIATION`
(lines 113, 124), while `handoff_reconcile.py:47-49` states "It reads the OWED
and GOTCHA sections only. A commitment buried in narrative prose is out of
scope". So the silence is a SCOPE hole, not "a verdict of CARRIED satisfies it".

Control arm that this negative is real, not a dead probe — reconcile rows per
handoff across all 30 handoffs:

```
session-2026-08-17-g.md   reconcile_rows=14 | 24 OK, 7 ambiguous, 0 unverifiable, 7 broken
session-2026-08-16-c.md   reconcile_rows=13 | 31 OK, 3 ambiguous, 0 unverifiable, 10 broken
session-2026-08-18-b.md   reconcile_rows=8  | 24 OK, 4 ambiguous, 0 unverifiable, 4 broken
...
session-2026-08-22-b.md   reconcile_rows=0  | 34 OK, 7 ambiguous, 1 unverifiable, 1 broken
```

**4. "35 OK / 0 broken" is already false.** Re-run at HEAD `e82708d97826`:
`34 OK, 7 ambiguous, 1 unverifiable, 1 broken`, rc=1 — the FAIL is the handoff's
own HEAD claim, invalidated by a commit the same round made (lane finding 4's
dirty tree). And that tally is `handoff.check`'s CLAIM-verification count; the
reconcile check contributes rows to it only in the FAIL direction
(`handoff.py:903-955`), so "35 OK ... because a verdict of CARRIED satisfies it"
mis-attributes the number.

**5. "none of the five since" — there are FOUR.** Handoffs strictly after
`session-2026-08-21.md`: `21-b`, `21-c`, `22`, `22-b`.

**6. "NINTH deferral" is an inherited number.** 11 handoff files name SIXTH
ADDENDUM (19-c .. 22); auto-memory records "deferred 7x". Neither yields nine.
Unverified as stated.

## Cross-finding

No live finding contradicts this one. Findings 8/9/16/17 (stale CLAUDE.md pin,
#446's premise) are independent instances of the same carrying behaviour and
support the residue. Finding 4 (dirty tree, mid-lane edits) EXPLAINS why the
`35 OK / 0 broken` figure no longer reproduces.

## Durable residue (what a rewritten finding should say)

#362 is OPEN with zero comments, is named in one of thirty handoffs, and
`handoff_reconcile.py` carries no per-item age or consecutive-round counter
(0 hits for `consecutive`, control 14 `def `). Beyond that, the reconcile gate's
real hole is narrower AND worse than the lane claimed: items reconciled under a
`## RECONCILIATION` heading are outside the module's stated scope, so they can
vanish without a single reconcile row — which is exactly what happened to
`pinact`, `advisor-strategy` and SIXTH ADDENDUM in `session-2026-08-22-b.md`.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — issues #362, #437 read via `gh`
