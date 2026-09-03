---
type: "query"
date: "2026-09-03T17:00:40.056777+00:00"
question: "Which model family is the DEFAULT cold review lane in this repo?"
contributor: "graphify"
outcome: "corrected"
correction: "CODEX IS THE PRIMARY REVIEW LANE. Gemini/antigravity is the EXCEPTION, not the default.\n\nRay, 2026-09-03, verbatim: \"codex is the primary as gemini subscription tokens are\nscarce / i've mentioned this so many times add to graphify memory and into the\nworkflow for reviews\".\n\nThe \"so many times\" is the point. This has been ruled before and has not stuck,\nbecause it lived only in a transcript while `kb-review/SKILL.md` carried a routing\nTABLE that says the opposite: it routes codex-authored diffs to `antigravity:review`\non the cross-family rule, and nothing in that file mentions token scarcity. A\ndirective that contradicts a written table loses to the table every time a session\nreads the skill instead of the transcript.\n\nWHAT IS TRUE NOW:\n\n- `codex review` is the DEFAULT cold lane for every diff, including codex-authored\n  ones.\n- Gemini/antigravity is reserved for the case where a second, genuinely independent\n  family is worth its scarce tokens - and that is a deliberate spend, not a routing\n  default.\n- The cross-family principle is not repealed; it is OUTRANKED by a resource\n  constraint that the principle never priced in.\n\nWHY THE COUNTER-ARGUMENT DOES NOT WIN: on 2026-09-03 a Gemini lane found a P1 that\ncodex's own side had documented as verified, which is a real argument FOR\ncross-family review. It is not an argument for spending a scarce subscription on\nevery diff. The correct reading is that cross-family review is VALUABLE and\nEXPENSIVE, so it is rationed rather than defaulted.\n"
---

# Q: Which model family is the DEFAULT cold review lane in this repo?

## Answer

CODEX IS THE PRIMARY REVIEW LANE. Gemini/antigravity is the EXCEPTION, not the default.

Ray, 2026-09-03, verbatim: "codex is the primary as gemini subscription tokens are
scarce / i've mentioned this so many times add to graphify memory and into the
workflow for reviews".

The "so many times" is the point. This has been ruled before and has not stuck,
because it lived only in a transcript while `kb-review/SKILL.md` carried a routing
TABLE that says the opposite: it routes codex-authored diffs to `antigravity:review`
on the cross-family rule, and nothing in that file mentions token scarcity. A
directive that contradicts a written table loses to the table every time a session
reads the skill instead of the transcript.

WHAT IS TRUE NOW:

- `codex review` is the DEFAULT cold lane for every diff, including codex-authored
  ones.
- Gemini/antigravity is reserved for the case where a second, genuinely independent
  family is worth its scarce tokens - and that is a deliberate spend, not a routing
  default.
- The cross-family principle is not repealed; it is OUTRANKED by a resource
  constraint that the principle never priced in.

WHY THE COUNTER-ARGUMENT DOES NOT WIN: on 2026-09-03 a Gemini lane found a P1 that
codex's own side had documented as verified, which is a real argument FOR
cross-family review. It is not an argument for spending a scarce subscription on
every diff. The correct reading is that cross-family review is VALUABLE and
EXPENSIVE, so it is rationed rather than defaulted.


## Outcome

- Signal: corrected
- Correction: CODEX IS THE PRIMARY REVIEW LANE. Gemini/antigravity is the EXCEPTION, not the default.

Ray, 2026-09-03, verbatim: "codex is the primary as gemini subscription tokens are
scarce / i've mentioned this so many times add to graphify memory and into the
workflow for reviews".

The "so many times" is the point. This has been ruled before and has not stuck,
because it lived only in a transcript while `kb-review/SKILL.md` carried a routing
TABLE that says the opposite: it routes codex-authored diffs to `antigravity:review`
on the cross-family rule, and nothing in that file mentions token scarcity. A
directive that contradicts a written table loses to the table every time a session
reads the skill instead of the transcript.

WHAT IS TRUE NOW:

- `codex review` is the DEFAULT cold lane for every diff, including codex-authored
  ones.
- Gemini/antigravity is reserved for the case where a second, genuinely independent
  family is worth its scarce tokens - and that is a deliberate spend, not a routing
  default.
- The cross-family principle is not repealed; it is OUTRANKED by a resource
  constraint that the principle never priced in.

WHY THE COUNTER-ARGUMENT DOES NOT WIN: on 2026-09-03 a Gemini lane found a P1 that
codex's own side had documented as verified, which is a real argument FOR
cross-family review. It is not an argument for spending a scarce subscription on
every diff. The correct reading is that cross-family review is VALUABLE and
EXPENSIVE, so it is rationed rather than defaulted.
