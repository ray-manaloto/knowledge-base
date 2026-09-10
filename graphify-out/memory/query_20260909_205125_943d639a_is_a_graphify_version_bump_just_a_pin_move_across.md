---
type: "query"
date: "2026-09-09T20:51:25.504925+00:00"
question: "Is a graphify version bump just a pin move across its recorded pin sites?"
contributor: "graphify"
outcome: "corrected"
correction: "A DEPENDENCY BUMP IS NOT A PIN MOVE UNTIL THE SDK CONTRACT SAYS SO.\n\n#728 was written and reasoned about as eight pin sites plus a rebase. It was not.\ngraphify 0.9.57 added a keyword-only parameter — `ast_sources` on\n`graphify.build.build_merge` (upstream #3411, graphify/build.py:1560-1625) — and\n`graphify_sdk.py` pins the EXACT signature. The contract refused, at cli.py:142,\nwhich blocked EVERY `kb-setup` command including kb-build and the baseline.\n\nThree durable lessons:\n\n1. The gate worked. It failed CLOSED on a real upstream API change rather than\n   letting a silent behaviour shift through, which is exactly what a signature\n   contract is for. Do not read its refusal as an obstacle to route around.\n2. \"Should we pass the new argument?\" is answerable from the code, not by\n   judgment. Reading `_tier_replacement_sources` settled it: the parameter unions\n   with each chunk's `extracted_sources` into a set governing `new_ast_sources`\n   ONLY, `new_sem_sources` never sees it, our sole call site merges DOC chunks,\n   and `grep -l extracted_sources sources/extractions/*.json` returns 0. Empty\n   before, empty after. That is a measurement, and it belongs beside the contract\n   so the next reader does not re-derive it.\n3. Budget a bump for MORE than its pin sites. A ticket enumerating eight pin\n   sites reads as complete and is not: the SDK contract, a re-derived\n   `sdk_fingerprint_sha256`, and a stored baseline snapshot were all real work\n   the enumeration did not name.\n"
---

# Q: Is a graphify version bump just a pin move across its recorded pin sites?

## Answer

The graphify fork was rebased onto upstream v0.9.57 in the designated checkout
(/Users/rmanaloto/dev/github/ray-manaloto/graphify), all eight KB pin sites moved,
and both .graphify_version stamps now read 0.9.57.

What it took, measured this session:

- Target resolution needs BOTH a version sort AND PyPI confirmation. Version-sort
  alone picks the stale April `v1.0.0` tag. Control-armed: PyPI `1.0.0` -> 404,
  `0.9.57` -> 200, `0.9.99` -> 404.
- Upstream v0.9.53..v0.9.57 = 54 commits / 64 files (the ticket's inherited 49/61
  were measured against v0.9.56). Conflict surface = the same four files
  (CHANGELOG.md, cli.py, llm.py, watch.py) — a prediction in the ticket, now a
  measurement. Eight patches replayed with ONE conflict, in CHANGELOG.md only.
- Acceptance was control-armed BOTH directions: fork suite 18 failed / 5406
  passed, pristine v0.9.57 18 failed / 5358 passed, `diff` of the FAILED sets
  EMPTY, and the +48 passed delta confirmed by a targeted run of the four fork
  test files reporting exactly 48 passed.
- backend_probes survived: claude-cli PRESENT, openai-cli PRESENT, control
  bogus-backend ABSENT.


## Outcome

- Signal: corrected
- Correction: A DEPENDENCY BUMP IS NOT A PIN MOVE UNTIL THE SDK CONTRACT SAYS SO.

#728 was written and reasoned about as eight pin sites plus a rebase. It was not.
graphify 0.9.57 added a keyword-only parameter — `ast_sources` on
`graphify.build.build_merge` (upstream #3411, graphify/build.py:1560-1625) — and
`graphify_sdk.py` pins the EXACT signature. The contract refused, at cli.py:142,
which blocked EVERY `kb-setup` command including kb-build and the baseline.

Three durable lessons:

1. The gate worked. It failed CLOSED on a real upstream API change rather than
   letting a silent behaviour shift through, which is exactly what a signature
   contract is for. Do not read its refusal as an obstacle to route around.
2. "Should we pass the new argument?" is answerable from the code, not by
   judgment. Reading `_tier_replacement_sources` settled it: the parameter unions
   with each chunk's `extracted_sources` into a set governing `new_ast_sources`
   ONLY, `new_sem_sources` never sees it, our sole call site merges DOC chunks,
   and `grep -l extracted_sources sources/extractions/*.json` returns 0. Empty
   before, empty after. That is a measurement, and it belongs beside the contract
   so the next reader does not re-derive it.
3. Budget a bump for MORE than its pin sites. A ticket enumerating eight pin
   sites reads as complete and is not: the SDK contract, a re-derived
   `sdk_fingerprint_sha256`, and a stored baseline snapshot were all real work
   the enumeration did not name.
