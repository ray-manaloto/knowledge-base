---
type: "query"
date: "2026-08-19T18:33:28.206183+00:00"
question: "What did the 2026-08-19 /clear-prep round find, and why did three defenses miss a supply-chain regression?"
contributor: "graphify"
outcome: "corrected"
correction: "Three corrections, all mine, all the same shape: I reported a fix as done when\nthe evidence said otherwise.\n\n1. I claimed \"81 tool sections preserved\" as proof the lockfile survived. It was\n   a TOTAL, and the total held only because one tool duplicated while two\n   emptied. The audit that actually works counts PER TOOL against the previous\n   revision.\n\n2. I claimed to have parenthesised an `except` in\n   `python/src/kb_setup/session_select.py`. `git log -S` finds no commit\n   containing the parenthesised form: this repo's ruff config STRIPS those\n   parentheses, so the edit never survived `mise run fmt`. Probed directly. The\n   form is valid under PEP 758 on the pinned 3.14 and FOUR reviewers have now\n   called it a SyntaxError.\n\n3. I proposed `tag_prefix`-style currency.toml machinery for rumdl's `v` prefix\n   instead of asking the tool. `mise ls-remote rumdl` lists bare versions, zero\n   v-prefixed — one command, no config needed. Ray caught it. The proposal was\n   withdrawn and the bump done with `mise use rumdl@0.2.57`, which wrote the bare\n   pin itself and kept the lock at 7/7.\n\nThe pattern across all three: a claim about my own work, stated with the\nconfidence of a measurement, where the measurement had not been made or had been\nmade at the wrong granularity.\n"
---

# Q: What did the 2026-08-19 /clear-prep round find, and why did three defenses miss a supply-chain regression?

## Answer

The /clear-prep round of 2026-08-19 answered Ray's question about automating the
previous round's three lessons, and then found that the previous round had
shipped a supply-chain regression to main.

THE REGRESSION. PR #375 merged a mise.lock that had lost uv's 7 platform blocks
and 7 checksums, hk's 6/6, six of doppler's seven, and had DUPLICATED fnox to
14. Every `checksum`, `url_api` and `provenance = "github-attestations"` line
for uv and hk was gone. Cause: hand-edited pins followed by `mise install`,
which rewrites lock entries only for the platform it resolves on. Fix:
`mise lock -p <all seven platforms>` with NO tool argument.

WHY IT WAS NOT CAUGHT, and this is the durable part. Three separate defenses
failed in the same direction:

1. My own check verified "81 tool sections preserved" and reported it as proof.
   The total held BECAUSE fnox doubled while uv and hk emptied. A count-based
   guard catches corruption only by luck.
2. graphify's PR bot reported it TWICE, 54 and 36 minutes before the merge. The
   bot sweep read `pulls/N/comments` — the INLINE-comment endpoint — while
   graphify posts in the review BODY at `pulls/N/reviews`. "Zero new inline
   comments" was true; "the bots found nothing" was false. A probe's SHAPE
   decided its answer.
3. No gate checks lockfile provenance at all.

ISSUES FILED: #376 (a deferral inside the reviewed window is SCOPE for the
reviewer, not an exemption — why the sweep skipped the whole THIRD ADDENDUM),
#377 (kb-restatements: 17 of the 20 red tests in the 0.9.46 bump were duplicated
literals), #378 (a justification's SCOPE is unchecked), #379 (a heredoc importing
kb_setup is a wrapper candidate by definition), #380 (the four bot-review
surfaces), #381 (use `mise use` / `uv add`, never hand-edit), #382 (dependencies
move during slow rounds), #383, #384.

CODESMITH PUSHED COMMITS TO WORKING BRANCHES THREE TIMES, and was right every
time: the exact-set assertion, the `$` anchor plus two record corrections, and
`sources/rumdl.manifest` left behind by `mise use`. Detected only because
`kb-ship` then failed non-fast-forward.


## Outcome

- Signal: corrected
- Correction: Three corrections, all mine, all the same shape: I reported a fix as done when
the evidence said otherwise.

1. I claimed "81 tool sections preserved" as proof the lockfile survived. It was
   a TOTAL, and the total held only because one tool duplicated while two
   emptied. The audit that actually works counts PER TOOL against the previous
   revision.

2. I claimed to have parenthesised an `except` in
   `python/src/kb_setup/session_select.py`. `git log -S` finds no commit
   containing the parenthesised form: this repo's ruff config STRIPS those
   parentheses, so the edit never survived `mise run fmt`. Probed directly. The
   form is valid under PEP 758 on the pinned 3.14 and FOUR reviewers have now
   called it a SyntaxError.

3. I proposed `tag_prefix`-style currency.toml machinery for rumdl's `v` prefix
   instead of asking the tool. `mise ls-remote rumdl` lists bare versions, zero
   v-prefixed — one command, no config needed. Ray caught it. The proposal was
   withdrawn and the bump done with `mise use rumdl@0.2.57`, which wrote the bare
   pin itself and kept the lock at 7/7.

The pattern across all three: a claim about my own work, stated with the
confidence of a measurement, where the measurement had not been made or had been
made at the wrong granularity.
