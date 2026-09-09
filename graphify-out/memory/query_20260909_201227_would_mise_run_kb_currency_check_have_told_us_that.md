---
type: "query"
date: "2026-09-09T20:12:27.399011+00:00"
question: "Would mise run kb-currency-check have told us that graphify released 0.9.57?"
contributor: "graphify"
outcome: "corrected"
correction: "`mise run kb-currency-check` is described in the root instruction file as\n\"offline ~10ms, silent when clean; + pin-vs-upstream\". Read plainly, that says a\nnew graphify release would show up as drift. For graphify it CANNOT, and the\nreason is structural rather than a bug.\n\nMeasured this session, every value read directly:\n\n- installed `graphify --version` -> 0.9.53\n- `pyproject.toml:32` -> `graphifyy[all]==0.9.53`\n- `graphify-out/.currency-stamp.json` -> `version: 0.9.53`\n- `sources/graphify.manifest` -> `ref = kb-pin/openai-cli-backend-v0.9.53`,\n  `commit = 157a957e89a16246bba3a078de2777711ee85e31`\n\nEvery internal value agrees, so the offline check is silent — correctly, by its\nown rules. And the manifest `ref` is **our own fork branch**, not an upstream\ntag, so even the pin-vs-upstream half is comparing against a ref that only moves\nwhen we move it. Nothing upstream can make that row go red.\n\nThe control arm is in the same run: the same command DID report drift for\nclaude-code (2.1.258 -> 2.1.266) and mise (2026.9.0 -> 2026.9.3), so the check\nwas working and discriminating. It was blind to graphify specifically.\n\nConsequence, and the reason this is a lesson rather than a note: PyPI moved\n0.9.53 -> 0.9.57, four releases, and **the only thing that noticed was Ray\nreading a release announcement.** For the repo whose core dependency graphify is,\nthat is the gap #739 exists to close.\n\nThe general form is this repo's own recurring failure: a fact carried without its\ncondition. \"pin-vs-upstream\" is true for the tools whose manifest pins an\nupstream ref. It is false for the one tool we fork. Carry the condition, and when\nyou meet a claim like it, ask what has to be true for it to hold and whether it\nis true HERE.\n"
---

# Q: Would mise run kb-currency-check have told us that graphify released 0.9.57?

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

- Signal: corrected
- Correction: `mise run kb-currency-check` is described in the root instruction file as
"offline ~10ms, silent when clean; + pin-vs-upstream". Read plainly, that says a
new graphify release would show up as drift. For graphify it CANNOT, and the
reason is structural rather than a bug.

Measured this session, every value read directly:

- installed `graphify --version` -> 0.9.53
- `pyproject.toml:32` -> `graphifyy[all]==0.9.53`
- `graphify-out/.currency-stamp.json` -> `version: 0.9.53`
- `sources/graphify.manifest` -> `ref = kb-pin/openai-cli-backend-v0.9.53`,
  `commit = 157a957e89a16246bba3a078de2777711ee85e31`

Every internal value agrees, so the offline check is silent — correctly, by its
own rules. And the manifest `ref` is **our own fork branch**, not an upstream
tag, so even the pin-vs-upstream half is comparing against a ref that only moves
when we move it. Nothing upstream can make that row go red.

The control arm is in the same run: the same command DID report drift for
claude-code (2.1.258 -> 2.1.266) and mise (2026.9.0 -> 2026.9.3), so the check
was working and discriminating. It was blind to graphify specifically.

Consequence, and the reason this is a lesson rather than a note: PyPI moved
0.9.53 -> 0.9.57, four releases, and **the only thing that noticed was Ray
reading a release announcement.** For the repo whose core dependency graphify is,
that is the gap #739 exists to close.

The general form is this repo's own recurring failure: a fact carried without its
condition. "pin-vs-upstream" is true for the tools whose manifest pins an
upstream ref. It is false for the one tool we fork. Carry the condition, and when
you meet a claim like it, ask what has to be true for it to hold and whether it
is true HERE.
