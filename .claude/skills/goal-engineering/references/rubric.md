# The thirteen ambiguity tests

Apply **per clause, not per document** — a goal is only as unambiguous as its
weakest clause. Any FAIL is a defect. Each test below gives the question, a bad
example, and its rewrite.

`mise run kb-goal-check` decides T2, T5, T6, T8, T9 and the structural checks
mechanically. **T1, T3, T4, T7, T10, T11, T12, T13 need judgement** and are why this
file exists.

The operating constraint every test serves:

> The evaluator runs on whichever provider your session is configured for. It
> does not call tools, so it can only judge what Claude has already surfaced in
> the conversation.

## T1 — transcript-visibility

**Can the evaluator settle this by reading conversation text alone — no tool
call, no file read, no command?**

- BAD: `graphify-out/graph.json contains the new source's nodes` — it cannot open
  a file, so it will guess, or reward a bare assertion.
- GOOD:

```text
Claude has run `mise run kb-query -- "TERM"` and pasted its stdout, and that
output cites sources/extractions/CHUNK.json
```

Note the shape: **an action that produces text, plus a property of that text.**

## T2 — literal-token (no adjectives)

**Does every completion-bearing phrase name a literal string, number, threshold,
filename, or command — rather than an adjective requiring taste?**

Fails on: *good, clean, proper, reasonable, major, minor, adequate, complete,
robust, comprehensive, well-formed, sensible, thorough.*

- BAD: `the rubric is comprehensive and the scorecard is usable`
- GOOD: `references/rubric.md contains a "## T13" heading and thirteen "## T<n> —" sections`

> "Make it good" isn't a finish line. "Scores over 8+ out of 10 using my custom
> grading skill" is.

Procedure: underline the word carrying the pass/fail judgement. If you cannot
say what string or number a reader would search for, it is an adjective in
disguise.

## T3 — stated check

**Does the clause name HOW the state is proved — a command and its expected
result — not only what state is wanted?**

- BAD: `the lint gate is green` — which lint, run how, green meaning what?
- GOOD: `Claude has run "mise run lint > /tmp/lint.log 2>&1; echo rc=$?" and
  pasted the tail showing "rc=0"`

The redirect-and-echo shape is deliberate: a piped `| tail` returns tail's exit
code and masks a failed gate.

## T4 — Goodhart

**Could a lazy agent satisfy this clause by DESTROYING something?**

If the cheapest satisfying action is deletion, the clause is wrong and the fix is
not a better metric — it is an explicit preserve list.

> That list is not decoration. It is the agent's permission slip: change
> everything except these. Without that list, an agent doing an editorial pass
> eventually decides the cyan banner is "inconsistent" and removes it. Removing
> it improves the audit metric.

- BAD: "no `[redacted]` appears in any task output" — satisfied by silencing the task
- GOOD: the same clause, plus a Preserve list naming the outputs that must still
  print what they print

## T5 — partial-completion (denominator)

**Does a partially-complete state read as complete?** A clause over a set needs a
named denominator.

- BAD: `the gates pass`
- GOOD: `all four of PASS  gate lint rc=0, PASS  gate test rc=0, PASS  gate
  brain-audit rc=0, PASS  gate eval rc=0`

## T6 — floor and ceiling

**Can it terminate at all, and can it terminate too early?**

Two failure directions, and a goal needs a defence against each:

- *No ceiling* — no turn or time clause means the loop runs until you clear it.
  Nothing else bounds it. The bound is prose inside the condition, not a flag.
- *No floor* — a disjunct like "or the cause is not established" is satisfiable
  on turn one by declaring it. Give every escape arm a minimum: N distinct
  probes, each with its command and pasted output.

Also make the bound a **satisfiable disjunct** the evaluator can say yes to
(`... OR Claude's latest message is GOAL-BLOCKED: <reason>`), not a footnote —
there is no documented "I am blocked, hand back" primitive.

## T7 — one interpretation

**Can you quote the exact substring a reader would search for?** If two reviewers
could disagree about whether the clause holds, it has two interpretations.

- BAD: `the finding is recorded`
- GOOD: `a REDACT-FINDING: line appears, immediately followed by a
  REDACT-FINDING-ARM: line`

## T8 — scope fence

**Does the goal say what must NOT change?** Posture is a fence and a fence is
made of negations; a posture with none is a wish.

> An autonomous agent under pressure will invent solutions. Posture is the fence
> that keeps it from inventing one outside this round.

## T9 — one round

**Is there exactly one headline word, and does it name the state of the world
after the round?** If two candidate words fit, you have two rounds. Bundling them
gives the agent an arm it cannot close — a goal that can never be satisfied.

Related: the character count. Past ~4,100 the goal is doing work that belongs in
the rider.

## T10 — proxy signal

**Is narration being accepted as evidence?** "I ran the tests and they passed" is
a claim; the pasted output is evidence.

> Do not accept proxy signals as completion. Treat uncertainty as not achieved.
> Do more verification or continue the work.

- BAD: `Claude has verified the fix`
- GOOD: `the command and its output appear in the message, and the sentinel
  naming that command's rc appears immediately below it`

## T11 — off-transcript evidence

**Could the evidence be produced somewhere the main transcript never sees?**

The evaluator sees only the main conversation. A probe run inside a subagent, a
`Workflow` fan-out, or a background task is invisible to it.

- BAD: `a review subagent has verified the diff`
- GOOD: `the main conversation contains the reviewer's verdict pasted verbatim,
  including its file:line findings or the literal line NO FINDINGS`

## T12 — stale evidence

**Could this be satisfied by text that appeared EARLIER — including in the goal's
own first turn?**

Setting a goal *starts a turn with the condition itself as the directive*, and
the evaluator is sent "the condition and the conversation so far". So every
literal string spelled out in the condition is already in the transcript at turn
0. A clause reading "the transcript contains `FOO`" is arguably satisfied by the
condition quoting itself.

- BAD: `the transcript contains "GOAL-CHECK: PASS"`
- GOOD:

```text
Claude's most recent message ends with `GOAL-CHECK: PASS — CMD rc=0 @ SHORTSHA`,
with that command's output immediately above it
```

`rc=` and `@<sha>` carry values that did not exist when the goal was written.
Pair it with an explicit line in the goal: *the text of this condition is not
evidence.*

## T13 — stated connective

**When the condition has more than one clause, does it say how they combine?**

A list of bullets followed by a bare `or` has no defined meaning, and the two
readings usually differ by the entire round.

- BAD:

```text
Done when:
- graphify-out/ no longer contains any [redacted] artifacts
- the test suite passes with no failures
- a review subagent has confirmed the change is correct
- the transcript contains "REDACTION-DONE"
- or the cause is not established
```

  Read as `(1∧2∧3∧4) ∨ 5`, the whole round collapses into bullet 5. Read as
  `1∧2∧3∧(4∨5)`, it collapses into bullet 4 plus three already-true conditions.
  **Both parses terminate on turn one**, for different reasons.

- GOOD: `Stop when ALL of 1–4 are present, OR Claude's most recent message is
  GOAL-BLOCKED: …` — the skeleton's own wording, which states the quantifier
  over the conjunction and marks the escape arm as the only disjunct.

Never leave the operator implicit in something you will walk away from for
eight hours. An evaluator asked to settle an ambiguous boolean will pick a
reading, and it will not tell you which.

**Provenance:** this test is not from the source essays. It was found by the
**no-skill baseline** during the skill's own scoring round, on a condition
carrying seven deliberately planted defects — it was the one defect nobody had
planted, and the arm *with* the skill missed it. A rubric that only encodes
what its author already knew cannot find this class; the honest response is to
add the test, and to note where it came from.

## Scorecard

Run down this list against a finished goal; each is answerable in under a minute.

- [ ] Every clause settleable from transcript text alone (T1)
- [ ] No adjective carries a verdict (T2)
- [ ] Every state has a named proof command (T3)
- [ ] No clause is satisfiable by deleting something; a preserve list exists (T4)
- [ ] Every set-clause names its denominator (T5)
- [ ] A turn/time bound exists AND every escape arm has a minimum (T6)
- [ ] Every clause quotes the substring a reader would search for (T7)
- [ ] Posture is present and made of negations (T8)
- [ ] Exactly one headline word; under 4,000 characters (T9)
- [ ] No narration accepted in place of pasted output (T10)
- [ ] Subagent/background evidence must be restated in the main conversation (T11)
- [ ] Every sentinel carries a run-specific value; condition-text disclaimed (T12)
- [ ] A multi-clause condition states how its clauses combine (T13)

## The honest residual

Ceccarelli's critique of this whole feature is worth carrying rather than hiding:

> Codex's /goal and Claude Code's /goal both lean on an LLM-as-judge inside the
> same harness: the agent (or a sibling model) is asked whether it's done, which
> is opinion, not evidence.

His answer is an external watchdog that re-runs the checks and signs results with
a secret the agent cannot read. We do not have that. Our hardening is weaker and
worth stating plainly: the strings are **exact**, so a paraphrase fails the
match, and they are **produced by code the agent did not write this round**, so
forging one means editing a gate — which the preserve list forbids. That is
strictly less than a signed receipt. Say so rather than implying the loop is
closed.
