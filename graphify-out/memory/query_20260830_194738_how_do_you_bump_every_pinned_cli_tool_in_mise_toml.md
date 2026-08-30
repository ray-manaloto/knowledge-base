---
type: "query"
date: "2026-08-30T19:47:38.063271+00:00"
question: "How do you bump every pinned CLI tool in mise.toml to latest without leaving an artifact behind, and what does the gate bundle not check?"
contributor: "graphify"
outcome: "useful"
---

# Q: How do you bump every pinned CLI tool in mise.toml to latest without leaving an artifact behind, and what does the gate bundle not check?

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

- Signal: useful