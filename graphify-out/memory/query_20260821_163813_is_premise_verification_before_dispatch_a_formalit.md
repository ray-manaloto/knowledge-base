---
type: "query"
date: "2026-08-21T16:38:13.682124+00:00"
question: "Is premise verification before dispatch a formality when a cold review follows?"
contributor: "graphify"
outcome: "corrected"
correction: "Belief overturned: \"a cold review + the author are the gate; premise rows are a formality\". Measured this round: every one of the six premise-verifier passes refuted or materially corrected the architect's spec BEFORE dispatch (build_candidate refuses an existing dir; a 4th test pinned 2.1.233; test_currency_ref_bindings asserted the lag EXISTS; `except (Exception, SystemExit)` would trip BLE001; runtime_identity raises SystemExit; verify_plan has 17→23 callers incl. the prototype; the CLI FAIL-arm demo would have tripped member-digest-mismatch first; the 'path-independent' estimator claim was suffix-conditional). Lesson: verify premises per spec, by a cold reader, before any lane runs — the cheapest tokens in the loop; and a cap derivation can be invalidated by the very next commit (58→26 chunks moved $140→$63) — re-derive numbers under the RULE, never carry them.\n"
---

# Q: Is premise verification before dispatch a formality when a cold review follows?

## Answer

Round kb-20260821.03 (branch corpus-gate-bundle-0821): landed PR #422; then built the pre-run gate bundle in six codex lanes (a67cbac4 slice re-attest at 0.9.48/2.1.238 + routing scrub; d8114ab1 #426 derive the plan's graphify runtime + refuse at verify/execute, G5 effort field, F3 cap/timeouts; ebcf9fcb scrub evidence + proxy exemption; 3d9bb3ff #414 content-hash dedupe — 28 groups/257 paths/305 units/571,462 of 1,038,052 tokens (55.1%), 475→170 units, 58→26 chunks; c720f1c9 round-2 fixes + refactor instead of a suppression; 964fb112 dedupe review fixes, cap 140→63 under the one-restart rule), each spec premise-verified (6 passes) and cold-reviewed by Opus (5 passes). Session-review workflow (44 findings, 30 NOT TRIAGED) filed #428–#434. Round 3 (residuals) + re-plan + authority (k) + ship go to the next session, then a go/no-go before the first provider call.


## Outcome

- Signal: corrected
- Correction: Belief overturned: "a cold review + the author are the gate; premise rows are a formality". Measured this round: every one of the six premise-verifier passes refuted or materially corrected the architect's spec BEFORE dispatch (build_candidate refuses an existing dir; a 4th test pinned 2.1.233; test_currency_ref_bindings asserted the lag EXISTS; `except (Exception, SystemExit)` would trip BLE001; runtime_identity raises SystemExit; verify_plan has 17→23 callers incl. the prototype; the CLI FAIL-arm demo would have tripped member-digest-mismatch first; the 'path-independent' estimator claim was suffix-conditional). Lesson: verify premises per spec, by a cold reader, before any lane runs — the cheapest tokens in the loop; and a cap derivation can be invalidated by the very next commit (58→26 chunks moved $140→$63) — re-derive numbers under the RULE, never carry them.
