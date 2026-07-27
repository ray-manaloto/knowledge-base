---
type: "query"
date: "2026-07-27T21:25:07.875509+00:00"
question: "When a security strip must cover a namespace, is a name list or a prefix rule the right shape?"
contributor: "graphify"
outcome: "useful"
---

# Q: When a security strip must cover a namespace, is a name list or a prefix rule the right shape?

## Answer

Prefix, when the namespace has an owner-declared marker. Measured on the __MISE_ fix (2026-07-27): a name list covering __MISE_DIFF/__MISE_SESSION passes every test today and fails open silently the day mise adds a third var — that is exactly the token-spelling bound probes-need-a-control-arm.md warns about. The host carried six __MISE_* vars, only two of which the handoff named. Evidence that __ is the private marker: mise's own docs give __MISE_ORIG_PATH 0 hits vs 32-file controls. The control arm matters as much as the rule: a test proving public MISE_* SURVIVES is what stops the prefix being widened by one underscore. Mutation probe confirmed it discriminates — widening __MISE_ to MISE_ failed 3 tests, removing the clause failed 2.

## Outcome

- Signal: useful