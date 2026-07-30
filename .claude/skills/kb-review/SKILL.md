---
name: kb-review
description: "Run this repo's local cross-family review of a diff — ONE cold reviewer from a different model family than whoever wrote the code, bounded at two rounds — and write the receipt `mise run kb-ship` gates on. Use this before shipping ANY branch, when the user says review / ship / open a PR / is this ready, and whenever a change is about to leave this machine. CodeRabbit is advisory here and often rate-limited, so this review is the real gate; a branch with no receipt for its current HEAD does not ship."
argument-hint: "[fixed point — a SHA, branch, or tag; defaults to the merge-base with main]"
---

# kb-review

**One** cold lens over one diff, from a different model family than whoever wrote
the code, bounded at **two rounds**. Then a receipt, keyed to the exact commit,
that `mise run kb-ship` refuses to push without.

It ran four lenses with no round bound until 2026-07-29. That version cost
**2.93M subagent tokens over 5 rounds / 17 lane-runs** on #67 and surfaced
**one** real defect among three findings it rated blocking — on a change that was
then reverted whole, and whose actual harm was already covered by ~3 lines of
scanner config. The simplification is the finding.

This exists because **CodeRabbit is not a gate here** — it returned
`pass — Review rate limited` on 4 of 5 PRs, and a doc-only commit once sat
blocked on someone else's quota queue. An advisory reviewer that is usually
rate-limited is not review; it is a delay. The gate had to come back on-machine.

## Why a skill and not a mise task

Every other recurring workflow here is a `kb-*` task wrapping a `kb_setup`
module (`mise-tasks-only.md`). This one cannot be: a task is a shell command,
and **only the model can spawn Claude agents.** Same reason `kb-extract` is a
workflow rather than a task.

So the work splits: the *skill* runs the review, and the *task* enforces that it
happened. `kb-ship` reads the receipt and compares its SHA to `HEAD`. That
inversion is deliberate — a gate the model can talk itself past is not a gate,
and a receipt whose SHA does not match is not a receipt.

## Process

### 1. Pin the fixed point

`$ARGUMENTS` is the fixed point when the user gave one — a SHA, a branch, a tag.
Empty means the merge-base with `main`. Confirm it before spawning anything:

```bash
git rev-parse <fixed-point>
git diff --stat <fixed-point>...HEAD -- . ':(exclude)docs/research/**'
git log <fixed-point>..HEAD --oneline
```

Three-dot, so the comparison is against the merge-base rather than against
whatever `main` has drifted to since.

A bad ref or an empty diff fails **here**, not inside a spawned sub-agent. An
agent reporting "nothing to review" costs an agent to learn one thing
`git rev-parse` would have told you for free.

**`docs/research/**` is excluded from the reviewed diff, and that exclusion is
the single biggest thing this skill got wrong.** On #67, **2,054 of 3,651
reviewed lines — 56%** were prose under `docs/research/`: the persisted lane
reports of *earlier rounds of the same review*. Every lane re-read the previous
rounds' transcripts, 17 lane-runs deep, and paid for them in context that could
have gone to the code. A review whose largest input is its own exhaust is not
reviewing anything.

Pass the exclusion to every lane, not just to your own `git diff`. Those files
are still tracked, still promoted, still verbatim (`agent-report-persistence.md`
is unchanged) — they are simply not code under review.

**A branch touching ONLY `docs/research/**` therefore has an empty SCOPED diff,
and that is a different state from a bad ref — do not report it as "nothing to
review".** There is something to ship; it is simply all excluded from review.

There is no receipt for this case, and that is deliberate. Every lane would be
skipped, so `kb-review-receipt` refuses with `records no lane that actually ran`
— correctly, because nothing was reviewed, and a receipt exists to say a review
happened. Ship such a branch the way the #75 revert was shipped: state in the PR
body that the whole diff is review-excluded prose, and let the local gates be the
gate. Do not reach for `not-applicable-excluded-scope-only` or any other reason to
manufacture a receipt for it.

### 2. Run ONE lane: the cold cross-family reviewer

**One lane, always. There is no diff-type table and no multi-lane mode.**

This replaced a table that scaled four lenses to the diff, and the reason is
measured rather than aesthetic. Over five rounds on #67 the four lanes cost
**2.93M subagent tokens across 17 lane-runs**, and of three findings rated
*blocking*, exactly **one** was a real defect — the other two were correct code
whose tests would not have caught a hypothetical future revert. The whole change
was then reverted. Four lenses did not buy four times the signal; they bought
four times the transcript, and the volume is what made the disproportion hard to
see from inside.

So the lane set is not a judgement call at the call site any more. If a diff
needs more than this, that is a decision for the human reading the summary, not
a table for the skill to consult.

**The cold lane must be a different model family than whoever wrote the code.**
That is a question about the diff, **not a constant** — ask it every time:

| Implemented by | Cold lane | Family |
|---|---|---|
| Claude (the usual case) | `fable-orchestrator:codex-reviewer` | OpenAI |
| `codex` (this repo's declared implementer lane) | `antigravity:review` | Google |
| `antigravity` | `fable-orchestrator:codex-reviewer` | OpenAI |

The middle row is not hypothetical: `.claude/CLAUDE.md` declares
`fable-orchestrator: implementation lane = codex`, so a branch built through the
orchestrator flow is **codex-authored**, and routing it to `codex-reviewer` buys
a same-family read while the receipt says `cold:codex` — the exact
false-cross-family claim the fallback chain is careful about. Hard-coding "Claude
wrote it" made that the default. Check `git log --format='%an %s'` over the range
and the session's declared lane before choosing.

Review it **by ref and COLD** — hand it the SHA and nothing about what the change
was *supposed* to do. Design context primes happy-path confirmation, which is the
one thing a second lens exists not to do. Hand it the same
`':(exclude)docs/research/**'` scope from step 1.

If the chosen CLI is missing or unauthenticated it returns a structured error
rather than substituting itself. Fall back **loudly, never silently**, to any
remaining cross-family lane, and only then to a Claude Opus subagent. Record
which lane actually ran in the receipt; a same-family reviewer still catches
things, but the receipt must not imply it was cross-family.

### 3. Report the lane verbatim

Present under `## Cold (<lane>)`, verbatim or lightly cleaned. End with the
finding count and the worst finding.

**Every finding must cite `file:line` or quote the hunk.** A finding without a
citation is labelled `unverified` and reported as such rather than dropped —
dropping it hides a lead, promoting it launders a guess.

### 4. Bound the review at TWO rounds

Round 1 reviews. You fix. Round 2 verifies, **and is the last round.**

The bound exists because a stop rule did not work. One was agreed before round 1
of #67 and the review still ran **five** rounds, for a structural reason worth
stating: `kb-review-receipt` refuses `blocking > 0`, so any stop rule silently
becomes *"rounds until zero blocking"* — the reviewer, not the rule, decides when
to stop. A count is the only bound that cannot be argued with.

**If round 2 reports something blocking:** fix it, re-run the local gates
(`mise run lint`, `mise run test`, and whatever else the change touches), and
write the receipt against the fixed SHA — **without a third lane round.** The
gates are the verification at that point. Say so in the PR body; nothing in the
receipt schema records it, and deliberately so — a `gate_verified_delta` field
would be one more thing to maintain for a case the prose already covers.

**That path needs one more step than it looks, and without it the gate refuses.**
A receipt is always keyed to `HEAD`, and `_missing_reports` looks for
`review-<that same sha>-<lane>.md` — so the moment you commit the fix, HEAD moves
and the round-2 report, named for the pre-fix SHA, is invisible to it. The
shortcut as first written was a dead end (found by the cold lane on this very
change). So write a **short fix-round report at the new SHA**:

```text
.agent/kb/review/reports/review-<fixed-sha>-cold.md

Round 2 reviewed <pre-fix-sha>; see review-<pre-fix-sha>-cold.md for the findings.
No lane re-ran against <fixed-sha>. Verification for the fix is the local gates:
<the gates you ran, and their rc>.
```

**Do not copy the round-2 report to the new name.** That would assert a lane read
bytes it never saw, which is the "gap wearing a reason's clothes" this gate exists
to refuse. The file above is honest precisely because it says a lane did *not*
re-run — the receipt records that a review happened, and this records what kind.

### 5. Persist the lane's report, THEN write the receipt

Write every lane's report verbatim to
`.agent/kb/review/reports/review-<sha>-<lane>.md` **as it arrives** —
`agent-report-persistence.md` requires it, and the receipt now checks for it.
A lane that left no report is a claim, not a review. `NO FINDINGS` is a
perfectly good report; an empty file is not.

```bash
mise run kb-review-receipt -- \
  --lanes cold:codex \
  --skipped standards:by-policy-one-lane,spec:by-policy-one-lane,silent-failure:by-policy-one-lane \
  --fixed-point <the same fixed point you reviewed against> \
  --findings <n> --blocking <n>
```

`LANES` is a closed set of four and every one must still be ACCOUNTED FOR, so the
three that the one-lane policy stands down are skipped with
**`by-policy-one-lane`** — a reason that exists for exactly this and is scoped to
those three lanes. `cold:by-policy-one-lane` is refused: the policy *is* "run
cold", so citing it to skip cold is self-contradictory.

Do **not** reach for `not-applicable-<why>` here. That reason asserts a
judgement — the lane read this diff and had nothing to say — and using it for "we
chose not to run it" would make every future receipt claim a judgement nobody
made. `no-spec-available` remains the spec lane's alone.

`--blocking` is required — state it even when it is `0`. `--fixed-point`
defaults to `main`; **pass it whenever you reviewed against anything else**, or
the receipt records a base you did not use. It is resolved to a commit and
stored as `fixed_point_sha`; an unresolvable one is refused rather than stored
empty. There is no `--sha` — the receipt is always for HEAD.

It writes `.agent/kb/review/receipt-<sha>.json`. Gitignored on purpose: a
receipt is machine-local proof that *this* machine reviewed *this* commit before
pushing. Committing it would make it stale the moment anyone rebased, and a
stale receipt is worse than none — it is a green light nobody earned.

**`kb-land` gates on it too**, not just `kb-ship` — it refuses to merge a PR head
with no receipt, **and one that covers only part of the branch**. That accepts a
machine-local coupling (the landing machine must be the reviewing one) in
exchange for closing the gap where a PR is pushed by one path and merged by
another.

The base-coverage half was missing until round 7 caught it, and the gap was
precisely the case this paragraph advertises: `gh pr create` is not guard-denied
here, so a hand-opened PR plus a `--fixed-point HEAD^` receipt was merged whole.

**A `--blocking` greater than 0 is refused before anything is written**, so the
command exits 2 and `kb-ship` then refuses for *no receipt*. The lane reports are
what preserve the distinction between "reviewed, found blockers" and "never
reviewed" — they are written first and survive the refusal.

**Amending or rebasing invalidates the receipt**, because the SHA moves. That is
correct, not friction: the reviewed bytes are gone.

**One exception, and only one: the round's own closing artifacts.**
`kb-remember` and `kb-goal-outcome` are mandated by every rider's "close the
loop" phase, and they write `graphify-out/memory/*.md` and `docs/goals/README.md`
— files that cannot exist until after the review has happened. Committing them
moved HEAD past the receipt and `ship` refused, so three rounds running left
them uncommitted instead, one `git clean -xdf` from gone (#66).

So `ship` and `land` accept an ANCESTOR's receipt when the entire delta since it
is inside `review.EXEMPT_PATHS`. One reviewed path in that delta and the
fallback is refused, naming the file. It changes which receipt is read, never
what is asked of it — a blocking finding on that ancestor still refuses.

The workflow this buys: review → receipt → run the closing tasks → commit what
they wrote → `kb-ship`. The summary line says which receipt covered HEAD and
what changed since, because a gate that relaxes silently is worse than one that
refuses.

## What this does not claim

The cold lane is a second opinion, not a proof. It shares no weights with the
author, which is the whole value, but it is still an LLM reading a diff — it
misses things and it invents things, which is why every finding needs a citation
and why `verify-before-advancing.md`'s gates still run underneath. This review
raises the floor; it does not replace `mise run lint`, `mise run test`, or your
own reading of the diff.

And it is strictly weaker than a signed external check. Say so rather than
implying the loop is closed.

**One lane costs coverage, and the measurement says so.** On #67 the *standards*
lane found **2 of the 3** blocking findings while cold found **0 in five runs** and
missed both on the SHA where they sat. So this is not "cold was the best lane" —
it is a deliberate trade of coverage for proportion, made because the four-lane
version's cost was not repayable at any observed yield. What actually predicted a
blocker was **method** (a lane that mutated code to test its claim) rather than
lane identity, which is the thread to pull if this bound ever needs revisiting:
give the one lane a mutating instruction before adding a second lane back.

## References

- `references/repo-smells.md` — the repo-specific smells that are NOT in the
  spine's Fowler baseline. Additions only; the spine carries the rest.
- `references/lanes.md` — the exact sub-agent prompts, the fallback chain, and
  the receipt schema.
