---
type: "query"
date: "2026-08-22T18:38:31.428913+00:00"
question: "Was the graphify runtime-pair staleness class closed by the 0.9.47 derive-the-version fix?"
contributor: "graphify"
outcome: "corrected"
correction: "# A self-consistency fix cures restatement, not staleness — and the prose that predicts a defect does not prevent it\n\n## The belief that was wrong\n\n`graphify_semantic_corpus_authority.py:573-600` records this exact class twice already\n(0.9.45→0.9.46, then 0.9.46→0.9.47), and states the fix: *\"The fix DERIVES the version half\nfrom the runtime half\"*, plus the lesson *\"Prose that forecasts a defect does not prevent\nit; deriving the value does.\"* Reading that, it is natural to believe the class is closed.\n\nIt is not. It recurred one bump later, at 0.9.47→0.9.48.\n\n## What was actually true\n\nThe derive-the-version-from-the-runtime fix cured the **restatement** half — the two halves\nof the pair can no longer disagree with each other. It did nothing about the **staleness**\nhalf: all three fields now move together, so they go stale together, and\n`version == cli_version == sdk_version == 0.9.47` stays perfectly self-consistent while\nevery other site in the repo has moved to 0.9.48.\n\nThat is why nothing caught it. Every self-consistency check was green, and this repo's own\nwork-memory already names the shape: *a self-consistency test cannot see staleness* — it\n\"proves the pair agrees with ITSELF, which stays true when both halves are stale\".\n\nThe resync that missed it was not careless: it advanced `_ACCEPTED_GRAPHIFY_REF` to v0.9.48\nAND `graphify_baseline._ACCEPTED_GRAPHIFY_VERSION` to 0.9.48. It moved two of three. A\nhand-maintained constant does not need negligence to go stale, only a third site.\n\n## How to apply\n\n1. **When a fix makes two values agree, ask what they are both anchored TO.** Internal\n   agreement is not currency. The next question after \"do these agree?\" is \"with what\n   outside this file?\"\n2. **Do not answer a recurrence with a fourth hand-edit.** Bind the constant to something\n   that moves on its own — the installed runtime, or `sources/graphify.manifest`'s pinned\n   ref, the way the 0.9.47 round's second test bound the slice constant to the manifest.\n3. **Count the sites before declaring a version bump done.** This one has at least six, and\n   `kb-currency-check`'s `ref_binding` rows cover some but not `_ACCEPTED_GRAPHIFY_RUNTIME`.\n4. **A frozen-evidence constant and a stale-identity constant look identical and are\n   opposites.** `graphify_semantic_slice.py`'s `v0.9.45` is reported as drift but reads as\n   deliberately frozen evidence for a committed receipt. Settle which each site is before\n   any sweep, or a \"fix\" will falsify real evidence.\n"
---

# Q: Was the graphify runtime-pair staleness class closed by the 0.9.47 derive-the-version fix?

## Answer

# The graphify runtime constant went stale for the THIRD time — and the module predicted it twice

Scoping the deep extraction found `_ACCEPTED_GRAPHIFY_RUNTIME` at **0.9.47** while the
installed runtime, `pyproject.toml`, `uv.lock`, `sources/graphify.manifest`,
`_ACCEPTED_GRAPHIFY_REF` and `graphify_baseline._ACCEPTED_GRAPHIFY_VERSION` all say
**0.9.48**. The 0.9.48 resync advanced two of the three constants and missed the third,
and the regenerated plan carries the stale value into its own `execution-config.json`.

Measured: `LIVE 0.9.48/0.9.48/0.9.48` vs `ACCEPTED 0.9.47/0.9.47/0.9.47`, EQUAL? False.
Control arm on the baseline path, which is fine: `_runtime_payload_reasons` returns `[]`
for the live payload and `['runtime-version-drift']` for a 0.9.47 one, so the probe
discriminates. It bites at `graphify_semantic_corpus.py:1916-1917`, which compares the
provider receipt's runtime against the config's for EQUALITY. Filed as #452.


## Outcome

- Signal: corrected
- Correction: # A self-consistency fix cures restatement, not staleness — and the prose that predicts a defect does not prevent it

## The belief that was wrong

`graphify_semantic_corpus_authority.py:573-600` records this exact class twice already
(0.9.45→0.9.46, then 0.9.46→0.9.47), and states the fix: *"The fix DERIVES the version half
from the runtime half"*, plus the lesson *"Prose that forecasts a defect does not prevent
it; deriving the value does."* Reading that, it is natural to believe the class is closed.

It is not. It recurred one bump later, at 0.9.47→0.9.48.

## What was actually true

The derive-the-version-from-the-runtime fix cured the **restatement** half — the two halves
of the pair can no longer disagree with each other. It did nothing about the **staleness**
half: all three fields now move together, so they go stale together, and
`version == cli_version == sdk_version == 0.9.47` stays perfectly self-consistent while
every other site in the repo has moved to 0.9.48.

That is why nothing caught it. Every self-consistency check was green, and this repo's own
work-memory already names the shape: *a self-consistency test cannot see staleness* — it
"proves the pair agrees with ITSELF, which stays true when both halves are stale".

The resync that missed it was not careless: it advanced `_ACCEPTED_GRAPHIFY_REF` to v0.9.48
AND `graphify_baseline._ACCEPTED_GRAPHIFY_VERSION` to 0.9.48. It moved two of three. A
hand-maintained constant does not need negligence to go stale, only a third site.

## How to apply

1. **When a fix makes two values agree, ask what they are both anchored TO.** Internal
   agreement is not currency. The next question after "do these agree?" is "with what
   outside this file?"
2. **Do not answer a recurrence with a fourth hand-edit.** Bind the constant to something
   that moves on its own — the installed runtime, or `sources/graphify.manifest`'s pinned
   ref, the way the 0.9.47 round's second test bound the slice constant to the manifest.
3. **Count the sites before declaring a version bump done.** This one has at least six, and
   `kb-currency-check`'s `ref_binding` rows cover some but not `_ACCEPTED_GRAPHIFY_RUNTIME`.
4. **A frozen-evidence constant and a stale-identity constant look identical and are
   opposites.** `graphify_semantic_slice.py`'s `v0.9.45` is reported as drift but reads as
   deliberately frozen evidence for a committed receipt. Settle which each site is before
   any sweep, or a "fix" will falsify real evidence.
