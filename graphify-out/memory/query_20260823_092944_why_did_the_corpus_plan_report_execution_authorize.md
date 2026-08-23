---
type: "query"
date: "2026-08-23T09:29:44.369711+00:00"
question: "Why did the corpus plan report execution_authorized:true against a Claude version it was never planned for?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why did the corpus plan report execution_authorized:true against a Claude version it was never planned for?

## Answer

The pre-spend identity check was asymmetric: graphify had a plan-vs-live refusal
since #426, Claude did not. Two checks looked like they covered the Claude half
and did not — `_adapter_overlay` compares the live binary against the PREFLIGHT
RECEIPT (both sides current, a tautology w.r.t. the plan), and
`_provider_runtime_reasons` does compare against the plan but takes a
SemanticReceipt, which exists only after a chunk has been PAID FOR. So a Claude
that self-updated between plan and run reached the provider, `_dispose` appended
a failed outcome without raising, and the loop bought and staged-failed every
remaining chunk.

The control arm was empirical rather than argued: `verify` reported
execution_authorized:true with the live binary at 2.1.241 against a plan recorded
at 2.1.240. Any pre-spend plan-vs-live Claude check would have refused there.

Added `_assert_claude_identity_matches_plan` beside the graphify twin in
`execute()`, armed both directions and PER FIELD, with tests for BOTH the helper
and the call site — the graphify twin's own cold review recorded that deleting
the one-line call site left every test green.


## Outcome

- Signal: useful