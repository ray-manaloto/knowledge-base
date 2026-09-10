---
type: "query"
date: "2026-09-10T04:35:49.890794+00:00"
question: "What does a currency dependency bump actually cost, and which failures does no metadata check predict?"
contributor: "graphify"
outcome: "useful"
---

# Q: What does a currency dependency bump actually cost, and which failures does no metadata check predict?

## Answer

# Round kb-20260909.007 — what a currency bump actually costs, measured by doing one

The round bumped codex 0.153.4 -> 0.154.0 and mise 2026.9.0 -> 2026.9.4 entirely
by hand, then had two codex lanes review the process. The findings are about the
PROCESS, not the versions.

## A pin bump is not metadata-only

`kb-build` failed twice before it passed, and neither failure was predicted by
any pin, hash or registry check:

- flipping codex from `build = skip` to included exposed
  `third_party/voice/opus-toolchain.cmake` — a CMake toolchain file graphify has
  no extractor for;
- resyncing mise v2026.9.0 -> v2026.9.4 introduced TWO files that did not exist
  at the old pin (`crates/mise-shim/native-shim-marker`, a 136 KB
  `SpaceGrotesk.ttf`), turning a passing build into a failing one with nothing
  wrong with mise and no manifest error.

Control-armed, because a shallow clone reports a missing OBJECT identically to a
missing FILE: the old commit resolves locally and three known-present files
confirm at it.

Consequence for the upgrade-command design: the 17 metadata rows and the 11
ordered steps all model DECLARATIONS. Only a real extraction finds this class,
so `kb-build` belongs INSIDE the command's verification, not after it.

## The engine already prevents the mistake the hand path makes

`manifest.resolve_tag` returns the PEELED commit for an annotated tag — its
docstring says "never the tag object `write_pin` used to record (#500)". The
hand path recorded a tag object for codex the same evening. Armed live on mise:
the engine returned `794948606e02`, a hand `ls-remote` returned `d0c2938993c5`.

`sources/mise.manifest` has documented this trap as #395 since 2026-08-19.
`sources/codex.manifest` carries no such warning and was walked into it. A
warning written into one file does not protect the next file.

## Declaring provenance REMOVES automation eligibility

`tool_sync.py:220-221` refuses every manifest-bearing tool. Adding `manifest =`
rows so three tools would finally be checked took `kb-tool-sync`'s eligible set
from 5 of 20 to 2 of 20; lifting that one refusal would give 12 of 20. It is the
third time the coupling has moved that census (antigravity-cli, 2026-09-03).

An astra advisor named the real defect: sync eligibility uses the ABSENCE of a
source relationship as a proxy for whether the required reconciliation is
implemented. And a cardinality finding no naming scheme fixes — `[tool.codex]`
can name ONE manifest, while 8 companion sources of tracked tools are checked by
nothing.

## A closed set typed as `str` fails silently

`ExpectedUnclassifiedFile.classification` was a bare `str` and its consumer
dispatched with two `if`s and no else, so an unrecognised value was silently
dropped — the entry looked reviewed and absorbed nothing. Two such entries cost
two full builds. The struct already set `forbid_unknown_fields`, so a typo'd
FIELD NAME raised while a typo'd VALUE said nothing.


## Outcome

- Signal: useful