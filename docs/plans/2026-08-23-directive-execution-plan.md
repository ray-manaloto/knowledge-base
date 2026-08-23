# One upgrade interface, one orchestrated unit at a time — executing Ray's 2026-08-23 directive

## The short version

Ray's directive is a **re-issue** of his 2026-08-21 one, already filed as epics #435/#436 and never worked. So this round executes a stalled backlog rather than
speccing new work — no duplicate issues, every unit anchored to a number.

Ten units, each a full orchestration cycle followed by `/clear-prep` +
session-review (his ruling):

| | unit | anchor |
|---|---|---|
| **U0** | unblock `kb-build` — prerequisite for the MERGE and for refreshing the graph at all. **Not** a prerequisite for the corpus run | #397 #409 #417 |
| **U2a** | **IMMEDIATE (corrections 8 + 10)** — the claude 2.1.241 resync, run **through U2's interface as its acceptance test**, then **START the graphify deep extraction** (~4.8 h, disjoint from everything else) | #464 #426 #458 |
| U1 | converge `/clear-prep` and session-review | #401 #449 |
| U2 | **one upgrade interface** (skill→task→module), zero-agent by default — mostly wiring `kb-tool-sync`, which already exists | #372 |
| U3 | run it on the eight real bumps | #447 #383 |
| U4 | reconfigure the cold-review lane | #445 |
| U4b | make "always on latest agy" a **gate**, not a bump | — |
| U5 | register the enabled antigravity plugin as a source | #446 |
| U6 | reverse-engineer graphify-labs, reproduce it locally | #448 #450 |
| U7 | the missing session-review lanes + triage consumption | #435 #423 #427 #461 |
| U8 | LSP, native static analysis, blast radius, visuals | #436 #370 |
| U9 | enforce graph use; ingest the PTC sources | — |
| U10 | code→docs tooling research; **every adopted tool becomes a currency row** | — |

**Six claims of mine were wrong.** Five I caught myself during planning by taking
one more step; the sixth was caught by the cold re-review — and it was **one of
the five "corrections"**, which had fixed a uv key name and then stated it
unconditionally for mise too. They are kept in place below rather than edited
out, because the pattern is the finding: `latest` vs `latest_version` (wrong
twice) · "JS is absent from the graph" · "one `kb-watch` away" · "#397 is the
blocker" · "the graph returns off-corpus junk". The re-review found **five more**
factual errors on top (a 32× wrong timeout, a wrong function name, a
self-contradicting section, an ordering that would un-authorize its own record,
and a control arm quoted with a command that was not the one run) — all now
corrected in place with the correction marked.

**The re-review's structural verdict, which matters more than any single fix:**
*"the dominant defect is NOT missing detail — the plan is unusually
well-evidenced — it is **UNDECIDED CHOICES STATED AS PAIRS**"* (`X or Y`,
`refuses or warns`, `decide, don't sweep`). **Eight of twelve units contain at
least one**, and only **U10** and **U8's `b0`** are READY as written. Those pairs
are the first thing to close, unit by unit, before dispatch.

## DECISIONS — settled by Ray across five grilling rounds, 2026-08-23

The re-review's verdict was that the plan's dominant defect was *undecided
choices stated as pairs*, in 8 of 12 units. These are those pairs, closed.

| # | decision | ruling |
|---|---|---|
| 1 | corpus spend cap | **RE-MEASURE before setting it** — and the cheapest measurement is the real run, stopped early (0 records if the cap holds) |
| 2 | currency identity fix | **opt-in flag on the `mise_key` path**, not a class move — one mechanism for all exposed rows |
| 3 | flag rollout | **all SEVEN** exposed rows, with the exemption reasoning recorded in `currency.toml` |
| 4 | U2 entry point | **a new `kb-currency-upgrade` wrapping `kb-tool-sync`** — the primitive stays narrow, the wrapper is what skills name |
| 5 | `/clear-prep` "only" | **"only" governs the STEPS** — every step becomes a lane; the remembered handoff survives as a failure path. **Plus: each step durable, so a died run resumes where it left off** |
| 6 | durability granularity | **per STEP within a lane**, where a step is defined by **the lane's brief declaring its own checkpoints** — units come from the caller's resolved list, not the agent's improvisation |
| 7 | the 20% trigger | **the intent wins over the flag's literal value** — stays model-invocable, the >20% measured-context trigger gets built, **#451 fixed first** |
| 8 | stale review lane | **REFUSE** — no receipt from an agy that disagrees with the pin. A warning is the 0-of-19 pattern |
| 9 | biome wiring | **(d) restructure the three workflow files** so the top-level `return` is legal. `--skip-parse-errors` is a measured false green and is disqualified |
| 10 | restructure verification | **run each workflow once before wiring the gate** — a syntax-legal file the harness executes wrongly is worse than today |
| 11 | transitive bumps | **leave boto3/botocore/pydantic-core** — they move with their owners; record the observation |
| 12 | effort provenance of $1.32 | **do not chase it** — the early-stop measurement answers it at the actual config as a side effect |
| 13 | U6 delivery surface | **Ray adds the claude.ai connector first**, then U6 builds the live page. U6 is blocked on an account-level action only he can take (#450) |
| 14 | U0 if the rebuild still fails | **register the failing sources `build = skip` with a written reason and move on** (#417's route) — a red build must not stall the round |
| 15 | U11 | **both** — `currency.toml` rows for the five now, **and** a gate so a sixth cannot appear silently |
| 16 | U5 "in sync" | **the manifest tracks the tag matching the INSTALLED plugin version**, with a currency row reporting drift — the same contract as `sources/claude-code.manifest` |
| 17 | **this session's scope** | **U2a only** — resync, start the run, `/clear-prep`. The run is the long pole and goes unattended for ~4.8 h |
| 18 | how U2a runs, given U2 is not built | **hand-run it, and the transcript becomes U2's spec** — every step recorded exactly as executed, so next round's automation is written from a real run rather than from reading code |

**The frontier is empty.** Every branch above was put to Ray and answered; nothing
below is silently assumed. Where a unit later than U2a still carries an open
choice (U9's enforcement acceptance criterion, U10c's rule-file name, U7's
per-lane briefs), it is out of this session's scope by decision 17 and belongs to
the round that reaches it — with the re-planning lane (decision 5/6) now existing
to catch exactly that.

## Context

At the `/clear` prompt after PR #466 landed, Ray answered with a directive
(verbatim in `.agent/kb/direction-addendum-2026-08-23b.md`) and told `/kb-resume`
to make it the next task, run through `/fable-orchestrator:orchestration`.

**Finding 1 — the directive is a re-issue.** Its §1 is a compressed restatement
of Ray's 2026-08-21 second addendum
(`docs/direction/2026-08-21-ray-directives.md:126-163`), filed the same day as
epics **#436** and **#435** (both `2026-08-21T17:12`) and not worked in the two
rounds since. §2 restates **#447** (filed 08-22 naming **1.1.18**; upstream is
**1.1.19**), **#445** and **#446**. Ray names the cause himself: *"a lot more
missing that the previous session-review workflow runs are missing/skipping
and/or have not been actioned upon from the aggregation/triage."* The aggregation
filed the epics; nothing consumed them. That is **#423** — session-review has no
lane pointed at itself — and it is why the directive arrived twice.

**Finding 2 — the uniform upgrade interface Ray is asking for is ~80% already
built, and nothing points at it.** He ruled:

> updating one currency/critical dependency should have the same interface
> following the same modular skill(s) → mise task(s) → python library
> module(s)/function(s) protocol … the internals can be different but the entry
> point should be the same … each step should try to have zero agent work and
> only really need agent work if a step has an issue … we've done enough of these
> dependency upgrades that we should be able to fully automate it by now

`mise run kb-tool-sync` (`mise.toml:1033` → `kb_setup.tool_sync.main`) already is
that entry point for mise-pinned tools: transactional (`_snapshot`/`_restore` —
"without leaving partial repository state"), `mise lock` + `mise install`, skill
refresh validation, and — decisively — **`_observed()` at `tool_sync.py:299` runs
`mise exec -- <binary> <version_args>` and `_validate_observed()` at `:327`
refuses when it disagrees with the pin.** That is exactly the binary-identity
check I was about to specify as new code.

**It is unwired.** Control-armed:
`grep -c "kb-tool-sync" .claude/skills/tool-currency/SKILL.md` → **0**, against
`grep -c "kb-currency"` → **3** in the same file. The probe discriminates: the
workflow's own skill never names the task that does the work. And
`currency.sync._check_resolution` re-derives the same fact from the install-dir
path segment instead of calling the probe next door — two modules holding one
fact, and the one wired into the SessionStart hook is the blind one.

So this round **executes a stalled backlog and unifies an interface that already
exists**. It files no duplicate issues; a stale ticket is amended, never diverged
from.

## Ray's process ruling — it governs everything below

> each work unit must be done via /fable-orchestrator:orchestration
> the /clear-prep skill must be run which includes the session-review workflow
> after each one is completed — until /clear-prep and session-review workflow are 1:1

Per unit: spec → `premise-verifier` where it triggers → codex lane at xhigh →
cross-family cold review → gates → receipt → ship/land → **`/clear-prep` with the
session-review workflow**. Once per unit, not once per round.

**Recommendation that follows from his own bound.** The discipline lasts *"until
they are 1:1"*, and they are not: `grep -c "session-review"
.claude/skills/clear-prep/SKILL.md` → **1**, a See-also, not a step (#401: *"Ray
has now said so twice"*; #449). Every unit before the convergence pays the
un-converged cost, so **U1 converges them first**. If Ray prefers his stated
order, U1 simply moves.

## What the probes found

Ray named the two structured surfaces; both work, and together they surface
**eight** drifts `currency.toml` reports as clean.

**`mise outdated -b -J`** — JSON per tool, keys `requested` · `current` · `bump`
· `latest` · `source.path`:

```
hk 1.56.0 → 1.56.1    rumdl 0.2.58 → 0.2.60    antigravity-cli 1.1.17 → 1.1.19
```

**`uv tree --outdated --all-groups --format json`** — five behind:

```
boto3 1.43.77→1.43.78   botocore 1.43.77→1.43.78   pydantic-core 2.46.4→2.48.0
tree-sitter 0.25.2→0.26.0        ty 0.0.73→0.0.74  ← currency tool AND an hk step
```

Five things the probing settled:

1. **These two commands ARE the bump check** — no homegrown fetch
   (`use-tool-builtins.md`). `CLAUDE.md:121-122` already conceded it and never
   wired it, which is why eight bumps sat unreported.
2. **Plain `mise outdated` is one-faced here** — every pin is exact, so nothing is
   ever out of range and it can only answer *up to date*. Without `-b` it is
   decoration.
3. **uv's `--format json` is EXPERIMENTAL** ("the schema may change without
   warning"; `--preview-features json-output` silences it). Carry the condition
   with the fact.
4. **THE KEY NAMES DIFFER PER TOOL — and my first correction of this was itself
   wrong, which is the more useful lesson.** Re-derived live by the cold lane:

   | tool | "what is installed" | "what is newest" |
   |---|---|---|
   | `mise outdated -b -J` | **`current`** | **`latest`** — full key set `bump · current · latest · name · requested · source`, **no `latest_version`** |
   | `uv tree --outdated --format json` | **`version`** | **`latest_version`** |

   My extractor looked for `latest` in **uv's** output, got `outdated=0`, and I
   then wrote *"the key is `latest_version`, not `latest`"* **unconditionally** —
   directly beneath a block correctly listing mise's keys. Applied to mise, my
   own "correction" reproduces the exact `outdated=0` false green the bullet
   exists to warn about. A true fact carried **without its condition** —
   `verify-before-advancing.md` § *Carry a fact's CONDITION, not just its
   source*, committed while writing the plan that cites that rule. **The consumer
   asserts against a known-behind fixture PER TOOL**; it neither trusts a zero
   nor shares a key name across the two.
5. **mise's own `current` has the blind spot too.** It reports
   `antigravity-cli current 1.1.17` while `agy --version` says **1.1.19**, because
   `current` is the install-dir label. `agy` self-updates *in place*.
   `CLAUDE.md:122-124` states step 1's whole purpose — *"whether the binary a
   shell actually reaches matches the pin"* — and `_check_resolution`
   (`sync.py:845`, via `resolve_from_path` `:210-248`) reads that same path
   segment. `-b -J` cannot close it either: it compares pin vs upstream, so it is
   silent whenever pin == upstream and the binary on disk is something else — the
   stale-PATH class this repo already hit with `pipx-graphifyy/0.9.23`. Only
   asking the binary closes it, which `currency.toml:1807-1811` demanded in
   capitals — and which **`tool_sync._observed` already does.**

**Class sweep** (`command -v` over every configured binary):

| resolution | binaries |
|---|---|
| **INSTALL-DIR** — version read from the path segment, blind to in-place self-update | `agnix` `agy` `codex` `doppler` `ffmpeg` `hk` `uv` `rumdl` `taplo` `gitleaks` `node` |
| OUTSIDE-MISE | `claude` (`expected`-owned, correctly caught) · `datamodel-codegen` `graphify` `ruff` `ty` (`.venv`) · `fnox` `mise` |
| **SHIM** | *none* — so `sync.py:846-850`'s unconditional-OK shim branch has never been armed here |

## The visual-artifact answer — Ray: *"this is not visual"*

He is right, and **#370's premise is what led me wrong**: it reasons *"plan mode
cannot publish an Artifact, so the mechanism is inline mermaid"* — true about plan
mode, but it turned a constraint into a standard, and the result was a fenced
block in a gitignored file.

**All three skills he named apply, and they do different jobs** (read this round):

| skill | what it gives | where |
|---|---|---|
| **`artifact-design`** | the calibration pass — **mandatory before writing any artifact**, Markdown included | every page |
| **`artifact-diagramming`** | *depict the mechanism, not its name*; *label every arrow*; plus inline-SVG mechanics (`viewBox`, `currentColor` for both themes, `<defs><marker>`, `<figure>`/`<figcaption>`, `role="img"`, no `<script>`/`<style>` inside) | the architecture/workflow/sequence diagrams |
| **`artifact-capabilities`** | **`artifact`** — the page saves new versions of itself, so it can *stay* current instead of being a snapshot; **`mcp`** — the page calls the viewer's **claude.ai connectors** with their credentials | a live graph-backed page, and U6 |

**The `mcp` capability was the lever for U6 — and it is CLOSED.** Settled by
`claude mcp list`, control-armed: that command renders **16 account-level
connectors with a literal `claude.ai` name prefix** (disabled ones included), so
it *can* produce the other answer. The graphify row carries **no prefix** —
`graphify: https://api.graphify.com/mcp (HTTP) - ✔ Connected`. It is a
**project-local `.mcp.json` registration** (`.mcp.json:3-6`, remote HTTP
transport but repo-local registration), **not a claude.ai connector** — and the
`mcp` artifact capability accepts only connectors.

**So a published page cannot query the hosted graph today.** Making it possible
is an account-level action outside this repo — adding it at claude.ai → Settings
→ Connectors, after which it would appear as `claude.ai graphify`. That is Ray's
call, not a code change, and #450 exists to get it ruled on.

**Three tiers of mechanism:**

| tier | mechanism | status |
|---|---|---|
| Now, rendered + shareable | the **Artifact** tool: mermaid (`<pre class="mermaid">`) + hand-authored inline SVG, theme-aware, with a URL; `design` adds an editable canvas | blocked by plan mode only — first action on approval |
| Durable, committed, synced | `mmdc` + `dot` → SVG/PNG beside the source | **installed** (mermaid-cli 11.16.0, graphviz 16.0.0) but **not pinned in this repo's `mise.toml`** and used in **zero** files here (control: `grep -n "^hk " mise.toml` → `:46`) |
| Derived from code (#436) | **`tree-sitter` 0.25.2 + ~30 grammars incl. `tree-sitter-javascript` 0.25.0 are ALREADY in the locked tree** via graphify — Ray's "use the AST tree sitter" needs wiring, not procurement. Then research with cited pros/cons: **D2** · **Structurizr/C4** · **PlantUML** · `madge`/`dependency-cruiser` (the right shape for `.claude/workflows/*.js`) · `pyreverse`/`pydeps` · graphify's own graphml/svg from `kb-artifacts` | tree-sitter present; rest unpinned |

**Sync enforcement needs no invention:** `kb_setup.currency.views` already answers
*"was this view generated from the current source?"* via a fingerprint map, and
already documents why an mtime ordering rule fails.

## Directive → existing issue map

| Directive item | Issue |
|---|---|
| visuals + AST tree-sitter + LSP, durable and synced | **#436** (filed 08-21, unstarted) |
| /clear-prep → session-review only; args/hints; telemetry→skill→task→module; universal loggers; manual-cmds-should-call-skills; profilers; self-improve | **#435** (filed 08-21, unstarted) |
| self-heal/optimise the workflow itself | **#423** (Ray already ruled: a focused follow-up *after* a review, not a lane inside it) |
| profilers / metrics / linter-skip detector | **#427**, **#443** |
| universal loggers | **#461** (extends #350) |
| manual command → skill/task/module | **#448** (research-only per Ray) |
| **reverse-engineer app.graphify.com + the graphify-labs bot, reproduce it LOCALLY** | **#448** (second half, already verbatim in the ticket) + **#450** — the bot's *"28 more findings outside this diff"* are unreachable via `gh`: check-run annotations = 0 on every PR-463 commit against a Repowise control of 7, `details_url` is graphify.com's homepage |
| /clear-prep must run session-review | **#401**, **#449** |
| durable home for the visual requirement | **#370** — whose "inline mermaid" premise this plan just corrected |
| **the apply path cannot be reached, and reports success anyway** | **#372** (P0, open, unfixed) |
| resync antigravity-cli | **#447** (stale at 1.1.18) |
| agy model/effort/settings | **#445** |
| yuting0624 plugin as currency/critical dep | **#446** (premise half-stale — `sources/fable-orchestrator.manifest` exists) |

## The work units

Each is a full orchestration cycle followed by `/clear-prep` + session-review.

### U2a — THE IMMEDIATE TASK, and it is U2's acceptance test (Ray, corrections 8 + 10)

> **U-1 should be part of U2** — automation of this upgrade/sync of
> critical/currency dependencies. we've done the upgrade enough times that we
> should be able to automate this.

**Restructured on Ray's ruling, and he is right.** My drafts had this as a
bespoke hand-run chain (U-1) *and* U2 as "build the uniform interface" — which is
the exact split his whole directive is against. **The claude 2.1.241 resync IS a
critical-dependency upgrade**, so it does not get its own procedure: it goes
through U2's entry point, and **running it is how U2 is tested**. If the
interface cannot carry this upgrade, the interface is not done.

That also fixes an ordering smell in my draft: I had U-1 running *before* U2
built the thing U-1 is an instance of.

**The `expected`-class path is the one U2 must widen anyway** — `claude-code` is
`expected`-owned, `apply` refuses a row with no `mise_key`
(`apply.py:176-193`), and `eligible_tools()` is "mise-only". So this upgrade
exercises precisely the gap U2 exists to close (its gap 3), rather than a happy
path.

**Everything below is the SPEC for what U2 must automate**, not a list of
commands to type by hand.

> i would still like to get the full deep extraction/reflection and all other
> agent work done on the graphify clone repo done as soon as possible — if we can
> slot that in as the immediate task

**It cannot start as-is, and the reason is a one-line version skew with an
expensive failure mode.** Re-derived this session rather than inherited:

```
uv run kb-setup graphify-semantic-corpus verify → {"execution_authorized":true,"state":"complete"} rc 0
execution-config.json  claude_version 2.1.240 · effort high
claude --version                      2.1.241          ← the plan was never made against this
graphify_semantic_slice.py:561        _CURRENT_CLAUDE_VERSION  = "2.1.240"
graphify_semantic_slice.py:475        _ACCEPTED_CLAUDE_VERSION = "2.1.238"
```

`verify` reports **authorized** against a Claude the plan does not describe.
**Settled this session by reading the code rather than trusting the handoff** —
the asymmetry is exact:

| identity half | what the plan-vs-live check compares | when | refuses before spend? |
|---|---|---|---|
| **graphify** | `_assert_graphify_runtime_unchanged_since_plan` (`…_run.py:1029-1060`): `preflight_receipt` vs **`config`** (the plan) | preflight | **YES** — `raise ValueError` |
| **Claude** | `_adapter_overlay` (`…_run.py:446-447`): the live binary's sha256 vs **`runtime.executable_sha256`**, i.e. the *preflight receipt* — **not the plan** | preflight | raises, but **both sides are current**, so the plan's 2.1.240 is never consulted |
| **Claude, plan-vs-live** | `_provider_runtime_reasons` (`graphify_semantic_corpus.py:2344,2347`): `provider.runtime` vs **`config`** (the plan) — the checks exist and are correct | **only once a `SemanticReceipt` exists — i.e. after a provider call was paid for** | **NO** |

Empirical control arm: `verify` → `execution_authorized: true` at live **2.1.241**
against plan **2.1.240**. Any pre-spend plan-vs-live Claude check would have
refused there; none did.

So the run started today would spend the cap and stage 26/26 failed
(`_dispose`, `…_run.py:1213-1223`, appends a failed outcome **without raising**).
The handoff's P1 is CONFIRMED, and step 2 below is the thing that unblocks Ray's
immediate task.

**The good news, and it is what makes this schedulable today: #397 does NOT block
the RUN.** The run's only input is the pinned `sources/graphify` clone
(lane-verified clean at the plan's commit `b2cd3626`). `kb-build` red blocks the
later **merge** of the run's output, not the run. So U2a runs *ahead of* U0.

**The chain, and every step is already decided:**

1. Advance the slice constants — `_CURRENT_CLAUDE_VERSION` → `2.1.241`, re-hash
   `_CURRENT_CLAUDE_EXECUTABLE_SHA256` from the installed binary, re-check whether
   the `--help` digest moved (it did not 2.1.232 → 2.1.240). Fix **#464** while
   there: the comment above `:475` claims `_ACCEPTED` *"now equals
   `_CURRENT_CLAUDE_VERSION`"* while they read **2.1.238 vs 2.1.240** — a comment
   contradicting its own code, three lines away.
2. **Close the plan→live window** — Ray already ruled *"Yes — close it in the
   resync"*. Bumping the constant alone does not close it: `current_claude()`
   (`graphify_semantic_slice.py:655-681`) returns LITERALS, which is why
   `verify` compares a plan literal against a module literal and never asks the
   binary.

   **CORRECTED SITE (cold lane, I5).** My draft said "make the **preflight**
   compare…". Wrong: `preflight()` (`graphify_semantic_slice.py:1014-1085`) takes
   `repo_root` and **never sees the plan candidate**, so it cannot read
   `config.claude_version`; its outputs are already all-live. **The correct site
   is `execute()` (`…_run.py:1094`), beside
   `_assert_graphify_runtime_unchanged_since_plan`** — which is the exact
   template, since that function already does plan-vs-live for the graphify half
   and raises. Add its Claude twin there.
3. `sources/claude-code.manifest` → the v2.1.241 tag + commit;
   `currency.toml [tool.claude-code]` `expected` → 2.1.241; a `docs/currency/`
   row (the last one there is **2.1.220** — 2.1.240's was never written either).
4. **DECIDE THE CAP — and it must come BEFORE the record, not after** (cold lane,
   I6; my draft had it as step 6). `max_total_cost_usd` is a field of
   `execution-config.json` (verified: **63.0**), written from
   `_MAX_TOTAL_COST_USD` at **`graphify_semantic_corpus.py:107`** — the line to
   edit, which my draft never named. Changing it moves `execution_config_sha256`,
   **one of `record`'s two `IDENTITY_DIGESTS`** (`…_record.py:38`), so a cap
   change *after* step 5 un-authorizes the record just made.

   **PREMISE CORRECTION — my "the cap is wrong" framing was overstated.** The cap
   does **not** encode $1.12/chunk. `_MAX_TOTAL_COST_USD = 63.0` is a module
   constant (`graphify_semantic_corpus.py:107`); $1.12 was only the *derivation
   input* (`:98-107`). **$63 ÷ 26 = $2.42/chunk of headroom against a measured
   $1.32 — the cap is already ~1.8× the measured rate.** So it is not obviously
   too low, and my ~$74.41 alternative was solving a problem that may not exist.

   **Ray's ruling: RE-MEASURE before deciding — and the cheapest measurement is
   the real run, stopped early.** Established by reading the driver:

   | fact | evidence |
   |---|---|
   | **no chunk limit exists** | `corpus_main` accepts exactly `plan\|run\|verify [PATH]`, `_MAX_ARGS = 2` (`corpus.py:143, 3633-3643`). No `--chunks`/`--limit`/`--dry-run`/`--resume-from`. The only bound is the cap, which raises `_SpendCapError` inside `on_chunk_done` (`_run.py:1171-1175`) |
   | **staged chunks resume free; provider calls are re-bought** | `_dispose` → `_resolve_existing_stage` returns REPAID for an already-staged ordinal (`_run.py:1211-1217, 876-913`); an AST walk of the pinned graphify found **no cache read** on this path (`:889-898`). `mise.toml:706-711` is TRUE |
   | **but the CAP IS DURABLE across restarts** | `spend-ledger.json` is written through on every charge (`_run.py:141-143, 219-240`) and `seeded_spend` refuses a plan already over cap **before the first provider call** (`:247-273`). A restart re-buys work; it does **not** reset the budget |
   | **per-chunk cost is a ledger delta** | `spend-ledger.json` `{total_usd, charges}` — one charge per chunk, so per-chunk = the delta between consecutive charges. `ChunkStageReceipt` carries **no cost field** (`authority.py:344`) |
   | **there is ZERO partial evidence on disk** | `graphify-out/graphify-semantic-corpus-chunks/` does not exist; no `spend-ledger.json`, no `provider-spend-*.json` anywhere |
   | **the slice is NOT a proxy** | haiku-4.5, `--max-budget-usd 0.25`, 3 turns, $0.0557 vs a chunk's opus-5 / `effort: high` / 64k output ceiling. **24× apart** |
   | **⚠ and $1.32 may be a FLOOR, not an estimate** | it was recorded 2026-08-18 against the **58-chunk pre-dedupe** plan, whose superseded config on disk records **`effort: None`** while the live plan records **`effort: high`**. Whether that measurement was taken at effort high is **UNSETTLED** |

   **The sequence — 0 records if the cap holds, 1 if it moves, never 2:**
   `verify` → start the real run → after 1–3 charges read
   `graphify-out/graphify-semantic-corpus-chunks/<ns>/spend-ledger.json` →
   if rate × 26 sits comfortably under 63, **let it run** and the measurement cost
   nothing (those were chunks you were buying anyway); if it does not, Ctrl-C,
   edit `corpus.py:107`, re-plan, `record --accept`, re-verify, re-run. **A
   measurement run mutates no plan member, so it needs zero records.**

   **The one trap:** Ctrl-C followed by a re-plan gives a new
   `cache_namespace_sha256`, hence a **fresh** ledger and stage dirs — the
   measured chunks are re-bought and the ledger restarts at 0. Budget that
   measurement as sunk in the cap-moves branch.
5. **The ninth `record --accept` BY TOOL** — the slice module is digested into
   every plan as `semantic_slice_sha256`, so step 1 invalidates the recorded plan.
   Dry run first (expect `moved = plan_manifest_sha256, execution_config_sha256`,
   `decision_moved = ()`, `recordable = true`), then `--accept` → `verify` →
   authorized. **No separate `plan` run is needed**: `record` re-plans internally
   (`…_record.py:439-440` writes `.agent/kb/replan-<suffix>` and calls
   `plan_source`).
6. **Start the run, supervised** — `mise run kb-graphify-semantic-corpus -- run`,
   26 chunks / 170 units, effort high, 900 s/call. **The task's hang guard is
   `timeout = "16h"` at `mise.toml:719`** — my draft said `30m` at `:704-716`,
   which is **the PRECEDING task's** timeout (`:702`) and **off by 32×**. The
   block's own comment does the sizing: *"26 chunks at the measured ~11 min/chunk
   projects to ~4.8h; 16h is roughly 3.3x that."* An implementer believing 30m
   would wrap or abort a healthy run.
7. Then the merge/reflect/artifacts half — which IS gated on U0.

**The one open question is now CLOSED — measured, not assumed.** The re-review
flagged that `_CURRENT_CLAUDE_HELP_SHA256` is an **alias** of
`_ACCEPTED_CLAUDE_HELP_SHA256` (`graphify_semantic_slice.py:565`), so if
2.1.241's `--help` digest had moved, step 1 would not be a one-line edit. Hashed
live:

```
_ACCEPTED_CLAUDE_HELP_SHA256 (:479)   71ad650f59e08ae40ede14c534db4f49d8590ee5a4f92f6da2882d3a5560fea6
claude --help | shasum -a 256 (2.1.241) 71ad650f59e08ae40ede14c534db4f49d8590ee5a4f92f6da2882d3a5560fea6   ← IDENTICAL
readlink -f $(command -v claude) → …/versions/2.1.241
shasum -a 256 of that              1495eb7c42d3b4451f5f1cd38b6d498d22a4a38c802bc2be5c1cf1795e64820d
```

**The `--help` digest did NOT move**, holding unchanged 2.1.232 → 2.1.241. So the
alias at `:565` stays, every flag this path depends on is spelled identically,
and **only implementation moved** — which is precisely the argument the constant's
own comment makes. Step 1 is therefore exactly two constant edits:

- `_CURRENT_CLAUDE_VERSION` (`:561`) → `"2.1.241"`
- `_CURRENT_CLAUDE_EXECUTABLE_SHA256` (`:562`) → `"1495eb7c42d3b4451f5f1cd38b6d498d22a4a38c802bc2be5c1cf1795e64820d"`

That executable digest was measured **independently twice** this session — by me
and by the cold re-review — and both agree.

### U0 — unblock `kb-build` (#397, #417) — a PREREQUISITE for the MERGE, not the run

Proven above: `kb-build` red → no `.compose-manifest.json` → `kb-watch` refuses →
the graph cannot be refreshed at all. That takes out blast radius on the
session-review workflow (Ray's correction 4), the graph-first rule every unit
opens with, and `.currency-stamp.json` (so `kb-currency-check` reports the
graphify build-stamp DEFECT every session).

**The current failure is NOT the one #397 describes — check before quoting the
ticket.** #397 (2026-08-19) is a **detect**-stage failure:
`anthropic-sdk-python` unclassified-files `[Brewfile, examples/.keep,
src/anthropic/lib/.keep]`. `84505916acf4` ("fix kb build 397", PR #410) landed
after that. What the build stamp actually records for the 2026-08-21T17:56 run is
an **extract**-stage failure:

> `IncompleteGraphifyOperationError: Graphify extract failed closed (incomplete):
> stderr; unaccounted_stderr='warning: 3 source file(s) produced zero nodes and
> are absent from the graph: pyproject.toml, pyproject.toml, pyproject.toml.
> A re-run will retry them (empties are no longer cached); if it persists, please
> report the file(s) (#1666).'`

Different stage, different cause, and graphify's own message says **a re-run will
retry**. So U0 may be as cheap as re-running `kb-build` — do that first and read
the real rc before assuming a fix is needed. If it persists, it is the
reviewed-warning inventory problem (#409: *"kb-build's reviewed-warning
inventories do not scale — GitNexus alone needs 94 entries"*), not #397. #417
tracks the `build = skip` register, whose own list omits `codegraph`, the only
`scope = corpus` one.

Note also that `kb-currency-check`'s wording — *"re-running `mise run kb-build`
will fail again"* — is an **inference, not a record** (#440 is open about exactly
this phrasing), and it contradicts graphify's own "a re-run will retry them".
Do not let the check's confidence substitute for a run.

### U1 — converge `/clear-prep` and session-review (#401, #449)

The bound on Ray's own rule. `/clear-prep` is 500 lines / 8 steps and names
session-review once, in a See-also. Wire the workflow in as the handoff engine
with the argument/hint plumbing his directive asks for.

**L3 — the concrete half I dropped, restored.** Ray, 08-21 directive `:140-141`:
*"it should also be able to be **triggered by an agent so that it runs when
context hits over 20%** — so toggle this flag: **`disable-model-invocation: true`**
in `.claude/skills/clear-prep/SKILL.md`."* A named flag in a named file, and the
most concrete instruction in the whole directive. Current state:
`disable-model-invocation: **false**` (model invocation is *enabled*).

**Note the flag and the intent point opposite ways** — `true` *disables* model
invocation, which would prevent the 20% auto-trigger he asks for in the same
sentence — and a prior session already flipped it once. So this needs his word on
the intent, not a literal edit: the deliverable is *"clear-prep fires itself at
>20% measured context"*, and `mise run kb-context` is the measuring instrument
(#451: it *"could ONLY refuse"* — still open).

**A RE-PLANNING LANE — Ray, correction 10, and it is the loop this whole round
exists because we lacked.**

> each /clear-prep run should have a lane that updates the next steps if they are
> affected by the previous task and/or deep extraction/reflection uncover new
> research that needs to be done and/or a different approach or the order of the
> tasks needs to be re-arranged

Every existing lane looks **backwards** at what the round did. None looks
**forwards** at what remains. That is precisely why #435 and #436 were filed by
the aggregation step and then sat for two rounds: nothing ever re-read the
backlog against what had just changed.

This lane runs at each `/clear-prep` and answers three questions about the
**remaining** units:

1. **Invalidated?** — did the unit that just landed make a later one unnecessary,
   wrong, or already-done? (Live example from this session: my U-1 was
   restructured into U2a by Ray for exactly this reason, and U0's premise moved
   from #397's detect failure to an extract failure PR #410 had already changed.)
2. **New work uncovered?** — did the deep extraction / reflection / artifacts
   surface research or a defect that belongs in the backlog? (Live example: the
   `.agents/` second skill tree, found only because Ray named a path.)
3. **Re-order?** — is the sequence still right given what is now known?
   (Live example: #397 moved from a background carry to a prerequisite, and
   `kb-artifacts` turned out to need no prerequisite at all.)

It pairs with U7's **triage-consumption** lane: that one asks *"what did we file
and never pick up"*, this one asks *"is the plan we are holding still correct"*.
Together they close the filed→consumed→re-planned loop. Its output is an edit to
the tracked plan document (see the durability section), not a report nobody reads.

**One conflict to settle explicitly rather than silently split the difference.**
Ray's word is *"convert /clear-prep to **only** use the session-review workflow"*.
`kb-session-review/SKILL.md` carries a standing rule that contradicts it:

> **Never make this the only path.** `/clear-prep` fires when the session budget
> is most depleted, and a session limit is **not model-scoped** — `judge()`'s
> fable→opus fallback cannot save it. A workflow handoff that dies leaves
> NOTHING, which is worse than an imperfect remembered one.

Both are Ray's. The resolution I propose — and it needs his word, not my
judgement: **"only" governs the STEPS** (every clear-prep step becomes a lane, as
his 08-21 text says: *"so every step it does should become a step/lane in the
session-review workflow"*), while the **fallback stays** as a failure path, not as
a second implementation. That satisfies "only one place does the work" without
reintroducing the leaves-nothing failure. If he means it literally — no fallback
at all — say so and the rule gets retired deliberately rather than eroded.

### U2 — ONE upgrade interface: `skill → task → module`, zero-agent by default

**This is Ray's ruling, and it is mostly unification rather than construction.**

**Entry point:** one task per Ray's protocol — `kb-tool-sync` widened, or a
`kb-currency-upgrade` that wraps it — reached from the `tool-currency` **skill**,
backed by `kb_setup` **modules**. Same entry point for every currency/critical
dependency; the per-tool internals differ behind it.

**What already exists and must be reused, not rebuilt:**

| step | already in | note |
|---|---|---|
| discover what is behind | *nothing* — wire `mise outdated -b -J` + `uv tree --outdated … --format json` | with the three parsing guards above |
| lock + install, transactionally | `tool_sync._sync`, `_snapshot`/`_restore` | already "no partial repository state" |
| **ask the binary, compare to the pin** | `tool_sync._observed` `:299`, `_validate_observed` `:327` | **the fix for the blind step-1 check is a call, not a new probe** |
| lockfile convergence | `tool_sync._lock_converged` `:277` (`mise lock --dry-run --json`) | |
| move the pin | `currency.apply.set_pin_version` | a **deliberate** text edit, not `mise use` — documented at `apply.py:77-78` because `mise use` installs as it edits. Keep the reason; do not "fix" it into a violation of its own rationale |
| advance the source manifest | `currency.apply` via `manifest.resolve_tag` | raises if the tag does not resolve, so a manifest is never pinned to a non-existent tag |
| refresh a generated skill | `currency.skill` + `ADDENDA` re-apply | graphify only — **and it only knows about ONE of the two skill trees; see below** |
| write the run report | `currency.report` → `docs/currency/` | |
| corpus/doc resync | **the incomplete half** — `kb-update -- <name>` + re-ingest; `apply` deliberately refuses and points at it (`apply.py:165`). **graphify is the hardest and is why this has never been finished** | |

**The gaps to close, in this order:**

1. **#372, P0 and unfixed** — `mise run kb-currency -- --tool X apply` cannot
   reach `apply` (`mise.toml` hardcodes `run = "… currency run"`, so `apply`
   lands as a second positional and `cli.py:717` takes `positional[0]`), and it
   **prints `auto-applying (6/6 gates)` having changed nothing**. Its three
   remedies: a task that reaches apply · `currency run` must **refuse** an
   unrecognised positional rather than discard it · fix the skill's step 4.
2. **Make step 1 ask the binary — and the cold lane found a cheaper fix than
   the one I specced.** I proposed a new opt-in `ToolSpec` field. The lane's read
   says it may be **a one-field ownership-class change**:

   - The four classes dispatch at `sync.py:1630-1681`. **Only `mise_key` never
     executes the binary**; `expected` (`_check_self_managed`, `sync.py:959-1058`)
     and `python_package` both do.
   - `_check_self_managed` already does precisely what is wanted:
     `shutil.which(spec.binary)` → absent = DRIFT → `observed_version(...)` → an
     unreadable version is **BLIND, not DRIFT** (*"rendering it as disagreement
     would make a broken `version_pattern` look like a tool upgrade"*) →
     `_check_manifest` against the **running** version → `running != expected` →
     DRIFT carrying the *"it self-updated"* remedy. **That is the path that
     catches `claude-code`.**
   - **`version_pattern` on the antigravity row is DEAD CONFIG today**
     (`currency.toml:1806`) — read only by `_check_python_resolution` and
     `_check_self_managed`, neither reachable from a `mise_key` row. Declared,
     parsed, never read. The row's capitalised demand is not merely unmet; its
     ownership class makes it *unreachable*.

   **Two corrections to my earlier draft:**
   - **`deep=True` does NOT close this, so `mise run kb-currency` is blind too.**
     `deep` threads to exactly one place — `_check_extra_probes` (`sync.py:1675`)
     — permitting one `mise where` subprocess, never a `--version`. The gap is
     **ownership class, not hook-vs-full-run**; my draft implied the full loop
     might differ.
   - **The cost argument is weak.** `observed_version`'s own docstring measures
     `mise --version` at **11.4 ms** and `graphify --version` at **50.6 ms** — not
     the ~0.4 s `resolve_from_path` cites. Seven rows at ~15 ms is not a
     per-session-hook problem.

   **The EXPOSED SET is 7 currency rows, not 11 binaries** — my table counted
   every install-dir binary; only the *tracked* ones are actionable: **`agnix`,
   `antigravity-cli`, `codex`, `doppler`, `ffmpeg`, `hk`, `uv`**. Only
   antigravity-cli is *measured* to have self-updated; `doppler` and `uv` ship
   self-update subcommands (**unprobed — do not inherit as verified**). `mise` and
   `fnox` are shell functions here so `command -v` could not measure them
   (`shutil.which` would); treat those two as **unmeasured**, not clean.

   Whichever shape wins, the sibling **dotfiles** repo consumes
   `kb_setup.currency` as a pinned uv git dependency, so it must stay
   backward-compatible.
3. **Widen the entry point across ownership classes** — `eligible_tools()` is
   deliberately "mise-only", so `ty` (python_package) and `claude-code`
   (`expected`) fall outside; `apply` refuses a row with no `mise_key`
   (`apply.py:176-193`). Those are exactly Ray's *"internals can be different,
   entry point should be the same"*.
4. **Point the skill at the task.** `grep -c "kb-tool-sync"` in
   `tool-currency/SKILL.md` → **0**. A built, tested, transactional task that the
   owning skill never names is indistinguishable from one that does not exist.
5. **THE SECOND SKILL TREE — Ray named it, and the engine has never heard of it.**

   > include the skill updates and verifying these versions:
   > `.claude/skills/graphify/.graphify_version` · `.agents/skills/graphify/.graphify_version`

   Measured, control-armed:

   | fact | value |
   |---|---|
   | both stamps exist and are **tracked in git** | both read **`0.9.48`**, matching `pyproject.toml:32` |
   | `.agents/skills/` is a **tracked 21-file mirror** of `.claude/skills/` | **13 skills in each, same names**; the agy/Antigravity workspace-rules location |
   | do the two copies agree? | **12 of 13 SKILL.md are byte-identical**; `graphify` differs **42,381 vs 1,487 bytes** — the platform-specific generated body, by design |
   | what `currency.toml` tracks | **`.claude` only** — `skill_dir = ".claude/skills/graphify"` (`:46`), `skill_stamp = ".claude/skills/graphify/.graphify_version"` (`:66`) |
   | what `currency/skill.py` knows about `.agents` | **0 mentions** (control: `.claude` → **14** in the same file) |

   **So on the next graphify bump, `currency.apply` refreshes `.claude/skills/graphify`
   and silently leaves `.agents/skills/graphify` at the old version.** It reads
   0.9.48 today by luck, not by mechanism. This is the same shape as U11 and as
   the antigravity row's own confession (`currency.toml:1782-1784`): *"the engine
   reported green for it forever by never asking."*

   Also worth recording because no rule file says it: **`.agents/` is a real,
   tracked directory distinct from `.agent/`**, and
   `.claude/rules/agent-artifact-conventions.md` — which exists precisely to say
   where things live — never mentions it (control: `.agent/` appears in **8**
   rule files). Every skill edit must land in two places and nothing enforces it.

   **Deliverable:** `skill_dir`/`skill_stamp` become plural, the refresh
   regenerates both trees, the upgrade verifies both stamps, and a gate fails
   when they disagree.

**Zero-agent is the acceptance criterion**, per Ray: a clean bump completes with
no agent turn; an agent is summoned only when a step *refuses*. The six existing
apply gates already encode "unambiguous → self-apply, anything unreadable →
ambiguity, not consent"; the work is to make the refusals rare and specific
rather than to loosen them.

### U3 — run the interface on the eight real bumps

Not hand-typed commands — the **first exercise of U2's entry point**, which is
also its acceptance test:

- **mise**: `antigravity-cli` 1.1.19 (amend #447 from 1.1.18), `hk` 1.56.1,
  `rumdl` 0.2.60 (#383's standing request).
- **uv**: `ty` 0.0.73 → **0.0.74** matters most — a tracked currency tool *and*
  an hk step, so it changes a gate and earns its own review. `tree-sitter`
  0.25.2 → 0.26.0 is graphify-owned and moves with graphify. `boto3`/`botocore`
  patch and `pydantic-core` 2.48.0 are transitive — decide, don't sweep.
- **claude-code** 2.1.240 → 2.1.241 is the `expected`-class case that proves gap
  (3): manifest + `currency.toml expected` + a `docs/currency/` row (the last
  row there is 2.1.220), then the slice constants and the ninth
  `record --accept`.

There is **no** `sources/antigravity-cli.manifest` (verified absent) and
`currency.toml:1813-1816` says it is deliberately absent until the source is
pinned — so #447's "advance the manifest" step does not apply; say so rather than
creating one.

### U4 — reconfigure the cold-review lane (#445)

Ray's ruling: **change it, then review the rest of the round with the new lane**;
state the circularity in the receipt.

- **`/antigravity:migrate` — corrected by the cold lane: read-only BY DEFAULT.**
  My draft said "must NOT run here", which is too strong.
  `scripts/agy-migrate.py:4` verbatim: *"Read-only by default: prints a per-unit
  plan and exits. `--apply` performs it."* **So the dry-run is safe and is the
  right way to see the blast radius.** It is `--apply` that breaches
  `do-not.md` #11: symlinks into `~/.claude/skills`, repo registration in
  `~/.gemini/config/projects/` (`migrate.md:29`), an `AGENTS.md` symlink behind
  `--include-repos` (`:464-467`), a flat plugin `copytree` into a staging dir
  (`:258`). Permission widening needs `--apply-permissions` explicitly (*"this
  widens the grant"*, `:872-883`); it honours `CLAUDE_CONFIG_DIR` (`:93-95`) and
  is reversible (`--uninstall --apply`). **Verdict: run the dry-run, never
  `--apply`.**
- **`/antigravity:setup` is safe** (`agy-doctor`) — run it; it grounds the tier
  decision. **But note a live hazard in its own script:** `doctor.sh:38-39`
  prefers `timeout`/`gtimeout` and falls back at `:56` to running `agy`
  **unbounded**. Both are absent on macOS — the reason this repo has an
  `absent_binary` guard at all — so here `agy_guard` runs with no time bound.
- **`--mode accept-edits` is NOT a write grant** — measured on agy 1.1.13,
  `agy-delegate.sh:143`: it is denied exactly like a plain write. A file write
  needs a `permissions.allow` rule in `~/.gemini/antigravity-cli/settings.json`
  or `--yolo`, and headless cannot prompt — so a missing rule is a **silent
  no-work**. Worth knowing before trusting any agy lane that reports edits.
- **Three unpinned surfaces on this lane, not one:** the `agy` CLI source (no
  `sources/antigravity-cli.manifest`), the `yuting0624` plugin repo (U5), and
  the plugin's own version on disk — **two cached copies, 0.23.0 and 0.24.0, no
  currency row**. The 0.24.0 copy even ships a `migrate-to-antigravity` skill
  still stamped `version: 0.23.0`.
- **#445's answer is a defect.** `scripts/agy-delegate.sh:155-161`:
  `flash` → **Gemini 3.7 Flash (High)**, `pro` → **Gemini 3.1 Pro (High)** — the
  `pro` tier we pass is an *older generation* than flash. And
  `.claude/settings.json` sets **none** of the plugin's eight `userConfig`
  options, so every delegation runs on the default **5-minute timeout** against a
  review measured at ~9 minutes. Candidate cause for "slow and something seems
  wrong": the lane is being cut off. Set the options at project scope, grounded
  on `agy models`, and record the reasoning.
- **Adopt `--adversarial`** (`commands/review.md:17-18`: it also challenges
  "design decisions and tradeoffs, not just line bugs").
- **The bypass is the finding.** `kb-review/SKILL.md:125` *already* mandates
  `antigravity:review` for codex-authored diffs — yet last round hand-ran
  `agy-delegate --tier pro --sandbox --mode plan`. A mandated skill bypassed by a
  hand-typed command: precisely Ray's *"manual commands that should be calling
  skills"*. Pin the invocation in `SKILL.md` and seed the instance into U7's
  `skill-not-triggered` lane.

### U4b — "the reviews must ALWAYS be on the latest agy" needs a gate, not a bump

Ray's words are *"the gemini/antigravity reviews **always** need to be on the
latest version of agy/antigravity-cli"*. A one-time bump to 1.1.19 does not
deliver "always"; the next self-update silently re-opens it — which is the whole
point of the U2 identity fix. So the deliverable is an **enforcement**: the cold
review lane refuses (or loudly warns) when the running `agy` disagrees with the
pin or the pin is behind upstream. `kb-review`'s receipt is the natural carrier —
it already refuses a lane that left no report, so recording the lane's *tool
version* and checking it is the same shape. Same treatment for `codex`, which is
also install-dir-resolved and also a review lane.

This is the one requirement in §2 that is about a **standing property**, not a
state, and my earlier drafts read it as a state.

### U5 — register the enabled plugin as a source (#446)

`sources/fable-orchestrator.manifest` **already exists**, so #446's "neither is in
the corpus" is half stale — amend it. Missing is
**`yuting0624/antigravity-for-claude-code`**, the plugin `.claude/settings.json:81`
enables (`:99-102` names the marketplace); the two existing antigravity manifests
are `antigravity-plugin-cc-chris` / `-marcos`, different repos. Register via
`mise run kb-manifest-add` with **`build = skip` + a reason** (`kb-build` is RED, #397/#417 — #446's own blocker note), plus the `currency.toml` row.

### U6 — reverse-engineer graphify-labs / app.graphify.com, reproduce it locally (#448, #450)

Ray: *"how can we use graphify locally to find those same issues instead of
waiting for the graphify-labs pr bot or app.graphify.com to generate them"*.
Deliverable: what the bot computes, which of it local graphify already produces,
and the gap — with the `use-tool-builtins.md` justification written down either
way. The `mcp` artifact capability above is a candidate delivery surface, pending
the connector check.

### U7 — the session-review lanes, including the one Ray just added (#435, #423, #427)

`session-review.js` has ten lanes (`circles` `forgotten` `contradicted` `unpinned`
`context` `tooling-gap` `bot-reviews` `pending-work` `extraction-readiness`
`telemetry`; `HANDOFF_LANES` at `:235` holds eight). Absent, each named by Ray:
skill-not-triggered · critical-escalation · codegen/enum (#412) ·
profiler/metrics (#427, #443) · universal-logger gap (#461) · linter-skip
detector (#427) · a lane pointed at the instrument (#423).

**Ray's new requirement, 2026-08-23:** *"the session-review workflow needs to do
the same analysis when it reviews the telemetry logs/session transcripts — find
ways to reduce agent token usage by migrating repeated steps into a workflow that
has been fully automated."* So the `telemetry` lane's brief gains U2's own test:
not just "which commands repeated", but **"which repeated sequence is already a
task nobody called, and which wants a new skill→task→module triple"**. This
round supplies its first two seeded examples — the `agy-delegate` bypass (U4) and
`kb-tool-sync` never being named by its own skill (U2 gap 4). `kb-distill` (#219)
is the existing frequency miner; `#448` says research before building a third.

**Two lanes Ray named that my drafts dropped entirely (cold lane, L1 + L2):**

- **`.codex/config.toml` writer hunt** — *"finding the cause of what is writing
  to `.codex/config.toml` and adding claude telemetry lines"* (08-21 `:133`,
  restated 08-23). `grep "codex/config.toml"` over the plan → **0**. The
  instrument already exists: `mise run kb-attribute-write -- <path>`, built
  because **eleven** candidate writers were refuted by reproduction across two
  incidents (#399, #374).
- **skill-authoring provenance** — *"all skills should be created via
  `/skill-creator` and use `/mattpocock-skills:writing-for-agents`"* (`:136`).
  Both → **0** in the plan. This is a lane about how *new* skills enter the repo,
  and it pairs with U10c's tool-adoption rule.

**And the lane this round's own evidence demands: TRIAGE CONSUMPTION.** Ray:
*"there are a lot more requests that i've made that are still either being lost
and/or have not been run through the aggregation/triage step"*. Every existing
lane FINDS things; **nothing consumes what was found.** The proof is this round's
premise: #435 and #436 were filed *by* the aggregation step on 2026-08-21 and no
mechanism ever picked them up, so the same directive arrived again on 08-23. The
handoff's own tallies say the same at scale — **41 + 25 + 23 NOT TRIAGED** across
three rounds. A lane that reads the open backlog against the current round and
reports *"filed N rounds ago, still unstarted, and re-requested since"* is the
missing half, and it is the one that would have caught this round before Ray had
to.

Ray's *"1 agent in the sweep lane"* is answered: `runs/2026-08-23-2/` was the
deliberate `lanes:['telemetry']` validation run — nothing was lost; the default
handoff set is eight.

### U8 — LSP, native static analysis, blast radius, and visuals (#436, #370)

**Scope correction before anything else (cold lane, L5 + L6).** Ray named
**three** workflow files — `.claude/workflows/kb-extract.js`,
`kb-tool-review.js`, `session-review.js` — each to be *"ingested / deep extracted
/ reflected / artifacts generated"*, **and** *"same synced visual documents
should be done for this project's **python code** also."* My drafts narrowed all
of that to `session-review.js`: the other two workflows appear only as evidence
about the graph, never as deliverables, and the python surface is absent
entirely. **Four surfaces, not one** — three JS files plus `python/src/kb_setup`
(~2,386 graph nodes). Every measurement below (biome, the parse trap, the
staleness chain) was taken across all three JS files, so the evidence already
covers the wider scope; only the deliverable list was narrow.

Ray, correction 4: *"an LSP for the session-review workflow should also be used
to help navigate the code · linters/static analyzers/type checkers/code
generators/code to automatic documentation generation tools should be used ·
**prefer native/system tooling (rust/c++/zig/c/etc)** · figure out how graphify
determines blast radius/call hierarchy to help determine what is affected by the
code and needs to be reviewed."*

**a. Blast radius — answered, and armed live.** graphify computes it as a
**reverse traversal** from the named node over `DEFAULT_AFFECTED_RELATIONS`:
`calls · indirect_call · references · imports · imports_from · dynamic_import ·
re_exports · inherits · extends · implements · uses · mixes_in · embeds ·
requires`, to a depth (default 2 upstream). The verb is
`mise run kb-affected -- "<symbol>" [--depth N]` (`mise.toml:783`), whose comment
already states why it exists: *"the question `kb-query` structurally CANNOT
answer — `query` is a forward BFS; 'what breaks if I change this' needs the edges
walked backwards."* Live arm:

```
graphify affected "check_sync"    → 9 real callers with file:line
                                    (run.py:92, cli.py:641, apply.py:35, …)
graphify affected "judge"         → No unique node match
graphify affected "HANDOFF_LANES" → No unique node match
```

**Chasing that negative changed the answer twice — and the final answer is much
better news.** First I wrote "`.claude/workflows/*.js` is absent from the graph,
`refresh_self` extracts `python/` + `tests/` only". Both halves were wrong:

- `_SELF_ROOT = "."` (`graph.py:1477`) — the extraction root is the **repo root**,
  with a long comment explaining that one root is the only way a cross-tree edge
  can exist at all.
- Reading `graph.json` directly (after two broken probes of my own — the keys are
  `source_file`/`source_location`, and the edge key is `links`, not `edges`):
  **6,573 `.js` nodes**, and `.claude/workflows/kb-extract.js` (11 nodes) and
  `kb-tool-review.js` (10 nodes) are both present with real functions and
  top-level consts at real line numbers (`promptFor()` L270, `CLAIMS_SCHEMA`
  L57). Our namespace is `.self-graph`, 2,386 `kb_setup` nodes.
- `session-review.js` → **0 nodes**, and the reason is **staleness, not
  capability**: `built_at_commit` is `fbc80305`, `graph.json` mtime **Aug 21
  18:16**, while `session-review.js` was last changed in **`c4ea46a0` on Aug 23**.
  The two older workflows (Aug 6, Aug 2) predate the build and are in.

I first wrote "so it is one `mise run kb-watch` away" and then checked instead of
assuming. **It is not, and the reason promotes #397 from a background carry to a
prerequisite.**

```
graphify-out/.compose-manifest.json   ABSENT
graphify-out/.merged-chunks.json      501 bytes, Aug 21 18:16
graphify-out/.currency-stamp.json     ABSENT
```

`_load_compose_manifest_or_refuse` (`graph.py:1937-1951`) raises `SystemExit` on a
missing manifest — *"unknown is not permission, and there is nothing safe to
recompose FROM until a `kb-build` has written one. Run `mise run kb-build`
first."* And `kb-build` **fails** (#397: `anthropic-sdk-python` has 3 unclassified
files and detect fails closed). So:

> **#397 → no compose manifest → `kb-watch` REFUSES → the graph cannot be
> refreshed → `session-review.js` stays out → blast radius on the session-review
> workflow is UNAVAILABLE.**

The standing handoff note says *"kb-build being RED blocks the MERGE step, not the
RUN"*. True of the corpus run; **false here**. It blocks Ray's blast-radius
requirement outright, and it is also why every graph query in this planning
session returned off-corpus junk: the graph is two days stale *and* cannot be
refreshed. **#397 is therefore U0** — a prerequisite for U7/U8, not a carry.

**The real #436 gap is DEPTH, not presence.** Eleven nodes for a
thousand-line file is top-level declarations only — no intra-file call edges — so
`affected` would return almost nothing useful even once the file is in. That is
what tree-sitter/LSP-grade analysis is for, and it is the honest justification for
that half of the epic.

**b0. LIVE PROBE — Ray asked for the LSP + linters twice, so this is now a spec,
not a research item.** Everything below was run, not looked up:

| fact | measured |
|---|---|
| `hk builtins` ships **`biome`** | yes — one of **148** builtins, alongside `deno`, `deno_check`, `eslint`, `prettier`. `use-tool-builtins.md` says take the builtin, so the JS gate is **one line** in `hk.pkl`: `["biome"] = Builtins.biome`, exactly like `["taplo"] = Builtins.taplo` |
| biome has an LSP | **`biome lsp-proxy`** ("Ensures the Biome daemon server is running, then forwards Language Server…"), plus `start`/`stop`. Rust. This is the LSP Ray asked for |
| speed | `biome lint` on the 1,408-line `session-review.js`: **9–34 ms** |
| real findings on that file | **`lint/complexity/useOptionalChain` ×1 (warning)**, **`lint/style/useTemplate` ×4 (info)** — all genuine, all FIXABLE, in a file whose only current check is a documented false green |

**And the trap, which is why this is a spec and not a one-liner.** biome also
reports **1 error — a PARSE error, not a rule violation**:

```
.claude/workflows/session-review.js:1334:1 parse
  × Illegal return statement outside of a function
  > 1334 │ return {
```

Workflow scripts are **wrapped by the harness** in an async function, so a
top-level `return` is legal at runtime and illegal as a standalone module.
**Control arm: all three workflow files fail identically** (`kb-extract.js` → 1,
`kb-tool-review.js` → 1). So it is a property of the workflow FORMAT, not a
defect in the code — and wiring `Builtins.biome` naively would ship a
permanently-red gate resting on a false premise.

That is the same trap the file's own header documents in the other direction, at
`session-review.js:3-15`: *"`node --check` IS A PROBE THAT CANNOT FAIL … returns
0 on syntactically broken code"*, with the wrapper recipe
(`{ echo '(async()=>{'; cat file; echo '})()'; } | node --check`) as the fix.
`node --check` is a **false green**; a naive biome step would be a **false red**.
Same cause, opposite sign.

**The "or biome config" half of my draft is now REFUTED — measured against the
pinned schema, with control arms.** There is no parse-mode option in biome
2.5.10:

- `$defs.JsParserConfiguration` has exactly three properties —
  `gritMetavariables`, `jsxEverywhere`, `unsafeParameterDecoratorsEnabled`.
  `sourceType` / `moduleKind` / `script` / `commonjs` → **0 hits** in the whole
  schema (control: `jsxEverywhere` → 1, so the grep discriminates).
- **Extension makes no difference** — the identical fixture as `.js`, `.cjs` and
  `.mjs` all emit `parse × Illegal return statement outside of a function`, rc=1.
- **Suppression cannot reach it** — parsing precedes suppression, so
  `// biome-ignore-all` still yields the diagnostic. Parse errors have no rule
  name.

| option | keeps the gate able to FAIL? |
|---|---|
| **(a) wrap at lint time** — copy into `(async()=>{ … })()` in a temp dir, lint that | **YES — full lint AND parse checking retained.** Needs a `kb_setup` module + task; prepend the prelude on one line so line numbers do not shift |
| **(d) restructure the three files** so the top-level `return` is legal | **YES — best fidelity, no config trickery.** Highest change risk: three harness-coupled files whose runtime semantics must not move |
| (b) `overrides[].linter.enabled = false` | **NO for those files** — measured, they are not processed at all. Honest exclusion, not a gate |
| (c) suppression comments | **impossible** |
| **(e) `--skip-parse-errors`** | **NO — a MEASURED FALSE GREEN.** A directory holding a genuinely broken file (`function f( {`) lints **rc=0**, "Checked 1 file", the broken file silently dropped. **This is the `node --check` failure exactly, and it is disqualified.** |

**So the deliverable is (a) or (d), never (e)** — plus the four genuine findings
kept, and the FAIL direction proven on a real break.

**b. Native tooling — mostly already here, and unconfigured.** Against Ray's
rust/c/zig preference:

| job | native tool | status |
|---|---|---|
| Python lint + format | **`ruff`** (Rust) | pinned; an hk step |
| Python type check | **`ty`** (Rust) | pinned; an hk step |
| **Python LSP** | **`ruff server`** and **`ty server`** — both subcommands verified present | **exist as project dependencies and no LSP is configured anywhere in the repo** |
| JS lint + format + **LSP** | **`biome`** (Rust) 2.5.10 | installed on this machine; **`grep -c biome mise.toml` → 0** (control: `hk` → 1). Not a project dependency, and no JS step exists in `hk.pkl` |
| TOML · Markdown · secrets · typos | `taplo` · `rumdl` (Rust) · `gitleaks` (Go) · `typos` (Rust) | already hk steps |
| diagram render | `dot`/graphviz (C) native; `mmdc` is Node | neither pinned here |
| code generation | `datamodel-code-generator` | a dependency; the #412 enum work is its use case |
| code → docs | **U10 — research dispatched**; the one row with no incumbent | |

So the LSP requirement's Python half is **configure what is already installed**,
and the JS half is **pin `biome` and add the hk step** — no eslint, no prettier,
no Node linter. `oxlint`, `tsgo`, `deno`, `swc` are all ABSENT here; biome is the
one native JS tool actually present.

**c. Visuals.** Research first with cited pros/cons per Ray's text, then pin
`mermaid-cli` + `graphviz` in **this** repo's `mise.toml`, generate the first
synced diagram, gate it on `currency.views`, and publish through the Artifact tool
per the three skills.

**Three requirements from the directive that my earlier drafts dropped, restored
here — self-audit, before the coverage agent reported:**

- **BEFORE and AFTER, not just "now".** Ray: *"architecture/workflow/sequence
  diagrams of what exi[s]ted before and what it is now"*. The deliverable is a
  **comparison**, and `artifact-diagramming` is explicit that a comparison must
  draw the difference — "a separate labeled box per option, with nothing
  connecting them to the system, is not a comparison". For session-review that
  means the seven-lane pre-#466 shape against the ten-lane current one, with the
  edges #466 added marked.
- **"the generated summaries also need to follow this visual artifact
  generation".** Not only the workflow's *code* gets diagrams — its **outputs**
  do: the synthesis and handoff that `docs/session-review/runs/<date>-<n>/`
  archives. So `session_review_archive` grows a rendered-figure step, and
  `kb-session-review-archive` is where it belongs (one task already owns writing
  that directory).
- **"ingested / deeply extracted / reflected / generate all graphify
  artifacts"** — four verbs, and my drafts carried only "ingested". The full
  chain is `kb-merge` (deep/semantic extraction, the only LLM path) →
  `mise run kb-label` → `mise run kb-reflect` → `mise run kb-artifacts`
  (wiki/graphml/svg/obsidian/report). All four are existing tasks; none is
  optional in Ray's sentence, and U0 gates every one of them.

Two measured facts:

- **Nothing generates a diagram today** — mermaid in **4** of our own markdown
  files, all hand-authored under `docs/agents/`, against a control of **40**
  carrying ```bash fences.
- **The JS workflows are the largest unlinted surface in the repo.** `hk.pkl`
  declares 21 steps and **not one covers JavaScript**; `session-review.js` alone
  is 1,408 lines whose only check is the `node --check` false green.

### U9 — enforce graph use, and ingest the programmatic-tool-calling sources (Ray, correction 5)

> the session-review workflow also needs [to] find ways to enforce all the agents
> to use the graphify sources via: /graphify skill · graphify query/explain/etc
> cli · kb-query · programmatic tool calling — add these as graphify sources if
> they do not exist yet … deep extraction and reflection … **make sure the
> sources are not truncated**

**a. The enforcement lane.** A session-review lane whose subject is *graph
compliance*: per agent and per session, did it reach the graph through any of the
four channels (the `/graphify` skill · `graphify query`/`explain`/`path` ·
`kb-query` · programmatic tool calls to the `mcp__graphify__*` tools) before
searching source? The measurement already exists in raw form — `kb_setup.graph_first`
writes a session marker to decide its DENY — so the lane reads compliance rather
than inventing a metric. Precedent for why a lane is not enough on its own: the
warning-only graph-first rule scored **0 compliance in 19 chances**; the DENY took
its violations **62 → 0**. So the lane's output should feed a guard change, not
just a report.

**b. The sources — one of the five is already in, four are not.** Measured:

| Ray's URL | state |
|---|---|
| `platform.claude.com/…/tool-use/programmatic-tool-calling` | **ALREADY INGESTED** — vendored as `sources/media/ptc-doc.md` (1,584 lines), REGISTRY row 48, referenced by three extraction chunks, and **queryable**: `kb-query --prose --idf` returns *"Tools as async Python functions"*, *"Token efficiency"*, *"When to use programmatic calling"* from `ptc-doc.md` |
| `platform.claude.com/cookbook/tool-use-programmatic-tool-calling-ptc` | absent |
| `github.com/daly2211/open-ptc` | absent — the only **code** source of the five, so `kb-manifest-add` + free AST extraction |
| `anthropic.com/engineering/advanced-tool-use` | absent |
| `platform.claude.com/cookbook/evals-agentic-search-reproduce-agentic-search-benchmarks` | absent |

Neither `open-ptc` nor the three cookbook/engineering URLs appear in
`sources/REGISTRY.md` (control: 68 `github.com` rows there, so the file reads).

**c. "Make sure the sources are not truncated" is a real hazard with a real arm.**
REGISTRY row 47 records the precedent verbatim: *"FULL text recovered via logged-in
Chrome (graphify fetch got TOC only; WebFetch 403'd)"* — a fetch that returned a
table of contents and looked like a successful ingestion. So each source gets a
length/section check against the live page before merge, and
`mise run kb-validate-chunks -- <chunk.json>` before `kb-merge`, because a chunk
that parses is not a chunk that captured anything.

**d. Why PTC matters beyond being a source.** Its own doc says it cuts *"model
round trips and token use in multi-tool workflows"* (REGISTRY row 48: *"20-40%
fewer tokens"*). That is Ray's *"reduce agent token usage"* theme with a named
mechanism — so this unit feeds U7's telemetry brief directly: some of what the
session-review fan-out does per-agent may belong in code that calls tools
programmatically instead.

**Sequencing:** ingestion is gated on **U0** — `kb-build` must be green before a
new manifest can reach the graph, and deep extraction is the only LLM-cost path
in the corpus, so it is scheduled, not improvised.

### U10 — code → documentation generation, and the tool-adoption policy (Ray, correction 7)

> /research tools to automate/generate documentation from the code
>
> - each tool we use must then become an critical/currency dependency
> - see if this a tool we can use for that: <https://github.com/tree-sitter/tree-sitter-graph>

**a. `tree-sitter-graph` — REJECT, and the research found harder reasons than
dormancy.** It is a **DSL for constructing graph structures from tree-sitter
CSTs** — it emits a graph and nothing downstream: no HTML, no docstring
extraction, no API surface. **Not a documentation generator.** Worse, that is
*the layer graphify already occupies here*, so adopting it means re-deriving
graphify's AST graph in a DSL — `use-tool-builtins.md`'s worked failure, in
advance. Four hard blockers, each measured:

| signal | value |
|---|---|
| last commit / release | **2024-12-11** (~20 months); v0.12.0's **entire** changelog is *"Upgraded the `tree-sitter` dependency to version 0.24."* |
| its principal consumer | **`github/stack-graphs` is ARCHIVED** — *"no longer supported or updated by GitHub"* |
| version fit | tsg pins tree-sitter **0.24**; this repo's locked tree is **0.25.2** |
| Python distribution | **none** — PyPI 404 (control: `tree-sitter` → 200). It could only enter as a `cargo install`ed foreign binary, i.e. a Rust toolchain dependency in a mise+uv repo |

Under Ray's own U10c policy that would mean a `currency.toml` row tracking a
crate dormant 20 months whose downstream is archived. **`ast-grep` (Rust,
0.45.1, 2026-08-07) is the maintained tree-sitter-based tool** if that layer is
ever wanted.

**b. THE CHEAPEST MOVE, and it costs nothing: run `mise run kb-artifacts`.**
The research's most useful finding is not a tool at all —
`artifacts.py:_ARTIFACTS` registers **eight** exports including `wiki/`
(agent-crawlable), `obsidian/`, `graphml`, `callflow-html` and `cypher`, and
**five of the eight have never landed on disk**: `ls graphify-out/` shows
`memory/`, `cache/`, `reflections/`, `GRAPH_REPORT.md` and **no `wiki/`**. Ray's
directive says *"generate all graphify artifacts"* — that is an unrun task, not
an adoption. **Judge the doc gap only after seeing what the tool we already own
produces.**

**c. But an API reference IS a real gap — graphify carries no docstring text.**
Control-armed: `graphify explain ".self-graph::…clean_env"` returns identity,
file:line, community and 32 edges — **no signature, no parameters, no
docstring** (control: a bogus symbol → *"No node matching … found"*, so the probe
discriminates). graphify is a **structure** index, not a **documentation** index,
and the long explanatory docstrings that are this repo's design record are
invisible to it. So this is not reinvention.

**d. The recommendation, native-first per Ray:**

| surface | tool | why | cadence |
|---|---|---|---|
| **Python gate** | **`griffe check kb_setup -s python/src -a <ref>`** | worktrees a git ref, diffs the **API surface**, **exits non-zero on breakage** — `kb-gates`-shaped, not regenerate-and-eyeball. Static AST, no import | 2.2.0, 2026-08-16, ~5/yr |
| **Python render** | **`pdoc`** | one command, no config, renders the docstrings this repo invests in. MIT-0. Caveat: **pdoc imports** the package (safe for `kb_setup`; if that changes, `mkdocstrings-python` is the griffe-backed drop-in) | 16.0.0, 2025-10-27 |
| **JS docs + gate** | **`deno doc --lint`** | **Rust**, single binary, first-class plain-JS JSDoc, **exits non-zero** on undocumented public symbols and missing return types | ~monthly |
| **JS architecture gate** | **`dependency-cruiser --validate`** | exit code = violation count, `--ignore-known` baseline, emits **mermaid**/dot/d2/markdown. Best-designed gate in the whole survey | v18.2.0, 2026-08-10 |
| **diagram render** | **graphviz `dot`** (pin it) | **C**, already installed at 16.0.0 and unpinned (U11); the common output target of pyreverse, dependency-cruiser and Doxygen | low |
| Python diagrams | `pyreverse` (ships **in pylint**) | emits `.mmd`/`.puml`/`.dot` **natively** — no graphviz required | pylint 4.0.7, 2026-08-09 |

**Rejected with reasons** (so the survey is not re-run): **Doxygen** — with `"""`
docstrings *none of its special commands work and text renders verbatim* unless
every docstring is rewritten (`doc/docblocks.dox`) · **Structurizr CLI** —
ARCHIVED 2026-02-01, JVM, and hand-authored rather than code-derived ·
**PlantUML** — JVM · **D2** — a third diagram format, zero new capability ·
**documentation.js** (2024-01-30) / **code2flow** (2023-01-08) / **madge**
(2024-08-05) — dormant · **CodeBoarding** — LLM-in-the-loop, collides with
`do-not.md` #4 · **pydeps / py2puml / dep-tree** — reinvent graphify's import and
call edges. **SCIP** is technically the richest source (its proto carries
`documentation` and `signature_documentation` for both Python and TypeScript) but
you would write the renderer.

**And the honest ordering for the JS surface:** generated API docs for
`session-review.js` are worth less than a **linter**. 1,408 lines, no lint, no
type check — U8b before U10.

**c. The policy, which is bigger than this unit.** *"each tool we use must then
become a critical/currency dependency"* is a **standing rule about all future
tool adoption**, not a one-off. It has a natural home and an enforcement point:
`currency.toml` gets the row, and U2's uniform upgrade interface is what makes
adding one cheap. Worth stating as a rule file so it survives this round —
adopting a tool without a `[tool.*]` row is how `antigravity-cli` was *"absent
from this file entirely … the engine reported green for it forever by never
asking"* (`currency.toml:1782-1784`, in the row's own comment).

## LOST — said in the transcript, absent from the plan (cold lane, ranked)

Twelve items the re-review found by grepping the transcript against the plan
(control: `grep -c "session-review"` → 37, so the probe discriminates). These are
the highest-value output of the whole review, because each is a requirement Ray
stated and I never wrote down.

| # | Ray's words | why it matters |
|---|---|---|
| **L3** | *"it should also be able to be triggered by an agent so that it runs when context hits over 20% — so toggle this flag: **`disable-model-invocation: true`** in `.claude/skills/clear-prep/SKILL.md`"* | **the most concrete instruction in the entire directive** — a named flag in a named file — and U1 does not carry it. `grep "20%"` → 0, `grep "disable-model-invocation"` → 0 |
| **L6** | *"all the workflows … `kb-extract.js` · `kb-tool-review.js` · `session-review.js`"* each ingested/deep-extracted/reflected/artifacts | **the three-file scope silently became one file.** The other two appear only as *evidence about the graph*, never as deliverables |
| **L5** | *"same synced visual documents should be done for this project's **PYTHON CODE** also"* | `grep "python code"` → 0. U8c scopes visuals to session-review only |
| **L1** | *"finding the cause of what is writing to `.codex/config.toml` and adding claude telemetry lines"* | a lane Ray named explicitly; `grep "codex/config.toml"` → 0. `kb-attribute-write` already exists as the instrument |
| **L2** | *"all skills should be created via `/skill-creator` and use `/mattpocock-skills:writing-for-agents`"* | both → 0 |
| **L10** | *"have a subagent **using the `/fable-orchestrator:orchestration`** review this session and the telemetry"* | the plan says only "an agent is doing it" — **and in fact this review ran as a plain `general-purpose` agent. The routing Ray specified was not used.** |
| **L4** | *"use graphify as ai agent memory … deep extraction and reflection … from its final output **or on its intermediate steps**"* | an open **question to Ray**, never answered or carried |
| **L9** | yuting0624 *"should be … **in sync w the latest version of** the antigravity plugin"* | U5 registers a manifest + row; **the plugin↔repo sync mechanism IS the requirement** and is unspecified (cache holds 0.23.0 AND 0.24.0) |
| **L7** | *"can you just use `mise ls-remote antigravity-cli`…?"* | `grep "ls-remote"` → 0. A direct question; the plan adopted `mise outdated -b -J` without ever saying why not `ls-remote` |
| **L8** | *"refactor it take in arguments/parameters/hints so it can work properly **in all modes**"* | "all modes" is never enumerated |
| **L12** | *"mermaid/tldr/**excalidraw**/etc"* | → 0. Minor |
| **L11** | *"review this session and **the telemetry**"* — asked **three times** (C4, C7, C8) | the plan contained **zero** telemetry measurements. **Discharged below.** |

### L11 discharged — the first actual telemetry measurements

`.agent/telemetry/` holds **11,370 files / 3.2 GB** (5,686 `.response.json` +
5,693 `.request.json`). Aggregated from the `usage` field:

```
ALL:     5,686 responses · cache_read 1,203,758,976 · cache_write 24,086,400
                          · input 529,078 · output 4,973,695
AUG 23:    851 responses · cache_read   295,830,679 · cache_write  5,229,535
                          · input  40,625 · output   802,729
today:   claude-opus-5 454 · claude-sonnet-5 240 · claude-fable-5 157
```

**One day is 24.6% of all cache-read tokens ever recorded here, and cache-read
outruns fresh input 7,282 : 1.** So Ray's *"reduce agent token usage"* has a
measured shape and it is **re-sent context, not generation** — which is exactly
what programmatic tool calling (U9) targets, and what U7's telemetry-lane brief
must say instead of counting commands. Note also that `.agent/` is gitignored, so
this 3.2 GB is invisible to every other machine.

### One mode the graph split misses

`kb-query` does not only return off-corpus junk — **it can fail outright**. The
lane's own orientation query returned
`ERROR: [kb-query] Graphify returned an incomplete TRUNCATED result with rc=0 …
task failed`. Since every unit "opens with a graph query", the plan must say that
step needs `--budget`/narrowing or it **errors** rather than degrading.

## Second sweep — UNOWNED items found by my own pass (Ray, correction 7)

Ray asked for *"one more sweep of this session's telemetry/transcript to make
sure we have not missed anything."* An agent is doing it; this is my own,
because four of five subagents this session went idle without their report ever
reaching me. Six items, ranked:

1. **SCOPE CONFLICT, unresolved.** Ray's AskUserQuestion answer was
   *"/fable-orchestrator:orchestration option 1"* = **PR 1 only this session**.
   The plan is now **eleven units**. His later corrections added requirements
   without visibly rescinding that scope; his *"each work unit … then
   `/clear-prep`"* rule reads as a cadence across sessions rather than a
   one-session batch. **My assumption, stated so it can be corrected: the eleven
   units are the backlog, and this session takes U2a → as far as it gets, ending
   at whatever unit `/clear-prep` catches.**

   **Corrected (cold lane, I7):** my draft said *"if he meant literally one PR,
   U0+U2+U3 is the PR"*. That is not what he chose. **Option 1 as written to him
   was: "the currency fix + antigravity resync + plugin audit + the two source
   manifests"** — i.e. **U2 (partial) + U3 + U4 + U5**. **U0 appears nowhere in
   option 1**, and my restatement had silently dropped U4 and U5. If the literal
   reading wins, that is the PR.
2. **`/graphify` was typed FIVE times and never invoked until the seventh
   correction.** I ran `fable-orchestrator:orchestration`, `artifact-diagramming`
   and `artifact-capabilities`, and skipped the one he prefixed most. This is a
   live instance of the exact category his directive names — *"cases where a skill
   isn't being triggered and manual commands are being done"* — produced by me,
   during the planning of the lane meant to catch it. It belongs in U7's
   `skill-not-triggered` lane as its **third** seeded example, beside the
   `agy-delegate` bypass and `kb-tool-sync`.
3. **"some differ in what type of documentation they sync to"** (correction 3) —
   U2's table has a single "corpus/doc resync" row; it does not enumerate WHICH
   tool syncs to WHICH doc surface (manifest? `docs/currency/`? a generated
   skill? the corpus itself?). That mapping is the per-tool internals Ray says
   may differ, and it is the part that must be explicit for the entry point to
   be uniform.
4. **"graphify has the most complicated documentation source that we have not
   been able to complete yet"** (correction 3) — named by Ray as the hardest
   case, and no unit currently *completes* it. U2 lists it as "the incomplete
   half"; that is a description, not a plan. Either scope it or say plainly it
   is deferred, rather than leaving it as a known-hard thing nobody owns.
5. **Four of five subagents went idle without reporting** (three Explore, one
   premise-verifier) — I re-derived everything by direct probe, so nothing is
   missing, but the findings those agents did produce are lost. #432 records this
   (*"8 of 20 subagents needed a hand-written nudge"*) and is unbuilt. It is also
   why this plan's own evidence is first-hand rather than delegated.
6. **`--show-sizes` was dropped** from Ray's `uv tree --outdated --show-sizes
   --all-groups --format json`. I ran it without that flag. It reports package
   sizes, which is directly relevant to a dependency-weight question — minor, but
   he specified it and I silently narrowed it.

## The work units (continued)

### U11 — the repo depends on Ray's PERSONAL machine, and `mise config ls` proves it (Ray, correction 9)

> make sure all tools/libraries/sdks/libraries/etc being used is added in
> mise.toml/pyproject.toml

Audited. The answer is worse than "a few pins are missing", and `mise config ls`
names the two configs side by side:

```
~/.config/mise/config.toml       python, npm, bun, NODE, go, rust, … jq, BIOME,
                                 npm:@mermaid-js/mermaid-cli, gitlab:graphviz/graphviz,
                                 npm:ctx7, pipx:graphifyy, pipx:datamodel-code-generator,
                                 pipx:mcp2cli, codex, antigravity-cli, rumdl, typos, …  (~150)
~/dev/…/knowledge-base/mise.toml python, uv, hk, pkl, typos, conda:ffmpeg, taplo,
                                 rumdl, gitleaks, agnix, fnox, doppler, gh, codex,
                                 antigravity-cli                                        (15)
```

**Every tool below is reachable only because Ray's personal global mise config
supplies it.** On a fresh clone by anyone else — or on another machine — they are
simply absent:

| tool | why this repo needs it | declared where |
|---|---|---|
| **`node`** | **the three workflow files ARE JavaScript**; `session-review.js` is 1,408 lines, and the file's own header documents a `node --check` recipe | **global only** |
| **`biome`** | U8b's linter/formatter/**LSP**; `hk` even ships a `biome` builtin | **global only** |
| **`mmdc`** (`npm:@mermaid-js/mermaid-cli`) | U8's diagram render | **global only** |
| **`dot`** (`gitlab:graphviz/graphviz`) | U8's diagram render | **global only** |
| **`ctx7`** | named as **step 3 of `research-doc-sources.md`'s preference chain** — a documented, mandated step | **global only** |
| `jq` | appears in docs/probes (`gh --jq` is builtin and fine) | global only |

**This contradicts two of the repo's own invariants**, which is what makes it a
unit rather than a chore: `CLAUDE.md` invariant 3 says *"Inputs are
reproducible"*, and the whole `currency.toml` engine exists so a dependency
cannot be green by never being asked about. A tool the repo invokes but never
declares is the purest form of that failure — and it is exactly the shape
`currency.toml:1782-1784` records for antigravity: *"absent from this file
entirely … the engine reported green for it forever by never asking."*

**One live corroboration, not a hypothetical:** the global config also carries
`pipx:graphifyy`. That is the source of the stale-PATH defect `CLAUDE.md:125`
already records from day one of the currency engine — *"`MISE_ENV_CACHE=1` had a
stale `pipx-graphifyy/0.9.23/bin` on PATH ahead of the mise shims."* The global
config shadowing a project pin is a defect this repo has already paid for once.

**Correctly NOT mise-pinned, stated so the list is not misread as all-gaps:**
`claude` self-updates and is tracked via `currency.toml`'s `expected` class;
`tree-sitter` + its ~30 grammars arrive transitively through `graphifyy[all]`;
`ruff`/`ty`/`pytest`/`mcp2cli`/`datamodel-code-generator`/`graphifyy` are all
correctly in `pyproject.toml`. `perl`, `curl` and `git` are OS-provided — but
`perl` is the sanctioned `timeout` substitute (`long-running-command-hangs.md`
rule 3a), so it belongs in the `absent_binary` awareness set even if it is never
pinned.

**Deliverable:** pin the five real ones through their owning tool (`mise use`),
add each as a `currency.toml` row per Ray's U10c policy, and add a **gate** —
because the failure mode here is invisible on the author's machine by
construction, which is why it survived this long.

## On `/graphify` — step 0, and which half of it actually works

Every unit opens with a graph query (`research-doc-sources.md` step 0, hook-
enforced). I told Ray twice during planning that the graph "returns off-corpus
junk". **That was too broad, and U9's probing disproved it.** The truth is a
clean split:

| question class | result |
|---|---|
| **corpus / prose** ("what is programmatic tool calling?") | **answers well** — `kb-query --prose --idf` returned ten on-target nodes from `ptc-doc.md` and the code-execution doc, correctly ranked |
| **this repo's own code** ("how does the currency in-sync check work?") | returns twenty off-corpus nodes and nothing about `kb_setup` — the third session to record it |

So the graph is not broken; **it is blind to exactly one class — our own code** —
which is what U0 (the graph cannot be refreshed at all) and U8 (extraction depth)
address. Reporting that as "the graph is useless" would have justified skipping
step 0 for every question, including the ones it answers best.

Meanwhile use the right verb: `graphify explain "<symbol>"` and
`graphify path "<A>" "<B>"` are read-only, allowed direct, and better suited to a
symbol question than `kb-query`'s ranked BFS.

## Concurrency — what may and may not run beside the 4.8 h corpus run

U2a runs for hours while other units proceed, so "what writes `graphify-out/`"
has to be settled before, not during. Read from the source:

| unit / task | touches `graphify-out/graph.json`? | safe beside U2a's run? |
|---|---|---|
| **U2a the corpus run** | **no** — `admit_source` materialises the pinned graphify clone into a `TemporaryDirectory` and stages chunks; nothing on the run path reads `graph.json`, `.compose-manifest.json`, or any `kb-build` product | — |
| **U0 `kb-build`** | **WRITES it** | yes w.r.t. U2a (disjoint), **but see the row below** |
| **`kb-artifacts`** | **`report` REWRITES it** — `_REWRITES_GRAPH = frozenset({"report"})` (`artifacts.py:54`), sharing the exact `cluster-only` CLI branch `kb-label` uses. The other seven are pure exports | **NOT beside `kb-build`** — two writers, one file. `artifacts.py:136` even names the hazard: *"graph.json just changed underneath us — every OTHER writer of it"* |
| `kb-watch` / `kb-merge` / `kb-label` | write it | serialize with the two above |

**Three consequences.** First, **`mise run kb-artifacts` IS safe with `kb-build`
RED** — it reads `graph.json` (present, 492,654 nodes) and only refuses if that
file is *missing* (`artifacts.py:95-97`), so U8c's "cheapest first move" is
unblocked today. Second, **`kb-artifacts` and `kb-build` must be serialized**, so
U0's re-run and U8c's artifact generation cannot be parallelised with each other
even though both are safe alongside U2a.

Third — **`record --accept` is disjoint from `graph.json` but destructive to the
plan dir**, which sets the one hard ordering constraint inside U2a. Its mutation
targets, read from `…_record.py`:

| target | operation |
|---|---|
| `graphify-out/graphify-semantic-corpus/` (the canonical plan dir) | **`shutil.rmtree` then `.replace()`** (`:158-163`) — the previous canonical is kept as `…​.superseded-<ts>/` (one already on disk from the eighth record) |
| `python/src/kb_setup/graphify_semantic_corpus_authority.json` | rewritten (`:164`) — **tracked** |
| `docs/agents/graphify-semantic-corpus-authority-ledger.md` | rewritten (`:165`) — **tracked** |

None of those is `graph.json`, so `record` never collides with `kb-build` or
`kb-artifacts`. But it **deletes and replaces the directory the run reads**, so:
`record --accept` must fully complete **before** the run starts (the step order
above already does this), and **no unit may trigger a re-record while the ~4.8 h
run is in flight** — which in practice means the cap decision, the slice
constants and the manifest all settle in U2a steps 1-5 and are not revisited
until the run finishes.

## Routing (session mode = codex, effort xhigh)

Architect keeps decomposition, specs, premise verification and verdicts. Trivial
edits stay inline. Everything else → **codex-implementer at xhigh**, cold-reviewed
by the **non-codex** family (antigravity/Gemini, through the reconfigured lane
once U4 lands). U2 changes a **gate** and emits findings the report layer
consumes, so its spec carries a `PREMISES` block, goes to `premise-verifier`
pre-dispatch, and the dispatch carries `PREMISES-VERIFIED:`.

## Verification — per unit, both arms

1. **Negative arm, recorded before any fix:** `--tool antigravity-cli` silent
   while `--tool claude-code` → DRIFT ×2 and `--tool no-such-tool` → "unknown
   tool". The probe discriminates.
2. **Positive arm after U2, before U3's bump:** with the pin at 1.1.17 and the
   binary at 1.1.19, the check must report DRIFT naming both numbers; after the
   bump it must go silent. Both arms.
3. **#372's own arm:** the documented apply command must **refuse** an
   unrecognised positional, not print a green line having changed nothing.
   Control: `git diff mise.toml` must be non-empty after a real apply.
4. **`mise run kb-arms -- <spec.toml>`** — never a hand-written harness (#160);
   `control = true` row required; mutate the *wiring*, not a symbol name.
5. `mise run kb-check -- <changed paths AND their test files>`.
6. `mise run kb-gates` → `.agent/kb/gates/gates-<sha>.json`.
7. **Read bot bodies before the first `kb-ship`** — on #463 the 16 inline
   comments pre-dated the session; reading them after ship #1 cost a second
   fix-round and a second six-gate run.
8. `kb-review` → receipt → `kb-ship` → `kb-land` → **branch again**.
9. `/clear-prep` **with** the session-review workflow. Per unit, per Ray.

## Durability of this plan — Ray: *"have this visual plan be durable"*

The plan currently lives at `~/.claude/plans/recursive-knitting-goose.md` —
outside the project, harness-owned, and gone on the next `/clear`. `.agent/plans/`
is no better: gitignored, dies with the clone
(`agent-artifact-conventions.md` rule 4). Durable in this repo's vocabulary means
**tracked**. So on approval, two writes, not one:

1. **Committed** — the plan becomes a tracked document under `docs/` beside the
   directive it executes, so it survives a clone and a reviewer can diff it
   against what actually shipped. That also gives #370 its missing durable home:
   the rule it needs is *"a non-trivial plan is committed and carries a rendered
   diagram"*, not *"a plan carries a mermaid fence"*.
2. **Published** — the rendered Artifact, which is the visual half.

Both, every unit. A plan that only one machine can open is the same failure as a
report that only one machine can open, and this repo already has a rule for that
(`agent-report-persistence.md` 1b: promote to `docs/` once it is load-bearing).

## First actions on approval

1. **Publish the architecture/workflow Artifact** — the answer to *"this is not
   visual"*. Load **`artifact-design`** first (mandatory), draw per
   **`artifact-diagramming`** (mechanism not name, every arrow labelled,
   `currentColor` for both themes), and use **`artifact-capabilities`** only if
   the page should stay live rather than be a snapshot.
2. Branch off `main` (`kb-land` left the session there; `do-not.md` #7).
3. Commit **the direction addendum and this plan** — the addendum appended to
   `docs/direction/2026-08-22-ray-directives.md`, the plan under `docs/`.
4. **Close the undecided pairs, unit by unit.** The re-review's structural
   verdict is that eight of twelve units carry at least one `X or Y` left open,
   and that this — not missing detail — is what would send an implementer back
   with questions. Only **U10** and **U8's `b0`** are READY as written. The four
   that need Ray specifically: U1's *"only"*-vs-fallback and the
   `disable-model-invocation` intent (L3); U2's entry point
   (`kb-tool-sync` widened **or** a new wrapper); U4b's *refuse* **or** *warn*;
   U3's transitive-bump decision.
5. **U2a** — decide the cap FIRST (step 4 of that unit), then the resync chain,
   then start the extraction. It is the long pole (~4.8 h) and everything else
   runs beside it. The `--help` unknown is **closed**: the digest did not move
   2.1.240 → 2.1.241, so step 1 is exactly two constant edits.
6. Then U0, U1, and onward — each through
   `/fable-orchestrator:orchestration` **using that routing** (L10: this
   session's own review was dispatched as a plain `general-purpose` agent, which
   is not what Ray asked for), each closed by `/clear-prep` with the
   session-review workflow.

**Agent-dispatch discipline — TWO rules, both learned the hard way this session:**

1. **Tell the agent to write its report to a FILE first, then reply.**
   **10 of 10 subagents this session finished without their report reaching the
   caller unprompted.** Two eventually delivered — both only after two or three
   hand-written nudges — and the other eight left nothing behind. **#432 already
   records this remedy** (*"8 of 20 subagents needed a hand-written 'your report
   has not reached me' nudge; the 12 that did not were told to write it to a file
   first"*) and I used it on none of the first nine dispatches.

   The measured consequence: **every load-bearing fact in this plan is
   first-hand.** The currency blind spot, the class sweep, the structured-output
   probes, blast radius, the graph-staleness chain, the Claude plan-vs-live read,
   the biome parse trap, the `mise config ls` finding, the `--help` digest, and
   the whole concurrency section were all measured directly. The two agents that
   did report added real corrections on top — they were worth having, and none of
   the plan waited on them.
2. **Check the agent's TOOLSET against the instruction before dispatching.** On
   the tenth dispatch I finally applied rule 1 — to
   `fable-orchestrator:premise-verifier`, whose tools are **Read, Grep, Glob
   only**. It has no `Write`, so the remedy was impossible for it. This repo
   already documents the identical trap in the graphify skill's extraction step,
   in capitals: *"Do NOT use `Explore` — it is read-only and cannot write chunk
   files to disk, which silently drops extraction results."*

   The pairing: **`general-purpose`** (has Write) for anything told to persist;
   the read-only lenses (`premise-verifier`, `Explore`, the CLI reviewers) only
   for work whose entire output is the reply.

**Final tally, 11 dispatches:** 5 delivered, 6 produced nothing reachable.
**Rule 1 is proven by the one case that used it correctly** — `grill-facts` went
idle without ever sending a reply, and its complete 37-line report was on disk
anyway; the remeasure lane the same, at 101 lines. Both were read in full and
both changed the plan. `final-sweep` was the counter-example: read-only, so no
file fallback, and after **four** idle returns and **three** nudges — the last
asking only for a single line saying it had nothing — it produced no output at
all. Settled without output, per the doctrine's *"a completion without a
structured report is an error state, not a success"*.

## What this plan deliberately does not do

- File a new issue for anything already ticketed; stale tickets are amended.
- Build a version probe, a lock check, or a transactional installer — `tool_sync`
  has all three; the work is wiring, not construction.
- "Fix" `apply.set_pin_version` into `mise use` — `apply.py:77-78` records why
  (`mise use` installs as it edits, measured 2026-07-24).
- Treat `kb-build` as something to *fix* before trying it. **Corrected (cold
  lane, I3):** an earlier draft of this section forbade running it at all, which
  directly contradicted U0's own first instruction. **U0 opens by re-running it
  and reading the real rc** — graphify's message says the zero-node files will be
  retried. What this plan does not do is make any *other* unit wait on a green
  build: U5 registers with `build = skip`, and U2a's run needs no build product
  at all.
- Touch anything outside the project (`do-not.md` #11) — which is why
  `/antigravity:migrate` is **answered rather than run**.
