> **PROMOTED VERBATIM from `.agent/kb/reports/agents/2026-08-21-session-review/`.**
> `.agent/` is gitignored and dies to any `git clean -xdf`; issues #426, #427, #423,
> #424 and #425 cite this document, and a citation only one machine can open is not a
> citation.
>
> ⚠️ **READ `2026-08-21-session-review-completeness.md` FIRST.** The critic found this
> document's own headline arithmetic wrong in the direction that flatters it (150 claims
> and 115 unverified, not 155 and 103) and found three gate items resting on claims that
> never passed an adversarial check. Not normalised or corrected here — promotion is
> verbatim, and the correction lives in the critic.

# Readiness gate for the graphify deep extraction

**Synthesis of the 2026-08-21 session review** — 7 lanes, 155 collected claims, 35 adversarially
verified (26 CONFIRMED, 9 REFUTED), 103 reported unreached by the per-lane verification cap.
Window: 2026-08-17 20:07 .. 2026-08-21, 14 sessions, 94 Ray messages.

Ray's question, verbatim:

> "make sure we have all pending issues/missing requirements ready before the full deep extraction
> and reflection and generated artifacts on the graphify cloned repo pinned to the latest graphify
> version. Especially the requests i made regarding tracking model/effort on each file extracted so
> we have a history of it when we have to rerun it on newer graphify releases and automating the
> process"

So this document is a **gate**, ranked by cost of getting it wrong, not by effort.

## The three sentences that matter most

1. **The plan says `execution_authorized: true` and will burn ~$65 and ~10.6 hours producing 58
   failed chunks**, because `_ACCEPTED_GRAPHIFY_RUNTIME` is still `0.9.47` while `0.9.48` is
   installed and the equality check that catches it runs *after* the money is spent (ER-01,
   CONFIRMED, **unfiled**).
2. **#411 does NOT have to be built first.** Two independent verifications refute the blocking
   framing: the per-chunk retained argv already records `--effort high` and `--model claude-opus-5`
   verbatim, and `graphify_semantic_corpus_authority.py:9` states the level in prose. The one thing
   that is genuinely unrecoverable-if-skipped is a single typed `effort` field in
   `CorpusExecutionConfig` (ER-04, RR-04). Ray's own ruling — *design + issue now, build as its own
   reviewed change, immediate run carries a minimal inline record* — stands and should be executed
   as written.
3. **#397 (kb-build RED) does not block the extraction RUN. It blocks the MERGE and the artifacts.**
   The corpus run reads `sources/graphify` at the pin, not `graphify-out/graph.json` (ER-10). This
   reorders the whole round: legs 1 and 2 of Ray's goal can proceed; leg 3 cannot.

---

## 1. THE GATE

Ordered by cost of getting it wrong. "Dep" names what must land first.

### G1 — `_ACCEPTED_GRAPHIFY_RUNTIME` is frozen at 0.9.47 while 0.9.48 runs · **NEEDS FILING** · dep: none

**Cost of getting it wrong: ~$65 and ~10.6 hours spent, 58/58 chunks staged `failed`, and nothing
warns you first.** `mise run kb-graphify-semantic-corpus verify` returns rc=0 with
`execution_authorized: true`, `reasons: []`. But `graphify_semantic_corpus.py:185-194` declares
version/cli_version/sdk_version `0.9.47` + wheel `2a8b13cc…` + sdist `26e5766f…`, while
`graphify_baseline.runtime_identity(Path('.'))` measures `0.9.48` / `4f745d72…` / `14eaac83…`.
The verifier called `_provider_runtime_reasons(<live preflight>, <committed config>)` directly and
got `['provider-graphify-runtime-mismatch', 'provider-graphify-version-mismatch']`;
`stage_chunk` (~:2240) sets `status="failed" if reasons else "complete"`. `execute()` computes the
preflight receipt at `graphify_semantic_corpus_run.py:1041` and **never compares it to
`config.graphify_runtime`** — the only post-preflight identity check is the Claude executable
(:447). Re-planning does not fix it: `_effective_config` (:746-747) reads the same constant.

Fix: re-**measure** the three digests from `graphify_baseline.runtime_identity` (do not transcribe
them from this report), edit `:185-194`, then re-plan once. Two things that are **not** stale and
must not be "fixed": `_ACCEPTED_GRAPHIFY_DETECT_OBJECT = d16b5800…` (the detect.py blob is
byte-identical at v0.9.47 and v0.9.48) and `review_status = "provisional"` on the cost advisory,
which `_advisory_reasons` (:1504) *requires*. `claude_version` already matches at 2.1.238.

This is the **third** 0.9.47 straggler and a natural sibling of #421 (which covers two different
ones); `gh search issues "_ACCEPTED_GRAPHIFY_RUNTIME"` returns only #378, control-armed.

### G2 — `graphify_semantic_slice.py` binds v0.9.45 / `0738af37` · **NEEDS FILING** · dep: fix in the SAME change as G1

**Cost of getting it wrong: fixing it after the run un-authorises the plan the run was executed
under** — the graphify circle, mechanically. `_effective_config` sets
`semantic_slice_sha256 = _module_sha(graphify_semantic_slice)` (`graphify_semantic_corpus.py:752`),
`_module_sha` hashes the module's **source bytes** (:676), and that digest is inside the cache
namespace (`cache_namespace_for`, :705-712). `graphify_semantic_corpus_authority.py:413` records
this having already fired twice on comment-only edits, and :469 records the authority block being
re-recorded 2026-08-20 for the 0.9.47→0.9.48 bump — so the plan is authorised against the *current*
slice bytes. Any edit now stales it.

`mise run kb-currency-check` names it verbatim: slice `:44 SOURCE_REF = "v0.9.45"`, `:45
SOURCE_COMMIT = "0738af37…"` against `sources/graphify.manifest` `v0.9.48` / `b2cd3626…`.
Control-armed: 2 of 10 declared ref-bindings are flagged; `graphify_baseline.py:228` and
`graphify_semantic_corpus.py:120-121` already read 0.9.48.

**Scope correction the lane raised and I am carrying forward:** `SOURCE_REF` is not a version pin —
it is the snapshot identity of one evidence file (`SOURCE_PATH = "docs/how-it-works.md"`) travelling
with SOURCE_TREE / SOURCE_GIT_OBJECT / SOURCE_SHA256 / SOURCE_SIZE. Fixing it means re-deriving those
digests at v0.9.48 and re-attesting the slice if the blob moved, not a two-line text bump.

**G1 + G2 + G5's effort field must be ONE change followed by ONE re-plan.** Three separate edits
mean three re-plans and three re-authorisations.

### G3 — 571,462 tokens (55.1%) of the plan is byte-identical re-extraction · **#414** · dep: must precede the re-plan

**Cost of getting it wrong: ~$36 of the ~$65, unrecoverable the moment the run starts.**
Re-derived from `source-inventory.json` (not from the issue text): 1,038,052 estimated tokens,
113 distinct parent files, 28 parent hashes reachable at >1 path; deduped 466,590; **saved 571,462 =
55.1%**. Worst families reproduce exactly — `graphify/skill-claw.md` ×10 (103,910),
`skills/*/references/query.md` ×29 (101,326), `update.md` ×29 (77,749).

The only duplicate check in the planner is `graphify_semantic_corpus.py:1452-1454`, keyed on
`(unit.path, unit.slice_index)` — structurally unable to see cross-path byte-identical content.
`grep -c "dedup"` over that module → 0 with control arms `def ` → 82, `estimated_tokens` → 11.
`exclusions.json` holds 4 entries, all binary visuals; none of the 28 families.
Nothing is spent yet: `graphify-out/graphify-semantic-corpus-chunks/` does not exist.

Note the method trap recorded during verification: grouping by *unit* gives a false 75.5% because
units are slices (`CHANGELOG.md` is 23 slices at one path). Group by distinct **path**.

### G4 — four ambient `AWS_*` names make the run refuse at preflight · **#334** · dep: none

**Cost of getting it wrong: zero dollars, total blockage.** It fails closed, which is correct — but
the run cannot start on this machine as configured. `env | grep -c '^AWS_'` → 4, surviving
`mise exec -- env` (control: `grep -c '^PATH='` → 1).
`graphify_semantic_slice.preflight(...)` raises
`ValueError: forbidden routing environment names: AWS_ACCESS_KEY_ID, AWS_DEFAULT_REGION, AWS_REGION,
AWS_SECRET_ACCESS_KEY`; the same call under `env -u …` returns a receipt reporting 0.9.48. Both arms
ran. `preflight` is the third statement of `execute()`, un-wrapped, so nothing is spent.

Two traps for the fix: (a) `clean_env()` returns a dict for a **subprocess** env and does not mutate
`os.environ`, so "call clean_env here" does not work — it must be passed as preflight's
`environment=` argument, or the vars must be absent from the task's own process env; (b) copying
`mise.toml:936`'s `AWS_REGION = ""` idiom does **not** clear it, because `route_override_names`
matches by NAME and an empty string still satisfies membership. `do-not.md` #4's cleaner is
control-armed absent from this path (`grep -c clean_env` → 0/0/0 against
`cache_namespace_sha256` → 4/21/0).

### G5 — #411's disposition: DESIGN suffices, but ONE field must land pre-run · **#411** · dep: bundle with G1/G2

**This is the item Ray named explicitly, and the answer is: do not build it first.**

The blocking framing is refuted twice over:
- `ChunkStageReceipt.source_paths` × `AdapterMetadata.argv` yields model+effort **per file** after
  the fact, for zero extra tokens. `graphify_semantic_slice.py:742` appends
  `("--effort", profile.effort)` to argv; `stage_chunk` (:2203-2277) writes `adapter-metadata.json`
  into each chunk directory **unmodified**; `.gitignore:63-69` deliberately does not ignore
  `graphify-out/graphify-semantic-corpus-chunks/` (#317).
- `--effort` is in `_CLAUDE_REQUIRED_FLAGS` (:233-236), compared for **equality** against the
  receipt, so a run that failed to pass it fails loudly rather than silently defaulting.
- `graphify_semantic_corpus_authority.py:9` and :89 state "extracted by `claude-opus-5` at
  `--effort high`" in prose, in a review-owned committed file.

**What must still land before the run:** `CorpusExecutionConfig` (:382-441) has no typed `effort`
field. Probed: effort-keys in the committed `execution-config.json` → `[]`, controls `deep_mode`
and `max_turns` present; the only `effort` string is the flag NAME in `claude_required_flags`,
which asserts support, not value. One field. Add it, then re-plan (which is why it bundles with
G1/G2).

**What #411 should be built as, later:** a per-`(source, content-sha256)` ledger. The raw material
already exists — `SourceUnit` carries `sha256`, `parent_sha256`, `source_git_object`, `slice_*`,
`estimated_tokens` (:277-292); `ChunkMember` carries `sha256` (:354-362); `chunk_sha256` binds the
member hashes and `execution_config_sha256` binds the model. It is a **join over artifacts that
already exist**, plus two genuinely missing inputs: the effort value, and rows for the
SKIPPED/EXCLUDED files with their reason.

Also fold in here: the **claude version is an extraction-provenance field** (`shutil.which("claude")`
at `graphify_semantic_corpus_prototype.py:138`, `claude_executable="claude"` at
`graphify_semantic_adapter.py:759`), and `currency.toml:843-844`'s claim that it "is not a thing this
repo can or should do" to pin is half false — `mise ls-remote claude-code` resolves and lists
2.1.238 (controls: `gh` resolves, `git` errors). Only the "should" survives. That disposition belongs
to #411, not to a new issue (UT-05).

### G6 — the run is unbounded, has no cache read, and its cap tolerates ~one interruption · **NEEDS FILING** · dep: none

**Cost of getting it wrong: an interruption past chunk ~31 makes the authorized plan
UNCOMPLETABLE inside its own cap**, requiring a fresh authorization — i.e. another turn of the
graphify circle.

Three verified facts compose into one risk:
- **No task bound.** `[tasks.kb-graphify-semantic-corpus]` (`mise.toml:669-671`) declares no
  `timeout`. Exactly 8 tasks do (lint 20m, test 25m, eval 25m, kb-build 180m, kb-transcribe 120m,
  kb-artifacts 60m, brain-audit 10m, hk-test 10m) — while `CLAUDE.md:176` says "7". The claim's
  superlative was **refuted**: 9 tasks lack the key (kb-add, kb-merge, kb-prose, kb-label, kb-update,
  kb-watch, kb-graphify-semantic-slice, kb-session-reflect, kb-graphify-semantic-corpus-merge), and a
  per-call ceiling *does* exist (`GRAPHIFY_API_TIMEOUT`, 900 s per Ray's ruling at
  `graphify_semantic_corpus_authority.py:249`; #335 is the adjacent open issue). The gap is the
  10.6-hour **wall clock**, not the call.
- **No cache read on this path, re-derived at 0.9.48** (not inherited from the 0.9.45-era comment):
  `load_cached` call sites are `cache.py:1236`, `cache.py:1519`, `extract.py:5279`,
  `extract.py:5575` — none in `llm.py`. Control arm: the WRITER `_checkpoint_chunk` (`llm.py:2571`)
  IS on `extract_corpus_parallel`'s chain, called at :2628 and :2653. The cache is **write-only** on
  this route. Resume re-publishes correctly (`_verified_stages`, `corpus_run.py:958`, disposes
  `repaid`) but **pays again**.
- **Cap arithmetic.** `max_total_cost_usd = 100.0`; chunk 1 measured 1.12 USD (:421-425);
  58 × 1.12 = 64.96. A restart after chunk N costs 1.12N + 64.96, so N > 31 exceeds the cap.
  Spend itself is genuinely well-built — `SpendLedger` persists per charge, `seeded_spend` refuses
  before the first provider call, `completeness_rc` checks `halted` first — which is why the failure
  mode is *refusal*, not overspend.

Action before the run: declare a task `timeout`; drive it as a **tracked background run with in-turn
polling** (the Bash tool caps a single call at ~600 s, and a `&`-detached local `mise run` gets
reaped); and either raise the cap to cover one full restart or restate it per-release.

### G7 — kb-build is RED, is in no gate, and the merge target is 8.6 days old · **#397 / #409** · dep: G1-G6 for the RUN; blocks the MERGE + ARTIFACTS legs

**Ordering correction, and it is load-bearing:** the corpus run needs only `sources/graphify` at the
pin (HEAD `b2cd3626…`, tree `be863673…`, matching the accepted constants). It does **not** read
`graphify-out/graph.json`. What requires a green build is the step *after*:
`graphify_ops.merge_chunk` merges INTO `graphify-out/graph.json` (`graphify_ops.py:207, :236`), so
merging onto an 8.6-day-old unstamped artifact produces an aggregate no `kb-build` reproduces —
Invariant 3 / `clean-git-state.md`.

State: `graphify-out/.currency-stamp.json` **does not exist** (control: 8 other dotfiles list fine);
`.build-failure.json` records `2026-08-20T21:20:51Z`; `graph.json` mtime `2026-08-12 06:12` — so
every `kb-query` this round, including the ones `graph_first` DENIES you into running, answered from
a graph 8.6 days stale. `kb-build` is absent from `GATE_TASKS` (`gates.py:139`) and from `pr.py`
(control-armed), so nothing on the ship path asks whether the corpus reproduces.

**The cause has moved and #397's body is stale on it.** `.build-failure.json` shows stage `build`
with `IncompleteGraphifyOperationError … 11 file(s) had syntax errors … c/backend_cuda.cu`, which
resolves to `sources/colibri/` (control: the same `find` locates `sources/graphify/graphify/detect.py`).
`.agent/kb/detect-census-397.json` shows `unclassified-files` gone entirely; the anthropic-sdk-python
detect failure that #397 was filed for is **fixed**, and the live blocker is #409's extract-stage
warning inventory. #397's criteria 1 (release-tag pins) and 2 (a branch-head gate) remain untouched:
52 of 73 manifests pin `main`/`master`/`HEAD`, and `manifest.py:245` defaults `ref: str = "main"`, so
the happy path *mints* new violations. Nobody has re-run kb-build since colibri was skipped, so
"is it green now" is **UNMEASURED**.

### G8 — the skip register is 3 sources out of date and its stated invariant is false · **#417** · dep: none

**Cost of getting it wrong: a coverage debt that reads as a fix.** Five manifests carry
`build = skip` — codebase-memory-mcp, GitNexus (registered), plus **codegraph, codex, colibri**
(not registered). #417 says verbatim "Every entry below is `scope = study` so far. If that stops
being true, the entry says so in bold." It has stopped being true:
`sources/codegraph.manifest` is `scope = corpus` and its own skip_reason says "scope=corpus, so this
IS aggregate loss"; `sources/codex.manifest` carries **no `scope` line at all** and its skip_reason
says the corpus "cannot describe a tool we run while this holds" — while `ai-cli-invocation.md`
names codex as a live lane. Update #417; do not file a new one. Each skip is a source the deep
extraction will not cover.

### G9 — every tracked file under `sources/**` is invisible to the secret scanners · **NEEDS FILING** · dep: none

**Cost of getting it wrong: a credential committed into corpus content, which is precisely what
happened once already** (`hk.pkl:113-117`: a `graphify-out/memory` file arrived 2026-07-28 carrying
three live credentials). The deep extraction writes chunks and evidence into exactly this surface.

Proven by evaluation *and* by a live two-armed planted-secret run in a scratch repo with the real
`hk.pkl` and hk 1.56.0: identical RSA key bytes in `sources/planted.json` and
`docs/planted_control.md` → only the control was flagged, rc=1. Same for gitleaks with an AWS token.
In the real repo, `hk check --all --step detect_private_key` reports 856 files; `git ls-files` = 996
and `git ls-files sources/` = 140 — 996 − 140 = 856 exactly.

The defect is not just the exclusion, it is that **`hk.pkl:200-203` asserts the opposite**:
"gitleaks, `detect_private_key` and the structural checks still read every one of these files, which
is what keeps an exclusion this wide tolerable." `hk.pkl:72` puts `sources/**` in `baseExclude`,
`:103` is `exclude = baseExclude`, `pkl eval -x 'exclude' hk.pkl` lists it at entry 17, and both
scanner steps evaluate to `exclude = List()` (no override). `check_merge_conflict` is blind too —
one more than the claim stated. The prose was added 2026-08-17 "approved by Ray" as the remedy for
the `--no-verify` incident (SC-09) and is a false-safety artifact. #94 states the underlying
blindness but is **CLOSED NOT_PLANNED** (2026-08-02) and predates the comment.

### G10 — currency reports four live drifts and exits 0, and currency is in no gate · **NEEDS FILING** (gate) + **#397/#225/#357/#383** (the drifts) · dep: none

Ray's 2026-08-18 directive made currency a hard gate. It is not one: `currency` is absent from
`GATE_TASKS` (control: `grep -c currency gates.py` → 7, all "concurrency"/rule-name prose;
`grep -c lint` → 22). `mise run kb-currency-check` prints drift and returns **rc=0** by design.
At `9dfc1255` all six gates recorded rc=0 while these stood: graphify **ref-binding** (G2),
graphify **build-stamp** (G7), **mise:version** (PATH 2026.8.10 vs reviewed 2026.8.9), **mise:manifest**
(`sources/mise.manifest` pins v2026.8.9) — plus skillopt reported UNKNOWN, "not a pass".
The mise bump is a **3-file** change, not 2: `currency.toml:598`, `sources/mise.manifest:39-40`, and
`mise.toml:40 min_version = { hard, soft }` per Ray's standing "min_version.hard MOVES" ruling.

Deciding whether `kb-currency-check` becomes blocking is a **Ray question**, because CLAUDE.md
currently documents the opposite ("always exits 0 and can never serve as a CI gate"). See §6.

---

## 2. AUTOMATION

### 2a. What the re-run on a NEW graphify release must look like

Ray's question is the delta question. Four requirements; **three unmet**.

| # | Requirement | State |
|---|---|---|
| 1 | A per-`(source, content-sha256)` ledger with model, effort, deep_mode, max_turns, and **rows for skipped/excluded files with reasons** | **absent** — #411, designed only. Raw material present (`SourceUnit.sha256`/`parent_sha256`/`source_git_object`, `ChunkMember.sha256`); missing inputs are the effort value (G5) and the skip rows |
| 2 | A cache **READ** on the execution path, or a delta is a planning-side saving only | **absent at 0.9.48**, re-derived. If a future graphify adds one, `corpus_run.py:882-893` says **re-derive it** rather than trust the name |
| 3 | The version constants move as a **SET** | **failed this release.** `_ACCEPTED_GRAPHIFY_REF/_COMMIT/_TREE` moved; `_ACCEPTED_GRAPHIFY_RUNTIME` (G1) and the slice binding (G2) did not. This is the whole reason the plan is authorized-but-doomed |
| 4 | A cap sized for at least one full re-run, or restated per release | **not sized** — $100 vs $64.96 with no cache read (G6) |

**The delta mechanism, concretely.** With #411's ledger keyed on content hash, a new release's run
is: re-plan → for each unit, look up `(source, sha256)` in the ledger → if present AND the recorded
`(model, effort, deep_mode, max_turns, graphify_runtime_compatible)` still satisfies the new plan,
carry the prior fragment forward and mark the unit `inherited`; otherwise extract. Requirement 2 is
what makes that a *cost* saving rather than only a *coverage* saving — without a cache read, an
inherited unit still has to be re-published from the prior chunk directory rather than re-bought,
which is exactly what `_verified_stages`/`_resolve_existing_stage` already do for a *resume*. So the
cheapest honest path is: **#411's ledger + reuse the existing `repaid` disposition machinery**,
rather than waiting on graphify to add a cache read.

**The free gate this release did not have:** compare `_ACCEPTED_GRAPHIFY_RUNTIME` against
`graphify_baseline.runtime_identity()` **at plan time**. Today the only comparison is at chunk-stage
time, after the money is gone. That single assertion turns G1 from a $65 loss into a plan refusal.
File it with G1.

### 2b. What should become skill → mise task → kb_setup module

Verification changed three of the five proposals. Ranked by evidence quality:

**BUILD IT — PR bot-review harvesting.** 64 `gh api .../pulls/N/(comments|reviews)` calls across 6
sessions, **63 of 64 command strings distinct**, across 11 PRs; `--jq` in 60; body truncation
re-chosen per call (`.[0:N]`, N ∈ {90,130,150,170,900}). The decisive datum: `reviews` 46 /
`comments` 41, and **only 20 of 64 touch BOTH** — exactly the split that let three graphify-labs
reviews go unread while a supply-chain regression merged
(`docs/direction/2026-08-19-ray-directives.md:161-166`). **Already specced as #380**, which is a
strict superset (four surfaces, UNREAD-vs-zero, per-bot priority, a `kb-land` gate). Fold the
`--new-only` dedupe parameter into #380; do **not** file `kb-pr-comments`. One correction: only 29
of 64 carry a `head`/`tail` bound, not "each".

**GUARD IT — the python-heredoc file edit.** 222 `read_text()…write_text()` heredocs across
**14 of 14 sessions**, 64 `sed -i ''` across 9, and 61 hand-written `assert t.count(old) == 1`
uniqueness guards that the Edit tool provides free. 203 of the 222 are `uv run python`, which
`hook_guard`'s `_BARE_PYTHON` explicitly does not touch (`hook_guard.py:165-167`). This earns **no
new layer** — building `kb_setup.edit` would be `use-tool-builtins.md`'s own anti-pattern. It earns
a **deny**, and it is already **#239 (OPEN)**, whose predecessor **#342 was CLOSED at 20
occurrences without the guard ever shipping**. The durable finding is not the 222; it is
20-in-one-session → 222-in-fourteen after closure.

**COMPLIANCE, NOT AUTOMATION — the cold-review lane launch.** The proposal to build a lane module is
**refuted**: `ai-cli-invocation.md:57-61` prescribes `antigravity:delegate|review|research`
("the plugin owns the invocation shape"), `kb-review/SKILL.md:122-126` names
`fable-orchestrator:codex-reviewer` / `antigravity:review` per implementer family, and both are
installed on disk (`antigravity/0.23.0/commands/review.md:14-15` already wraps the call). Building a
`kb_setup` lane launcher would displace an existing tool feature. Counts also did not reproduce
(24 `agy` / 10 sessions and 12 `codex exec` / 7, not 76/7 and 22/6). The real finding is
**the prescribed lane is bypassed 24+ times**, with observable cost: three different flag spellings
probed before one worked, and `--mode plan` used twice against the standing note that it blocks
incremental write. Reframe and file as a compliance/enforcement item.

**REFUTED — lane liveness polling.** `pgrep` is 44/6, not 48/8; **37 of the 44 poll local background
bash jobs** (`kb-setup arms` ×12, `update_claude.py` ×13, `kb-gates` ×7, `bun install` ×5) that
ListAgents cannot observe by design, 3 are MEMORY.md prose, and only **4** target a delegated AI
lane. The ListAgents baseline (4/3) was measured from a bash-command corpus that structurally cannot
contain tool calls — all 4 "hits" are prose. And the auto-memory that would be violated
(`subagent-liveness-comes-from-listagents.md`) was **authored by** session 6b974f05, whose 14 polls
are its origin, not a repeat. Post-lesson delegated-lane pgrep: 2 calls, 1 session. No layer earned.

**REFUTED AS FRAMED — a `kb-issue` task.** All headline numbers reproduce exactly (57 `gh issue
create` / 11 sessions, 216,740 chars, median 3,798) but the premise does not: there are **248
distinct `##` headings across 360 occurrences, 224 of them appearing exactly once**; the 7 "skeleton"
headings cover 24%. Heading lines are 5.2% of the total and non-body scaffolding 13.0%, so the
savings are ~5-13%, not ~54k tokens. Also: 46 of 57 use a heredoc (not all), 34 already pass
`--body-file`, and those 57 commands contain **76** invocations. The narrow residue is real and
untracked — nothing owns issue filing, no `ISSUE_TEMPLATE` exists, and the evidence-anchor rule is
enforced by discipline alone — so file it in that narrowed form, without the token argument.

**PARAMETER, NOT TASK — human-message extraction.** `kb_setup/session_select.py` already resolves the
session set and parses transcripts but has no message-emitting path (grep for
`human|user_message|--messages` → only `def main` at :505). Once #401 lands and `/clear-prep` runs
session-review every round, this lane's own one-off `humans/` extraction becomes a per-round step.
Add `--emit-human-messages <dir>` to the existing module rather than forking session resolution.

### 2c. The measured drift-away-from-existing-automation

From `mise run kb-session-reflect -- --sessions 14`, and this is the honest denominator for
everything above: **piped-rc ×91**, bare-interpreter ×34, relative-cd ×8, and **91 of 105 greps
stood with no control arm**. Graph-first is the one healthy rate (20 queries vs 12 direct reads).
Independently, gate invocations piped into `head`/`tail`/`grep`: **351 piped vs 74 unpiped** across
the 14 sessions — worse than the 311/150 originally claimed, and worse than every prior measurement
of the same class (35 → 12 → 351). Armed both directions in zsh 5.9: `kb-check` on a broken file
unpiped → rc=1; the same command `| tail -3` → rc=0; control on a clean file → rc=0. Mechanism
confirmed in source: `check_first` and `hook_guard` both **allow** `mise run kb-check … | tail -3`,
because `mise-tasks-only.md:89` whitelists anything containing `mise run kb-`. **Already #348
(OPEN, P0)**, which specifies exactly the widening. Comment the 351/74 onto it.

So: the round's problem is **not mainly missing automation**. It is four genuinely un-owned
workflows (bot harvesting, heredoc guarding, lane compliance, issue filing) beside a large volume of
drift away from automation that already exists and, in three cases, is already filed as P0.

---

## 3. NEEDS FILING

Nothing here is already tracked. Bodies are file-ready.

### F1 — `_ACCEPTED_GRAPHIFY_RUNTIME` is frozen at 0.9.47 while 0.9.48 runs: the plan verifies AUTHORIZED and every chunk will stage `failed`

`python/src/kb_setup/graphify_semantic_corpus.py:185-194` declares version/cli_version/sdk_version
`0.9.47`, wheel `2a8b13cc…`, sdist `26e5766f…`, while `graphify_baseline.runtime_identity(Path('.'))`
measures `0.9.48` / `4f745d72…` / `14eaac83…`. `mise run kb-graphify-semantic-corpus verify` returns
rc=0, `execution_authorized: true`, `reasons: []` — nothing warns. Calling the gate directly with
the live preflight receipt returns `['provider-graphify-runtime-mismatch',
'provider-graphify-version-mismatch']`; `_provider_evidence_reasons` (:1893) feeds `stage_chunk`
(~:2240), which sets `status="failed"` when reasons are non-empty. `execute()` computes the preflight
receipt at `graphify_semantic_corpus_run.py:1041` and never compares it to `config.graphify_runtime`;
the only post-preflight identity check is the Claude executable (:447). So the run pays for all 58
chunks (`chunk-ledger.json`; ~$1.12/chunk per the comment at :421-425, ≈$65) and stages 58 failures.
Re-planning does not fix it — `_effective_config` (:746-747) reads the same constant. The
constant's own comment (:189-190) says it is "MEASURED rather than carried forward", i.e. it tracks
the installed runtime and should have moved with `graphify_semantic_slice._CURRENT_GRAPHIFY_RUNTIME`,
which *was* advanced to 0.9.48. No test covers it: `grep -rn ACCEPTED_GRAPHIFY_RUNTIME tests/` returns
two hits, both slice-scoped, and `test_only_the_frozen_receipt_bindings_may_lag_the_manifest`
(`tests/test_currency_ref_bindings.py:323`) scopes its exemption to the slice module. This is a third
0.9.47 straggler, sibling of #421 (which covers `sources/graphify.dispositions.json:91` and
`graphify_baseline.py:266-290`). **Acceptance:** (1) the three digests are re-measured from
`graphify_baseline.runtime_identity`, never transcribed; (2) a **plan-time** assertion compares
`_ACCEPTED_GRAPHIFY_RUNTIME` to `runtime_identity()` and refuses the plan, so this class costs a
refusal instead of $65; (3) a test arms the FAIL direction by pinning a wrong version and confirming
`plan` refuses. Do **not** touch `_ACCEPTED_GRAPHIFY_DETECT_OBJECT` (`d16b5800…` is byte-identical at
both tags) or `review_status = "provisional"` (required by `_advisory_reasons`, :1504).

### F2 — `graphify_semantic_slice` still binds v0.9.45 / `0738af37`, and fixing it after the run un-authorises the plan

`mise run kb-currency-check` reports: `graphify_semantic_slice.py` `(ref)` reads `v0.9.45` but
`sources/graphify.manifest` pins `v0.9.48`; `(commit)` reads `0738af373af9cf5c95f862cc5f3327fd96b4ea23`
but pins `b2cd36267456c166788c95be6e68574064a92a42` (`:44`, `:45`). Committed state, not a dirty tree.
Control-armed: 2 of 10 declared ref-bindings are flagged; `graphify_baseline.py:228`,
`graphify_semantic_corpus.py:120-121` and `sources/graphify.dispositions.json:4-5` already read
0.9.48. The ordering constraint is mechanical: `_effective_config` sets
`semantic_slice_sha256 = _module_sha(graphify_semantic_slice)` (`graphify_semantic_corpus.py:752`),
`_module_sha` (:676) hashes the module's source **bytes** so even a comment moves it, and
`cache_namespace_for` (:705-712) folds that digest into the cache namespace.
`graphify_semantic_corpus_authority.py:413` records this having fired twice already on comment-only
edits, and :469 records the authority block re-recorded 2026-08-20 for the 0.9.48 bump — so the plan
is authorised against the current bytes and any edit stales it. **Scope warning:** `SOURCE_REF` is not
an ordinary version pin; it is the snapshot identity of one evidence file (`SOURCE_PATH =
"docs/how-it-works.md"`) travelling with SOURCE_TREE / SOURCE_GIT_OBJECT / SOURCE_SHA256 / SOURCE_SIZE
(:46, :54-56), so the fix requires re-deriving those digests at v0.9.48 and re-attesting the slice if
the blob moved. **Acceptance:** this lands in the SAME commit as F1 and the `effort` field of #411,
followed by exactly ONE re-plan and ONE authority re-record.

### F3 — the 10.6-hour corpus run has no task bound, no cache read, and a cap that tolerates ~one interruption

Three facts compose into one failure mode. (a) `[tasks.kb-graphify-semantic-corpus]`
(`mise.toml:669-671`) declares no `timeout`; exactly 8 tasks do (lint 20m, test 25m, eval 25m,
kb-build 180m, kb-transcribe 120m, kb-artifacts 60m, brain-audit 10m, hk-test 10m) while
`CLAUDE.md:176` says "the 7 slow tasks" — and 9 tasks total lack the key (kb-add, kb-merge,
kb-prose, kb-label, kb-update, kb-watch, kb-graphify-semantic-slice, kb-session-reflect,
kb-graphify-semantic-corpus-merge). A per-call ceiling does exist (`GRAPHIFY_API_TIMEOUT`, 900 s,
`graphify_semantic_corpus_authority.py:249`; #335 adjacent), so the gap is the wall clock, not the
call. (b) Re-derived against the INSTALLED 0.9.48: `load_cached` call sites are `cache.py:1236`,
`cache.py:1519`, `extract.py:5279`, `extract.py:5575` — none in `llm.py`, i.e. none on
`extract_corpus_parallel`'s chain; control arm, the writer `_checkpoint_chunk` (`llm.py:2571`) IS on
that chain (:2628, :2653). The cache is write-only on this route, so a resumed chunk is
**re-published free but re-bought at full price**. (c) `max_total_cost_usd = 100.0` against
58 × $1.12 = $64.96 means a restart after chunk N costs 1.12N + 64.96, so an interruption past
N≈31 makes the plan uncompletable inside its own authorization. With a ~10.6 h wall clock and no
bound, an interruption is the expected case. **Acceptance:** a `timeout` on the corpus task; a
documented background-run + in-turn-polling procedure (the Bash tool caps a single call at ~600 s
and a `&`-detached local `mise run` is reaped); and either a cap sized for one full restart or an
explicit per-release restatement. Also fix `CLAUDE.md`'s "7" (now 8) in the same change.

### F4 — `hk.pkl`'s justification comment asserts the secret scanners read `sources/**`; they do not

`hk.pkl:200-203` says of the `sources/**` entry: "gitleaks, `detect_private_key` and the structural
checks still read every one of these files, which is what keeps an exclusion this wide tolerable."
That is false. `hk.pkl:72` puts `"sources/**"` in `baseExclude`; `:103` is `exclude = baseExclude`
(hk's global exclude, per `sources/hk/pkl/Config.pkl:88`); `pkl eval -x 'exclude' hk.pkl` lists it at
entry 17; and `pkl eval` of both the `gitleaks` and `detect_private_key` steps yields
`exclude = List()`, i.e. no per-step override. Armed live in a scratch repo with the real `hk.pkl` and
hk 1.56.0: identical RSA private-key bytes in `sources/planted.json` and `docs/planted_control.md` →
`hk check --all --step detect_private_key` flagged only the control, rc=1; identical AWS token in
`sources/leak.json` and `docs/leak_control.md` → gitleaks flagged only the control. In the real repo,
`hk check --all --step detect_private_key` reports 856 files while `git ls-files` = 996 and
`git ls-files sources/` = 140 (996 − 140 = 856 exactly). `check_merge_conflict` is blind too. Blast
radius: 25 tracked `sources/extractions/*.json` plus all of `sources/media/**`, and every artifact the
deep extraction will add. `hk.pkl:85-90` records that gitleaks may still reach them only by
**accident** (`gitleaks dir` ignoring its path arguments when given more than one) — an accident an
upstream fix removes silently, and which did not save the arm above.
`tests/test_hk_scanner_scope.py:100-105` asserts the exclusion is correct, so code and test agree and
the **comment** is the wrong artifact. #94 states the underlying blindness but is CLOSED NOT_PLANNED
(2026-08-02) and predates the comment, which was added 2026-08-17 as the remedy for the `--no-verify`
incident. **Acceptance:** either narrow the exclusion so the scanners see `sources/**` (it was widened
for `typos` and formatters only), or correct the comment to say what is actually true — and add a
planted-secret arm to the suite so the claim is machine-checked either way.

### F5 — the scanner-scope regression gate covers 3 of the 5 prose paths, and misses the one its own comment calls highest-risk

`tests/test_hk_scanner_scope.py:42-46` defines `_VERBATIM_PATHS` as three entries
(`graphify-out/memory/**`, `docs/research/**`, `docs/goals/*-goal.md`), while `proseExclude`
(`hk.pkl:179-183`) carries five — those three plus `docs/direction/**` (:180) and
`docs/session-review/runs/**` (:181). Both directions of the gate parametrize over `_VERBATIM_PATHS`
(:88-94 and :110-120), so if either omitted path is "tidied" onto `baseExclude`, no test fires — which
is exactly what the file's own docstring (:18) exists to prevent ("A comment saying do not tidy these
onto proseExclude did not prevent the second"). The miss lands on the worst candidate:
`hk.pkl:191-195` says of `docs/session-review/runs/**` that "these files quote transcripts, commands
and `gh api` output, so they are a plausible place for a token to land". Current state is SAFE —
`pkl eval -x 'exclude' hk.pkl | grep docs` → no match against 20 total entries — so this is an
ungated invariant, not a live breach. `grep -rn 'docs/direction\|docs/session-review' tests/` returns 2
unrelated hits against a control of 8 for `docs/research`, so the gap is real. **Acceptance:**
`_VERBATIM_PATHS` is derived from `proseExclude` rather than re-listed, or a test asserts the two sets
are equal.

### F6 — currency reports drift and exits 0, and is in no gate — Ray asked for it to be a hard gate

Ray's 2026-08-18 directive: "currency as a hard gate". It is not one. `currency` is absent from
`GATE_TASKS` (`gates.py:139`; control `grep -c currency` → 7, all "concurrency" or rule-name prose,
vs `grep -c lint` → 22), and `mise run kb-currency-check` returns **rc=0** while printing drift — by
design, per `CLAUDE.md` ("always exits 0 and can never serve as a CI gate — an out-of-date tool is a
signal, not a failure"). At `9dfc1255`, `.agent/kb/gates/gates-9dfc1255….json` records six gates all
rc=0 with four drifts standing: graphify **ref-binding** (see F2), graphify **build-stamp** (a build
RAN AND FAILED 2026-08-20T21:20:51Z), **mise:version** (PATH 2026.8.10 vs reviewed 2026.8.9), and
**mise:manifest** (`sources/mise.manifest` pins v2026.8.9). skillopt is separately reported UNKNOWN
("this is not a pass"). **This issue is a decision request, not a fix:** the documented design and the
directive contradict each other. Options to put to Ray: (a) a *narrow* blocking gate — only
ref-binding drift and a FAILED build stamp block, while "a newer version exists upstream" stays
advisory; (b) fully blocking; (c) the doctrine stands and the directive is scoped to the currency
sweep rather than the ship gates. Separately, and independent of the ruling, the mise bump is a
**3-file** change — `currency.toml:598`, `sources/mise.manifest:39-40`, and `mise.toml:40
min_version = { hard, soft }` per Ray's standing "min_version.hard MOVES" ruling.

### F7 — `requires-python` is `>=3.14` and Ray asked for `>=3.14.7`; and can python then leave `mise.toml`?

`pyproject.toml:5` reads `requires-python = ">=3.14"`, unchanged since the initial commit
(`git log -L5,5:pyproject.toml` → one commit, `886584dd`). `mise.toml:44` pins
`python = "3.14.7"`. Ray, verbatim (2026-08-19, `docs/direction/2026-08-19-ray-directives.md:237-241`):
"we should add verify specifc version of python dependency in pyproject.toml if possible / update:
from `requires-python = \">=3.14\"` to `\">=3.14.7\"` / will this allow us to remove python from
mise.toml using mise's dependency feature so we can have the configuration in multiple places?"
Untracked: a full-body sweep of all 278 issues for `requires-python` OR `3.14.7` returns only #316,
#238, #227, #226 (control in the same pass: `graphify` matches 133 of 278). **Correction to a claim
made twice in this round: #227 is NOT the defect this closes.** #227's own body says
"`pyproject.toml` declares `requires-python = \">=3.14\"`, so nothing fails. **A floor cannot catch
this; that is why it went unnoticed for weeks**", and it explicitly warns "Do not assume bumping the
pin fixes it". #227 is a venv-resolution defect; this is a separate, unfiled request with a second
half (whether the floor lets python leave `mise.toml`) that nothing has answered. Carried in at least
three handoffs (`session-2026-08-19-b.md:52`, `-19-c.md:226`, `-21.md:126`).

### F8 — CI/CD epic: `.github/` does not exist, and "start semantic versioning after every successful pr" is unimplemented and unfiled

Ray asked twice. 2026-08-18 (`docs/direction/2026-08-19-ray-directives.md:253`): "add gha workflows
for full ci/cd of the project — run tests / renovate updates / dependabot updates / semantic version
increments and package deploys / provide other suggestions / improving upon what
`~/dev/github/ray-manaloto/dotfiles` using modern best practices and all modern
services/tools/libraries/sdks vs hand-writing our own code". 2026-08-19, the **last line** of the
SIXTH ADDENDUM (:339): "start semantic versioning after every successful pr". State: `ls -d .github`
→ No such file or directory (control `ls -d .claude` → `.claude`); `git tag | wc -l` → 0 and
`git ls-remote --tags origin` → empty against 165 commits; `pyproject.toml:3` is `version = "0.1.0"`,
last touched at `f008f1b8` (2026-07-21, a file move) and never incremented;
`grep -rn "git tag\|gh release\|create_release" python/src/kb_setup/` → 1 docstring hit (control
`grep -rn "gh pr"` → `session_state.py:45,82,262`). Tracker: full-text `gh search issues "semantic
versioning"` → 0 open and 0 closed (control "mutation" → 6); title sweep for
gha/ci-cd/dependabot → 0 (control "renovate" → #418, #204). **#204 covers only the Renovate slice**
— one of five sub-items. The nearest neighbours #306 and #137 are one-off release-bundle specs, not
"version after every PR". File as one epic with the five sub-items, and note that this repo has **no
CI at all**, so `gh-cli-watch.md`'s "this repo has no CI" note and `kb-ship`/`kb-land`'s local-gate
design both change if it lands.

### F9 — `pinact` was named specifically as an hk builtin to add and is unfiled; #361 does not name it

Ray, `docs/direction/2026-08-19-ray-directives.md:224-226`: "review new builtins we should
add/update/replace into this project — such as: https://github.com/suzuki-shunsuke/pinact — so we can
proactively update versions in place instead of waiting for renovate — if added make a
currency/critical dependency". Not adopted: `grep -ni "pinact\|kingfisher\|betterleaks" hk.pkl` → 0
against a control of 12 `gitleaks` lines including the live step `hk.pkl:265 ["gitleaks"] =
Builtins.gitleaks`. Not filed: a full title+body sweep of all 278 issues for `pinact` → 0 results,
with control `kingfisher` → #360, #361, #362 and `adhd` → #384. #361 is the generic
"review EVERY hk builtin" sweep and its body names only betterleaks (#359) and kingfisher (#360) as
the adoptions already called out; it encodes neither of Ray's two riders. Feasible:
`mise exec -- hk builtins` lists 148 builtins including `pinact`, `pinact_update`, `pinact_update_v3`,
`pinact_v3`. **Scope question the issue must carry:** `.github/` does not exist here (control
`ls -d .claude` → exists), so pinact would have zero workflow files to pin today — its adoption is
downstream of F8. The only in-repo mentions are narrative (`currency.toml:1345` quoting hk's 1.56.0
release notes).

### F10 — all 10 enabled Claude Code plugins and all 5 marketplaces are version-unpinned; two record no commit at all

`.claude/settings.json` enables 10 plugins; every `extraKnownMarketplaces` entry is
`{"source":"github","repo":"owner/name"}` with **no ref, tag or SHA**, so each resolves to whatever
that repo's default branch holds. `currency.toml` has 15 `[tool.*]` sections and none is a plugin or
marketplace (`[tool.codex]`/`[tool.antigravity-cli]` track the CLI **binaries**;
`grep -c '^\[tool\.fable-orchestrator\]'` → 0 against control `grep -c skillopt` → 14 with a real
`[tool.skillopt]` at :1504). No plugin lockfile exists in-repo. This is Ray's SIXTH ADDENDUM class
verbatim: "should find cases of using tools/clis/sdks/libraries/skill/plugins/etc that are not tracked
in mise.toml or pyproject.toml". Machine-local state shows what is actually loaded and why it matters:
`~/.claude/plugins/installed_plugins.json` records fable-orchestrator 1.21.0/`78f9cb566cd9`,
antigravity 0.23.0/`cb47ce41597a`, mattpocock-skills 1.2.3/`6acc160e4e0c`, codex 1.0.6/`db52e28f4d9d`,
plugin-eval 0.1.1/`c4b82b0ad771`, astral 0.1.0/`f3ce88a7ba83` — and **skill-creator and
pr-review-toolkit at version "unknown" with no `gitCommitSha` at all**. All five marketplaces
re-fetched 2026-08-21T02:00-02:16Z, and `claude-code-workflows` (plugin-eval's marketplace) carries
`autoUpdate: true`, so its owner can change what `/eval` and `kb-skill-score` load with nothing here
noticing. Two secondary doc defects to fix in the same change: `.claude/CLAUDE.md:46` says "Nine
plugins are enabled in total" (10 in settings.json, **8 effective** — `.claude/settings.local.json`
disables `claude-md-management` and `mise@brentmitchell25`), and `astral` and `codex@openai-codex` are
named nowhere in CLAUDE.md (control: `grep -cE 'pr-review-toolkit|skill-creator|claude-md-management|plugin-eval'` → 3;
`mattpocock` IS named at `.claude/CLAUDE.md:10`). **Before specifying a fix, probe whether Claude
Code's marketplace config accepts a ref/SHA field at all** — that was not verified. Nearest tracked
items are #384, #124, #243; none covers this.

### F11 — nine tools this repo instructs agents to use resolve from the USER's global mise config, including `pipx:graphifyy`

`mise ls --current` prints the source config per tool. Control arm: gh 2.97.0, hk 1.56.0,
antigravity-cli 1.1.15, codex 0.148.0, conda:ffmpeg 9.0.1, doppler, fnox, agnix, gitleaks all print
`~/dev/github/ray-manaloto/knowledge-base/mise.toml`. These print `~/.config/mise/config.toml`:
jq 1.8.2, node 26.7.0, npm 12.0.2, npm:ctx7 0.5.8, pipx:mcp2cli 3.6.0, chezmoi 2.72.0, delta 0.19.2,
gitlab:graphviz 16.0.0 — **and `pipx:graphifyy 0.9.48`**, this repo's core dependency, which is both
unpinned here and drifted from `pyproject.toml`'s own declaration. `grep -nEi 'jq|node|npm|ctx7|mcp2cli|chezmoi|delta|graphviz' mise.toml`
returns 11 hits, every one prose (control: `grep -nE '^gh = |^hk = '` → :95, :46). This is the failure
`mise.toml:85-95` already documents for `gh` ("pinned NOWHERE in this repo and resolved only from
Ray's user config, so on a fresh clone `mise run kb-ship` fails at the tool it needs most") applied to
nine more tools — **two of which this repo's own rules instruct agents to run**:
`research-doc-sources.md` step 3 prescribes `ctx7 library` / `ctx7 docs`, and the same file plus
`do-not.md:101` name `mcp2cli` as the preferred MCP transport. Even `curl` resolves to a mise **shim**,
not `/usr/bin/curl`. Measured usage across the 14 sessions: jq 64, node 47, curl 25, delta 12,
chezmoi 4, ctx7 1, mcp2cli 1. Untracked — nearest are #329, #314, #225, #405. **Accepted and out of
scope, recorded so it is not rediscovered:** `perl` (24 invocations, `/usr/bin/perl`, the sanctioned
`timeout` replacement per `long-running-command-hangs.md` rule 3a) is unpinned on the same precedent
`mise.toml:96-107` sets for `git`.

### F12 — `.mcp.json` registers a remote `api.graphify.com` MCP server that no config file tracks, and CLAUDE.md invariant 4 does not acknowledge it

`.mcp.json` declares one server: `{"graphify": {"type": "http", "url": "https://api.graphify.com/mcp"}}`.
It is a versionless third-party network dependency whose tool schemas load into every session in this
project (28 `mcp__graphify__*` tools), whose behaviour can change server-side, and which appears in
neither `mise.toml`, `pyproject.toml` nor `currency.toml` (`grep -c 'api.graphify.com'` → 0/0/0;
control `grep -c graphifyy pyproject.toml` → 1). It also sits beside CLAUDE.md Invariant 4 ("One MCP
server per graph. The server binds to an ABSOLUTE `graph.json` path — `mise run kb-serve`") without
either document acknowledging the other, so **which graph an agent reaches through MCP is currently
ambiguous** — and given `graphify-out/graph.json` is 8.6 days stale (G7), that ambiguity has teeth.
This issue asks two things: track it as a dependency, and rule on whether it should be registered at
all.

### F13 — `mise` supports OS-scoping on both tools and tasks, and `mise.toml` uses none of it

Ray asked (`docs/direction/2026-08-19-ray-directives.md:228-231`): "why does mise.lock have references
to linux? ... mise should provide a way to add attributes or settings to specify what operating system
a specific tool or task should run on". **The first half is answered — cite #391, do not re-file it.**
#391 (OPEN, created 2026-08-19) states the cause: the Linux rows are conda-backend portability slots
with no live consumer here. Independently confirmed: every linux-bearing header in `mise.lock` is a
conda one (135 `[conda-packages.linux-x64.…]`, 135 musl, 125 linux-arm64, 125 arm64-musl;
`[conda-packages` 783 vs `[tools` 104, and no `[tools.*]` header carries linux), all traceable to the
single entry `mise.toml:52 "conda:ffmpeg" = "9.0.1"`. It is **not** for CI/CD — `.github/` does not
exist. **The second half is unanswered and this issue is only that half:** the pinned mise clone
already ships the feature — `sources/mise/schema/mise.json:53-65` defines `"os_filter"` ("operating
system filters to install on"), a tool entry references it at `mise.json:2661`, a task entry at
`mise-task.json:1085`, and `mise.json:1383` has a settings-level `"os"`. `mise.toml` uses no `os` key
(grep → 0). (`currency.toml:128`/`:571` carry `os = ["macos"]`, but that is this repo's own
currency-engine key, not mise's.) Decide whether to scope the conda/ffmpeg tool and any
macOS-only tasks, and record the answer so the question is closed rather than re-asked. Note the
probe lesson: a **title-only** issue search missed #391 entirely; the full-text search found it.

### F14 — record the answer: graphify's CLI has no PR features; what we consume is the graphify-labs review bot

Ray asked (`docs/direction/2026-08-19-ray-directives.md:302`): "are we using graphify pr features?"
Answered here for the first time: `mise exec -- graphify --help` on the pinned 0.9.48 lists **no `pr`
subcommand**. Control arm from the same output: `hook install/uninstall/status`, `global
add/remove/list/path`, `export callflow-html`, `benchmark` and `merge-driver` are all present, so the
negative discriminates. What this repo actually consumes is the **graphify-labs GitHub App's PR
reviews**, cited in-code at `python/src/kb_setup/hk_test.py:114,121,167,196` and
`write_attribution.py:127`, all crediting PR #406 findings — and Ray's 2026-08-19 SECOND ADDENDUM
already ruled those "critical since we need to understand how graphify works". No issue exists for the
question (`grep -ic 'graphify pr'` → 0 across 278 titles, control `renovate` → 2). File this as a
short **answer-of-record** so it is not re-asked, and cross-link #380 (which owns harvesting those
bot reviews properly).

### F15 — smaller items, file as a batch or fold into the named parents

- **`tests/test_graphify_sdk.py:9` imports `networkx` at runtime and it is in no dependency group.**
  `pyproject.toml:81-87` lists only ruff, ty, pytest, pytest-xdist, trafilatura. NOTE: the
  headline version of this claim was **refuted** — `graphify_sdk.py:56-57` is under
  `if TYPE_CHECKING:` with `from __future__ import annotations`, so shipped code cannot break at
  import time. Only the test import is undeclared. Remedy is `uv add --group dev networkx`, never an
  editor edit (#381).
- **`_VERBATIM_PATHS`, currency.toml retirement residue.** Of `currency.toml`'s 15 `[tool.*]`
  sections, 12 map onto an existing `mise.toml`/`pyproject.toml` pin; three do not:
  `[tool.mise]` (mise is absent from its own registry — control-armed), `[tool.claude-code]` (which
  *is* mise-pinnable, see G5), and `[tool.skillopt]` (a VCS-revision contract at `pyproject.toml:31`
  that a version pin cannot express). Fold this 3-item residue into **#393** as the migration plan's
  open question — the collapse goal itself is already #393/#381/#357.
- **Commit the two untracked directive files.** `docs/direction/2026-08-20-ray-directives.md` and
  `2026-08-21-ray-directives.md` exist on disk (so `/clear-prep` and `/kb-resume` do read them) but
  `git status --short` reports both as `??`. They would not survive a fresh clone or `git clean -xdf`.
  One commit.
- **`.agent/kb/reports/agents/otel-collector-plan.md` promotion** to `docs/research/reports/`
  (carried five handoffs; `.agent/` is gitignored, control: `docs/research/reports/` holds 87 entries).
- **`the-advisor-strategy` source uningested** — `sources/REGISTRY.md:84` row 58, no manifest, no
  chunk (controls: 73 manifests, 25 chunks exist).
- **SARIF `diagnostic_format` + the gates-record codegen** — carried as "not filed, and should be"
  across three handoffs, then silently dropped. `gh issue list --search "SARIF"` → empty, control
  `"rumdl"` → #358/#383/#81.
- **`ctx7` removal status is UNKNOWN.** Ray said "remove that broken context7 install"
  (2026-08-20, session 6d692fdd msg 7); `research-doc-sources.md` step 3 still prescribes it; F11
  shows a `ctx7` binary resolving from the user config. Run `command -v ctx7` with a control arm and
  either restore the rule's accuracy or remove the step.
- **No owner for issue filing** (the narrowed AC-3 residue): 57 `gh issue create` commands / 76
  invocations across 11 sessions, no mise task, no `kb_setup` module, no `ISSUE_TEMPLATE`, and the
  evidence-anchor rule enforced by discipline alone. File **without** the token-savings argument,
  which its own data refutes.
- **The prescribed cold-review lane is bypassed** (the reframed AC-1): `ai-cli-invocation.md:57-61`
  and `kb-review/SKILL.md:122-126` name plugin skills as the owner; 24 hand-typed `agy` invocations
  across 10 sessions bypassed them, with three flag spellings probed before one worked and
  `--mode plan` used twice against the standing note.

---

## 4. ALREADY TRACKED — do not double-file

| Issue | One line | Verified state |
|---|---|---|
| **#397** | kb-build RED — but its stated cause (anthropic-sdk-python unclassified files) is **fixed**; criteria 1 (release-tag pins) and 2 (branch-head gate) untouched, 52/73 still pin a branch head | OPEN, body stale |
| **#409** | The live kb-build failure: extract-stage syntax-error warnings, currently `sources/colibri/c/backend_cuda.cu` | OPEN |
| **#411** | Per-file model/effort provenance keyed on content hash | OPEN — **design only, correctly** |
| **#414** | 55.1% of the plan's 1.04M tokens is byte-identical re-extraction (571,462 saved) | OPEN, figures re-derived and exact |
| **#417** | Register of `build = skip` sources — **3 sources missing and its "all scope = study" invariant is now false** | OPEN, needs update |
| **#334** | The corpus run requires the operator to scrub ambient `AWS_*` by hand | OPEN, reproduced live |
| **#335** | Two independent 120s ceilings on one provider call; only one config-reachable | OPEN (adjacent to F3) |
| **#421** | Two 0.9.48 evidence claims left at 0.9.47 + a line-scoped exclusion in the argv guard | OPEN — F1 is the third straggler |
| **#389** | 8 plans, 0 runs; the reauthorize task and a run-floor | OPEN |
| **#301 / #302 / #305** | Scale semantic extraction, compose AST+semantic, assemble the expert bundle | OPEN |
| **#348** | `check_first` whitelists any `mise run kb-`, so a piped gate is unguardable — **P0**; new measurement 351 piped / 74 unpiped | OPEN |
| **#239** | Guard the heredoc-edits-a-source-file shape (#342 was CLOSED at 20 occurrences without shipping; now 222) | OPEN |
| **#380** | Read all four PR-feedback surfaces; UNREAD ≠ zero; graphify-labs never skippable — **superset of the bot-harvest proposal** | OPEN |
| **#407** | PR bot rounds are unbounded (8 on #406) | OPEN |
| **#355** | CodeRabbit rate-limit misread as a pass | OPEN |
| **#390** | Fix-round reports satisfy the receipt without a fresh cold pass — 32 of 63 this round | OPEN |
| **#401** | `/clear-prep` does not run session-review (grep → **zero** hits, control `kb-session-reflect` → 3) | OPEN |
| **#423** | session-review has no lane pointed at itself + the measurement harness — **this is Ray's "what is preventing it" clause** | OPEN |
| **#415 / #387 / #343** | Automate triage + auto-fix of repeated mistakes; detectors ran 0× in 22h; 93% of cross-checked findings refuted | OPEN |
| **#352 / #344 / #362** | No coverage ledger over 238 transcripts; handoff derived by session-review; the reconcile gate catches only drops | OPEN — **#362 has a live instance: #373, skillopt, and DOCS DRIFT were carried five handoffs then dropped silently** |
| **#350** | Universal logger — stdout+stderr durable for every task and workflow agent | OPEN |
| **#356 / #379 / #265** | Named wrapper candidates for hand-run chains | OPEN |
| **#393 / #377 / #381 / #357 / #383** | mise.toml+pyproject.toml as master; duplicated version literals; `mise use`/`uv add` enforcement; the 18-name roster; the two zero-outdated gates | OPEN |
| **#372** | `kb-currency -- --tool X apply` cannot reach apply — documented and non-functional | OPEN |
| **#227** | The gates run on a uv-managed 3.14.0, not the mise pin — **explicitly NOT closed by F7's floor** | OPEN |
| **#391** | mise.lock's Linux rows are conda portability slots — answers half of Ray's question | OPEN |
| **#354 / #218** | The 20%-context `/clear-prep` trigger is unimplementable as worded; the eager-context cap | OPEN — **needs Ray's ruling, see §6** |
| **#399 / #374 / #345** | A review lane mutated `.codex/config.toml`; recurred; 11 candidate writers refuted | OPEN — and it is modified in the tree right now |
| **#369** | Ray was the retry loop: 8 consecutive 529s, 43m, zero output | OPEN — relevant to a 10.6h run |
| **#382** | Dependencies move mid-round: adopt-or-defer, and MEASURE what moved | OPEN |
| **#384 / #370 / #394 / #365 / #353 / #412 / #404 / #405 / #366 / #376 / #240 / #276 / #361 / #204 / #358** | Plugin review at project scope · visual-plan requirement has no durable home · generated-code lint exemption must be enforced · schemas dedup · manifest enums · agent-harness-docs 93 behind · chezmoi port · narrowed `remote.origin.fetch` · deferrals inside the window are in scope · prose-question enforcement · impact maps · hk builtin sweep · Renovate port · rumdl use-or-remove | OPEN |

---

## 5. REFUTED / NOT VERIFIED

### 5a. Refuted (9 of 35 verified) — do not act on these

| Claim | What was refuted | What survives |
|---|---|---|
| **RR-03** | "No 2026-08-20 directive file exists." `ls docs/direction/` returns **six** files (control: the four older ones list fine); `2026-08-20-ray-directives.md` records the skip-and-file ruling verbatim under "THE RULING THAT IS NOW LOAD-BEARING" | Both new files are **untracked** (`??`) — commit them (F15) |
| **RR-04 (blocking half)** | "#411 must be built or the run cannot be backfilled." Retained per-chunk argv + `.gitignore:63-69` + the authority module make model/effort recoverable for zero tokens | One typed `effort` field is missing from `CorpusExecutionConfig` (G5) |
| **A5-04** | "Nobody answered why mise.lock carries linux." **#391 answers it**; the claim's probe was title-only and could not see it | The OS-scoping half is unanswered, and `os_filter` exists unused (F13) |
| **A5-05** | "No session-review lane is a repeated-mistake detector." `session-review.js:458-460` puts repeated mistakes explicitly in the tooling-gap lane's prompt, added 2026-08-19 in `d6641b98` in response to the directive; the `circles` lane is a second site. The claim read lane KEYS, not lane PROMPTS. The diagnostic clause is **#423** | Nothing — but note this is about the detector *existing*, not about it working; #343/#415 own that |
| **UT-01** | "`networkx` is imported by shipped code and will break at import time." `graphify_sdk.py:56-57` is `if TYPE_CHECKING:` under `from __future__ import annotations`; `TYPE_CHECKING` is False at runtime. networkx reaches the runtime through graphify's own submodules — it would break graphify first | The test-only runtime import (F15) |
| **UT-04** | "`shutil.which` makes the docker/ollama/brew gap invisible." `reclaim.py:90-97` documents the three-state design (FOUND/UNAVAILABLE/real empty) that this module was rewritten to *fix*; `_report` prints "COULD NOT CHECK", `main` prints "the total above is a floor". Four tests cover it **including a control arm** (`test_reclaim.py:448,456,467`). The claim's own greps did not reproduce (measured 2/0/5, not 0/0/0). docker and ollama **are** mise-pinned globally | Only `brew` is unmanaged, and only in this repo's own configs — an observation, not a finding |
| **AC-1** | "Nothing owns the cold-review lane launch." `ai-cli-invocation.md:57-61` and `kb-review/SKILL.md:122-126` prescribe plugin skills that are installed on disk. Counts did not reproduce (24 `agy`/10 and 12 `codex exec`/7, not 76/7 and 22/6, with no stated method for the originals) | A compliance failure, reframed in F15 |
| **AC-3** | "A stable, unenforced skeleton re-derived 57 times ≈ 54k tokens." **248 distinct headings over 360 occurrences, 224 appearing once**; the 7 cited headings cover 24%; heading lines are 5.2% and non-body scaffolding 13.0% of the total; 34 of 57 already use `--body-file`; 46 of 57 use a heredoc, not all; 57 commands hold 76 invocations | The narrow "nothing owns issue filing" residue (F15) |
| **AC-4** | "48 pgrep polls / 8 sessions vs 4 ListAgents." pgrep is 44/6, of which **37 poll local background bash jobs** ListAgents cannot see, 3 are prose, and 4 target an AI lane. The ListAgents baseline was measured from a bash-command corpus that cannot contain tool calls — all 4 hits are prose. The lesson file was **authored by** the session whose polls are cited | Nothing actionable; post-lesson delegated-lane pgrep is 2 calls in 1 session |

### 5b. Corrections carried inside CONFIRMED verdicts

Do not repeat these numbers as originally stated: **#397's cause** has moved from detect to extract
(#409); **SC-01** is 351/74, not 311/150, and is **already #348**; **SC-05's fourth drift** is
`mise:manifest`, not skillopt (which is UNKNOWN, not drift); **ER-05's** "only slow task without a
timeout" is nine tasks, and a per-call ceiling exists; **UT-02's** effective plugin count is 8, not
10, and `mattpocock` *is* named in CLAUDE.md; **UT-05's** claude-version C4 blocker is **already
closed** (`currency.toml:908` = 2.1.238 = running); **A5-06/DW-04's** "#227 is the defect this floor
would close" is contradicted by #227's own body; the repo has **278 issues**, not 421 (421 is the
highest issue-or-PR number); **DW-08's** "1,146 linux vs 230 darwin" holds as a *token* count, not a
line count (`grep -c darwin` = 18) — state the metric; and **graphify's line anchors** were off by one
in three separate citations this round (`A5-05` lane keys, `A5-06` mise.toml:45, `ER-03`
corpus.py:753), so re-read the cited line before quoting it.

### 5c. Not verified — 103 claims the per-lane cap never reached

**The lanes collected 155 claims; 35 were adversarially verified; the harness reports 103 as
unreached. 155 − 35 = 120, so those two figures disagree by 17 and I did not reconcile them.**
Treat every unverified claim as a **lead**, not a finding. What that means concretely for this
document: everything in §1 rests on a verified claim, and every §3 body cites the probe it came
from — but the long tail of §4's table rows and §3's F15 batch includes items whose only evidence is
a lane's own probe with no adversarial pass.

**Named gaps the lanes themselves declared, which nobody closed:**

- **Nobody re-ran `mise run kb-build`** (180 min, network). Whether it is green now that colibri,
  codegraph and codex carry `build = skip` is **UNMEASURED**. G7's "RED" rests on the absent
  `.currency-stamp.json`, the `.build-failure.json` artifact, and an 8.6-day-old `graph.json`.
- **Nobody ran the corpus.** G1's 58-failure prediction is a confirmed inequality feeding a
  confirmed equality check plus the code path, not an observed staging failure. G4 *was* observed
  live.
- **Two Ray messages are truncated** in the extracted corpus — `773421d1-2026-08-18.md:104` (mid
  shell transcript) and `:181` (immediately after a trailing "NOTE:"). The tail of message 4 is
  unread; its substance was recovered from the mirrored directive file, but anything after that
  final "NOTE:" is unseen.
- **`docs/direction/2026-08-02` and `2026-08-17` were not read in full** — only grepped. Items in
  them may be open and unfiled and no lane checked.
- **The 2026-08-18 directive's VERBATIM block, FIRST, SECOND and THIRD addenda** were read but only
  spot-checked against the tracker.
- **Absence probes were title-only in the addenda lane** (bodies unchecked); the requirements lane's
  issue-status calls came from `--state open` titles and did not check whether an open issue is in
  fact implemented and merely unclosed. Two verdicts (A5-04, F9-adjacent) turned on exactly this —
  a title-only sweep missed #391 and a body sweep found it.
- **Transcript command counts exclude subagent and Workflow fan-out transcripts**, so SC-01's 351,
  SC-13's zeros and every AC count are **floors**.
- **The bare-vs-`mise exec` invocation rate is NOT MEASURABLE** with the ad-hoc segmenter — heredoc
  prose was counted as commands (e.g. `graphify 0.9.48 and claude 2.1.238…`). Four real bare calls of
  a version-sensitive binary were confirmed by reading them individually; that is a lead, not a rate.
- **647 Edit, 146 Write, 141 Read and 22 Agent tool calls were never mined** — Edit is the
  second-most-used tool, so a repeated manual sequence expressed as Edit→Edit→Write is invisible to
  every automation finding above.
- **The extraction fan-out itself was never audited.** Every `blocks_extraction: false` in the
  automation lane means "I found no blocker", not "I verified there is none".
- **F4's planted-secret arm was run in a scratch repo, deliberately not in this one**; F5's
  other direction (does adding `docs/direction/**` to `baseExclude` actually pass the suite?) was
  never armed.
- **`graphify_semantic_corpus_authority.py` and `graphify_semantic_corpus_prototype.py` were not
  read** by the extraction lane, and `graphify_semantic_slice.py`'s receipt-verification surface
  (:1356-1410) was only partially read — further stale-pin or acceptance logic may exist there.
- **`feat-kb-check-guard`** (session 6b974f05: "1 commit, gates 5/5 green, no review receipt — next
  session ships it") was never named again and its fate was never probed.
- **RR-46 (`ctx7` removal)** was never probed with a control arm.

---

## 6. Four things that need Ray, not an agent

These are contradictions or rulings; resolving them silently would be the worse error.

1. **Ordering: triage-first or extraction-first?** 2026-08-18: "aggregate and triage ALL GitHub
   issues per the THIRD ADDENDUM, file what is missing, and prioritise. **Nothing else starts until
   that and currency are done.**" 2026-08-20: "our goal is to get to the full graphify repo
   extraction and reflection ... we can get back to it on the aggregation/triage work **after
   graphify is fully extracted**." The later ruling wins on ordinary reading, and this document
   assumes it — but nothing in the repo records the supersession.
2. **Is currency a blocking gate?** Ray's directive says hard gate; `CLAUDE.md` documents the exact
   opposite ("always exits 0 and can never serve as a CI gate"). F6 offers three options.
3. **Wayfinder.** The SIXTH ADDENDUM asks session-review to re-apply findings to
   "wayfinder/grilling maps"; the standing recorded call is "Wayfinder over the whole backlog —
   RULED OUT, and it cannot be model-invoked. Do not offer." Both cannot hold.
4. **The 20%-context trigger.** #354 found it unimplementable as worded (crossed 58 minutes in,
   before the round's first commit). Ray has restated it three times. It needs a re-specification,
   not another implementation attempt.

One more, smaller: **#353's finding contradicts Ray's own example.** He asked to merge duplicate
enums in `schemas/*.json` "into one superset"; the investigation found the enums are different
domains and must NOT be merged, while the real duplication is the absence of shared `$defs`. Surface
it rather than doing either.

---

## Recommended sequence

```
F1 + F2 + G5's effort field + G3's dedupe   →  ONE commit, ONE re-plan, ONE authority re-record
G4 (strip AWS_* from the task env)          →  independent, do first, it is cheap
F3 (timeout + background procedure + cap)   →  before the run starts, not after it dies
────────────────────────────────────────────────  RUN the deep extraction (leg 1)
G7 (#409 → kb-build green) + G8 (#417)      →  required before MERGE (leg 2) and artifacts (leg 3)
F4/F5 (scanner scope)                       →  before corpus artifacts land in sources/**
#411 built properly, keyed on content hash  →  its own reviewed change, per Ray's ruling
────────────────────────────────────────────────  the NEXT release is then a DELTA, not a re-run
```

The single highest-leverage line in this whole document is **the plan-time runtime assertion in
F1's acceptance criteria**: one comparison that already exists at stage time, moved earlier, turns
the most expensive failure mode here into a refusal that costs nothing.
