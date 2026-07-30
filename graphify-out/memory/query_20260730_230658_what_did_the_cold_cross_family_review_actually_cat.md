---
type: "query"
date: "2026-07-30T23:06:58.590265+00:00"
question: "What did the cold cross-family review actually catch that self-review did not?"
contributor: "graphify"
outcome: "corrected"
correction: "A carefully-worded failure message is not evidence the failure path works; I wrote a good UNKNOWN message and made the state it describes irrecoverable in the same function."
source_nodes: ["python/src/kb_setup/graph.py"]
---

# Q: What did the cold cross-family review actually catch that self-review did not?

## Answer

The defect I had REASONED PAST in my own comment. _report_doc_changes wrote the manifest pin, then diffed, and on diff failure printed 'UNKNOWN, not empty. Re-run.' My comment said 'Advancing the pin already succeeded, so this is a report gap, not a build failure' — wrong, because the pin had moved, so the re-run hit 'latest == m.commit' and reported 'already at latest — nothing to do'. The worklist was UNRECOVERABLE and the careful message pointed at a retry that could not work. Fix: clone to latest in memory, diff, write the pin ONLY on success. Three more, all real and all cited: update_all() filtered kind=='code' so a bare kb-update skipped every docs mirror (a check that exists and never runs); an unfiltered --name-only reported repo metadata like docs_manifest.json as re-extraction work; and --name-only discards D/R status so upstream deletions came back as pages to read rather than stale extractions to remove. LESSON: the lane was COLD — given only a SHA range, no statement of intent. A reviewer handed my rationale would have nodded at that comment, because it READS as though the case was handled. Cold is what made the difference, not model strength.

## Outcome

- Signal: corrected
- Correction: A carefully-worded failure message is not evidence the failure path works; I wrote a good UNKNOWN message and made the state it describes irrecoverable in the same function.

## Source Nodes

- python/src/kb_setup/graph.py