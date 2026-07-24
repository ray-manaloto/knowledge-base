# how-hints-work

Outcomes are recorded per delegation and aggregated deterministically. A lane node is tagged
preferred / tentative / contested for a [[task-class-migration]]-style cell only when >=3
CONSISTENT outcomes agree, session-deduplicated (one bad spec producing 3 reworks in one
session is NOT 3 votes). The tag is advisory over [[routing-doctrine]] — it nudges, never
overrides on a single result. Regression path: a preferred tag can decay to tentative.
