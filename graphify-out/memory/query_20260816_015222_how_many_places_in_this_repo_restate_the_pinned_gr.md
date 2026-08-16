---
type: "query"
date: "2026-08-16T01:52:22.999632+00:00"
question: "How many places in this repo restate the pinned graphify revision, and what does a version bump have to carry?"
contributor: "graphify"
outcome: "useful"
---

# Q: How many places in this repo restate the pinned graphify revision, and what does a version bump have to carry?

## Answer

Eight places, measured -- not the three the invariant comments describe.

At the 0.9.44 bump the revision had to move in: pyproject.toml + uv.lock, the
installed binary, sources/graphify.manifest, the sources/graphify clone,
graphify_baseline._ACCEPTED_GRAPHIFY_REF and its _ACCEPTED_AUTHORITY commit,
sources/graphify.dispositions.json (ref AND commit),
graphify_semantic_corpus._ACCEPTED_GRAPHIFY_{REF,COMMIT,TREE},
graphify_semantic_slice.SOURCE_{REF,COMMIT,TREE}, and the gitignored
.claude/skills/graphify/.graphify_version stamp. Plus derived values that follow:
wheel and sdist digests, catalog and source-manifest sha256s, a detect.py blob
object, and detected/extracted counts.

kb-currency-check reported NO graphify drift while graphify_baseline and the
disposition catalog were TWO RELEASES behind -- correctly, because manifest ==
pin, and nothing in the engine looked anywhere else.

Now gated: currency.toml carries eight [[tool.graphify.ref_binding]] rows plus a
skill_stamp check. Two design points that make them checks rather than decoration
-- a pattern matching NOTHING is DRIFT (a renamed anchor otherwise turns a
declared row into a silent no-op), and a suite test asserts every binding in the
real config still reaches its anchor.

Also found: DispositionCatalog.source_ref DEFAULTED to the literal "v0.9.42", so
a catalog constructed without a ref silently claimed that release and the loader
believed it. Now required. Defaulting it to the accepted ref would have been
worse -- the check becomes unfalsifiable, since a constructed catalog would always
agree with whatever the code accepts.


## Outcome

- Signal: useful