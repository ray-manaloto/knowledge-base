# fable-advisor consult — codex lane verification quality (2026-08-29)

Session kb-20260829.02. Consulted on whether codex-implementer/codex-reviewer
lanes do proper verification before claiming completion, whether an
independent 4th verification dispatch is needed, and whether codex lanes
follow `/grilling -> /to-spec -> /to-tickets -> /implement`.

## Verdict (verbatim)

**Verdict: the current discipline is adequate — do NOT add an independent
verification dispatch. But the load-bearing step (caller re-runs anything the
lane couldn't verify) is currently discretionary, and that's the one gap
worth an issue.**

**Q1.** No extra codex dispatch. It would run in the same `workspace-write`
sandbox with the same no-egress limit, so it cannot run the very verification
(schemastore-backed `kb-plugin-validate`) that mattered in Case 2 — it would
re-reason over the diff, which is exactly the layer that missed the
`$comment` defect (locally schema-valid, wrapper-invalid). The defect was
caught by the only element with different capabilities: the caller re-running
the real command. Three cases show the three layers each catching a distinct
failure class (lane: environment limits + spec inaccuracies; caller re-run:
environment-dependent verification; cold review: caller-authored content). A
fourth same-family, same-sandbox layer covers no new class. What's missing is
not another verifier but a rule: **any verification item a lane grades
UNVERIFIED must be re-run by the caller before "complete" can be claimed — as
a hard requirement, not architect judgment.** Case 2 worked because Claude
chose to re-run; nothing forces the next session to.

**Q2.** Two separate, non-conflicting things — correct. The mattpocock chain
is a *planning/authoring* workflow (grill the human, produce a spec doc, mint
tickets); the fable-orchestrator 7-part spec is a *dispatch contract* between
architect and lane. They compose (ticket -> architect writes the 7-part
spec), they don't substitute. Routing every dispatch through `/grilling` would
add human-interview latency to machine-to-machine handoffs and gain nothing —
the 7-part contract already carries verification + premises, which is what
the tickets lack anyway. Keep them separate; use the chain when the *decision*
is unsettled, the contract when it is.

**Q3.** One issue: **"Lane verification grades must be machine-checked: a
completion whose report contains any UNVERIFIED verification item is refused
until the caller re-runs it"** — wire into the dispatch-report template
and/or the `kb-review` receipt path. Secondary line item in the same issue:
bake known sandbox limits (no new git refs, no network egress) into the
dispatch spec template, so Case 1's correctly-dissented-but-wasted first
dispatch doesn't recur per session.

## Where this landed

Filed as `ray-manaloto/knowledge-base#602`, reprioritized to the top of
`docs/roadmap/aggregated-research-chain.toml` (PR #607) ahead of #573.

## GitHub repos touched

_None._
