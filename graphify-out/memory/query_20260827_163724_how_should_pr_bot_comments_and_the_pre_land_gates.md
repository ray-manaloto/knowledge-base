---
type: "query"
date: "2026-08-27T16:37:24.527998+00:00"
question: "How should PR bot comments and the pre-land gates be treated before kb-land?"
contributor: "graphify"
outcome: "useful"
---

# Q: How should PR bot comments and the pre-land gates be treated before kb-land?

## Answer

RAY'S STANDING DIRECTIVE, 2026-08-27, verbatim: "yes, always review all pr bot comments,
they are free and should never be dismissed."

This is stronger than the existing doctrine and supersedes how it was being read.
`.claude/rules/verify-before-advancing.md` and `kb_setup.pr._ADVISORY_CHECKS` say
CodeRabbit and `Repowise / code health` are ADVISORY — blocking in no bucket. That was
being treated as licence to glance at a red advisory check and move on. It is not. The
rule says advisory checks are "still read and reported, never silently dropped", and
Ray's directive settles the ambiguity: NEVER BLOCKING is not NEVER READ.

Measured on PR #550, which is why this is worth keeping:

- `Repowise / code health` reported FAIL and one concrete instruction — run
  `tests/test_build_outcome.py`, `tests/test_graph_detect_preflight.py`,
  `tests/test_graphify_sdk.py`, `tests/test_graphify_env.py`, "they import the changed
  files". Run explicitly: ruff/format/ty/pytest all rc=0. `mise run kb-check` had only
  covered the changed files' OWN tests, so nothing before this had asked the
  reverse-dependency question. The bot's blast-radius map is the thing this repo's own
  graph could not produce.
- CodeRabbit's check read `pending` and its comment said "Currently processing new
  changes" — a review IN PROGRESS, not a clean one. A pending advisory check is not a
  green one, and reading the comment rather than the check state is what distinguishes
  those. `kb-land` gives them a bounded window and then proceeds; that bound exists to
  avoid waiting on someone's rate limit, never to avoid reading the result.

TWO SHIPPING MECHANICS this round paid for:

1. `kb-ship` REFUSES on a stale handoff HEAD line. The newest `.agent/plans/session-*.md`
   recording this branch had `HEAD: 9f8f9b76`, three commits behind. That is the gate
   working. The cheap order is: write the handoff BEFORE `kb-ship`, not after. Doing it
   after costs a refused ship plus a re-run of every gate.
2. `kb-handoff-check`'s reconcile step demands each prior owed item be named LITERALLY.
   A glob does not satisfy it: writing "the two `graphify-out/memory/query_20260827_0638*.md`
   files" left two entries broken, and naming both filenames in full cleared them. It took
   three rounds to reach rc=0 — budget for that, or write the carry-forward table by
   copying the previous handoff's item names verbatim and appending a verdict to each.

AND one that recurred despite being in memory already: prose passed to a CLI goes via a
FILE. `mise run kb-remember -- --correction "...\`affected\` resolves..."` had the
backticked word executed by zsh as a command substitution — `zsh: command not found:
affected` — and the saved correction had a HOLE where the word should be. Caught only by
reading the written file back. `--correction-file` is the fix, and STAT WHAT YOU WROTE is
the general rule: the write succeeded, the exit code was 0, and the content was wrong.


## Outcome

- Signal: useful