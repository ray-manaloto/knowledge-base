---
type: "query"
date: "2026-08-30T19:47:38.391205+00:00"
question: "Does confirming the new binaries are installed verify a version bump?"
contributor: "graphify"
outcome: "corrected"
correction: "The belief was that confirming the new binaries are INSTALLED verifies a version\nbump. It does not, and the gap is structural rather than an oversight.\n\n`mise ls --current` reads `mise.toml`. The currency engine reaches versions\nthrough `mise.toml` via each block's `mise_key`. **Neither reads `mise.lock`**,\nand no gate in the seven-gate bundle reads it either. So a bump can move the\npin, the manifests and the installed binary, leave `mise.lock` holding the old\nper-platform URLs and checksums for every platform this host is not, and produce\n7/7 green.\n\nThe correct verification is a probe that asks the lockfile directly —\n`mise lock --dry-run --json`, which returned all five bumped tools while\n`hk`/`gh`/`python` returned `[]`.\n\nThe generalisable lesson is narrower and sharper than \"run more checks\": **a\nverification can be true, well-chosen for the failure it was chosen against, and\nstill orthogonal to the defect.** \"The binaries are installed\" correctly rules\nout a vacuous green — gates passing against the OLD binaries — which is a real\nfailure mode worth ruling out. It says nothing about whether the artifacts\ndescribing those binaries agree with each other. Asking which failure a check\nrules out is a different question from asking whether the check passed, and only\nthe first one tells you what remains unchecked.\n\nA second, cheaper lesson from the same round: a fix's own prose is where the\nnext defect lands. The rewrite closing one finding dropped two words — \"not\ntouch\" — and inverted an invariant into its opposite (\"this repo still does\n`~/.config/fnox`\"). It passed every gate, because no gate reads English.\n"
---

# Q: Does confirming the new binaries are installed verify a version bump?

## Answer

# Bumping a pinned CLI tool touches more artifacts than the gates read

Measured 2026-08-30 on branch `chore/cli-currency-sweep` (PR #637).

Five patch-level pins were bumped — uv 0.12.5→0.12.7, rumdl 0.2.60→0.2.62,
biome 2.5.10→2.5.11, fnox 1.34.0→1.34.1, npm:ctx7 0.5.8→0.5.9 — plus mise's own
`min_version` 2026.8.10→2026.8.14.

## The procedure that actually works

1. `mise outdated --bump` names the movers; `mise latest <tool>` is the
   independent second route. Control-arm it: `mise latest python` returns the
   pin unchanged while `mise latest uv` does not, so the probe produces both
   answers.
2. Bump `mise.toml` **as text**. Never `mise config set` — it deletes the
   comment block above an existing key, and this repo's pins carry load-bearing
   comments.
3. Advance each `sources/<tool>.manifest` to the matching upstream tag AND that
   tag's DEREFERENCED commit. `gh api repos/<o>/<r>/git/ref/tags/<tag>` returns
   a tag OBJECT for an annotated tag; dereference via `.../git/tags/<sha>` when
   `.object.type` is `tag`. Ref spelling is per-manifest and NOT uniform.
4. **Advance `mise.lock`, scoped**: `mise lock <tool>...`. This is the step that
   gets forgotten and that nothing catches.
5. `mise install` && `mise deps` BEFORE any gate, or the gates test the old
   binaries and pass vacuously.
6. `currency.toml` usually needs NO edit — most tools are `mise_key`-tracked and
   derive the expected version from `mise.toml`. Only five blocks hardcode
   `expected`.

## What only a cold review caught

All seven gates were green over a `mise.lock` still holding the five OLD
versions. `mise ls --current` reads `mise.toml`, not `mise.lock`, and the
currency engine never reads the lockfile at all — so "the new binaries are
installed" was TRUE and orthogonal to the defect. The probe that finds it is
`mise lock --dry-run --json`; control arm, `hk`/`gh`/`python` return `[]`.

## The trap inside the repair

A bare `mise lock` rewrote 2951 lines and re-solved the conda dependency
closure as a side effect: `macos-x64` and `macos-x64-baseline` each fell from 89
pinned packages to 72, and it errored resolving `conda:coreutils` for both
Windows platforms. Scoped to the five tools: 137 insertions, 137 deletions, zero
conda lines. So a universal upgrade command must know each tool's OWN artifact
set — regenerating everything reachable is a platform-coverage regression on
hosts you cannot test.

Filed as #636 (umbrella), #634 (orphaned aqua lock entry), #635 (gates artifact
`dirty` ambiguity).


## Outcome

- Signal: corrected
- Correction: The belief was that confirming the new binaries are INSTALLED verifies a version
bump. It does not, and the gap is structural rather than an oversight.

`mise ls --current` reads `mise.toml`. The currency engine reaches versions
through `mise.toml` via each block's `mise_key`. **Neither reads `mise.lock`**,
and no gate in the seven-gate bundle reads it either. So a bump can move the
pin, the manifests and the installed binary, leave `mise.lock` holding the old
per-platform URLs and checksums for every platform this host is not, and produce
7/7 green.

The correct verification is a probe that asks the lockfile directly —
`mise lock --dry-run --json`, which returned all five bumped tools while
`hk`/`gh`/`python` returned `[]`.

The generalisable lesson is narrower and sharper than "run more checks": **a
verification can be true, well-chosen for the failure it was chosen against, and
still orthogonal to the defect.** "The binaries are installed" correctly rules
out a vacuous green — gates passing against the OLD binaries — which is a real
failure mode worth ruling out. It says nothing about whether the artifacts
describing those binaries agree with each other. Asking which failure a check
rules out is a different question from asking whether the check passed, and only
the first one tells you what remains unchecked.

A second, cheaper lesson from the same round: a fix's own prose is where the
next defect lands. The rewrite closing one finding dropped two words — "not
touch" — and inverted an invariant into its opposite ("this repo still does
`~/.config/fnox`"). It passed every gate, because no gate reads English.
