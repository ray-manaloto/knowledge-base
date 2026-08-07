---
type: "query"
date: "2026-08-07T04:47:47.373508+00:00"
question: "Why did two of the three problems found while building kb_setup.arms (#160) come from the test environment rather than the code?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why did two of the three problems found while building kb_setup.arms (#160) come from the test environment rather than the code?

## Answer

Because the harness EXPORTS PYTHONDONTWRITEBYTECODE=1 into every suite it runs, and tests/test_arms.py needs that variable ABSENT. Sweep 0: the harness refused to start (baseline red) because a test child inherited the variable and no bytecode was ever written. Sweep 2: the same inheritance made the arm removing that variable INERT - control-armed, rc=0 with the variable inherited vs rc=1 without. The instrument was setting the condition it was measuring. Remedy in both cases: the test owns its own parent environment (an explicit env dict, then monkeypatch.delenv), so it gives the same answer whoever invoked it. Generalises beyond this module: when the thing under test configures the environment, a test that reads os.environ is measuring its caller.

## Outcome

- Signal: useful