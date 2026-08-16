---
type: "query"
date: "2026-08-16T17:46:20.251142+00:00"
question: "Why did a verified diagnostic fix fail to appear in the real run?"
contributor: "graphify"
outcome: "corrected"
correction: "Two reporters can emit IDENTICAL text from different code — fixing one proves nothing about the other.\n\nI added `unresolved_paths` to `graphify_health.require_complete`'s failure\nmessage and verified it in isolation:\n\n    Graphify detect failed closed (incomplete): unclassified-files; unresolved=['a.zzz']\n\nThe real build still printed `unclassified=[...]`. Not caching, not a stale\nprocess — `graph.py:_source_census_failure_detail` SYNTHESISES the same-looking\nsentence from a `SourceCensusReceipt`, a different struct that never carried the\nfield. Same wording, different producer, and the string I grepped for existed in\nboth places.\n\n**The isolated probe passed and the production path was untouched.** Only\nre-running the end-to-end build exposed it. If I had trusted the unit check I\nwould have shipped a diagnostic that never fires where it is needed.\n\nThe tell was available and I nearly reasoned past it: the message said\n`unclassified=`, which under my change was only reachable when `unresolved` was\nempty — but the blocking reason had fired, and both are computed from the same\nset. That contradiction meant \"this is not my code running\", and the right next\nmove was to find the OTHER producer rather than to re-explain the one I had.\n\nSame shape, same round, third instance: `_require_post_detection_clone_identity`\nCAUGHT the exception and replaced its message with a fixed string, so four\ndistinct drift causes reported identically. Discarding an exception's detail is\nthe same defect as duplicating a message — in both cases the text a reader sees\nis decoupled from the code that decided it.\n\nAsk of any diagnostic: **who else can print this sentence?** `grep` the message,\nnot the function.\n"
---

# Q: Why did a verified diagnostic fix fail to appear in the real run?

## Answer

Two reporters can emit IDENTICAL text from different code — fixing one proves nothing about the other.

I added `unresolved_paths` to `graphify_health.require_complete`'s failure
message and verified it in isolation:

    Graphify detect failed closed (incomplete): unclassified-files; unresolved=['a.zzz']

The real build still printed `unclassified=[...]`. Not caching, not a stale
process — `graph.py:_source_census_failure_detail` SYNTHESISES the same-looking
sentence from a `SourceCensusReceipt`, a different struct that never carried the
field. Same wording, different producer, and the string I grepped for existed in
both places.

**The isolated probe passed and the production path was untouched.** Only
re-running the end-to-end build exposed it. If I had trusted the unit check I
would have shipped a diagnostic that never fires where it is needed.

The tell was available and I nearly reasoned past it: the message said
`unclassified=`, which under my change was only reachable when `unresolved` was
empty — but the blocking reason had fired, and both are computed from the same
set. That contradiction meant "this is not my code running", and the right next
move was to find the OTHER producer rather than to re-explain the one I had.

Same shape, same round, third instance: `_require_post_detection_clone_identity`
CAUGHT the exception and replaced its message with a fixed string, so four
distinct drift causes reported identically. Discarding an exception's detail is
the same defect as duplicating a message — in both cases the text a reader sees
is decoupled from the code that decided it.

Ask of any diagnostic: **who else can print this sentence?** `grep` the message,
not the function.


## Outcome

- Signal: corrected
- Correction: Two reporters can emit IDENTICAL text from different code — fixing one proves nothing about the other.

I added `unresolved_paths` to `graphify_health.require_complete`'s failure
message and verified it in isolation:

    Graphify detect failed closed (incomplete): unclassified-files; unresolved=['a.zzz']

The real build still printed `unclassified=[...]`. Not caching, not a stale
process — `graph.py:_source_census_failure_detail` SYNTHESISES the same-looking
sentence from a `SourceCensusReceipt`, a different struct that never carried the
field. Same wording, different producer, and the string I grepped for existed in
both places.

**The isolated probe passed and the production path was untouched.** Only
re-running the end-to-end build exposed it. If I had trusted the unit check I
would have shipped a diagnostic that never fires where it is needed.

The tell was available and I nearly reasoned past it: the message said
`unclassified=`, which under my change was only reachable when `unresolved` was
empty — but the blocking reason had fired, and both are computed from the same
set. That contradiction meant "this is not my code running", and the right next
move was to find the OTHER producer rather than to re-explain the one I had.

Same shape, same round, third instance: `_require_post_detection_clone_identity`
CAUGHT the exception and replaced its message with a fixed string, so four
distinct drift causes reported identically. Discarding an exception's detail is
the same defect as duplicating a message — in both cases the text a reader sees
is decoupled from the code that decided it.

Ask of any diagnostic: **who else can print this sentence?** `grep` the message,
not the function.
