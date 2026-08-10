---
type: "query"
date: "2026-08-10T13:32:43.182269+00:00"
question: "Build §2.5's stdout sink and convert the six deferred boundaries. What did building it find that review did not?"
contributor: "graphify"
outcome: "corrected"
correction: "An end-to-end arm finds what a unit suite structurally cannot: every test in this\nround passed an explicit stream= or ran offload=False, so all 30 of them were\nblind to the DEFAULT path -- where both remaining defects lived. Running ONE real\nconverted command exposed both in seconds. The inverse of \"a test must own its own\nenvironment\": these tests owned it too thoroughly, and so never exercised the one\nconfiguration users get.\n\nAnd a finding is a SAMPLE of a class, which failed on the very fix meant to apply\nit: round 1 fixed `--audit` swallowing a record request by matching flag STRINGS,\nand round 2 found the identical bug still reachable through `--question=Q`. The\ndurable fix was not handling one more spelling -- it was deciding the mode from\nthe PARSED request so argv spellings stop being a surface at all.\n"
---

# Q: Build §2.5's stdout sink and convert the six deferred boundaries. What did building it find that review did not?

## Answer

BUILT §2.5's stdout sink (structlog event layer + stdlib sinks) and converted all
six boundaries §9b/§9d had deferred: launch (cc_main/doctor_main), graph_counts,
insights, skill_refresh, graphify_ops, pr (ship_main/land_main). PR #273.

The library choice was NOT settled before this round, contrary to what the D20
report implied. Six logging libraries were ingested; only three had any verdict.
Writing the six-way comparison first is what made structlog a documented win
rather than the only candidate tried -- decided on §2.5's own axis: whoever owns
the sink layer owns the shape of every report this repo prints. structlog ships
NO sinks, so rendering stays a logging.Formatter subclass in kb_setup.

MEASURED, closing an owed probe: logbook's MultiProcessingHandler collects 0
records under pytest-xdist (workers are execnet subprocesses, not multiprocessing
children); with the manager assembly it needs, stdlib's QueueHandler works
identically. Control arm 4/4 in logbook's designed topology, so the negative
discriminates. D20's one row favouring logbook is void.

MEASURED, the other owed item: launch.cc_main returned a child's raw returncode,
so a signal-killed child reported SIGINT as 254, SIGKILL as 247, SIGTERM as 241 --
all plausible-looking application exit codes, which is why nothing ever flagged
them. External + external_from_returncode reports 130/137/143.

SEVEN defects found by BUILDING, none by review: an emit with no sink writes
nothing; "the logger has handlers" is not "a sink is attached" (pytest's own
LogCaptureHandler fooled the guard); a StreamHandler pins sys.stdout at
construction; QueueHandler.prepare() stringifies the event dict by design and
logging swallows the resulting handler error; teardown order lost the tail; and
TWO more that only an END-TO-END arm found after everything was green -- every
line printing twice, and structlog internals leaking into the JSONL.

Separately: kb-remember was silently losing lessons. graphify save-result takes
--correction and graphify reflect renders only that field; the mise task
description never mentioned it, so 21 of 32 recorded corrections reached
LESSONS.md as a question followed by an empty arrow. Control-armed: the 11 that
DO carry the field render fine under the same renderer.


## Outcome

- Signal: corrected
- Correction: An end-to-end arm finds what a unit suite structurally cannot: every test in this
round passed an explicit stream= or ran offload=False, so all 30 of them were
blind to the DEFAULT path -- where both remaining defects lived. Running ONE real
converted command exposed both in seconds. The inverse of "a test must own its own
environment": these tests owned it too thoroughly, and so never exercised the one
configuration users get.

And a finding is a SAMPLE of a class, which failed on the very fix meant to apply
it: round 1 fixed `--audit` swallowing a record request by matching flag STRINGS,
and round 2 found the identical bug still reachable through `--question=Q`. The
durable fix was not handling one more spelling -- it was deciding the mode from
the PARSED request so argv spellings stop being a surface at all.
