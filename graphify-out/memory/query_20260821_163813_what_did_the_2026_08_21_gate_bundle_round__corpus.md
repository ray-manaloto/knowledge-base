---
type: "query"
date: "2026-08-21T16:38:13.372758+00:00"
question: "What did the 2026-08-21 gate-bundle round (corpus-gate-bundle-0821) change before the graphify deep extraction?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did the 2026-08-21 gate-bundle round (corpus-gate-bundle-0821) change before the graphify deep extraction?

## Answer

Round kb-20260821.03 (branch corpus-gate-bundle-0821): landed PR #422; then built the pre-run gate bundle in six codex lanes (a67cbac4 slice re-attest at 0.9.48/2.1.238 + routing scrub; d8114ab1 #426 derive the plan's graphify runtime + refuse at verify/execute, G5 effort field, F3 cap/timeouts; ebcf9fcb scrub evidence + proxy exemption; 3d9bb3ff #414 content-hash dedupe — 28 groups/257 paths/305 units/571,462 of 1,038,052 tokens (55.1%), 475→170 units, 58→26 chunks; c720f1c9 round-2 fixes + refactor instead of a suppression; 964fb112 dedupe review fixes, cap 140→63 under the one-restart rule), each spec premise-verified (6 passes) and cold-reviewed by Opus (5 passes). Session-review workflow (44 findings, 30 NOT TRIAGED) filed #428–#434. Round 3 (residuals) + re-plan + authority (k) + ship go to the next session, then a go/no-go before the first provider call.


## Outcome

- Signal: useful