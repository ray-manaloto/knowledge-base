---
type: "query"
date: "2026-07-31T10:37:04.714920+00:00"
question: "How reliable is a file:line citation I read off a sed window?"
contributor: "graphify"
outcome: "useful"
---

# Q: How reliable is a file:line citation I read off a sed window?

## Answer

NOT reliable — measured 2026-07-31, and it cost a wrong citation in three committed places. I ran sed -n '1815,1840p' on graphify's cli.py, saw the to_json(...graph.json...) call inside the window, and wrote ':1836' by eye. The real line is 1830; 1836 is _wja(labels_path, ...), the LABELS SIDECAR write. So the citation for 'label is not a sidecar-only write' pointed at the sidecar write. It shipped in PR #95 and was repeated into a work-memory entry under a 'Verified in installed 0.9.30' framing, which is how a confidently-wrong fact becomes settled. Caught by the cold lane on the very next branch. THE RULE: a line number is a MEASUREMENT — get it from 'grep -n <exact pattern>' which prints the number, never by counting rows in a sed/head window. A ranged read tells you a line is somewhere in the range; it does not tell you where. This is probes-need-a-control-arm rule 6 (an inherited or eyeballed number is not a measurement) applied to the cheapest possible case.

## Outcome

- Signal: useful