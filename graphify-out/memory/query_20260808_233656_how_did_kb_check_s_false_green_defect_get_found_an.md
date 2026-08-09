---
type: "query"
date: "2026-08-08T23:36:56.813006+00:00"
question: "How did kb-check's false-green defect get found and fixed, and what did the three attempts teach?"
contributor: "graphify"
outcome: "useful"
---

# Q: How did kb-check's false-green defect get found and fixed, and what did the three attempts teach?

## Answer

Three defects in one round, each found by a different mechanism, and the sequence is the lesson. (1) A cold lane with a MUTATING brief found a false green: kb-check returned 0 for a directory holding no .py, because ruff/format/ty all answer "no Python files found" with a WARNING AND EXIT 0 rather than a failure. (2) The fix for that introduced its own defect, caught by the control arm written alongside it: python_paths stat'd against the process CWD while the new holds_python resolved against repo_root, so a directory genuinely holding .py was present to one and absent to the other and every tool came back SKIP. (3) The fix was then still INCOMPLETE, and I found that myself by probing the hole I had flagged to the reviewer instead of waiting: rglob does not apply ruff/ty exclusions, so a directory whose only .py sits under .venv answered yes while ruff reported nothing and exited 0 -- the identical false green one layer narrower. A finding is a SAMPLE of a class; fixing the instance you were handed is not fixing the class. The native fix was to ask the tool -- ruff check --show-files prints the files ruff WOULD check -- rather than reimplement three exclusion rule sets, and it fails CLOSED when ruff cannot be run, because handing the verdict to three tools that were never launched is the defect the module exists to remove. The durable habit: after fixing a reviewer's finding, ask what ELSE reaches the same wrong verdict by a different route, and probe that before shipping.

## Outcome

- Signal: useful