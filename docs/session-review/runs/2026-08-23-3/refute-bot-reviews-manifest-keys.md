# Refutation attempt — "manifest.py validates enum VALUES but not field NAMES"

VERDICT: **NOT REFUTED** (claim stands, confirmed empirically).

## Probe (could return either answer)

Three manifests in the scratchpad, loaded through `kb_setup.manifest.load`:

- `badvalue.manifest` — `build = skpi` (bad VALUE)   -> expected RAISE
- `typokey.manifest`  — `buld = skip`  (typo'd NAME) -> ?
- `typoscope.manifest`— `scoep = study`(typo'd NAME) -> ?

```
uv run python - "$SP/src" <<'PY'  # loops load() over the three files
```

Output, verbatim:

```
RAISE badvalue.manifest: ValueError: .../badvalue.manifest: build = 'skpi' is not one of ['include', 'skip'] — an unrecognised value would otherwise fall through to the default
OK   typokey.manifest: build='include' scope='corpus' kind='code' skip_reason=''
OK   typoscope.manifest: build='include' scope='corpus' kind='code' skip_reason=''
```

**Control arm**: the same probe, same command shape, on a bad enum VALUE raises.
So the probe discriminates — it is not "everything loads OK".

## Source anchors (re-derived, the finding's 61-118 is accurate)

- `python/src/kb_setup/manifest.py:61` `_parse` — accumulates EVERY `k = v` line
  into a dict, no key filter.
- `:81` `_ENUMS` — kind/scope/build value sets.
- `:88-118` `load()` — checks (a) required {url,ref,commit} present, (b) enum
  VALUES, (c) `build = skip` implies non-empty `skip_reason`. **No key-set check.**
  Unrecognised keys in `f` are simply never read.

## Second route (corroboration, not the same probe)

`cat sources/*.manifest | grep -o '^[a-z_]* *=' | sort | uniq -c`:

```
  73 url =      73 ref =      73 kind =      73 commit =
  37 added =    13 scope =     5 skip_reason =   5 build =
```

`added` is **not a field of the `Manifest` dataclass** (`sources/graphify.manifest`
ends `added = 2026-07-21`, and `manifest.add()` at :255-283 never writes it). So
an unmodelled key is silently dropped in 37 committed files today — the
permissive behaviour is live, and any strict key check must allowlist `added`.

## Gate search (all negative, each control-armed)

- `grep -n '^\s*\["' hk.pkl` -> 24 steps, none touches `sources/*.manifest`
  (control: the same grep lists `no_lint_skip`, `skill_lint`, which do exist).
- `grep -rn "unknown field" python/src/` -> 1 hit, a COMMENT in
  `graphify_semantic_corpus.py:545` about a msgspec struct, not manifests.
  `SourceGroupValidationError` lives only in `source_groups.py` and validates a
  source-group registry, not `*.manifest`.
- `ls tests/ | grep -i manifest` -> `test_manifest_add.py`,
  `test_manifest_build_skip.py`; neither greps for unknown/typo/misspell.
- The repo DOES do key-name validation elsewhere — `arms.py:479,515`
  (`unknown key(s)`) — which is the control proving this repo can and does
  express the check, and that my grep for it returns hits when present.

## Contradiction check against the other live findings

None contradicts. #30 (`manifest.add()` writes an unvalidated `kind`) is the
same file and consistent — confirmed at `manifest.py:275-283`: `add()` writes
`kind = {source.kind}` with no `_ENUMS['kind']` check. #32 is orthogonal
(chunk-file collision validation, not manifest keys).

## Only real caveat (a scope narrowing, not a refutation)

The doc-comment at :72-79 claims closure for VALUES only; it does not claim to
cover names. The finding says so. Its last line — "A field whose typo is
indistinguishable from its default is not a setting" — is the general principle,
and a typo'd KEY is exactly that case left open.

## GitHub repos touched

_None._
