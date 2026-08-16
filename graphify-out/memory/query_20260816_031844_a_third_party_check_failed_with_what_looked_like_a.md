---
type: "query"
date: "2026-08-16T03:18:44.850216+00:00"
question: "A third-party check failed with what looked like a complaint about AI authorship — what should I have done?"
contributor: "graphify"
outcome: "useful"
---

# Q: A third-party check failed with what looked like a complaint about AI authorship — what should I have done?

## Answer

Read the check's DETAIL page. The summary line was almost unactionable and the
detail was specific and correct.

`Repowise / code health` failed PR #325 with only:

    AI-authored files account for the larger share of this PR's regression
    (-0.7 vs -0.0 human)

That reads as a complaint about WHO wrote the code, and the natural next thought
was to classify the check as advisory the way CodeRabbit already is. It has zero
annotations, so `gh api .../check-runs` gives nothing more.

The detail page named the actual finding: `currency/config.py` down 0.6, with
`_ref_bindings` at cyclomatic complexity 10 — code added in that same PR, and
exactly this repo's `[tool.ruff.lint.mccabe] max-complexity`, which is why ruff
passed it. Real, actionable, and below the local gate's threshold.

Split into three functions; behaviour identical, 18 tests unchanged, and at a
threshold of 6 ruff flags neither new function. Repowise then passed.

Two durable points:

1. A gate's SUMMARY can be a worse description of its finding than its detail.
   Fetch the detail before deciding a check is unactionable — and especially
   before reclassifying it as advisory, which is reclassifying a gate to get past
   it. CodeRabbit's advisory status was earned by a measured rate-limit problem,
   not by inconvenience.

2. Repowise counted `_tool_spec` at 12; ruff counts 7. Two tools measuring
   "cyclomatic complexity" disagreed by 5 on one function. Neither number is
   absolute — what they agreed on was WHICH function moved, and that is the part
   worth acting on.


## Outcome

- Signal: useful