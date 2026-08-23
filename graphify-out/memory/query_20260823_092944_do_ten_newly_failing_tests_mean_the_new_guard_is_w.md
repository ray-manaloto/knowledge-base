---
type: "query"
date: "2026-08-23T09:29:44.662120+00:00"
question: "Do ten newly-failing tests mean the new guard is wrong?"
contributor: "graphify"
outcome: "corrected"
correction: "A guard added to real state finds defects in the FIXTURES first, and that is the\nguard working rather than the guard being wrong.\n\nTen existing tests failed the moment the new check existed. Their fixture\nhardcoded `version=\"2.1.233\"` with zero digests while `config` came from the real\ncommitted plan — internally inconsistent, and passing only because nothing had\never compared the two halves. Note the graphify half of that same fixture WAS\nderived correctly (`accepted_graphify_runtime()`); only the Claude half was\ninvented. The asymmetry in the fixture mirrored the asymmetry in the code, which\nis why one guard exposed both.\n\nThe corrected belief: \"existing tests passing\" is not evidence a fixture is\ncoherent. It is only evidence that nothing checked. When a new comparison makes\nold tests fail, read the fixture before reading the guard.\n"
---

# Q: Do ten newly-failing tests mean the new guard is wrong?

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

- Signal: corrected
- Correction: A guard added to real state finds defects in the FIXTURES first, and that is the
guard working rather than the guard being wrong.

Ten existing tests failed the moment the new check existed. Their fixture
hardcoded `version="2.1.233"` with zero digests while `config` came from the real
committed plan — internally inconsistent, and passing only because nothing had
ever compared the two halves. Note the graphify half of that same fixture WAS
derived correctly (`accepted_graphify_runtime()`); only the Claude half was
invented. The asymmetry in the fixture mirrored the asymmetry in the code, which
is why one guard exposed both.

The corrected belief: "existing tests passing" is not evidence a fixture is
coherent. It is only evidence that nothing checked. When a new comparison makes
old tests fail, read the fixture before reading the guard.
