---
name: kb-review
description: "Run this repo's local cross-family review of a diff — Standards, Spec, a cold different-family reviewer, and a silent-failure lens — and write the receipt `mise run kb-ship` gates on. Use this before shipping ANY branch, when the user says review / ship / open a PR / is this ready, and whenever a change is about to leave this machine. CodeRabbit is advisory here and often rate-limited, so this review is the real gate; a branch with no receipt for its current HEAD does not ship."
argument-hint: "[fixed point — a SHA, branch, or tag; defaults to the merge-base with main]"
---

# kb-review

Four lenses over one diff, run in parallel, reported side by side and never
reranked against each other. Then a receipt, keyed to the exact commit, that
`mise run kb-ship` refuses to push without.

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
git diff --stat <fixed-point>...HEAD
git log <fixed-point>..HEAD --oneline
```

Three-dot, so the comparison is against the merge-base rather than against
whatever `main` has drifted to since.

A bad ref or an empty diff fails **here**, not inside four parallel sub-agents.
Four agents reporting "nothing to review" costs four agents to learn one thing
`git rev-parse` would have told you for free.

### 2. Scale the lanes to the diff

Running four lenses over a typo is the same friction this skill exists to
remove, so pick lanes by what actually changed. This is not an escape hatch —
the receipt records which lanes ran and why, and a skipped lane is visible.

| The diff touches | Lanes |
|---|---|
| any `.py`, `hk.pkl`, `mise.toml`, `.claude/settings.json` | all four |
| any other executable config — `currency.toml`, `pyproject.toml`, `.mcp.json` | all four |
| only markdown, `docs/**`, `sources/**` | Standards + Spec |
| only `docs/goals/*-goal.md` | Spec + Standards, plus `mise run kb-goal-check` |
| anything not listed above | **all four** — the default is coverage, not a skip |

The last row is load-bearing. The table used to end at the goal row, so a real
repo surface it did not name (`currency.toml`, `pyproject.toml`) had no verdict
at all, and "not listed" reads as "docs-only" to a reader in a hurry. Absence of
a row is not a judgement that a lane has nothing to say.

The docs-only row is the case that motivated this skill. Docs cannot fail silently
and have no Fowler smells, so a cold code reviewer over them returns nothing —
that is a **SKIP because it does not apply**, which the receipt must distinguish
from a lane that failed to run. Collapsing those two is how every defect in the
currency engine's review happened.

The goal row keeps **Standards** as well, because `kb-goal-check` is mechanical —
it counts sections, sentinels, and negations. The judgement tests that
actually catch a bad condition (Goodhart shortcuts, stale evidence, the
stated-connective trap) live in `goal-engineering`'s rubric — thirteen of them,
and no gate runs any.
Dropping Standards left a goal pair reviewed only by the tool that cannot read it,
and a goal pair is its own Spec source, so Spec alone is close to self-review.

### 3. Resolve the two sources the spine cannot find here

The Standards and Spec axes are **not implemented here.** They come from
`mattpocock-skills:code-review`, which already does exactly what this repo
needs: two axes, parallel sub-agents, no cross-axis reranking, a Fowler smell
baseline, and an explicit rule to skip whatever tooling already enforces.
`use-tool-builtins.md` makes composing it the default and re-writing it the
thing that needs justifying — and an earlier draft of this skill did re-write
it, which the Spec lane caught.

What it *cannot* do unaided is find this repo's two sources, because both of
its defaults are absent here. Resolve them first and hand them over:

**Standards sources** → `.claude/rules/*.md` plus `CLAUDE.md`. There is no
`CODING_STANDARDS.md` and no `CONTRIBUTING.md` in this repo; those are the
spine's defaults, and it will find nothing if left to look.

**Spec source** → in this order:

1. The `docs/goals/` pair for the round, if one is open.
2. The newest `.agent/plans/session-*.md`.
3. An issue referenced in a commit message (`#123`, `Closes #45`) — `gh issue view`.
4. If none exists, say so and let the Spec axis report *no spec available*
   rather than inventing one to review against.

Do **not** reach for `docs/agents/issue-tracker.md`, and do **not** run
`/setup-matt-pocock-skills` when the spine asks you to: agnix rejects
`**/agents/*.md` here because that glob reads as agent *definitions*, so the
file the spine wants **cannot exist in this repo**.

### 4. Run the two axes through the spine

Invoke `mattpocock-skills:code-review` with the fixed point from step 1, and
give it the two sources from step 3 so it does not go looking for its defaults.

**It carries the Fowler baseline itself — do not supply one.** Add only
`references/repo-smells.md`, which holds the handful of recurring smells that
are specific to this repo and are not in Fowler.

### 5. Run the two lanes the spine does not have

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
one thing a second lens exists not to do.

If the chosen CLI is missing or unauthenticated it returns a structured error
rather than substituting itself. Fall back **loudly, never silently**, to any
remaining cross-family lane, and only then to a Claude Opus subagent. Record
which lane actually ran in the receipt; a same-family reviewer still catches
things, but the receipt must not imply it was cross-family.

**Silent failures** is `pr-review-toolkit:silent-failure-hunter` — swallowed
exceptions, bare excepts, fallbacks that mask a real error. `zero-skip-policy.md`
is the reason this gets its own lens instead of a bullet in Standards: a
suppressed error is the failure mode this repo cares most about, and a lens that
shares context with three other concerns finds fewer of them.

### 6. Aggregate — verbatim, unreranked

Present under `## Standards`, `## Spec`, `## Cold (<lane>)`, `## Silent failures`.
Verbatim or lightly cleaned. The spine aggregates its own two axes — keep its
wording and set the other two alongside rather than folding them in.

**Do not merge or rerank findings across lenses.** A change can pass one axis and
fail another — code that follows every rule and implements the wrong thing is
Standards-pass / Spec-fail — and cross-axis ranking is exactly how one lens masks
another.

End with one line per lens: finding count, and the worst finding *within that
lens*. No single winner across lenses.

**Every finding must cite `file:line` or quote the hunk.** A finding without a
citation is labelled `unverified` and reported as such rather than dropped —
dropping it hides a lead, promoting it launders a guess.

### 7. Persist each lane's report, THEN write the receipt

Write every lane's report verbatim to
`.agent/kb/review/reports/review-<sha>-<lane>.md` **as it arrives** —
`agent-report-persistence.md` requires it, and the receipt now checks for it.
A lane that left no report is a claim, not a review. `NO FINDINGS` is a
perfectly good report; an empty file is not.

```bash
# All four ran — the usual case for a diff touching .py / mise.toml / hk.pkl.
mise run kb-review-receipt -- \
  --lanes standards,spec,cold:codex,silent-failure \
  --fixed-point <the same fixed point you reviewed against> \
  --findings <n> --blocking <n>

# Docs-only — two ran, two do not apply. Every lane is still accounted for.
mise run kb-review-receipt -- \
  --lanes standards,spec \
  --skipped cold:not-applicable-docs-only,silent-failure:not-applicable-docs-only \
  --fixed-point <…> --findings <n> --blocking <n>
```

Two examples because the single one that used to sit here named `cold` in **both**
`--lanes` and `--skipped` — a lane cannot have run and been skipped, and copying it
verbatim produced a receipt claiming coverage it did not have. `no-spec-available`
excuses the **spec lane only**; `not-applicable-<why>` excuses any lane.

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

## What this does not claim

The cold lane is a second opinion, not a proof. It shares no weights with the
author, which is the whole value, but it is still an LLM reading a diff — it
misses things and it invents things, which is why every finding needs a citation
and why `verify-before-advancing.md`'s gates still run underneath. This review
raises the floor; it does not replace `mise run lint`, `mise run test`, or your
own reading of the diff.

And it is strictly weaker than a signed external check. Say so rather than
implying the loop is closed.

## References

- `references/repo-smells.md` — the repo-specific smells that are NOT in the
  spine's Fowler baseline. Additions only; the spine carries the rest.
- `references/lanes.md` — the exact sub-agent prompts, the fallback chain, and
  the receipt schema.
