---
type: "query"
date: "2026-08-31T22:41:45.257430+00:00"
question: "Why could PR #639 not merge, and what did three cross-family review lanes find in the fix?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why could PR #639 not merge, and what did three cross-family review lanes find in the fix?

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

- Signal: useful