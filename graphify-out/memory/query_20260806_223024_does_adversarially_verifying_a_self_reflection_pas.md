---
type: "query"
date: "2026-08-06T22:30:24.305251+00:00"
question: "Does adversarially verifying a self-reflection pass's findings actually change the answer, or is it ceremony?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does adversarially verifying a self-reflection pass's findings actually change the answer, or is it ceremony?

## Answer

Yes, decisively — and the finding is about the READERS, not the corpus.

Eight claims from the pass were routed to kb-adversarial-verifier. SEVEN changed
the answer. The single confirmation (currency.toml deep-tracks 4 of 14 mise
pins, not 7) still corrected the committed memory it was checked against.

All FIVE proposed issue closes/merges were refuted, each for a different reason:
#134 is completed rather than refuted and its rationale was false on the issue's
own current text; #19 and #200 are an authored upstream-vs-local scope split;
#203 is a proper subset of #21 option 2; the #202-into-#122 superset relation
does not hold; and #23's four asks are all live with ask 4 regressed.

The readers were not sloppy. The close-#134 reader's three-arm probe reproduced
EXACTLY under re-run. It was reading a stale layer of a multi-layer issue. That
is the failure mode to design against: a correct probe pointed at superseded
text.

Consequence for the kb-reflector agent, still unwritten: its output contract
must be candidate findings with a verification cost estimate, never a
recommended-actions list. A pass that filed its readers' conclusions directly
would have closed five live tickets.

## Outcome

- Signal: useful