---
type: "query"
date: "2026-09-09T07:08:54.494693+00:00"
question: "Should memories_about be in scope for the kb-memory MCP server?"
contributor: "graphify"
outcome: "corrected"
correction: "`source_nodes` is not a THIN field that fills in as the corpus grows — it is a\nFROZEN one. Nothing has written it in a month: 25 records carry it, all dated\n2026-07-22..2026-08-10, while 18 records added since carry none.\n\nSo `memories_about` would be a tool over a field that stopped being written, and\nit is out of scope for the transport work. The real question is a different one\nand belongs in its own issue: why did `kb-remember` stop populating\n`source_nodes`, and should it?\n\nThe general form, and why this is filed as a correction rather than a note: the\ninherited figure \"25 of 364\" was TRUE when written and stayed true-looking\nbecause only its DENOMINATOR moved. A ratio whose numerator is frozen looks like\na ratio that is merely small. Re-deriving both halves is what separated them —\n`probes-need-a-control-arm.md` rule 6, an inherited number is not a measurement.\n"
---

# Q: Should memories_about be in scope for the kb-memory MCP server?

## Answer

#681 recorded "only 25 of 364 records currently populate `source_nodes`, so that
tool would be thin until more do" — which reads as a field that fills in as the
corpus grows.

Re-derived 2026-09-09 against the live store: **25 of 382.** The numerator has
not moved while the store grew by 18 records. Every one of those 25 is dated
between **2026-07-22 and 2026-08-10**, and the store now runs to 2026-09-09.


## Outcome

- Signal: corrected
- Correction: `source_nodes` is not a THIN field that fills in as the corpus grows — it is a
FROZEN one. Nothing has written it in a month: 25 records carry it, all dated
2026-07-22..2026-08-10, while 18 records added since carry none.

So `memories_about` would be a tool over a field that stopped being written, and
it is out of scope for the transport work. The real question is a different one
and belongs in its own issue: why did `kb-remember` stop populating
`source_nodes`, and should it?

The general form, and why this is filed as a correction rather than a note: the
inherited figure "25 of 364" was TRUE when written and stayed true-looking
because only its DENOMINATOR moved. A ratio whose numerator is frozen looks like
a ratio that is merely small. Re-deriving both halves is what separated them —
`probes-need-a-control-arm.md` rule 6, an inherited number is not a measurement.
