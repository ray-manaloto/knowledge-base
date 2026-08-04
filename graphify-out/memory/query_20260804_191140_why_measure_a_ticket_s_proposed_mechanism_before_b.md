---
type: "query"
date: "2026-08-04T19:11:40.881114+00:00"
question: "Why measure a ticket's proposed mechanism before building it?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why measure a ticket's proposed mechanism before building it?

## Answer

MEASURE a ticket's proposed mechanism before you build it. The proposal can be
unsatisfiable against the ticket's own acceptance criteria.

#154 asked for a stem probe: when a token's extension is unknown, take its stem
and report it if exactly one authored file shares that stem. Criterion 2 of the
same ticket said the false-positive posture must not regress.

Before writing any code I ran the proposed rule over the corpus using the shipped
extraction pipeline. It promotes 233 distinct tokens / 278 occurrences across 156
authored markdown files -- and essentially all of them are `module.attribute`
references, which this repo's handoffs are made of: `graphify_env.clean_env()`,
`gates.record`, `pr.ship_main`, `prose.derive_for`, `skill_eval.main`. A
`module.attribute` reference ALWAYS has a real module for a stem, so the probe
cannot help but fire on them. Criteria 1 and 2 could not both be met as written.

The alternative -- repair the unknown extension to a known one at Damerau
distance 1, then require the REPAIRED path to resolve uniquely -- measures 1
token / 2 occurrences on the same corpus. `gates.record` never reaches the
filesystem because no known extension is within one edit of `record`.

WHAT TO DO: when a ticket names a mechanism, spend the ten minutes to run that
mechanism over real data first. It is cheaper than building it, and the output is
exactly the evidence needed to AMEND the ticket honestly (edit the criteria, mark
them AMENDED, keep the original verbatim in a details block, comment with both
measurements) rather than silently diverging from it. A review lane later
re-derived both numbers independently and judged the amendment honest rather than
goalpost-moving -- which is only possible because the measurement was recorded.

## Outcome

- Signal: useful