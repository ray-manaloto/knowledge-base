---
type: "query"
date: "2026-07-27T22:12:30.547193+00:00"
question: "Which literal success strings can a transcript-checking condition rely on from this repo's gates?"
contributor: "graphify"
outcome: "useful"
---

# Q: Which literal success strings can a transcript-checking condition rely on from this repo's gates?

## Answer

Verified twice, independently, from the code that PRINTS them (never from prose — the prose is stale in 5+ places): 'PASS  gate <name> rc=0' with TWO spaces (pr.py:82); the four gates kb-ship runs are lint, test, brain-audit, eval (pr.py:74); 'ship: OK — PR open, gates green' (pr.py:166, em dash); 'land: OK — PR #N merged, main synced' (pr.py:226); 'OK eval: N passed, N skipped, 0 failed, 0 unarmed' (evals.py:1163). TRAP: 'mise run test' runs pytest with -qq, so 'N passed' NEVER appears in its output — control-armed, bare 'uv run pytest tests/' prints '578 passed' while the task prints none. A condition requiring 'N passed' for the test gate is UNSATISFIABLE; require 'PASS  gate test rc=0' instead. Second trap: kb-currency-check prints NOTHING on success, so silence is indistinguishable from never-ran — a condition must have the agent echo a file-recorded rc, never a piped tail. Third: eval has a third verdict, 'NOT VERIFIABLE HERE: all N case(s) skipped — this is not a pass' (rc=1), so an all-skipped run cannot masquerade as green.

## Outcome

- Signal: useful