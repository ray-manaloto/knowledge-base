---
type: "query"
date: "2026-08-17T11:59:29.126410+00:00"
question: "A third-party health check failed a PR and the handoff had already ruled out the cause"
contributor: "graphify"
outcome: "useful"
---

# Q: A third-party health check failed a PR and the handoff had already ruled out the cause

## Answer

A third-party health check (`Repowise / code health`) failed PR #331 with a
summary that reads as unactionable — an AI-vs-human authorship split and a
"-0.1 vs -0.0" regression. The previous session's handoff had already ruled out
the obvious cause, stating: "Complexity is NOT the obvious cause this time. At a
threshold of 6, ruff C901 over the four modules this round changed flags only
`open_directory_nofollow` (7) and `parse_result_envelope` (10), both
pre-existing. The probe found two functions, so it discriminates."

TWO THINGS WERE TRUE AND ONE CONCLUSION WAS WRONG.

1. The check's SUMMARY is not the check's FINDING. The `check-runs` API carries
   no annotations for it and `output.text` holds only a blast-radius list. The
   actionable content lives on the vendor's detail page
   (`https://repowise.dev/pr/<owner>/<repo>/<n>`), fetchable with WebFetch. It
   named exactly one cause: `adapter_main` at cyclomatic 9 with 3 nested blocks
   at the same level, and attributed the ENTIRE -0.1 to that one file. Prior art
   on PR #325 is the same check failing the same way with the same
   authorship-flavoured summary and the same kind of real complexity regression
   underneath. READ THE DETAIL PAGE BEFORE BELIEVING THE SUMMARY.

2. The handoff's ruling-out was WRONG, and the mechanism is NOT a threshold
   bound — which is what makes it worth recording. Re-derived: at threshold 6
   over those four modules ruff flags NINETEEN functions, and over the adapter
   alone it flags three, INCLUDING `adapter_main`, which was at 9 then and met
   the probe's own stated criterion. So the probe was fine and could
   discriminate; the LIST reported from it dropped a qualifying row — and that
   row was the answer. This is `measure-a-ruled-list-before-executing-it`
   arriving from the other direction: there, a named list was longer than the
   criterion justified; here, it was SHORTER, and the omitted row was the whole
   finding. A ruled-out list needs re-deriving exactly as much as a ruled-in one,
   and a negative conclusion inherited from a handoff carries no control arm.

THE FIX AND WHAT IT EXPOSED. Extracting `_completion_reasons` and
`_report_rejection` out of `adapter_main` took it 9 -> 6, below the 8 it carried
at the last commit where the check passed. But the refactor was not the whole
value: before it, NO test reached the adapter's refusal path at all.
`truncation_retry_hint` was armed as a DECISION while its only consumer sat
inline in `adapter_main`, which no test invokes — so deleting the call left the
entire suite green. A decision can be thoroughly armed while its one consumer is
completely unarmed, and the mutation sweep on the decision cannot see that. The
extraction is what made the wiring reachable; two of four new `kb-arms` rows are
exactly that deletion, and they now fail.

CARRY THE PROBE'S CONDITION. The first version of the code comment said "ruff
C901 read 9 and now reads 6" without stating the threshold. This repo's
configured `max-complexity` is 10, so `adapter_main` never failed our own ruff
gate at either value and the refactor turned no red gate green. The cold lane
caught it. The lowered threshold's only purpose was to make ruff report the same
METRIC the external check reports so the two could be compared — and they agreed
exactly at 9, which is what converted an opaque vendor summary into a named
function. A number without its condition survives review and is still wrong
where it is read.


## Outcome

- Signal: useful