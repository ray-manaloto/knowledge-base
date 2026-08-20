---
type: "query"
date: "2026-08-20T09:41:15.782879+00:00"
question: "What did the eight-round PR bot loop on #406 cost, and what did it actually find?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did the eight-round PR bot loop on #406 cost, and what did it actually find?

## Answer

# The eight-round PR bot loop on #406: what it cost and what it bought

## The shape

One cold codex lane (10 findings) was followed by EIGHT PR bot passes, because
every fix commit triggers a fresh pass. Ray's stop rule was "loop until a pass
returns zero real findings". It took 8.

| bot | findings | real | refuted | no-op |
|---|---|---|---|---|
| graphify-labs | 25 | 13 | 9 | 3 |
| CodeRabbit | 5 | 5 | 0 | 0 |
| Repowise | 4 co-change | 1 | 3 | - |

## The finding that justifies the whole loop

`start_new_session`, added in round 2 so the gate's timeout could kill hk's
LINTERS rather than only hk, is exactly what takes hk out of the terminal's
FOREGROUND PROCESS GROUP. A terminal delivers SIGINT to that group only. So
Ctrl-C stopped reaching hk, and an interrupt left hk plus every linter it spawned
running orphaned.

A fix for one leak created another, in the opposite direction, four rounds apart.
Nothing in the gates, the type checker or 15 mutation arms could see it: the
suite never sends SIGINT.

## The self-generated yield

Passes 3-8 found ZERO defects in the branch's original subject. Every real
finding was in code the review process itself caused to be written, and three
were regressions introduced by an earlier round's fix. The loop was converging on
its own tail, not on the branch.

That is not an argument against it — two findings were worth any cost:
- the naive-datetime crash, found INDEPENDENTLY by both bots. One offsetless line
  in any transcript aborted the whole scan. I introduced it: ruff flagged
  `.replace("Z", "+00:00")` as redundant (it is, on 3.11+) and removing it read
  as pure cleanup while deleting the only thing that guaranteed a tzinfo.
- `--window -5` printed NO EVENTS at rc 0 with the window rendered `+/--5s` - a
  FALSE NEGATIVE from the one module built to refuse false negatives.

## graphify's precision degrades as a diff stabilises

9 refuted of 25, and FOUR of those nine were the SAME fabricated location: an
"unclosed docstring" / "stray bare name" at `tests/test_hk_test.py:312` and
`:326`, across four consecutive passes, in a file that parses and whose suite is
green. A repeated line number across unrelated files is itself the tell - one
pass anchored the same claim at `:312` of TWO different files.

Every graphify finding is self-labelled "agreed by 2 of 2 members but NOT
verified (no proof, no reproducing execution)". That caveat is load-bearing and
each refutation was settled by READING THE CITED LINE, never by argument.

CodeRabbit went 5 for 5 - but was RATE LIMITED on three of eight heads, recorded
in every receipt as a gap, never as a pass.

## Two survivors, both defects in MY tests

- F6 survived because the arms spec omitted `test_write_attribution.py` from
  `suites` - the mutation applied and its named test never ran. A hand-run failed
  both its tests.
- F9 survived because its test asserted only `rc == NOT_RUN`, which the mutation
  ALSO reaches by a different route (no transcripts). It now asserts the message.

A survivor is a claim about the HARNESS until the suite list and the assertion
have both been checked.

## `--dry-run` earned its keep twice

Extracting `_parse_args` (to fix C901 by EXTRACTION rather than by raising the
threshold - a relaxation is what a clean sweep cannot speak to) moved three arms'
anchors. `kb-arms --dry-run` named all three before any suite ran. An earlier
restructure had done the same to one arm.

## How to read a check run from the CLI

The PR web UI was the only known route to graphify's "3 more findings on lines
outside this diff". It is reachable:

    gh api repos/{o}/{r}/commits/{sha}/check-runs        # enumerate + ids
    gh api repos/{o}/{r}/check-runs/{id} --jq .output.text
    gh api repos/{o}/{r}/check-runs/{id}/annotations

## The structural gap this exposes

`kb-review` bounds its OWN lane at two rounds and says NOTHING about PR bot
rounds, which have no bound at all. That asymmetry is what made this eight
rounds. The skill should carry a bot-round bound, or an explicit statement that
bot rounds are unbounded by design and the human decides.


## Outcome

- Signal: useful