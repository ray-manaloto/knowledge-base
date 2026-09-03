---
type: "query"
date: "2026-09-03T11:59:05.407586+00:00"
question: "What do two METHOD-instructed cold codex rounds find on a security guard, and where do the findings come from?"
contributor: "graphify"
outcome: "useful"
---

# Q: What do two METHOD-instructed cold codex rounds find on a security guard, and where do the findings come from?

## Answer

Two METHOD-instructed cold `codex review` rounds on a security guard produced
NINE findings across three commits, and **not one was reachable by reading the
code**. Three passes read the same scanner; every finding came from the passes
that RAN a shell shape through the real entry point.

WHAT THE ROUNDS FOUND, in order:

Round 1 (4, all P1, all BLINDING): `<<$'END-MSG'` (ANSI-C quoting) and
`cat <<\` + `EOF` (line continuation) were REGRESSIONS the fix introduced against
the regex it replaced — the old code denied both. Nested command substitution
(`"$(printf "%s" "<<EOF")"`) and multiple heredocs on one line (`cat <<A <<B`)
were pre-existing.

Round 2 (4: 3 P1, 1 P2), all against round 1's OWN fixes: two refusals added in
round 1 were themselves the bug; popping the substitution frame on the first `)`
ended it early when an ordinary subshell was nested inside; and resuming at
`start + len(delimiter)` landed INSIDE a quoted token, so `<<'A'` left the
scanner on the closing quote and it never saw the `<<B`.

Plus one the caller found by reading the diff: a work-memory record whose
`## Answer` was a byte-identical copy of a sibling record's, while asking a
different question.

THE PATTERN WORTH KEEPING: the most dangerous code in every round was the
CALLER'S OWN FIX. An inert `<<<` branch carrying a comment claiming it was
load-bearing; a test that could not fail because it used a guard with an
independent regex fallback; two refusals that read as caution; and a
"conservative limit" docstring that was itself a blinding path.

MEASUREMENTS. Arms went 7/7 -> 12/12 -> 13/13 died with 1/1 controls held, and
each sweep found something the previous one could not: an inert mutant, a test
that could not fail, an uncovered input, and three anchors silently moved by a
refactor (caught only by `--dry-run`). Real-chain cases ended at 23, seven of
them negatives — re-derived from the module, after a previous commit message
asserted 19/5 and the lane caught it.


## Outcome

- Signal: useful