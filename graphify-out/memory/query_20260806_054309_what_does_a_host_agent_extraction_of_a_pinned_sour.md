---
type: "query"
date: "2026-08-06T05:43:09.129710+00:00"
question: "What does a host-agent extraction of a pinned source's own docs cost per file, and what can silently destroy another source's nodes?"
contributor: "graphify"
outcome: "useful"
---

# Q: What does a host-agent extraction of a pinned source's own docs cost per file, and what can silently destroy another source's nodes?

## Answer

Measured 2026-08-06 on 16 files of graphify's own docs: 1,810,589 subagent tokens
over 675s = ~113k tokens/file, about 20% BELOW the ~141k/file figure issue #118
had been carrying unverified. Condition: this corpus, this prompt shape, files
spanning 0.4 KB to 57 KB, one date — a planning average, not a constant.

Yield: 43 nodes over 8 files became 796 nodes / 1,099 edges / 45 hyperedges over
16. README went 8 -> 165; graphify's shipped operational runbook (skill.md, 41 KB)
went 0 -> 76.

The file COUNT was mostly duplication and the enumeration is what made a curated
set defensible: of 371 markdown files in the pinned clone, 33 are README
translations, ~16 are per-platform skill variants (five byte-identical), and ~165
are the skillgen fragments that assemble them. Roughly 15 distinct English
documents exist.

THE DEFECT THIS ROUND FOUND, and no gate can: kb-extract derives source_file as
the CLONE-RELATIVE path, and for a file at the root of a clone that IS the bare
basename. Six identities were global names, so graphify's CHANGELOG.md superseded
72 nodes of mattpocock/skills' CHANGELOG.md. Every gate was green - the chunk
validated, the cold review passed it as data, nothing compares across chunks. The
only detector was merge-line arithmetic: +796 printed while the total rose 681.
Fix: qualify every source_file with the source name, rewritten textually with an
assertion that every other byte is identical. Re-measured after: 336461 + 796 =
337257 exactly, zero replaced.

## Outcome

- Signal: useful