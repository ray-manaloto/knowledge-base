# Prior upgrade-protocol design — distillation

Read-only fact-finding report. Purpose: establish what was ALREADY designed and
decided about a dependency-upgrade workflow for this repo, so the next round
continues rather than re-invents. Written incrementally per source. Today:
2026-09-09.

Graph orientation performed first (`mise run kb-query -- "upgrade protocol
design decisions tool currency"`): the aggregate graph is AST-dominated by
third-party sources (uv, datamodel-code-generator) — 0 relevant hits, as
expected per `prose-and-code-layers-never-touch.md` (these design docs are
published artifacts / plan files, not graphify-ingested corpus sources). This
report reads the primary artifacts directly instead.

---

## A. Published design pages (`docs/artifacts/`)

### A.1 `upgrade-protocol.html` — added `564a01c9` (2026-08-30, PR "chore/cli currency sweep" #637)

**(a) Summary.** The foundational "design understanding" page. Frames a
dependency upgrade as a **13-stage pipeline** exercised by hand this session on
five real tools (uv, rumdl, biome, fnox, ctx7) — not a design sketch. Table
(stage / who / existing command):

1. Detect what's behind — machine — `mise outdated -b --local -J` · `uv tree --outdated`
2. Move the pin — machine — `mise use` / `uv add` (never hand-edit)
3. Move the lockfile — machine — `mise lock <tool>` scoped · `uv lock`
4. Resolve upstream tag→commit — machine — `gh api .../git/ref/tags`, dereferencing annotated tags
5. Write `sources/<dep>.manifest` — **unclear** — today hand-edited, no command
6. Sync `currency.toml` — **unclear** — only 5 blocks hardcode a version; rest derive
7. Re-clone at new SHA — machine — `mise run kb-build`
8. AST extraction — machine — free, no LLM
9. Deep/semantic extraction — **AGENT** — the fan-out, real tokens, not free to redo
10. Cluster + label — machine — `mise run kb-label`
11. Derived views — machine — `mise run kb-artifacts`
12. Reflect → LESSONS — **unclear** — `kb-reflect` is deterministic; the memory it reads is authored
13. Gates + per-tool validation — machine — `kb-gates`; per-tool half doesn't exist yet

Tally: **10 machine / 2 unclear / 1 agent**. Proposes a **3-layer architecture**
(the only place identical across every later page):
```
layer 1 — skill:  /upgrade <dependency> --deep-extract --reflect --artifacts
layer 2 — mise task: mise run upgrade -- <dependency> --deep-extract ...
layer 3 — python module: kb_setup.upgrade.run(dependency, deep_extract=, reflect=, artifacts=)
```
plus `/upgrade-all` (every tool stage 1 reports behind) and `/upgrade a,b,c`
(explicit list).

**Root-cause claim:** every previous upgrade attempt failed not because changes
were "too small" but because **each pipeline stage has its own checker reading
a different file** — `mise ls --current` reads `mise.toml`; the currency engine
reads `mise.toml` via `mise_key`; **nothing reads `mise.lock`** — so a bump can
move the pin/manifest/binary while all seven gates go green over a lockfile
still holding old checksums. Verbatim: *"That is not a missing feature. It is
the absence of one object that knows a dependency has a set of artifacts and
that all of them must agree. Every fix so far has added another checker to the
pile instead of adding that object."*

**Design consequence (near-ruling):** *"If there is one thing to carry from the
current system into a rewrite, it is not the code. It is `currency.toml`'s
~2,100 lines of per-tool judgment — tag prefixes, version patterns, platform
gates, and comments recording why. A generated mapping would recreate the
config and lose the judgment."*

**(b) Decisions/rulings recorded verbatim:** None yet — this page POSES the
four grilling questions, it does not resolve them (resolution happens in the
three round pages + `five-decisions-before-the-spec.html`). One correction is
recorded in-page (self-correction, not a Ray ruling): the "ten of thirteen /
every command exists" tally was wrong twice against the page's own table; a
cold review + re-derivation fixed it to 10/2/1, both rows 5 and 13 stated their
commands don't exist.

**(c) Marked OPEN — "Four things I could be wrong about," verbatim:**
1. *"Where the state lives"* — derive-only vs. per-dependency record vs. real workflow engine+DB.
2. *"Whether 'latest' is ever an agent decision"* — an advisor deferred two minor lint bumps and said "read the release notes first"; if upgrading is zero-agent that judgment has nowhere to go.
3. *"What atomicity means"* — one dep/one commit/one PR vs. one batch.
4. *"What the code generator can actually own"* — mise/uv publish schemas for CONFIG, not for command OUTPUT (`outdated` appears zero times in either); uv's own `outdated` declares `{"version":"preview"}` with zero `latest` fields.

A second correction is recorded in-page: *"Corrected 2026-08-30. This paragraph
previously read 'publish no schema' flat. That is the exact claim Ray corrected
during session kb-20260830.001 — it had been asserted from plausibility rather
than probed."* — i.e. Ray directly corrected an unprobed claim mid-session.

Cites `docs/artifacts/lockfile-blind-spot.html` (not in our reading list — a
sibling evidence page for the mise.lock claim) and **issue #636** as "the
umbrella this design would close."

### A.2–A.4 `upgrade-protocol-round{1,2,3}.html` — all added `564a01c9` (2026-08-30, PR #637)

**Structural note (important for the next round to know):** these three pages
are **interactive `AskUserQuestion`-style artifacts** (radio/checkbox forms
rendered client-side via inline JS, matching `eli5-visual`'s "grilling round"
pattern), not static prose. The committed HTML in each still holds the
**blank template state** — `{"a":{},"notes":{},"freeform":"","saved":null}` —
because a save from the live artifact page writes to the hosted artifact
version, not back into this git file, and none of the three was ever
recommitted after Ray answered. **Ray's actual answers to these 12 questions
are therefore NOT recoverable from the repo files themselves** — only the
*questions and recommended options* survive here. The synthesis that
presumably captured his answers is `five-decisions-before-the-spec.html`
(A.7, committed the next day, 2026-08-31) — read that page's own text for
whether it explicitly carries these answers forward or re-derives its five
from scratch (it does the latter — see A.7).

**(a) Summary — the 12 grilling questions, RECOMMENDED option marked ★:**

*Round 1 (Q1–Q4, directly restates "Four things I could be wrong about" from
A.1):*
- **Q1** Where does pipeline state live? — ★`derive+record` (derive from filesystem, then write down what was derived — "the written record IS the typed status enum from #636. No database.") / `derive` only / hand-maintained `record` / real workflow-engine+DB (`dbos`).
- **Q2** Is "latest" ever an agent decision? — ★`classify` (pipeline classifies via flag: patch→auto, minor/major/wide-blast-radius→stop with needs-review, `--force` overrides) / `auto` (upgrade blindly, gates catch it) / `always-review`.
- **Q3** What is the unit of atomicity? — ★`commit-per-dep` (one dep = one commit, batch = one PR) / `pr-per-dep` (one dep = one PR) / `one-commit` (whole batch).
- **Q4** (multi-select) What should the code generator own? — ★`mise-json` (`mise outdated -b --local -J`) / ★`uv-json` (`uv tree --outdated --format json` — "the one that silently reported '0 outdated' today") / ★`status` (our own typed pipeline-position enum) / ★`gates` (the kb-gates artifact, "hand-parsed four times in this session… has no schema today") / `currency` (currency.toml itself — flagged riskier, not recommended, "carries ~2,100 lines of per-tool judgment… a generated file cannot hold").

*Round 2 (Q5–Q8):*
- **Q5** Which durable-execution engine, and which database? — ★`dbos-sqlite` — "VERIFIED this session: DBOS supports SQLite… PR 'Add support for sqlite/tursodb' is merged… dbos 2.31.0 on PyPI, requires-python >=3.10; this repo runs 3.14.7." (Presupposes Q1 answered toward a workflow engine.)
- **Q6** A blind upgrade fails the gates — then what? — ★`revert-continue` (auto-revert that one dependency, continue the batch, report it — "the batch always lands something"). (Presupposes Q2 answered toward `auto`, which conflicts with Q2's own ★`classify` recommendation — see "still open" in consolidation.)
- **Q7** (multi-select) What counts as a "dependency" the protocol can upgrade? — ★`mise-tools` (mise.toml `[tools]`, "20 today") / ★`pyproject-direct` (pyproject.toml direct deps+groups, "13 today. Note 3 are `>=` floors, not pins").
- **Q8** Where does irreducible per-tool judgment live? — ★`in-mandatory` (inside mise.toml/pyproject.toml next to the pin, "Zero extra config files… Requires checking whether mise.toml accepts unknown keys").

*Round 3 (Q9–Q12):*
- **Q9** What becomes the single source of truth for a version? — ★`mandatory-only` (mise.toml + pyproject.toml are the ONLY places a version is ever typed; everything else derived/generated) — "MEASURED: every tracked tool version exists in 3 to 5 places. The graphify fork SHA lives in FOUR tracked files."
- **Q10** The 23 state files nobody shares — ★`to-db` (all state moves into the workflow database) — "MEASURED: docs/currency/ holds 23 TRACKED JSON state files… Each has exactly ONE reader; sampled content is empty objects… `graphify-out/.currency-stamp.json` is ABSENT despite SIX readers."
- **Q11** currency.toml has 22 readers and ~85% prose judgment — ★`strip` (strip what duplicates; keep the judgment where it is) — "22 modules read it… NOT cheap to merge."
- **Q12** The manifests split cleanly — do you want the split? — ★`split` (yes: 16 tool manifests get generated from the pins; 81 corpus manifests stay authored) — "MEASURED: 97 files match `sources/*.manifest`… Only 16 are TOOL manifests duplicating a version pin. The other 81 are pure corpus sources."

**(b) Decisions/rulings verbatim:** none of the three pages records Ray's
actual pick — see structural note above. Each option's "s:" text is the
proposing session's own reasoning, not a ruling.

**(c) Marked OPEN:** every question is open by construction (that is the
page's purpose); rounds 2 and 3 additionally show visible **directional
drift between the pages themselves**: round 2's Q6 defaults to the "auto,
gates catch it" branch of round 1's Q2, even though round 1 recommended
`classify` (needs-review), not `auto` — i.e. the round-2 page's own framing
silently narrowed round 1's still-open question before it was answered.
Flag this explicitly for whoever resumes: **Q2 and Q6 have not been
reconciled**, unless a source below shows Ray closing it.

### A.5 `the-upgrade-schema.html` — added `564a01c9` (2026-08-30, PR #637)

**(a) Summary.** The concrete DB schema for the DBOS/SQLite-backed engine
implied by round-3's Q9/Q10 answers. **Nine tables** in three groups (a
self-correction is recorded in-page: *"this line read 'Eight tables … two,
three, three' until a cold review counted the page's own cards. The real set
is nine — `manifest`, `dep · probe`, `watch`, `watch_review`, `fork ·
upgrade_run`, `stage_event`, `gate_result`. Group 2 always had four."*):

- **Group 1 — truth read out of files:** `dep` (one row/dependency, 33 direct
  today; `pin` is OBSERVED never authoritative — "if it disagrees with the
  file, the file wins and the row is stale"), `manifest` (one row per
  `sources/*.manifest`, 97 today; `owner_dep` NULLABLE — "35 map to a pinned
  dependency, 50 are dependency-shaped but unpinned, 12 are not dependencies
  at all").
- **Group 2 — judgment rescued from currency.toml before deletion:** `probe`
  (one row per declared check — collapses the current `extra_probes` /
  `backend_probes` / `ref_binding` / `docs_watch` / artifact / input-glob /
  skill-stamp constructs into one shape, with a `params_json` escape hatch),
  `watch` (tracked upstream issue), `watch_review` (append-only re-probe log —
  "roughly 900 lines… wearing a blob's clothes"), `fork` (optional, at most
  one row/dependency, all-or-nothing columns).
- **Group 3 — what happened during a run:** `upgrade_run` (one row per
  attempt = the DBOS workflow instance), `stage_event` (append-only, current
  state is DERIVED never updated in place), `gate_result` (one row per
  authorization gate per run, six per run today, from `decide.py`'s six gates
  — "verdict: pass | ambiguous — never a silent third state… fails closed").

**(b) Decisions/rulings verbatim:**
1. *"You ruled the file [currency.toml] gets deleted — 'then add the
   necessary tables to support what would be lost'."* — this is the page's
   own quote of an earlier Ray ruling that currency.toml is deleted in the
   rewrite, with the schema built to not lose its judgment content.
2. Design principle stated as settled: *"every enum here is generated, so
   adding a member is a codegen run rather than a hand-edit — which is
   exactly what your state-machine requirement asks for, applied beyond the
   state machine itself."* (ties to Q4's `status`/generated-enum answer.)
3. The two-clock problem (codex's code-manifest follows a release tag, its
   docs-manifest follows another repo's `main`) is resolved by SCOPING, not a
   bigger enum: `stage_event.manifest` required for source-facing stages,
   forbidden for dependency-level ones; one sub-run per owned manifest.

**(c) Marked OPEN, verbatim from its own "Provenance" section:**
- *"Not yet decided, and deliberately absent from this page: which state
  machine library owns the transitions, and the exact DBOS pin set. Both are
  being researched by codex lanes right now; neither is guessed here."*
- *"Column names are a proposal. Nothing in this schema has been built. It
  exists to be argued with before a spec rests on it."*
- Provenance also flags a **trust gradient** worth carrying forward: measured
  this session at `56b98d8af809` (97 manifests, the codex/codex-docs example,
  a rumdl control arm) vs. **lane-reported, not re-read** (the 35/50/12
  manifest partition, currency.toml's 22-readers/~85%-prose figure, the six
  gates in `decide.py`, the ~900-line re-probe history — "treat them as
  strong leads") vs. **fable-advisor's verdict** (table list, note-splitting
  rule, `stage_event.manifest` scoping, `params_json` hedge, read against
  `currency.toml`/`config.py`/`decide.py`/`manifest.py`) vs. "the DDL, column
  comments and failure reasoning are mine."

### A.6 `two-commands-one-upgrade.html` — added `b1d92a56` (2026-09-03, PR "feat/phase u tool resolution" #707)

**THIS PAGE IS THE MOST DIRECTLY RELEVANT TO THE CURRENT ASK.** Headed "Phase
U · step 0 · why nothing moves." It is later than every other artifact page in
this set and shows the design had, by this point, moved from schema-sketch
(A.5) to **two already-shipped, real commands**:

**(a) Summary.** *"Two commands cover the whole upgrade. Both turn codex away
at the door. Between them they already do every step a version bump needs —
and their coverage does not even overlap."* Six real steps (move the pin,
lock, install, check what actually runs, find the real upstream commit, write
the source pin) split as:
- **`currency apply`** (blue) owns some steps but *"refuses: it only
  auto-applies patch bumps."*
- **`mise run kb-tool-sync`** (green, backed by `tool_sync.py`) owns the rest
  but *"refuses: any tool that has a source in the corpus."*

Worked example: **codex** needs all six steps, but is rejected by BOTH —
*"It is a corpus source, so the green one says no — and 0.152 to 0.153 is not
a patch, so the blue one says no."* Refusal strings cited **from code, this
session**: `tool_sync.py:214,220` and `decide.py:33`.

**(b) The proposal (Ray had not yet said go as of this page):**
*"Nothing here is missing machinery. Every one of the six steps has working
code today. What is missing is that no single command owns all six — so a
real upgrade is carried by hand between two halves that each refuse it."*
Closing ask, verbatim: *"I want to make one command own all six, with the
tool as an argument and the graphify steps off unless asked for. Say go and I
will bring you the plan before any code."*

**(c) Marked OPEN:** the entire page IS the open question — whether/how to
unify `currency apply` + `kb-tool-sync` into one command that also accepts a
corpus-sourced, non-patch tool like codex. **No record found yet (continue
checking sources B/C/D) of Ray having said "go."** This is very likely the
direct ancestor of the "build a dependency-upgrade workflow" proposal Ray
just referenced as "we have been working towards this already" — check
session handoffs after 2026-09-03 for whether this shipped.

**Confirms shipped code as of 2026-09-03:** `mise run kb-tool-sync` (task) /
`python/src/kb_setup/tool_sync.py` (module, referenced lines 214 and 220),
and `decide.py` (the six-gate currency-apply decision engine, line 33 cited)
— both pre-existing this page, not proposed by it.

### A.7 `four-step-upgrade-chain.html` — added `41b33639` (2026-09-01, PR "chore/s1 tool currency 2026 09 01" #651)

**(a) Summary.** Titled "Four Steps, One Broken Check" / "Your 4-step plan ·
corrected 2026-09-01, round 3." A **self-correcting** page: it records that
Ray had proposed a 4-step plan for handling the graphify-fork specifically,
the author (wrongly) proposed suppressing the currency check's "behind"
signal for the fork as noise, and this page **retracts that** after Ray
pushed back. No embedded JS/questions (static page — grepped for `<script>`,
0 hits, so no interactive form to lose here unlike A.2–A.4).

Static page has no form element ("the box below" is likely a rendered
callout, not a working control — could not confirm what mechanism, if any,
captured "the last three decisions").

**(b) Decisions/rulings verbatim:**
1. Opening line, Ray's correction acknowledged directly: *"You were right. It
   is already handled — and my fix would have broken it."*
2. The core ruling about the fork's currency signal: *"graphify showing as
   'behind' is not a false alarm to silence. It is the signal that tells us
   to do step 3. Someone already decided that deliberately, wrote down why,
   and built the checks around it."* Quoted from the config itself: *"a new
   upstream release is still a finding — it is the REBASE TRIGGER."*
3. **On DBOS specifically — a scope-narrowing ruling relevant to A.5's
   schema:** *"The DBOS plan exists, nothing is built, and it already
   answers 'don't build throwaway'. Plain functions in one module, no new
   dependency — adopting DBOS later is adding decorators. What would be
   waste is a new config file: you asked to reduce those, and the current
   one [currency.toml] is slated for deletion."* — i.e., **build plain
   functions first; DBOS is a deferred/optional later upgrade, not a
   day-one dependency**, even though A.5's schema was drawn assuming
   DBOS+SQLite from the start (round 3 Q10 recommended `to-db`). This page
   is dated 2026-09-01, one day after A.5 (2026-08-30) — it appears to
   narrow/soften A.5's DBOS assumption rather than reverse the DB-schema
   idea outright.
4. Root cause of why the check was quiet, stated as fact not question: *"a
   7-day-old cached number. It remembers upstream at 0.9.49 and we are at
   0.9.50, so we look ahead. A full refresh moves it to 0.9.53 and the
   3-release debt appears on its own."*

**(c) Marked OPEN, verbatim:** *"What I need from you: the last three
decisions, in the box below. Still nothing changed."* — three decisions are
solicited but their content is NOT stated on this page; not found elsewhere
in the artifact pages read so far. Check sources C/D for whether these three
were answered in a session or the pwf plan.

Also explicit about its own history: *"Corrected after publishing. The
previous version of this page told you the opposite — that an exclusion was
needed. It was wrong; this page replaces it."* — confirms this artifact was
republished at least once in place.

### A.8 `what-to-pin.html` — added `564a01c9` (2026-08-30, PR #637)

**(a) Summary.** Answers "what exactly goes in pyproject.toml" for the
state-machine + DBOS dependencies A.5's schema presupposes. Two codex lanes
researched separately; the page adds one more finding neither reported.

**Proposal — two lines, as FLOORS (`>=`) per house style (`pyproject.toml:20-24`):**
```
"dbos>=2.31.0",             # durable workflows; SQLite system DB in base package
"python-statemachine>=3.2.1",  # States.from_enum() consumes our generated StrEnum; async native
```
Nothing added to `mise.toml` — both are Python libraries, `dbos` CLI ships in
the same wheel.

**`python-statemachine` won a 6-candidate scoring** (vs. `transitions`,
no-library/generated-enum+table, `sismic`, `Automat`, `statesman`) on: accepts
an externally-defined enum, Python 3.14 metadata, native async, persistence.
Only `python-statemachine` clears every hard axis (`States.from_enum(...,
use_enum_instance=False)`).

**DBOS cost finding (the page's headline new fact):** resolving the two lines
against Python 3.14 pulls **12 packages: 5 already held, 7 new** — including
**two PostgreSQL drivers (`psycopg`, `psycopg-binary`)** that the design never
uses (SQLite is the default store). *"It is not a blocker... It is a cost
worth naming before we pay it... for a database this design does not use."*
Measured via `uv pip compile` diffed against `uv.lock`, with stated control
arms (`dbos>=999.0.0` unsatisfiable; lock-probe finds msgspec, not a bogus
name).

**Self-correction on DBOS's default backend:** *"I told you the opposite
earlier. I said DBOS defaults to PostgreSQL and that SQLite would be the hard
part. That is false for the released 2.31.0. SQLite is the default system
store."* Verified against the released tag, not `main` (an earlier lane had
cited a "merged SQLite PR" that doesn't exist).

**(b) Decisions/rulings — a second, larger finding, verbatim:**
*"The conflict both lanes surfaced independently: Every floor-pinned
dependency is invisible to our own currency engine."* The currency engine
matches only exact `==` (`currency/sync.py:168`, called at `:151`), so
`anthropic`, `httpx2`, `structlog` (floors already in `pyproject.toml`) are
invisible to it today, and `dbos` would join them if added the same way.
**Recommendation (independently reached by a lane too): "change the engine,
not the policy"** — treat a floor's presence in `[project].dependencies` as
proof of ownership, then read the concrete resolved version from `uv.lock`,
rather than forcing an exact `==` pin (which would "export a hard constraint
onto every downstream consumer to work around our own tooling"). This
directly extends A.1's root-cause finding (nothing reads `mise.lock`) to the
Python side (nothing usable reads `uv.lock` for floors).

**(c) Marked OPEN, verbatim from "Provenance":**
- *"Not established by anyone: an end-to-end install of either package on
  3.14.7 (resolution only), and any DBOS-specific integration with a state
  machine library. Both belong in the adopting ticket as its first task."*
- *"Nothing here has been applied. No file was edited; these are lines to
  paste, not lines that exist."* — **as of 2026-08-30, dbos/python-statemachine
  were NOT in pyproject.toml.** Worth checking in "what shipped" whether a
  later PR added them.
- The state-machine risk flagged explicitly: *"no upstream source documents
  the full combination — our generated StrEnum + Python 3.14.7 + a SQLite
  row + DBOS retry/replay. That is an integration probe nobody has run, and
  it should be the first task of whatever ticket adopts this."*

### A.9 `five-decisions-before-the-spec.html` — added `cef09f08` (2026-08-31, PR "chore/cli currency sweep" #639)

**HIGH VALUE — the closest thing to an actual decision RECORD in this whole
set.** Headed "Q0 · the re-grill · session kb-20260830.004." A cold lane read
four prior cold reports + the design page (A.1), answered **11 of 16**
questions itself from repo evidence, and left **5** for Ray. Page banner,
verbatim: *"Updated after publication — four of five now answered. 1 —
enrollment first. 4 — the spec waits. 3 — dissolved by measurement, not
decided... 5 — Ray's call: 'full' means every pin site, 35, not the 18
mapped. Only 2 is still open."*

**(a) Summary of the five, with provenance caveat:** decisions 3 and 5 carry
an explicit inline "ANSWERED" tag with sourcing; decisions 1 and 4 carry only
a "Recommended:" with no inline confirming quote — the page's own top banner
asserts all four (1,3,4,5) are answered, but only 3 and 5 show their
receipt in the body text read here. Treat 1 and 4 as "recommended and
apparently accepted per the banner," not as directly-quoted Ray rulings.

**(b) Decisions/rulings verbatim:**

1. **Decision 1** — *Does dependency population read `mise.toml` directly, or
   inherit the curated list?* Recommended (banner says accepted):
   auto-discover from `mise.toml [tools]` with an **exclude-list** (not the
   current include-list) — "all seven [previously-invisible] tools are
   already in mise.toml... reading that table closes the gap at zero extra
   cost." Mitigation: an exclude-list so new tools default to covered.

2. **Decision 2 — STILL OPEN**, verbatim: *"Where does new tracked state
   live — given the repo already breaks its own rule?"* Live violation
   found: `do-not.md` claimed one exception (`memory/`) but
   `git ls-files graphify-out/` returns a second tracked, undocumented
   subtree, `graphify-semantic-slice/` (5 files). Two self-corrections are
   recorded in-page (checked against live upstream graphify README: *"`graphify-out/`
   is meant to be committed to git so everyone on the team starts with a
   map"* — upstream commits the whole tree by default; this repo inverts
   that only because the graph is 737 MB). Two options laid out: **(a)
   declare it** — amend `do-not.md` to name a second sanctioned exception
   (smaller diff, follows upstream's shape) vs. **(b) move it** to
   `sources/extractions/` (restores "everything under `graphify-out/` is
   derived except `memory/`" as a clean invariant). Author's stated lean:
   *"I lean (b)... But this is a judgment call about which story you want to
   maintain, not a fact the evidence settles."* **No Ray ruling captured in
   this page.**
   **⚠ Cross-check against current `do-not.md` (read live in this session's
   system prompt, rule 5):** *"Do NOT commit `graphify-out/` beyond `memory/`
   and `graphify-semantic-slice/`."* — **option (a) was the one actually
   adopted**, contradicting the author's stated lean toward (b). This is
   confirmed-shipped; see "what shipped" below.

3. **Decision 3 — ANSWERED by measurement**, verbatim: *"`mise run kb-gates`
   at `d08baaa7`: all 7 rc=0, every row `dirty:false` — and the specific
   number was `hk-test: 46 passed, 0 failed (floor 40)`. Note 40+6=46: the
   prior report saw the right test count and misattributed six of them as
   failures. There is no red baseline, so it blocks nothing."* **Residual
   Ray ruling, verbatim:** *"kb-build IS red, but it is not one of the seven
   gates. Ray, 2026-08-31: it stays out (≈55 min, network, re-clones every
   pinned source; a transient DNS failure would become a blocked ship). A new
   seconds-long manifest-audit gate catches the same class before a build
   ever runs."* — i.e. Ray explicitly ruled `kb-build` stays OUT of the gate
   set; a fast manifest-audit gate substitutes for it.

4. **Decision 4** — *Does the spec wait for decision 1, or proceed on a
   stated assumption?* Recommended (banner says accepted): **wait** —
   "Decision 1 is one answer away and it is the cheapest possible moment to
   change it."

5. **Decision 5 — ANSWERED, Ray's ruling verbatim:** *"Ray, 2026-08-31: every
   pin site. 35, not 18."* "Full protocol" is redefined to mean literally
   every pin site (**35**, re-derived as 20 mise `[tools]` + 13 pyproject
   packages = 33, **plus** `[tool.mise]`/`[tool.claude-code]` which sit
   outside the 33 while being real tracked tools). Cost accepted knowingly:
   *"the criterion reads 18/35 on day one and stays red until the 15 are
   mapped. That is a roadmap, not a defect."* **The 15 uncovered, named:**
   mise (7) — `biome, gh, gitleaks, pkl, python, taplo, typos`; pyproject (8)
   — `anthropic, httpx2, mcp2cli, msgspec, pytest, pytest-xdist, structlog,
   trafilatura`.

**(c) Marked OPEN:** Decision 2 only (see above) — everything else on this
page is presented as resolved by the time of its "Updated after publication"
revision.

**Provenance table (CONFIRMED / RE-DERIVED / REFUTED)** — worth carrying
forward as a caution: the widely-repeated "15 of 33 unmapped" figure was
independently **RE-DERIVED and HOLDS**; a previously-reported "hk-test 40
pass / 6 fail" was **REFUTED** (actually 46/0, the same 46 tests
misattributed); a "wrong upstream PR number" claim against a public comment
was also **REFUTED** — the comment was correct and a lane had misread a
refutation as an endorsement. Source reports cited: `.agent/kb/reports/
agents/q0-regrill-questions.md` (333 lines) and `.agent/kb/reports/agents/
dep-inventory.md` — both under gitignored `.agent/`, likely not present on
disk today (verify separately if needed; not re-checked in this pass).

### A.10 `graphify-fork-location.html` — added `b47b60cb` (2026-09-01, PR "chore/round memory 2026 09 01" #646)

**(a) Summary.** "Where The Graphify Fork Lives" — narrow, measured answer
page: *"The fork is github.com/ray-manaloto/graphify — and you are already
running it. The version number in your project file is not what decides
where graphify comes from. One line below it points at the fork instead, and
that line wins."* pyproject.toml said `0.9.50`; a git-dependency override
line fetches the fork at commit `0a2eb5f`, which is what actually installs
and has the patch. *"Seven places in the repo record the same commit and
none disagree."* — cross-checked, not assumed.

**Two problems named, neither fixed as of this page:**
1. *"CLAUDE.md:177 still says `==0.9.48` from a plain package index — wrong
   version, and no mention of the fork. It was written three days before the
   fork landed and never updated."*
2. *"There is a second graphify on your Mac, and it is missing the patch. A
   leftover 0.9.53 install — three versions newer, so any version-comparing
   check reads it as better. It wins nothing today only because of where it
   sits on your PATH."*

**(b) Decisions/rulings:** none yet on this page — it ends with a question,
verbatim: *"What I need from you: say the word and I fix both — one line in
CLAUDE.md, and remove the stale install. Neither is touched yet."*

**(c) Marked OPEN:** both fixes above, pending Ray's word.

**Cross-check against current repo state (this session):** the root
`CLAUDE.md` read at the top of this session's system prompt now describes
`pyproject.toml` as pinning "exact `graphifyy[all]==0.9.53`, installed from
OUR FORK by git rev (never plain PyPI — `sources/graphify.manifest` says
why)" — i.e. **problem 1 (the stale CLAUDE.md line) appears fixed**, and the
pin has since advanced to 0.9.53, matching or superseding the stale leftover
install named in problem 2. Not independently re-verified against
`sources/graphify.manifest` or an actual `which -a graphify` in this pass —
flagging as a likely-shipped item for the consolidation, not a confirmed one.

### A.11 `graphify-fork-lineage.html` — added `e938b471` (2026-08-25, PR "reship/stranded ten" #496)

**(a) Summary.** Earlier/foundational provenance page (predates A.1 by 5
days). Establishes that the fork (`ray-manaloto/graphify`) sits directly on
upstream's newest commit (v0.9.49, `282976b2`) with 7 replanted commits on
top (HEAD `cdfb11c0`), and that the upstream PR it forked to get (#2981) is
untouched/conflicting, so there is currently nothing to rebase onto.

**Directly relevant precedent for the upgrade-protocol's "single source of
truth" question (A.5 Q9, A.8's floor-visibility finding): "One pin, written
in five places"** — a table showing the SAME 40-hex commit must be checked
across: `pyproject.toml [tool.uv.sources]` / `uv.lock` /
`sources/graphify.manifest` / `currency.toml [tool.graphify.fork]` (records
the base, not HEAD) / `graphify_baseline + dispositions` (a **ref-binding
check** in the currency engine). Verbatim: *"A fork ships the same package
name and version string as the release it sits on, so nothing that reasons
from a version number can see it. The only honest check is that all five
surfaces name the same 40-hex commit."* — *"The ref-binding check in the
currency engine is the instrument that finds these — it is what caught four
surfaces a research lane had not predicted when the fork was first cut."*
This is a **concrete, already-built precedent** for the multi-surface-pin
problem the later schema/protocol pages (A.1, A.5, A.8) treat as
theoretical.

**Two watched trigger events, verbatim:**
1. *"A newer upstream release lands → rebase the fork"* (mechanical: replant
   branch onto new tag, push, move the commit in every surface in one
   commit). Noted base rate: "Upstream shipped 15 releases in 15 days when
   last measured" (labelled explicitly as inherited/not re-measured on this
   page).
2. *"#2981 merges and ships to PyPI → retire the fork entirely"* — three
   steps: revert pyproject.toml to an ordinary `==` PyPI pin; point the
   manifest back at Graphify-Labs at the matching tag; delete the
   `[tool.graphify.fork]` block.

**(b) Decisions/rulings:** none new — this is a measurement page. One
self-correction in-page: *"One stale sentence found while checking:
`sources/graphify.manifest` still says the fork reports `0.9.48` and that
pyproject.toml installs `1d0a9338…`. Both were true before the v0.9.49 rebase
and are wrong now."*

**(c) Marked OPEN, verbatim:** *"Neither event notifies us. There is
currently no command that records a watch item as re-probed — that gap is
filed as **issue #486**, and it is the same gap that blocked five reviewed
dependency bumps from landing last round."* — a watch/re-probe mechanism is
named as missing infrastructure directly relevant to any upgrade-automation
design.

Also records (unrelated to the fork, flagged as such in-page) a `kb-build`
failure this session: detect preflight failed on 6 of 84 sources
(unclassified-files in biome/gh/ctx7/firecrawl-cli/trafilatura; a timeout on
ffmpeg) — failed closed, no aggregate artifact/stamp mutated.

### A.12 `the-forks-new-floor.html` — added `1d03e461` (2026-08-26, PR "round/2026 08 25 h openai cli fork" #517)

**(a) Summary.** Documents rebasing the graphify fork's 7 own patches from
v0.9.49 (`282976b2`) onto upstream's new v0.9.50 (`43d54acb`, **"Ray named
that exact commit as the new floor"**) — 17 upstream commits, 1 clash
(CHANGELOG.md only, resolved keeping both), all 7 patches replayed cleanly.

**Methodology worth reusing: a two-armed test as the anti-fake-green check.**
The same 4 test files run against the rebased fork (pass, 48 passed exit 0)
and against plain upstream with the patches removed (4 of 4 fail, distinct
rc's) — *"two different answers ⇒ the test is real... A test suite that only
ever passes proves nothing."* Backed by a second independent check: diffing
old-base→old-tip against new-base→new-tip (changelog excluded) gives an
identical line count, so nothing was dropped in the replay.

**Status-changing fact:** *"New this session... The upstream pull request
that would have made this fork unnecessary — #2981 — is now closed without
being merged. Upstream v0.9.50 still contains zero mentions of openai-cli...
The fork is no longer a temporary bridge waiting for a merge. It is where
this capability lives."* This directly informs why A.11's "retire the fork"
exit path is now moot and the fork must be treated as permanent
infrastructure — matching this session's own root `CLAUDE.md`, which
describes graphify as a fork this repo owns and maintains (`pyproject.toml`
entry).

**The pin-surface count keeps growing — worth flagging as a live pattern:**
A.11 (same day, 2026-08-25) counted **5** surfaces; this page, revised twice
after publication, corrects itself to **8**: *"It was eight surfaces, not
three [an earlier draft's count] — `uv.lock`, the deterministic baseline's
accepted constants, the disposition catalog, and the generated skill stamp
all carry the same pin"* (plus `sources/graphify.manifest`,
`pyproject.toml`, `currency.toml` ref_binding rows named in the table below
it). Verbatim on why this matters: *"Splitting them is how a surface ends up
describing code nobody runs."* **This is the direct, concrete precedent
behind every later page's push toward a single source of truth (A.5 Q9,
A.8's uv.lock-reading recommendation)** — the count of places a version must
agree has been observed to grow every time someone re-audits it (memory
elsewhere in this repo — outside this reading list — puts a later count at
14 pin pairs), which is itself evidence for, not against, building the
`dep`/`manifest` schema in A.5.

**(b) Decisions/rulings verbatim:** *"Ray named that exact commit as the new
floor"* (which upstream commit to rebase onto) is the only explicit Ray
action recorded on this page.

**(c) Marked OPEN / self-corrections:** The page records **two rounds of
post-publication revision** in place (not silently): the "eighth commit"
SHA changed identity after amendment (`825b8fb4` → `0a2eb5fd`, "if you
copied the old one, that is why it resolves to nothing"); the pass count
moved from 38 (seven-commit state) to 48 (after the eighth commit added ten
tests); and *"the pin has now moved, in commit `66a7e1fc`"* — so the pin-move
step is CONFIRMED DONE on this page, not left open.

---

## B. Claude plan-mode files (`~/.claude/plans/`)

**Triage note before the detail below:** of the 10 named files, only **two**
are actually about the dependency-upgrade protocol. The other eight are
plan-mode files for unrelated rounds (the now-removed `graphify-semantic-corpus`
deep-extraction pipeline, a "research funnel" restructuring, config-mutation
tooling, and a dotfiles-repo devcontainer/CI incident) whose keyword hits
(`pin`, `currency`, `upgrade`, `dbos`) were incidental generic-English matches,
not upgrade-protocol content. Reporting this precisely rather than force-fitting
all ten into the narrative, per this task's instruction to report what each
plan *actually* planned.

### B.1 `recursive-knitting-goose.md` — mtime 2026-08-23 04:18 — ⭐ THE DIRECT ORIGIN OF THE WHOLE DESIGN LINE

**THIS IS THE MOST IMPORTANT SOURCE READ IN THIS ENTIRE PASS.** Titled "One
upgrade interface, one orchestrated unit at a time — executing Ray's
2026-08-23 directive" — a week **before** the first artifact page (A.1,
2026-08-30). Its "U2" unit is titled *"ONE upgrade interface: `skill → task →
module`, zero-agent by default"* — this is verbatim the same 3-layer
architecture A.1 later draws as its "shape you asked for" diagram, and its
"two commands" framing is the direct ancestor of A.6. **Cross-check confirms
this plan's design decisions from 2026-08-23 are STILL not implemented as of
this session (2026-09-09), 17 days later** — see verified checks below.

**(a) Summary.** Ray's directive was itself a **re-issue** of a stalled
2026-08-21 directive (epics #435/#436, never worked). The plan lists 18
questions Ray answered directly in "five grilling rounds" that same day
(2026-08-23) — this is an EARLIER round of exactly the grilling-round pattern
later repeated for A.2–A.4 and A.9. Ten work units (U0–U10, plus U2a as an
immediate acceptance test), of which **U2 and U3 are the load-bearing ones**
for the upgrade protocol.

**(b) Decisions/rulings verbatim — the 18-row table, "DECISIONS — settled by
Ray across five grilling rounds, 2026-08-23":**

| # | decision | Ray's ruling |
|---|---|---|
| 1 | corpus spend cap | RE-MEASURE before setting it (real run, stopped early) |
| 2 | currency identity fix | opt-in flag on the `mise_key` path, not a class move |
| 3 | flag rollout | all SEVEN exposed rows, exemption reasoning recorded in `currency.toml` |
| **4** | **U2 entry point** | **"a new `kb-currency-upgrade` wrapping `kb-tool-sync`" — the primitive stays narrow, the wrapper is what skills name** |
| 5 | `/clear-prep` "only" | "only" governs the STEPS; every step becomes a lane; remembered handoff survives as a failure path |
| 6 | durability granularity | per STEP within a lane, from the lane's own declared checkpoints |
| 7 | the 20% context trigger | intent wins over the flag's literal value |
| 8 | stale review lane | REFUSE — no receipt from an agy that disagrees with the pin |
| 9 | biome wiring | restructure the three workflow files; `--skip-parse-errors` disqualified as a measured false green |
| 10 | restructure verification | run each workflow once before wiring the gate |
| 11 | transitive bumps | leave boto3/botocore/pydantic-core — they move with their owners |
| 12 | effort provenance of $1.32 | do not chase it |
| 13 | U6 delivery surface | Ray adds the claude.ai connector first, then U6 builds the page |
| 14 | U0 if rebuild still fails | register failing sources `build = skip` with a written reason, move on |
| 15 | U11 | both — `currency.toml` rows now, AND a gate so a sixth can't appear silently |
| 16 | U5 "in sync" | manifest tracks the tag matching the INSTALLED plugin version, currency row reports drift |
| 17 | this session's scope | **U2a only** |
| 18 | how U2a runs, given U2 isn't built | hand-run it; the transcript becomes U2's spec |

**(b-continued) U2's detailed design, verbatim:** *"Entry point: one task per
Ray's protocol — `kb-tool-sync` widened, or a `kb-currency-upgrade` that
wraps it — reached from the `tool-currency` skill, backed by `kb_setup`
modules. Same entry point for every currency/critical dependency; the
per-tool internals differ behind it."* Reuses existing pieces rather than
rebuilding: `tool_sync._sync`/`_snapshot`/`_restore` (transactional
lock+install, "no partial repository state"), `tool_sync._observed`/
`_validate_observed` (ask the binary), `tool_sync._lock_converged` (`mise
lock --dry-run --json`), `currency.apply.set_pin_version` (a **deliberate**
text edit, NOT `mise use`, because "`mise use` installs as it edits" —
`apply.py:77-78`), `currency.apply` via `manifest.resolve_tag` (raises on an
unresolvable tag), `currency.skill`+`ADDENDA` (graphify-only skill refresh),
`currency.report`. **The incomplete half, named explicitly: corpus/doc
resync via `kb-update -- <name>` — "`apply` deliberately refuses and points
at it... graphify is the hardest and is why this has never been finished."**

**Named bugs/gaps to close, in order (verbatim highlights):**
1. **#372, P0, unfixed**: `mise run kb-currency -- --tool X apply` cannot
   reach `apply` (a positional-arg bug) and **"prints `auto-applying (6/6
   gates)` having changed nothing"** — a false-positive success message.
2. Step-1 "ask the binary" fix identified as a **one-field ownership-class
   change**: only `mise_key`-class rows never execute the binary; `expected`
   and `python_package` classes already do via `_check_self_managed`. **The
   exposed set: 7 currency rows — `agnix, antigravity-cli, codex, doppler,
   ffmpeg, hk, uv`.**
3. Widen the entry point across ownership classes — `eligible_tools()` is
   "deliberately mise-only," excluding `ty` (python_package) and
   `claude-code` (expected). Ray's words quoted: *"internals can be
   different, entry point should be the same."*
4. **Point the skill at the task**: *"`grep -c 'kb-tool-sync'` in
   `tool-currency/SKILL.md` → 0. A built, tested, transactional task that the
   owning skill never names is indistinguishable from one that does not
   exist."*
5. **"THE SECOND SKILL TREE — Ray named it, and the engine has never heard
   of it."** Ray's own words quoted from the directive: *"include the skill
   updates and verifying these versions: `.claude/skills/graphify/
   .graphify_version` · `.agents/skills/graphify/.graphify_version`."*
   Measured: both tracked, both read `0.9.48` at the time — **"by luck, not
   by mechanism"** — because `currency.toml`/`currency/skill.py` track ONLY
   `.claude/skills/graphify` (0 mentions of `.agents`). Deliverable specified:
   *"`skill_dir`/`skill_stamp` become plural, the refresh regenerates both
   trees, the upgrade verifies both stamps, and a gate fails when they
   disagree."*

**Zero-agent acceptance criterion, Ray's ruling verbatim (paraphrased in
plan, attributed to him):** *"a clean bump completes with no agent turn; an
agent is summoned only when a step refuses."*

**U3** (run the interface on 8 real bumps as U2's acceptance test):
antigravity-cli, hk, rumdl (mise); ty, tree-sitter, boto3/botocore/
pydantic-core (uv, transitive — "decide, don't sweep"); claude-code 2.1.240→
2.1.241 (the `expected`-class case).

**(c) Marked OPEN, verbatim:** *"The re-review's structural verdict... 'the
dominant defect is NOT missing detail — the plan is unusually well-evidenced
— it is UNDECIDED CHOICES STATED AS PAIRS.' Eight of twelve units contain at
least one, and only U10 and U8's `b0` are READY as written."* Session scope
was explicitly narrowed to **U2a only** (decision 17); U2/U3 (the interface
itself) were deferred to a later round — **exactly the round the current
"build a dependency-upgrade workflow" ask is now reopening**, 17 days later.

**⚠ VERIFIED TODAY (2026-09-09) — these 2026-08-23 gaps are confirmed STILL
OPEN, not stale claims:**
- `kb-currency-upgrade` (decision #4's named wrapper task): **grep returns
  zero hits** anywhere in `mise.toml`, `python/src/kb_setup/`, or
  `.claude/skills/tool-currency/SKILL.md`. Never built.
- `tool-currency/SKILL.md` mentioning `kb-tool-sync`: **still 0** (checked
  this session) — gap #4 above is unresolved 17 days later, exactly as
  A.6 (2026-09-03) independently re-discovered from a different angle.
- `mise.toml`'s `[tasks.kb-tool-sync]` description today: *"Lock, install,
  and verify one eligible reviewed mise-only tool pin"* — **still says
  "mise-only"**, meaning gap #3 (widen across ownership classes) also
  appears unresolved.
- The second-skill-tree stamps: `.claude/skills/graphify/.graphify_version`
  and `.agents/skills/graphify/.graphify_version` **both read `0.9.53`
  today** — still agreeing "by luck," and `currency/config.py:241` still
  declares a **singular** `skill_stamp: str = ""` field (not the plural the
  plan's deliverable specified) — gap #5 also appears unresolved.

**This means: the next round does not need to re-decide U2's shape — Ray
already decided it on 2026-08-23 (decision #4, verbatim above). It needs to
either build `kb-currency-upgrade` as specified, or explicitly re-open
decision #4 if the later `two-commands-one-upgrade.html` (A.6) framing
(2026-09-03) is meant to supersede it.**

### B.2 `starry-skipping-torvalds.md` — mtime 2026-08-25 12:49 — "Config mutation without hand-editing — APPROVED plan"

**(a) Summary.** A related but distinct initiative from B.1, two days later:
stopping agents from **hand-editing** `mise.toml`/`pyproject.toml`/
`currency.toml`/`sources/*.manifest` at all. Context, Ray's mandate verbatim:
*"agents must not hand-edit config files. All mutation... goes through a
sanctioned command, so an agent runs an API call instead of reasoning about
file bytes."* Trigger: the author `sed`-edited three config surfaces, made
one mistake (`hk = "v1.56.1"`, filed #499), and "my response was to take the
work away from the automation rather than fix it."

**(b) Decisions/rulings — a second grilling round (Q1–Q12), key ones
verbatim/paraphrased:** Q2: **one `kb-config` CLI** with per-file verbs
(`kb-config currency set-version <tool> <version>`, `source add|remove`,
`pin set`) — generalizing the already-existing `set_pin_version` (mise-pins
only) across all four file types. Q3: a comment-preserving writer is already
the implemented design. Q4: **openai-cli backend is the immediate goal;
config work sits behind it** (rumdl 0.2.60 sanctioned as a one-off hand-bump
to unblock). Q9: **consolidation review DEFERRED entirely until openai-cli
lands.** Q10: add all 14 currency blocks now, in the current shape (accepting
rework risk if Q9's consolidation later restructures them) — **this is the
plan's own count of "14 currency blocks," one more provenance point for the
pin-surface-count-keeps-growing pattern noted at A.12.**

**Confirmed DONE at time of writing:** P0 (fixed a published-artifact error,
commit `2dee8d58`) and P1 (rumdl bumped to 0.2.60 through the sanctioned
path, `[tool.rumdl]` added, #485 closed) — both marked ✅ in the plan.

**A genuinely important correction recorded mid-plan (§10, "RE-SCOPED
2026-08-25f AFTER A CONTROL-ARMED RE-READ"):** the original P1b root-cause
diagnosis was wrong on all three counts it made (whether `--refs` strips a
peeled tag line — it doesn't; whether a tag-object SHA "breaks
reproducibility" — it doesn't, `kb-build` peels before verifying by design;
and whether "only agnix and rumdl are known-correct" — refuted, the corpus
is already split 5-peeled/4-tag-object across 9 annotated manifests). **The
real, surviving defect (#501):** `latest_commit()` also returns the tag
object and is compared raw against the recorded commit, so for the 5 peeled
sources `kb-update` reports a false "advance" **every run** — full re-clone
+ re-extraction for a source that never moved. Stated invariant: *"
`latest_commit()` and `resolve_tag()` must return the SAME git identity, from
ONE shared code path."*

**(c) Marked OPEN / deferred, verbatim:** *"The consolidation review (Q9) —
deferred entirely until openai-cli lands... `.codex/hooks.json`'s CONTENTS —
the only thing still unprobed... `session-select` codegen task + gating the
codegen checks."* **Standing risk flagged:** *"Subagent lanes go idle
without returning reports — 3× this session... Every fact in this plan that
a lane was supposed to supply was instead probed in-session."*

**⚠ VERIFIED TODAY:** `kb-config` (P4's proposed unified verb surface) —
**grep of `mise.toml` returns zero hits.** Never built; `set_pin_version`
remains mise-pin-only, exactly as this plan found it. This is a second,
independent "unify the config-mutation surface" ask (distinct from B.1's
`kb-currency-upgrade`) that also never shipped — worth flagging to whoever
scopes the next round, since a third unification attempt should either
subsume both or explain why it doesn't.

### B.3–B.10 — the remaining eight plan files: NOT about the upgrade protocol

Checked each against specific markers (`kb-tool-sync`, `kb-currency-upgrade`,
`dbos`, `state machine library`, `one upgrade interface`, `upgrade
protocol`) — **zero hits across all eight.** Their titles and content
confirm they are separate initiatives; recording briefly for completeness
since the task asked about all ten:

| File | mtime | What it actually is |
|---|---|---|
| `squishy-sniffing-book.md` | 2026-08-26 19:38 | "Make the knowledge-base actually be the research funnel" — corpus-ingestion tracking (a proposed `[source.*]` table type in `currency.toml`, distinct from `[tool.*]`); mentions `currency.toml`'s then-19 `[tool.*]` blocks only incidentally. |
| `i-enabled-plan-mode-nifty-breeze.md` | 2026-08-15 17:52 | "Recover the knowledge base, then document it so anyone can continue" — disaster-recovery/rebuild session, the earliest file in the set; incidental `sources/graphify.manifest`/`currency.toml` mentions from that recovery work. |
| `kb-resume-indexed-rossum.md` | 2026-08-24 08:01 | "Native graphify migration — backend decision + multi-source storage" — the session that decided to investigate forking graphify for an `openai-cli`/codex backend (dispatches `pr-fork-lane` to research PR #2981). **This is the direct ancestor of the graphify-fork storyline (A.10–A.12)**, not of the general upgrade-protocol pipeline. Ray's ruling quoted: *"just do native graphify extract/reflection/generate output. stop doing internal hashing."* |
| `twinkling-shimmying-hanrahan.md` | 2026-08-22 22:04 | "Land PR #463 with the unpushed `d85f2835`" — ordinary ship/land bookkeeping for a one-line config commit; no upgrade-protocol design content. |
| `rustling-booping-locket.md` | 2026-08-21 01:44 | "Land #422, then the pre-run gate bundle" — entirely about the now-removed `graphify-semantic-corpus` deep-extraction pipeline (slice re-attestation, runtime-identity refusal, content-hash dedupe). Unrelated subsystem, since retired. |
| `can-we-update-the-optimized-sky.md` | 2026-08-18 09:38 | "session-review: ship the verified slice, then let it audit its own plan" — fixing the `kb-session-review` workflow itself (cache keys, agent-count math, prompt contracts) plus the graphify-semantic-corpus "circle" diagnosis. One incidental graphify point-bump (0.9.44→0.9.45) in a 8-item verified-slice table. |
| `i-changed-to-plan-bubbly-sprout.md` | 2026-08-17 15:46 | "Plan — native-workflow-first session review (Ray's 2026-08-17 directive)" — building the session-review-as-a-workflow mechanism; graphify 0.9.45→0.9.46 appears only as one deferred "Phase 4" bump task, not upgrade-protocol design. |
| `run-session-resume-then-tell-peppy-bachman.md` | 2026-09-03 17:19 | **Not this repo at all** — a devcontainer/CI incident (`apt:gnupg` pin conflict, Renovate PR #947, `mise run ship`/`land` not `kb-ship`/`kb-land`, issues #962–966, `.github/ci.yml`). This is the **sibling dotfiles repo** (which has CI; knowledge-base does not, per `gh-cli-watch.md`). Included here only because the task named the file; it carries no upgrade-protocol-design content for **this** repo. |

---

## C. The live pwf plan `.planning/2026-08-30-upgrade-protocol-spec/`

**This directory IS the working plan for the exact deliverable this task
asks about** — its `task_plan.md` header, verbatim: *"Goal: Turn the five
design artifacts from session `kb-20260830.002` into a reviewed, tracked
spec for the zero-token dependency upgrade protocol, with #637 landed and
#638's refuted claims corrected on the issue so the chain head stops reading
as settled."* "The five design artifacts" = A.1, A.5, A.8, A.9's ancestor
(the "clear-to-spec" Q0 regrill), and `what-to-pin.html`. **#637 = the PR
that added A.1/A.2-4/A.5/A.8 (`564a01c9`).** `#638` = a companion
issue/PR carrying claims that needed correcting — not independently read
this pass.

**⚠ Scope note the next round needs: `task_plan.md` is 2,800 lines and has
been REPURPOSED into this repo's general rolling task backlog** — it now
also carries Phase T (ty LSP wiring), Phase G (graphify openai-cli
provenance), Phase N (2026-09-01 resync), and Phase U (codex/graphify/claude
setup + the "replicate hosted graphify in `kb`" programme, U-R/U-G/U-P/U-S/
U-B/U-X) — all separate initiatives, extensively covered already in this
session's own auto-loaded MEMORY.md. This report extracts ONLY the sections
that are actually about the dependency-upgrade protocol: Phase S1, S1a, S2,
2e, 2f, and the original Phase 2/3/4/5 (design questions → spec → review →
close).

### C.1 Phase S1 — First-level dependency currency (Ray's step 1, 2026-09-01) — ✅ SHIPPED

Ray, verbatim: *"make the very step be updating all first level dependencies
to the latest version so these commands dont show anything outdated for
first level dependencies and resync graphify sources."* **Ray's own
diagnosis of why nothing was moving, verbatim and confirmed correct:**
*"dont we already have most of this as a skill -> mise task -> python
library module(s)/function(s)? i just dont think the skill is triggering."*
Confirmed: `tool-currency/SKILL.md` says to fire "when the SessionStart hook
reports drift"; the hook DID report drift at session start and the skill was
never invoked — `hook_guard.py` mentions currency **0 times** (vs
`graph_first`'s 9).

10 first-level deps bumped (5 mise: uv/hk/typos/agnix/antigravity-cli; 4
python: datamodel-code-generator/mcp2cli/ruff/ty; 1 separate: anthropic
1.0.0→1.3.0, the only non-patch bump, isolated in its own PR for easy
revert). Plus 2 self-updating tools needing separate `currency.toml`
`expected` + manifest moves: claude-code and mise. **Status line, verbatim:
"complete — LANDED. `mise outdated -b --local` prints 'All tools are up to
date'; `uv tree` first-level outdated is 0."** Commits: `ac7e4522`,
`5a1dd6b9`, `5fb0cfa7`, `933b1207`.

**A ruling worth carrying forward as a standing fact, verbatim:** graphify's
"behind" status must NOT be excluded from currency checks even though it's a
fork — `currency.toml:182-186`: *"a new upstream release is still a finding
— it is the REBASE TRIGGER."* (This is the same ruling A.7 records reaching,
independently, the next day.)

### C.2 Phase S1a — five currency-engine defects S1 exposed (RESEARCH ONLY, not fixed)

Ray: *"did something die? if yes, we need to add a task plan item to
research how to fix it and add a github issue for it."* All five filed with
repro + control arms:

| Issue | Defect |
|---|---|
| **#647** | `currency apply` advances the manifest but NOT `graph.py`'s pinned_commit values (each also needs its `content_sha256` RE-DERIVED) — **BLOCKS the uv bump**, a naive fix is silently wrong |
| **#648** | `--json` output is interleaved with `[currency]` log lines; `json.load` fails (a `raw_decode` loop recovers only 1 of 20 objects) |
| **#649** | Nothing enforces the `tool-currency` skill — same gap S1 found (`hook_guard` currency mentions: 0) |
| **#650** | lychee's tag scan picked a **NINE-RELEASE DOWNGRADE** (`0.24.2 -> v0.15.1`) — cannot see the `lychee-v*` tag family, maxes an abandoned `v*` family instead. Effectively unwatched. |
| #483/#372 | `apply` cannot bump a pyproject-pinned tool at all (confirmed live on ruff+ty, rc=2) — pre-existing |

**Ray's ruling on how to treat these, verbatim — the single most important
line in this file for scoping the next round: "Reconcile all five against
#638's `kb-upgrade` design before fixing any of them — Ray: 'i dont want to
build throw away work so we can get the dbos work done which is the final
end state.'"** This is decisive: **DBOS remains the intended FINAL STATE**
as of 2026-09-01 (reconciling, not contradicting, A.7's "plain functions
now, DBOS later" — both agree DBOS is deferred construction, not a deferred
goal). It also confirms **`#638` names an existing design called
"`kb-upgrade`"** — a concrete prior-art name the next round should look up
directly rather than re-deriving.

Also decided: a guard against #650's class — *"a proposed version LOWER than
the current pin must be refused outright, never offered as a bump"* — and
this defect class was named explicitly as NOT isolated: *"graphify's eighth
pin site is the same shape [as #647], so uv is the second confirmed
instance."* **Status: pending (research only, not fixed) as of this
writing.**

### C.3 Phase S2 — give the graphify fork a real home (Ray's step 2) — ✅ SHIPPED (per Decisions table)

Ray: *"move the graphify local workspace to
/Users/rmanaloto/dev/github/ray-manaloto/graphify so we stop working in a
scratch directory."* Finding: **nothing could be moved — the fork's `/private/
tmp` scratchpad work tree had already been reaped by macOS** (1,828
directories, 0 files survive) — but nothing was LOST, because the branch had
been pushed (`kb-pin/openai-cli-backend-v0.9.50` intact on GitHub at
`0a2eb5fd`). This is the durable lesson recorded verbatim: *"agent work in
`/private/tmp` session scratchpads is reaped in days and nothing watches it.
This patch survived only because it was pushed. Anything you would mind
losing gets pushed in the session that creates it."* The later "Decisions
Made" table confirms this shipped: *"The fork lives at
`~/dev/github/ray-manaloto/graphify` (Ray, Q7/Q10)... Moved (not re-cloned)
with its 287MB of objects, branch renamed to the canonical
`kb-pin/openai-cli-backend-v0.9.53`, `upstream` remote added."*

### C.4 Phase 2e — rebase the graphify fork onto v0.9.53 — checklist status "pending" at last write, but branch-name evidence suggests it proceeded

Ray, 2026-08-31, verbatim: *"update the graphify fork to rebase on the
latest graphify git tip as it has been updated to graphify 0.9.53 and we are
still on graphify 0.9.50."* Measured then: 3 releases behind (.51/.52/.53);
fork's divergence IS the openai-cli work, "which is what makes this rebase
risky rather than routine." Fork default branch is `v8`; pin branch
convention is `kb-pin/openai-cli-backend-v0.9.5x` (never rebase/force-push
`v8` itself).

**The pin-site checklist here lists EIGHT sites — cross-confirms A.12's
independently-reached count exactly:** `pyproject.toml:32` (`==` pin),
`pyproject.toml:246` (`[tool.uv.sources]` git rev), `uv.lock` (3 line refs:
version + 2 fork-rev occurrences), `currency.toml [tool.graphify]`,
`sources/graphify.manifest`, `CLAUDE.md`, **`graph.py:541 pinned_commit`**
(named explicitly as "the EIGHTH site... found by the cold session lane via
codex"), `graph.py:540 content_sha256` (must be RE-DERIVED from the new
clone, never carried forward — "carrying it is the silent-wrong case, since
it still looks like a hash"). Explicit anti-pattern named: *"A tool bump
must advance its manifest AND its lock; a partial bump is drift that reads
as current."*

**Standing hazards recorded verbatim, worth repeating to any future round:**
*"THE GRAPHIFY CIRCLE is mechanical. Do NOT pin harder to escape it."* /
*"The graphify bump is not a one-line change — it never has been here."* /
*"`kb-currency apply` is unreachable for graphify, so this bump is done by
hand."* / **"A fork hides behind an unchanged version string — the fork can
report 0.9.53 and still have lost a patch. The version number is not the
check; `backend_probes` is."**

**Cross-check against today's actual repo state:** this session's own root
`CLAUDE.md` (loaded at conversation start) states the current pin as exact
`graphifyy[all]==0.9.53`, matching Phase 2e's TARGET version — strongly
suggesting this phase completed since it was checklisted "pending," though
the individual checkbox items were not independently re-verified in this
pass (recommend a fresh `mise run kb-manifest-audit` + `mise run
kb-currency-check` to confirm tier-1 pin agreement before assuming done).

### C.5 Phase 2f — resume the openai-cli backend work (the standing end goal) — status "pending"

Ray, 2026-08-31: *"need to eventually get back to the openai-cli work before
we forget about it"* — restated from the 2026-08-28 directive's *"the
ultimate goal of graphify setup starting with openai-cli backend."* Ordered
right after 2e because *"the fork's entire divergence from upstream is
openai-cli work."* Planned steps (none checked off): re-establish where the
work stopped by reading code, not memory; confirm `do-not.md` #4's sanctioned
backends still hold; cheapest-rung-first validation (ONE file via `--backend
openai-cli`); only then one real source end-to-end with cost named up front;
decide (with evidence) whether openai-cli becomes the DEFAULT corpus
extraction path or stays opt-in.

### C.6 Phase 2/3/4/5 — the ORIGINAL deliverable this whole plan exists for — ⚠️ LARGELY NOT DONE

**This is the single most important status finding in the entire report.**
The plan's own Phase 2 ("Answer the five open design questions") shows only
**Q0 checked** (the re-grill prerequisite); **Q1–Q5 are unchecked**, status
line verbatim: *"pending — resumes after 2c and 2d."* Its own Q5 ("full
protocol or slice 1 for `/to-spec`") is the SAME question A.9 shows Ray
answering on 2026-08-31 ("every pin site, 35 not 18") — so the checklist may
simply be stale relative to A.9's publication, OR the checkbox is
specifically gated on a further step: *"Publish the answers back into
`docs/artifacts/clear-to-spec.html`"* — **a page not in this task's reading
list**, and worth the next round fetching directly, since it may be the
actual up-to-date consolidated answer sheet (title suggests it is literally
named for turning the design "clear" enough "to spec").

**Phase 3 ("Write the spec") — ALL UNCHECKED, status "pending."** Its own
first checkbox names the load-bearing premise still needing verification:
*"floors vs `==` in `currency/sync.py:168` — this is what makes 15 of 33
dependencies unmapped"* (= A.8's finding). **Phase 4 ("Review and break into
tickets") — ALL UNCHECKED, status "pending."** **Phase 5 ("Close the
round") — ALL UNCHECKED, status "pending,"** including its own last
checkbox: *"ARCHIVE THIS PLAN DIRECTORY — otherwise it re-injects into every
future session"* — confirming why `.planning/2026-08-30-upgrade-protocol-
spec/` still exists on disk today, unarchived.

**The plan's own "Current Phase" pointer (read separately) confirms the
round never returned to finish this**: it names **Phase G** (graphify
openai-cli provenance) as current, with Phase T and Phase U having
successively outranked the original upgrade-protocol spec work. **The spec
that A.1–A.9 designed was never actually written up as a formal spec
document, reviewed, or broken into tickets — this is the single biggest gap
for the next round to close**, and it is exactly what "we have been working
towards this already" is pointing at: the design work (A.1–A.9, B.1, B.2) is
substantial and mostly decided; the SPEC-WRITING step that was supposed to
consume it (Phase 3) never ran.

### C.7 Decisions Made / Errors Encountered (plan-mechanics, not upgrade-protocol design)

Mostly about the pwf-planning-tooling itself (plugin mode, `.planning/`
gitignored, `progress.md` vs `ledger-main.jsonl`), not the upgrade schema.
One relevant carry-forward: *"`kb-build` RED is NOT in this plan — graphify
#1666 is an upstream defect, not a design decision. [Its] own plan."* Errors
table: a `kb-ship` refusal was masked by a background notification reporting
`exit 0` when nothing had actually been pushed — caught only by checking
`gh pr view` directly (reinforces this repo's own `verify-before-advancing.md`).

### C.8 `findings.md` (read in full) — two facts worth carrying into the next round's design

**The tag-vs-commit resolution bug is a CLASS, not a one-off — now confirmed
on a SECOND tool (mise), independently of B.2's graphify/#500/#501 finding.**
Verbatim, "THE LANDMINE, reproduced live (#395)": *"`gh api
repos/jdx/mise/commits/v2026.8.15 --jq .sha` → `06c9ad7a39b1…` [the COMMIT]
vs `git ls-remote --tags <url> v2026.8.15` → `b4f948d8349c…` [the TAG
OBJECT]. mise ships ANNOTATED tags, so `ls-remote` returns the tag object.
It is silent because `git checkout` peels a tag object — the clone is right
while the recorded provenance is wrong... it cost this repo weeks of a wrong
`commit` value once already."* **Any upgrade-protocol spec must pin the
resolution METHOD, not just the resulting SHA, or this recurs per-tool.**
Open question sent to `kb-advisor` and left unanswered here: does
`min_version.hard` move for a tool's own self-update, or only the manifest +
`expected`?

**The exact code-level root cause for A.8's "floors are invisible" finding,
confirmed independently by a codex lane's re-verification of issue #638:**
*"The mechanism (`sync.py:168-205`): `version_pattern` requires `==`,
`vcs_pattern` requires `git+https`, and no floor pattern exists — so
`anthropic>=1.0.0` yields `("", ())`."* Also reconfirms the **15-of-33
unmapped** figure with the full 15 named (7 mise-side: python, pkl, typos,
taplo, biome, gitleaks, gh; 8 pyproject-side: anthropic, httpx2, msgspec,
structlog, pytest, pytest-xdist, trafilatura, mcp2cli) — matching A.9's
later list exactly.

**Correction chain on the DBOS SQLite PR citation — now three citations, two
wrong, worth recording so a fourth session doesn't re-cite the wrong one:**
issue #638 originally cited DBOS issue #101 as a "merged PR" (it's a closed
*issue*, no PR closer); a prior session's correction claimed the real PR was
**#680** (wrong — that closes unrelated issue #679, "Retry Serialization
Errors in Datasources"); **the actually-correct citation, verified directly
by `gh api search/issues`: PR #441, "SQLite Support," merged 2025-08-27**
(corroborated by follow-ups #553/#564/#790). Nuance for A.8's `what-to-pin`
recommendation: DBOS's own README still describes itself as "built on top of
Postgres" throughout — SQLite support is real but is not the headline path.

**Skipped as off-topic for this report** (present in `findings.md` but not
about the upgrade-protocol schema): four codex-lane infrastructure defects
(C-1 model-not-pinned, C-2 missing effort in codex-side mirror, C-3 MCP auth
failures, C-4 SessionStart hook failure on every codex launch) and a
skills-integration review of `clear-prep`/`session-resume` (10 findings, 3
P1) — both belong to the Phase-T/codex-setup thread this session's MEMORY.md
already covers extensively.

### C.9 `progress.md` (read in full) — confirms the plan's own completion state, chronologically

Corroborates C.6 independently: *"This plan is NOT complete — `check-
complete.sh` reports 1/5 phases done, 1 in progress, 3 pending. So it must
NOT be archived"* (2026-08-30 boundary) → *"Plan grew 8 -> 14 phases... NOT
archived: 2/14 complete, 1 in progress, 11 pending"* (2026-08-31 boundary,
after PR #639 landed). The log continues through **2026-09-03** (U-R0
landed as PR #677; a do-not.md repair round; Phase U step 0 + codex 0.153.1
resync; the live-PATH question) — **all of that later activity is Phase
T/G/U work, never a return to Phase 2/3/4/5 of the upgrade-protocol spec
itself.** This is the clearest confirmation available that the spec-writing
step was set aside, not finished, when the round's priorities shifted.

One other durable, cross-cutting fact recorded here: PR #639's own review
found **an eighth graphify pin site "that would have red-lit the gate
shipped this round"** — the same eighth-site fact as A.12/C.4, now dated to
its actual landing (2026-08-31, `cef09f08cfe2`) rather than only to the
design pages that discussed it.

---

## D. Session handoffs (`.agent/plans/session-2026-08-3{0,1}-*.md`, `session-2026-09-01-*.md`)

Grepped for `upgrade|currency|S1|fork|rebase|pin`, relevant regions read.
These are chronological checkpoints of the SAME work already covered in A/B/C
— reported here mainly for exact PR/commit numbers and one live self-
correction the design pages don't show.

### D.1 `session-2026-08-30-g.md` — PR #637 open

Confirms A.1–A.9's context: currency-sweep PR #637 open (5 patch pins +
`min_version`, 13 pins verified already-latest); 3 `/grilling` rounds run
(= A.2–A.4); 97 manifests partitioned A=35/B=50/C=12 (matches A.9 exactly).
**States a finding worth flagging because the very next handoff refutes
it** — verbatim: *"Exactly ONE of 75 mise tasks names an LLM backend, and it
is not in the upgrade pipeline. **A full zero-token upgrade is achievable
today.**"*

### D.2 `session-2026-08-30-h.md` — same-day correction of D.1's headline claim

**⚠ Directly refutes D.1, same day, after a 3-lane review of issue #638:**
verbatim, *"'A full zero-token upgrade of every dependency is achievable
today' is FALSE — but not for the reason codex gave. The token axis holds...
It fails on **coverage**: 15 of 33 direct dependencies have no currency
mapping."* **Report this pairing to whoever scopes the next round: the
optimistic zero-token claim was made and retracted within the same
day/round — cite the coverage caveat, not the bare claim.**

Confirms `clear-to-spec.html` is the artifact holding the AUTHOR'S
recommendations (pre-Ray-answer) for the same 5 design questions A.9 later
shows Ray answering — *"Each has my recommendation on the page; none is
answered"* at this point. Lists **"Seven I already decided"** (settled,
non-controversial facts worth reusing rather than re-deriving): `pyproject-
direct` = every explicitly declared requirement (version read from
`uv.lock`); all three gate layers run; no commit for a failed dependency;
`source_synced` is per-manifest; missing manifests are valid nullable
mappings; **`kb-upgrade` does NOT call `kb-ship`** (an architectural
boundary decision); `python-statemachine>=3.2.1` (A.8's pin, adopted).

Also repeats the DBOS-PR citation error one step into its own correction
chain: names PR **#680** as the real merged SQLite PR — itself later refuted
by C.8's finding of the actually-correct PR #441.

### D.3–D.4 `session-2026-08-31-{c,d}.md` — mostly Phase 2c/2d bookkeeping; one Ray ruling on A.9's open decision 2

Confirm the "eight pin sites" figure is now standard (graphify's rebase, the
8th being `graph.py:541`). **Session -d surfaces what appears to be Ray's
actual answer to A.9's still-open "Decision 2" (the `graphify-out/` second
tracked subtree vs `do-not.md`'s claimed one exception), not captured in any
artifact page read in this pass:** *"Decision 2 — `graphify-out/` two tracked
subtrees vs `do-not.md` #5 asserting one — CARRIED, unstarted. Ray's answer
stands: merge both into graphify's own preferred layout, updating
`.gitignore`, `do-not.md` and `CLAUDE.md` together."*

**⚠ Possible discrepancy worth the next round checking directly (not
resolved in this pass):** this handoff's Ray ruling reads as "restructure to
match graphify's own preferred layout" — a bigger change than simply
declaring a second exception. But the do-not.md text loaded at the top of
THIS session's own system prompt (rule 5, checked live) reads: *"Do NOT
commit `graphify-out/` beyond `memory/` and `graphify-semantic-slice/`"* —
which reads as the simpler "declare a second sanctioned exception" (A.9's
option (a)), not a structural merge into upstream's layout. Both facts are
real; whether the shipped fix matches Ray's fuller intent, or only
partially implements it, was not traced to a specific commit in this pass —
worth a `git log -p -- do-not.md` on that section before assuming either
way.

### D.5–D.6 `session-2026-09-01-{a,b}.md` — Phase 2e still "planned, not started"

Both state, verbatim/near-identical: *"Phase 2e — the eighth graphify pin
site, `python/src/kb_setup/graph.py` — CARRIED, untouched. The fork rebase
to v0.9.53 is planned, not started."* Confirms C.4's status read (Phase 2e
was still pending at this point, later evidence — this session's CLAUDE.md
showing 0.9.53 installed — suggests it did complete at some point after).
Also flags a related, narrower gap: *"`currency.toml` has no
`[tool.agentsview]` — a pinned tool we do not track"* — carried across both
handoffs as undecided.

### D.7 `session-2026-09-01-c.md` — ⭐ S1 COMPLETE and LANDED — exact commits

**The most concrete "what shipped" evidence in this pass.** Verbatim: *"S1
of Ray's 4-step chain is COMPLETE. `mise outdated -b --local` prints 'All
tools are up to date'; `uv tree --outdated` first-level is 0."* **Landed as
issues/PRs #646 (`b47b60cbc271`) and #651 (`a7a8dd69cdf4`).** Ten
first-level deps bumped by exact target version: `antigravity-cli` 1.1.23,
`ruff` 0.16.5, `ty` 0.0.77, `anthropic` 1.3.0, `mcp2cli` 3.7.0,
`datamodel-code-generator` 0.76.0, `typos` 1.50.0, `uv` 0.12.8, `agnix`
0.52.1, `hk` 1.57.0.

**A cold review (codex, cross-family) caught a real P1, fixed in the same
round:** ruff/ty/dcg were bumped in `pyproject.toml` but NOT propagated to
3 manifests, 2 `graph.py` `pinned_commit`s, and 3 `currency.toml`
`expected`s — **the exact #647 "tail" defect class, self-inflicted and
caught by review rather than by the gate.** This produces the clearest
general checklist recorded anywhere in this pass for **"what a complete tool
bump actually touches," worth lifting verbatim into any future spec:**
*"manifest + `graph.py pinned_commit` + `content_sha256` (RE-DERIVE, never
carry forward) + `currency.toml expected` + the local clone synced to the
pin (tier 2 compares against the CHECKOUT)."*

**The tag-object-vs-commit landmine (C.8, B.2) is now confirmed on FOUR
independent tools** — graphify (B.2/A.12), mise (C.8), and here **typos**
(`v1.50.0` → tag `7e602057` vs commit `4d9c206a`) and **agnix** (`v0.52.1` →
tag `acb895a7` vs commit `d18c0a88`), with ruff/ty/dcg serving as the control
arm (lightweight tags, no second `^{}` line, so no divergence possible).
**This is unambiguously a systemic defect in the manifest-resolution
mechanism, not a per-tool quirk — any upgrade-protocol spec must fix the
resolution method once, centrally, rather than patch it per tool.**

One unrelated but sharp trap recorded here: *"`Builtins.gitleaks` now scans
the whole tree and does not read `.gitignore`. A gitignored `.agent/` file
CAN red `mise run lint`."*

---

## Cross-check against the live repo (done this session, not inherited)

- `mise.toml:1054` — **`kb-manifest-audit` EXISTS**: "Gate: registry entries
  still agree with `sources/*.manifest` (offline tier 1) + clone
  freshness/coverage (tier 2)" — built directly from this design line's
  repeated "the tail gets forgotten" finding.
- `pyproject.toml` — **`dbos` and `python-statemachine` are ABSENT.** A.8's
  "nothing here has been applied" is still true today.
- `pyproject.toml:32,264` — current graphify pin: `graphifyy[all]==0.9.53`,
  fork rev **`157a957e89a16246bba3a078de2777711ee85e31`** — a DIFFERENT,
  newer commit than the `0a2eb5fdd3110b821bc4fa2759bc964a8bc0a956` every
  design page (A.10–A.12, C.4, D) centers on, confirming the fork has been
  rebased again since those pages were written.
- `mise.toml` — **`kb-currency-upgrade` and `kb-config`: zero hits, neither
  exists.**
- `.claude/skills/tool-currency/SKILL.md` — **still zero mentions of
  `kb-tool-sync`** (the 2026-08-23 gap, B.1 item 4).
- `[tasks.kb-tool-sync].description` — still **"one eligible reviewed
  mise-only tool pin"** (the 2026-08-23 gap, B.1 item 3, still unresolved).
- `.claude/skills/graphify/.graphify_version` and
  `.agents/skills/graphify/.graphify_version` — both **`0.9.53`**, agreeing
  "by luck" exactly as B.1 predicted; `currency/config.py:241` still
  declares a **singular** `skill_stamp` field.
- `gh issue view 638` — **CLOSED**, titled *"Session kb-20260830.001: the
  full record — currency sweep, the upgrade-protocol design round, and what
  a codex lane must re-verify."* It is a session-record issue, not itself a
  schema document — the *"`kb-upgrade` design"* phrase C.2 quotes appears to
  be a working name referenced from within it, not a separate artifact
  found in this pass.

---

## Consolidated: decisions already made

1. **Three-layer architecture: skill → mise task → python module, "zero-agent by default."** Source: B.1 ("U2", Ray's ruling, 2026-08-23) — *"This is Ray's ruling, and it is mostly unification rather than construction."* Restated identically by A.1 (2026-08-30) as "the shape you asked for."
2. **Entry-point shape/name: "a new `kb-currency-upgrade` wrapping `kb-tool-sync` — the primitive stays narrow, the wrapper is what skills name."** Source: B.1 decision #4, Ray, 2026-08-23, verbatim. **NOT YET BUILT** (verified live: zero hits anywhere in the repo).
3. **Zero-agent acceptance criterion: "a clean bump completes with no agent turn; an agent is summoned only when a step refuses."** Source: B.1, Ray's ruling, 2026-08-23.
4. **Same entry point across ownership classes; internals may differ per class.** Ray's own words, quoted in B.1: *"internals can be different, entry point should be the same."* **NOT YET DONE** (verified live: `kb-tool-sync`'s own description still says "mise-only").
5. **The second (`.agents/`-mirrored) skill tree must be tracked and refreshed too**, not just `.claude/skills/`. Ray named both paths explicitly in his 2026-08-23 directive (quoted in B.1). **NOT YET DONE** (verified live: `skill_stamp` is still a singular field; both copies agree today "by luck," per B.1's own predicted failure mode).
6. **Agents must never hand-edit config files — all mutation goes through a sanctioned command.** Ray's mandate, quoted in B.2, 2026-08-25, verbatim. Partially shipped (a comment-preserving writer and `set_pin_version` exist); the unifying `kb-config` CLI (B.2's P4) was **never built** (verified live: zero hits).
7. **graphify's "behind" currency signal must never be excluded/suppressed — it is the deliberate rebase trigger.** Source: `currency.toml:182-186` itself, quoted independently in both A.7 and C.1, reaching the same conclusion twice: *"a new upstream release is still a finding — it is the REBASE TRIGGER."* A.7 records Ray directly endorsing this after an earlier draft got it backwards: *"You were right. It is already handled — and my fix would have broken it."*
8. **DBOS is the intended final-state workflow engine, but must not be built prematurely / as throwaway.** Ray, quoted in C.2, 2026-09-01, verbatim: *"i dont want to build throw away work so we can get the dbos work done which is the final end state."* Consistent with A.7's *"plain functions in one module... adopting DBOS later is adding decorators."* **NOT YET IMPLEMENTED** (verified live: `dbos` absent from `pyproject.toml`).
9. **State-machine library choice: `python-statemachine>=3.2.1`.** Researched and recommended in A.8 (6-candidate comparison); listed as one of "seven already decided" in D.2. **NOT YET ADDED** to `pyproject.toml` (verified live).
10. **`kb-build`'s redness is explicitly OUT of the 7-gate ship bundle; a fast manifest-audit gate substitutes for it.** Ray's ruling, quoted in A.9, 2026-08-31: *"it stays out (≈55 min, network...); a transient DNS failure would become a blocked ship. A new seconds-long manifest-audit gate catches the same class."* **SHIPPED**: `kb-manifest-audit` exists live today.
11. **"Full protocol" (the completeness bar) means literally every pin site — 35, not the 18 currently mapped.** Ray's ruling, quoted verbatim in A.9, 2026-08-31: *"every pin site. 35, not the 18 mapped."*
12. **Ray's 4-step chain, step 1: bring every first-level dependency current FIRST, before building new machinery.** Ray, quoted in C.1, 2026-09-01. **SHIPPED**: PRs #646/#651, 10 tools bumped, `mise outdated`/`uv tree --outdated` both report clean.
13. **Step 2: give the graphify fork a permanent, non-scratchpad home.** Ray, quoted in C.3. **SHIPPED** per the plan's own "Decisions Made" table (moved to `~/dev/github/ray-manaloto/graphify`).
14. **Steps 3–4: rebase the fork onto the latest upstream tag; move every pin site in ONE change.** Ray, quoted in C.4, 2026-08-31. Evidence suggests this has since happened at least once more: today's installed rev (`157a957e...`) postdates the one the design pages discuss.
15. **Reconcile the 5 new currency-engine defects (#647–650, #483/#372) against the eventual `kb-upgrade`/DBOS design before fixing any in isolation.** Ray, C.2. **Still pending** (research-only status, per S1a).
16. Seven smaller settled facts, bundled from D.2 (2026-08-30h) since each is minor alone: `pyproject-direct` scope = every explicitly declared requirement (version read from `uv.lock`); all three gate layers run; no commit for a failed dependency; `source_synced` is per-manifest; missing manifests are valid nullable mappings; **`kb-upgrade` does NOT call `kb-ship`** (an explicit architectural boundary).

## Consolidated: still open

1. **The spec itself was never written.** The pwf plan's Phase 3 ("Write the spec") is 100% unchecked; Phase 4 (review→tickets) and Phase 5 (close round) likewise. Confirmed by three independent sources (task_plan.md's own checklists, progress.md's chronological boundary logs, and the plan's "Current Phase" pointer having moved on to unrelated Phase G/T/U work). **This is the central gap the next round exists to close** — the design substance (A.1–A.12, B.1–B.2, every grilling round) is substantial and mostly decided; the step that was supposed to consume it into a reviewed, ticketed spec never ran.
2. **A.9's "Decision 2" has conflicting signals and needs a direct check, not re-derivation.** A.9 itself leaves it open with no captured Ray quote; D.4 records what reads like a LATER, fuller Ray answer ("merge into graphify's own preferred layout"); but current `do-not.md` (checked live) reads like the narrower "declare a second sanctioned exception" outcome. Run `git log -p -- do-not.md` on that section before assuming which actually shipped.
3. **A.6's "one command" question (2026-09-03) appears to re-open B.1's decision #4 (2026-08-23), which already answered it** ("`kb-currency-upgrade` wraps `kb-tool-sync`"). Ray had not yet said "go" on A.6 as of that page. **The next round should reconcile these as ONE decision, not treat A.6 as a fresh question** — likely by simply building what decision #4 already specified, updated for what A.6 additionally learned (codex needs BOTH halves; neither existing command accepts it).
4. **The Q2/Q6 tension was never reconciled**: round 1's Q2 recommended "classify" (patch→auto, else needs-review); round 2's Q6 defaulted toward "auto, gates catch it" without revisiting Q2. task_plan.md's own Phase-2 checklist names the unresolved form directly: *"`revert-continue` vs `zero-skip-policy` — scope the rule in writing."*
5. **DBOS and `python-statemachine` remain proposals only** — neither is in `pyproject.toml` (verified live). The A.5 nine-table schema is explicitly self-labelled *"a proposal... nothing has been built... to be argued with,"* never ratified.
6. **`kb-currency-upgrade` (B.1 #4) and `kb-config` (B.2 P4) were both proposed unifying entry points; neither was built** (verified live).
7. **The tag-object-vs-commit resolution bug is a confirmed CLASS across at least four tools** (graphify, mise, typos, agnix) with no central fix — each instance was caught and patched separately. B.2's stated invariant — *"`latest_commit()` and `resolve_tag()` must return the SAME git identity, from ONE shared code path"* — is the design answer; it has not been implemented centrally.
8. **Currency-engine defects #647, #648, #649, #650 are filed but not fixed** (S1a status: research only).
9. **Phase 2f (resume the openai-cli backend work) is fully unstarted** — every checkbox empty.
10. **`docs/artifacts/clear-to-spec.html` was not in this task's reading list** and, per D.2, is the artifact actually carrying the pre-Ray-answer recommendations for the five design questions — likely worth the next round fetching directly rather than relying solely on A.9's synthesis.
11. **`currency.toml` still has no `[tool.agentsview]` row** — flagged across two handoffs as undecided.
12. **Whether floors (`>=`) should be made visible to the currency engine by reading `uv.lock`** instead of requiring exact pins (A.8's recommendation, independently reached by a lane too) — recommended, not confirmed implemented.

## Consolidated: what shipped

1. **PR #637** (`564a01c9`, merged 2026-08-31) — added A.1, A.2–A.4, A.5, A.8; landed the first currency sweep (5 patch pins + `min_version`).
2. **PR #639** (`cef09f08cfe2`, merged 2026-08-31) — added A.9; fixed a real graphify eighth-pin-site gate defect found by review.
3. **PR #646** (`b47b60cbc271`, 2026-09-01) — added A.10; part of the fork-relocation (S2) work.
4. **PR #651** (`a7a8dd69cdf4`, 2026-09-01) — **Phase S1 complete**: 10 first-level dependencies bumped to latest; added A.7.
5. **PR #707** (`b1d92a56`, 2026-09-03) — added A.6.
6. **`mise run kb-manifest-audit`** (`kb_setup` module) — tier-1/tier-2 pin-agreement gate, live today; built directly from this design line's repeated "the tail gets forgotten" finding.
7. **`mise run kb-tool-sync` / `python/src/kb_setup/tool_sync.py`** — the transactional lock+install+verify primitive (pre-existing, reused and hardened throughout this design line).
8. **`python/src/kb_setup/currency/{apply,sync,skill,report}.py`** — the currency engine itself (pre-existing; its internals — `_python_project_pin`, `_check_self_managed`, the six apply gates — are the mechanisms every design page reasons about and, per B.1/A.6, is meant to be wrapped rather than replaced).
9. **The graphify fork given a permanent home** at `~/dev/github/ray-manaloto/graphify` (S2), and rebased at least once past the version every design page discusses — current pin (`157a957e...`) is newer than the `0a2eb5fd...` rev centered on throughout A.10–A.12/C.4/D.
10. **`do-not.md`'s `graphify-out/` exception extended to two directories** (`memory/` + `graphify-semantic-slice/`) — resolves A.9's Decision 2 in SOME form; exact shipping commit not traced in this pass (see "still open" #2).

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under study; every artifact, plan, and handoff read is from here.
- [ray-manaloto/graphify](https://github.com/ray-manaloto/graphify) — the maintained fork central to A.10–A.12, B.1 (U2a context), C.3–C.4, D.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — upstream graphify; read by the design pages for release notes, tags, and upstream PR #2981's status (A.11, A.12).
- DBOS (PyPI package `dbos`, org `dbos-inc`) — researched for SQLite-support verification and the PR #441 "SQLite Support" citation chain (A.5, A.8, C.8). Exact repo path not independently re-verified in this pass.
- `python-statemachine` (PyPI package, maintainer `fgmacedo`) — researched for the state-machine library comparison (A.8). Exact repo path not independently re-verified in this pass.
- [jdx/mise](https://github.com/jdx/mise) — read for the annotated-tag-vs-commit resolution bug now confirmed as a cross-tool class (`findings.md`/C.8, D.7).

