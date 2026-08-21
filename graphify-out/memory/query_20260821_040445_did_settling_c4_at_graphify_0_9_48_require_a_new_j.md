---
type: "query"
date: "2026-08-21T04:04:45.493415+00:00"
question: "Did settling C4 at graphify 0.9.48 require a new judgement, and what did the PR bot round find that the cold review did not?"
contributor: "graphify"
outcome: "corrected"
correction: "An ADVISORY reviewer found the round's only real defect, and both gates missed it.\n\nThis repo's doctrine says CodeRabbit is advisory and `kb-review`'s cold\ncross-family lane is the real gate, because CodeRabbit returned \"Review rate\nlimited\" on 4 of 5 PRs. That reasoning is about AVAILABILITY and it is still\ncorrect. It says nothing about DETECTION, and the round measured the difference:\n\n- the cold codex lane: 3 findings, all LOW/INFO documentation accuracy, 0 blocking\n- the author reading his own diff: 0\n- CodeRabbit: the one Major that was a live break\n\nThe break had been shipped TWO releases earlier and sat behind a green suite the\nwhole time, because no test exercised the path it broke.\n\nThe transferable lesson is not \"trust the bots\". It is that a reviewer's\nCLASSIFICATION (advisory vs gate) is about whether you can DEPEND on it, and\ncarries no information about whether its findings are real. An advisory reviewer's\nfindings still have to be read and verified — and on this round, verifying them\nrefuted three of four while confirming the one that mattered.\n\nSecond, smaller lesson, from the fix: the first test written alongside it was\ninsufficient and only a mutation sweep said so. An arm reverting the constant to\nits stale value SURVIVED, because a self-consistency assertion stays true when\nBOTH halves are stale. The test covered the restatement half of the defect and not\nthe staleness half — the half actually reported. A fix's own test is the\nleast-reviewed code in the diff, and `kb-arms` is what makes that visible.\n"
---

# Q: Did settling C4 at graphify 0.9.48 require a new judgement, and what did the PR bot round find that the cold review did not?

## Answer

# Round: settle C4, ship the graphify-corpus branch, and close the bot round

## What the round asked

Ray chose C4 from the resume report: settle the plan-authority blockers before
deciding anything else, then `kb-review` and ship the branch.

## What was settled

**The three C4 "blockers" were ONE blocker.** `verify_plan` emits
`cost-advisory-review-required` and `provisional-input-decisions` only inside its
`if not authorized` branch, alongside `plan-authority-mismatch`. They are
companions to the mismatch, never independent gates. The advisory is additionally
REQUIRED to read `review_status == "provisional"`, so "move the cost advisory off
provisional" — carried in the handoff as a separate task — describes an action
that cannot be performed on this plan. Two handoffs had propagated it.

**The workload was measured before re-recording, per Ray's standing ruling.**
374 detected / 479 discovered / 475 admitted / 58 chunks / 370 unique paths,
identical either side of 0.9.47 -> 0.9.48, compared as SETS. Estimated tokens
moved +0.07%, all of it CHANGELOG.md and README.md growing at the release.

**Two things moved that the authority file had never recorded moving**, both
checked rather than reasoned about:
- `exclusions.json` ENTRY BYTES, a first — two presentational entries bind to the
  README that describes them, and that README changed. The two decision-bearing
  entries are byte-identical, so the evidence document moved under an unchanged
  judgement.
- `graphify_semantic_fingerprint_sha256` — a real signature change
  (`max_retry_depth: int = 3` -> `int | None = None`, upstream #2880). No effect
  on this repo, established by reading all three call sites: the driver passes
  the kwarg explicitly, so the new env-reading default is unreachable.

## The defect the bots found that two human-directed reviews did not

CodeRabbit — advisory here by doctrine, and rate-limited often enough that this
repo built `kb-review` to replace it — found a LIVE BREAK the cold cross-family
lane and the author both missed.

`_runtime_reasons` matched `(graphify_runtime, graphify_version)` against pairs
whose version half was HAND-WRITTEN beside the runtime half. The 0.9.46 -> 0.9.47
bump advanced the runtime and left the literal, so the pair was unmatchable and
the non-authority path rejected EVERY run under the installed version.

The comment at that site PREDICTED this failure in those words, having been
written after the identical slip one release earlier. It recurred anyway. Prose
that forecasts a defect does not prevent it; deriving the value does — the fix
computes `(identity, identity.version)`, making the skew unrepresentable.

Nothing in this repo caught it: the suite was rc=0 throughout because no test
exercised the non-authority path.

## Three of four bot findings were REFUTED, each with a control arm

graphify-labs rated four findings "agreed by 2 of 2 members but NOT verified" —
the right hedge, because consensus between two members was wrong three times:
- skip_reason `#` stripped as a comment: FALSE (`_parse` skips only a line whose
  FIRST character is `#`; control arm showed a real comment line being skipped in
  the same probe).
- inserted dataclass field breaks positional construction: FALSE (AST-walked all
  9 construction sites; zero positional).
- manifest `load` rejects previously accepted `kind` values: FALSE (73 of 73 load;
  control arm showed an invalid kind being refused).

## The environmental defect

`kb_setup.graph_first` writes its PreToolUse session marker relative to cwd, so a
`cd sources/graphify && git ...` planted an untracked file inside a pinned source
clone. `source_manifest` refused with `source-snapshot-drift` and two corpus tests
failed several layers from the cause. Filed as #420.


## Outcome

- Signal: corrected
- Correction: An ADVISORY reviewer found the round's only real defect, and both gates missed it.

This repo's doctrine says CodeRabbit is advisory and `kb-review`'s cold
cross-family lane is the real gate, because CodeRabbit returned "Review rate
limited" on 4 of 5 PRs. That reasoning is about AVAILABILITY and it is still
correct. It says nothing about DETECTION, and the round measured the difference:

- the cold codex lane: 3 findings, all LOW/INFO documentation accuracy, 0 blocking
- the author reading his own diff: 0
- CodeRabbit: the one Major that was a live break

The break had been shipped TWO releases earlier and sat behind a green suite the
whole time, because no test exercised the path it broke.

The transferable lesson is not "trust the bots". It is that a reviewer's
CLASSIFICATION (advisory vs gate) is about whether you can DEPEND on it, and
carries no information about whether its findings are real. An advisory reviewer's
findings still have to be read and verified — and on this round, verifying them
refuted three of four while confirming the one that mattered.

Second, smaller lesson, from the fix: the first test written alongside it was
insufficient and only a mutation sweep said so. An arm reverting the constant to
its stale value SURVIVED, because a self-consistency assertion stays true when
BOTH halves are stale. The test covered the restatement half of the defect and not
the staleness half — the half actually reported. A fix's own test is the
least-reviewed code in the diff, and `kb-arms` is what makes that visible.
