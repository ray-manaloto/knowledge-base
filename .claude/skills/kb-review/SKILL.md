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
| only markdown, `docs/**`, `sources/**` | Standards + Spec |
| only `docs/goals/*-goal.md` | Spec, plus `mise run kb-goal-check` |

The middle row is the case that motivated this skill. Docs cannot fail silently
and have no Fowler smells, so a cold code reviewer over them returns nothing —
that is a **SKIP because it does not apply**, which the receipt must distinguish
from a lane that failed to run. Collapsing those two is how every defect in the
currency engine's review happened.

### 3. Gather the sources each lane needs

**Standards** — `.claude/rules/*.md` (this repo's real standards; there is no
`CODING_STANDARDS.md` or `CONTRIBUTING.md` here, which is what the upstream
spine assumes) plus `CLAUDE.md`, plus the smell baseline in
`references/smell-baseline.md`.

**Spec** — in this order:

1. The `docs/goals/` pair for the round, if one is open.
2. The newest `.agent/plans/session-*.md`.
3. An issue referenced in a commit message (`#123`, `Closes #45`) — `gh issue view`.
4. If none exists, say so and let the Spec lane report *no spec available*
   rather than inventing one to review against. Do **not** reach for
   `docs/agents/issue-tracker.md` — agnix rejects `**/agents/*.md` here, because
   that glob reads as agent *definitions*, so the file the upstream spine wants
   cannot exist in this repo.

### 4. Spawn the lanes — one message, all of them

**Standards** and **Spec** are `general-purpose` subagents. Paste the smell
baseline into the Standards prompt in full; it has no other access to it.

**The cold lane must be a different model family than whoever wrote the code.**
Claude wrote it, so the cold lane is `fable-orchestrator:codex-reviewer`
(GPT-5.6 Sol, read-only sandbox). Review it **by ref and COLD** — hand it the
SHA and nothing about what the change was *supposed* to do. Design context
primes happy-path confirmation, which is the one thing a second lens exists not
to do.

If `codex` is missing or unauthenticated it returns a structured error rather
than substituting itself. Fall back **loudly, never silently**:
`codex` → `antigravity` (Gemini 3.x, still cross-family) → a Claude Opus
subagent. Record which lane actually ran in the receipt; a Claude reviewer of
Claude code is same-family and the receipt must not imply otherwise.

**Silent failures** is `pr-review-toolkit:silent-failure-hunter` — swallowed
exceptions, bare excepts, fallbacks that mask a real error. `zero-skip-policy.md`
is the reason this gets its own lens instead of a bullet in Standards: a
suppressed error is the failure mode this repo cares most about, and a lens that
shares context with three other concerns finds fewer of them.

### 5. Aggregate — verbatim, unreranked

Present under `## Standards`, `## Spec`, `## Cold (<lane>)`, `## Silent failures`.
Verbatim or lightly cleaned.

**Do not merge or rerank findings across lenses.** A change can pass one axis and
fail another — code that follows every rule and implements the wrong thing is
Standards-pass / Spec-fail — and cross-axis ranking is exactly how one lens masks
another.

End with one line per lens: finding count, and the worst finding *within that
lens*. No single winner across lenses.

**Every finding must cite `file:line` or quote the hunk.** A finding without a
citation is labelled `unverified` and reported as such rather than dropped —
dropping it hides a lead, promoting it launders a guess.

### 6. Write the receipt

```bash
mise run kb-review-receipt -- --sha "$(git rev-parse HEAD)" \
  --lanes standards,spec,cold:codex,silent-failure \
  --skipped "cold:not-applicable-docs-only" \
  --findings <n> --blocking <n>
```

It writes `.agent/kb/review/receipt-<sha>.json`. Gitignored on purpose: a
receipt is machine-local proof that *this* machine reviewed *this* commit before
pushing. Committing it would make it stale the moment anyone rebased, and a
stale receipt is worse than none — it is a green light nobody earned.

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

- `references/smell-baseline.md` — the Fowler smell baseline the Standards lane
  carries, and the two rules that bind it.
- `references/lanes.md` — the exact sub-agent prompts, the fallback chain, and
  the receipt schema.
