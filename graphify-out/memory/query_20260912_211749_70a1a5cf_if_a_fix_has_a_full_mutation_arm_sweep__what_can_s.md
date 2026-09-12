---
type: "query"
date: "2026-09-12T21:17:49.235437+00:00"
question: "If a fix has a full mutation-arm sweep, what can still be wrong with it?"
contributor: "graphify"
outcome: "useful"
---

# Q: If a fix has a full mutation-arm sweep, what can still be wrong with it?

## Answer

**An arm proves a TEST notices a mutation. It says nothing about whether the FIX
was the right fix.** Measured 2026-09-12, and it is the sharpest version of
"the fix is where the defect lives" this repo has recorded.

Round 1 closed three P1s in `python/src/kb_setup/mod_runtime.py` and armed every
one: **20/20 arms died, 1/1 control held, rc 0.** A cold `gpt-6-astra` lane then
reviewed that commit and raised nine findings — and **four were defects inside
those armed fixes**:

- the bracket extractor matched only DOUBLE quotes, so `e['permissionMode']` was
  still invisible; the destructuring pattern had no room for `: any` before `=`,
  so `const { permissionMode }: any = e` was still invisible. **The P1 was
  half-closed and the arms could not tell.**
- the same extractor needed no RECEIVER and ran with strings intact, so
  `const status = ["bogusMember"]` and prose in a log line each promoted local
  data to a declared runtime dependency — a NEW defect the fix introduced, in
  the safe-looking direction, since more tokens reads as a stricter gate.
- the dotted boundary `(?![\w$])` still admitted a dot, so `tool.call.after`
  satisfied `tool.call`. The renamed-event case had a sibling that EXTENDS.
- comments were stripped before strings, and the stripper is not a lexer: `//`
  inside `"https://example.com"` eats the rest of the line, erasing a real
  property read beside a URL.

**Why an arm cannot see any of this.** An arm asks "if I break this line, does a
named test go red?" Every one of those lines was load-bearing for the case its
test covered. None of the tests covered the case the fix MISSED, so no mutation
of any line could reveal it. A mutation sweep is a statement about coverage, and
coverage is exactly what an incomplete fix lacks.

**How to apply:** budget a cold cross-family read of the FIX, not only of the
original defect. Arms and review answer different questions and neither
substitutes.

Three further things round 2 measured, each worth keeping:

1. **A tautological test survived into a "complete" batch.** `kb-arms` A22
   SURVIVED because the test meant to catch it could not fail: written with
   escaped quotes, the character after `[` was a BACKSLASH, so the pattern never
   matched with OR without the fix. Found by a mutation, not by re-reading.
2. **`kb-arms`' two refusal modes are the whole value.** `pattern not found`
   caught four arms whose anchors the round-2 fixes had moved. `red suite did
   not name the test` caught a confident WRONG PREDICTION: I expected severing
   the dotted branch to stop dotted events matching entirely — it does not,
   because `\btool\.call\b` still matches inside a quoted string. A harness that
   only counted red and green would have scored that as a pass.
3. **A scheduling artifact has a prose layer and a data layer.** I corrected a
   DAG's comment ("only S9 depends on P0") and left `depends_on = ["P0"]` on five
   units. The reviewer PARSED the TOML and counted six. Correcting the prose left
   the machine-readable half stating the opposite.


## Outcome

- Signal: useful