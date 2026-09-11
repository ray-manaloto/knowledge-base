---
type: "query"
date: "2026-09-11T06:42:31.434415+00:00"
question: "Is a kb-arms run only dangerous to the working tree if it crashes?"
contributor: "graphify"
outcome: "corrected"
correction: "`kb_setup.arms` restores in a `finally` (`arms.py:440-441`), which covers a\nhandled exception and nothing else. Two distinct failures follow, and only the\nfirst was known:\n\n  run KILLED mid-arm      -> a LIVE MUTATION left in a tracked source file\n  run COMPLETES normally  -> any CONCURRENT EDIT to a mutated file, reverted\n\nBoth silent. The second is worse because nothing looks abnormal afterwards — the\nfirst at least leaves code that fails a check. Crash-safe restore (persisting the\noriginal before mutating) closes the first and does NOTHING for the second: it\nwould restore the same stale bytes, just more reliably. The second wants a lock,\nan in-flight marker, or a re-read before restore that refuses when the on-disk\nbytes differ from the mutated text it wrote — `_restore` already holds both\nstrings, so it can tell \"unchanged since I mutated it\" from \"someone else wrote\nhere\" with no new state.\n\nTHE HUMAN HALF, which is the part that actually bit. The rule already exists —\n\"never edit while a mutating lane runs\" — and it did not prevent this. The\nsession had run `pgrep -f 'kb-setup arms'` earlier in the same turn, and THE\nFACT THAT THE CHECK HAD BEEN RUN ONCE is what made skipping it the second time\nfeel safe. A stale liveness check is more dangerous than none, because it\nanswers with authority about a moment that has passed.\n\nOperationally: `pgrep -f 'kb-setup arms'` immediately before ANY edit, not once\nper turn. Tracked as #751.\n\nA second, unrelated lesson from the same stretch: after the arms run reverted\nthe edits, the session read a FILTERED `git diff`, saw the completion logic\napparently deleted with no replacement, and concluded its own edit had destroyed\nit. Both halves were wrong — the \"deletion\" was a live arm mutation doing its\njob, and a `grep -v` had hidden the replacement line. Reading the actual function\nsettled it in one command. A conclusion drawn from what survived your own filter\nis a display bound (`probes-need-a-control-arm.md` rule 3), and it recurred three\ntimes in this one round in three different costumes: `tail`, `grep -v`, and a\n`| head -5` that hid an arm from a PROBE BROKEN list.\n"
---

# Q: Is a kb-arms run only dangerous to the working tree if it crashes?

## Answer

# Belief: a kb-arms run only endangers the tree if it CRASHES

Wrong in both directions, and the second one has no crash in it.

A `mise run kb-arms` run was mid-flight on `codex_review_evidence.py` while this
session edited that same file to fix two review findings. The arms loop reached
its next `finally`, wrote back the text it had captured BEFORE those edits, and
both fixes vanished. Exit 0. No warning. `git status` showed only the ordinary
"modified" it would have shown anyway.


## Outcome

- Signal: corrected
- Correction: `kb_setup.arms` restores in a `finally` (`arms.py:440-441`), which covers a
handled exception and nothing else. Two distinct failures follow, and only the
first was known:

  run KILLED mid-arm      -> a LIVE MUTATION left in a tracked source file
  run COMPLETES normally  -> any CONCURRENT EDIT to a mutated file, reverted

Both silent. The second is worse because nothing looks abnormal afterwards — the
first at least leaves code that fails a check. Crash-safe restore (persisting the
original before mutating) closes the first and does NOTHING for the second: it
would restore the same stale bytes, just more reliably. The second wants a lock,
an in-flight marker, or a re-read before restore that refuses when the on-disk
bytes differ from the mutated text it wrote — `_restore` already holds both
strings, so it can tell "unchanged since I mutated it" from "someone else wrote
here" with no new state.

THE HUMAN HALF, which is the part that actually bit. The rule already exists —
"never edit while a mutating lane runs" — and it did not prevent this. The
session had run `pgrep -f 'kb-setup arms'` earlier in the same turn, and THE
FACT THAT THE CHECK HAD BEEN RUN ONCE is what made skipping it the second time
feel safe. A stale liveness check is more dangerous than none, because it
answers with authority about a moment that has passed.

Operationally: `pgrep -f 'kb-setup arms'` immediately before ANY edit, not once
per turn. Tracked as #751.

A second, unrelated lesson from the same stretch: after the arms run reverted
the edits, the session read a FILTERED `git diff`, saw the completion logic
apparently deleted with no replacement, and concluded its own edit had destroyed
it. Both halves were wrong — the "deletion" was a live arm mutation doing its
job, and a `grep -v` had hidden the replacement line. Reading the actual function
settled it in one command. A conclusion drawn from what survived your own filter
is a display bound (`probes-need-a-control-arm.md` rule 3), and it recurred three
times in this one round in three different costumes: `tail`, `grep -v`, and a
`| head -5` that hid an arm from a PROBE BROKEN list.
