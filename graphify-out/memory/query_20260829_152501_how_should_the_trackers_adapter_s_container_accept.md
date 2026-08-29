---
type: "query"
date: "2026-08-29T15:25:01.942191+00:00"
question: "How should the trackers adapter's container acceptance gate be tightened so it can fail (#571)?"
contributor: "graphify"
outcome: "useful"
---

# Q: How should the trackers adapter's container acceptance gate be tightened so it can fail (#571)?

## Answer

# Round answer — #571, tighten the trackers acceptance assertion

The container acceptance gate's direct-CLI check for the trackers adapter
asserted only `.adapter == "trackers" and (.hits | type == "array")` — true even
for a completely empty/broken result, since an empty array is still an array.

Fixed in `ray-manaloto/claude-code-marketplace` PR #6 (merged `fa27cb3`),
`ci/acceptance.sh` step d.5: split into two arms, both real —

- a term known to HIT (`openai/codex-plugin-cc` "agent team tokens") now
  asserts `total_count > 0` and a non-empty `hits` array;
- a term known to MISS asserts an empty result with a **discriminating**
  `null_result` arm (`discriminates == true`), proving the search mechanism
  actually ran rather than silently returning nothing.

Proved red-then-green directly against the live `aggregated-research` CLI
already installed on this host (no container spin-up needed): the OLD
assertion incorrectly passed a synthetic broken/empty record; the NEW
assertions correctly fail on that same record and pass on real hit/miss
records from the live CLI.

Cold cross-family review (codex, since Claude implemented it): 0 findings.
Container `acceptance` CI: SUCCESS, cross-verified via the API `conclusion`
field, not just the watch exit code.

Chain-removal follow-up: knowledge-base PR #597 (merged `d7b9ab8e`) removed
#571's entry from `docs/roadmap/aggregated-research-chain.toml`; chain now
reads READY -> #572. That mechanical 5-line diff also got its own cold review
(0 blocking, 2 informational notes about #578's stale `blockers=[570,571]`
list — expected, the file's own contract resolves blockers from live tracker
state, not chain-file presence).

Issue #571 closed by hand in knowledge-base — a bare `Closes #571` in a
cross-repo PR body does not auto-close (same trap as #569/#570 in prior
rounds, now confirmed to ALSO apply across repos, not just within one).


## Outcome

- Signal: useful