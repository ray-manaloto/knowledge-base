---
type: "query"
date: "2026-08-07T01:21:07.171979+00:00"
question: "How do you machine-enforce 'skills call mise tasks that wrap the python library' without writing a second implementation?"
contributor: "graphify"
outcome: "useful"
---

# Q: How do you machine-enforce 'skills call mise tasks that wrap the python library' without writing a second implementation?

## Answer

By reusing the decision function that already existed, rather than writing a
second one.

Ray's directive had been tracked as issue 128 and had sat unactioned; it also
sits in the directive backlog memory. His words: "i keep requesting this and it
is not being done so we need to try and enforce this somehow." What kept failing
was that it stayed prose, in mise-tasks-only.md and zero-bash-logic.md.

The graph decided the design. kb-query --prose --idf returned "graphify: skill
over a Python library" at rank 1 on both framings, and graphify explain gave the
chain: "Lint messages inject remediation into agent context" enables "Enforce
invariants, don't micromanage" defines "Rigid layered architecture with
validated dependencies". So a finding prints the canonical task, never just a
refusal.

hook_guard.decide already owned the redirect table, the read-only allowlist and
the remediation wording, and its docstring says it is public precisely so a gate
can reach it. So there are now two consumers of ONE decision function: the
PreToolUse guard at runtime, and skill_lint at authoring time. A redirect added
to _REDIRECT is enforced in both places with no second table to drift. A test
pins that identity, and the cold lane armed that test by forking the default and
watching it go red. decide is an injectable parameter, which is the reusability
Ray asked for.

The module is about 80 lines because of that reuse. A second implementation
would have been several hundred and would have drifted.

Measured before building: the 6 project skills were ALREADY compliant, 83 mise
run references against 5 bare command lines, all 5 legitimate. So the gate is
green on arrival and what it closes is regression, which was the actual
complaint. Nothing was stopping the next skill from drifting.

The half that is NOT gateable is stated in the module docstring, because issue
128 asked for that explicitly: no check can distinguish a skill that delegates
from one that narrates. That half is a build, tracked as 219.

## Outcome

- Signal: useful