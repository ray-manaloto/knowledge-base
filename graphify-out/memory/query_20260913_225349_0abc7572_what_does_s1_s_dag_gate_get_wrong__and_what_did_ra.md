---
type: "query"
date: "2026-09-13T22:53:49.608376+00:00"
question: "What does S1's DAG gate get wrong, and what did Ray rule?"
contributor: "graphify"
outcome: "useful"
---

# Q: What does S1's DAG gate get wrong, and what did Ray rule?

## Answer

S1's DAG gate was reviewed cold, advised on by three lanes, premise-verified, and
synthesised. Nine defects, all armed in-session with controls. Three of them
disable the gate SILENTLY while every file on disk says it is armed: a
future-dated filename (a negative day-delta is never `> 7`, and the file also wins
`sorted(glob)[-1]`), a stray non-ISO filename (sorts last, reads stale, blocks
every commit), and an unwritable state directory (ALLOW x6 against a control's
ALLOW,DENY x5 — under a docstring asserting that can never happen, and reachable
because this repo's cold lanes run `--sandbox read-only`).

Fifteen rulings came out of the round and are now committed as DAG units rather
than living in a transcript.


## Outcome

- Signal: useful