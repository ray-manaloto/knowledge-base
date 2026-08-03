---
type: "query"
date: "2026-08-03T22:19:18.340533+00:00"
question: "PR #141 hardened kb-skill-score over two cold review rounds. What did the review and the verification actually teach, beyond the individual fixes?"
contributor: "graphify"
outcome: "useful"
---

# Q: PR #141 hardened kb-skill-score over two cold review rounds. What did the review and the verification actually teach, beyond the individual fixes?

## Answer

Three lessons, all measured this round on PR #141 (kb_setup.skill_eval).

1. A DETECTOR CAN READ THE WRONG KEY AND REPORT A CLEAN CORPUS. The
anti-pattern reader looked for name/type/pattern; plugin-eval emits "flag". It
therefore reported ZERO anti-patterns for all 7 project skills when 5 have one,
and that false claim reached a committed baseline, a commit message and a
session handoff before anything questioned it. Its unit test passed throughout
because the fixture used "name" -- code and test shared one wrong assumption and
agreed with each other, so a green suite proved nothing. The fix is to build the
fixture from a payload captured from a real run, not from what the reader
expects. Same shape as the earlier dead-detector lesson; the recurrence is the
finding.

2. A MUTATION ARM CAN BE DEFEATED BY THE BYTECODE CACHE. A mutation that
SWAPPED TWO LINES reported the test still passing. The test was correct; the
harness was not. A line swap leaves the file SIZE unchanged, and CPython
invalidates a cached .pyc on (mtime, size) -- so a same-second, same-size edit
was served from cache and the subprocess ran the OLD code. Every other arm in
the same run changed the file size and was unaffected, which is precisely why
this was the one that looked green. Any mutation harness that spawns a
subprocess must clear __pycache__ or set PYTHONDONTWRITEBYTECODE=1, and a
same-size mutation is the case that exposes it.

Re-running with the cache defeated then exposed a real gap the first arm had
hidden: nothing proved the temp-then-rename write at all. Injecting an error AT
write_text cannot distinguish in-place from atomic -- both leave the target
untouched -- so the arm passed against a mutation that deleted the rename
entirely. The discriminating failure is an interruption PART-WAY THROUGH, which
truncates the committed file only in the in-place case. An arm must inject the
failure the mechanism exists to survive, not merely a failure.

3. A COMPOSITE SCORE CAN MOVE AGAINST EVERY DIMENSION IT REPORTS. A doc edit
improved every reported plugin-eval dimension (ecosystem_coherence 0.990 ->
1.000, token_efficiency 0.988 -> 0.989) and the composite still fell 66.1 ->
62.8. The whole move was composite.anti_pattern_penalty = 0.95, a multiplier the
dimensions array does not expose. So a reader shown only dimensions concludes
the tool is broken, and a session chasing the reported dimensions can lower its
score while improving all of them. kb-skill-score now renders the penalty beside
the flags. Corollary for any scored artifact: if the reported components cannot
reconstruct the headline number, the report is incomplete, and the missing term
is where the movement lives.

Also settled this round: an advisory task is advisory about its FINDINGS, never
about a malformed REQUEST. kb-skill-score returns 0 for every measurement
outcome including "nothing here could measure anything", and 2 for an unknown
skill name, an unrecognised flag, or a --write that cannot record a complete
table -- the same split currency.run already drew for an unknown --tool, on the
stated grounds that a silent 0 hides a typo.

## Outcome

- Signal: useful