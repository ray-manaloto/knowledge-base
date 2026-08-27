---
type: "query"
date: "2026-08-27T17:15:51.856308+00:00"
question: "How many graphify subcommands are missing from --help, and was callflow-html one of them?"
contributor: "graphify"
outcome: "corrected"
correction: "The count was 18. It is 14, and one of the two examples was wrong.\n\nRE-DERIVED by a cold codex lane against upstream Graphify-Labs/graphify, then the\nsharpest correction re-confirmed by hand before propagating:\n\n    graphify --help | grep -n callflow   ->  122:  export callflow-html …\n    graphify --help | grep -c hook-guard ->  0     (control: the grep discriminates)\n\nSo `callflow-html` was NEVER missing from --help, and neither was `status`\n(`hook status` is listed under its parent). Two real gaps were MISSED instead:\n`export neo4j`, and `provider` — an entire undocumented parent command with four\nsubcommands. Corrected figure: 14 undocumented command paths.\n\n    prs · provider · cache-check · merge-chunks · merge-semantic ·\n    hook-check · hook-guard · 7 of export's 8 formats\n\nRETRACTED ENTIRELY: the claim that Ray's PART TWO directive 3 asked for\n`callflow-html` because --help hid it. The command is listed. Why he asked for it\nis not something anyone measured, and asserting a cause for someone else's\nrequest was the overreach, not just the arithmetic.\n\nSURVIVES: `prs` is genuinely absent from --help while being fully working and\ndocumented in the README with eight usage lines. That is the feature this session\nmissed, and the root-cause lesson is unchanged — a tool's --help is a SECONDARY\nartifact about itself and it ages; the graph knew and was not asked.\n\nNARROWER THAN CLAIMED: every one of the 14 except `prs`, `hook-check` and\n`hook-guard` prints its own usage on bad or missing args. The defect is\nspecifically that the TOP-LEVEL listing never names the verb, not that the\ncommands are undocumented everywhere.\n\nROOT CAUSE, read from source: `__main__.py`'s help is ~140 hand-written print()\ncalls, not generated from `dispatch_command()`'s dispatch table. Two\nindependently maintained lists that drifted.\n\nTHE PROCESS LESSON, which is the durable half: I authored the wrong number and\nthen propagated it into a PUBLISHED artifact, a committed memory file, a handoff\nand four messages before anything checked it. `probes-need-a-control-arm.md`\nrule 6 is about INHERITED numbers; this is the same failure with a shorter fuse,\nbecause an author's own figure reads as verified forever. The lane that caught it\nwas doing a different job. Corrections applied to the artifact IN PLACE with the\noriginal claim left visible, per the output style's rule that a page corrected\nafter publication says so.\n"
---

# Q: How many graphify subcommands are missing from --help, and was callflow-html one of them?

## Answer

The count was 18. It is 14, and one of the two examples was wrong.

RE-DERIVED by a cold codex lane against upstream Graphify-Labs/graphify, then the
sharpest correction re-confirmed by hand before propagating:

    graphify --help | grep -n callflow   ->  122:  export callflow-html …
    graphify --help | grep -c hook-guard ->  0     (control: the grep discriminates)

So `callflow-html` was NEVER missing from --help, and neither was `status`
(`hook status` is listed under its parent). Two real gaps were MISSED instead:
`export neo4j`, and `provider` — an entire undocumented parent command with four
subcommands. Corrected figure: 14 undocumented command paths.

    prs · provider · cache-check · merge-chunks · merge-semantic ·
    hook-check · hook-guard · 7 of export's 8 formats

RETRACTED ENTIRELY: the claim that Ray's PART TWO directive 3 asked for
`callflow-html` because --help hid it. The command is listed. Why he asked for it
is not something anyone measured, and asserting a cause for someone else's
request was the overreach, not just the arithmetic.

SURVIVES: `prs` is genuinely absent from --help while being fully working and
documented in the README with eight usage lines. That is the feature this session
missed, and the root-cause lesson is unchanged — a tool's --help is a SECONDARY
artifact about itself and it ages; the graph knew and was not asked.

NARROWER THAN CLAIMED: every one of the 14 except `prs`, `hook-check` and
`hook-guard` prints its own usage on bad or missing args. The defect is
specifically that the TOP-LEVEL listing never names the verb, not that the
commands are undocumented everywhere.

ROOT CAUSE, read from source: `__main__.py`'s help is ~140 hand-written print()
calls, not generated from `dispatch_command()`'s dispatch table. Two
independently maintained lists that drifted.

THE PROCESS LESSON, which is the durable half: I authored the wrong number and
then propagated it into a PUBLISHED artifact, a committed memory file, a handoff
and four messages before anything checked it. `probes-need-a-control-arm.md`
rule 6 is about INHERITED numbers; this is the same failure with a shorter fuse,
because an author's own figure reads as verified forever. The lane that caught it
was doing a different job. Corrections applied to the artifact IN PLACE with the
original claim left visible, per the output style's rule that a page corrected
after publication says so.


## Outcome

- Signal: corrected
- Correction: The count was 18. It is 14, and one of the two examples was wrong.

RE-DERIVED by a cold codex lane against upstream Graphify-Labs/graphify, then the
sharpest correction re-confirmed by hand before propagating:

    graphify --help | grep -n callflow   ->  122:  export callflow-html …
    graphify --help | grep -c hook-guard ->  0     (control: the grep discriminates)

So `callflow-html` was NEVER missing from --help, and neither was `status`
(`hook status` is listed under its parent). Two real gaps were MISSED instead:
`export neo4j`, and `provider` — an entire undocumented parent command with four
subcommands. Corrected figure: 14 undocumented command paths.

    prs · provider · cache-check · merge-chunks · merge-semantic ·
    hook-check · hook-guard · 7 of export's 8 formats

RETRACTED ENTIRELY: the claim that Ray's PART TWO directive 3 asked for
`callflow-html` because --help hid it. The command is listed. Why he asked for it
is not something anyone measured, and asserting a cause for someone else's
request was the overreach, not just the arithmetic.

SURVIVES: `prs` is genuinely absent from --help while being fully working and
documented in the README with eight usage lines. That is the feature this session
missed, and the root-cause lesson is unchanged — a tool's --help is a SECONDARY
artifact about itself and it ages; the graph knew and was not asked.

NARROWER THAN CLAIMED: every one of the 14 except `prs`, `hook-check` and
`hook-guard` prints its own usage on bad or missing args. The defect is
specifically that the TOP-LEVEL listing never names the verb, not that the
commands are undocumented everywhere.

ROOT CAUSE, read from source: `__main__.py`'s help is ~140 hand-written print()
calls, not generated from `dispatch_command()`'s dispatch table. Two
independently maintained lists that drifted.

THE PROCESS LESSON, which is the durable half: I authored the wrong number and
then propagated it into a PUBLISHED artifact, a committed memory file, a handoff
and four messages before anything checked it. `probes-need-a-control-arm.md`
rule 6 is about INHERITED numbers; this is the same failure with a shorter fuse,
because an author's own figure reads as verified forever. The lane that caught it
was doing a different job. Corrections applied to the artifact IN PLACE with the
original claim left visible, per the output style's rule that a page corrected
after publication says so.
