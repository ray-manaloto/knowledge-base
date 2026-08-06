# Arm Your Own Work: A Fix Is Unreviewed Code

The change you just made to close a finding is **the least reviewed code in the
diff**. It was written under time pressure, by the person who already
misunderstood the area once, and it arrives wearing a finding's authority. Treat
a fix as owing *at least* as much scrutiny as the code it replaces — and
scrutiny means an arm, not a re-read.

## Why this rule exists

This is the most-recorded lesson in the repo's own corpus and, until this file,
**the only one with no rule** — measured in the 2026-08-06 self-reflection pass:
9 rounds of handoffs and 6 work-memories record it, and a control-armed grep
across all 22 rule files returned zero hits. Those two counts are derived from
the session handoffs in `.agent/plans/`, which are **gitignored** — so the
committed, checkable source is
`docs/research/reports/2026-08-06-self-reflection-pass.md` and the synthesis
beside it, not the handoffs themselves.

It is expensive. One `kb-review` loop ran five rounds without converging, cost
**2.93M tokens**, and was reverted. Round 2 of another found **two defects that
round 1's own fixes introduced**. The countermeasure the corpus records as
actually working is not another review lane — it is **mutating your own fix**.

Four sub-shapes, all observed here:

| shape | worked example |
|---|---|
| **removes a guard nobody re-armed** | adding one guard made two earlier guards' arms survive; each needed a fresh reaching case to show it still held a distinct property |
| **trades one failure for its mirror** | a module built against unknown-as-known collapsed a **CHECKED** answer into unknown |
| **makes the sequence unrunnable** | building #149's criterion "relocated the ticket's own harm instead of removing it" and refused 8 of 21 branches |
| **raises a bound instead of removing it** | `--limit 200` truncates silently exactly as the default did at 30 |

**A live instance, from the session that wrote this file.** Repairing dangling
`[[wikilinks]]`, the correction itself used the phrase "breaks every
`[[wikilink]]` silently" — and a backticked double-bracket token *is* a link
target. The fix for the dangling-link defect **introduced a dangling link**, in
the same edit. It was caught only because the set was re-derived afterwards
rather than the edit being trusted: the count came back one *higher* than the
repair predicted, and the extra one was the fix's own. Seconds to catch here; a
round to catch anywhere else.

That anecdote is deliberately stated without its counts. The store it happened
in is not in this repo and mutates continuously, so a pinned number here would
be unverifiable by construction — which is itself rule 4 below. The mechanism is
the lesson; the tally was never the evidence.

## Rules

1. **Revert the fix and watch its own test go red.** One command. A test written
   alongside its fix routinely cannot fail, and **neither a review lane nor a
   mutation sweep can see that** — an arm mutates production code, so a test
   asserting nothing is invisible to it. Reverting is the only cheap probe that
   catches this class. If the test still passes with the fix removed, you have
   written decoration.

2. **Mutate the fix, not just the original defect.** Re-run the arms *after*
   adding a guard, not only before. And prove the mutation hit the intended
   LINE — three of five "survivors" in one round were a `str.replace` matching
   the wrong occurrence. A survivor is not a coverage gap until the mutant is
   shown to differ there.

3. **An arm score is a statement about your TESTS, never about the PREMISE.**
   17-arm and 21-arm sweeps came back green over a **wrong ownership rule** —
   every arm faithfully mutating a correct implementation of what the tool does
   not do. A 22nd could not have helped: an arm asks "does a test notice this
   line changing", and the premise is not in that question's range. Two things
   do reach a premise, and each found one of these: **running the thing and
   reading its output**, and **reading the tool's own source** for the rule
   rather than inferring it from your docs.

4. **A check you SHIP must declare what it cannot see, and its FAIL arm must
   inject the ABSENCE it exists to detect** — not a corruption of what is
   present. A check that samples its own output is structurally blind to what
   never entered it: one roundtrip reported *"11 tokens sampled, 0 missing"*
   while **974 chars were absent**. Four separate corpus losses happened past a
   green gate — the validator ran, opened the right artifact, and could not see
   the loss class. Ask of every gate you add: *what would be missing that this
   check would still call clean?*

5. **A comment is a claim about the code and owes the same arm as a gate.** The
   worst form is a comment **defending** the choice that is the bug, because the
   prose is what prevents your own re-read and what disarms the next reviewer.
   Observed: a docstring explaining that lexical containment was *deliberate*,
   walked straight through by a symlink the next round; and a comment asserting
   the exact opposite of what the line below it did, found by a cold lane in the
   code its author had documented most confidently.
   Nobody re-reads a comment they agree with. When a comment states an
   ordering, a precondition, or a "before/after", go read the lines — especially
   when you wrote both.

6. **A clean sweep is never evidence the change is correct.** Report what it
   proves (the tests cover these lines) and what it does not. Four clean sweeps
   in this repo — 12/12, 15/15, 17/17, 21/21 — each immediately preceded a real
   blocking defect in the very code they scored, and twice the defect was **in
   the fix**.

## The cheapest version of all of this

Before calling a fix done, ask the three questions in order. Each is one command
or one read:

1. If I revert this, does its own test go red?
2. What input reaches the same verdict by a different route?
3. Does the comment I just wrote describe the line below it?

## Applies to

Every fix in this repo — a code change closing a finding, a rule amendment
closing a judgement failure, a corrected ticket, a corrected work-memory, and a
gate added in response to a loss. It applies with **more** force to a fix
written in the same breath as the finding it closes.

## See also

- `probes-need-a-control-arm.md` — the parent principle; this rule is that
  principle turned on your own remedy. Its rule 9 ("unreachable by construction"
  needs an arm) and its warning that a **predicted** survival owes more evidence
  than a surprising one are the same idea in the other direction.
- `verify-before-advancing.md` — "prove the FAIL direction of anything you add",
  and the evidence discipline a fix's green run still owes.
- `zero-skip-policy.md` — a fix that silences a warning is not a fix.
- `agent-report-persistence.md` — a review lane's finding is only as good as the
  artifact it left; a fix round owes its own report.
