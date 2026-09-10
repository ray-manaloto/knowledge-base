---
type: "query"
date: "2026-09-09T20:12:27.013296+00:00"
question: "What did landing PR #738 and closing out V0 (#727) require, and what judgment call was made about the chain file's blocker lists?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did landing PR #738 and closing out V0 (#727) require, and what judgment call was made about the chain file's blocker lists?

## Answer

# Round: land V0, close it out, and record the 0.9.57 drift

Session `kb-20260909.003`, 2026-09-09, branch `feat/728-kb-fork-rebase`.

## What the round did

`/session-resume` reconciled clean — `kb-handoff-check` 68 OK / 0 broken, and the
handoff's branch, HEAD, tree and PR all matched the repo. Ray chose "land, close,
drop entry".

`mise run kb-land -- 738` merged pinned to `6f682f79a596016b384957f62a79303256014065`;
squash `80d0d3197c0d912dd2e8a8c4713fee554f8d7763`, main synced. All three advisory
checks ended green, CodeRabbit included. The #724 ordering gate was satisfied
because the previous round closed the corpus loop BEFORE shipping, so the receipt
for `7d3bcb842b84` still covered HEAD under `review.EXEMPT_PATHS`.

#727 closed by hand after checking BOTH routes: `closingIssuesReferences` empty AND
no closing verb immediately before the reference in the squash body — the subjects
read `(#727)` only, and `fix(recall-work):` is a conventional-commit type rather
than a closing word. The arm that settled it was the issue still reading OPEN after
the merge completed.

Branched FIRST to `feat/728-kb-fork-rebase`, then `d60c6a71f808` dropped #727's
chain entry and named `kb-recall-work` in the root instruction file's task
inventory — the item the previous round deliberately deferred to protect its review
receipt. Gates 8/8 at the merge commit.

## A judgment call worth keeping

The three `blockers = [727]` lists on #728, #729 and #731 were LEFT in place after
#727's own chain entry was removed. `next_ticket` resolves every blocker's state
from the live tracker rather than from the chain file (`next_ticket.py:428`), and
it is written to report an out-of-chain blocker by title, so a closed blocker whose
entry is gone reads as satisfied. Stripping them would have deleted Ray's recorded
ordering for no behavioural gain. `next-ticket` reads READY — #728 V1.

## The new fact Ray brought

graphify released **0.9.57**. Verified on PyPI with both control arms: `0.9.53`
present (true positive), `0.9.99` absent (true negative), so the probe
discriminates. We pin `graphifyy[all]==0.9.53`, four releases behind. #728's body
says "v0.9.56 today" and is now stale by one; commented there.

Asked whether "always be rebased on the latest commit" overrode #728's recorded
*"tag by default, HEAD on request"*, Ray chose **latest release tag, checked
automatically** — the pin invariant stands, and "always" means the check fires on
its own. He put the recurring machinery in its own ticket, **#739**, blocked on
#728.


## Outcome

- Signal: useful