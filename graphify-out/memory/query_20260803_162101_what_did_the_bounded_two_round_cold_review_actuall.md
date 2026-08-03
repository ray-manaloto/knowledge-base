---
type: "query"
date: "2026-08-03T16:21:01.470667+00:00"
question: "What did the bounded two-round cold review actually catch on a 16-commit branch?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did the bounded two-round cold review actually catch on a 16-commit branch?

## Answer

8 findings, 0 blocking at HEAD, from ONE cross-family lane (codex/GPT-5.6 against Claude-authored code). Round 1: (a) mise.toml bumped hk/fnox while sources/*.manifest still pinned the old tags, invisible because currency.toml declared no manifest so the check SKIPped with the reason 'this repo pins no source manifest' — a reason that was true when written and became false when the manifest landed; (b) chunks.validate was referenced ONLY in cli.py, so the _origin rule added the same day gated nothing — the exact defect filed as #134 hours earlier, repeated inside the fix for a different one. Round 2 found SIX more, the sharpest being that round 1's own fix DESTROYED DATA: 4 of 37 'provably inert' deleted edges resolved cross-chunk, because graphify's build_merge prepends existing nodes as a base chunk and resolves against the COMBINED set. I trusted my per-chunk validator model over graphify's merge semantics. Also: build() validated AFTER overwriting graph.json (non-atomic refusal); the manifest check compared ref while kb-build checks out commit (independent fields); hyperedges were outside the validator entirely; a valid-JSON array crashed validate() against its own never-raises contract. GIVING THE LANE A MUTATING INSTRUCTION IS WHAT MADE IT SHARP — the skill records that method, not lane identity, predicted blockers, and every finding here came with the mutation that would falsify it.

## Outcome

- Signal: useful