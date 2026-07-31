---
type: "query"
date: "2026-07-31T23:29:04.181561+00:00"
question: "Can this repo tell, unprompted, that its graph no longer matches its committed inputs?"
contributor: "graphify"
outcome: "useful"
---

# Q: Can this repo tell, unprompted, that its graph no longer matches its committed inputs?

## Answer

Yes, since the Fluent round: currency.toml declares 'inputs' globs (sources/*.manifest, sources/extractions/*.json), kb-build digests them with sha256 BEFORE reading any of them and records the map in .currency-stamp.json, and currency.staleness compares them on every SessionStart under its own [graph] header. Four states, kept distinct: never-built (absence of a build short-circuits BEFORE any compare, so a fresh clone is not told its corpus went stale), not-verifiable (unreadable stamp, or one predating input fingerprinting), changed (named per path), ok (silent). Outputs KEEP size:mtime_ns (341MB vs the inputs' 2.4MB); inputs get sha256 because a stat fires on git checkout --, a branch round-trip and a stash+pop on byte-identical files. Proved live: a git-restored manifest had an mtime 60s AFTER the build and the detector stayed silent.

## Outcome

- Signal: useful