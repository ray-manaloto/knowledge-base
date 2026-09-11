# Currency run — datamodel-code-generator — 2026-09-11T07:35:08+00:00

**Verdict:** datamodel-code-generator 0.76.0 → 0.79.0: 2 question(s) for review

Related: [[tool-currency-log]] · [[datamodel-code-generator]]

## Step 1 — in sync?

Pinned `0.76.0` · resolved `0.76.0`

| check | status | detail |
|---|---|---|
| version | ok | datamodel-codegen on PATH is the reviewed 0.76.0 (<repo>/.venv/bin/datamodel-codegen) |
| manifest | skip | sources/datamodel-code-generator.manifest pins 0.76.0; the local clone could not resolve that ref (no clone, no `.git`, no such tag, or git unavailable), so `commit` was NOT checked — run `mise run kb-build` |

## Steps 2-3 — upstream

- Latest (pypi): `0.79.0`
- GitHub release: `0.79.0`
- Reachable: yes

### Release notes

```text
## 0.76.1

## Highlights

* Parser source loading, run state, output-model capabilities, field-name policies, and input-model transport have been separated to clarify internal ownership. Compatibility imports and the public field-name resolver mapping are retained. (#3818, #3820, #3821, #3822, #3823, #3824, #3825)
* Root-model collapsing tracks references incrementally, and the built-in formatter skips unnecessary string normalization. These optimizations retain the existing generated-output behavior. (#3826, #3827, #3828)
* `x-enum-descriptions` now accepts null entries, allowing schemas with missing individual enum descriptions to generate successfully. (#3835)

## What's Changed

* Optimize collapsed root model replacement by @koxudaxi in https://github.com/datamodel-code-generator/datamodel-code-generator/pull/3826
* Track collapsed root model references incrementally by @koxudaxi in https://github.com/datamodel-code-generator/datamodel-code-generator/pull/3827
* Skip unnecessary built-in string normalization by @koxudaxi in https://github.com/datamodel-code-generator/datamodel-code-generator/pull/3828

… (truncated)
```

### Features to consider adopting

_Advisory — these did not block the bump. Skim for a new capability worth a config change._

- Parser source loading, run state, output-model capabilities, field-name policies, and input-model transport have been separated to clarify internal ownership. Compatibility imports and the public field-name resolver mapping are retained. (#3818, #3820, #3821, #3822, #3823, #3824, #3825)
- Root-model collapsing tracks references incrementally, and the built-in formatter skips unnecessary string normalization. These optimizations retain the existing generated-output behavior. (#3826, #3827, #3828)
- `x-enum-descriptions` now accepts null entries, allowing schemas with missing individual enum descriptions to generate successfully. (#3835)
- Empty allOf enum intersections now raise an error - When merging allOf subschemas whose enum values do not overlap, generation now raises a `SchemaParseError` and aborts instead of producing a widened or concatenated enum, so schemas that previously generated successfully can now fail (#3961)
- Embedded schema resources now resolve in-document first - References to schemas declared with a nested `$id` are now resolved within the containing document before any file or HTTP lookup, and resource-scoped anchors and JSON pointers are honored, so schemas that previously resolved such references to physical files or remote URLs (including cases where an embedded resource shares a physical filename) can now produce different generated models and different fetch behavior (#3977)

_**This list may be incomplete.** At least one release in this span uses a changelog format the scan could not read, so features announced there are missing from the list above — read those notes by hand._

## Step 4 — tracked issues and watch items

| item | state | updated | comments | moved? | reviewed |
|---|---|---|---|---|---|
| local:codegen-version-literal-is-load-bearing-in-a-test | local | — | 0 | no | — |
| local:codegen-tags-carry-no-v-prefix | local | — | 0 | no | — |

## Step 5 — decision

Gates passed:

- ✅ versions are readable and move forward
- ✅ latest version has a readable GitHub release
- ✅ extras unchanged
- ✅ step 1 currently green

### Gate: no breaking/removal/deprecation marker

**The release notes flag a breaking change. Adopt it anyway?**

- Detail: Markers found: breaking.
- Recommended: Read the notes; plan a rebuild and a re-verify before adopting.
- **Answer:** _not yet answered_

### Gate: no tracked issue moved

**2 local watch item(s) must be re-probed against this release. Done?**

- Detail: local:codegen-version-literal-is-load-bearing-in-a-test: `tests/test_skillopt_contract.py` copies the REAL `pyproject.toml` into a tmp dir and `.replace()`s the exact string `codegen = ["datamodel-code-generator==<version>"]`. The bump to 0.74.0 made that replace a silent no-op and the assertion failed — loudly, which is the only good part. The repair is more fragile than it looks, and that is the finding: the literal also depends on the ARRAY BEING ON ONE LINE. `uv add --group codegen` writes it multi-line; `mise run fmt` (taplo) collapses it back. So the test passes today because two independent tools happen to agree on formatting, not because anything asserts it. A taplo config change would break it with no bump at all. The durable fix is for that test to construct its own fixture rather than string-replace a copy of a real config file — a test must own its own environment. Until then: bump the pin, update BOTH literals, and run `mise run fmt` before `pytest`. Re-probe on each bump by running `pytest tests/test_skillopt_contract.py` BEFORE assuming the pin change is complete.; local:codegen-tags-carry-no-v-prefix: Tags here are bare (`0.74.0`), not `v0.74.0`. A resolver that tries only `v<x>` finds nothing and an apply aborts rather than mispinning — the same class as `[tool.codex]`'s `rust-v<version>`, in the opposite direction. Stated so that abort reads as a known shape rather than a bug.
- Recommended: Re-probe each against the new version, then record it: `kb-setup currency watch-reviewed --tool <name> --ref <ref> --version <ver>` — an untested local finding is folklore, not a finding, and this gate cannot see a hand-written currency.toml note.
- **Answer:** _not yet answered_

## Step 6 — process note

This page is the immutable record of ONE run — a later run writes its own new
page rather than rewriting this one. Annotate it freely with review notes;
nothing here is regenerated.
