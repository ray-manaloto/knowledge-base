---
type: "query"
date: "2026-08-18T07:59:13.777786+00:00"
question: "What did the 2026-08-17/18 review round establish about how review and measurement fail here?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did the 2026-08-17/18 review round establish about how review and measurement fail here?

## Answer

Round of 2026-08-17/18. Three PRs landed (#337, #338, #339) and the durable
lessons are about how REVIEW and MEASUREMENT behaved, not about the features.

## A second review round is what catches the first round's fix

PR #337: round 1 found 6, all confirmed; the fix replaced a regex with `shlex`
tokenising. Round 2 then found 5 more and TWO were created by the round-1 fix —
newline-splitting before tokenising tore a multi-line commit message apart, and
scanning forward from `uv run` promoted an ARGUMENT into the command position so
`uv run pytest -k ruff -k check` was denied for a tool the guard's own docstring
excludes. A third defect was found by neither reviewer, only by re-running my own
decision table after each edit: uv's value-flag set (`-p` = `--python`) applied
to every wrapper, so `time -p ruff check` had its command word eaten.

PR #339 repeated the shape: round 2 found that the guard added in that very
branch DENIED `git add -u .`, which cannot introduce an untracked path and is the
safe form the guard's own message recommends.

## A guard that pattern-matches cannot see quoting

Across both rounds on #337 every false positive was one class: a gate name inside
a quoted string. No regex fixes it. `shlex.shlex(command, posix=True,
punctuation_chars="();<>|&\n")` with `lexer.whitespace = " \t\r"` moves newline
out of whitespace and into punctuation, so a real newline separates commands
while a newline inside quotes stays in its token.

## The prompt was a MIRROR, not the prompt

Chunk 1 attributed 61 of 109 nodes to 26 files it never contained. The attempted
fix added a scope clause to `_EXTRACTION_USER_INSTRUCTION` — but that constant
mirrors text `graphify.llm` hardcodes, graphify builds the prompt and pipes it to
our adapter over stdin, and `graphify.llm` never references `kb_setup` at all.
The fix could not reach the model, changed only our RECONSTRUCTION, and produced
`provider-prompt-bytes-mismatch`. The fix WAS the defect.

Worse: the 61 -> 0 improvement on the re-run was NOT caused by that change. Same
members, same commit, same graphify-built prompt. The drift is NONDETERMINISTIC,
so one clean run is not evidence of a fix.

## A cap that lives in a TemporaryDirectory is a cap on one process

`_Spend` seeded at 0.0 and summed records in a tempdir, so a run interrupted at
chunk 30 resumed with a fresh $100; `ChunkStageReceipt` carries no cost field to
contradict it. Fixed with a durable `spend-ledger.json` under the run namespace.
It works: chunk 1 cost **$1.32**, recorded, so 58 chunks projects to ~$77.

## Probe mechanics that produced false results this round

* A wait condition (`until ls .../chunks/0001/receipt.json`) was satisfied by a
  STALE receipt from a previous run, so a new run was stopped before it finished
  and the old result was nearly reported as the new one. A wait condition is a
  probe and mine could only say yes.
* `ps | grep -iE "claude|python"` matched the Claude desktop app, not the run.
* An inherited figure — "currency.toml tracks 4 of ~14 pins" — was repeated
  without re-derivation and was false: 12 sections, 9 of 18 already tracked.


## Outcome

- Signal: useful