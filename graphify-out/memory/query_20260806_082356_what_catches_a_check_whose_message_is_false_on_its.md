---
type: "query"
date: "2026-08-06T08:23:56.947320+00:00"
question: "What catches a check whose MESSAGE is false on its most common input, when every mutation arm is green?"
contributor: "graphify"
outcome: "corrected"
correction: "A green mutation sweep is not evidence a check is right — RUN IT. A 17-arm sweep was green while the merge line printed 'the identities collided and the loss is real' for a ROUTINE re-merge, because re-merging a committed chunk replaces its own nodes one-for-one, which is what every re-merge does. Every test asserted the message was PRODUCED; none asked whether it was TRUE for that input. A check that cries wolf on the most common operation it has is one people learn to skip, which would have cost the whole feature. The discriminator (_self_remerge: committed AND sole claimant) was added only because the first live invocation looked wrong to a human reading it."
---

# Q: What catches a check whose MESSAGE is false on its most common input, when every mutation arm is green?

## Answer

Run it. A 17-arm sweep was green while the merge line printed "the identities
collided and the loss is real" for a ROUTINE re-merge — re-merging a committed
chunk replaces its own nodes one-for-one, which is what every re-merge does.
Every test asserted the message was PRODUCED; none asked whether it was TRUE for
that input. A check that cries wolf on the most common operation it has is one
people learn to skip, which would have cost the whole feature. The discriminator
(_self_remerge: committed AND sole claimant) was added only because the first
live invocation looked wrong to a human reading it.

## Outcome

- Signal: corrected
- Correction: A green mutation sweep is not evidence a check is right — RUN IT. A 17-arm sweep was green while the merge line printed 'the identities collided and the loss is real' for a ROUTINE re-merge. Every test asserted the message was PRODUCED; none asked whether it was TRUE for that input. A check that cries wolf on the most common operation it has is one people learn to skip. The discriminator (_self_remerge: committed AND sole claimant) was added only because the first live invocation looked wrong to a human reading it.