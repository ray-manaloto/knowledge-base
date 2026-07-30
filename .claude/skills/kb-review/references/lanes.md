# The lane: the one this skill runs, the fallback, and the receipt

## Standards, Spec and Silent-failures — NOT RUN (since 2026-07-29)

The review is **one lane**. These three are stood down by policy and recorded in
the receipt as `by-policy-one-lane` (see below). They are described here only so a
future reader knows what was given up and where to find it again:

- **Standards** and **Spec** were two axes of `mattpocock-skills:code-review`,
  handed this repo's two sources: the project rule files plus `CLAUDE.md` for
  standards, and the `docs/goals/` pair or newest session plan for spec. The
  spine still exists and can be invoked directly if a human wants those axes on
  a given diff.
- **Silent failures** was `pr-review-toolkit:silent-failure-hunter`.

Reviving any of them is a human decision on a specific diff, not something this
skill chooses per-diff any more — that table was the thing removed.

## Cold — a lane from a DIFFERENT family than the implementer

Which lane that is depends on who wrote the diff; **SKILL.md step 2 owns the
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
Review <FIXED>...HEAD in this repository. Read the diff yourself, using this
exact scope — it excludes one tracked prose directory that is not code under
review:

    git diff <FIXED>...HEAD -- . ':(exclude)docs/research/**'

Return a findings list: severity, a one-line claim, and file:line for each.
Cite every claim or label it unverified. Report NO FINDINGS explicitly if you
find nothing, rather than inventing something.
```

**The scope is IN the template, not just in SKILL.md.** It was described in the
skill and missing from this prompt, so following this file verbatim reintroduced
the 56%-prose context cost the exclusion exists to remove — the same
skill-corrected/reference-not-corrected split as the `codex-reviewer` paragraph
directly above. Found by the cold lane, on the change that added the exclusion.

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

### Two shapes in this repo that are DELIBERATE

Carried over from the retired silent-failure lane, because the cold lane reads the
same code and will meet them. Check the reasoning is intact rather than flagging
the shape:

- `kb_setup.hook_guard` **fails open on its own errors.** A crashed PreToolUse
  guard must not brick every Bash call. That is a documented trade, not a
  swallowed error.
- `kb_setup.pr.checks_state` **fails closed on an unparsable payload.** Output
  it cannot parse means the question was never asked, which must never authorise
  a merge.

They point opposite directions on purpose. A lens that flags either one has
found the shape and missed the reasoning; a lens that finds one of them
*inverted* has found a real defect.

`zero-skip-policy.md` is why a suppressed error used to get its own lens. With one
lane, that concern rides along in the cold review instead — a real reduction in
coverage, recorded in SKILL.md's "what this does not claim" rather than smoothed
over.

## The receipt

`.agent/kb/review/receipt-<sha>.json`, written by
`mise run kb-review-receipt`:

```json
{
  "sha": "9521853...",
  "written_at": "2026-07-28T02:14:09+00:00",
  "fixed_point": "main",
  "fixed_point_sha": "9698879...",
  "lanes_ran": ["cold:codex"],
  "lanes_skipped": [
    "standards:by-policy-one-lane",
    "spec:by-policy-one-lane",
    "silent-failure:by-policy-one-lane"
  ],
  "findings": 3,
  "blocking": 0
}
```

`lanes_skipped` entries carry their reason — `standards:by-policy-one-lane`,
`spec:no-spec-available`. **A skip with no reason is not a skip, it is a gap**,
and `kb-ship` rejects a receipt containing one.

`cold:not-applicable-docs-only` was the third example here and **no longer names a
reachable state.** Under one-lane-always (`SKILL.md`), a docs-only branch either has
a non-empty scoped diff — in which case cold runs — or an empty one, in which case
there is no receipt at all rather than a per-lane skip. It survived the very commit
that made it unreachable, one line above a table stating `cold` can never be
excused. (Cold lane, round 2.)

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

**Three skip reasons excuse a lane, and two of them are lane-scoped**:

| Reason | Excuses | Asserts |
|---|---|---|
| `not-applicable-<why>` | any lane | a JUDGEMENT — the lane read this diff and had nothing to say |
| `no-spec-available` | the **spec** lane only | there is no spec to review against |
| `by-policy-one-lane` | **standards**, **spec**, **silent-failure** — never `cold` | a POLICY — the skill deliberately runs one lane |

`not-yet-run` is a **gap** and is rejected, which is what the paragraph above
already said and the first version of the gate did not enforce.

`by-policy-one-lane` exists because the review became single-lane (2026-07-29)
and `LANES` is still closed, so the three stood-down lanes need a reason that is
TRUE. Reusing `not-applicable-` would have been the easy move and the wrong one:
it asserts a judgement nobody made, which is the gap-wearing-a-reason's-clothes
shape this file records three times below. **`cold` is deliberately excluded** —
the one-lane policy *is* "run cold", so `cold:by-policy-one-lane` cites the policy
to skip the lane the policy exists to run. It is scoped in `_SKIP_BY_LANE` rather
than added as a lane-blind prefix for exactly that reason; a prefix would have
accepted it, and the `records no lane that actually ran` backstop only fires when
ALL four lanes are skipped.

The scoping is the THIRD instance of one hole. The reason was matched without
ever checking which lane it was attached to, so `cold:no-spec-available` bought a
pass for a lane that never ran — a cold lane does not review against a spec, so
"there is no spec" cannot explain its absence. `--lanes placeholder` and
`cold:not-yet-run` were the first two. Found by the cold lane each time, which is
now three for three on this gate — a reviewer that keeps finding the same *shape*
is telling you the shape is the defect, not the instances.

**The lane set is CLOSED** (`kb_setup.review.LANES`), and all four must be
accounted for — each either ran or was skipped with a reason. It stays four
entries even though the skill now runs one: changing `LANES` to `("cold",)` would
touch 63 references across 11 files including the eval harness, so the
"simplification" would be larger than the thing it simplifies. Both halves of
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
`proseExclude` both deliberately keep them visible to gitleaks. **Two tests pin
it, one per half** — `tests/test_gitleaks_scope.py` for the `.gitleaks.toml`
allowlist, and `tests/test_hk_scanner_scope.py` (added with #73) for the hk half,
asserted against the **evaluated** pkl config rather than the source text, so a
`proseExclude` that stops applying cannot pass by still being written down. Do
not widen `EXEMPT_PATHS` to a path the scanner cannot see.
