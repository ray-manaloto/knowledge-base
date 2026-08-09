---
type: "query"
date: "2026-08-09T21:43:59.229152+00:00"
question: "What did kb-session-reflect measure about directive compliance this round?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did kb-session-reflect measure about directive compliance this round?

## Answer

Three directives improved, one got WORSE, and the worse one is the only one with
no machine enforcement. That correlation is the finding, not the numbers.

  bare-interpreter   62 -> 1   (guard DENIES)
  piped-rc           35 -> 13 -> 1   (kb-check exists, remedy points at it)
  graph-first        1 query/9 reads -> 12/10 -> 8 queries/3 reads   (hook DENIES)
  counting greps     3/16 armed (19%) -> 2/15 armed (13%)   NO ENFORCEMENT

Every directive backed by a hook or a task improved. The one backed only by prose
regressed, in the round where I was most vocal about control arms and where I
personally caught three separate probes returning false negatives. Being aware of
a rule does not make me follow it; a DENY does.

The one bare-interpreter hit is worth reading as a success: the guard denied a
`python3` call, I rewrote it as `curl | jq`, and the work continued. A denial cost
one turn.

kb-session-reflect ALSO reported 6 OWNED false positives, all of them commands
that merely QUOTED a rule's pattern inside a timing harness — in the round that
was fixing those rules. The noise is maximised exactly when the rules are being
worked on, which is when the section is least trustworthy and most likely to be
read. Filed as #264. The skill file already names this shape ("the rule matches
text ABOUT the rule"); what it did not say is that the false-positive rate is
correlated with the round's subject.

Wrapper candidates, both measured: kb-manifest-add x12 then kb-build (and
kb-build ran TWICE because a manifest was added after the build passed its
alphabetical position), and the background-wait idiom typed x7 — which greps a
process name (a spelling bound) and ends in `tail` (discarding the real rc).
Filed as #265.

## Outcome

- Signal: useful