# The lanes: the two this skill owns, the fallback, and the receipt

## Standards and Spec — NOT here

Both axes belong to `mattpocock-skills:code-review`. Its prompts, its Fowler
baseline, and its no-reranking rule are the spine's, and duplicating them here
is what `use-tool-builtins.md` forbids — an earlier draft did exactly that.

This skill supplies only the two sources the spine cannot find in this repo
(SKILL.md step 3) and `references/repo-smells.md` as additions to its baseline.
Everything below is the part the spine does not have.

## Cold — a lane from a DIFFERENT family than the implementer

Which lane that is depends on who wrote the diff; **SKILL.md step 5 owns the
routing table and this file defers to it.** Claude-authored (the usual case) →
`fable-orchestrator:codex-reviewer`; codex-authored — which this project's
Claude config makes the default for orchestrator-driven work — →
`antigravity:review`.

This section used to name `codex-reviewer` unconditionally, in its heading and
in step 1 of the chain below, which meant following this file literally on a
codex-authored branch recorded a **same-family** read as `cold:codex`. Three
separate lanes flagged it in one round: SKILL.md had been corrected and its own
reference file had not.

**By ref, and cold.** Hand it the range and nothing else:

```text
Review <FIXED>...HEAD in this repository. Read the diff yourself.
Return a findings list: severity, a one-line claim, and file:line for each.
Cite every claim or label it unverified.
```

Do **not** tell it what the change was for. That is the point of the lane — a
reviewer given the design intent confirms the happy path, which is the failure
mode a second lens exists to break. It shares no weights with Claude, so its
blind spots are different ones.

### The fallback chain — loud at every step

| Step | Lane | Family |
|---|---|---|
| 1 | whichever cross-family lane SKILL.md's table selects for THIS diff | OpenAI or Google — cross-family |
| 2 | the other cross-family lane | still cross-family |
| 3 | a Claude Opus subagent | **same family as the author** |

Step 3 is a real fallback and never a silent one. Record it as
`cold:claude-fallback-SAME-FAMILY` in the receipt. A same-family cold read still
catches things — a fresh context with no design intent is worth something — but
it is not the cross-family check the lane is named for, and a receipt that
implies otherwise is a lie told to a future reader.

Both CLIs are pinned in `mise.toml` (`codex`, `antigravity-cli`) and auth is
per-user, so "installed" is not "authenticated". The plugin agents return a
structured error rather than substituting themselves; treat that error as
"advance the chain", not as "no findings".

## Silent failures — `pr-review-toolkit:silent-failure-hunter`

Give it the same range. It looks for swallowed exceptions, bare `except`,
fallbacks that mask a real error, and error paths that log-and-continue where
they should fail.

Two things in this repo are **deliberate** and must not be reported as findings
— check the reasoning is intact rather than flagging the shape:

- `kb_setup.hook_guard` **fails open on its own errors.** A crashed PreToolUse
  guard must not brick every Bash call. That is a documented trade, not a
  swallowed error.
- `kb_setup.pr.checks_state` **fails closed on an unparsable payload.** Output
  it cannot parse means the question was never asked, which must never authorise
  a merge.

They point opposite directions on purpose. A lens that flags either one has
found the shape and missed the reasoning; a lens that finds one of them
*inverted* has found a real defect.

## The receipt

`.agent/kb/review/receipt-<sha>.json`, written by
`mise run kb-review-receipt`:

```json
{
  "sha": "9521853...",
  "written_at": "2026-07-28T02:14:09+00:00",
  "fixed_point": "main",
  "fixed_point_sha": "9698879...",
  "lanes_ran": ["standards", "spec", "cold:codex", "silent-failure"],
  "lanes_skipped": [],
  "findings": 3,
  "blocking": 0
}
```

`lanes_skipped` entries carry their reason — `cold:not-applicable-docs-only`,
`spec:no-spec-available`. **A skip with no reason is not a skip, it is a gap**,
and `kb-ship` rejects a receipt containing one.

`cold:claude-fallback-SAME-FAMILY` was listed here as a third example and is
**not a skip at all** — it belongs in `lanes_ran`, because that lane *ran*, just
same-family (`_lane_prefix` already reads the `cold:` prefix). The gate rejected
it, so this doc told you to do something the code refuses, on exactly the path it
was written for: both cross-family CLIs down. Found by two lanes independently.

`fixed_point_sha` is the **merge-base**, not the fixed point resolved as a ref —
three-dot semantics, matching the `git diff <base>...HEAD` the review runs
against. Two rules now bind it:

- **An EMPTY range is refused for every consumer.** `--fixed-point HEAD`
  resolves through `git merge-base HEAD HEAD` to HEAD itself, and the field was
  checked only for non-blankness — so one flag minted a full-coverage receipt
  for a zero-line diff.
- **`kb-ship` AND `kb-land` both require it to equal the branch's merge-base with
  `main`.** A receipt against a narrower base is still a *truthful* record of
  what it reviewed; it just does not gate the whole branch. The dangerous case is
  not adversarial but ordinary: on a second review round the instinct is "review
  what changed since last time" (`--fixed-point HEAD^`), which produces an honest
  receipt covering one commit of twelve.

  `land` was the half that mattered and the half that was missing. `ship` guards
  what IT pushes, but `gh pr create` is not guard-denied here, so a PR can reach
  the remote another way — and `land`'s receipt check is documented as the
  backstop for exactly that. A backstop that accepted a suffix-only receipt did
  not cover its own stated case. The base is resolved against the commit being
  validated (the PR head oid for `land`), not live `HEAD`, or `land` would refuse
  every merge.

So pass `--fixed-point` only when you genuinely reviewed against something other
than `main`, and expect both tasks to refuse it.

**A lane claimed as RUN must have left a report** at
`.agent/kb/review/reports/review-<sha>-<lane>.md`, non-empty — where `<lane>` is
the lane, with any `:variant` **stripped**. A lane recorded as `cold:codex` leaves
`…-cold.md`, not `…-cold:codex.md`. Without that the
whole receipt was honor-system: one command with four lane names minted full
coverage having run nothing, which is the widest form of a hole whose narrower
forms had already been closed twice. It raises the bar rather than proving
anything — a stub file still passes — but the honest path is now the easy one.

**Only two skip reasons excuse a lane, and one of them is lane-scoped**:
`not-applicable-<why>` excuses any lane; `no-spec-available` excuses **the spec
lane only**. `not-yet-run` is a **gap** and is rejected, which is what the
paragraph above already said and the first version of the gate did not enforce.

The scoping is the THIRD instance of one hole. The reason was matched without
ever checking which lane it was attached to, so `cold:no-spec-available` bought a
pass for a lane that never ran — a cold lane does not review against a spec, so
"there is no spec" cannot explain its absence. `--lanes placeholder` and
`cold:not-yet-run` were the first two. Found by the cold lane each time, which is
now three for three on this gate — a reviewer that keeps finding the same *shape*
is telling you the shape is the defect, not the instances.

**The lane set is CLOSED** (`kb_setup.review.LANES`), and all four must be
accounted for — each either ran or was skipped with a reason. Both halves of
that matter, and the first draft had neither: the gate only checked that
`lanes_ran` was non-empty, so `--lanes placeholder --blocking 0` satisfied it,
and `--lanes standards` quietly bought a pass for three lanes that never ran.

That hole was found by the **cold lane, reviewing this feature's own first
commit** — after the module's unit tests were green over it. It is the argument
for the lane, arrived at by accident rather than by construction, so it is
recorded here rather than smoothed away.

## Spawning: prefer an UNNAMED subagent

A *named* teammate needs a tmux pane, and panes run out — measured at 18 open,
most of them finished agents whose panes persist. Two lanes failed to spawn that
way on the first real run, and `tmux kill-pane` is not always permitted.

An **unnamed** `Agent` call runs in the background without a pane and is the
default here. For the cold lane there is a second route that needs no agent at
all: drive the CLI directly, per `ai-cli-invocation.md` —

```bash
cat prompt.txt | codex exec --ephemeral --sandbox read-only -
```

Record that variant honestly as `cold:codex-cli-direct`: same model and the same
coldness, but not the plugin agent, so it lacks the plugin's structured-error
fallback and a hang shows up as a hang.

**A lane that could not be spawned is `not-yet-run`, never `not-applicable`.**
The first is a gap; the second is a judgement that the lane had nothing to say.
Writing the second when you mean the first is how a receipt reports coverage it
does not have.

**`--blocking N` where N > 0 is refused at RECEIPT-WRITE time** — `kb-review-receipt`
validates before it writes, so it exits 2 having written nothing, and `kb-ship`
then refuses for "no receipt". It never reaches a ship-time blocking check.

Say that precisely, because the loose version ("`blocking > 0` fails the ship
gate") described a path that does not exist and hid a real consequence: a review
that FOUND blockers leaves the same empty disk as one that never ran. If you need
those distinguishable, the lane reports are what distinguishes them — they are
written before the receipt and survive its refusal. `review.py`'s own
`_check_blocking` is what performs that refusal — `cli.py` calls `rejection()`,
which runs the same `_CHECKS` the reader runs, so writer and reader cannot drift.

Everything below blocking is reported and does not block — the review's job is to
put findings in front of a human, not to adjudicate taste.

The receipt is gitignored. It proves *this machine* reviewed *this commit*, and
an amend or rebase moves the SHA and invalidates it — correctly, because the
reviewed bytes are gone.

**One exception, `review.EXEMPT_PATHS` (#66):** `ship`/`land` accept an
ANCESTOR's receipt when the ENTIRE delta since it is `graphify-out/memory/**` or
`docs/goals/README.md` — the files P7's `kb-remember` and `kb-goal-outcome`
write, which cannot exist until after the review. One reviewed path in that
delta and it refuses, naming the file. So close the loop BEFORE `kb-ship` and
commit what it wrote; three rounds running had left those artifacts uncommitted.

The exemption removes the only lane read those paths get, which is what makes
**scanner** coverage of them load-bearing: `.gitleaks.toml` and `hk.pkl`'s
`proseExclude` both deliberately keep them visible to gitleaks, and
`tests/test_gitleaks_scope.py` pins that. Do not widen `EXEMPT_PATHS` to a path
the scanner cannot see.
