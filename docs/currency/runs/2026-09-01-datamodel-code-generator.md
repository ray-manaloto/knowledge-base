# Currency run — datamodel-code-generator — 2026-09-01T18:17:06+00:00

**Verdict:** datamodel-code-generator 0.75.1 → 0.76.0: 3 question(s) for review

Related: [[tool-currency-log]] · [[datamodel-code-generator]]

## Step 1 — in sync?

Pinned `0.75.1` · resolved `0.75.1`

| check | status | detail |
|---|---|---|
| version | ok | datamodel-codegen on PATH is the reviewed 0.75.1 (<repo>/.venv/bin/datamodel-codegen) |
| manifest | skip | sources/datamodel-code-generator.manifest pins 0.75.1; the local clone could not resolve that ref (no clone, no `.git`, no such tag, or git unavailable), so `commit` was NOT checked — run `mise run kb-build` |

## Steps 2-3 — upstream

- Latest (pypi): `0.76.0`
- GitHub release: `0.76.0`
- Reachable: yes

### Release notes

````text
## 0.76.0

## Breaking Changes


### API/CLI Changes
* `--list-deprecations` output format changed - The deprecations listing now includes a new `Status` column and renames the `Warning since` column header to `Since` across all output formats (`table`, `json`, and `markdown`). Table rows also no longer emit trailing whitespace padding, so column widths and spacing differ. Scripts or tooling that parse the `--list-deprecations` output may need to be updated. The JSON output additionally gains a `status` field per entry (the existing `warning_since` field is retained). (#3810)
```text
# Before
ID   Kind   Target   Warning since   Removal   Replacement

# After
ID   Status   Kind   Target   Since   Removal   Replacement
```

## What's Changed
* Update CHANGELOG for 0.75.1 by @dcg-generated-docs[bot] in https://github.com/koxudaxi/datamodel-code-generator/pull/3789
* Update release benchmark data by @dcg-generated-docs[bot] in https://github.com/koxudaxi/datamodel-code-generator/pull/3790
* Cache local reference file resolution by @koxudaxi in https://github.com/koxudaxi/datamodel-code-generator/pull/3799

… (truncated)
````

### Features to consider adopting

_**Could not tell.** The release notes are non-empty but match no changelog format this scan understands (no `Added`/`Highlights` section, no `feat:` prefixes, no adoption phrases), so this is **not** a report of zero features — read the notes by hand._

## Step 4 — tracked issues and watch items

| item | state | updated | comments | moved? | reviewed |
|---|---|---|---|---|---|
| local:codegen-version-literal-is-load-bearing-in-a-test | local | — | 0 | no | — |
| local:codegen-tags-carry-no-v-prefix | local | — | 0 | no | — |

## Step 5 — decision

Gates passed:

- ✅ latest version has a readable GitHub release
- ✅ extras unchanged
- ✅ step 1 currently green

### Gate: patch-level bump

**0.75.1 → 0.76.0 is not a patch bump. Adopt it?**

- Detail: Only the patch component may move unattended. Pre-1.0 projects use the MINOR slot as their breaking channel, so 0.9.x → 0.10.0 stops here.
- Recommended: Read the release notes, then decide.
- **Answer:** _not yet answered_

### Gate: no breaking/removal/deprecation marker

**The release notes flag a breaking change. Adopt it anyway?**

- Detail: Markers found: breaking, deprecation.
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
