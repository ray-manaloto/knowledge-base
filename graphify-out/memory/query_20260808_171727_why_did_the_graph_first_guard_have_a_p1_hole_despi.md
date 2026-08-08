---
type: "query"
date: "2026-08-08T17:17:27.867979+00:00"
question: "Why did the graph-first guard have a P1 hole despite every ambiguity being resolved deliberately?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why did the graph-first guard have a P1 hole despite every ambiguity being resolved deliberately?

## Answer

Two individually-defensible "ambiguity resolves to ALLOW" defaults, chained,
produced the least safe answer. `_looks_like_a_path` resolved its ambiguity
toward "this word IS a path"; `_is_single_file` resolved its own toward "a path
that does not exist is one file". Each is the right call alone. Together they
let `rg 'src/utils'` — a repo-wide search with NO path argument, whose PATTERN
merely contains a slash — read as a targeted single-file search and sail past
the guard entirely.

The failure mode is COMPOSITION, and no arm or review of either function alone
would find it: both are correct in isolation. It surfaced only because a cold
lane executed inputs rather than reading code. When a module states a blanket
principle like "ambiguity favours X", that principle is about ONE ambiguous
input and it does not compose for free — the moment two such decisions feed each
other, ask what the chain produces, not what each link does.

Related: this was a P1 IN the round-1 fix, so it is also another instance of
`a-fix-can-be-the-defect`. Round 1 found 4 (2xP1), round 2 found 4 more, and the
worst of round 2 was created by round 1.

## Outcome

- Signal: useful