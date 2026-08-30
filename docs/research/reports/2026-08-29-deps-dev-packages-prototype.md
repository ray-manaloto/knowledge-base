# deps.dev packages protobuf prototype (#575)

Date: 2026-08-29

## Result

The prototype closes the schema-to-payload path without a hand-written response
model or an API key. This repository's pinned `datamodel-code-generator` reads a
committed copy of deps.dev's published API v3 protobuf, resolves its pinned
Google API imports, emits strict msgspec structs, and round-trips a captured real
package response while preserving lowerCamelCase JSON keys.

This is a declared spike. Its review tier is verification-only under the
fable-orchestrator doctrine; no cold cross-family review is required. The diff
does not add the `packages` CLI verb, `AdapterRecord` output, or a transport or
clock seam. Those remain #579 work.

## Acceptance criteria

### AC 1 — Generate models from the published protobuf

Closed. `sources/deps-dev.manifest` pins `google/deps.dev` commit
`dc936a45c6574bb6e6bd5433de8c74e4cdff1276` as a schema-only provenance source
with `build = skip`. The generator input is the committed
`schemas/deps-dev-api-v3.proto`, not an ignored source checkout. Its imports are
backed by committed `annotations.proto` and `http.proto` copies from
`googleapis/googleapis` commit `9af1fae615707962433f1d7338e707cde4d9e55e`.

The `codegen` dependency enables the pinned protobuf extra, and the `packages`
job uses `input-file-type = "protobuf"` plus the per-job
`schema-version = "auto"`. This empirically proves that a job-level schema
version overrides the root JSON-Schema version: both batch generation and its
drift check exited 0. The committed custom templates deterministically emit:

```python
class Struct(_Struct, forbid_unknown_fields=True, rename="camel"):
```

### AC 2 — Decode and re-encode a real package response offline

Closed. `tests/fixtures/research/deps-dev-pypi-requests.json` is the captured
`pypi/requests` response supplied from an environment with network egress. The
tracked JSON is 27,117 bytes (the 27,116 captured response bytes plus the
repository-required final line feed), SHA-256
`3e46b20901c3865f7f1425887916c8e8398b31b6f0b91e039e01dee7b4a3c385`.

`generated_packages_prototype.round_trip_package` decodes those bytes directly
as the generated `DepsDevV3Package` and re-encodes the object with msgspec. The
offline test proves the object contains the `PYPI` / `requests` package key and
161 versions; decoded output equals the input JSON; top-level output keys are
`packageKey` and `versions`, never `package_key`; and nested `publishedAt` and
`isDefault` keys survive without snake_case aliases.

```text
$ UV_CACHE_DIR=/tmp/kb-575-uv-cache UV_OFFLINE=1 uv run pytest tests/test_generated_packages_prototype.py -x -q
.                                                                        [100%]
exit 0
```

The test reads only the committed fixture and performs no network call.

### AC 3 — A real package returns 200 without an API key

Closed with architect-supplied evidence. This was confirmed by the architect
from an environment with network egress, since this lane's sandbox has none.
The request sent no API key. This lane did not rerun or fabricate the live
probe.

```text
$ curl -o /dev/null -w '%{http_code}' https://api.deps.dev/v3/systems/pypi/packages/requests
200
```

### AC 4 — A bogus package is discriminated by 404

Closed with architect-supplied evidence from the same egress-enabled
environment. This request also sent no API key.

```text
$ curl -o /dev/null -w '%{http_code}' https://api.deps.dev/v3/systems/pypi/packages/this-package-does-not-exist-xyz-999
404
```

The 200/404 pair demonstrates real-versus-missing discrimination rather than
merely proving that the service responds.

### AC 5 — Track the findings and reproducibility evidence

Closed by this report, the manifest and registry provenance entries, the
committed protobuf inputs, generated module, prototype, real fixture, and
offline test. The evidence is reproducible on a fresh clone without first
running `kb-build` and without network access during pytest.

## Verification evidence

The final generator checks retained protoc's truthful warning that its temporary
sanitized protobuf does not use the annotations import. The published input and
both transitive Google API files remain committed because the unmodified
protobuf import graph requires them.

```text
$ UV_CACHE_DIR=/tmp/kb-575-uv-cache UV_OFFLINE=1 mise run kb-codegen
[kb-codegen] $ uv run --project /Users/rmanaloto/dev/github/ray-manaloto/knowle…
…/deps-dev-api-v3.proto:19:1: warning: Import google/api/annotations.proto is unused.
exit 0

$ UV_CACHE_DIR=/tmp/kb-575-uv-cache UV_OFFLINE=1 mise run kb-codegen-check
[kb-codegen-check] $ uv run --project /Users/rmanaloto/dev/github/ray-manaloto/…
…/deps-dev-api-v3.proto:19:1: warning: Import google/api/annotations.proto is unused.
exit 0

$ UV_CACHE_DIR=/tmp/kb-575-uv-cache UV_OFFLINE=1 mise run kb-check -- python/src/kb_setup/generated_packages_prototype.py python/src/kb_setup/generated/packages.py tests/test_generated_packages_prototype.py
All checks passed!
3 files already formatted
All checks passed!
.                                                                        [100%]

kb-check:
  ruff     rc=0    ok
  format   rc=0    ok
  ty       rc=0    ok
  pytest   rc=0    ok
exit 0
```

`mise run lint` was re-run by the architect (a different environment, with
network/SystemConfiguration access this lane's sandbox lacked) and passed clean,
including Taplo — the earlier sandbox run's Taplo panic
(`system-configuration-0.5.1/src/dynamic_store.rs:154:1: Attempted to create a
NULL object`) does not reproduce outside that sandbox and was a captured
environment limitation there, not a TOML finding. Real captured result:

```text
$ mise run lint
✔ newlines  ✔ pkl  ✔ trailing_whitespace  ✔ taplo  ✔ check_merge_conflict
✔ ruff  ✔ rumdl_format  ✔ agnix (0 errors, 0 warnings, 8 info)  ✔ skill_lint
✔ workflow_lint  ✔ lychee_offline (1289 total, 0 errors)  ✔ no_lint_skip
✔ ty  ✔ md_size_budget  ✔ typos  ✔ gitleaks (no leaks found)  ✔ ruff_format
exit 0
```

No lint suppression or configuration bypass was added.

Graph orientation was also unavailable as authority. Two repository-owned
`kb-query` attempts emitted the pre-#1504 node-ID warning and returned only
53/1,673 nodes marked incomplete and truncated; `kb-query` rejected that result
and exited 3. Source inspection was therefore the declared fallback.

## GitHub repos touched

- [google/deps.dev](https://github.com/google/deps.dev) — published API v3
  protobuf and keyless package endpoint provenance.
- [googleapis/googleapis](https://github.com/googleapis/googleapis) — pinned
  `google/api/annotations.proto` and `google/api/http.proto` import dependencies.
