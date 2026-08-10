---
type: "query"
date: "2026-08-09T22:28:00.997618+00:00"
question: "Where did this round's defects actually live, and what do they have in common?"
contributor: "graphify"
outcome: "useful"
---

# Q: Where did this round's defects actually live, and what do they have in common?

## Answer

Three defects this round, and ALL THREE were prose I wrote to explain something.
None was a code defect. None would have been caught by any test, because a
comment and a doc paragraph have no behaviour to mutate. All three were caught
by a cold lane recomputing from primary sources.

  1. "many `uv run ruff` and no && re-expanded BOTH gaps from every start" —
     impossible; if && never matches, gap 2 is never reached.
  2. the rewrite: "the second gap pays when && is present without a trailing
     token" — measured 2.0x, linear; it does not.
  3. cited CORRECT numbers for the unbounded pattern beside the BOUNDED one,
     unlabelled, where they read as its cost and asserted the opposite.
  4. (PR 2) explained a 99-node arithmetic gap with deduplication — causally
     BACKWARDS. Dedup happens DURING each source's extraction, immediately
     before that source's count is printed, so the figures were already
     post-dedup and dedup cannot shrink anything between table and aggregate.
     Zero dedup events occur during the merge; control 43 across the log.

The pattern is sharper than "I make mistakes in prose". In every case I reached
for a MECHANISM when the honest answer was either a measurement or an
admission. A mechanism is satisfying to write and impossible to test, which is
exactly why it is where my errors accumulate.

The terminal fixes that worked were both STRUCTURAL, not corrective:
  - the regex comment now carries NO figures and points at the constant whose
    docstring states them per pattern. A number beside a pattern reads as that
    pattern's cost, so the durable fix is to not put one there.
  - the 99-node paragraph now says the residual is NOT fully explained, keeps
    the wrong explanation and why it was wrong, and labels the likely cause (an
    INHERITED baseline from the previous round's handoff) as a hypothesis.

WHAT TO DO DIFFERENTLY: when about to write "because <mechanism>", either
measure it in the same turn or write "not established". A third explanation was
available both times and would have been wrong both times.

## Outcome

- Signal: useful