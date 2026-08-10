---
type: "query"
date: "2026-08-07T01:21:07.654650+00:00"
question: "Can a gate's own test suite be blind to the mutation its ticket named?"
contributor: "graphify"
outcome: "corrected"
correction: "A passing test suite does not prove a gate, and it can be blind to the exact mutation its own ticket named in writing. Issue #128's acceptance bar was to prove the FAIL direction by deleting the WIRING LINE that calls the check, not by renaming its definition. I wrote 15 tests; all 15 called check() or skill_lint_main() DIRECTLY, so deleting the CLI dispatch branch left 15 of 15 green while `uv run kb-setup skill-lint` was already broken — only the hk step caught it. The cold lane found it by EXECUTING the mutation rather than reading the tests, the third time in one day that the sharpest finding came from running something rather than reasoning about it. Fixed with a cli.main(['skill-lint']) test: the mutation now goes red and restoring goes green, 18 tests. Two more from the same lane, both found by construction: command_lines toggled on ANY 3-or-more-backtick line, so a bash block inside a four-backtick markdown example read as a real instruction (CommonMark closes a fence of N only with N-or-more and no info string) — and the file most likely to contain such an example is a SKILL.md documenting this very gate; tilde fences, which render identically on GitHub, bypassed the gate entirely. Why it generalises: a test written alongside the code it tests inherits the AUTHOR'S MODEL of what the input looks like. When a ticket names a mutation, write the test at the LEVEL THE MUTATION HAPPENS, not at the level you happen to be working."
---

# Q: Can a gate's own test suite be blind to the mutation its ticket named?

## Answer

It can, and it did, and the ticket had named the exact mutation it was blind to.

Issue 128's acceptance bar was: prove the FAIL direction by deleting the wiring
line that calls the check, not by renaming its definition. I wrote 15 tests. All
15 called check() or skill_lint_main() directly. Deleting the CLI dispatch branch
left 15 of 15 GREEN while uv run kb-setup skill-lint was already broken. Only the
hk step caught it.

The cold lane found this by EXECUTING the mutation rather than reading the tests.
That is the third time in one day that the sharpest finding came from running
something rather than reasoning about it.

Fixed with a cli.main(["skill-lint"]) test: the mutation now goes red, restoring
goes green, 18 tests.

Two more from the same lane, both real and both found by construction rather
than inspection. A nested fence false positive: command_lines toggled on any
3-or-more backtick line, so a bash block inside a four-backtick markdown example
read as a real instruction. CommonMark closes a fence of N only with N-or-more of
the same character and no info string. The reviewer's framing is the sharp part:
the file most likely to contain such an example is a SKILL.md documenting this
very gate. And tilde fences, which render identically on GitHub, bypassed the
gate entirely.

Why this generalises: a test written alongside the code it tests inherits the
author's model of what the input looks like. The ticket predicted the blind spot
in writing and I still built a suite that could not see it. When a ticket names
a mutation, write the test at the level the mutation happens, not at the level
you happen to be working.

## Outcome

- Signal: corrected
- Correction: A passing test suite does not prove a gate, and it can be blind to the exact mutation its own ticket named in writing. All 15 tests called check() or skill_lint_main() DIRECTLY, so deleting the CLI dispatch branch left 15 of 15 green while the task was already broken; only the hk step caught it. A test written alongside the code it tests inherits the AUTHOR'S MODEL of the input. When a ticket names a mutation, write the test at the LEVEL THE MUTATION HAPPENS.