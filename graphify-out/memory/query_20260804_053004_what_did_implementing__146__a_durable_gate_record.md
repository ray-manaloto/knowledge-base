---
type: "query"
date: "2026-08-04T05:30:04.952061+00:00"
question: "What did implementing #146 (a durable gate record) teach about verifying your own verification?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did implementing #146 (a durable gate record) teach about verifying your own verification?

## Answer

Three findings, in order of what they cost to learn.

1. A REVIEW FOUND A BLIND TEST INSIDE A MUTATION-ARM DELIVERABLE. The branch
shipped 20 line-grained mutation arms, all caught, and a second reader still
found an assertion in the same suite that could not fail: it checked a substring
that the per-gate row emits regardless of the summary line under test. Dropping
the clause passed all 42 tests. Mutation arms only cover the claims you thought
to mutate; they are a floor, not a ceiling, and a suite full of control arms is
not evidence that every assertion has one.

2. TWO LANES AGREEING IS THE STRONGEST SIGNAL, AND THE CAUSE MATTERS MORE THAN
THE DEFECT. Both review axes independently found the same guard enforced in one
of two callers: kb-gates refused an unreadable HEAD, the ship path did not, so a
ship would write a record naming no commit. The standards lane went further and
named the cause as duplicated sequence, which turned the fix from "add a second
guard" into "give the sequence one owner". The defect also falsified a sentence
in the branch's own commit message claiming the two callers could not disagree,
which was true of the loop and false of the sequence around it.

3. A HARNESS NEEDS ITS OWN CONTROL ARM, AND A WRITTEN-DOWN LESSON IS NOT A
CARRIED-FORWARD ONE. The mutation harness returned a false negative, reporting a
caught arm as SURVIVED. CPython invalidates a cached bytecode file on the
source's size and mtime in whole seconds, and the harness rewrote one file many
times per second, so two same-size mutations reused the first one's bytecode.
The prior round's harness already cleared the cache and its own report says so;
this one was written fresh and did not carry it. Applying the mutation by hand
settled which side was broken in about a minute. When a probe surprises you,
reproduce by a second route before believing it.

Also settled: a durable gate record must carry whether the working tree was
clean, not only the commit. Recording the commit without recording whether the
tree WAS that commit reproduces the same untrue-artifact defect one layer down,
because gating happens before committing, so the dirty case is the normal one.

## Outcome

- Signal: useful