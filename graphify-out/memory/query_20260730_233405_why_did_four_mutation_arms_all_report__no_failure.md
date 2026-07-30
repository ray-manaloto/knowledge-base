---
type: "query"
date: "2026-07-30T23:34:05.706121+00:00"
question: "Why did four mutation arms all report 'no failure' at once?"
contributor: "graphify"
outcome: "corrected"
correction: "I treated a uniform negative result across four independent arms as four findings instead of one probe defect."
source_nodes: ["tests/test_graph_docs_kind.py"]
---

# Q: Why did four mutation arms all report 'no failure' at once?

## Answer

THE PROBE WAS BROKEN, NOT THE GATES. I set T='fileA fileB' and passed $T to pytest. ZSH DOES NOT WORD-SPLIT UNQUOTED PARAMETERS (unlike bash), so pytest received ONE argument — the literal string 'tests/a.py tests/b.py' — found no such path, exited 4, and my 'grep ^FAILED' matched nothing. Every mutation 'passed' by never being tested. Use ${=T} in zsh, or inline the paths. WHAT CAUGHT IT: the restore/control line printed NOTHING either, and a clean tree was guaranteed to print something; silence where output is guaranteed is the tell. THE REAL LESSON: I had control-armed every gate all session and never the MUTATION RUNNER itself. A harness that reports 'arm is dead' for all N arms simultaneously is far more likely to be broken than N independent fixes all being untested. Always put an unmutated CONTROL ROW first in a mutation sweep — it costs one run and converts a silent false-negative into an obvious one.

## Outcome

- Signal: corrected
- Correction: I treated a uniform negative result across four independent arms as four findings instead of one probe defect.

## Source Nodes

- tests/test_graph_docs_kind.py