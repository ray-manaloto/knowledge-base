# codex lane — does automation already exist for graphify pin DERIVED values?

**Codex banner, verbatim from this lane's own run:** `model: gpt-5.6-sol` /
`sandbox: read-only` (OpenAI Codex v0.153.4, `reasoning effort: xhigh`,
`approval: never`, session `01a08817-581b-7682-a9a3-90fe5daf9235`). The lane
ran; the verdict below is a cross-family read, not a Claude one. Full stdout:
`/tmp/kb-codex-advisor-stdout.log`; verdict file: `/tmp/kb-codex-advisor-verdict.md`.

Commit under review: `5cb4b74e` on `feat/728-kb-fork-rebase`.

---

## VERDICT

**No such path exists. One must be built** — and the right build is NOT a new
standalone deriver, it is repairing `graphify_baseline.py` so its own #373
diagnostic can be reached, then letting a future `kb_setup.fork_rebase` call it.

Codex, first line verbatim:

> VERDICT: No—the supplied evidence shows no existing `skill → mise task → Python
> module` path that advances the derived Graphify baseline values; one must be built.

---

## Q1 — Does any function WRITE `source_tree` / `catalog_sha256` / `source_manifest_sha256`?

**NOT FOUND.** No writer exists anywhere in `python/src/kb_setup/`.

Negative arm:

```
grep -rn "source_tree=\|catalog_sha256=\|source_manifest_sha256=" \
  python/src/kb_setup/ --include='*.py' | grep -v graphify_baseline.py
```
-> **empty**.

**Control arm proving the probe discriminates:** the same grep shape finds a real
pin writer, `manifest.write_pin` at `python/src/kb_setup/manifest.py:418`. So the
search CAN find a writer; it found none for these three fields.

Inside `graphify_baseline.py` every occurrence is one of three kinds, none a writer:

| kind | lines |
|---|---|
| frozen constant | `:304` `source_tree`, `:305` `catalog_sha256`, `:306` `source_manifest_sha256`, `:343` `detected_count=471`, `:377` `extracted_count=463` |
| READ of `catalog.source_tree` into a candidate struct | `:1688 :1751 :1756 :1776 :1801 :1823 :1885 :1912 :1930 :1959` |
| validator / comparison | `:649 :692 :712 :1068 :1081 :1221-1226 :1991 :2023` |

`sources/graphify.dispositions.json` is referenced at exactly one place —
`load_disposition_catalog`, `graphify_baseline.py:636` — and it is a **read**.
Nothing in the repo writes that file back.

`python/src/kb_setup/fork_rebase.py` does not exist; no `kb-fork-rebase` task is
declared in `mise.toml`. (It is tracked as OWED work on #728, i.e. planned, unbuilt.)

## Q2 — mise tasks touching graphify pins / manifests / baselines / currency

| task | run | can it do this update? |
|---|---|---|
| `kb-graphify-baseline` (`mise.toml:808-810`) | `uv run kb-setup graphify-baseline` | **No** — `build\|controls\|verify` only; it is the thing that FAILS |
| `kb-graphify-contract` (`:804-806`) | `uv run kb-setup graphify-contract` | No — CLI/SDK signature agreement |
| `kb-graphify-native-extract` (`:812`) | — | No — extraction, not identity |
| `kb-update` (`:749-753`) | `uv run kb-setup update` | No — advances a source to upstream **HEAD** and re-extracts; moves `sources/*.manifest`, not the catalog `source_tree` or any authority constant |
| `kb-manifest-add` (`:1416`) | — | No — pins a NEW source |
| `kb-manifest-audit` (`:1054`) | — | No — a read-only gate |
| `kb-currency-check` (`:1349`) | — | No — offline drift report |
| `kb-currency` (`:1356`) | — | No, see below |

`currency/apply.py` is the closest thing and it stops short: `set_pin_version` (`:75`)
edits the mise.toml pin line, `apply` (`:151`) resolves a tag (`:233`) and calls
`mf.write_pin(manifest_obj, ref=…, commit=…)` (`:240`), then writes mise.toml (`:241`).
Its own docstring at `:14` scopes it: *"G8 — committable parts only. The pin and the
manifest are edited"*. **`ref` and `commit` only** — the three derived values and the
two counts are outside its surface entirely.

**Answer: no declared task can perform this update.**

## Q3 — What bytes is `_ACCEPTED_AUTHORITY.source_manifest_sha256` a digest OF?

**Neither of the caller's candidates. Both measured comparisons were the wrong bytes.**

It is the sha256 of the **emitted `candidate/source-manifest.json`** — a full
`git ls-tree -rz --full-tree` blob inventory of the materialized graphify source.

Chain, all read this session:

- `_authority_reasons:1217` — `source_manifest = by_name.get("source-manifest.json")`
- `_authority_reasons:1223-1227` — compares `source_manifest.sha256` to the constant
- `build_from_snapshot:1946-1953` — `ArtifactMember.sha256 = hashlib.sha256((candidate / name).read_bytes()).hexdigest()`
- `build_from_snapshot:1942` — `_write_json(candidate / "source-manifest.json", before)`
- `build_from_snapshot:1798-1801` — `before = source_manifest(source, commit=catalog.source_commit, tree=catalog.source_tree)`
- `source_manifest:583-610` — runs `git ls-tree -rz --full-tree` and inventories every blob

So `0b8864166852ab68c0a11090c9500384090f54072d974ec846612f9316519a67`
(= `shasum -a 256 sources/graphify.manifest`, measured this session) is **NOT the
right comparison**. That value is unobtainable without materializing the pinned
source and running the build.

### The same correction applies to `catalog_sha256`, and this one is coupled

`build_from_snapshot:1960` — `catalog_sha256=hashlib.sha256(catalog_raw).hexdigest()`,
where `catalog_raw` is returned by `_write_candidate_inputs:1402`
(`_write_json(candidate / "dispositions.json", catalog)`) and `_write_json:1388-1391`
is `msgspec.json.encode(value) + b"\n"`.

That is the **msgspec re-encoding of the loaded struct**, not the on-disk file.
Measured two-armed this session:

| bytes | sha256 |
|---|---|
| on-disk `sources/graphify.dispositions.json` | `5492544d4470a047b716e8f3267611d53f38b9d8352aae4315487de381e8f54d` |
| `sha256(msgspec.json.encode(load_disposition_catalog(.)) + b"\n")` | `a52e4f6e56dd144ae0a5ad152078e91243399a1ea8653f3855fd89c0d1d383c1` |

They differ, so `5492544d…` is the wrong constant.

**And `a52e4f6e…` is also wrong**, for the reason codex names as the decisive risk:
`DispositionCatalog` CONTAINS `source_tree` (`:66`), so `a52e4f6e…` was computed over
the still-stale catalog. Fixing stale value (1) changes the correct value for (3).
The two are **ordered**, and a hand-derivation done out of order yields a
cryptographically valid hash that is semantically stale — a wrong answer that looks
exactly like a right one.

Codex, verbatim:

> **Decision risk:** `catalog_sha256` is order-dependent. Computing it before
> replacing `source_tree` yields a cryptographically valid but semantically stale
> hash—a failure that looks authoritative and can be silently accepted.

## Q4 — Is there a bootstrap path so `build` can report OBSERVED values?

**CONFIRMED: none exists, and the caller's reading of the #373 defect is correct.**

`baseline_main:2029-2051` accepts exactly `build|controls|verify [PATH]`
(`_MAX_BASELINE_ARGS = 2` at `:242`). No flag, no env var, no alternate entry point.
Control arm on that negative: the same read correctly enumerates the three
subcommands and both arity checks (`:2043`, `:2046`), so it is not a blind read.

The wall is `build_baseline:1990-1993`:

```python
        provenance = graph.materialize_source_snapshot(graphify_manifest, source)
        if (
            provenance.resolved_commit != catalog.source_commit
            or provenance.tree_digest != catalog.source_tree
        ):
            raise ValueError("Graphify source manifest and disposition catalog identity differ")
```

It compares against **`catalog.source_tree`** — stale value (1) — and fires before
`build_from_snapshot` is called at all, therefore before `_verify_candidate` ->
`_authority_reasons`. The #373 diagnostic at `:1211-1270`, headed
`"[graphify-baseline] authority drift — move these in _ACCEPTED_AUTHORITY:"` (`:1264`),
is the ONLY mechanism in the repo that can report the observed values, and it is
**unreachable** while (1) is stale.

The identical guard is duplicated in `certify_baseline_controls:2020-2025`, so
`kb-graphify-baseline -- controls` hits the same wall. There is no second door.

This is a **design defect**, not a missing feature: #373's stated purpose (comment at
`:325-328`) was to turn the next bump into reading one line, and it is defeated by a
guard that runs earlier.

## Does a path exist, or must one be built?

**One must be built.** Codex's recommendation, verbatim:

> **Recommendation:** Choose **(c): repair the baseline design, then let
> `fork_rebase` orchestrate it**.
>
> Add an explicit bootstrap/observe interface to `graphify_baseline.py`, exposed
> through `kb-graphify-baseline`, while preserving the normal build's fail-closed
> guard:
>
> 1. Materialize the pinned commit and derive `source_tree`.
> 2. Substitute that tree into an in-memory catalog.
> 3. Canonically encode that updated catalog and derive `catalog_sha256`.
> 4. Build the candidate and derive `source_manifest_sha256` and both counts.
> 5. Emit one complete acceptance proposal; optionally apply all coupled values
>    atomically through an explicit acceptance command.
>
> This restores #373's intended "read one diagnostic" behavior and keeps derivation
> beside the serialization/build implementation that defines it. A future
> `kb_setup.fork_rebase` module should call this interface, not duplicate its hash
> and inventory logic.

The ordering in steps 1-4 is the whole point: it is the only sequence that respects
the `source_tree` -> `catalog_sha256` coupling.

## What could NOT be verified

Codex's own list, verbatim, plus my additions:

> - The final catalog hash, source-manifest hash, and counts; they require the real
>   materialization/build.
> - Whether the proposed bootstrap reaches every later validation without another guard.
> - The inherited claim that `kb-currency apply` never works for Graphify.
> - Absolute repo-wide absence of an external/generated writer outside the searched
>   Python and mise surfaces.

Mine:

- I did **not** run `mise run kb-graphify-baseline -- build` (instructed not to), so
  the `:1993` failure is read from code, not observed this session.
- `8fae076d…` as the tree of `3c9b930f…` is the caller's measurement, **inherited by
  me, not re-derived**.
- The graph query I ran returned **rc=3 (truncation guard)** — it surfaced
  `_authority_reasons()` at the correct `file:line`, so it discriminated, but it was
  not a complete traversal and no conclusion here rests on it.
- `detected_count` / `extracted_count` will also move (0.9.57 added files upstream);
  I did not measure by how much.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under review; all code read here.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — the forked dependency whose pin moved; referenced via `sources/graphify.manifest`, source not read this session.
- [openai/codex](https://github.com/openai/codex) — the CLI this lane ran on (v0.153.4); no source read.
