---
type: "query"
date: "2026-07-30T15:21:26.306283+00:00"
question: "How do you verify a fix round when the kb-review two-round bound is already spent?"
contributor: "graphify"
outcome: "useful"
---

# Q: How do you verify a fix round when the kb-review two-round bound is already spent?

## Answer

Mutate each fix back to its pre-fix LINE and confirm the guarding test goes red, reading a file-based rc. Two probes in this round were themselves broken: one piped pytest into tail so $? was tail's 0 and every mutation read 'still green'; another mutated the token regex rather than the rest-check line the test guards, and correctly stayed green. A third defect was in the TEST — its fixture put the prose heading first, where the harm cannot occur, so it could not fail. Mutation is only evidence when the mutation, the probe's rc, and the fixture all reproduce the real failure.

## Outcome

- Signal: useful