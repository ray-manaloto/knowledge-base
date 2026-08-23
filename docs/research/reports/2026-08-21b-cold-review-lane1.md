# Cold review — commit `a67cbac4` (base `8929d47f`)

Reviewed BY REF only (`git show` / `git diff` / `git grep <rev>`); the working
tree was never read. Reviewed SHA: **`a67cbac49702673a0fc198cc5fd1cdc5962ff8e2`**
(`a67cbac4`). No edits, no writes other than this file. Every line number below
is as of `a67cbac4`.

No P0. Three P1, five P2, five nits.

---

## P1

### P1-1 — The scrub turns the routing REFUSAL into a silent, unrecorded deletion; every call site discards the evidence

`scrub_route_overrides` returns the removed names
(`python/src/kb_setup/graphify_semantic_slice.py:807-808`), and **all three call
sites throw that value away** as a bare statement:

- `python/src/kb_setup/graphify_semantic_slice.py:1907` (`build_candidate`)
- `python/src/kb_setup/graphify_semantic_slice.py:2042` (`semantic_main`)
- `python/src/kb_setup/graphify_semantic_corpus_run.py:1043` (`execute`)

`preflight` defaults to `environment=None` and therefore reads the
just-scrubbed `os.environ` (`graphify_semantic_slice.py:947-950`), so the
refusal at `:950` **cannot fire from any production caller**. Every in-repo
caller passes `environment=None`
(`graphify_semantic_slice.py:1913`, `:2051`,
`graphify_semantic_corpus_run.py:1046`,
`graphify_semantic_corpus_prototype.py:373`).

Consequence: a host deliberately configured for a non-first-party route —
`CLAUDE_CODE_USE_BEDROCK`, `ANTHROPIC_BASE_URL`, `CLAUDE_CODE_OAUTH_TOKEN`, all
in `_ROUTE_OVERRIDE_NAMES` (`:113-152`) — now produces a committed receipt that
is **byte-indistinguishable from a clean host**. `ClaudePreflight` records
`environment_names=tuple(sorted(child))` (`:985`), i.e. the CHILD allowlist
built by `claude_child_environment` (`:705-720`), never the parent; nothing
anywhere attests "there was nothing to remove". Verified against the committed
evidence: `graphify-out/graphify-semantic-slice/receipt.json` `runtime.environment_names`
is the 16-name child allowlist, with no scrub field.

The docstring calls the refusal "the backstop, not the mechanism"
(`:783-784`). A backstop that is unreachable *and* a removal that is never
recorded means the invariant `do-not.md` #4 exists to protect is no longer
falsifiable after the fact — you cannot tell from the artifact whether the run
was clean or was cleaned.

Second-order, operator-facing: `CLAUDE_CODE_OAUTH_TOKEN` used to produce a
precise `forbidden routing environment names: …` refusal. It is now silently
deleted, and on a host whose only credential was that token the run instead
fails downstream in `classify_auth` (`:981`) with `logged_in: false`.

Cheapest remedy that keeps #334's benefit: emit the returned names (stderr, or
a `scrubbed_routing_names` field on the receipt) instead of dropping them. I am
deliberately *not* claiming the scrub should be reverted — it does preserve the
security outcome, which is why this is P1 and not P0.

### P1-2 — The two slice-side scrub call sites have no test; deleting either survives the entire suite

`git grep -n scrub_route_overrides a67cbac4 -- tests` returns exactly four
hits, all in one file: `tests/test_graphify_semantic_slice.py:229`, `:241`,
`:252`, `:271`. **Neither `semantic_main` nor `build_candidate` appears in any
scrub test.** The two new slice tests exercise the FUNCTION
(`tests/test_graphify_semantic_slice.py:229-253` dict-based,
`:256-275` real-`os.environ`), not the WIRING.

Only `execute()`'s call site is wired-in-tested, and that test is well built —
it asserts from *inside* a stubbed `preflight`, so a scrub placed after it would
be caught (`tests/test_graphify_semantic_corpus_run.py:719-746`).

Therefore the mutations "delete `graphify_semantic_slice.py:2042`" and "delete
`graphify_semantic_slice.py:1907`" both survive a green run. Line 2042 is the
one the commit body names as the mechanism covering `preflight`/`run`/`verify`
— the highest-traffic entry point of the three, and the only one with no arm.
The pattern used at `test_graphify_semantic_corpus_run.py:729-733` ports
directly.

### P1-3 — The commit lands a knowingly RED suite, so this SHA cannot ship and no later "suite green" claim covers it

The commit body states: *"Left test_recorded_authority_authorizes_this_plan_and_only_this_plan
red"*. Verified statically, by ref, without running tests:
`graphify_semantic_corpus.py:752` sets
`semantic_slice_sha256=_module_sha(graphify_semantic_slice)`, and `_module_sha`
hashes the module's source file (`graphify_semantic_corpus.py:676-680`). This
commit changes that file — its sha256 at `a67cbac4` is
`bc3a588cff507001afe4c13f23dffca67b434ec39fd8434c7414a67569ad48d7` — while the
frozen `AUTHORITY_JSON` pins `execution_config_sha256` at
`83a1fc8da307c9f86daa414ff064b9135eda4066a54644ae9ce93230b635bc92`
(`graphify_semantic_corpus_authority.py:610-612`). So `execution_authorized` is
false at this SHA and that test is red, exactly as disclosed.

It is disclosed and deliberate, deferred to a whole-bundle re-plan, which is why
this is P1 and not P0. What still needs saying: `mise run kb-ship` runs
`mise run test` (`pytest -x`) and will refuse this HEAD, `zero-skip-policy.md`
forbids committing on a red gate, and any handoff or receipt that later cites
"full suite green" is citing a run that was never green *here*. The re-plan is
not optional cleanup — it is the thing that makes this commit shippable.

---

## P2

### P2-1 — Stale comment contradicts the constant five lines above it

`python/src/kb_setup/graphify_semantic_slice.py:328-332` still reads:

> `_ACCEPTED_…` above now reads 0.9.45 because the COMMITTED receipt was
> re-produced at 0.9.45 in the same change

`_ACCEPTED_GRAPHIFY_RUNTIME` at `:310-327` now reads **0.9.48** — advanced by
this very commit. The same comment block, at `:334-337`, states
`semantic_api_fingerprint()` "hashes to … 43122fca…", which this commit advanced
to `6047cf0e…` (`:513-515`). The second is corrected 60 lines later by the ⚠️
block at `:396-403`; the first is not corrected anywhere. A reader landing on
`:328` reads a false statement about the constant directly above it.

### P2-2 — `test_non_authority_path_accepts_the_current_graphify_runtime` became incapable of failing in this commit, and was not re-derived while its sibling was

`_ACCEPTED_GRAPHIFY_RUNTIME` (`:310-327`) and `_CURRENT_GRAPHIFY_RUNTIME`
(`:407-415`) are now **field-for-field identical** — version/cli/sdk `0.9.48`,
executable `.venv/bin/graphify`, `sdk_fingerprint_sha256` `b10406f9…`,
`wheel_sha256` `4f745d72…`, `sdist_sha256` `14eaac83…`. `RuntimeIdentity` is a
frozen `msgspec.Struct`, so equality is structural and `_ACCEPTED == _CURRENT`.

`_runtime_reasons` builds the non-authority tuple as
`(_ACCEPTED_GRAPHIFY_RUNTIME, _CURRENT_GRAPHIFY_RUNTIME)` (`:1427-1431`), which
is now `(A, A)`. So dropping `_CURRENT_GRAPHIFY_RUNTIME` from that tuple —
precisely the defect class the test's own docstring says it exists to catch
("the pair became unmatchable and the non-authority path rejected EVERY run
under the installed version", `tests/test_graphify_semantic_slice.py:1006-1014`)
— now **survives** `tests/test_graphify_semantic_slice.py:1003-1024`.

This commit re-derived the AUTHORITY sibling at
`tests/test_graphify_semantic_slice.py:1027-1050` for exactly this vacuity, and
even removed the vacuity guard that would have announced it — and left the
non-authority arm untouched. Same for `tests/test_graphify_semantic_slice.py:82`
(`_runtime_reasons(committed, enforce_authority=False) == []`), which can no
longer distinguish the two entries either.

Mitigating: `test_the_current_graphify_runtime_tracks_the_pinned_manifest_ref`
(`:1053-1090`) binds `_CURRENT_GRAPHIFY_RUNTIME.version` to
`sources/graphify.manifest`, so a stale `_CURRENT` is still caught. This is a
lost arm, not an open hole — but it is lost silently, which is the failure the
deleted guard existed to prevent.

### P2-3 — The two new "real `os.environ`" tests permanently delete host-ambient names that monkeypatch cannot restore

`tests/test_graphify_semantic_slice.py:256-275` plants only `AWS_REGION` and
`AWS_ACCESS_KEY_ID` via `monkeypatch.setenv` (`:269-270`), then calls
`scrub_route_overrides()` with **no argument** (`:271`) — which deletes all 37
forbidden names *present*, not just the two planted. On the host the commit body
itself describes (`env | grep -c '^AWS_'` = 4), `AWS_DEFAULT_REGION` and
`AWS_SECRET_ACCESS_KEY` are ambient, were never recorded by monkeypatch, and are
gone from the pytest process for the rest of the session.
`tests/test_graphify_semantic_corpus_run.py:719-746` does the same thing through
the real `execute()` (`:743`).

No live breakage today: `tests/test_graphify_env.py:95-96` plants its own
sentinels and `tests/test_model_limits.py:186,443` uses explicit dicts. But the
result of those two tests now depends on what ran before them, which is the one
property a test must not have. Scrub a `dict(os.environ)` copy, or
`monkeypatch.setattr(os, "environ", dict(os.environ))` first.

### P2-4 — Scrubbing the proxy variables changes the PARENT's egress, and the docstring's justification only covers the child

`graphify_semantic_slice.py:791-796` justifies removing
`HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY`/`NO_PROXY` as "what the child environment
allowlist (`claude_child_environment`) already did downstream of preflight".
That is true of the `claude` child (`:705-720` builds a closed allowlist) and
**not** true of this process: the scrub mutates `os.environ`, and
`_temporary_environment` (`:1651-1662`) *overlays* onto `os.environ`
(`os.environ.update(updates)`, `:1654`) rather than replacing it — so the
graphify SDK, the adapter subprocess, and the `git` processes `_admit_source`
drives (`:1671-1685`) all now run with no proxy configuration at all.

On a proxied host the old behaviour was a loud refusal; the new one is a silent
direct connection or an opaque clone failure. Not a defect on this host — an
unstated consequence, and the docstring currently reads as if it had been
considered and bounded.

### P2-5 — The scrub silently overrides `graphify_env`'s written "ANTHROPIC_* is KEPT" policy for any `clean_env()` built later in the same process

`python/src/kb_setup/graphify_env.py:21-24` states that `ANTHROPIC_API_KEY` /
`ANTHROPIC_BASE_URL` "are intentionally KEPT — that is the Claude path", and
`clean_env()` (`:85-89`) is documented as "Use for EVERY graphify subprocess"
and copies `os.environ`. After a scrub, that copy can no longer contain them,
because both names are in `_ROUTE_OVERRIDE_NAMES` (`graphify_semantic_slice.py:115,117`).

Not currently live — no `clean_env()` caller (`artifacts.py`, `citations.py`,
`currency/skill.py`, `graph.py`, `graphify_ops.py`, `launch.py`, `mcp_serve.py`,
`remember.py`, `tool_sync.py`) is reachable from `semantic_main` or `execute()`.
But two modules now state opposite policies about the same two variable names,
with nothing pointing either way, and the newer one wins by side effect.

---

## Nits

1. `tests/test_graphify_semantic_slice.py:256` —
   `test_preflight_passes_after_scrub_with_ambient_routing_names` **never calls
   `preflight`**; it asserts `route_override_names(os.environ) == ()` (`:275`).
   Its docstring calls itself "The end-to-end arm for #334" (`:260`). Both the
   name and the docstring will be read as evidence that the CLI path is covered.
   It is not (see P1-2).

2. `tests/test_graphify_semantic_slice.py:950` —
   `assert current.help_sha256 == _ACCEPTED_CLAUDE_HELP_SHA256` is true by
   assignment: `_CURRENT_CLAUDE_HELP_SHA256 = _ACCEPTED_CLAUDE_HELP_SHA256`
   (`graphify_semantic_slice.py:510`). The comment added above it
   (`tests/…:947-949`) says this "reads the REAL current help digest" — nothing
   in this module measures the installed binary at import time; both values are
   literals and one is an alias of the other. The assertion can fail only if
   `current_claude()` stops reading that global, which is not the claim the
   comment makes.

3. `graphify_semantic_slice.py:1904-1907` gives `build_candidate` its own scrub
   because it "is public and may be called directly", but
   `graphify_semantic_corpus_prototype.build_no_inference_preflight`
   (`python/src/kb_setup/graphify_semantic_corpus_prototype.py:360-373`) is
   equally public, calls `preflight` with `environment=None`, and got none. The
   commit-message claim "every CLI entry that reaches it" does hold —
   `cli.py:243-254` wires only `graphify-semantic-slice`,
   `graphify-semantic-corpus` and `graphify-semantic-corpus-merge`, and the
   prototype has no CLI entry — but coverage is by enumeration, so a fifth
   caller inherits the refusal rather than the mechanism.

4. `graphify_semantic_slice.py:387` (pre-existing, unchanged context adjacent to
   the diff) cites a test `test_non_authority_graphify_pairs_*` that does not
   exist: `git grep test_non_authority_graphify_pairs a67cbac4` returns only the
   comment itself.

5. `docs/agents/graphify-semantic-slice.md:88` says the blob is "byte-identical
   to the v0.9.42/v0.9.45 snapshots". The v0.9.45 half is verified by ref
   (`git show 8929d47f:graphify-out/graphify-semantic-slice/manifest.json`
   carries the same `git_object` `e0e6e527…`, `sha256` `cd4a6700…`, `size` 5147).
   The v0.9.42 half is **UNVERIFIED** here — it is carried forward from the
   comment this commit rewrote, and the pinned clone was not read.

---

## What I checked and found clean

- **Manifest digest matches the constant.**
  `git show a67cbac4:graphify-out/graphify-semantic-slice/manifest.json | shasum -a 256`
  → `61006e39d3d6ea20e1bb41deff64ff3cffbcf1894db92920a9006924c19f4cc9`, exactly
  `_ACCEPTED_CANDIDATE_MANIFEST_SHA256` (`graphify_semantic_slice.py:62`).
- **Every manifest member is self-consistent.** Recomputed all four:
  `adapter-metadata.json` `7d37afd7…`/2630, `provider-boundary-start.json`
  `d8755205…`/427, `receipt.json` `fcb75200…`/3124, `semantic-fragment.json`
  `5559be9c…`/7337 — each matches the size and digest recorded in
  `manifest.json`.
- **Receipt agrees with every advanced constant.** `receipt.json` `runtime`:
  version `2.1.238` = `_ACCEPTED_CLAUDE_VERSION` (`:437`); `executable_sha256`
  `1c196c45…` = `:439-441`; `help_sha256` `71ad650f…` = `:442`;
  `graphify_runtime` 0.9.48 + `b10406f9…`/`4f745d72…`/`14eaac83…` =
  `_ACCEPTED_GRAPHIFY_RUNTIME` (`:310-327`);
  `graphify_semantic_fingerprint_sha256` `6047cf0e…` =
  `_ACCEPTED_SEMANTIC_FINGERPRINT_SHA256` (`:515-517`); `execution_config`
  matches `_ACCEPTED_EXECUTION_CONFIG` field-for-field (`:518-532`).
- **Source identity agrees three ways.** `SOURCE_REF`/`SOURCE_COMMIT`/
  `SOURCE_TREE` (`:46-48`) = `manifest.json.source` = `receipt.json.source` =
  `sources/graphify.manifest` (`ref = v0.9.48`,
  `commit = b2cd36267456c166788c95be6e68574064a92a42`). `SOURCE_GIT_OBJECT`/
  `SOURCE_SHA256`/`SOURCE_SIZE` are unchanged from the base commit's manifest,
  so the "byte-identical input" claim for v0.9.45 → v0.9.48 is measured, not
  asserted.
- **Counts agree end to end.** `semantic-fragment.json` has 18 nodes / 17 edges
  / 2 hyperedges; `receipt.json` records the same; `adapter-metadata.json`
  records attempt 1, `num_turns` 3, `stop_reason` `tool_use`, `result_subtype`
  `success`, `terminal_reason` `completed`, `stderr_size` 0,
  `permission_denial_count` 0, `total_cost_usd` 0.0556709; and
  `docs/agents/graphify-semantic-slice.md:24-25,85-98` states every one of those
  correctly. `tests/test_graphify_semantic_corpus.py:2368`'s re-derived
  `(18, 17, 2)` is consistent with the retained fragment.
- **Deleting the ref-binding exemption is sound, and was checked the hard way.**
  All eight graphify `ref_binding` rows in `currency.toml:134-186` now agree
  with the manifest: `graphify_baseline.py:228,262`,
  `graphify_semantic_corpus.py:120-121`, `graphify_semantic_slice.py:46-47`,
  `sources/graphify.dispositions.json:4-5` are all `v0.9.48` /
  `b2cd3626…`. The new plain assertion
  (`tests/test_currency_ref_bindings.py:349`) can therefore fail on a real
  future drift, and the zero-bindings vacuity it no longer guards against is
  covered by `tests/test_currency_ref_bindings.py:265`
  (`assert spec.ref_bindings`).
- **No stale copies of any superseded value survive.** `git grep` over the whole
  tree at `a67cbac4` for the previous manifest digest `4621b26e`, and for the
  base evidence digests `ee547d04` / `411ca685` / `a1fce9fa` / `e0d7d6e1`,
  returns **zero** hits. `graphify_semantic_corpus_authority.py` already carries
  2.1.238 and `6047cf0e…` (`:512-544`); its `43122fca` occurrences are
  historical narrative only.
- **`scrub_route_overrides` itself is correct.** It materialises the name tuple
  before deleting (`:805-808`), so it cannot raise "dictionary changed size
  during iteration"; it never reads a value; it is genuinely idempotent; the
  docstring's "37-name set" is accurate (counted: `_ROUTE_OVERRIDE_NAMES` has
  exactly 37 members, `:113-152`); and `MutableMapping` (`:16`) is the right
  annotation for a mapping it mutates, with `os.environ` satisfying it.
- **The refusal itself was not weakened.** `_ROUTE_OVERRIDE_NAMES`,
  `route_override_names` (`:773-775`), `preflight`'s raise (`:948-950`) and the
  adapter's independent check (`graphify_semantic_adapter.py:721`) are all
  untouched by this diff; the child environment remains a closed allowlist
  (`:705-720`), and `_adapter_environment` (`:1766-1812`) still builds a fixed
  dict rather than inheriting. Nothing here can route the corpus to a non-Claude
  backend — the loss is refusal and auditability (P1-1), not routing.
- **ty-style unreachable-code shape:** the only "unreachable" I can substantiate
  is *runtime* unreachability of `graphify_semantic_slice.py:950` (P1-1), not a
  static one. I found no lexically-unreachable statement introduced by the diff:
  the scrub calls at `:1907` and `:2042` and
  `graphify_semantic_corpus_run.py:1043` all precede live code, and
  `target = os.environ if environment is None else environment` (`:805`) narrows
  cleanly. **UNVERIFIED by tooling** — I did not run `ty`, since the gate
  commands are hook-redirected and I was scoped to read-only inspection.
- **Docs internal consistency:** `docs/agents/graphify-semantic-slice.md` has no
  surviving reference to 0.9.42/0.9.45 or 2.1.232/2.1.233 — frontmatter (`:3`),
  prose (`:9`), both mermaid diagrams (`:17,24,25,45`) and the retained-result
  section (`:83-98`) are all current and all agree with the committed evidence.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under review; read entirely by git ref at `a67cbac4` and `8929d47f`.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — referenced only through this repo's committed pin (`sources/graphify.manifest`, `v0.9.48` / `b2cd3626…`); its own source was NOT fetched or read.
