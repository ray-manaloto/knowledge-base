---
type: "query"
date: "2026-08-22T16:48:20.376812+00:00"
question: "Does the sibling dotfiles repo deny fnox get / doppler secrets get at its PreToolUse hook, as #441 stated?"
contributor: "graphify"
outcome: "corrected"
correction: "SOURCE BEATS ISSUE TRACKER, and this repo already had that rule\n(`probes-need-a-control-arm.md`) before violating it.\n\nA claim about ANOTHER REPO'S CODE is a claim you have to go and read. \"The ticket\nsays so\" is not a reading, and neither is \"an earlier session's prose says so\" —\nthe chain here was #441's body <- an earlier session's prose <- nothing. No link\nin it was ever the file. The sibling repo was checked out on this very machine\nthe whole time; the read that refuted the premise took one grep with a control\narm.\n\nThe propagation half is the expensive half and is already recorded here as\n\"a wrong fact I authored propagates too\": RE-DERIVE BEFORE THE SECOND WRITE, not\nafter the fourth. This round wrote the false claim into a NEW module docstring\nhours after inheriting it, which is the moment the cost was locked in — a fact\ninherited into your own new code reads as verified forever, because you wrote it.\n\nThe generalisation worth carrying: when a ticket's PREMISE is a statement about\ncode you can open, opening it is part of implementing the ticket. A ticket is a\nrequest, not a measurement.\n"
---

# Q: Does the sibling dotfiles repo deny fnox get / doppler secrets get at its PreToolUse hook, as #441 stated?

## Answer

FALSE for the verbs. #441 opened on "dotfiles denies the value-revealing commands
at its PreToolUse hook; this repo has no equivalent", and that premise travelled
into four artifacts before anyone read the sibling's source.

Measured 2026-08-22 in `dotfiles_setup/hook_guard.py`: exactly ONE secret rule,
`secret_value_substitution` at line 531, covering the `${VAR:..}` printing shape
ALONE. Control-armed — `fnox get`, `fnox export`, `fnox list --values`,
`doppler secrets get`/`download` and `security .. -w`/`-g` are 0 hits there,
against a control of the rule names that DO exist in the same file.

Corrected in: `docs/secrets.md` (twice — the substitution warning and the
enforcement section), `.claude/CLAUDE.md`, `secret_guard.py`'s own docstring
written hours earlier in the SAME session, and #441's body (commit f5c9d7d4 plus
an issue comment). Filed upstream as ray-manaloto/dotfiles#780.


## Outcome

- Signal: corrected
- Correction: SOURCE BEATS ISSUE TRACKER, and this repo already had that rule
(`probes-need-a-control-arm.md`) before violating it.

A claim about ANOTHER REPO'S CODE is a claim you have to go and read. "The ticket
says so" is not a reading, and neither is "an earlier session's prose says so" —
the chain here was #441's body <- an earlier session's prose <- nothing. No link
in it was ever the file. The sibling repo was checked out on this very machine
the whole time; the read that refuted the premise took one grep with a control
arm.

The propagation half is the expensive half and is already recorded here as
"a wrong fact I authored propagates too": RE-DERIVE BEFORE THE SECOND WRITE, not
after the fourth. This round wrote the false claim into a NEW module docstring
hours after inheriting it, which is the moment the cost was locked in — a fact
inherited into your own new code reads as verified forever, because you wrote it.

The generalisation worth carrying: when a ticket's PREMISE is a statement about
code you can open, opening it is part of implementing the ticket. A ticket is a
request, not a measurement.
