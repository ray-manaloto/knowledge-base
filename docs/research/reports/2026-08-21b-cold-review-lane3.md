# Cold review — commit `3d9bb3ff` (base `ebcf9fcb`)

Reviewed SHA: **`3d9bb3ff7fedc6ff7959355ed7126d4b50fd17bc`** (`3d9bb3ff`), read entirely
by ref (`git show 3d9bb3ff:<path>`, `git diff ebcf9fcb 3d9bb3ff`). Working-tree files
were not read. Nothing was modified; no test, gate, or mise task was run. Installed-library
facts come from `.venv/lib/python3.14/site-packages/graphify/`.

Line numbers are **as in `3d9bb3ff`** unless marked otherwise.

**No P0.** I could not construct a case where the dedupe admits the wrong bytes, drops
content that has no admitted twin, produces a non-deterministic plan, or breaks the
plan↔run repacking identity. The findings below are about what the change *claims* to
have guarded and measured versus what it actually guards and has actually measured.

---

## P1

### P1-1 — `duplicate-group-git-object-mismatch` cannot fire; the design leans on two guards, not three

`graphify_semantic_corpus.py:1306-1307`

```python
        canonical = canonical_by_parent.setdefault(member.sha256, relative)
        if member.git_object != members[canonical].git_object:
            raise ValueError(f"duplicate-group-git-object-mismatch:{relative}")
```

The branch is entered only when `member.sha256 == members[canonical].sha256` (that is the
dict key). Tracing where those two fields come from:

- `graphify_baseline.py:495` — `sha256=hashlib.sha256(blob).hexdigest()`
- `graphify_baseline.py:494` — `git_object=git_object`, the `ls-tree` blob id
- `graphify_baseline.py:478` — `blob = blobs[git_object]`, and `_git_blob_batch`
  (`graphify_baseline.py`, `["git","-C",…,"cat-file","--batch"]`) returns **raw object
  bytes**; no `--filters`, so no `.gitattributes`/`core.autocrlf` path can separate
  worktree bytes from blob bytes.
- `graphify_baseline.py:488` — `if current != blob: raise ValueError("source-snapshot-drift…")`,
  so the manifest additionally refuses any worktree/blob divergence before dedupe runs.

Therefore `sha256(blob_A) == sha256(blob_B)` ⟹ `blob_A == blob_B` ⟹ identical git blob
ids (git is content-addressed over `blob <len>\0<content>`). I tried to construct the
reaching case per `probes-need-a-control-arm.md` rule 9 and the only construction is a
**SHA-256 collision** — at which point every digest in this plan scheme is already void.

Why it is P1 and not a nit: the commit body ("Plan-time asserts (git-object, kind,
slice-total/suffix-class) guard the one assumption the design leans on") and the
`DuplicateGroup` docstring at `:339-344` ("safe because `_inventory` asserts every path
sharing a `parent_sha256` agrees with the canonical on **git object**, kind, and slice
count") both present three discriminating guards. Two discriminate. The docstring also
credits the git-object assert with making `parent_size` safe — `parent_size` is safe, but
for the simpler reason (equal sha256 ⟹ equal bytes ⟹ equal length), not because of a
check that cannot fire. A reader auditing this later will believe a guard exists that does
not.

### P1-2 — the arms spec cannot run at this commit, and no arm has ever been observed red

`docs/research/reports/2026-08-21-414-content-dedupe-arms.toml:19` declares
`suites = ["tests/test_graphify_semantic_corpus.py"]`.

`arms.py:458-463`:

```python
    baseline_rc, _ = runner()
    if baseline_rc != 0:
        return Report(
            baseline_rc,
            aborted="baseline suite is RED - no arm could have discriminated",
        )
```

The commit body declares `test_recorded_authority_authorizes_this_plan_and_only_this_plan`
**expected-red**, and that test is at `tests/test_graphify_semantic_corpus.py:878` — inside
the one suite the spec names. So `mise run kb-arms -- <spec>` aborts at the baseline at this
commit and will keep aborting until `AUTHORITY_JSON` is re-recorded. The spec is not merely
"not run", it is **unrunnable as committed**.

What was actually run is `--dry-run`, i.e. `arms.check` (`arms.py:374`), whose docstring says
it is "answerable without pytest" — it verifies only that each `old` string applies. Reporting
"6/6 apply" alongside a claim about arms is evidence about string matching, not about any test
going red. Under `probes-need-a-control-arm.md` rule 2 and the repo's own "an arms spec never
run is a claim", this change currently has **zero measured FAIL-direction evidence** for its
new logic.

Secondary: the commit body says "full sweep intentionally not run **per spec**". The spec
contains no such instruction — its SCOPE block (`…arms.toml:11-17`) only lists what is *not*
armed.

### P1-3 — two of the six new verifier reasons are asserted by no test, and one whole predicate has no FAIL-direction coverage

| new reason | asserted by a test? | armed? |
|---|---|---|
| `inventory-parent-content-duplicate` (`:1691`) | yes (`tests/…:1879`) | no |
| `inventory-duplicate-group-invalid:<path>` (`:1695`) | **no** | **no** |
| `inventory-duplicate-canonical-not-admitted` (`:1697`) | yes (`tests/…:1903`) | no |
| `inventory-duplicate-path-admitted` (`:1699`) | yes (`tests/…:1878`) | yes (R4) |
| `inventory-duplicate-group-order-invalid` (`:1711`) | **no** | **no** |
| `inventory-duplicate-totals-mismatch` (`:1724`) | yes (`tests/…:1927`) | no |

`_duplicate_group_is_well_formed` (`:1646-1674`) is 18 conjuncts and is the sole producer of
`inventory-duplicate-group-invalid`. Nothing in the diff makes it return `False`. Likewise the
three plan-time asserts (`:1307`, `:1309`, `:1313`) have no fixture — no test builds two
byte-identical files whose suffixes put them in different `is_splittable_text` classes, which
is precisely the assumption the commit body says the asserts exist to guard.

### P1-4 — a `DuplicateGroup` carries no evidence about the paths it drops, so the record is uncheckable without full recomputation

`:1347-1352`

```python
                    parent_sha256=parent_sha256,
                    source_git_object=members[canonical_by_parent[parent_sha256]].git_object,
                    parent_size=members[canonical_by_parent[parent_sha256]].size,
                    kind=kinds[canonical_by_parent[parent_sha256]],
                    canonical_path=canonical_by_parent[parent_sha256],
                    dropped_paths=tuple(sorted(group_dropped_paths)),
```

Every identity field is the **canonical's**. `dropped_paths` is bare strings. Contrast
`IntentionalExclusion` (`:1240-1249`), which records `sha256`, `size`, `evidence_git_objects`
and `evidence_sha256` per excluded path — a record you can check against the tree.

Traced tamper (constructed, not run): delete N admitted units, renumber ordinals, invent one
`DuplicateGroup` naming a surviving admitted path as canonical and the deleted paths as
`dropped_paths`, set `dropped_unit_count`/`dropped_estimated_tokens` to the deleted sums,
fix `admitted_unit_count`/`admitted_estimated_tokens`/the three `duplicate_dropped_*` totals,
repack the ledger over the survivors, then re-sign with the recipe the tests themselves use
(`tests/…:1761-1775` + `_rehash_plan`). That plan passes:

- `_duplicate_group_is_well_formed` (all fields copied from a real admitted unit),
- `inventory-parent-content-duplicate` (the deleted paths are no longer admitted),
- `inventory-duplicate-canonical-not-admitted` / `-path-admitted`,
- `inventory-duplicate-group-order-invalid`,
- `inventory-duplicate-totals-mismatch` (self-consistent by construction),
- both `_exclusion_reasons` count invariants (`:1800-1807`, likewise self-consistent).

Only `source-inventory-recomputation-mismatch` (`:1946`) catches it — which the change's own
tests confirm, since each tamper test asserts the recomputation reason alongside the targeted
one (`tests/…:1880`, `:1904`, `:1928`). The six new reasons are therefore defence-in-depth over
recomputation, not independent detection. That is a defensible design; presenting them as "six
new verifier reasons" without saying so overstates what the plan record alone can prove.

### P1-5 — on the verify path all three new named asserts are erased into `source-snapshot-unavailable`

`:1932-1943`

```python
    try:
        expected_inventory, … = _inventory(…)
        expected_ledger = _ledger(…)
    except OSError, ValueError:
        return ["source-snapshot-unavailable"]
```

The three new `ValueError`s (`duplicate-group-git-object-mismatch`,
`-kind-mismatch`, `-suffix-class-mismatch`) are `ValueError`s raised from inside `_inventory`.
On the verify path they are caught here and reported under a name that says the **snapshot
could not be read**. Two consequences:

1. The carefully-chosen reason strings never reach a verdict, so the operator loses the one
   diagnostic the asserts exist to produce.
2. `persistence-gate-retry.md` classifies snapshot/environment-shaped failures as the
   retry-once class. A genuine content-class divergence would be triaged as transient and
   retried — the exact "a tool reporting a real defect in the words of an environment
   failure" shape that rule warns about.

Verification still fails closed, which is why this is P1 and not P0.

---

## P2

### P2-1 — five present-tense pre-dedupe figures survive in the module this commit rewrites

| site | text | post-dedupe |
|---|---|---|
| `:57` | "a MEDIAN chunk, since the **58** range 13,067 to 19,989" | 26 chunks, different distribution |
| `:72` | "**58 chunks** at ~11 minutes each is ~10.6 h" | 26 → ~4.8 h |
| `:88` | "**58 chunks** at the measured 1.12 USD/chunk is 64.96 … 2 x 64.96 = 129.92; +~8% margin -> 140.0" | 26 × 1.12 = 29.12; 2× = 58.24; +8% ≈ 63 |
| `:502-504` | "so **58 chunks** each individually within authority… 58 chunks project to roughly 65" | as above |
| `:2602` | "would spend a subprocess call **58 times**" | 26 |

`:88` is the load-bearing one. `_MAX_TOTAL_COST_USD = 140.0` (`:93`) was set to exactly that
derivation in the **immediately preceding** commit `d8114ab1` (same day, "size the cap for one
restart"), on Ray's ruling. This commit invalidates the derivation the ruling rested on: the cap
is now roughly **2.2×** its stated sizing. The constant is conservative in the safe direction and
"makes 1,450 unreachable" still holds, so this is P2 — but a reviewer reading `:88` will believe
the cap is tight when it is not. This is `probes-need-a-control-arm.md` rule 6's "a number can be
invalidated by the very commit that writes it", one commit removed.

`graphify_semantic_corpus_authority.py:462` ("474 -> 475 admitted units, still 58 chunks") is a
**historical** re-record entry and is correctly left alone.

### P2-2 — the canonical↔dropped mapping exists only in a gitignored artifact

`:327-329`:

> The record's own stated reason a duplicate group is absent from admission — so a reader of
> `source-inventory.json` never has to know the planner to see WHY a path is missing.

`.gitignore:57` ignores `graphify-out/graphify-semantic-corpus/`, and `do-not.md` #5 forbids
committing it. So no clone has `source-inventory.json`; what is tracked is only its **digest**
inside `graphify_semantic_corpus_authority.py`. Meanwhile the extracted graph binds nodes to
admitted paths only (`_semantic_graph_integrity_reasons`, `:3145-3146`), and I found no alias/
canonical handling in `graphify_semantic_corpus_merge.py` (grepped `canonical|duplicate|alias`
at the commit — three hits, all `encode_canonical`/`chunk_sha256`/an unrelated comment).

Net: after this change **257 of 374 detected paths** will have no `source_file` in the produced
graph, and the only durable artifact recording why is a machine-local file. Whether a later slice
intends to publish aliases is **UNVERIFIED** — I checked only `python/src/kb_setup/`.

### P2-3 — `events.say`'s `dropped_paths=` field is an integer under a name that means a path tuple everywhere else

`:3516` emits `dropped_paths=inventory.duplicate_dropped_path_count` (an `int`), while
`DuplicateGroup.dropped_paths` (`:352`) is `tuple[str, ...]` and the inventory names the count
`duplicate_dropped_path_count` (`:371`). A structured-log consumer querying the field
`dropped_paths` gets a different type than the same identifier means in the two structs this
event describes. `dropped_path_count` would match the record.

### P2-4 — the second count invariant's arm is declined by argument, and the argument is wrong

`…arms.toml:13-15` excludes `discovered-unit-count-mismatch` because "the second invariant is
the same shape as the first, reverted by the same review". They are not the same shape:

```python
:1800    if inventory.detected_source_count != (
:1801        len(admitted_paths) + len(paths) + inventory.duplicate_dropped_path_count   # PATHS
:1804    if inventory.discovered_unit_count != (
:1805        inventory.admitted_unit_count + len(paths) + inventory.duplicate_dropped_unit_count  # UNITS + a PATH count
```

The second mixes `len(paths)` — a count of excluded **paths** — into a **unit** total (see
nit-1). Under `probes-need-a-control-arm.md` rule 9, a predicted survival owes more evidence,
not less.

---

## Nits

- **nit-1** `:1804-1806` — the unit invariant adds `len(paths)` (excluded *paths*) to unit
  counts. It holds today only because all four `_INTENTIONAL_EXCLUSIONS` (`:100`) are
  non-splittable single-unit files (`.svg`, `.png`, `.png`, `.html`; graphify's
  `_SPLITTABLE_TEXT_SUFFIXES` is `{.md,.mdx,.markdown,.txt,.rst}`, `file_slice.py:29`). Add one
  oversized `.md` exclusion and the invariant fires on a **correct** plan. Pre-existing, but this
  commit is the one that re-derived both lines.
- **nit-2** `:375` — `schema_version: int = 2` is bumped and nothing verifies it. It carries a
  default, so a plan declaring `1` beside the v2 fields decodes cleanly and is caught only by
  recomputation. (Also true at v1; the bump was the moment to add the check.)
- **nit-3** `:1673` — `all(unit.parent_sha256 == group.parent_sha256 for unit in canonical_units)`
  is vacuously `True` when `canonical_units` is empty, which is exactly the tamper
  `test_a_group_whose_canonical_is_not_admitted_is_refused` exercises. It only works because
  `:1696-1697` covers that case separately. Fragile pairing; a `canonical_units and all(...)`
  would make the predicate stand alone.
- **nit-4** `:3462` / `tests/…:1964` — `f"{…} groups"` is unpluralised, and the test pins the
  literal `"duplicate-content: 1 groups · …"`, so the wart is now a contract.
- **nit-5** `:3511` — `_typed_members(output)` is unguarded here, while every other decode site
  wraps it (`verify_plan`, `:2016-2020`). A malformed just-written plan turns a successful plan
  run into a traceback *after* the plan has already been published to `output`.
- **nit-6** — the commit body says "six tests"; the diff adds **five** new test functions plus an
  extension to `test_exact_graphify_plan_is_structurally_complete_after_authority_revocation`.
- **nit-7** `tests/…:112` — the new fixture uses `git add -A`, the exact shape
  `kb_setup.stage_explicitly` denies at the PreToolUse hook. Harmless inside a `subprocess` call,
  but it is the repo's own named anti-pattern reproduced in new code; `git add .` on a fresh
  temp repo, or naming the four paths, avoids the mixed signal.
- **nit-8** `:3450-3469` — `_dedupe_summary`'s "of {total} estimated tokens" denominator is
  `admitted + dropped`, i.e. *all non-excluded* units, not "what the corpus would have cost"
  restricted to duplicated files. That is the right denominator for the sentence as written; I
  note it because the same 55.1% will be quoted later and its condition should travel with it.

---

## What I checked and found clean

1. **Determinism across re-plans.** `expand_oversized_files` (`file_slice.py:107-133`) is a
   strict order-preserving per-file loop, so the unit stream is `sorted(kinds)` order with each
   file's slices contiguous — the canonical really is the lexicographically-first path.
   `dropped_paths` values are `set` but emitted `tuple(sorted(...))` (`:1352`); the group tuple
   is `sorted(key=canonical_path)` (`:1359`) over unique canonicals. No dict-iteration order
   escapes into the plan.
2. **`advisories.json` / `exclusions.json` byte-identity.** The dedupe block (`:1305-1320`) sits
   strictly *after* the `_INTENTIONAL_EXCLUSIONS` `continue` (`:1293-1304`) and writes only the
   five new dicts plus `admitted`/`units`. Neither `advisories` nor `exclusions` is reachable
   from it. The commit's control-arm claim is structurally sound, independent of the two digests
   quoted.
3. **plan↔run repacking identity survives dedupe.** `_ledger` packs the `admitted` unit list
   (`:1406`); the run replays `admitted_paths(inventory, source_root)`
   (`graphify_semantic_corpus_run.py:401-422`, used at `:1208`) through graphify's own
   `expand_oversized_files` + `_pack_chunks_by_tokens`. `expand_oversized_files` is per-file
   independent and `admitted_paths` preserves first-appearance (= sorted) order, so re-expanding
   only the admitted subset reproduces exactly the units the plan packed.
   `_pack_chunks_by_tokens` sorts by absolute parent dir under a common prefix, so ordering is
   preserved across the two roots.
4. **Arms anchors.** Each `old` string occurs **exactly once** in the committed source
   (`canonical = canonical_by_parent.setdefault(...)`, `) + _estimate_file_tokens(unit)`,
   `dropped_tokens[member.sha256] = dropped_tokens.get(`,
   `reasons.append("inventory-duplicate-path-admitted")`,
   `reasons.append("detected-source-count-mismatch")` — all count 1), and the multi-line blocks
   match `:1317-1320`, `:1698-1699`, `:1800-1803` verbatim including indentation.
5. **Each arm would go red, reasoned per-arm** (not executed, see P1-2): R1 drops the `continue`
   → `admitted_paths.isdisjoint(group.dropped_paths)` fails; R2 overwrites the canonical after
   `setdefault` → both the recorded `canonical_path` assertion and (from slice 2 onward) actual
   re-admission fail; R3 substitutes raw bytes → `dropped_estimated_tokens == 2 * canonical_tokens`
   fails; R4 neuters the reason → the membership assert fails; R5 reverts the path invariant →
   `detected-source-count-mismatch` fires on the *correct* fixture and breaks test 1's exact
   `("plan-authority-unset",)` tuple. C0 is a comment append, a genuine no-op.
6. **Struct equality.** All five new fields and the nested `DuplicateGroup` participate in
   msgspec's generated `__eq__`, so `inventory != expected_inventory` (`:1945`) covers the whole
   new surface, including `schema_version` and tuple ORDER of `dropped_paths`.
7. **Blast radius of the schema change.** The only readers of `SourceInventory` outside the
   planner are `graphify_semantic_corpus_run._load_plan` (`:999-1022`) / `admitted_paths`
   (`:401`) and `graphify_semantic_corpus_prototype._plan_inputs` (`:158-197`); both touch only
   `units`, and both strict-decode — so an old on-disk plan is **refused**, not silently run.
   `graphify_semantic_corpus_merge.py` does not read it. Exactly one hand-constructed
   `SourceInventory` exists in the whole tree outside the planner
   (`tests/…:1932`), and it is the new one — no pre-existing construction was left with missing
   required fields.
8. **The commit's headline arithmetic is internally consistent** and re-derived here rather than
   copied: admitted paths = 374 − 257 − 4 = **113**; 113 + 257 + 4 = 374 ✓ (invariant 1);
   170 + 305 + 4 = **479** ✓ (invariant 2, with the four exclusions at one unit each);
   466,590 + 571,462 = **1,038,052** ✓; 571,462 / 1,038,052 = 0.550514 → `:.1%` → **55.1%** ✓
   (correct, though only 0.0014 pp above the rounding boundary); 475 − 305 = **170** ✓;
   466,590 / 20,000 = 23.3, so 26 chunks is plausible under directory-grouped packing, as is 58
   for 1,038,052. The `55.1%` figure's condition — tiktoken installed — is stated in the commit
   body, correctly.
9. **`_dedupe_summary` ratio** (`:3458-3460`) matches its test literal: 200 / (300+200) = 40.0% ✓,
   and the `if total_tokens else 0.0` guard makes the empty case safe.
10. **Style/gates I could check statically**: every added line is < 100 chars
    (`pyproject.toml:105` sets `line-length = 100`); `except OSError, ValueError` at `:1942` is
    valid under PEP 758 on this repo's Python 3.14 (pre-existing idiom, not new);
    `events.say(event, text, **fields)` (`events.py:235`) matches the call at `:3512-3521`; the
    new test file uses `hashlib` and `cast`, both already imported (`tests/…:11`, `:24`).
11. **The new block is plan-only.** `corpus_main`'s `verify`/`run` branches return at `:3492` /
    `:3495`, so `_typed_members` + `events.say` (`:3511-3521`) run on the plan path alone.
12. **`_INTENTIONAL_EXCLUSIONS` × dedupe.** An excluded path never registers as canonical
    (`continue` at `:1304` precedes `:1305`), so an excluded file that duplicates an admitted one
    is counted once as an exclusion and never as a dropped duplicate — both invariants still
    balance. A dropped path that were also an exclusion would be double-counted, but the totals
    would then exceed `detected_source_count` and `detected-source-count-mismatch` fires.

---

## GitHub repos touched

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — read the **installed**
  `graphify/file_slice.py` (`expand_oversized_files`, `slice_boundaries`,
  `_SPLITTABLE_TEXT_SUFFIXES`) and `graphify/llm.py` (`_estimate_file_tokens`,
  `_pack_chunks_by_tokens`) to settle whether unit order, slice counts, and token estimates are
  functions of content alone.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under
  review; all other citations are to this tree at `3d9bb3ff`.
