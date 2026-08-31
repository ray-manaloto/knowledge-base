---
type: "query"
date: "2026-08-31T21:00:12.159663+00:00"
question: "Why did kb-build keep failing after two fixes, and what is the durable fix?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why did kb-build keep failing after two fixes, and what is the durable fix?

## Answer

# kb-build was a CLASS of 11, not an open-ended queue — and the gate found a 12th

`kb-build` failed three times, once per build, always the same mechanism: a package
manifest that extracts to ZERO nodes emits a graphify warning, and unless that warning
is pre-approved in one of `graph.py`'s four `_EXPECTED_*` registries or the source is
excluded by a manifest `build` key, `graphify_health` fails closed.

Two instances were fixed in prior rounds. The third (`biome`) was written up as an
open-ended queue — "34 Cargo.toml exist, the rest are unaudited" — with the explicit
advice DO NOT fix biome and re-run, because each ~55-minute build buys one more name.

**Running that audit costs about thirty seconds and closes the set.** Parsed with
`tomllib`, not grepped: 475 `Cargo.toml` under `sources/`, 462 parse with `[package]`,
**11 bare `[workspace]`**, 2 raise `TOMLDecodeError` (a third class entirely). Of the 11:
4 excluded by a `build` key, 6 registered, **1 unguarded — `biome`**.

The discriminator is NOT the file's shape. `uv`'s `Cargo.toml` is just as bare as
`biome`'s; what separates them is registration. That was found by a control arm FAILING —
`uv` was chosen as the "has a real `[package]`" control and turned out not to.

**The gate built from this found a 12th case on its first run**: `uv:crates/uv/pyproject.toml`,
zero nodes, no error, unregistered — invisible to a `Cargo.toml`-only census.

Shipped as PR #639: `kb-manifest-audit`, two tiers split by evidence availability. Tier 1
compares each registry entry's new `pinned_commit` against its manifest's current `commit`
— offline, always runs, catches the `b2d51b53` class (six manifests bumped, `graph.py`
touched zero times) with no clone present. Tier 2 does content hashes and the coverage
scan across BOTH extraction routes, and SKIPs per source when the clone is absent. SKIP
never blocks; the three-state outcome travels in a sidecar because the exit code cannot
carry it.


## Outcome

- Signal: useful