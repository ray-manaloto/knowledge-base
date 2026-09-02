---
type: "query"
date: "2026-09-02T06:10:06.106092+00:00"
question: "Was the stale v0.9.48-s2 cache and the 1,259 root-anchored aggregate nodes the cause of the kb-build collision failure?"
contributor: "graphify"
outcome: "corrected"
correction: "The inherited root cause was WRONG, and it named real things that were not the carrier.\n\nThe handoff said: purge the stale `v0.9.48-s2` aggregate cache and the 1,259\nroot-anchored nodes in `graphify-out/graph.json`. Both figures were correctly measured\nand both were causally irrelevant:\n\n- the stale cache contained ZERO references to the failing source (control: 789 of 789\n  files in it contain `source_file`);\n- the 1,259 root-anchored values span only 18 distinct paths, 995 of them under\n  `sources/media/` — this repo's own vendored documents, correctly filed. Deleting them\n  would have destroyed correct data.\n\nThe real carrier was a stale root-anchored sub-graph inside each of twelve CLONES.\n\nThe lesson is not \"check harder\". It is that a root-cause story can name a carrier that\ndoes not carry it, and the cheap way to tell is to ask of each purge target: does the\nfailing identifier actually appear in it? Two greps with control arms answered that in\nunder a minute and saved an expensive purge of correct data.\n\nSecond correction in the same round: my own census module reported\n`dependency-cruiser` as 0 syntax / 0 collisions when a build had measured 10 and 7\ntwenty minutes earlier. Two probes of one fact disagreeing is a free defect detector,\nand the defect was mine — the census ran against warm sub-graphs, so `--force` went\nincremental and the silence was mistaken for health.\n"
---

# Q: Was the stale v0.9.48-s2 cache and the 1,259 root-anchored aggregate nodes the cause of the kb-build collision failure?

## Answer

The inherited root cause was WRONG, and it named real things that were not the carrier.

The handoff said: purge the stale `v0.9.48-s2` aggregate cache and the 1,259
root-anchored nodes in `graphify-out/graph.json`. Both figures were correctly measured
and both were causally irrelevant:

- the stale cache contained ZERO references to the failing source (control: 789 of 789
  files in it contain `source_file`);
- the 1,259 root-anchored values span only 18 distinct paths, 995 of them under
  `sources/media/` — this repo's own vendored documents, correctly filed. Deleting them
  would have destroyed correct data.

The real carrier was a stale root-anchored sub-graph inside each of twelve CLONES.

The lesson is not "check harder". It is that a root-cause story can name a carrier that
does not carry it, and the cheap way to tell is to ask of each purge target: does the
failing identifier actually appear in it? Two greps with control arms answered that in
under a minute and saved an expensive purge of correct data.

Second correction in the same round: my own census module reported
`dependency-cruiser` as 0 syntax / 0 collisions when a build had measured 10 and 7
twenty minutes earlier. Two probes of one fact disagreeing is a free defect detector,
and the defect was mine — the census ran against warm sub-graphs, so `--force` went
incremental and the silence was mistaken for health.


## Outcome

- Signal: corrected
- Correction: The inherited root cause was WRONG, and it named real things that were not the carrier.

The handoff said: purge the stale `v0.9.48-s2` aggregate cache and the 1,259
root-anchored nodes in `graphify-out/graph.json`. Both figures were correctly measured
and both were causally irrelevant:

- the stale cache contained ZERO references to the failing source (control: 789 of 789
  files in it contain `source_file`);
- the 1,259 root-anchored values span only 18 distinct paths, 995 of them under
  `sources/media/` — this repo's own vendored documents, correctly filed. Deleting them
  would have destroyed correct data.

The real carrier was a stale root-anchored sub-graph inside each of twelve CLONES.

The lesson is not "check harder". It is that a root-cause story can name a carrier that
does not carry it, and the cheap way to tell is to ask of each purge target: does the
failing identifier actually appear in it? Two greps with control arms answered that in
under a minute and saved an expensive purge of correct data.

Second correction in the same round: my own census module reported
`dependency-cruiser` as 0 syntax / 0 collisions when a build had measured 10 and 7
twenty minutes earlier. Two probes of one fact disagreeing is a free defect detector,
and the defect was mine — the census ran against warm sub-graphs, so `--force` went
incremental and the silence was mistaken for health.
