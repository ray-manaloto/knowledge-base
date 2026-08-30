# deps.dev SDK-vs-protobuf-codegen evaluation (#575, #568)

Date: 2026-08-29

## Question

Before building #575's protobuf-codegen prototype: does a modern third-party
SDK, client library, or API wrapper for deps.dev already exist that would make
generating models from the raw `.proto` unnecessary? This was re-checked from
primary sources this session, not assumed from #568's original spec text.

## Sources checked

- `google/deps.dev`'s own `README.md`
  (<https://raw.githubusercontent.com/google/deps.dev/main/README.md>)
- The `google/deps.dev` GitHub repository tree (via the GitHub API)
- PyPI, probed for plausible package names
  (`deps-dev`, `depsdev`, `deps_dev`, `pydeps-dev`, `google-deps-dev`,
  `libraries-io`)
- `FlavioAmurrioCS/depsdev`'s own `README.md` on GitHub
- buf.build's Schema Registry (<https://buf.build>)

## Findings

**No official Google SDK exists.** `google/deps.dev`'s own README, under
"Using the gRPC API":

> "The gRPC API can be accessed using any gRPC client. The service
> definition... can be found in [api/v3/api.proto](api/v3/api.proto)"

No first-party client library is linked anywhere in the README. The repo's
root tree (checked via the GitHub API) has no `python/`, `clients/`, or SDK
directory — only `api/` (the protos), `examples/` (`go` and `skills`
subdirectories), `submodules/`, and `util/`.

**The two community tools Google's README does name are explicitly
disclaimed, and neither is a Python client:**

> "Note that these are community built tools and unsupported by the core
> deps.dev maintainers."

— `edoardottt/depsdev` (a Go CLI/module) and `safedep/vet` (a policy tool).

**A third, different unofficial package exists on PyPI**, unrelated to either
of the above: `depsdev` by `FlavioAmurrioCS`, version 0.0.5, 5 releases, single
author, no `home_page` set. Its own README states:

> "Thin Python wrapper (async-first) around the public deps.dev REST API...
> responses are returned as decoded JSON (dict / list)."

It carries **no typed models at all** — so even if adopted, it would not
satisfy #575's own AC #1 ("Models are generated from the upstream published
protobuf definition, not hand-written from a sample"): there is nothing
generated *or* hand-written to point at, just raw dicts.

**buf.build's Schema Registry was checked and is inconclusive, but immaterial
either way.** Its pages are a client-rendered single-page app: a real module
path (`https://buf.build/google/deps-dev`) and a deliberately bogus one
(`https://buf.build/google/this-module-does-not-exist-xyz-999`) both returned
HTTP 200 with byte-identical HTML (10,652 bytes each) — confirmed with a
control-arm probe, so the page cannot be checked this way. Even if deps.dev
were registered there, a BSR-generated SDK would still hand back raw
`google.protobuf.Message` classes, not this repo's msgspec `Struct` types —
functionally the same trade-off as running `grpc_tools.protoc` directly, which
was also considered and rejected.

## Alternatives considered and rejected

| Option | Why rejected |
|---|---|
| `FlavioAmurrioCS/depsdev` (PyPI) | Untyped raw JSON dicts; fails AC #1; solo-author v0.0.5 |
| Hand-rolled dataclasses from a sample response | Explicitly excluded by AC #1 |
| `grpc_tools.protoc` + native `_pb2.py` message classes | Technically "generated from the proto," and `json_format.ParseDict` handles camelCase natively — but adds `protobuf`/`grpcio-tools` as a second runtime codegen path, produces unreadable `_pb2.py` output, and breaks the standing convention that this repo's ONE generator (`datamodel-codegen`, msgspec output) owns every model type |
| A buf.build BSR-generated SDK | Same trade-off as the row above, if it even exists (unconfirmed) |

## Verdict

No official or usable unofficial SDK exists. The protobuf-codegen approach in
`#575`/`#568` is not avoidable complexity — it is what Google's own
documentation directs integrators to do. This finding is also recorded as
comments on
[knowledge-base#575](https://github.com/ray-manaloto/knowledge-base/issues/575#issuecomment-5465561077)
and
[knowledge-base#568](https://github.com/ray-manaloto/knowledge-base/issues/568#issuecomment-5465561702),
and in `graphify-out/memory/` via `kb-remember`, so a future session does not
need to re-derive it.

## GitHub repos touched

- [google/deps.dev](https://github.com/google/deps.dev) — README and repo
  tree checked for an official SDK; none found.
- [googleapis/googleapis](https://github.com/googleapis/googleapis) — named
  here because it supplies the `google/api/annotations.proto`/`http.proto`
  import chain that #575's prototype vendors; not itself a candidate SDK.
- [FlavioAmurrioCS/depsdev](https://github.com/FlavioAmurrioCS/depsdev) — the
  unofficial Python wrapper checked and rejected above.
