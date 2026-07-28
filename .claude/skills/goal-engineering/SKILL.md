---
name: goal-engineering
description: "Author and audit `/goal` completion conditions as goal+rider document pairs in docs/goals/. Use this whenever the user mentions /goal, a goal condition, a completion condition, a finish line for an agent loop, a long-running or unattended round of work, or asks whether a goal is well-formed, unambiguous, or safe to set — and whenever they paste goal text for review. Use it BEFORE any /goal is set, even if the user does not name this skill; an unaudited condition is the usual cause of a loop that never terminates or one that declares victory on turn one."
argument-hint: "[path to a goal/rider/pair, or nothing to author a new one]"
---

# Goal engineering

A `/goal` sets a completion condition. After every turn a small fast model
(Haiku by default) decides whether it holds, and if not, Claude takes another
turn. That evaluator is the whole ballgame, and it has one property that
determines everything else:

> It does not call tools, so it can only judge what Claude has already surfaced
> in the conversation.
> — `code.claude.com/docs/en/goal.md`

No file reads. No commands. No git. **A clause is legitimate only if a
Haiku-class reader, given the transcript and nothing else, can settle it by
string match.** "The tests pass" is unjudgeable. "The transcript contains
`PASS  gate test rc=0`" is judgeable. Almost every defect in a bad goal traces
back to forgetting this.

## Which mode

Route on `$ARGUMENTS`:

**Empty → author.** The user wants a new round scoped. Go to *Authoring*.

**A path, a pair prefix, or pasted goal text → audit** that. Go to *Auditing*.
A bare pair prefix (no `-goal.md` suffix) audits both halves and their
cross-reference.

**After a round ends → record the outcome.** Go to *Closing the loop*. This is
the part everyone skips, and it is the only thing that makes the next goal
better rather than merely conformant.

## Authoring

A round is one **pair**: a `goal` capped at 4,000 characters (the text pasted
after `/goal `) and a `rider` with no cap. The cap is not a style choice — it is
what `/goal` enforces, and both harnesses tell you to *"put longer instructions
in a file and refer to that file in the goal."* The rider is that file.

Work in this order. The rider is where the thinking goes; compress the goal out
of it afterwards.

1. **Ground in what is actually open.** Read the newest `.agent/plans/session-*.md`
   and the tracked state. A goal invented from the conversation instead of the
   repo will name work that is already merged.

2. **Pick the headline word.** One word naming *the state of the world after the
   round* — `Legible`, `Coherent`, `Liveness`. If you cannot pick one, the scope
   is more than one round: split it and say so. This test is cheap and it is the
   one that most often prevents a goal that can never be satisfied.

3. **Query the graph before inventing anything.** `mise run kb-query -- "<question>" --prose --idf`
   reads the ingested goal-engineering corpus at zero LLM cost. Prior lessons —
   including outcomes recorded by step 8 — live there.

4. **Write the rider**: phases (each with its depth tests where it changes code),
   the preserve list in full, posture, an explicit out-of-scope list, and the
   sentinel formats. `references/conventions.md` has the section-by-section
   recipe and a worked example.

5. **Compress the goal out of the rider**, using the skeleton in
   `references/conventions.md`. Two sections carry most of the weight and are the
   ones most often skipped:
   - **Posture** — what this round will *not* do, mostly negations. An agent
     under pressure invents solutions; posture is the fence.
   - **Preserve** — the change-everything-except list. Without it, the cheapest
     way to satisfy any metric is to delete the thing the round exists to
     protect. This is Goodhart, and it is not hypothetical: a consistency pass
     eventually removes the banner, *because removing it improves the metric*.

6. **Audit your own draft** — run the *Auditing* section below on it. Do not skip
   this because you just wrote it; the defects this catches are structural, not
   careless.

7. **Write the pair to `docs/goals/`** using the naming schema, then tell the
   user to paste the goal file's contents after `/goal `. You cannot set a goal
   yourself — `/goal` is typed by the user. Say so plainly rather than implying
   it is armed.

8. **Record it.** `mise run kb-remember -- --question "..." --answer "..." --outcome useful`
   then `mise run kb-reflect`. Record the goal, its headline word, and its audit
   verdicts — so step 3 has something to find next time.

## Auditing

Run the mechanical checks first, because they are free and they tell you where
to look:

```bash
mise run kb-goal-check -- <path|pair-prefix>
mise run kb-goal-check -- --text "GOAL: ..."   # a draft that is not a file yet
```

It reports OK / WARN / FAIL per check and **always exits 0** — a goal document
is authored input, not repo source, so read the report, not the rc. It owns
everything decidable without a model: character count (characters, not bytes —
`wc -c` over-counts and will send you trimming a goal that already fits),
required sections, naming schema, headline-word count, sentinel format, turn
bound, posture negations, preserve list, and the rider's structure.

Then apply the judgement tests it cannot: **`references/rubric.md`** holds all
twelve, each with a bad example and its rewrite. The four the checker cannot
reach, and which catch the expensive defects:

- **T4 Goodhart** — could a lazy agent satisfy this clause by *destroying*
  something? If the cheapest satisfying action is deletion, the clause is wrong.
- **T7 one-interpretation** — can you quote the exact substring a reader would
  search for? If not, two reviewers will disagree about "done".
- **T9 one round** — does the headline word actually name the end state, or is it
  a bag holding two rounds?
- **T12 stale evidence** — could this be satisfied by text already in the
  conversation? Setting a goal *starts a turn with the condition as the
  directive*, so anything the condition spells out is in the transcript at turn
  0. This is the subtlest defect in the set and the easiest to reintroduce.

Report verdicts as a short list, then **rewrite the failing clauses** rather than
only naming them. A verdict without a replacement puts the work back on the user.

## Closing the loop

When a round ends, come back and record what actually happened:

```bash
mise run kb-goal-outcome -- <pair> --result achieved|cleared|stalled|blocked \
  --turns <n> --note "which clause kept failing, and why"
```

That writes through `kb-remember` + `kb-reflect` and flips the Status cell in
`docs/goals/README.md` — one command, so the step that is easiest to skip is
also the cheapest to do.

**`cleared` and `stalled` are not failures to hide.** They teach more than
`achieved`, because they say the *condition* was wrong rather than the work —
which is why the recorder tags them `corrected` rather than `useful`. A skill
whose memory contains only successes has learned nothing about its own
conventions.

This matters more than it looks. The conventions in this skill are hypotheses
about what makes a goal work; only outcomes test them. The one worked example so
far: a condition requiring `"N passed"` from `mise run test` would have looped
forever, because that task runs pytest under `-qq` and the string never appears.
Nothing but a recorded outcome finds that class of defect.

## Keeping this skill current

`/goal` is young and the docs move. `currency.toml` carries a `[tool.claude-code]`
entry tracking the CLI version and a content fingerprint of the `/goal` and hooks
docs pages, and the SessionStart hook runs `mise run kb-currency-check` every
session. **When it reports drift on those pages:** re-read the changed page,
re-ingest it through the `kb-curator` skill so the graph carries current truth,
and update `references/` here in the same change — a skill and a doc that
disagree is worse than either alone. The `tool-currency` skill owns that loop.

Do not treat this file as the authority on `/goal` semantics. The graph and the
live docs are; this file is the technique built on top of them.

## References

- `references/rubric.md` — the twelve ambiguity tests, each with a bad example
  and its rewrite. Read this whenever auditing, and when a clause feels vague but
  you cannot say why.
- `references/conventions.md` — the goal and rider recipes, the naming schema,
  the sentinel formats, and the sources this technique comes from.
