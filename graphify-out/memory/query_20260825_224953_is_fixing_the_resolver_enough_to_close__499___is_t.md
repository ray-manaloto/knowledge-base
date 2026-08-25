---
type: "query"
date: "2026-08-25T22:49:53.653658+00:00"
question: "Is fixing the resolver enough to close #499 — is the defect in one place?"
contributor: "graphify"
outcome: "corrected"
correction: "The ticket's stated root cause was `--refs`, and the prior round had already\nrefuted that. This round's own belief was narrower and also wrong: that the #499\ndefect lived in ONE place and that fixing the resolver closed it.\n\nIt was three places, and the second and third were found by readers who had NOT\njust written the fix — a cold lane, twice. The architect swept `upstream.py` for\nstale citations, fixed that sample, and missed two more of the identical class in\nthe same commit, including collateral damage to a page from a different round.\n\nThe correction: **a fix is a sample of a class, and the person who just wrote it\nis the worst-placed reader to find the rest.** Fixing one instance can make the\nothers harder to spot rather than easier, because the surrounding code then LOOKS\ncorrect at a glance. Budget an independent lens per fix round, and treat \"I swept\nfor this\" as covering only the file you were already looking at.\n\nCorollary, measured this round: THREE separate citation-drift instances were\ncaused by insertions in the very commit that wrote the citations. A `file:line`\nis a measurement, and inserting text above it invalidates it silently — including\nin other people's documents.\n"
---

# Q: Is fixing the resolver enough to close #499 — is the defect in one place?

## Answer

Three defects, one class. The round set out to fix #499 (a `mise.toml` pin that
took a git TAG where it needs a bare VERSION) and found the same shape twice
more, each time in a place the previous fix had made HARDER to see.

1. **#499 itself** — `currency apply` carried one resolved string to two write
   targets that spell it differently. `mise ls hk` reported the resulting pin
   `(missing)`. Fixed by normalising PER WRITE TARGET, not at resolve time:
   `verdict.latest` is also what the gates parse, what the report renders, and
   what `resolve_tag` searches for, so stripping upstream would change four
   consumers to fix one.

   Why it went unseen: the only two tools that DECLARE a `tag_prefix` (codex
   `rust-v`, firecrawl-cli `v`) are the only two that CANNOT exhibit it, because
   declaring a prefix is what triggers the strip.

2. **The backend/model/parallel constants** — `--backend claude-cli` was
   hardcoded in `resolve_argv` while the model and parallel env keys were
   separate module constants. Switching only the first left `--model` pointing
   at a variable an `openai-cli` run never reads: an INERT override under a
   confident dry-run.

3. **The dry-run NOTE, then the model VALUE** — found by two cold-review rounds.
   The NOTE hardcoded claude-cli's variable, words, line numbers AND evidence,
   and printed all of it under `--backend openai-cli`. Then round 2 found the
   sharpest instance: the env KEY was backend-derived but the VALUE was not, so
   `GRAPHIFY_OPENAI_CLI_MODEL=claude-opus-5` — a Claude identifier in an OpenAI
   backend's own variable, on any run without `--model`.

The durable finding is (3)'s shape: **fixing the key made the value's blindness
harder to see, not easier**, because the overlay then LOOKED backend-aware at a
glance. A fix can hide its own remaining half.

Also closed: #479 (a parser that took a flag as a value, so `--out --dry-run`
ran a real token-spending extraction into a directory named `--dry-run`), #480
(an ambient `GRAPHIFY_OUT` that relocated the output past every `--out` guard),
#481 (no coverage on the only two functions that spawn a subprocess). All three
were the stated precondition for un-parking `graphify_native_extract`.

Evidence: 27 mutation arms across 5 specs, all died; 5 controls held. Gates 6/6.


## Outcome

- Signal: corrected
- Correction: The ticket's stated root cause was `--refs`, and the prior round had already
refuted that. This round's own belief was narrower and also wrong: that the #499
defect lived in ONE place and that fixing the resolver closed it.

It was three places, and the second and third were found by readers who had NOT
just written the fix — a cold lane, twice. The architect swept `upstream.py` for
stale citations, fixed that sample, and missed two more of the identical class in
the same commit, including collateral damage to a page from a different round.

The correction: **a fix is a sample of a class, and the person who just wrote it
is the worst-placed reader to find the rest.** Fixing one instance can make the
others harder to spot rather than easier, because the surrounding code then LOOKS
correct at a glance. Budget an independent lens per fix round, and treat "I swept
for this" as covering only the file you were already looking at.

Corollary, measured this round: THREE separate citation-drift instances were
caused by insertions in the very commit that wrote the citations. A `file:line`
is a measurement, and inserting text above it invalidates it silently — including
in other people's documents.
