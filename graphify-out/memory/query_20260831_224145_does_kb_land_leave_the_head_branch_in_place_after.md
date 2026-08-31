---
type: "query"
date: "2026-08-31T22:41:45.643205+00:00"
question: "Does kb-land leave the head branch in place after a squash-merge?"
contributor: "graphify"
outcome: "corrected"
correction: "I asserted, in a dispatch brief to an advisor lane, that `kb-land` \"does not\ndelete or reset the head branch afterward\". That is FALSE: `--delete-branch` sits\nat `python/src/kb_setup/pr.py:817`, in the same `gh pr merge --squash` call.\n\nTwo failures, and the second is the one worth keeping.\n\nFirst, I stated a fact about code I had only partially read — a grep for\n`squash|--merge|--rebase` surfaced line 816 and I concluded from its absence in\nmy own narrow output, without control-arming the grep.\n\nSecond, and new: I found the error MYSELF twenty minutes later while re-deriving\nthe advisor's claims, and corrected it on the artifact page and in a message to\nRay — but never to the lane I had already handed the wrong version to. The\nadvisor went on reasoning from my bad premise until it read `pr.py` itself and\nrefuted me.\n\n**A correction owes a message to every consumer that received the wrong version,\nnot only to the person in front of you.** A lane is a consumer; so is a committed\ndoc, a plan file, and an open issue. Fixing the visible copy while a working copy\nof the error runs elsewhere gives one wrong fact two lifetimes.\n\nIt cost more than a re-derivation: the wrong premise made \"delete the landed\nbranch\" look like the obvious prevention, and that option is empirically refuted\n— remote deletion was already in force and did not prevent the incident. An\nentire prevention design was being ranked around a fact I had already corrected\nin one place.\n\nWhat caught it: the advisor had been told to VERIFY the facts in its brief rather\nthan accept them. Put that instruction in every dispatch.\n"
---

# Q: Does kb-land leave the head branch in place after a squash-merge?

## Answer

# Why PR #639 could not merge, and what three review lanes found in the fix

## The blocker

PR #637 was squash-merged from `chore/cli-currency-sweep`, and then that SAME
branch was reused: new commits added, PR #639 opened from it. A squash-merged
branch shares zero commits with what landed, so continuing to work on it does not
risk a conflict — it GUARANTEES one on every file the squash touched.

Measured: `git merge-tree --write-tree HEAD origin/main` rc 1, four conflicts.
Control-armed at the previous commit, which named only three — the round's own
last commit added the fourth, so the handoff's figure was right when written and
stale by one on arrival.

Resolution: all four files take the pre-merge HEAD content, whole-file, because
for each one `main`'s differing content was a value HEAD deliberately superseded.
Verified by `git diff --stat a72eacf3 HEAD` returning EMPTY — zero delta across
every file, not merely the four.

## The mechanism is supported, not a gap

`kb-land` already passes `--delete-branch` (`pr.py:817`), so remote deletion was
in force and did not prevent this. `ship_main` recreates the branch
(`pr.py:671`), and `_open_or_update_pr` (`pr.py:491`) deliberately opens a NEW PR
when the old one is MERGED. `tests/test_pr.py:863`'s docstring already names the
state: "land deletes the remote branch and leaves the local one, and every PR in
this repo is MERGED." The repo knew; nothing acted on it.

So deleting branches is not the fix. The ranked prevention is: refuse a ship from
a branch whose MERGED PR's commit is not an ancestor of HEAD (detects the cause),
plus a pre-ship mergeability check that FETCHES and refuses on fetch failure
(a stale `origin/main` returns rc 0 — in this incident it would have reported
#639 perfectly mergeable). They are complements: reuse guarantees a bad ANCESTRY
signature, not a textual conflict, so identical work merges cleanly past a
conflict check.

## What the review lanes found — eleven, all in work just completed

Three rounds: two codex on this session's own commits, one Gemini across all 36
files (chosen because part of the range was codex-authored, so a codex reviewer
would have been same-family while the receipt claimed otherwise).

Among them: a citation to a rule that does not exist; a new rule contradicting
the rule below it with no statement of which wins; a fix that solved one problem
with two different shapes in two files, guaranteeing drift; an EIGHTH graphify
pin site (`graph.py:541`) byte-identical to the manifest, which tier 1 of the
gate shipped this round compares — a manifest-only bump would have red-lit that
gate and been blamed on it; a docstring stating the opposite of its own
mechanism while its conclusion stayed true; a control-arm test that could not
fail; and a skill whose prose instructed a step its own code block omitted.

## Gate behaviour worth keeping

`kb-ship` refused twice, correctly both times. First: a receipt covering 7 files
when the branch's base had moved and the real range was 36 — "a partial range
does not gate the whole branch". Second: a handoff citing a HEAD that work had
moved past. Neither refusal was a defect; both were the gate doing its job
against a claim that had quietly gone stale.


## Outcome

- Signal: corrected
- Correction: I asserted, in a dispatch brief to an advisor lane, that `kb-land` "does not
delete or reset the head branch afterward". That is FALSE: `--delete-branch` sits
at `python/src/kb_setup/pr.py:817`, in the same `gh pr merge --squash` call.

Two failures, and the second is the one worth keeping.

First, I stated a fact about code I had only partially read — a grep for
`squash|--merge|--rebase` surfaced line 816 and I concluded from its absence in
my own narrow output, without control-arming the grep.

Second, and new: I found the error MYSELF twenty minutes later while re-deriving
the advisor's claims, and corrected it on the artifact page and in a message to
Ray — but never to the lane I had already handed the wrong version to. The
advisor went on reasoning from my bad premise until it read `pr.py` itself and
refuted me.

**A correction owes a message to every consumer that received the wrong version,
not only to the person in front of you.** A lane is a consumer; so is a committed
doc, a plan file, and an open issue. Fixing the visible copy while a working copy
of the error runs elsewhere gives one wrong fact two lifetimes.

It cost more than a re-derivation: the wrong premise made "delete the landed
branch" look like the obvious prevention, and that option is empirically refuted
— remote deletion was already in force and did not prevent the incident. An
entire prevention design was being ranked around a fact I had already corrected
in one place.

What caught it: the advisor had been told to VERIFY the facts in its brief rather
than accept them. Put that instruction in every dispatch.
