---
type: "query"
date: "2026-09-10T04:35:54.287892+00:00"
question: "Is a line-count delta evidence that a particular file:line citation went stale?"
contributor: "graphify"
outcome: "corrected"
correction: "A control arm proves a probe discriminates for the question THAT PROBE ASKS, and\na probe can be bounded in ways that do not look like bounds.\n\nFive probes were discarded this round before any answer was believed:\n\n1. `gh api compare` caps `.files` at 300 and returned exactly 300 — its silence\n   about four files was a DISPLAY bound, not evidence.\n2. Grepping `exec/src/cli.rs` for CLI flags could not discriminate: `--sandbox`\n   scored 1 there and the known-removed `--full-auto` scored 0. Wrong file.\n3. Grepping the UNDERSCORE identifier `dangerously_bypass_hook_trust` reads 0 in\n   both versions, because the file carries only the hyphenated clap attribute.\n   A token spelling is a bound.\n4. Counting `ref_bindings` in currency.toml returned 0 for every tool; the real\n   key is `ref_binding`, singular. Same class, in my own code.\n5. Inferring that `do-not.md` #12's line citations went stale because the file\n   grew 207 -> 220 lines. The growth was BELOW the cited range, so lines 44-59\n   never moved. A line-count delta says something moved, never that a PARTICULAR\n   span did — and that false claim reached a commit message before a cold lane\n   refuted it.\n\nThe habit that caught each: run the same probe shape against a case whose answer\nis known. `--full-auto` as a known-removed control is what made the surviving\nflags mean something.\n"
---

# Q: Is a line-count delta evidence that a particular file:line citation went stale?

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

- Signal: corrected
- Correction: A control arm proves a probe discriminates for the question THAT PROBE ASKS, and
a probe can be bounded in ways that do not look like bounds.

Five probes were discarded this round before any answer was believed:

1. `gh api compare` caps `.files` at 300 and returned exactly 300 — its silence
   about four files was a DISPLAY bound, not evidence.
2. Grepping `exec/src/cli.rs` for CLI flags could not discriminate: `--sandbox`
   scored 1 there and the known-removed `--full-auto` scored 0. Wrong file.
3. Grepping the UNDERSCORE identifier `dangerously_bypass_hook_trust` reads 0 in
   both versions, because the file carries only the hyphenated clap attribute.
   A token spelling is a bound.
4. Counting `ref_bindings` in currency.toml returned 0 for every tool; the real
   key is `ref_binding`, singular. Same class, in my own code.
5. Inferring that `do-not.md` #12's line citations went stale because the file
   grew 207 -> 220 lines. The growth was BELOW the cited range, so lines 44-59
   never moved. A line-count delta says something moved, never that a PARTICULAR
   span did — and that false claim reached a commit message before a cold lane
   refuted it.

The habit that caught each: run the same probe shape against a case whose answer
is known. `--full-auto` as a known-removed control is what made the surviving
flags mean something.
