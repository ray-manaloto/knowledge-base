---
type: "query"
date: "2026-08-31T21:00:17.600935+00:00"
question: "Was the kb-build zero-node failure an open-ended queue of unaudited sources?"
contributor: "graphify"
outcome: "corrected"
correction: "# I measured a proxy for the thing FIVE times in one workstream\n\nEvery instance read exactly like evidence, and each was caught only by a second probe of\nthe same fact by a different route:\n\n1. `find … | head -6` reported as \"six sources carry a Cargo.toml\". Real: 34+.\n2. Three `_*_MANIFEST_PATHS` constants reported as \"the registry\". Real: 4 registries.\n3. `grep -c '[package]'` reported as the census — on a page whose own argument is to use\n   the real predicate. It counted 2 unparseable files as class 1. Real split 462/11/2.\n4. A text parse bounded at the first `\\n)\\n` gave \"13 registry entries\". Runtime: **31**,\n   and the bound hid that there are FOUR registries, not one — 40 entries, 14 sources.\n5. `grep -c 'pinned_commit'` read as \"22 of 40 sites populated\". `grep -c` counts LINES.\n   Runtime: **40/40**. I nearly reported a lane's correct work as incomplete.\n\n**The rule that actually caught these**: ask the RUNTIME, not the text. Instances 4 and 5\nwere both settled by `uv run python -c \"from kb_setup...; print(len(R))\"` in seconds.\n\n**And the control arm is worth more when it FAILS.** Choosing `uv` as a control for\n\"has a real `[package]`\" was wrong — and that wrongness is what revealed the real\ndiscriminator was registration, not file shape. A control that fails informatively beats\none that passes.\n\n**Corollary, learned the same round:** a claim's blast radius is not its wording.\nFraming `uv:crates/uv/pyproject.toml` as \"register it vs exclude it\" implied two\ncomparable costs. `build` is a field of `Manifest` — per-SOURCE — so the smallest\n\"exclude\" was dropping all 638 `.rs` files of `astral-sh/uv` to avoid one registry row\nfor a 3-line test fixture. There was no trade-off; there was a wrong framing.\n"
---

# Q: Was the kb-build zero-node failure an open-ended queue of unaudited sources?

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

- Signal: corrected
- Correction: # I measured a proxy for the thing FIVE times in one workstream

Every instance read exactly like evidence, and each was caught only by a second probe of
the same fact by a different route:

1. `find … | head -6` reported as "six sources carry a Cargo.toml". Real: 34+.
2. Three `_*_MANIFEST_PATHS` constants reported as "the registry". Real: 4 registries.
3. `grep -c '[package]'` reported as the census — on a page whose own argument is to use
   the real predicate. It counted 2 unparseable files as class 1. Real split 462/11/2.
4. A text parse bounded at the first `\n)\n` gave "13 registry entries". Runtime: **31**,
   and the bound hid that there are FOUR registries, not one — 40 entries, 14 sources.
5. `grep -c 'pinned_commit'` read as "22 of 40 sites populated". `grep -c` counts LINES.
   Runtime: **40/40**. I nearly reported a lane's correct work as incomplete.

**The rule that actually caught these**: ask the RUNTIME, not the text. Instances 4 and 5
were both settled by `uv run python -c "from kb_setup...; print(len(R))"` in seconds.

**And the control arm is worth more when it FAILS.** Choosing `uv` as a control for
"has a real `[package]`" was wrong — and that wrongness is what revealed the real
discriminator was registration, not file shape. A control that fails informatively beats
one that passes.

**Corollary, learned the same round:** a claim's blast radius is not its wording.
Framing `uv:crates/uv/pyproject.toml` as "register it vs exclude it" implied two
comparable costs. `build` is a field of `Manifest` — per-SOURCE — so the smallest
"exclude" was dropping all 638 `.rs` files of `astral-sh/uv` to avoid one registry row
for a 3-line test fixture. There was no trade-off; there was a wrong framing.
