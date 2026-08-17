---
type: "query"
date: "2026-08-17T15:41:33.982379+00:00"
question: "Why does kb-build die at the extraction phase, and is #328's per-file registration the right remedy?"
contributor: "graphify"
outcome: "corrected"
correction: "A ticket written from the first failure is written from a sample of one, and its\nproposed remedy is sized to that sample. #328 stated the per-file hash registry\nwas right \"here\" — a handful of files in a curated source, not #289's 7,603\nvendored paths. It was measured this round at **2,675 zero-node JSON files\nacross 55 of 71 sources**. The build had only ever reached source 2 of 71, so\nnobody had seen past it; the argument was sound and its population was wrong.\n\nTwo habits follow, and the first is the cheap one:\n\n1. **Before implementing a ticket's specified remedy, measure the population it\n   is sized for.** Here it cost one census script and answered in seconds what\n   two build rounds could not.\n\n2. **A gate can be a check that could only fail, and it looks exactly like a\n   gate that never fired.** The approver reconstructed graphify's warning by\n   joining every reviewed name while graphify truncates the list at five, so any\n   source with six or more registered files was unapprovable by construction.\n   Nothing reported this: it presented as \"the files are not registered yet\",\n   which is precisely what the issue concluded. `probes-need-a-control-arm.md`\n   rule 2 says to arm the PASS direction of a gate; that had never been done\n   here because the gate had never passed, and its one passing case (4 files)\n   sat under the truncation limit and so could not exhibit the bug.\n"
---

# Q: Why does kb-build die at the extraction phase, and is #328's per-file registration the right remedy?

## Answer

`kb-build` reached the extraction phase for the first time since the graph was
lost and died on `Attacca` with reason `stderr`. #328 read that as "register the
8 zero-node files and decide what to do about one .astro file". Both halves of
that reading were too small.

## The registration could not have worked, for two independent reasons

**Graphify truncates its own warning.** The #1666 zero-node warning shows at
most five basenames and then "(+N more)" (`extract.py:5511`). The approver built
its expected string by joining EVERY reviewed name and comparing for equality,
so for a source with more than five metadata-only files the two strings can
never be equal. `Attacca` has eight. The registration was unsatisfiable however
correctly it was written — a check that could only fail, which is the shape
`probes-need-a-control-arm.md` is about, sitting inside a gate rather than a
probe.

**Approval was whole-stderr, not per warning.** `_basic_reasons` cleared stderr
when `approved_classifications == (TOKEN,)`, i.e. one recognised warning
approved everything the subprocess printed. `Attacca` prints TWO independent
warnings, so there was no spelling of "both of these are reviewed" — and in the
passing case, a single registered warning would have waved through any unrelated
second warning for free. The same hole existed twice more in different spellings:
`checked_extract` blanked all of stderr on approval (which also swallowed
unrelated `warnings.catch_warnings` messages raised in the same call), and
`graphify_baseline` built its warnings list as "stderr unless something was
approved".

Approval is now per warning line. Each line is accounted for by name; whatever
is left over is `residual_stderr` and blocks. A classification token records WHY
something was approved and is no longer sufficient on its own.

## The .astro loss is total, not partial

Ray's ruling was to measure before choosing a remedy, because "may be partially
extracted" states no count. Measured: `website/src/pages/index.astro` (898 lines)
yields **1 node — its own file stub — and 0 of its 25 named symbols** (5
frontmatter consts, 7 named functions in the inline `<script>`, 13 script-level
bindings, each enumerated from the file at pin 34a52ce09db1).

Two independent routes agree. The sub-graph contains exactly one node for that
path; and graphify's own warning is gated at `extract.py:5622` on
`len(nodes) <= 1 or multiline_error`, so the branch that fired is the
file-node-only one — graphify had already concluded the same thing.

Control arm: `scripts/validate-plugins.mjs` in the same source yields 9 symbol
nodes, so graphify's JS extractor works here and the failure is `.astro`-specific.

**Root cause is narrower than upstream #2551.** `extract_astro` runs
`_extract_generic(path, _JS_CONFIG)` over the WHOLE file — its own docstring says
this "produces a top-level ERROR node because the template is not valid JS" —
and then regex-rescues imports only. `extract_vue`, 70 lines further down the
same file, masks the non-`<script>` regions and recovers "imports, symbols, and
type refs". The correct strategy is already in-tree and `.astro` does not use it.
This file has no imports at all, so the rescue recovered nothing.

## The issue's own premise was a sample, not the population

#328 argued per-file hashes were right here because these are "a handful of
files in a source we curate, not the 7,603 vendored paths #289 was about".

Census over all 71 clones, using the same `extract_json` graphify uses:
**2,675 zero-node JSON files across 55 of 71 sources** — pkl 679, orjson 396,
datamodel-code-generator 291, agents 289, agnix 176, ruff 129. Two dispositions,
not one: 2,199 "data json (not a config/manifest)" and 476 "data json
(non-object root)", the second never registered at all.

Control-armed against graphify's own warnings: 10x-Team census 4 / warned 4,
Attacca 8 / 8, GitNexus 89 / 79 — exact on small sources, ~11% over on large
ones, so it is an upper bound and the order of magnitude is not in doubt.

The premise was TRUE for the source it was written on and FALSE for the corpus.
That is the whole lesson: the build failed on the first source, so the issue was
written from a sample of one, and the remedy it specified scales to exactly that
sample.


## Outcome

- Signal: corrected
- Correction: A ticket written from the first failure is written from a sample of one, and its
proposed remedy is sized to that sample. #328 stated the per-file hash registry
was right "here" — a handful of files in a curated source, not #289's 7,603
vendored paths. It was measured this round at **2,675 zero-node JSON files
across 55 of 71 sources**. The build had only ever reached source 2 of 71, so
nobody had seen past it; the argument was sound and its population was wrong.

Two habits follow, and the first is the cheap one:

1. **Before implementing a ticket's specified remedy, measure the population it
   is sized for.** Here it cost one census script and answered in seconds what
   two build rounds could not.

2. **A gate can be a check that could only fail, and it looks exactly like a
   gate that never fired.** The approver reconstructed graphify's warning by
   joining every reviewed name while graphify truncates the list at five, so any
   source with six or more registered files was unapprovable by construction.
   Nothing reported this: it presented as "the files are not registered yet",
   which is precisely what the issue concluded. `probes-need-a-control-arm.md`
   rule 2 says to arm the PASS direction of a gate; that had never been done
   here because the gate had never passed, and its one passing case (4 files)
   sat under the truncation limit and so could not exhibit the bug.
