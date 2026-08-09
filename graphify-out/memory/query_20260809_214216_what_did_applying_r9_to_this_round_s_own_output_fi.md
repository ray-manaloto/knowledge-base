---
type: "query"
date: "2026-08-09T21:42:16.313623+00:00"
question: "What did applying R9 to this round's own output find, and how did a flaky gate lead to two real defects?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did applying R9 to this round's own output find, and how did a flaky gate lead to two real defects?

## Answer

A green build hid 1,024 lost nodes, and a flaky gate hid two quadratic regexes.
Both were found by looking at output nobody greps — which is R9's entire thesis,
demonstrated on live data rather than argued.

R9 APPLIED TO MY OWN BUILD: kb-build exited 0 and printed
"424,699 nodes ... 0 dangling, 0 malformed" — with 1,024
"is minted by two different files" warnings in the same stream, each one a node
graphify itself says is LOST. 35 distinct ids, all .swift, all from
sources/turbo-fieldfare/. Control-armed three ways (extension histogram
1024/1024; known-absent marker 0; known-present term 826). Filed on #231, which
had described the risk for weeks without a number.
The assertion shape already exists — "0 dangling, 0 malformed" is on the same
line. It simply does not cover this.

A FLAKY GATE IS A LEAD, NOT A TRANSIENT. kb-gates failed on a wall-clock
assertion (elapsed < 0.05) measuring 73.9 ms under -n auto, then passed 3/3
reruns. "Retry" and "widen the bound" were both wrong: a timing proxy cannot
survive parallel execution, because it measures the scheduler and reports it as
the property it names. Asserting the property directly surfaced the real defect —
the quadratic A.*B shape fixed on one rule the day before was still live on two
others, at ~4.0x cost per input doubling against ~2.0x bounded.
A finding is a sample of a class, and the sample was found by investigating a
flake rather than by reading the rules.

I GOT ONE COMMENT WRONG THREE TIMES, and no test could have caught any of them:
1. claimed a command with many `uv run ruff` and no `&&` "re-expanded BOTH gaps
   from every start" — impossible; if `&&` never matches, gap 2 is never reached.
2. the rewrite claimed gap 2 "pays" when `&&` is present without a trailing
   token — measured 2.0x, linear; it does not.
3. cited correct numbers for the UNBOUNDED pattern beside the BOUNDED one, with
   no label, so they read as its cost and said the opposite of the truth.
Only the cold lane caught #3, by recompiling the pattern from the file's own
constants. A comment has no behaviour, so a mutation arm cannot reach it and a
green suite says nothing about it.
The durable fix was structural: the comment now carries NO figures and points at
the constant whose docstring states them per pattern. A number beside a pattern
reads as that pattern's cost.

## Outcome

- Signal: useful