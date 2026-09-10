# Upgrade dependency inventory — read-only fact-find

Session date 2026-09-09. Read-only; no tracked file edited. Every figure below
was produced by a command run THIS session; the command is cited inline or in
the row. `mise ls-remote` calls used the Bash tool's own `timeout` param
(60000ms), one tool per call, sequential — never shell-chained. PyPI/GitHub
API reads used `curl --max-time 20`.

## 1. First-level dependency inventory

### 1a. `mise.toml [tools]` (21 entries; `sed -n '/^\[tools\]/,/^\[/p' mise.toml`, `grep -n min_version mise.toml`)

Latest column: `mise ls-remote <backend>:<tool> | tail -N` this session, one call
per tool. Two entries additionally cross-armed via a second independent route
(noted) because their `ls-remote` output was surprising or historically flaky.

| tool | backend | pinned | latest | behind? | currency.toml `[tool.<name>]`? | manifest? ref/commit | build flag | owning-tool bump command |
|---|---|---|---|---|---|---|---|---|
| python | core | 3.14.7 | 3.14.7 | CURRENT (3.14.x line) | no | no (language, not a source) | — | `mise use python@3.14.x` |
| uv | core | 0.12.8 | 0.12.11 | BEHIND (3 patch) | yes `[tool.uv]` | uv.manifest `0.12.8`/`68209e5c` — MATCH | — | `mise use uv@0.12.11` |
| hk | core | 1.57.0 | 1.58.1 | BEHIND | yes `[tool.hk]` | hk.manifest `v1.57.0`/`6189ceff` — MATCH | — | `mise use hk@1.58.1` |
| pkl | core | 0.32.1 | 0.32.1 | CURRENT | no `[tool.*]` entry in currency.toml | pkl.manifest **`ref = 0.32.0`** — STALE vs pin | build=defer | `mise use pkl@0.32.1` (pin already current; only the MANIFEST needs `kb-manifest-add`/hand re-pin to 0.32.1) |
| typos | core | 1.50.0 | 1.50.1 | BEHIND (1 patch) | no | typos.manifest `v1.50.0`/`4d9c206a` — MATCH | — | `mise use typos@1.50.1` |
| conda:ffmpeg | conda | 9.0.1 | 9.0.1 | CURRENT | yes `[tool.ffmpeg]` | ffmpeg.manifest `n9.0.1`/`bf1b838f` — MATCH | build=defer | `mise use conda:ffmpeg@9.0.1` (already current) |
| taplo | core | 0.10.0 | 0.10.0 | CURRENT | no | taplo.manifest `0.10.0`/`20a91451` — MATCH | — | `mise use taplo@0.10.0` (already current) |
| rumdl | core | 0.2.62 | **0.2.69** | BEHIND (7 patch — largest mise gap) | yes `[tool.rumdl]` | rumdl.manifest `v0.2.62`/`96c85204` — MATCH | — | `mise use rumdl@0.2.69` |
| biome | core | 2.5.11 | 2.5.12 | BEHIND (1 patch) | no | biome.manifest `@biomejs/biome@2.5.11`/`4d9c1d53` — MATCH | build=defer | `mise use biome@2.5.12` |
| gitleaks | core | 8.30.1 | 8.30.1 | CURRENT | no | gitleaks.manifest `v8.30.1`/`83d9cd68` — MATCH | — | `mise use gitleaks@8.30.1` (already current) |
| github:kenn-io/agentsview | github | 0.41.1 | 0.42.0 | BEHIND (1 minor) | no `[tool.*]` (see §2) | **NO manifest — deliberate**, mise.toml comment: capacity/risk (`kb-build` red, graph 736/1024 MiB at adoption) | — | `mise use github:kenn-io/agentsview@0.42.0` |
| github:agent-sh/agnix | github | 0.52.1 | 0.52.2 | BEHIND (1 patch) | yes `[tool.agnix]` | agnix.manifest `v0.52.1`/`d18c0a88` — MATCH | — | `mise use github:agent-sh/agnix@0.52.2` |
| fnox | core | 1.34.1 | **1.35.1** | BEHIND (1 minor) — `ls-remote` returned exactly 1 line, cross-armed via `mise latest fnox` (agrees) AND `gh api repos/jdx/fnox/releases/latest` (agrees: `v1.35.1`) | yes `[tool.fnox]` | fnox.manifest `v1.34.1`/`bfce41f1` — MATCH | — | `mise use fnox@1.35.1` |
| doppler | core | 3.76.5 | 3.76.5 | CURRENT | yes `[tool.doppler]` | doppler.manifest `3.76.5`/`a8671b86` — MATCH | — | `mise use doppler@3.76.5` (already current) |
| gh | core | 2.98.0 | 2.100.0 | BEHIND (2 minor) | no | gh.manifest `v2.98.0`/`a255baf7` — MATCH | — | `mise use gh@2.100.0` |
| npm:@openai/codex | npm | 0.153.4 | 0.153.4 | CURRENT — cross-armed via `curl registry.npmjs.org/@openai/codex/latest` (agrees exactly) | yes `[tool.codex]` | codex.manifest `rust-v0.153.4`/`3d2ee51c` — MATCH (accounts for `rust-v` prefix) | build=skip | `mise use npm:@openai/codex@0.153.4` (already current) |
| antigravity-cli | core | 1.1.25 | 1.1.28 | BEHIND (3 patch) | yes `[tool.antigravity-cli]` | antigravity-cli.manifest `1.1.25`/`7e1316ca` — MATCH | — | `mise use antigravity-cli@1.1.28` |
| npm:ctx7 | npm | 0.5.9 | 0.5.11 | BEHIND (2 patch) | yes `[tool.ctx7]` | ctx7.manifest `ctx7@0.5.9`/`0ff958c9` — MATCH | — | `mise use npm:ctx7@0.5.11` |
| npm:firecrawl-cli | npm | 1.23.3 | 1.23.3 | CURRENT | yes `[tool.firecrawl-cli]` | firecrawl-cli.manifest **`ref = v1.23.1`** — STALE, 2 patches behind the PIN itself | — | already current; MANIFEST needs re-pin to 1.23.3 |
| conda:coreutils | conda | 9.11 | 9.11 | CURRENT | yes `[tool.coreutils]` (no `sources/coreutils.manifest`; no reason documented — gap) | no manifest | — | `mise use conda:coreutils@9.11` (already current) |
| lychee | core | 0.24.2 | 0.24.2 | CURRENT | yes `[tool.lychee]`, explicitly documents no manifest ("a 40 MB Rust clone is a corpus decision, not a pin decision") | no manifest (documented) | — | `mise use lychee@0.24.2` (already current) |

**mise.toml `min_version`** (line 40): `{ hard = "2026.9.0", soft = "2026.9.0" }`. Self-managed — no `mise_key`, bumped via `mise config set min_version.hard <v>` per the standing rule, but see §3: nothing in this repo's code actually calls that command today.

**Self-updater drift — quoted verbatim from `mise run kb-currency-check` (bound 120s, run once this session), not re-derived:**
```
[currency]   claude-code: version — claude on PATH is 2.1.266 but the reviewed version is 2.1.258 — it self-updated.
[currency]   claude-code: manifest — sources/claude-code.manifest pins v2.1.258 but the running version is 2.1.266
[currency]   mise: version — mise on PATH is 2026.9.3 but the reviewed version is 2026.9.0 — it self-updated.
[currency]   mise: manifest — sources/mise.manifest pins v2026.9.0 but the running version is 2026.9.3
[currency] NOT CHECKED against upstream (not a pass): skillopt — pin is a VCS SHA vs recorded 'v0.2.0', comparison UNKNOWN
[graph] corpus inputs changed since the graph was built — run `mise run kb-build`:
  sources/antigravity-cli.manifest, sources/codex-docs.manifest, sources/codex.manifest (content changed)
```
So **mise itself** (the tool every task in this repo runs through) is currently 2026.9.3 on PATH against a reviewed/manifest-pinned 2026.9.0 — a live, self-inflicted drift on top of everything in the table above. Both `claude-code` and `mise` are self-managed with **no `mise_key`**, so neither `currency.apply` nor `kb-tool-sync` can write their pin at all (see §2/§3, and open issue **#701**).

### 1b. `pyproject.toml` — `[project] dependencies`, `[project.optional-dependencies]`, `[dependency-groups]`, `[tool.uv.sources]`

"Locked" = `uv.lock`'s resolved `version` for that package this session (`awk` over `uv.lock`, local, no network).

| dep | file/table | pin shape | pinned/locked | latest | behind? | currency.toml? | manifest? | owning-tool bump command |
|---|---|---|---|---|---|---|---|---|
| anthropic | `[project]` | floor `>=1.0.0` | **locked 1.3.0** | PyPI 1.4.0 | BEHIND (1 minor, floor technically satisfied) | no | anthropic-sdk-python.manifest `v1.3.0`/`370ee927` — a CORPUS source for the SDK repo, tracked independently of the pip floor; matches the locked version coincidentally, not causally | `uv lock --upgrade-package anthropic` (floor already satisfied; nothing to edit in pyproject unless raising the floor) |
| graphifyy | `[project]` + `[tool.uv.sources]` | exact `==0.9.53`, git rev `157a957e` | 0.9.53 | fork — **another agent covers this pin's currency** per task instructions | — | — | graphify.manifest `kb-pin/openai-cli-backend-v0.9.53`/`157a957e` — MATCH (exact rev) | `uv add "graphifyy[all]" --git https://github.com/ray-manaloto/graphify --rev <new-sha>` |
| httpx2 | `[project]` | floor `>=2.12.0` | locked 2.12.0 | PyPI 2.12.0 | CURRENT (at floor) | no | **NO manifest** (pure pip dep, no corpus source) | `uv lock --upgrade-package httpx2` |
| msgspec | `[project]` | exact `==0.21.1` | 0.21.1 | PyPI 0.21.1 | CURRENT | no | msgspec.manifest **`ref = main`** (tracks branch HEAD, not a version tag) `593ec549` | `uv add "msgspec==0.21.1"` (already current) |
| skillopt | `[project]` | git rev `93bdf3d7` (exact commit, deliberate — see pyproject comment) | 93bdf3d7 (lockfile `version` field reads `0.2.0`, its last tag) | main HEAD = `79124b37` (2026-09-05) — **54 commits ahead** (`gh api .../compare/93bdf3d7...main` → `ahead_by: 54`) | BEHIND main by 54 commits, but **DELIBERATELY HELD**: pyproject.toml quote: *"its current public surface is 180 commits past the still-current 0.2.0 release, so only the reviewed VCS SHA can identify it; the contract below rejects any other origin or revision"* | yes `[tool.skillopt]` | skillopt.manifest `ref=main`/`93bdf3d7` — matches pin exactly | `uv add skillopt --git https://github.com/microsoft/SkillOpt --rev <new-sha>` (only after a fresh review, per the held-pin rationale) |
| structlog | `[project]` | floor `>=26.1` | locked 26.1.0 | PyPI 26.1.0 | CURRENT (at floor) | no | structlog.manifest `ref=main` — plan's own findings.md flags this manifest as STALE prose ("research candidates… not tools this repo runs" while it is now a first-level dep) | `uv lock --upgrade-package structlog` |
| trafilatura | `[project.optional-dependencies].fetch` (floor `>=2.0`) + `dev` group (exact `==2.2.0`) | dual | 2.2.0 | PyPI 2.2.0 | CURRENT | no | trafilatura.manifest `v2.2.0`/`c1bc9531` — MATCH | `uv add --optional fetch "trafilatura>=2.0"` (floor) is already satisfied; dev pin already current |
| ruff | `dev` group | exact `==0.16.5` | 0.16.5 | PyPI 0.16.6 | BEHIND (1 patch) | yes `[tool.ruff]` | ruff.manifest `0.16.5`/`9e4938c4` — MATCH, build=defer | `uv add --group dev "ruff==0.16.6"` |
| ty | `dev` group | exact `==0.0.77` | 0.0.77 | PyPI 0.0.79 | BEHIND (2 patch, pre-1.0) | yes `[tool.ty]` | ty.manifest `0.0.77`/`371111b4` — MATCH | `uv add --group dev "ty==0.0.79"` |
| pytest | `dev` group | exact `==9.1.1` | 9.1.1 | PyPI 9.1.1 | CURRENT | no | pytest.manifest `ref=main` | `uv add --group dev "pytest==9.1.1"` (already current) |
| pytest-xdist | `dev` group | exact `==3.8.0` | 3.8.0 | PyPI 3.8.0 | CURRENT | no | pytest-xdist.manifest `ref=master` | already current |
| mcp2cli | `dev` group | exact `==3.7.0` | 3.7.0 | PyPI 3.7.0 | CURRENT | no | mcp2cli.manifest `ref=main` | already current |
| datamodel-code-generator | `codegen` group | exact `[protobuf]==0.76.0` | 0.76.0 | PyPI **0.77.0** | BEHIND (1 minor) | yes `[tool.datamodel-code-generator]` | datamodel-code-generator.manifest `0.76.0`/`1e422243` — MATCH | `uv add --group codegen "datamodel-code-generator[protobuf]==0.77.0"` |

**Tally:** mise.toml — 21 tools, **11 behind** (uv, hk, typos, rumdl, biome, agentsview, agnix, fnox, gh, antigravity-cli, ctx7), 10 current. pyproject.toml — 12 first-level deps (excluding graphifyy, covered elsewhere), **4 behind** (anthropic, ruff, ty, datamodel-code-generator), 1 deliberately held far behind (skillopt), 7 current. Plus the two self-updaters (mise, claude-code) drifted ABOVE their reviewed pin with **no bump path at all** (§2/§3).

## 2. Manifests without a first-level pin, and pins without a manifest

`ls sources/*.manifest | wc -l` → **97** manifests total this session (not a round
number quoted from memory — counted fresh).

**Pins with NO manifest at all (4):**
- `lychee` — documented (`[tool.lychee]`: *"No source manifest yet… a 40 MB Rust
  clone is a corpus decision, not a pin decision"*), pinned at latest at adoption.
- `conda:coreutils` — **no documented reason found** in currency.toml's
  `[tool.coreutils]` block or mise.toml; this is a gap, distinct from lychee's.
- `httpx2` — pure PyPI runtime dep, never had a corpus-source rationale (not
  flagged as deliberate anywhere read this session).
- `python` — the language runtime; not a graphify source by nature, no gap.
- `github:kenn-io/agentsview` — **documented** deliberate exclusion in the
  mise.toml pin comment itself (capacity: `kb-build` was RED and the graph sat
  736/1024 MiB at adoption time, 2026-09-01).

This matches (independently, not copied from) the prior design round's own
`manifest-dependency-map.md` finding (§4 below): **4 pinned dependencies have no
manifest: lychee, conda:coreutils, httpx2, python** — same four, same count,
different session. `agentsview` came later and wasn't in that count.

**Manifests that correspond to a pinned tool vs. pure corpus sources:** of 97
manifests, this session correlated **29** to a first-level pin (21 mise.toml
tools minus the 1 with-no-manifest agentsview, plus 12 pyproject.toml deps minus
httpx2, plus graphifyy = 21-1+12-1+1... — concretely: uv, hk, pkl, typos, ffmpeg,
taplo, rumdl, biome, gitleaks, agnix, fnox, doppler, gh, codex, antigravity-cli,
ctx7, firecrawl-cli, graphifyy, msgspec, skillopt, structlog, trafilatura, ruff,
ty, pytest, pytest-xdist, mcp2cli, datamodel-code-generator = **28**, plus
`claude-code` tracked as a self-updater rather than a mise/pyproject pin = **29**
manifest names accounted for). The other **~68** are pure corpus sources with no
first-level-pin correlation (research repos, competing tools, plugin repos,
docs mirrors, etc.) — e.g. `anthropic-sdk-python` and `claude-agent-sdk-python`
are corpus sources ABOUT the Anthropic/Claude SDKs, not the mechanism that
installs the `anthropic` pip package (that comes from PyPI via the plain
`>=1.0.0` floor; the manifest's `v1.3.0` pin is independent and happens to be
one minor behind PyPI-latest and exactly at the locked version — coincidence,
not linkage). This ~29/68 split is close to, but not identical to, the prior
round's A/B/C partition (35/50/12, see §4) — expected, since manifests have been
added and removed since 2026-08-31 and the two counts used different criteria
("first-level pin" here vs. "dependency-shaped" there).

**Ref/commit MISMATCHES found (manifest lags the mise.toml/pyproject pin it
should track) — this is the same recurring defect class the prior round already
named "a finding is a sample of a class" (§4):**

| manifest | manifest `ref` | actual pin | gap |
|---|---|---|---|
| `pkl.manifest` | `0.32.0` | mise.toml `pkl = "0.32.1"` | **1 patch behind the PIN**, even though the pin itself is current vs upstream |
| `firecrawl-cli.manifest` | `v1.23.1` | mise.toml `"npm:firecrawl-cli" = "1.23.3"` | **2 patches behind the PIN**, even though the pin itself is current vs upstream |

Both are live instances of `do-not.md`'s own invariant ("a tool bump must
advance its manifest in the same commit") being violated in the past — the pin
moved and the manifest did not follow, for two different tools, independently
of each other. No ref/commit mismatches found among the other 27 correlated
manifests checked this session (`msgspec`/`structlog`/`pytest`/`pytest-xdist`/
`mcp2cli` intentionally track `main`/`master` rather than a version tag, so
"mismatch" does not apply to them the same way — see §1b).

## 3. The bump machinery that ALREADY EXISTS — do not reinvent it

### Tasks (`mise.toml`, grep + read)

- **`[tasks.kb-build]`** (`run = "uv run kb-setup build"`, `timeout = "180m"`) —
  clones every `sources/*.manifest` at its PINNED sha (free, no LLM, AST-only),
  replays committed doc chunks. Deliberately has NO mise task-cache: a cache hit
  would skip the re-clone that proves reproducibility, and would launder a
  build that never ran into `.currency-stamp.json`. Logic in `kb_setup.graph`.
- **`[tasks.kb-update]`** (`run = "uv run kb-setup update"`) — "Advance a source
  to latest upstream + incrementally re-extract: `mise run kb-update -- <name>`".
  **Read `graph.py:3448` (`update()`) and `manifest.py:231` (`latest_commit()`)
  directly — this is the single most load-bearing finding in this section:**
  `latest_commit` does `_resolve_ref(m.url, m.ref, tags=False)` — it re-resolves
  the manifest's OWN CURRENT `ref` string to upstream HEAD. It does **not**
  discover a newer tag. For a `ref = "main"`/`"master"` source (msgspec,
  structlog, pytest, pytest-xdist, mcp2cli) this genuinely advances the pin to
  new commits. For a `ref = "v0.32.0"`-shaped source (pkl, uv, hk, ruff, ty,
  rumdl, biome, gitleaks, agnix, fnox, doppler, gh, codex, antigravity-cli,
  ctx7, firecrawl-cli, datamodel-code-generator, taplo, typos) it is a **no-op**
  — re-resolving `v0.32.0` returns the same commit every time, because the tag
  doesn't move. **`kb-update` cannot bump a version-tag-pinned tool to a NEW
  version at all.** Something else has to first rewrite the manifest's `ref =`
  line to the new tag before `kb-update` (or a plain `kb-build`) means anything
  for those tools. That "something else" is `currency.apply` (below) — for the
  ~29 tools it can reach — or a human, for the rest.
- **`[tasks.kb-watch]`** (`run = "uv run kb-setup watch"`) — one-shot
  recomposition of THIS repo's own code into the aggregate graph (AST-only,
  free); explicitly NOT a watcher despite the inherited name from `graphify
  watch`, which only rebuilds a scoped sub-graph. Logic in
  `kb_setup.graph.refresh_self`.
- **`[tasks.kb-currency-check]`** (`run = "uv run kb-setup currency check"`) —
  step 1 only: offline, ~10ms, silent when clean, ALWAYS exits 0. Logic in
  `kb_setup.currency.sync`.
- **`[tasks.kb-currency]`** (`run = "uv run kb-setup currency run"`) — the full
  steps 1-4+6 loop; step 5 (the `AskUserQuestion` interview) is deliberately
  NOT here — "only the model can ask, so it can never live in a hook or a
  task" — it lives in the `tool-currency` skill instead. **Always exits 0**;
  "an out-of-date tool is a signal, not a failure", so it can never be a CI
  gate. Logic in `kb_setup.currency.run`.
- **`[tasks.kb-tool-sync]`** (`run = "uv run kb-setup tool-sync"`) — "Lock,
  install, and verify one eligible reviewed mise-only tool pin." **This is the
  ONLY task in the repo that shells out to real `mise lock`/`mise install`**
  (`tool_sync.py:281,360,368`) rather than hand-editing text. But per open issue
  **#314** (still OPEN), `tool_sync.eligible_tools(Path('.'))` returns exactly
  **`('ffmpeg',)`** — ONE of the ~29 candidate tools. Five manifest-bearing tools
  (`codex`, `doppler`, `fnox`, `hk`, `uv`) are explicitly refused at
  `tool_sync.py:181` (*"manifest-bearing tools require the separate provenance
  workflow"* — that workflow **does not exist yet**); four more (`mise`, `ruff`,
  `ty`, `claude-code`) are refused because they are self-managed/pyproject-
  pinned and would compare pinned-against-pinned forever
  (`currency/config.py:126-138`). **Net effect: today, nothing in this repo can
  atomically move a manifest-bearing tool's pin AND its manifest AND its
  `mise.lock` entry together, for any tool except ffmpeg** (which is already
  current, so the one working case never actually needs to run).
- **`[tasks.kb-skill-refresh]`** — regenerates `.claude/skills/graphify/**` from
  the PINNED graphify (never hand-copy) and repairs 3 files the installer
  regresses every run (`.claude/settings.json`, root `CLAUDE.md`,
  `.claude/CLAUDE.md`) plus restores local `ADDENDA`. Refuses to run on a
  graphify that disagrees with the pin. Logic in `kb_setup.currency.skill`.

### `currency.apply` — step 2's "and update" (`python/src/kb_setup/currency/apply.py`)

Docstring: *"The engine EDITS two things and returns what changed: the
`mise.toml` pin and, if the tool has one, its source manifest (`ref` → the new
tag, `commit` → that tag's SHA). It does NOT open the PR."* Three invariants:
**G7** — only a verdict with `auto_apply=True` (all six gates, below) may be
applied, re-checked and refused otherwise (fails closed). **G8** — "committable
parts only": the graph is NOT rebuilt (`kb-build` runs separately, locally).
**H4** — session-only, called only from the `tool-currency` skill (human-driven);
the daily/session check never applies anything.

**`set_pin_version` (`apply.py:72-91`) is a deliberate targeted TEXT edit — NOT
`mise use` and NOT a tomllib round-trip.** Quoted verbatim, because it
contradicts the "pins are bumped by their owning tool" framing directly: *"`mise
use` INSTALLS as it edits (verified 2026-07-24: it failed to install a
not-yet-released version and left the file untouched), which couples the pin
edit to a successful install and breaks G8's 'committable parts only, rebuild is
separate'. A tomllib round-trip would drop comments and reformat the whole
file."* So it regex-replaces only the version token on the matching line,
preserving every comment (mise.toml's comments are load-bearing prose in this
repo, not decoration). **This is a real, measured, currently-load-bearing
reason the existing engine does NOT shell to `mise use`** — any round that
"fixes" this to match the owning-tool rule literally needs to either accept
losing comments/coupling-to-install, or keep the text-edit approach and update
the rule's wording instead of the code.

**`apply.py` cannot touch a self-managed pin at all**: `mise` and `claude-code`
have no `mise_key` (`ToolSpec(mise).mise_key` is empty), and `apply.py:186-201`
refuses them outright — this is tracked as open issue **#701** ("A self-managed
tool has no bump path at all: mise is reachable by neither currency apply nor
kb-tool-sync"). It is why the mise self-drift quoted in §1a (2026.9.0 pinned vs
2026.9.3 running) cannot currently be closed by any automation in this repo.

**`apply.py` also cannot bump a pyproject-pinned tool** — the prior design
round's `task_plan.md:2300` records this as *"pre-existing, CONFIRMED live
today"*: hit live on ruff+ty, `rc=2`, "the `mise --tool X apply` token is
discarded". Matches this session's independent grep finding: **0 hits** for
`["uv", "add", ...]` or any `upgrade-package` invocation anywhere in
`python/src/kb_setup/` (control arm: `["uv", "run", ...]` returns 5 hits in the
same tree, so the grep methodology is not silently broken). The only
`uv add`-adjacent code found is in `currency/sync.py:1463,1519` — PROSE
describing what `uv add` leaves behind (a lockfile/pyproject consistency check
the engine uses to detect a HAND edit), never a call that runs it.

**Net for pyproject.toml-side tools (ruff, ty, pytest, pytest-xdist, mcp2cli,
datamodel-code-generator, trafilatura, msgspec, structlog, skillopt, anthropic,
httpx2, graphifyy): there is no automated bump path today, full stop.** Every
`uv add`/`uv lock --upgrade-package` in the §1b table above is this session's
proposal of what the owning-tool command WOULD be, not something that exists.

### The six gates (`currency/decide.py:45-57`, verbatim)

```
GATE_READABLE = "versions are readable and move forward"
GATE_RELEASE  = "latest version has a readable GitHub release"
GATE_MARKERS  = "no breaking/removal/deprecation marker"
GATE_EXTRAS   = "extras unchanged"
GATE_ISSUES   = "no tracked issue moved"
GATE_SYNC     = "step 1 currently green"
```
A bump self-applies only when ALL SIX pass; fails closed on anything unreadable.
A SEVENTH gate ("patch-level bump") existed here until **2026-09-03**, when Ray
removed it verbatim: *"we always want to be on the [latest]..."* (file
truncated at the point read) — confirmed independently via the prior design
round's `task_plan.md:2740`: *"gate 1 was patch-level... FIXED in `217b3537`;
gate 1 removed."* Two near-misses the removal almost introduced, both measured
and closed: `_has_upgrade("1.0.5","1.0.2")` was `True` (a downgrade would have
self-applied) and `same_release("main","feature-x")` was `False` (two
non-versions would too) — `GATE_READABLE` (formerly a size/patch test) is what
now catches both.

**🔴 Found this session, not previously flagged in either §1 finding above:
NOTHING in the six-gate bundle reads `mise.lock` or verifies it converges.**
This matches the prior design round's own finding (`#638` §2.1, quoted in §4
below): a bump can go 6/6 (7/7 before the gate-1 removal) green over a
lockfile still holding the OLD per-platform checksums, because `mise ls
--current` and the currency engine both read `mise.toml`, never `mise.lock`.
`kb-tool-sync` is the only path that runs `mise lock` at all, and (per above)
it is eligible for exactly one tool. **A `currency.apply` bump today can leave
`mise.lock` silently stale for 28 of 29 tools it can otherwise reach.**

### `tool-currency` skill (`.claude/skills/tool-currency/SKILL.md`, first 80 lines)

Six steps, engine owns 1-4+6, the skill (human-driven) owns step 5 because only
the model can call `AskUserQuestion`. `mise run kb-currency -- --json` runs the
full loop and writes `docs/currency/`; `mise run kb-currency-check` is the fast
offline step-1-only path. Verdict shapes: `auto_apply: true` → proceed;
`ambiguities: [...]` → stop and ask (each carries `question`/`detail`/
`recommendation`); `feature_review: [...]` → advisory, never blocking, surfaced
even on a clean auto-apply; `tracked: false` → presence-only tool (ffmpeg),
"latest UNKNOWN" is expected. Step 4 (apply) used to read "a **patch** bump"
before the 2026-09-03 gate-1 removal — the file's own text flags this as the
line that changed.

### Summary answer to "does bump machinery already exist?"

**Partially, and unevenly.** The READ side (steps 1-4: is it in sync, what's
latest, release notes, tracked issues) is solid and shared engine code
(`kb_setup.currency`). The WRITE side is split into two disconnected paths that
together cover a minority of the 33 first-level pins:
1. `currency.apply` — text-edits `mise.toml` + manifest for tools WITH a
   `mise_key`, gated by 6 gates, human-driven, does NOT touch `mise.lock` and
   does NOT touch pyproject.toml.
2. `kb-tool-sync` — the only path that runs real `mise lock`/`mise install`,
   eligible for 1 of ~29 candidate tools today (#314 open).
Neither path exists for the 12 pyproject.toml-pinned deps, and neither path
can move a self-managed pin (`mise`, `claude-code` — #701 open). A round that
builds a "universal bump" without reading `apply.py:72-91`'s measured reason
for avoiding `mise use`, and without reading #314's exact refusal line, will
very likely re-derive both the wrong way and re-break something already fixed
once (the `mise use` install-coupling bug from 2026-07-24).

## 4. The prior design: "zero-token dependency upgrade protocol" — do not reinvent

**A large, live `planning-with-files` plan already exists and is the ACTIVE
plan** (`.planning/.active_plan` points at it): `.planning/2026-08-30-upgrade-
protocol-spec/` — `task_plan.md` is **198,122 bytes**, `findings.md` 20,952
bytes, last touched 2026-09-03. This is not a stale abandoned design; per this
session's own MEMORY.md the same slug's phase letters (U-R3, U-R9, Phase U) are
still the active work as of 2026-09-09. Below is what it already settled, sourced from `gh issue view 637/638`, `gh issue list`, and targeted greps of the plan
files (NOT a full read of the 198KB file).

**PR #637** (`chore/cli-currency-sweep`, MERGED) already bumped: `uv 0.12.5→
0.12.7`, `rumdl 0.2.60→0.2.62`, `biome 2.5.10→2.5.11`, `fnox 1.34.0→1.34.1`,
`npm:ctx7 0.5.8→0.5.9`, `min_version 2026.8.10→2026.8.14`. **All of those have
since drifted behind AGAIN** (this session's §1a: uv now 3 patches behind,
rumdl 7, biome 1, fnox 1, ctx7 2, min_version now 2026.9.0 after further
bumps) — upstream releases kept shipping after the sweep landed; this is
expected, not a sign the sweep failed. A later round (per `.planning/…
task_plan.md:2285`) also landed "Status: complete — LANDED… Ten first-level
deps bumped" — again, since superseded by new upstream releases by the time of
THIS session's measurements.

**Issue #638** ("Session kb-20260830.001: the full record") is the design
record — 17,589 chars, read in full this session. Key decisions from three
`/grilling` rounds (Ray's answers, verbatim, quoted in the issue):
- Engine: **DBOS-SQLite** (`dbos-transact-py`, SQLite support verified via a
  real merged PR — see caveat below).
- Latest-is-agent-decision: **auto** (upgrade blindly, let gates catch it).
- Atomicity: **commit-per-dependency**.
- Scope: **mise-tools + pyproject-direct ONLY** — Ray explicitly rejected
  tracking transitive deps ("if we want a transitive dependency to be a
  currency, then just make it a first level dependency") and asked which
  `sources/*.manifest` entries do NOT map to a dependency.
- `currency.toml`: **rewrite** per Ray, but `fable-advisor`'s architecture
  verdict in the SAME issue overrode this: rewriting `currency.toml` (Q11)
  contradicts DB-as-truth (Q8) and "reduce config files" (free-form) — **verdict:
  DELETE currency.toml, do not rewrite it; judgment becomes DB columns; a
  read-only `kb-currency-export` can regenerate a TOML view for humans.**
- Manifests: **all-generated** — all 97 manifests brought under the protocol.
- Proposed architecture (fable-advisor): `kb_setup.deps` — one SQLite DB
  populated from `mise.toml`+`pyproject.toml`+the 97 manifests (those files
  stay the VERSION truth; DB owns status/mapping only) + a `kb-upgrade` mise
  task (per-dep bump → gates → auto-revert on red → commit; batch → one PR via
  `kb-ship`) + DBOS "confined to one module, ship it as plain functions DBOS
  merely decorates" (Ray's own words on keeping the DBOS bet cheap to reverse).
  Two tables sketched: `dep(name PK, kind, pin, latest, note, tag_prefix,
  probes_json)` and `dep_stage(dep FK, stage {outdated, bumped, gated,
  source_synced, deep_extraction, reflection, artifacts}, state {pending,
  running, ok, failed, reverted, skipped_tokens}, ts, evidence)`.
- **MVP slice 1** (explicitly scoped down from the full design): two tables +
  populate + `kb-upgrade` with token-consuming stages hard-recorded
  `skipped_tokens`, **plus "a gate that reads whether `mise.lock` advanced"**
  — i.e. the exact gap this session independently re-found in §3 was already
  named as a required MVP gate. NOT in slice 1: currency deletion/generation,
  deep extraction, artifacts, DBOS recovery testing.
- Findings that motivate the DB-over-files design: only **1 of 75(→85, see
  below) mise tasks** names an LLM backend at all — meaning a fully zero-token
  bump-everything pipeline is achievable today; the only token-consuming stage
  in the whole corpus lifecycle is semantic/deep extraction. **48 files/
  families are hand-maintained** with per-dependency facts (23 of them dead
  JSON files in `docs/currency/` — see caveat below); the graphify fork SHA
  lives in 4 tracked files reconciled by 6 `ref_binding` rows; `currency.toml`
  has 22 readers.
- `manifest-dependency-map.md` partitioned all 97 manifests: **A=35 map to a
  pinned dependency, B=50 dependency-shaped but not pinned, C=12 not a
  dependency at all** — so only 12% (not the ~81% Ray's free-form question
  implied) fail the "does this cleanly map to a dependency" test. **4 pinned
  deps have no manifest: lychee, conda:coreutils, httpx2, python** — this
  session's §2 independently found the SAME four, by a different method.

**🔴 CRITICAL CAVEAT — #638's own successor session re-verified it and found it
substantially wrong.** `findings.md` (same plan dir, dated 2026-08-30 session
`kb-20260830.003`, which #638 itself assigned as the mandatory next step):
*"5 of #638's 7 'measured' claims are refuted, 3 more unverifiable."* Specific
corrections on record: **85 mise tasks, not 75**; baseline behind on **8**
tools, not 5; **6** piped-gate violations, not 4; **#638 cited a merged DBOS
PR that does not exist** (it named a closed *issue* #101 as a merged PR — the
real merged PR is **#680**; the underlying SQLite-support fact held, the
citation was fabricated); the **agentsview tool-call-schema blocker #638 called
"UNVERIFIED and load-bearing" was RESOLVED** the same round (v0.41.1 docs
confirm full bash command capture); and **the 23 JSON files #638's MVP slice
says to delete are NOT dead** — they hold reviewed findings/baselines/
fingerprints, so that specific MVP instruction rests on a wrong premise as
written. Treat every number pulled from #638 above as a LEAD, not settled fact,
unless cross-checked — exactly as its own follow-up concluded.

**Open, unresolved, and directly on-point for this round:**
- **#636** — OPEN. Umbrella: "make every tool upgrade scoped, validated, and
  pipeline-typed." Links ten prior-art issues (includes #634, #635, #314,
  #701 per this session's cross-reference).
- **#634** — OPEN. `mise.lock` carries an orphaned `aqua:openai/codex` entry at
  a stale version that blocks `_lock_converged` (`tool_sync.py:277`) for ANY
  future tool-sync bump — a live landmine for whichever tool gets promoted
  into `kb-tool-sync`'s eligible set next.
- **#635** — OPEN. `kb-gates` writes top-level `dirty: null` while every
  per-gate row says `false` — an evidence-quality bug in the gate artifact the
  MVP's "does mise.lock advance" gate would presumably build on.
- **#314** — OPEN. `kb-tool-sync` covers 1 of 12 (now effectively ~29) tools;
  the "separate provenance workflow" for manifest-bearing tools it names as
  missing is exactly what this round is being asked to inventory toward.
- **#701** — OPEN. Self-managed tools (`mise`, `claude-code`) have no bump path
  in either mechanism — directly explains this session's §1a mise/claude-code
  drift with no available fix task.
- **Process failures the design round logged against itself** (§9 of #638,
  worth inheriting as a checklist rather than repeating): piped `mise run
  kb-gates | tail` 4×; 0-of-3 greps carried a control arm; **hand-wrote
  throwaway JSON/TOML parsers instead of using this repo's own `kb-codegen` /
  `[tool.datamodel-codegen]` machinery, and two of them returned FALSE
  ANSWERS** (a `mise.lock` platform parser reported `0→0`, a `uv tree` parser
  reported "0 outdated" when 23 packages were behind) — both plausible zeros,
  caught only because a control arm was run.

**Net for this round:** the architecture question (DBOS-SQLite, two tables,
delete currency.toml, mise-tools+pyproject-direct scope, commit-per-dep,
auto-apply-and-let-gates-catch-it) is Ray-decided and fable-advisor-reviewed
already. What is NOT settled: Q9 (single source of truth for the version
itself — architect's inference, "stated to Ray and not contradicted, but also
not confirmed") and Q10 (do the 23 state files move into the DB — unanswered,
and the very next session showed 23 of them are NOT dead weight). The assigned
next step from #638 itself — a codex-lane re-verification BEFORE `/to-spec` —
has been partially done (`findings.md` above) but §4's own text says the
expected outcome is "probably triggers another `/grilling` round before
`/to-spec`", and nothing found this session shows that round has happened yet.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo itself; every file/task/module cited above, plus issues #637 #638 #636 #634 #635 #314 #701.
- [jdx/mise](https://github.com/jdx/mise) — pinned self-managed tool; `mise ls-remote`d for 16 of the 21 `[tools]` entries; manifest read.
- [astral-sh/uv](https://github.com/astral-sh/uv) — pinned tool; `mise ls-remote uv`; manifest read; owns `uv.lock`/`uv add` semantics discussed throughout §3.
- [jdx/hk](https://github.com/jdx/hk) — pinned tool; `mise ls-remote hk`; manifest read.
- [apple/pkl](https://github.com/apple/pkl) — pinned tool; `mise ls-remote pkl`; manifest read (found stale ref).
- [crate-ci/typos](https://github.com/crate-ci/typos) — pinned tool; `mise ls-remote typos`; manifest read.
- [FFmpeg/FFmpeg](https://github.com/FFmpeg/FFmpeg) — pinned tool (conda backend); `mise ls-remote conda:ffmpeg`; manifest read.
- [tamasfe/taplo](https://github.com/tamasfe/taplo) — pinned tool; `mise ls-remote taplo`; manifest read.
- [rvben/rumdl](https://github.com/rvben/rumdl) — pinned tool; `mise ls-remote rumdl`; manifest read (largest drift found, 7 patches).
- [biomejs/biome](https://github.com/biomejs/biome) — pinned tool; `mise ls-remote biome`; manifest read.
- [gitleaks/gitleaks](https://github.com/gitleaks/gitleaks) — pinned tool; `mise ls-remote gitleaks`; manifest read.
- [kenn-io/agentsview](https://github.com/kenn-io/agentsview) — pinned tool (github backend, deliberately no manifest); `mise ls-remote github:kenn-io/agentsview`.
- [agent-sh/agnix](https://github.com/agent-sh/agnix) — pinned tool (github backend); `mise ls-remote github:agent-sh/agnix`; manifest read.
- [jdx/fnox](https://github.com/jdx/fnox) — pinned tool; `mise ls-remote`/`mise latest` (both returned a surprising 1-line list) cross-armed via `gh api repos/jdx/fnox/releases/latest`; manifest read.
- [DopplerHQ/cli](https://github.com/DopplerHQ/cli) — pinned tool; `mise ls-remote doppler`; manifest read.
- [cli/cli](https://github.com/cli/cli) — pinned tool (`gh`); `mise ls-remote gh`; manifest read; also the CLI used for every `gh issue view`/`gh api` call this session.
- [openai/codex](https://github.com/openai/codex) — pinned tool (npm backend); `mise ls-remote npm:@openai/codex` cross-armed via `curl registry.npmjs.org/@openai/codex/latest`; manifest read.
- [google-antigravity/antigravity-cli](https://github.com/google-antigravity/antigravity-cli) — pinned tool; `mise ls-remote antigravity-cli`; manifest read.
- [upstash/context7](https://github.com/upstash/context7) — pinned tool (`ctx7`, npm backend); `mise ls-remote npm:ctx7`; manifest read.
- [firecrawl/cli](https://github.com/firecrawl/cli) — pinned tool (`firecrawl-cli`, npm backend); `mise ls-remote npm:firecrawl-cli`; manifest read (found stale ref).
- [ray-manaloto/graphify](https://github.com/ray-manaloto/graphify) — the maintained fork pinned via `[tool.uv.sources]` git rev; manifest read; excluded from latest-version-authority per this session's own scope instructions.
- [jcrist/msgspec](https://github.com/jcrist/msgspec) — pyproject dependency; PyPI + manifest read.
- [microsoft/SkillOpt](https://github.com/microsoft/SkillOpt) — pyproject git-pinned dependency; `gh api` commit + compare endpoints to measure the deliberate 54-commit hold; manifest read.
- [hynek/structlog](https://github.com/hynek/structlog) — pyproject dependency; PyPI + manifest read.
- [adbar/trafilatura](https://github.com/adbar/trafilatura) — pyproject dependency; PyPI + manifest read.
- [astral-sh/ruff](https://github.com/astral-sh/ruff) — pyproject dev dependency; PyPI + manifest read.
- [astral-sh/ty](https://github.com/astral-sh/ty) — pyproject dev dependency; PyPI + manifest read.
- [pytest-dev/pytest](https://github.com/pytest-dev/pytest) — pyproject dev dependency; PyPI + manifest read.
- [pytest-dev/pytest-xdist](https://github.com/pytest-dev/pytest-xdist) — pyproject dev dependency; PyPI + manifest read.
- [knowsuchagency/mcp2cli](https://github.com/knowsuchagency/mcp2cli) — pyproject dev dependency; PyPI + manifest read.
- [koxudaxi/datamodel-code-generator](https://github.com/koxudaxi/datamodel-code-generator) — pyproject codegen dependency; PyPI + manifest read.
- [anthropics/anthropic-sdk-python](https://github.com/anthropics/anthropic-sdk-python) — corpus source correlated to (but independent of) the `anthropic` PyPI dep; manifest read.
- [anthropics/claude-agent-sdk-python](https://github.com/anthropics/claude-agent-sdk-python) — pure corpus source, no first-level pin; manifest read for the pin-vs-manifest cross-reference in §1b/§2.
- [anthropics/claude-code](https://github.com/anthropics/claude-code) — self-updating harness tracked via `currency.toml`/manifest, not a mise/pyproject pin; manifest read; drift confirmed via `kb-currency-check`.

---

## Correction — 2026-09-09, session `kb-20260909.007`

Appended rather than edited in place: this repo does not rewrite a research
report to tidy it, and line 385's claim should stay visible alongside what
refutes it.

**Line 385 cites dbos-transact-py PR `#680` as the merged SQLite-support PR. It
is not.** Verified directly with `gh pr view` against `dbos-inc/dbos-transact-py`:

| PR | actual title | state |
|---|---|---|
| **#680** | *Retry Serialization Errors in Datasources* | MERGED — **unrelated to SQLite** |
| **#441** | *SQLite Support* | MERGED — this is the real one |
| **#442** | *System Database URL* | MERGED — its companion |

**The underlying fact is unharmed: SQLite support is real, merged, and is the
zero-config DEFAULT** (`system_database_url` unset resolves to
`sqlite:///[app].sqlite`). Only the citation was wrong.

**The provenance of the error is the lesson.** This report inherited the wrong
number from issue **#638**, which had itself cited a *closed, unmerged issue*
(`#101`) as a merged PR. A wrong citation was corrected once — to a different
wrong citation — and the second one read as verified because it was now a real
merged PR with a plausible number. Nobody opened it until this session.

**Re-derived facts, this session, on the live index** (the report's other DBOS
numbers were not re-measured and remain as originally written):

- PyPI `dbos` **2.31.1**, MIT, `requires_python >=3.10`, and the classifiers
  **explicitly list Python 3.14** — so this repo's 3.14 pin is a declared
  supported version, not a risk. Resolved cleanly against the real 3.14.7 via a
  read-only `uv pip compile`; `pyproject.toml` was not touched.
- **6 genuinely new** packages against this repo's `uv.lock`: `dbos`, `greenlet`,
  `psycopg`, `psycopg-binary`, `sqlalchemy`, `websockets`. `psycopg-binary` is a
  ~4.6 MiB compiled wheel installed **unconditionally**, even when only SQLite is
  used.
- No mandatory server. DBOS Conductor is opt-in via `conductor_key`, absent by
  default.
- `dbos-inc/dbos-transact-py`: `has_issues=true`, **`has_discussions=false`** —
  so a Discussions search there is a structural zero and proves nothing. Control
  arm on the search that WAS used: a known-present term returned 40 hits, so the
  mechanism discriminates.

**Verdict carried forward: VIABLE WITH CONSTRAINTS.** The constraint is the
maintainers' own — their live docs say Postgres is recommended for production —
plus the unconditional psycopg pair. Neither blocks an offline single-laptop CLI.

Full re-research: `.agent/kb/reports/agents/dbos-research.md`.
