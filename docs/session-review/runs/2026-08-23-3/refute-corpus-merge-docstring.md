# Refutation lane: corpus-merge docstring "Nothing is written on a refusal"

Lane: refute-corpus-merge-docstring. Task: try to REFUTE the finding that
`graphify_semantic_corpus_merge.py:300` ("Nothing is written on a refusal") is
false for downstream refusals because :307-316 create/clear staging and write
per-chunk files before `chunks.assemble`'s cross-chunk gates run.

## Probe 1 — read the cited lines (2026-08-18)

`Read python/src/kb_setup/graphify_semantic_corpus_merge.py:260-366`:

- :296-301 docstring of `assemble()`: "Raises ValueError with every reason on any
  refusal — from `collect` above or from `chunks.assemble`, which owns per-chunk
  schema validation and both cross-chunk collision gates. **Nothing is written on
  a refusal.**" — the quoted sentence IS at :300. CONFIRMED.
- :302-306: the `collect` refusal raises BEFORE any write — for THAT path the
  docstring is true (the finding correctly scopes to "downstream refusals").
- :307 `staging = _staging_dir(candidate)`; :315 `staging.mkdir(...)`;
  :316-317 stale `chunk-NNNN.json` unlink loop; :318-326 per-chunk
  `out.write_text(...)` (:325); :327 `return chunks.assemble(repo_root, name, paths), accepted`.
- No try/finally, no cleanup of staging on failure anywhere in `assemble` or in
  `merge_main` (:351-355 catches and returns 1, no cleanup).

Citation imprecision noted (not a refutation): the per-chunk WRITES are at
:318-326, slightly past the finding's cited ":307-316" (which covers only the
create/clear). Substance unaffected — all writes precede :327.

## Refutation angles tried

1. "Written" might mean the committed output only → the docstring sentence is
   unqualified, and the code's own comment (:308-314) treats leftover staging
   files as "a reproducibility trap", i.e. these writes matter. Not a refutation.
2. Gates might run before the writes → impossible: `chunks.assemble` reads the
   just-written `paths`; it is called at :327 after every write.
3. Downstream refusal might be unreachable (no gates in chunks.assemble) →
   probing chunks.py next.

## Probe 2 — the downstream gates exist and fire after the caller's writes

`grep -n "def assemble" python/src/kb_setup/chunks.py` -> :782.
`sed -n 872,940p chunks.py | grep -nE "raise ValueError|problems|write_text"`:
problems collected (id collisions, combined `_hyperedge_issues`,
`assembly_overlaps`), then `if problems: raise ValueError` at chunks.py:905-908,
and chunks.assemble's OWN output write only after, at :928. So chunks.assemble
honors its "never write a broken chunk" — but the CALLER's staging writes at
merge.py:315-326 have already happened when it raises.

## Probe 3 — no cleanup mechanism exists (armed)

`grep -nE "rmtree|unlink|remove|TemporaryDirectory|tempfile"` over the merge
module: ONLY hit is :317 (`stale.unlink()` — the PRE-write clear of a prior
run's ordinal files). Control in the same command: `write_text` -> 1 hit (:325),
so the grep discriminates. No rmtree, no tempdir, no post-refusal cleanup.

## Probe 4 — the refusal-after-write path is TEST-PINNED (the decisive arm)

`tests/test_graphify_semantic_corpus_merge.py:264-276`
(`test_cross_chunk_id_collision_is_reported_with_the_chunk_ordinal`): stages two
chunks with colliding node id "dup"; `merge.assemble` raises
`ValueError "id collision 'dup'"` — a `chunks.assemble` cross-chunk gate — and
the test asserts the message CONTAINS `chunk-0001.json` and `chunk-0002.json`,
i.e. the staging files. An id-collision (not unreadable-JSON) problem proves
those files were successfully READ, hence written, before the gate fired. The
test's own docstring says so: "the assembled per-chunk files ... the refusal
names which ordinals collided". The design DEPENDS on writing before refusing.

`tests:289-292` additionally pins that `chunk-0001.json` persists on disk after
assemble returns — the staging dir is durable, not a tempdir.

## Verdict: NOT refuted — CONFIRMED

The docstring sentence at :300 is unqualified and sits in a docstring that
explicitly includes refusals "from `chunks.assemble`"; for that downstream path
the module writes (and leaves behind) this run's `chunk-NNNN.json` staging files.
The original probe could have produced the opposite answer (a try/finally
cleanup, a TemporaryDirectory, or gates-before-write would each make the
docstring true) — none exists.

One citation imprecision for the issue list: the per-chunk WRITES are at
:318-326 (write_text :325); the finding's ":307-316" covers only the
create/clear. Cite :307-327.

Severity "low" consistent: the leftovers are the gitignored `-assembly`
intermediate (handoff e item 4), cleared by the next successful assemble
(:316-317) — a reproducibility-trap + misleading-docstring defect, not
corruption.

## Contradicting findings in the set: NONE

The settled 2026-08-18 triage AGREES (REAL low, final). Ray's 2026-08-18
directive (read in full) and all 7 handoffs (b-g, 18-a; read in full) contain
nothing about this docstring; handoff (e) corroborates the module's history
(`81b3cc85` built the merge step + id-collision gate keyed on resolved path).
The only artifact disagreeing with the code is the docstring itself — which is
the defect.

## COVERAGE

- REACHED AND ANALYSED: graphify_semantic_corpus_merge.py:260-366 (full
  assemble + merge_main); chunks.py:782-940 (assemble docstring, gates, raise,
  write ordering); tests/test_graphify_semantic_corpus_merge.py:257-295 + a
  refusal/staging/cleanup grep of the whole test file;
  docs/direction/2026-08-18-ray-directives.md IN FULL; all 7 handoffs IN FULL.
- OPENED BUT NOT FINISHED: none.
- NEVER REACHED: the transcripts themselves (not needed — the finding is about
  code, the triage disposition was declared final and settled); chunks.py
  outside :782-940.
