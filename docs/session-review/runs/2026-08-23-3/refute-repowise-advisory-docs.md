# Refutation lane: "Repowise advisory reversal exists only in gitignored artifacts"

Lane: refute-repowise-advisory-docs · 2026-08-18 · commit at start: docs-directive-addendum @ 3d957f15

## FINDING UNDER TEST
"Tracked docs present CodeRabbit as THE advisory check while the code has two ...
'Repowise' appears in zero tracked docs ... the only durable prior art records Ray's
#331 ruling 'investigate, do NOT reclassify as advisory', so the reversal exists only
in gitignored artifacts."

## Probe 1 — unbounded `git grep -in repowise` over ALL tracked files (2026-08-18)

REFUTES the "zero tracked docs" and "reversal only in gitignored artifacts" claims.
6 tracked files match (original probe searched only rules+CLAUDE.md+kb-review SKILL — a BOUND):

- `docs/direction/2026-08-18-ray-directives.md:77` — tracked DOC, records the reversal
  explicitly: "`Repowise / code health` was made advisory on #336."
- `docs/research/README.md:86` — tracked DOC, long Repowise paragraph (#331 round).
- `python/src/kb_setup/pr.py:75-94` — 19-line tracked doc-comment: "`Repowise / code
  health` joined 2026-08-17 **on Ray's ruling**", with the full rationale (advisory
  because of what it MEASURES) and the stated COST (no PR blocks on code health again;
  C901/PLR0915 are the binding backstop).
- `tests/test_pr.py:1040` — `test_repowise_health_is_advisory_but_still_reported`.
- `graphify-out/memory/query_20260816_031844_*.md` (PR #325) and
  `query_20260817_115929_*.md` (PR #331) — COMMITTED memory.

Control arm: same grep shape for `coderabbit` → 20 tracked files. The probe discriminates.

## Probe 2 — the three cited doc lines (verifying the TRUE remainder)
- verify-before-advancing.md PR row: "CodeRabbit is *advisory here* ...
  (`kb_setup.pr._ADVISORY_CHECKS`)" — names only CodeRabbit but CITES the set as the
  authority. (line TBC)
- gh-cli-watch.md: "CodeRabbit is advisory — reported in every bucket, blocking in
  none" — names only CodeRabbit. (line TBC)
- CLAUDE.md ~:180 "CodeRabbit is advisory, never blocks". (line TBC)
So the NARROW staleness (three lines name only CodeRabbit) is real; the headline
claims around it are false.

## Probe 3 — provenance of the change (2026-08-18)
- `git log -S "Repowise" 2b364443 -- python/src/kb_setup/pr.py` → exactly one commit:
  `37f6a1c5 feat model limits resolver (#336)`. "Changed in #336": TRUE.
- ON MAIN (2b364443): `git show 2b364443:docs/direction/2026-08-18-ray-directives.md`
  grep repowise → line 77 present (landed via #339). `docs/research/README.md` on main:
  1 Repowise mention. So even main, not just this branch, carries tracked-doc records.

## Probe 4 — the three cited lines: TRUE but non-exclusive
- verify-before-advancing.md:42 — "CodeRabbit is *advisory here* and blocking in no
  bucket (`kb_setup.pr._ADVISORY_CHECKS`)" — cites the SET as authority, does not
  claim exclusivity.
- gh-cli-watch.md:40 — "CodeRabbit is advisory". CLAUDE.md:180 — "CodeRabbit is
  advisory, never blocks". Both statements remain TRUE today; neither says "only".
The finding's "THE advisory check" is its own inference, not the docs' claim.

## Probe 5 — the timeline (handoffs b, c; memories 031844, 115929)
- handoff b:44-45 (session early 2026-08-17, PR #331 open): Ray's ruling verbatim —
  "investigate Repowise before landing — do NOT reclassify it as advisory." CONFIRMED.
- memory query_20260816_031844 (#325 era): warns "reclassifying a gate to get past it".
  CONFIRMED — but it is about PR #325, and it is a lesson, not the #331 ruling.
- handoff c:81-94: that ruling was HONORED AND CONSUMED — "It was fixed on its
  merits"; Repowise failure@398c7b87 → success@7a89a4b7; #331 merged with Repowise
  GREEN, still binding.
- pr.py:75-93 (#336, later on 2026-08-17): a NEW Ray ruling ("joined 2026-08-17 on
  Ray's ruling") reclassified it, with a recorded argument that explicitly
  distinguishes itself from CodeRabbit's case and states the cost — i.e. the code
  comment ANSWERS the memory's caution head-on. handoff g:39: "Repowise / code
  health made advisory so kb-land could merge."
So there is no contradiction between rulings: #331's ruling governed #331 and was
followed; #336's ruling superseded it and is durably recorded WITH attribution.

## VERDICT SO FAR: core claims REFUTED
1. "'Repowise' appears in zero tracked docs" — FALSE (6 tracked files; 2 are docs/).
2. "the reversal exists only in gitignored artifacts" — FALSE (pr.py:75-93,
   test_pr.py:1040, docs/direction/…:77 on main, docs/research/README.md:86).
3. Original probe was BOUNDED (rules + CLAUDE.md + kb-review SKILL only) — it never
   searched docs/ or python/, so rc=1 was guaranteed for the strongest claim.
What survives: the three named rule/CLAUDE.md lines do lag (name only CodeRabbit) —
a real but narrow doc-currency nit, already subsumed by directive item 4.

## Remaining required reading
- [x] docs/direction/2026-08-18-ray-directives.md — read IN FULL
- [x] handoffs b, c
- [ ] handoffs d, e, f, g, 18-a
