# Currency run — datamodel-code-generator — 2026-08-25T05:32:08+00:00

**Verdict:** datamodel-code-generator 0.74.0 → 0.75.1: 2 question(s) for review

Related: [[tool-currency-log]] · [[datamodel-code-generator]]

## Step 1 — in sync?

Pinned `0.74.0` · resolved `0.74.0`

| check | status | detail |
|---|---|---|
| version | ok | datamodel-codegen on PATH is the reviewed 0.74.0 (<repo>/.venv/bin/datamodel-codegen) |
| manifest | skip | sources/datamodel-code-generator.manifest pins 0.74.0; the local clone could not resolve that ref (no clone, no `.git`, no such tag, or git unavailable), so `commit` was NOT checked — run `mise run kb-build` |

## Steps 2-3 — upstream

- Latest (pypi): `0.75.1`
- GitHub release: `0.75.1`
- Reachable: yes

### Release notes

````text
## 0.75.0

## Breaking Changes



* minProperties/maxProperties now generate runtime validators - When using the experimental `--generate-schema-validators` option, `minProperties`/`maxProperties` constraints on named object models are now emitted as Pydantic v2 model validators. Previously these constraints were ignored. Data that omits or exceeds the allowed property count will now be rejected at validation time, and generated models gain a new `__json_schema_property_count_rule__` class variable (#3780)
* Runtime-validation helper base class renamed in mixed modules - When a module contains both core validators (patternProperties / required groups / conditional required) and the new property-count validators, the shared helper base class previously named `_JsonSchemaRuntimeValidationBase` is now split: the core helper is renamed to `_JsonSchemaRuntimeValidationBaseCore` and a new `_JsonSchemaRuntimeValidationBase` subclass is inserted. Code that references the generated helper class name by hand will need to be updated (#3780)

```python
# Before (--generate-schema-validators)
class _JsonSchemaRuntimeValidationBase(BaseModel):

… (truncated)
````

### Features to consider adopting

_**Could not tell.** The release notes are non-empty but match no changelog format this scan understands (no `Added`/`Highlights` section, no `feat:` prefixes, no adoption phrases), so this is **not** a report of zero features — read the notes by hand._

## Step 4 — tracked issues and watch items

_No watch items configured for this tool._

## Step 5 — decision

Gates passed:

- ✅ latest version has a readable GitHub release
- ✅ extras unchanged
- ✅ no tracked issue moved
- ✅ step 1 currently green

### Gate: patch-level bump

**0.74.0 → 0.75.1 is not a patch bump. Adopt it?**

- Detail: Only the patch component may move unattended. Pre-1.0 projects use the MINOR slot as their breaking channel, so 0.9.x → 0.10.0 stops here.
- Recommended: Read the release notes, then decide.
- **Answer:** _not yet answered_

### Gate: no breaking/removal/deprecation marker

**The release notes flag a breaking change. Adopt it anyway?**

- Detail: Markers found: breaking.
- Recommended: Read the notes; plan a rebuild and a re-verify before adopting.
- **Answer:** _not yet answered_

## Step 6 — process note

This page is the immutable record of ONE run — a later run writes its own new
page rather than rewriting this one. Annotate it freely with review notes;
nothing here is regenerated.
