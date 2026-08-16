---
name: kb-session-reflect
description: "Self-reflect on a finished round: what did it do BY HAND that a mise task already owns, which standing directives it violated and at what rate, which probes could not have answered, and which sequential calls want one wrapper. Use this at the end of any session — it is a step of /clear-prep — and whenever the user asks what went wrong this session, what should be automated, whether a step should become a skill or task, or asks for a retrospective, post-mortem or self-assessment of the round. Also use it before proposing any new automation, so the proposal rests on measured transcript evidence rather than recollection."
---

# Session reflect — what this round did by hand

`mise run kb-session-reflect` reads this project's transcripts and reports the
manual work that already has a home. **The detection is entirely in python**
(`kb_setup.session_reflect`); this skill's job is to say when to run it and how
to read what comes back.

That split is the point. An agent re-deriving "did I violate the interpreter
directive?" by reading its own transcript spends thousands of tokens to produce
a number it will get wrong — the last hand-count took a whole turn and reported
62 violations against 111 compliant calls. The task answers the same question
deterministically, for free, every time.

## Run it

```bash
mise run kb-session-reflect              # this round
mise run kb-session-reflect -- --sessions 5   # is it a habit, not a slip?
```

Default is **one** session, because a round is a session. Widening it answers a
different question and a per-session count read as a per-round count overstates
every rate — ask for more only when you mean *is this recurring?*

## Read it as leads

It always exits 0 and gates nothing. An un-automated step is a statement about
future cost, not a failure, and **an empty section is the common, correct
result** for genuinely novel work — which is what makes a non-empty one worth
reading.

Six sections, each answering one question:

| Section | The question | What to do with a hit |
|---|---|---|
| Hand-rolled work a task owns | did I rebuild something that exists? | run the named task next time; the row carries the command |
| Standing-directive violations | at what RATE did I comply? | a rate, never a yes/no — compare it against the last round |
| Probes that could not have answered | did a negative result get believed? | re-run the probe with a control arm before trusting it |
| Repeated shapes in ONE session | did I type one idea N times? | the strongest wrapper candidate, because it recurred under one context |
| Sequential calls wanting a wrapper | are adjacent calls one intention? | propose `skill -> mise task -> kb_setup module`, in that order |
| Graph-first | did I read source the graph could have answered? | a ratio; a high read-count against zero queries is the signal |

## Turning a lead into a triple

The house mandate is **skill → mise task → python module**, and the module is
where the work goes. A finding earns each layer separately:

- **A module** whenever logic is involved — the varying parts become keyword-only
  parameters, following `skill_lint.check(root, *, glob, exclude, decide)`.
- **A mise task** as the one-line seam over it, so the workflow has a name.
- **A skill only when an agent must be told WHEN to run it.** A task reached from
  an existing skill needs no new skill of its own, and every skill spends the
  skill-listing budget on every turn (`md-size-budgets.md`).

Zero bash, always: logic lives in `kb_setup`, and config carries a seam
(`zero-bash-logic.md`).

## Where it sits relative to kb-distill

Both read the same transcripts through one reader, `distill.tool_uses`, so the
format is parsed in a single place.

They ask different questions, and the difference is measurable rather than
stylistic. `kb-distill` is a **frequency miner**: it groups ad-hoc scripts across
50 sessions by import signature, answering *was a program written twice?* This
asks *what did this round do by hand?* — which frequency mining structurally
cannot see, because a step done once has no frequency to mine.

The gap has a number on it. distill's largest group is **149 hand-written
mutation harnesses across 21 sessions**, every one a fresh scratchpad, while
`kb-arms` has existed to replace them since #160. Run both at a round's end;
`/clear-prep` step 2 does.

## Adding a detector

`OWNED`, `DIRECTIVES` and `UNARMED` are tuples of `Rule` — data, not branches —
so a new detector is a table row plus a test. Give the row a **remedy**: a
finding that names a problem without naming its replacement is a complaint, and
the reader has to go find the task themselves.

**Write the must-NOT-fire arm first.** Every rule here has one, because the
first draft of `piped-rc` matched any `| head`, fired **111 times in one
session**, and looked thorough rather than broken. A rule at that volume teaches
the reader to skip the section holding the real finding.

Four failure shapes this module has already met, all worth checking a new rule
against:

- **The rule flags its own remedy.** `piped-rc` tripped on
  `mise run lint > log; echo "rc=$?" | tail -1` — the exact form it recommends —
  because its gap `[^|\n]*` ran past the `;` to the next pipe. The fix is
  `_SEG`, which refuses to cross a command separator.
- **The rule matches text ABOUT the rule.** A rule table contains every pattern
  by construction, so editing it trips it. `SELF` drops those commands;
  `kb_setup.hook_guard` records the same class.
- **An exemption reaches further than the rule.** `Rule.unless` is searched
  against the WHOLE command, so it is the loosest thing in a rule and the
  easiest to over-write. `piped-rc` has now had two too-wide ones: `\brc=\$\?`
  excused the very violation the rule names (that `$?` is `tail`'s), and its
  replacement `\bPIPESTATUS\b` excused the wrong index and any prose mention of
  the word. It is `PIPESTATUS\[0\]` now — index 0 is the only element holding a
  piped gate's own status. **Write the exemption's must-STILL-fire arm**, not
  just the rule's.
- **A cheap regex hides an expensive one.** A rule meaning "A appears, and later
  B" written as `A.*?B` under DOTALL retries the gap to end-of-string from every
  `A`: measured 5.98 ms at k=200 rising to 395 ms at k=1600. Use `Rule.also` —
  two linear searches — and note that `scan` checks `also` BEFORE `pattern`, so
  the cheap filter is what keeps the expensive one off the adversarial input.

## See also

- `python/src/kb_setup/session_reflect.py` — the detectors and their evidence.
- `.claude/skills/clear-prep/SKILL.md` — step 2 runs this at a round's end.
- `.claude/rules/probes-need-a-control-arm.md` — the norm the UNARMED table encodes.
- `.claude/rules/mise-tasks-only.md` — the canonical task each OWNED row points at.
