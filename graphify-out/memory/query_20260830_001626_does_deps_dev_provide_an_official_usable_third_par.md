---
type: "query"
date: "2026-08-30T00:16:26.987728+00:00"
question: "Does deps.dev provide an official/usable third-party SDK we should use instead of generating models from its protobuf (#575)?"
contributor: "graphify"
outcome: "useful"
---

# Q: Does deps.dev provide an official/usable third-party SDK we should use instead of generating models from its protobuf (#575)?

## Answer

No official Google/deps.dev SDK exists. Google's own `google/deps.dev`
README directs integrators to generate a client from the published
`api/v3/api.proto` for the gRPC API, and explicitly disclaims the two
community tools it names (`edoardottt/depsdev`, a Go CLI; `safedep/vet`,
a policy tool) as "unsupported by the core deps.dev maintainers." A third,
unrelated unofficial PyPI package (`depsdev` by `FlavioAmurrioCS`, v0.0.5,
solo author) returns only untyped raw JSON dicts, no models at all.
buf.build's Schema Registry was checked and is inconclusive (its pages are
a client-rendered SPA that returns byte-identical HTML for a real and a
bogus module path) but immaterial either way, since a BSR-generated SDK
would still hand back raw `google.protobuf.Message` classes rather than
this repo's msgspec `Struct` types.

Verdict: protobuf codegen via this repo's own `datamodel-codegen`
generator (issue #575) is not avoidable complexity — it is what Google's
own docs tell integrators to do. Full evidence:
docs/research/reports/2026-08-29-deps-dev-sdk-evaluation.md and
docs/research/reports/2026-08-29-deps-dev-packages-prototype.md.


## Outcome

- Signal: useful