---
type: "query"
date: "2026-09-01T09:44:52.591738+00:00"
question: "Do two cold review rounds plus a green receipt mean a diff has been verified?"
contributor: "graphify"
outcome: "corrected"
correction: "The belief: two cold review rounds plus a green receipt means a diff has been\nverified, and a third pass over the same branch is redundant.\n\nRefuted this round. The branch carried two cold rounds and a receipt at\n`3f1ce491`. A third cold pass — the first one given an explicit METHOD\ninstruction to RUN each check rather than read it — found a claim the two\nreading passes had both walked over: `hk.pkl`'s `lane_recording` comment\nasserting the gate scans \"8 files\" when it scans 15.\n\nThe distinction is not the number of rounds and not the lane's identity. It is\nwhether the lane EXECUTED the thing it was reviewing. Running the gate prints\n`15 file(s) checked`; reading the gate does not, and a reviewer with no reason\nto doubt a comment has no reason to run it.\n\nSo: a round count is not a verification depth. When a diff contains a check, a\ngate, or a guard, the dispatch prompt must ask the lane to construct the input\nthat trips it and RUN it — both directions — and to report the exit codes. That\nparagraph is what separates a review that could only agree from one that could\ndisagree.\n\nThe corollary, which is the expensive half: the same is true of MY own reading.\nI read the `0184d2cc` hunk myself and reasoned correctly about the shell's\nbackslash-newline semantics, and I did not notice the comment eight lines above\nthe code I was reading — because I was reading, not running.\n"
---

# Q: Do two cold review rounds plus a green receipt mean a diff has been verified?

## Answer

# Round: reconcile a diverged PR, and what a METHOD instruction bought

## What the round did

PR #645 (`fix/agentsview-lane-visibility`) had diverged: local HEAD and the
remote head were siblings holding commits the other lacked, because a
second author (`sortakool`, co-authored by the Codesmith bot) pushed
`0184d2cc` while the local session held two unpushed commits.

Reconciled by REBASE, not a merge commit, because the local commits were
unpushed — so nothing published was rewritten and `0184d2cc` stayed
byte-identical as authored. Verified the result BOTH directions rather than one:
`git diff --name-only <old-local-HEAD> HEAD` returned exactly the 4 files the
remote commit touched, and `git diff --name-only <remote> HEAD` returned exactly
the 3 files the local commits touched. The merged tree is the union, nothing
invented and nothing dropped.

Landed as `c63e68d3b4f32aa6a3ac72e2bebca043d1a56353`, cross-verified two ways:
`kb-land` reported OK and `gh pr view 645` returned `state=MERGED`.

## The finding worth keeping: a METHOD instruction changed what the review was

This repo's own work-memory already held the hypothesis — "METHOD predicts a
blocker, not lane identity", and `kb-review` SKILL.md's closing section says
*"give the one lane a mutating instruction before adding a second lane back"*.
This round is the first time that was actually DONE rather than noted.

The cold codex lane was told: do not review by reading; construct the input that
should trip each check and RUN it, plus one that should pass; report the exit
codes.

What came back was not a reading review. Nine synthetic arms against
`kb_setup.lane_recording` (the realistic multi-line `--ephemeral` regression, the
clean multi-line form, the round-2 cross-fence-merge shape, a
`mise exec -- codex` wrapper, `--ephemeral=true`, a prose-only mention that must
NOT fire, an unparsable-quote fallback, a zero-match glob that must exit
`NOT_RUN` rather than pass, and two commands in one fence) — plus an end-to-end
mutate-and-restore against the REAL tracked file: it reintroduced `--ephemeral`
into `.claude/agents/kb-codex-advisor.md`'s live multi-line `codex exec` block,
confirmed the gate went rc=1 with the correct `file:line`, restored, and
confirmed rc=0 and a clean `git status` (independently re-checked afterwards —
the tree was clean, so the lane did restore).

It also left the repo to check two factual claims the diff ASSERTED rather than
merely reading them: that `sources/codex.manifest`'s SHA is what
`refs/tags/rust-v0.152.0` actually dereferences to, and that
`[tools.update_plan] enabled = true` matches the real `ToolsToml` /
`UpdatePlanToolConfig` schema at that commit.

The instruction cost one paragraph in the dispatch prompt.

## The defect it found, and what makes it interesting

One finding, Low, zero blocking: `hk.pkl`'s `lane_recording` step comment claimed
the gate scans "8 files". It scans **15** — re-derived independently before
acting (`uv run kb-setup lane-recording` prints the count).

Two things make it worth recording rather than shrugging at:

1. It was **wrong on arrival, not stale.** Nothing in the reviewed diff added or
   removed a scanned file, so the number was false the moment it was written.
2. **Two prior cold rounds on this same branch missed it.** The branch already
   carried two cold reviews and a receipt at `3f1ce491`. The third pass — the one
   given the METHOD instruction — is the one that caught it, because running the
   gate prints the real count while reading the gate does not.

Fixed by REMOVING the number rather than correcting it to 15, and pointing the
comment at `DEFAULT_GLOBS` plus the command that prints the real set. A count
frozen in a comment reads as verified forever, and the next commit invalidates
it again — `probes-need-a-control-arm.md` rule 6.

## The cost of closing the loop after the land

This round landed #645 BEFORE running `kb-remember`, which is the ordering trap
`clear-prep` step 2 warns about. `kb-land` squash-merges, so the receipt's commit
stopped being an ancestor of `main`, and `review.EXEMPT_PATHS` could not rescue
the memory commit. The work-memory therefore lands on its own branch and owes its
own receipt, rather than riding under the reviewed commit's.


## Outcome

- Signal: corrected
- Correction: The belief: two cold review rounds plus a green receipt means a diff has been
verified, and a third pass over the same branch is redundant.

Refuted this round. The branch carried two cold rounds and a receipt at
`3f1ce491`. A third cold pass — the first one given an explicit METHOD
instruction to RUN each check rather than read it — found a claim the two
reading passes had both walked over: `hk.pkl`'s `lane_recording` comment
asserting the gate scans "8 files" when it scans 15.

The distinction is not the number of rounds and not the lane's identity. It is
whether the lane EXECUTED the thing it was reviewing. Running the gate prints
`15 file(s) checked`; reading the gate does not, and a reviewer with no reason
to doubt a comment has no reason to run it.

So: a round count is not a verification depth. When a diff contains a check, a
gate, or a guard, the dispatch prompt must ask the lane to construct the input
that trips it and RUN it — both directions — and to report the exit codes. That
paragraph is what separates a review that could only agree from one that could
disagree.

The corollary, which is the expensive half: the same is true of MY own reading.
I read the `0184d2cc` hunk myself and reasoned correctly about the shell's
backslash-newline semantics, and still did not catch the false count — because I
was reading, not running.

CORRECTED 2026-09-01 by a round-2 cold lane, and the correction matters more than
the anecdote. This paragraph originally said the comment was "eight lines above
the code I was reading". That was false two ways, and both are checkable in one
command each. `git show --name-only --format= 0184d2cc` returns FOUR files and
`hk.pkl` is not among them — so nothing I read in that commit was adjacent to
that comment at all. And the real distance, `git show 0184d2cc:hk.pkl | nl -ba`,
is comment at 522 to step at 525: THREE lines, not eight.

A vivid specific ("eight lines above") is exactly the shape that survives review
unchallenged, because it reads as recalled measurement. It was neither recalled
nor measured. The lesson stands; the number was invented to dramatise it.
