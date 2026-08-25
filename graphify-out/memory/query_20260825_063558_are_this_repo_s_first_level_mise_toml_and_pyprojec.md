---
type: "query"
date: "2026-08-25T06:35:58.902184+00:00"
question: "Are this repo's first-level mise.toml and pyproject.toml dependencies up to date, their sources synced, and AST-extracted?"
contributor: "graphify"
outcome: "useful"
---

# Q: Are this repo's first-level mise.toml and pyproject.toml dependencies up to date, their sources synced, and AST-extracted?

## Answer

# The dependency sweep round — 2026-08-25

Ray's option-4 directive: every first-level mise.toml / pyproject.toml dependency
up to date, its source synced, and graphify's AST step run over all of them.

## What the round actually found

The sweep's premises were mostly wrong, and finding that out was most of the value.

- The handoff's `_authorized_source_manifest` symbol DOES NOT EXIST in kb_setup.
  Control-armed: `authorized` returns 10 hits elsewhere, so the probe discriminates.
- graphify was NOT drifted. Manifest, clone and installed package all agree at
  0.9.49 / cdfb11c0.
- The recorded kb-build failure's stated cause NO LONGER REPRODUCES. Armed both
  directions against `graphify_health._unaccounted_stderr`: the exact recorded line
  now filters to empty, while a real WARNING and a trailing-text variant survive.
- The three "drifts" were manifest-side only; mise.toml already pinned the newer
  pkl / typos / codex. The real upstream drift was five OTHER tools.
- Python first-level deps were already current: all 8 available updates transitive.

## What shipped

- 8 new source manifests (76 -> 84), each pinned to the version we RUN.
- The ffmpeg manifest corrected: `n9.0.1` is an ANNOTATED tag and the first commit
  stored the TAG OBJECT. Caught within the hour because a release-note lane
  independently flagged `gh api` as the required resolution route.
- antigravity-cli 1.1.20 and ty 0.0.74, both verified.
- docs/direction/2026-08-25-ray-directives.md — the primary source for the ruling
  that relaxes do-not.md #4.
- Five tickets (#483-#487) and a correction on #417.

## The rulings

- claude-cli AND openai-cli are both permitted graphify agents. do-not.md #4's
  phrasing goes. clean_env() does NOT change, and keeping the OPENAI_API_KEY strip
  is now load-bearing for a NEW reason: upstream's own comment says the CLI route
  exists to stay on OAuth, and reverting it can send the work through a metered key.
- codex flips skip -> include, manifest advanced FIRST so the registered hash
  describes bytes we actually build.
- ffmpeg is `include`: measure before excluding.
- The dependency table is a dependency x pipeline-step MATRIX, shipping v1 with
  honest UNKNOWNs rather than inventing green cells.


## Outcome

- Signal: useful