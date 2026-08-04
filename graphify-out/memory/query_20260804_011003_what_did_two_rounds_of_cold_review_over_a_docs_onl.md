---
type: "query"
date: "2026-08-04T01:10:03.758656+00:00"
question: "What did two rounds of cold review over a docs-only diff find, and why did the work-memory note drift?"
contributor: "graphify"
outcome: "corrected"
---

# Q: What did two rounds of cold review over a docs-only diff find, and why did the work-memory note drift?

## Answer

WORK MEMORY IS REVIEWED BY NOBODY, SO IT DRIFTS TOWARD THE CRISPER LESSON.
Measured 2026-08-04 shipping the setup-matt-pocock-skills adaptation.

graphify-out/memory/** is in kb_setup.review.EXEMPT_PATHS, so no lane normally
reads it. This branch was the exception -- a memory note happened to be IN the
reviewed diff -- and the cold lane found it overstated: it claimed /clear-prep
step 6 was "impossible" because nothing records a gate rc, when step 5 of the
same skill tells you to redirect the gate to a file and record rc=$?. The
in-session check is performable. The two true claims are narrower: nothing
ENFORCES that step 5 ran, and the /tmp log dies with the session, so at audit
time the handoff's number is prose with no surviving artifact.

The overstatement survived because it read BETTER than the truth. "The step is
impossible" is a sharper lesson than "the evidence expires before the check", and
sharpness is what a memory note is selected for. That is a systematic bias, not
one bad sentence: the same claim had already propagated to an auto-memory entry
and to a session handoff before any reviewer saw it.

Three things follow.

1. A LANE EXEMPTION IS ALSO A REVIEW EXEMPTION. The exemption exists for a good
reason (those files cannot exist until after the review). But the corpus that
teaches every future session is the one artifact class nothing reads twice.
Scanner coverage was already made load-bearing for this directory; correctness
coverage still is not.

2. WHEN A VERIFICATION STEP LOOKS IMPOSSIBLE, CHECK THE STEP BEFORE IT. The
artifact was being created one step earlier in the same skill. "No artifact
exists" and "the artifact expires before the check" demand different fixes, and
only the second was true here.

3. ROUND 2 FOUND A DEFECT IN ROUND 1'S OWN FIX. Round 1's correction said two
skills are "handed the path explicitly" -- true for a READER (code-review) and
meaningless for a WRITER (setup-matt-pocock-skills, whose output path is itself
the problem). A single sentence covering two mechanisms will describe the one
you thought of first. It became a table, one row per skill.

Also: 7 findings across 2 rounds on a 222-line DOCS-ONLY diff, every one a false
factual claim rather than a style point -- four wrong label names, a non-consumer
listed as a consumer, a rule cited for a claim outside its stated scope. Prose
that other agents read as authoritative is code. Review it like code, and give
the lane a PROBING instruction ("go run it, both directions") rather than a
reading one -- every finding in both rounds came from a probe, none from reading.

## Outcome

- Signal: corrected