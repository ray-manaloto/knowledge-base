# mise CLI currency — 2026-07-27

Agent: `mise-currency`. Written incrementally as probes ran.

## 1. Installed version and install method

```
$ mise --version
2026.7.15 macos-arm64 (2026-07-27)

$ command /Users/rmanaloto/.local/bin/mise version
2026.7.15 macos-arm64 (2026-07-27)          # rc=0
```

**Installed: `2026.7.15`.**

Note: `which -a mise` first prints a **shell function** wrapper (the standard
`mise activate` shim function) that delegates to `command
/Users/rmanaloto/.local/bin/mise`. The version above was re-probed through the
real binary directly to bypass the function — same answer, so the function is
not masking a different binary.

Install method: **standalone binary**, not a package manager.

```
-rwxr-xr-x@ 1 rmanaloto staff 104317136 Jul 27 12:31 /Users/rmanaloto/.local/bin/mise
/Users/rmanaloto/.local/bin/mise: Mach-O 64-bit executable arm64

$ brew list mise
Error: No such keg: /opt/homebrew/Cellar/mise
```

`~/.local/bin/mise` + not-in-brew is the signature of the `mise.run` install
script / `mise self-update`. Consequence: **mise on this machine is not managed
by anything this repo controls** — it updates out-of-band, and nothing in either
repo would notice or gate a change.

Binary mtime is `Jul 27 12:31` local. The v2026.7.15 release published
`2026-07-27T18:51:46Z` (= 11:51 PDT). So the binary was laid down ~40 min after
the release went public — consistent with a self-update performed **today**.

## 2. Is mise pinned in either repo?

**No — neither repo pins mise itself.**

| Repo | File(s) checked | `mise = ` pin? |
|---|---|---|
| knowledge-base | `mise.toml` | none (rc=1) |
| dotfiles | `mise.toml`, `.config/mise/conf.d/**` | none |

**Control arm** (per `probes-need-a-control-arm.md`): the same grep shape run
for a pin known to exist returns a hit —

```
$ grep -rnE '^\s*"?hk"?\s*=' dotfiles/mise.toml dotfiles/.config/mise/
dotfiles/.config/mise/conf.d/shared.toml:31:hk = "1.52.0"
```

— so the grep discriminates. `mise` genuinely has no self-pin; the absence is
real, not a broken probe.

knowledge-base `[tools]` pins (for the record): `python=3.14.6`, `uv=0.11.28`,
`hk=1.52.0`, `pkl=0.32.0`, `typos=1.48.0`, `pipx:graphifyy=0.9.26 [all]`,
`conda:ffmpeg=8.1.2`, `taplo=0.10.0`, `rumdl=v0.2.40`, `gitleaks=8.30.1`,
`github:agent-sh/agnix=0.40.0`, `codex=0.145.0`, `antigravity-cli=1.1.5`.
mise is conspicuously not among them.

## 3. Latest released version

```
$ gh release list --repo jdx/mise --limit 40
v2026.7.15: Experimental Task Output Caching   Latest   v2026.7.15   2026-07-27T18:51:46Z
v2026.7.14: ...                                         v2026.7.14   2026-07-26T16:26:10Z
```

Cross-verified by a second route (`probes-need-a-control-arm.md` § cross-check):

```
$ gh api repos/jdx/mise/releases/latest --jq '.tag_name ...'
v2026.7.15  published=2026-07-27T18:51:46Z  prerelease=false

$ gh api 'repos/jdx/mise/releases?per_page=5'    # includes drafts + prereleases
v2026.7.15 draft=false pre=false 2026-07-27T18:51:46Z
v2026.7.14 draft=false pre=false 2026-07-26T16:26:10Z
```

Both routes agree. **Latest: `v2026.7.15`.**

(The `tags` endpoint's first page is dominated by `vfox-v2026.7.*` tags — a
*separate* tag series in the same repo for the vfox component. Those are **not**
mise CLI releases and must not be read as "mise is at 2026.7.20". This is the
one trap on this lookup; the releases API is the authority.)

## 4. Gap: releases between installed and latest

**Installed `2026.7.15` == latest `v2026.7.15`. The gap is ZERO releases.**

There is nothing to enumerate for task 3, and consequently nothing to flag for
task 4 *as a pending change*. mise on this machine is fully current, as of
2026-07-27.

This is a verified-current answer, not a could-not-check: installed version read
from the binary directly (rc=0), latest read from two independent GitHub API
routes that agree.

## 5. Recent releases already in effect (context, NOT a pending gap)

The five most recent releases all landed within the last 7 days, and the machine
self-updated **today**. So these changes are *already live* on this host and
were not necessarily live when this repo's current PATH/shim work
(branch `fix/cc-doctor-judges-session-path`) was written. Recorded here because
they bear directly on a repo that drives everything through `mise run`.

Notes read in full via `gh release view <tag> --repo jdx/mise --json body --jq .body`
(the plain `gh release view` output is ~30KB of asset listings and buries the body).

> **Numbering trap, cited:** v2026.7.11's own notes state that **2026.7.8,
> 2026.7.9 and 2026.7.10 were tagged but never published** due to a release
> pipeline issue, and their changes ship inside v2026.7.11. ([v2026.7.11]) So a
> version-count based on tags overstates the release count. Separately, the
> `tags` API's first page is all `vfox-v2026.7.*` — a different series entirely.

### 5a. BREAKING changes / PATH, shims, task-env, activation

- **[v2026.7.14] BREAKING (filed under Security).** Project-local
  `unix_default_file_shell_args`, `unix_default_inline_shell_args`,
  `windows_default_file_shell_args`, and `windows_default_inline_shell_args`
  are now **ignored** — these settings became global-only. Rationale given:
  "local config is loaded before trust evaluation, [so] an untrusted repository
  could previously influence how commands from trusted sources were executed."
  Global config and `MISE_*` env vars still apply. Reported by @arpitjain099
  ([#11293]). The release's own mitigation: set `shell` on each task.
  → **Impact here: NONE.** Neither repo sets any of the four settings
  (grepped `knowledge-base/mise.toml` and `dotfiles/mise.toml` +
  `dotfiles/.config/mise/**` — no hits). This is the single largest
  behaviour change in the window and it does not touch this stack.
- **[v2026.7.15] The migration path for the above:** new `task_config.shell`
  sets a project-scoped default shell for tasks, task-local and template
  `shell` still winning ([#11354]). Explicitly described as "a safe migration
  path after the 2026.7.14 change".
- **[v2026.7.12] Activation regression, introduced in v2026.7.11 and fixed
  here.** `mise activate zsh` **hung non-interactive login shells under
  Rosetta** — env-state snapshotting autoloaded the `zsh/parameter` module via
  `dlopen` ([#11188]). Anyone sitting exactly on v2026.7.11 is exposed; ≥7.12
  is not. This is the one genuinely dangerous version in the window.
- **[v2026.7.13] PowerShell task shells now run `-NoProfile` by default**,
  with the stated reason that "a profile that mutates `PATH` (such as a mise
  activation snippet) can no longer shadow a task's own tools and cause
  confusing 'cannot find binary path' errors" ([#11199]). Windows-only in
  effect, but the failure mode named is exactly the class this repo's
  `fix/cc-doctor-judges-session-path` branch is about — a profile-mutated PATH
  shadowing a task's intended binaries.
- **[v2026.7.13] `[env]._` directive ordering.** `_.path` / `_.file` /
  `_.source` inside a single `[env]._` block are now resolved **in written
  order**, so a `_.path` can reference a variable exported by a `_.source`
  written before it ([#11163]). This changes how a PATH built across mixed
  directives resolves.
- **[v2026.7.11] Shim recursion prevented when the directory env is filtered**
  ([#10982], shipped via the unpublished 7.8–7.10 batch).
- **[v2026.7.11] Activation perf:** the redundant initial prompt hook
  immediately after activation is now skipped for bash/zsh/fish when the
  session is unchanged, avoiding an extra `mise` process on shell startup
  ([#11130], [#11131], [#11134]).
- **[v2026.7.11] Network fail-fast on the hot path:** DNS failures are
  non-retryable, a process-local circuit breaker opens after hard
  DNS/connection failures, and "shims, shell activation, and `mise x` make one
  bounded attempt instead of grinding through full retry schedules"
  ([#11066]). Directly relevant to `long-running-command-hangs.md`.
- **[v2026.7.12] Windows exe-shim dispatch** now reports actionable "no version
  is set" guidance rather than "cannot find binary path" ([#11189]).
- **[v2026.7.15] `~/` paths expand with the platform path separator**, fixing
  mixed separators through `mise where`, shims, and related output ([#11312]).
  Windows-only in practice.

### 5b. Secrets / env-var encoding

- **[v2026.7.14] The important one.** Values loaded from structured env files
  (`env._.file` with JSON/YAML/TOML) are **literal by default again**. This
  fixes a regression where *every* value was shell-expanded when
  `env_shell_expand` was on — which "corrupted literals such as bcrypt-style
  `$6$salt$hash` **and could pull in matching process-environment values**"
  ([#11269]). Opt back into expansion with `expand = true`.
  Two distinct hazards: silent secret corruption, and secret *leakage* from the
  ambient process env into a config value.
  → **Impact here: NONE observed** — neither repo sets `env_shell_expand` nor
  uses `env._.file` (grepped; no hits).
- **[v2026.7.15] `pass_through_env` / `task_config.global_pass_through_env`**
  keep selected ambient variables "like tokens" available under `deny_env`
  **without them affecting cache keys** ([#11363]). This is the correct
  mechanism for a secret that a task needs but that must not be hashed into a
  cache key.
- **[v2026.7.12] `MISE_SAFE=1` safe mode** — a global-only `safe` setting that
  makes mise an inert config reader. Blocks (with errors) template `exec()` /
  `read_file()`, `_.source`, hooks, tasks, asdf plugin scripts, plugin
  installs; **ignores** project `[env]`, `_.path`, `_.file`, `[shell_alias]`,
  `[settings]`. Intended for CI/Renovate running `mise lock --bump` against
  untrusted branches, and it skips the trust requirement because the config is
  inert ([#11146], [#11151]).
- **[v2026.7.12] `_.file` env files now resolve references to variables defined
  in earlier files or `[env]` blocks** instead of collapsing to empty
  ([#11158]).
- **[v2026.7.12] `gpg_verify` no longer silently skips.** Node/Swift signature
  verification moved in-process (rPGP); previously a *missing* `gpg` binary
  silently skipped verification, now it always runs when enabled. Listed as a
  breaking change — opt out explicitly with `gpg_verify = false` ([#11148]).
- **[v2026.7.14] A rejected GitHub token (401) now names its source** (gh CLI,
  `github_tokens.toml`, OAuth, env var…) plus a remediation hint ([#11236]).
- **[v2026.7.12] `trusted_config_paths` now overrides the ignore list**, so a
  settings-trusted config is actually discovered and loaded ([#11152]).

### 5c. Would change how a task-driven repo is written

This is the richest category in the window, and it is all **additive/opt-in**.

- **[v2026.7.15] Experimental local task output caching** ([#11328], [#11347]).
  A task with `sources` and explicit `outputs` can restore outputs from a
  content-addressed cache instead of rerunning, replaying stdout/stderr. Cache
  keys combine source contents, task config + args, declared and allowlisted
  ambient env, resolved tools, OS, and arch. Opt-in; cache failures degrade to
  misses/warnings rather than failing the task.
- **[v2026.7.15] `outputs = []` result-only caching** for checks that produce
  no files — the notes name **"lint, test, and typecheck"** explicitly
  ([#11351]). This is the single most directly applicable feature to a repo
  whose gates are `mise run lint` / `mise run test`.
- **[v2026.7.15] Reusable + global cache inputs:** named
  `[task_config.input_groups]` referenced from `sources` as `@group:<name>`,
  plus `task_config.global_inputs` applying config-rooted patterns to every
  task in scope, "so shared lockfiles and toolchain files no longer need
  repeating per task" ([#11356]). And `task_config.global_env` for scoped
  environment inputs that participate in cache keys ([#11363]).
- **[v2026.7.15] `outputs` gain ordered `!` exclusions/re-inclusions** mirroring
  `sources`, with `\!` escaping ([#11367]).
- **[v2026.7.15] `--output` / `MISE_TASK_OUTPUT` now honour raw and interactive
  tasks** the same way `task.output` config does, "fixing mixed command/timing
  output for tasks that need inherited stdio" ([#11355]). Relevant: this repo's
  `mise.toml` already carries a comment about using `raw` because mise's
  captured output prefixes task lines with `[cc]`.
- **[v2026.7.15] Circular-dependency detection runs on the fully resolved
  graph**, so cycles through `wait_for`, `{{usage.*}}` deps, and `depends_post`
  are reported with a concrete path before any task runs — while valid
  post-dependency graphs are no longer wrongly rejected ([#11329]).
- **[v2026.7.15] `source_freshness_hash_contents = true` now skips mtime
  comparison entirely**, so tasks stop re-running on every CI job after a cache
  restore resets timestamps; output integrity moves to a content hash
  ([#11319]).
- **[v2026.7.14] Task cache correctness, two fixes that matter:** changing a
  task's `run`, `sources`, or `outputs` now **invalidates** its cached state
  (previously such edits could leave a task incorrectly skipped, [#11288]); and
  a task's source hash is now persisted **only after a successful run**, so a
  failed run no longer marks stale sources as up to date ([#11296]).
  → Both are "a gate that silently didn't run" bugs — the exact failure class
  `verify-before-advancing.md` exists to prevent.
- **[v2026.7.14] Nested git worktrees:** with a worktree checked out inside the
  main checkout, mise no longer loads the enclosing monorepo root's tasks into
  the nested root's namespace (env/tools/vars still inherit) ([#11283]).
  Relevant given this repo sits beside `../dotfiles` and uses worktrees.
- **[v2026.7.14] usage 4.0 is now required** (`min_usage_version` bumped);
  every command declares read-only / modifies-state / destructive, and shell
  completions + doc rendering now depend on usage 4.0 ([#11306]).
- **[v2026.7.13] Inline task definitions now follow a consistent first-wins
  precedence** across local, `conf.d`, and monorepo configs, so
  lower-precedence metadata no longer leaks into script tasks ([#11103]).
- **[v2026.7.11] File tasks from user-global/system configs are treated as
  global** regardless of include path, and `mise tasks info` / JSON output
  gained a `config_sources` array naming every config contributing to a task
  ([#11106], [#11098]).
- **[v2026.7.15] `mise generate task-docs --inject`** now errors clearly when
  the `<!-- mise-tasks -->` markers are missing or reversed instead of
  truncating/clobbering the target file ([#11359]).
- **[v2026.7.12] Other breaking changes** (none applicable here): `mise oci
  push --tool` removed; unreleased `npm.use_npm_view` replaced by
  `npm.shell_out`.
- **[v2026.7.11] Exact-version fast path** for cargo/npm/go/gem/**pipx**/dotnet
  backends — an exact semver request skips the remote version list entirely
  ([#11013], [#11070]). This repo pins `pipx:graphifyy = "0.9.26"`, so it is on
  that fast path.
- **[v2026.7.13] `rename_exe` accepts a table** mapping source patterns to
  target names, exposing several executables from one archive ([#11231]).
- **[v2026.7.15] `mise deps --list`** now shows inactive-but-configured
  providers with a reason instead of silently omitting them ([#11182]).
  → A "could not check is not green" fix, same spirit as this repo's currency
  engine.

## 6. Bottom line

**Is bumping advisable? There is nothing to bump.** Installed `2026.7.15` is
the latest release (`v2026.7.15`, published 2026-07-27), verified from the
binary directly and from two independent GitHub API routes that agree. Gap =
**0 releases**. No action required on the version itself.

**Does any release in the window carry risk for a wholly-`mise run`-driven
repo?** Reviewing the last five releases (all landed within 7 days, and this
host self-updated onto them *today*):

- The one **BREAKING** change that could bite a task-driven repo —
  v2026.7.14's global-only shell-arg settings — **does not apply**: neither
  repo sets any of the four settings.
- The one **dangerous** version — v2026.7.11's Rosetta zsh activation hang — is
  already behind us (fixed in v2026.7.12). Being current is what avoids it.
- The **secrets** change (v2026.7.14 literal-by-default env files) is a fix in
  the safe direction and does not apply either (no `env._.file`, no
  `env_shell_expand`).
- Everything else task-related is additive and opt-in.

So: **current, and safely current.** No behavioural change is pending against
this stack.

### Two real findings that are not version drift

1. **mise is unpinned and unmanaged.** Neither repo pins mise, and it is
   installed as a standalone `~/.local/bin/mise` binary outside brew — i.e. it
   self-updates out-of-band. This host jumped onto v2026.7.15 **today**, within
   the same day as this repo's active PATH/shim work
   (`fix/cc-doctor-judges-session-path`). A repo where *every* workflow is a
   `mise run` task has its most load-bearing dependency completely ungated:
   a future release could change task-env or PATH construction and nothing
   would notice. Note this is partly inherent — mise bootstraps the toolchain,
   so it cannot fully pin itself in `[tools]` — but it can be *tracked*.
2. **`currency.toml` does not track mise.** It has exactly two tool tables,
   `[tool.graphify]` and `[tool.ffmpeg]`. mise appears only in a comment
   ("graphify is the pilot; mise, hk, …"), i.e. it was always intended and
   never added. Adding `[tool.mise]` (source = GitHub releases `jdx/mise`,
   installed version from `mise --version`) would put mise under the same
   step-1 offline drift check that runs at every SessionStart — turning this
   whole manual investigation into a ~10ms automatic check. That is the
   concrete recommendation.

### Probe hygiene

- Installed version re-probed through the real binary (`command
  /Users/rmanaloto/.local/bin/mise version`) to bypass the `mise()` shell
  function — same answer, so the function was not masking anything.
- Latest version cross-checked via `gh release list` **and**
  `gh api .../releases/latest` **and** `gh api .../releases?per_page=5`
  (which would reveal drafts/prereleases). All three agree.
- The "no mise pin" negative was control-armed: an identically-shaped grep for
  `hk` returns `shared.toml:31:hk = "1.52.0"`, so the probe discriminates.
- **Not used as evidence:** `grep -ohE '2026\.[0-9]+\.[0-9]+'` over
  `~/.local/state/mise/mise.log` returns many version strings (2026.3.0 …
  2026.7.14), but that log records *all* tool versions mise handles, not mise's
  own version history. It cannot distinguish "mise was at 2026.7.7" from "mise
  installed something at 2026.7.7". Reported here as **UNKNOWN**: the prior
  installed mise version on this host is not determinable from the artifacts
  available.

---

# PART II — Full v2026.7.x line review (added 2026-07-27, second pass)

## Why this section exists (the framing changed)

Part I concluded "gap = 0 releases". That remains true **as of now**, and it is
the wrong question. mise is **not pinned** and self-updates from any terminal on
this machine, including ones outside this repo. Part I already recorded the
prior installed version as **UNKNOWN and unrecoverable** from available
artifacts. Therefore the honest exposure window is not "the last 5 releases" —
it is **the entire v2026.7.x line**, any member of which may have arrived
mid-work.

**13 published releases reviewed**, v2026.7.0 (2026-07-02) → v2026.7.15
(2026-07-27). All notes read as primary sources via
`gh release view <tag> --repo jdx/mise --json body,publishedAt`.

### The 7.8–7.10 question, verified rather than repeated

Part I repeated v2026.7.11's own claim that "2026.7.8 through 2026.7.10 were
tagged but never published". **That claim is partly wrong, and I verified it
rather than carrying it forward.**

| version | git tag exists? | GitHub release exists? |
|---|---|---|
| v2026.7.8 | **yes** (`refs/tags/v2026.7.8`) | no (404) |
| v2026.7.9 | **NO — never tagged at all** (404) | no (404) |
| v2026.7.10 | **yes** (`refs/tags/v2026.7.10`) | no (404) |

Authoritative route: `gh api repos/jdx/mise/git/matching-refs/tags/v2026.7.`
returns `v2026.7.0 … v2026.7.8, v2026.7.10 … v2026.7.15` — **`v2026.7.9` is
absent from the complete tag listing**, so this is not an exact-match lookup
artifact.

**Control arm:** the same `git/ref/tags/<tag>` endpoint returns real refs for
v2026.7.7, v2026.7.8, v2026.7.10 and v2026.7.11, and 404s only for v2026.7.9 —
so the probe discriminates; the negative is real.

**What became of their content:** it shipped inside **v2026.7.11**, whose notes
carry a dedicated "Also in this release: v2026.7.8–v2026.7.10" section
([v2026.7.11]). So no content was lost — but v2026.7.11 is a **double-sized
release**, and anything in it is correspondingly more likely to be the thing
that changed under us. Note the primary source is itself imprecise about 7.9;
cite the tag listing, not the release prose.

## Per-release relevance (13 releases)

| tag | date | relevant to a wholly-`mise run` repo |
|---|---|---|
| [v2026.7.0] | 07-02 | **`env_shell_expand` ON by default** (#10702); `[vars]` `redact`/`required` (#10697); task template env fix (#10714) |
| [v2026.7.1] | 07-07 | **Tera v1 → v2 engine swap** (#10756) + `tera_v1` escape hatch (#10817); redaction wildcards become globs (#10729) |
| [v2026.7.2] | 07-07 | **`get_env` restored for Tera v2** (#10830) — i.e. it was broken in 7.1 |
| [v2026.7.3] | 07-08 | `MISE_TERM_WIDTH` (#10862). Otherwise nothing relevant |
| [v2026.7.4] | 07-09 | `task_source_files()` restored when a task defines `usage` args (#10870) |
| [v2026.7.5] | 07-09 | **Trust shared across git worktrees** (#10890), names `.claude/worktrees/`; `codex` shorthand flipped to npm (#10893) |
| [v2026.7.6] | 07-14 | **`mise doctor` warns on shim shadowed in PATH** (#10919); 2 BREAKING (output/`usage_*`); `[settings.sandbox]` (#10940) |
| [v2026.7.7] | 07-15 | `mise cache clear` concurrency fix (#10993); Tera in nested task tool options (#10960) |
| [v2026.7.11] | 07-20 | Double release (absorbs 7.8–7.10). Activation perf (#11130–4); **shim recursion fix** (#10982); network fail-fast (#11066); pipx exact-version fast path (#11013) |
| [v2026.7.12] | 07-23 | **Fixes the 7.11 Rosetta zsh activation hang** (#11188); `MISE_SAFE=1` (#11146); `gpg_verify` no longer silently skips (#11148) |
| [v2026.7.13] | 07-24 | **`[env]._` directives resolve in written order** (#11163); pwsh `-NoProfile` (#11199) |
| [v2026.7.14] | 07-26 | **BREAKING** shell-args global-only (#11293); **env files literal again** (#11269); task-cache correctness (#11288, #11296) |
| [v2026.7.15] | 07-27 | Task output caching (#11328); `outputs = []` for lint/test (#11351); `task_config.shell` (#11354) |

Releases with genuinely nothing else applicable: **v2026.7.3** and
**v2026.7.7** are almost entirely brew-cask / vfox / monorepo / systemd /
Windows surface, none of which this stack uses.

## Group 1 — Could have changed behaviour under us mid-work

### 1.1 The headline answer on PATH construction: NOTHING CHANGED

**No release in the entire v2026.7.x line altered how tool install directories
are injected into a task's PATH.** Evidence, all three routes agreeing:

- A term sweep across all 13 release bodies returns **zero** hits for
  `PRISTINE`, `__MISE_DIFF`, `env_cache`, and `install dir`.
- **Control arm:** the identical `grep -il` shape over the same 13 files
  returns `Tera` → 8 files, `PATH` → 11 files, and `get_env` → **exactly one**
  file (m7-2, which is precisely the release that restored it). The probe
  discriminates; the negatives are real.
- Independently corroborated by the sibling report's own history sweep, which
  found `__MISE_DIFF` mentioned in exactly 4 releases across *all* mise
  history — **v2026.5.6, v2025.11.4, v2024.12.13, v2024.11.28 — none in 7.x**.

**Conclusion, with its condition:** the ~154 install dirs are **not**
attributable to any v2026.7.x change. Measured on this host right now:
**188 PATH entries / 154 `mise/installs` dirs / `mise/shims` appearing twice**
(and `~/.local/bin` three times). That is long-standing mise behaviour plus
local duplication, not a regression that landed under you. Condition: measured
in *this* activated shell; a non-activated or `env -i` caller yields different
counts (see 1.3).

### 1.2 Template rendering DID change — twice — and `get_env` was collateral

This is the one genuine "changed under us" finding, and it lands squarely on
the mechanism the sibling report investigated.

- **[v2026.7.1] mise upgraded its template engine from Tera v1 to Tera v2**
  (#10756, plus #10814/#10815/#10817), with a temporary `tera_v1` /
  `MISE_TERA_V1` escape hatch **scheduled for removal in 2027.4.0** (#10817).
- **[v2026.7.2] `get_env` had to be *restored* for Tera v2 templates**,
  "backed by mise's original process environment, so older templates keep
  working" (#10830). The same release let shared configs opt back into v1 with
  `[env] MISE_TERA_V1 = "true"`, "which older mise versions safely ignore".

**Read together: `get_env` was broken or absent under v2026.7.1 and repaired in
v2026.7.2.** A host sitting on exactly v2026.7.1 — a one-release, ~11-hour
window (7.1 published 07-07T05:27Z, 7.2 at 07-07T16:19Z) — would have seen
template renders behave differently.

**CONDITION — mandatory, per the caller's annotation which I read first
(`mise-path-research.md` lines 74–106):** v2026.7.2's phrase "backed by mise's
original process environment" means `PRISTINE_ENV`, which reverses
`__MISE_DIFF` **and removes each path mise added**. Under an **activated
shell** that laundering deletes exactly the stale install dirs a drift check
exists to detect (measured by the caller: activated → 0 install dirs surviving;
`env -i` → 1 intact). So this release note is *not* an endorsement of
`get_env` for PATH-drift detection — it restores a helper whose semantics make
it unusable for that purpose. `knowledge-base/mise.toml:365–375` already
carries the "DO NOT simplify this to `get_env`" note with that measurement, and
`dotfiles/mise.toml:240` carries a matching note. **Nothing in this section
should be read as reopening that.**

- **[v2026.7.6] "config: add Tera contrib helpers"** (#10970) — the one-line
  changelog entry does not say which helpers, and I could not resolve the set
  from the notes. **UNKNOWN** — flagged rather than guessed, because it is an
  additive change to the same rendering surface.

### 1.3 `[env]` directive evaluation order changed

- **[v2026.7.13]** `_.path` / `_.file` / `_.source` inside a single `[env]._`
  block are now resolved **in written order**, so a `_.path` can reference a
  variable exported by a `_.source` written earlier (#11163).
  **Condition:** only affects a config that mixes ≥2 directives in one
  `[env]._` block. Neither repo does (`env_shell_expand`, `_.file`, `_.source`
  → 0 hits in both; control arm below), so **no impact here** — but it is a
  real ordering-semantics change to PATH assembly for anyone who does.
- **[v2026.7.12]** `_.file` env files now resolve references to variables
  defined in earlier files or `[env]` blocks instead of collapsing to empty
  (#11158). Same condition, same non-impact.

### 1.4 Shim behaviour

- **[v2026.7.11]** "shim: recursion is prevented when the directory env is
  filtered" (#10982) — arrived via the unpublished 7.8–7.10 batch. This is a
  shim-execution-path change and is the closest any 7.x release comes to the
  PATH/shim surface under investigation. Scope is not stated in the one-line
  entry: **UNKNOWN** whether it is platform-general or Windows-specific.
- **[v2026.7.15]** documentation-only: "documented how `activate` treats the
  shims directory with auto-install" (#11366). Docs, not behaviour.

### 1.5 Activation

- **[v2026.7.11]** the redundant initial prompt hook immediately after
  activation is now skipped for bash/zsh/fish when the session is unchanged
  (#11130, #11131, #11134). Fewer `mise` processes on shell startup.
- **[v2026.7.11]** network fail-fast: DNS failures non-retryable, process-local
  circuit breaker, and "shims, shell activation, and `mise x` make one bounded
  attempt" (#11066). Changes hang behaviour on a degraded network.
- **[v2026.7.1]** `restore $LASTEXITCODE after _mise_hook` (#10718) — pwsh only.

### 1.6 Env caching — no change in the line

`env_cache` / `env_cache_ttl` are **not mentioned in any of the 13 releases**
(control-armed above). `dotfiles/mise.toml:106` already documents these as
verified against 2026.7.0 defaults. The sibling report separately measured that
`get_env` tracks per-invocation and is **not** served stale from `env_cache`
(`env_cache=true`, `ttl=1h` on this machine), and that `mise run --fresh-env`
exists as the belt-and-braces bypass. Nothing in 7.x disturbs that.

## Group 2 — Every BREAKING change in the line, with applicability

**What I grepped** for each verdict: `knowledge-base/mise.toml`,
`dotfiles/mise.toml`, and `dotfiles/.config/mise/conf.d/*.toml` (2 files
confirmed present by `ls`). **Control arm for every "0 hits" below:** the same
grep shape over the same files returns `HK_MISE` → `mise.toml:126` and
`hk = "1.52.0"` → `shared.toml:31`, so an absent term is genuinely absent.

| # | tag | breaking change | applies here? |
|---|---|---|---|
| 1 | [v2026.7.0] | `env_shell_expand` **enabled by default**; opt out with `env_shell_expand = false` (#10702) | **No** — 0 hits in either repo, and no `env._.file`. But see Group 3.1: this default is what *armed* the 7.0→7.13 secret-corruption window |
| 2 | [v2026.7.1] | Tera **v1 → v2** engine (#10756); `tera_v1` escape hatch removed in 2027.4.0 | **Yes, silently** — both repos render task templates. No config change was needed, but the engine beneath them changed. `tera_v1` → 0 hits, i.e. neither repo pinned the old engine |
| 3 | [v2026.7.6] | `--quiet` / `quiet = true` / `MISE_QUIET=1` **no longer** collapse task output to un-prefixed interleave; use `--output quiet` / `-o interleave` (#10885) | **No** — `MISE_QUIET` → 0 hits both repos; `quiet` → 0 in kb, 1 in dotfiles but at `mise.toml:141` it is prose in a comment ("keep console quiet"), not a setting |
| 4 | [v2026.7.6] | `usage_*` variables are now **invocation-local**; workflows injecting them as implicit inputs must declare an input with `env=` (#10963) | **No** — `usage_` → 0 hits in both repos |
| 5 | [v2026.7.12] | `mise oci push --tool` removed (#11132) | **No** — no OCI usage |
| 6 | [v2026.7.12] | Node/Swift signature verification **always runs** when enabled; a missing `gpg` no longer silently skips. Opt out with `gpg_verify = false` (#11148) | **No** — neither repo installs node or swift through mise |
| 7 | [v2026.7.12] | unreleased `npm.use_npm_view` → `npm.shell_out` (#11149) | **No** |
| 8 | [v2026.7.14] | project-local `unix_default_file_shell_args`, `unix_default_inline_shell_args`, `windows_*` **ignored** (global-only) (#11293) | **No** — `default_file_shell_args` → 0 hits in both repos (re-verified this pass) |

**Net: 8 breaking changes in the line; exactly one (#2, the Tera v2 swap) took
effect on this stack, and it did so invisibly.** That is the finding worth
carrying: the only breaking change that touched you is the only one that
required no config to opt into.

## Group 3 — Bugs we may have been sitting on, or just escaped

### 3.1 The env-file secret-corruption window (7.0 → 7.13) — the big one

- **[v2026.7.0]** turned `env_shell_expand` **on by default** (#10702).
- **[v2026.7.14]** fixed the consequence: values from structured env files
  (`env._.file` loading JSON/YAML/TOML) were being **shell-expanded**, which
  "corrupted literals such as bcrypt-style `$6$salt$hash` **and could pull in
  matching process-environment values**" (#11269). Literal-by-default was
  restored; opt into expansion with `expand = true`.

**So the exposure window is v2026.7.0 → v2026.7.13 inclusive — 12 of the 13
releases, the overwhelming majority of the line.** Two distinct hazards: silent
secret corruption, and secret *leakage* from the ambient process env into a
config value.

**CONDITION — and it is what saves us:** the defect requires
`env._.file` loading a **structured** (JSON/YAML/TOML) env file. Neither repo
uses `env._.file` at all (0 hits, control-armed). **Not exposed.** But had
either repo adopted structured env files any time this month, this would have
been live and silent.

### 3.2 `get_env` broken by Tera v2, fixed one release later (7.1 → 7.2)

Covered in 1.2. Window: v2026.7.1 only, ~11 hours. Fixed by #10830.

### 3.3 Rosetta zsh activation hang (7.11 → 7.12)

Introduced in v2026.7.11, fixed in v2026.7.12: `mise activate zsh` **hung
non-interactive login shells under Rosetta**, because env-state snapshotting
autoloaded the `zsh/parameter` module via `dlopen` (#11188). Window: v2026.7.11
only (~3 days, 07-20 → 07-23). Already identified in Part I; re-confirmed as
the only *hang*-class regression in the line.

### 3.4 Task-freshness bugs — a gate that silently did not run

Three fixes in this class, i.e. it was wrong for most of the line:

- **[v2026.7.6]** invalidate auto freshness after a **failed** rerun (#10953).
- **[v2026.7.14]** changing a task's `run`, `sources`, or `outputs` now
  invalidates cached state — previously such edits could leave a task
  **incorrectly skipped** (#11288).
- **[v2026.7.14]** a task's source hash is persisted **only after a successful
  run**, so a failed run no longer marks stale sources as up to date (#11296).

**CONDITION:** all three require a task declaring `sources`/`outputs`. Neither
repo's tasks do (`task_config` → 0 hits; no `sources =` on any `kb-*` task), so
**not exposed**. This matters prospectively: it is precisely the failure mode
`verify-before-advancing.md` exists to prevent, and it would arrive the moment
Group 4.1 is adopted. Adopt on ≥ v2026.7.14, never earlier.

### 3.5 Over-redaction scrubbing unrelated task output (fixed 7.1)

**[v2026.7.1]** redaction wildcards are now matched as **globs**, fixing
over-redaction where patterns like `*_KEY` scrubbed unrelated values from task
output (#10729).

**This one is not hypothetical here.** `knowledge-base/mise.toml:100–101`
documents exactly this symptom in the caller's own words: "host masks some
literal strings as `[redacted]` — including the digit `1` (`16` prints as
`[redacted]6`)". That is an over-redaction artifact of the same family. The
mise-side fix landed in v2026.7.1; whether the repo's observation predates or
postdates that is **UNKNOWN** (the comment is undated). Worth re-checking now
that the host is on 7.15 — if the `[redacted]6` behaviour has vanished, the
comment is stale and can be retired.

## Group 4 — Task-system features worth adopting

Ranked by fit with `zero-bash-logic` (all logic is python behind `mise run`).

### 4.1 `outputs = []` result-only caching for lint/test — top candidate

**[v2026.7.15]** (#11351). The notes name the use case verbatim: "checks like
**lint, test, and typecheck** that produce no files. Their successful result
and replayable logs are cached without writing an archive." Combined with
`sources` (#11328) and `task_config.input_groups` / `global_inputs` (#11356),
this is a native answer to "don't re-run the gate when nothing changed".

**Conditions before adopting:** (a) requires **≥ v2026.7.15** — the whole
feature is new in the current release; (b) requires **≥ v2026.7.14** for the
cache-invalidation correctness fixes in 3.4, else a gate can be silently
skipped after an edit — which would directly violate `verify-before-advancing`;
(c) it is explicitly **experimental and opt-in**, and "cache failures degrade
to misses or warnings rather than failing a task". Given mise is unpinned here,
(a)+(b) are not guaranteed to hold on the next host that clones this repo —
which argues for Group 5 first.

### 4.2 `mise doctor`'s native shim-shadow warning — replaces hand-rolled logic

**[v2026.7.6]** "`mise doctor` now warns when a mise shim is **shadowed by an
earlier executable in `PATH`**" (#10919). This is a native implementation of a
check very close to what `kb_setup.launch` / `cc-doctor` is being built to do,
and `use-tool-builtins.md` makes evaluating it mandatory before keeping custom
code.

**Do not treat this as a drop-in replacement without measuring.** Two open
questions I could not settle from the notes: whether it reports *which* entry
shadows (needed for a useful diagnostic), and whether it exits non-zero
(needed for a gate). **UNKNOWN** — resolve empirically before adopting or
retiring anything. Note the check is present on this host: `mise doctor`
reports `shims_on_path: yes` and lists the shims dir **twice**, which is itself
a finding (see 1.1).

### 4.3 Per-task `output` style, decoupled from verbosity

**[v2026.7.6]** (#10885) added a per-task `output` style field so "styles like
`prefix` and quietness combine freely", and **[v2026.7.15]** (#11355) made
`--output` / `MISE_TASK_OUTPUT` honour raw and interactive tasks the same way
`task.output` config does.

Directly relevant: `knowledge-base/mise.toml:324` documents using `raw`
specifically because mise's captured output prefixes task lines with `[cc]`.
A per-task `output` style may now express that intent without `raw` — which
matters because `raw` also opts out of other output handling. Re-evaluate that
comment against 7.15 behaviour.

### 4.4 Others worth knowing

- **`[settings.sandbox]` deny defaults** — `deny_all`, `deny_read`,
  `deny_write`, `deny_net`, **`deny_env`** ([v2026.7.6], #10940). Paired with
  `pass_through_env` ([v2026.7.15], #11363), which keeps selected ambient vars
  "like tokens" available under `deny_env` **without** them entering cache
  keys. That pairing is the correct shape for a secret a task needs.
- **Trust shared across git worktrees** ([v2026.7.5], #10890) — the notes
  explicitly name "AI-agent worktrees under `.claude/worktrees/`". Trusting the
  main checkout now covers every worktree; sharing flows one way only, and
  paranoid mode is excluded.
- **`mise trust --all` walks nested subdirectory configs** ([v2026.7.5],
  #10889), respecting `.gitignore` and skipping `node_modules`/`vendor`/
  `target`/`dist`/`build`.
- **Circular-dependency detection on the fully resolved graph**
  ([v2026.7.15], #11329) — cycles through `wait_for`, `{{usage.*}}` deps, and
  `depends_post` are now reported with a concrete path *before* any task runs.
- **`config_sources` in `mise tasks info` JSON** ([v2026.7.11], #11098) — names
  every config contributing to a task; useful for debugging task provenance
  across `mise.toml` + `conf.d`.
- **`mise generate task-docs --inject`** now errors clearly on missing/reversed
  `<!-- mise-tasks -->` markers instead of clobbering the file ([v2026.7.15],
  #11359).
- **`[vars]` `redact = true` and `required` validation** ([v2026.7.0], #10697).

## Group 5 — Detecting that mise changed underfoot

This is the actionable group, given mise cannot fully pin itself.

### 5.1 `mise doctor`'s `self_update_available` is UNRELIABLE — measured

On this host, right now:

```
$ mise doctor | grep -i 'version\|self_update'
version: 2026.7.15 macos-arm64 (2026-07-27)
self_update_available: yes          # <-- but we ARE on latest

$ cat ~/.cache/mise/latest-version
2026.7.15                            # <-- cache agrees with installed
```

**mise reports an update is available while installed == cached-latest ==
2026.7.15.** Cross-checked against the GitHub releases API in Part I, which
also says 2026.7.15 is latest. Three routes agree that we are current; the
field disagrees with all of them. **Root cause UNKNOWN** — plausibly related to
the negative-caching change in [v2026.7.14] (#11285) or to the binary having
been laid down by the `mise.run` installer rather than `self-update`, but I did
not establish it and will not guess.

**Consequence: do not use `self_update_available` as a currency signal.** It is
a false-positive here, and a check that cries wolf is the same defect class as
one that cannot fail. Use the releases API (Part I §3) or
`~/.cache/mise/latest-version`.

### 5.2 What 7.x actually offers for pinning/detection

- **`MISE_INSTALL_SKIP_IF_EXISTS`** ([v2026.7.4], #10882) — makes the
  `mise.run` installer skip re-downloading when the requested version is
  already at the install path. **Condition, stated in the notes:** "Only the
  resolved install path is checked (**not the wider `PATH`**), and default
  behavior is unchanged unless you opt in." This makes a *pinned bootstrap*
  idempotent; it does not detect drift.
- **`MISE_SAFE=1`** ([v2026.7.12], #11146, #11151) — an inert config reader for
  running `mise lock --bump` against untrusted config with no code execution
  and no trust prompt. Useful for a currency job; **not** a version pin.
- **`mise lock --bump`** ([v2026.7.12], #11145) — advances fuzzy lockfile
  selectors without installing and without touching `mise.toml`, and pairs with
  `--json` / `--dry-run`. This is the machine-readable drift feed a currency
  check wants — **for tools, not for mise itself**.
- **Nothing in the line lets mise pin its own version via a lockfile entry.**
  Sweep across all 13 bodies found no such feature. This is the structural gap:
  mise bootstraps the toolchain, so it cannot be a `[tools]` entry in the
  config it reads.

### 5.3 The recommendation, unchanged and now better grounded

Part I recommended adding `[tool.mise]` to `currency.toml`. This pass
strengthens it: with 13 releases in 25 days, **one silent breaking change that
required no opt-in** (Tera v2), and a 12-release secret-corruption window that
this repo escaped only by not using a feature — the absence of any drift
detection on mise is the single largest un-instrumented risk in the stack.

The `[tool.mise]` entry should record installed version from `mise --version`
and latest from the **GitHub releases API** — explicitly **not** from
`mise doctor`'s `self_update_available`, per 5.1.

## Probe hygiene for Part II

- **Every negative control-armed.** Release-body term sweep: `PRISTINE`,
  `__MISE_DIFF`, `env_cache`, `install dir` → 0 files, while the identical
  `grep -il` shape returns `Tera` → 8, `PATH` → 11, `get_env` → exactly 1.
- **Repo config greps:** control arm `HK_MISE` → `mise.toml:126` and
  `hk = "1.52.0"` → `shared.toml:31` in the same file set.
- **Tag existence:** control-armed via `git/matching-refs` (full listing, no
  exact-match trap) plus per-tag `git/ref` returning real refs for 7.7/7.8/
  7.10/7.11 and 404 only for 7.9.
- **A surprise was cross-checked, not reported raw:** `self_update_available:
  yes` was checked against `~/.cache/mise/latest-version` and the releases API
  before being written up as a false positive.
- **The `codex` backend ambiguity was resolved empirically, not guessed.**
  [v2026.7.5] (#10893) flipped the `codex` shorthand to prefer
  `npm:@openai/codex`; [v2026.7.6] (#10922) logged "revert preferring aqua for
  codex", which is ambiguously worded in both directions. Rather than guess, I
  read the installed registry: `mise registry codex` → `aqua:openai/codex
  npm:@openai/codex` (aqua **first**). Control arm: `mise registry taplo` →
  `aqua:tamasfe/taplo cargo:taplo-cli`, the same two-backend ordered shape, so
  the ordering is meaningful. **Net across the line: back to aqua-first, so
  `knowledge-base/mise.toml`'s comment "`codex`=aqua:openai/codex" is correct
  today** — but it was wrong for the v2026.7.5 window, and the pin is
  `codex = "0.145.0"` with no explicit backend, so it follows the registry.
- **Marked UNKNOWN rather than guessed:** the contents of "Tera contrib
  helpers" (#10970); the platform scope of the shim-recursion fix (#10982);
  whether the doctor shim-shadow check names the shadowing entry or exits
  non-zero (#10919); the root cause of the `self_update_available` false
  positive; whether `mise.toml:100`'s `[redacted]6` observation predates the
  v2026.7.1 redaction-glob fix.
- **Condition carried on the load-bearing claim:** the caller's annotation on
  `mise-path-research.md` (lines 74–106) was read **before** writing anything
  about `get_env` / `PRISTINE_ENV` / `__MISE_DIFF`, and §1.2 states the
  activated-shell condition under which v2026.7.2's `get_env` restoration must
  **not** be read as an endorsement for PATH-drift detection.

## GitHub repos touched

- [jdx/mise](https://github.com/jdx/mise) — the subject: release list, five
  release-note bodies (v2026.7.11 → v2026.7.15), and the releases/tags APIs.

<!-- citation anchors -->
[v2026.7.0]: https://github.com/jdx/mise/releases/tag/v2026.7.0
[v2026.7.1]: https://github.com/jdx/mise/releases/tag/v2026.7.1
[v2026.7.2]: https://github.com/jdx/mise/releases/tag/v2026.7.2
[v2026.7.3]: https://github.com/jdx/mise/releases/tag/v2026.7.3
[v2026.7.4]: https://github.com/jdx/mise/releases/tag/v2026.7.4
[v2026.7.5]: https://github.com/jdx/mise/releases/tag/v2026.7.5
[v2026.7.6]: https://github.com/jdx/mise/releases/tag/v2026.7.6
[v2026.7.7]: https://github.com/jdx/mise/releases/tag/v2026.7.7
[v2026.7.11]: https://github.com/jdx/mise/releases/tag/v2026.7.11
[v2026.7.12]: https://github.com/jdx/mise/releases/tag/v2026.7.12
[v2026.7.13]: https://github.com/jdx/mise/releases/tag/v2026.7.13
[v2026.7.14]: https://github.com/jdx/mise/releases/tag/v2026.7.14
[v2026.7.15]: https://github.com/jdx/mise/releases/tag/v2026.7.15
[#10982]: https://github.com/jdx/mise/pull/10982
[#11013]: https://github.com/jdx/mise/pull/11013
[#11066]: https://github.com/jdx/mise/pull/11066
[#11070]: https://github.com/jdx/mise/pull/11070
[#11098]: https://github.com/jdx/mise/pull/11098
[#11103]: https://github.com/jdx/mise/pull/11103
[#11106]: https://github.com/jdx/mise/pull/11106
[#11130]: https://github.com/jdx/mise/pull/11130
[#11131]: https://github.com/jdx/mise/pull/11131
[#11134]: https://github.com/jdx/mise/pull/11134
[#11146]: https://github.com/jdx/mise/pull/11146
[#11148]: https://github.com/jdx/mise/pull/11148
[#11151]: https://github.com/jdx/mise/pull/11151
[#11152]: https://github.com/jdx/mise/pull/11152
[#11158]: https://github.com/jdx/mise/pull/11158
[#11163]: https://github.com/jdx/mise/pull/11163
[#11182]: https://github.com/jdx/mise/pull/11182
[#11188]: https://github.com/jdx/mise/pull/11188
[#11189]: https://github.com/jdx/mise/pull/11189
[#11199]: https://github.com/jdx/mise/pull/11199
[#11231]: https://github.com/jdx/mise/pull/11231
[#11236]: https://github.com/jdx/mise/pull/11236
[#11269]: https://github.com/jdx/mise/pull/11269
[#11283]: https://github.com/jdx/mise/pull/11283
[#11288]: https://github.com/jdx/mise/pull/11288
[#11293]: https://github.com/jdx/mise/pull/11293
[#11296]: https://github.com/jdx/mise/pull/11296
[#11306]: https://github.com/jdx/mise/pull/11306
[#11312]: https://github.com/jdx/mise/pull/11312
[#11319]: https://github.com/jdx/mise/pull/11319
[#11328]: https://github.com/jdx/mise/pull/11328
[#11329]: https://github.com/jdx/mise/pull/11329
[#11347]: https://github.com/jdx/mise/pull/11347
[#11351]: https://github.com/jdx/mise/pull/11351
[#11354]: https://github.com/jdx/mise/pull/11354
[#11355]: https://github.com/jdx/mise/pull/11355
[#11356]: https://github.com/jdx/mise/pull/11356
[#11359]: https://github.com/jdx/mise/pull/11359
[#11363]: https://github.com/jdx/mise/pull/11363
[#11367]: https://github.com/jdx/mise/pull/11367
