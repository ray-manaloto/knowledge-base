---
type: "query"
date: "2026-09-13T22:53:50.011537+00:00"
question: "Does re-deriving a citation make a relayed claim safe to repeat?"
contributor: "graphify"
outcome: "corrected"
correction: "My re-derivation checks that a citation RESOLVES, never that the claim is as\nSTRONG as stated. Three overstatements reached Ray today and all three were\ncaught by a lane rather than by me:\n\n1. I cited `result.py` for the precedent that a fourth `Rc` member was ADDED,\n   while the same file forty lines away records Ray REFUSING a fifth for the same\n   reason. The citation resolved; the conclusion was backwards.\n2. I told Ray the untrusted-text problem was \"already solved\" by\n   `_SAFE_SESSION_ID`. My seven-case arm tested terminal and path safety, which\n   holds, and I reported the whole claim. Real credential formats\n   (`sk_live_…`, `ghp_…`, `AKIA…`) pass that regex — the confidentiality half is\n   false.\n3. I built a decision page around a quote of `_REASON` that stopped one sentence\n   before the part that made the decision necessary, and then closed the page\n   saying the choice changed no behaviour. The page also printed a spawn count\n   the code cannot produce.\n\nThe general form, stronger than `probes-need-a-control-arm.md` rule 6: an\nunverified claim handed to another actor becomes a work order regardless of its\nlabel. Labelling discharges the duty to the READER and does nothing about the\nACTION the claim induces. Measured the same day: a claim I passed to a peer\nclearly marked \"carried, unverified\" sent them to read a credential file, and two\nsecrets reached a transcript.\n\nThe counter-practice: before repeating a claim, ask whether the text SAYS this or\nmerely PERMITS it, whether the claim's scope is the cited scope, and whether the\nsource's own body marks it UNVERIFIED nearby.\n"
---

# Q: Does re-deriving a citation make a relayed claim safe to repeat?

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

- Signal: corrected
- Correction: My re-derivation checks that a citation RESOLVES, never that the claim is as
STRONG as stated. Three overstatements reached Ray today and all three were
caught by a lane rather than by me:

1. I cited `result.py` for the precedent that a fourth `Rc` member was ADDED,
   while the same file forty lines away records Ray REFUSING a fifth for the same
   reason. The citation resolved; the conclusion was backwards.
2. I told Ray the untrusted-text problem was "already solved" by
   `_SAFE_SESSION_ID`. My seven-case arm tested terminal and path safety, which
   holds, and I reported the whole claim. Real credential formats
   (`sk_live_…`, `ghp_…`, `AKIA…`) pass that regex — the confidentiality half is
   false.
3. I built a decision page around a quote of `_REASON` that stopped one sentence
   before the part that made the decision necessary, and then closed the page
   saying the choice changed no behaviour. The page also printed a spawn count
   the code cannot produce.

The general form, stronger than `probes-need-a-control-arm.md` rule 6: an
unverified claim handed to another actor becomes a work order regardless of its
label. Labelling discharges the duty to the READER and does nothing about the
ACTION the claim induces. Measured the same day: a claim I passed to a peer
clearly marked "carried, unverified" sent them to read a credential file, and two
secrets reached a transcript.

The counter-practice: before repeating a claim, ask whether the text SAYS this or
merely PERMITS it, whether the claim's scope is the cited scope, and whether the
source's own body marks it UNVERIFIED nearby.
