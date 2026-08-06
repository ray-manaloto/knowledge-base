# Renovate recon: dotfiles → knowledge-base port

**Agent:** renovate-recon. **Date:** 2026-08-06. **Mode:** READ-ONLY, facts only.
**Repos read:** `/Users/rmanaloto/dev/github/ray-manaloto/dotfiles` (source),
`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base` (target).

Written incrementally as findings landed. `UNKNOWN` marks anything not determined.

---

## A. The Renovate config — `dotfiles/renovate.json` (205 lines, 11,726 bytes)

Location: **repo root**, `renovate.json`. **CONFIRMED the only one:**
`git ls-files | grep -iE "renovate.*\.(json|json5)$|\.renovaterc"` → exactly one
hit, `renovate.json`. `.github/` holds only `actions/`, `workflows/`, and
`dependabot.yml` (see B.3) — no Renovate config there.

### A.1 Top-level (`renovate.json:1-17`, `:202-204`)

| Key | Value | Line |
|---|---|---|
| `$schema` | `https://docs.renovatebot.com/renovate-schema.json` | `:2` |
| `extends` | `["github>jdx/renovate-config", "group:all"]` | `:3-6` |
| `schedule` | `["at any time"]` | `:7-9` |
| `minimumReleaseAge` | `"1 hour"` | `:10` |
| `minimumReleaseAgeBehaviour` | `"timestamp-optional"` | `:11` |
| `lockFileMaintenance` | `{enabled: true, minimumReleaseAge: "1 hour"}` | `:12-15` |
| `prConcurrentLimit` | `20` | `:16` |
| `prHourlyLimit` | `0` (unlimited) | `:17` |
| `ignoreDeps` | `["CC", "CXX"]` | `:78-81` |
| `vulnerabilityAlerts` | `{enabled: true}` | `:202-204` |

**No `labels` key. No `commitMessage*` key. No `ignorePaths` key.** Commit/PR message
format and labels are therefore whatever `github>jdx/renovate-config` + Renovate
defaults produce — **UNKNOWN without fetching that preset** (it is a remote GitHub
preset, not vendored here).

`group:all` + `"group:all"` in extends means **one PR for everything** by default —
that is the "all-deps PR" referenced in the pixi rule (`:71`).

### A.2 `enabledManagers` (`renovate.json:192-201`) — the whitelist

```json
["npm", "cargo", "mise", "dockerfile", "docker-compose",
 "devcontainer", "github-actions", "custom.regex"]
```

Note **`mise` IS a native Renovate manager** and is enabled. Also note what is
absent: **no `pep621`, no `pip_requirements`, no `poetry`, no `uv`** — so dotfiles'
Python deps are NOT managed by Renovate at all. That is a direct gap for the port
(knowledge-base's `pyproject.toml` would need `pep621` added to this list).

### A.3 `packageRules` (`renovate.json:18-77`) — 6 rules

1. **`:19-24`** — `matchPackageNames: ["bats-core"]` → `groupName: "bats-core"`
   (splits it out of `group:all`).
2. **`:25-31`** — `matchManagers: ["devcontainer"]` → **`pinDigests: false`**.
   Reason (verbatim from its `description`): the devcontainer manager + `pinDigests`
   appends a digest to an already-tagged feature ref producing the invalid
   `ghcr.io/devcontainers/features/sshd:1@sha256:...`, which `@devcontainers/cli`
   rejects. Broke main in PR #187, 2026-07-08.
3. **`:32-41`** — **the automerge rule**: `matchUpdateTypes: ["minor","patch","digest"]`
   → `automerge: true`, `automergeType: "pr"`, `platformAutomerge: true`.
   **Major updates are NOT automerged.**
4. **`:42-49`** — **`graphifyy`: `automerge: false`, `groupName: null`** (review-before-merge,
   pulled out of the group). Rationale verbatim: ships ~2x/day as PATCH releases so the
   blanket rule would merge it unread twice daily; pre-1.0 with a documented history of
   SILENT data loss (v0.9.22 fixed a node eviction + a real `env/.env/*_env` source dir
   pruned as a false-positive virtualenv). "A green build hides a corrupted graph, which
   no CI check can see." **`minimumReleaseAge` deliberately REMOVED 2026-07-20 (Ray's call)** —
   a soak delay adds no safety on top of `automerge:false`, it only prolongs running the
   known-buggy version.
5. **`:50-61`** — `apt-ubuntu-pockets`: `matchDatasources: ["deb"]` → four `registryUrls`
   (apt.llvm.org resolute, Ubuntu resolute / resolute-updates / resolute-security).
   Relies on the deb datasource's `registryStrategy='merge'`.
6. **`:62-69`** — `matchDatasources: ["custom.gcc-latest"]` → `extractVersion` regex +
   `minimumReleaseAgeBehaviour: "timestamp-optional"` (the html datasource emits no
   `releaseTimestamp`, and the default behaviour holds timestamp-less updates FOREVER).
7. **`:70-76`** — `pixi`: `extractVersion: "^v?(?<version>.+)$"` — strips the upstream
   `v` prefix because mise's registry serves unprefixed versions only. Without it,
   Renovate writes `pixi = "v0.76.1"` and mise cannot resolve it (PR #455, two red runs).

### A.4 `customManagers` (`renovate.json:82-185`) — 8 regex managers

All `customType: "regex"`. **None of them reads `pyproject.toml`.** One reads a
`mise`-family TOML but it is `.devcontainer/mise-system.toml`, not `mise.toml`:

| # | Lines | Files matched | What it pins | depName / datasource |
|---|---|---|---|---|
| 1 | `:83-95` | `hk.pkl`, `hk-common.pkl`, `hk-image.pkl` | hk pkl schema pin — **two** matchStrings (`download/v<X>/hk@` and `hk@<X>`) because the version appears twice per URL; a single match produces a 404 URL (fixed #248) | `jdx/hk` / `github-releases` |
| 2 | `:96-107` | `.chezmoiversion` | chezmoi minimum version | `twpayne/chezmoi` / `github-releases` |
| 3 | `:108-122` | `docker-bake.hcl`, `.devcontainer/Dockerfile` | `CLANG_P2996_REF` 40-char git SHA | `bloomberg/clang-p2996` / `git-refs`, `currentValueTemplate: "p2996"` |
| 4 | `:123-135` | `.devcontainer/Dockerfile` | `ARG GCC_LATEST_DEB=gcc-latest_<v>.deb` | `gcc-latest` / `custom.gcc-latest`, `versioningTemplate: "loose"` |
| 5 | `:136-148` | `docker-bake.hcl`, `.devcontainer/Dockerfile` | `ubuntu:<v>@sha256:<64>` base image digest | `ubuntu` / `docker` |
| 6 | `:149-160` | `.devcontainer/Dockerfile` | `ARG MISE_VERSION=<v>` | `jdx/mise` / `github-releases` |
| 7 | `:161-172` | `.github/workflows/image-analysis.yml` | `DIVE_VERSION: <v>` env var | `wagoodman/dive` / `github-releases` |
| 8 | `:173-184` | `.devcontainer/mise-system.toml` | every `"apt:<pkg>" = "<version>"` in `[bootstrap.packages]` (52 LLVM + 14 Ubuntu) | (depName from regex) / `deb`, `versioningTemplate: "deb"` |

**Manager #8 carries the single most portable fact in this file** (`:175`, verbatim):
> "Renovate's NATIVE mise manager cannot do this — its schema parses only `tools`/`tasks`
> and z.object silently strips `[bootstrap.packages]` — so this regex + the `deb`
> datasource is the only route."

and

> "Renovate compiles regexes with RE2, which has no lookaround."

Both constrain any custom manager written for knowledge-base.

### A.5 `customDatasources` (`renovate.json:186-191`)

One: `gcc-latest` → `defaultRegistryUrlTemplate: "https://jwakely.github.io/pkg-gcc-latest/"`,
`format: "html"`. Entirely dotfiles-specific.

---

## B. How it runs in CI — **it does not. There is no Renovate workflow.**

**Finding: zero workflows invoke Renovate.** dotfiles runs the **Mend-hosted
Renovate GitHub App** (app id **2740**, slug `renovate` — `renovate.py:30-31`).
The scan cadence is Mend-side; GitHub Actions only *reacts* to it.

**Control arm (per `probes-need-a-control-arm.md`).** Searched
`dotfiles/.github/workflows/` for a runner —
`renovatebot/github-action|renovate/renovate|npx renovate|npm exec renovate|uses:.*renovate|mise run renovate|renovate --` → **0 hits**.
Two controls, same command shape, same directory:
- `uses: actions/checkout` → hits in `ghcr-cleanup.yml:56`, `autofix.yml:46`, `image-analysis.yml:58`.
- the bare word `renovate` per file → `autofix.yml` 1, `gcc-sha-repair.yml` 5, `ci.yml` 1, `refresh.yml` 3, others 0.

So the probe discriminates, and the negative is real: the word is present, a
runner is not.

### B.1 The four workflows that REACT to Renovate

| File | Trigger | Renovate relationship | Cite |
|---|---|---|---|
| `gcc-sha-repair.yml` | `push:` branches `renovate/**`, paths `.devcontainer/Dockerfile` | **The only Renovate-coupled job.** Recomputes `GCC_LATEST_DEB_SHA256` (kayari publishes no checksum, so Renovate cannot manage it) and commits it **back to the Renovate branch** so the bump goes green | `:19-24`, `:2-18` |
| `autofix.yml` | (its own) | **Skips** bot PRs: `if: github.actor != 'github-actions[bot]' && != 'renovate[bot]' && != 'dependabot[bot]'` | `:41` |
| `ci.yml` | `push`/`pull_request` | Lists `renovate.json` in its `paths:` filter, so editing the config runs CI | `:23` |
| `refresh.yml` | daily cron `00:00` | Does what Renovate **cannot** — see B.2 | `:1-30`, `:118-130` |

`gcc-sha-repair.yml` details worth porting-by-analogy (`:25-53`):
`permissions: contents: read` at file level; the write comes from a minted
**GitHub App token** (`actions/create-github-app-token@bcd2ba49...` v3.2.0, `:60`)
because a `secrets.GITHUB_TOKEN` push does **not** re-fire the PR's
`pull_request` CI (GitHub's recursion guard). `concurrency: gcc-sha-repair-${{ github.ref }}`,
`cancel-in-progress: true` (`:38-40`); `timeout-minutes: 15` (`:44`);
`HK_SKIP_HOOKS: pre-commit,pre-push` (`:53`). Logic lives in
`dotfiles-setup gcc-sha` per zero-bash-logic; the workflow is "a thin trigger +
commit seam" (`:16-18`).

### B.2 The documented Renovate boundary (`refresh.yml:12-18`, verbatim)

> "Why not Renovate: the hosted app can never run `mise lock` (the command is
> admin-allowlisted) and does not know mise-system.lock by name; **its native
> `mise` manager only rewrites version STRINGS in config files.** This job owns
> re-RESOLUTION of `"latest"` pins."

This is the single most load-bearing fact for the port: **Renovate's mise
manager edits `mise.toml` strings and never regenerates `mise.lock`.**
knowledge-base has a committed `mise.lock` (repo root) and a
`lockfile-invariants-have-no-gate` memory — so a ported Renovate would bump
`mise.toml` and leave `mise.lock` behind unless something else re-resolves it.

**Secrets/tokens referenced:** `REFRESH_APP_ID` + the App private key, via
`actions/create-github-app-token` (`gcc-sha-repair.yml:55-60`, shared with
`refresh.yml`). Exact secret names beyond `REFRESH_APP_ID`: **UNKNOWN** (not
read in full).

### B.3 ⚠️ Renovate is only HALF the story — `.github/dependabot.yml` is the other half

`dotfiles/.github/` contains exactly three entries: `actions/`, `workflows/`, and
**`dependabot.yml`** (1,779 bytes). And `renovate.json` at the repo root is the
**only** Renovate config (`git ls-files | grep -iE "renovate.*\.(json|json5)$|\.renovaterc"`
→ one hit: `renovate.json`).

`dependabot.yml:4-6`, verbatim:
> "Scope: Python deps in /python, and nothing else. **This is the repo's ONLY
> Python dependency updater** — renovate.json's `enabledManagers` lists no
> pip/pep621 manager, so removing this file silently stops Python bumps."

**The two tools are deliberately partitioned to avoid duplicate PRs**
(`dependabot.yml:10-14`):
> "github-actions ecosystem is intentionally NOT in `updates` here. Renovate
> handles GHA action bumps via `enabledManagers`… Having both would generate
> duplicate PRs and race-condition merge conflicts."

Full config:

| Key | Value | Line |
|---|---|---|
| `version` | `2` | `:8` |
| `package-ecosystem` | `"pip"` — "use pip even for pyproject.toml projects" | `:17` |
| `directory` | `"/python"` | `:18` |
| `schedule` | `interval: "cron"`, `cronjob: "0 0 * * *"`, `timezone: "America/Chicago"` | `:19-25` |
| `open-pull-requests-limit` | `5` | `:27` |
| `groups` | `python-deps: patterns: ["*"]` — one PR for all | `:29-35` |
| `labels` | `["dependencies"]` | `:37-38` |
| `commit-message.prefix` | `"ci"` | `:40-41` |
| `cooldown.default-days` | `7` | `:42-43` |

Note `:21-23`: **Dependabot rejects cron expressions under a 24h minimum**, so
sub-daily intervals fail validation. And `:30-32`: the group was once misnamed
`github-actions`, making Python bumps arrive titled "bump the github-actions
group" — renamed in #93.

**Consequence for the port:** dotfiles' answer to "who bumps Python deps" is
**Dependabot, not Renovate**. Since knowledge-base's only real bumpable
dependency table is its 4 exact dev pins (F.3), the dotfiles-shaped answer for
that half is a `dependabot.yml`, not an `enabledManagers` entry. **This also
supplies the labels/commit-message convention that `renovate.json` itself does
not carry** (`labels: ["dependencies"]`, `commit-message.prefix: "ci"`).

---

## C. How it runs LOCALLY — the important half

**Yes, there is a full local dry-run path, and it is already zero-bash.**
Control-armed: **no `.sh` file in dotfiles mentions renovate** (the only 3 hits
under `scripts/` are vendored `node_modules/**/package.json`; control `bash` →
hits in `workspace-hash.sh` etc.). Renovate here is *skill → mise task → python*.

### C.1 The binary is a pinned mise tool

`dotfiles/mise.toml:22`:
```toml
"npm:renovate" = "44.13.2"
```
Node is pinned **per-task**, not globally — see C.2.

### C.2 The two mise tasks (verbatim `run =` lines)

**`[tasks.renovate-dryrun]`** — `mise.toml:629-662`
```toml
description = "Report the updates Renovate would raise, from this working tree (no PRs)"
tools.node = "24"
run = 'uv run --project python dotfiles-setup renovate-dryrun'
```
Usage documented in the comment block (`:635-637`):
`mise run renovate-dryrun` (report, always rc=0) ·
`-- --check` (rc=1 if any update pending) · `-- --json`.

`tools.node = "24"` (`:661`) is mise's per-task version override. Rationale
(`:646-655`): renovate 43.x declares `engines.node ^24.11.0`; under the repo's
node 26 the binary logs "Unsupported node environment detected" and **exits
rc=1**. Corrected in #299: it still extracts and resolves **normally** — the pin
buys a clean exit code, **not** report correctness. Probed 2026-07-15: default
task → v26.5.0, pinned task → v24.x.

> **DRIFT WORTH FLAGGING:** every probe cited in the task comment and the module
> docstring was run against **renovate 43.260.2 / 43.265.1**, but the pin is now
> **44.13.2** (`mise.toml:22`). The `engines.node ^24.11.0` condition is stated
> for *43.x*. Whether renovate 44.x still needs `tools.node = "24"` is
> **UNKNOWN — not re-probed**. Carry the condition, not just the number.

Also `mise.toml:658-660`: a `deb` datasource pointed at Ubuntu's archive makes
lookup slow (downloads the whole main,universe Packages index); apt.llvm.org's
index is ~13 KB. **A full pass over dotfiles takes ~80s.**

**`[tasks.renovate-status]`** — `mise.toml:664-670`
```toml
description = "Report Mend-hosted Renovate install + privileges + open update PRs"
run = 'uv run --project python dotfiles-setup renovate-status'
```

### C.3 `python/src/dotfiles_setup/renovate_dryrun.py` (383 lines) — the dry-run

Entrypoint: `renovate_dryrun_main(*, json_output=False, check=False) -> int` (`:352`).

**Step by step (`:352-382`):**
1. Open a `tempfile.TemporaryDirectory()`; report path = `<tmp>/renovate-report.json` (`:354-355`).
2. `run_renovate(report_path)` (`:193-202`) → `subprocess.run(["renovate", "--platform=local", "--dry-run=lookup"], env=renovate_env(...), timeout=900.0)`.
3. On `returncode != 0` **or** no report file: write stderr, then emit a message that **distinguishes the two cases** — report-on-disk means extraction ran and the exit code is the complaint; no report means it died before writing (`:357-373`, the #299 fix). Return 1.
4. `parse_report(report_path.read_text(), complete=resolve_github_token() is not None)` (`:374-376`).
5. Emit `json.dumps(asdict(result))` or `render_report(result)` (`:378-381`).
6. `decide_exit_code(result, check=check)` (`:382`).

**The four probed renovate facts (module docstring `:12-53`) — all portable:**

1. **`cloneSubmodules` must be forced off (#290).** The `github>jdx/renovate-config`
   preset sets `cloneSubmodules: true`; `initRepo` then reaches `syncGit()`, which
   throws `Cannot sync git when platform=local`. **No `.gitmodules` needed — the
   flag alone does it.** `RENOVATE_CLONE_SUBMODULES=false` does **NOT** work (env is
   the *global* layer; repo config is applied over it). `force` is the only layer
   applied AFTER repo resolution → `_FORCE_CONFIG = '{"cloneSubmodules":false}'`
   passed as `RENOVATE_FORCE` (`:69`, `:184`). This keeps `renovate.json`
   byte-identical to what hosted Renovate reads.
2. **`--dry-run=full` is silently downgraded.** The local platform's `initPlatform`
   coerces: `extract` stays `extract`, everything else — **including `full`** —
   becomes `lookup`. "The task asked for `full` for months and never got it."
   → `RENOVATE_ARGS = ("--platform=local", "--dry-run=lookup")` (`:74`).
3. **The native report IS populated in lookup mode.** `addExtractionStats` runs
   BEFORE the `dryRun !== 'lookup'` guard, so `reportType=file` yields every
   packageFile's deps *with* resolved `updates[]` → parse JSON instead of scraping
   a 5k-line debug log (`use-tool-builtins.md`). Set via `RENOVATE_REPORT_TYPE=file`
   + `RENOVATE_REPORT_PATH` (`:185-186`).
4. **`persistRepoData: true`** is what suppresses the repository worker's
   `deleteLocalFile('.')` — under `platform=local` the "localDir" IS your working
   tree. **Do not set it false** (`:40-43`). ⚠️ This is the destructive-risk note.

**The token behaviour (`:79-100`, `:163-176`) — a real trap:**
Renovate reads github.com lookup creds from `GITHUB_COM_TOKEN` /
`RENOVATE_GITHUB_COM_TOKEN` **only**, and **actively DELETES a bare `GITHUB_TOKEN`
from its own env** (parse/env.js) so a *platform* token cannot leak into
*datasource* lookups. Without a token renovate **silently skips every
github-datasource dep** and reports a smaller number with no error — measured on
dotfiles 2026-07-15: **8 pending without a token vs 33 with one (53 deps
unlooked-up)**. So an untokened run is labelled `INCOMPLETE` / "a FLOOR, not a
total", never reported as a total (`:286-309`). Search order (`_TOKEN_ENV_VARS`,
`:94-100`): `GITHUB_COM_TOKEN`, `RENOVATE_GITHUB_COM_TOKEN`, `GITHUB_TOKEN`,
`GITHUB_API_TOKEN`, `MISE_GITHUB_TOKEN`.

**Dataclasses:** `PendingUpdate` (`:103-118`), `GroupStats` (`:121-143`),
`DryRunResult` (`:146-160`). `GroupStats` exists to answer *"did my regex
extract?"* — "a custom manager that matched zero files and a custom manager whose
deps are all current both render as silence" (`:126-129`). `parse_report`
(`:223-277`) tallies per-manager and per-datasource, counting a dep with a
`skipReason` as **neither pending nor current** (`:244-247`).

### C.4 `python/src/dotfiles_setup/renovate.py` (218 lines) — hosted-app status

Entrypoint `renovate_status_main(*, json_output=False) -> int` (`:206`). Answers
three questions (`:8-14`): is the app installed with the right privileges; what
update PRs are open; what did it recently merge.

- `RENOVATE_APP_ID = 2740`, slug `renovate` — "the 'renovate' app IS 'the Mend
  app'; there is no separate Mend app to install" (`:28-31`).
- `REQUIRED_PERMISSIONS` (`:35-41`): `contents=write`, `pull_requests=write`,
  `issues=write`, `checks=write`, `statuses=write`.
- All data via `gh` subprocess, 60s timeout, **empty string on failure** (`:65-76`).
  `gh repo view --json nameWithOwner`; `gh api /orgs/<owner>/installations`;
  `gh pr list --author app/renovate` (open limit 50, merged limit 10) (`:116-142`).
- **Exit code is a gate:** `return 0 if status.healthy else 1`, where `healthy =
  installed and not missing_permissions` (`:59-62`, `:217`).

### C.5 CLI wiring — argparse subparsers in one monolith

`python/pyproject.toml:41`: `dotfiles-setup = "dotfiles_setup.main:main"`.
`main.py:73-74` imports both entrypoints; `main.py:756-777` registers the
subparsers (`renovate-status` with `--json`; `renovate-dryrun` with `--json` and
`--check`); `main.py:1404-1408` dispatches via a lambda table to `sys.exit(...)`.

### C.6 The tests — the contract

**`tests/test_renovate.py` (87 lines, 7 tests)** — all pure, no subprocess:

| Test (`:line`) | Asserts |
|---|---|
| `test_missing_permissions_all_present` `:14` | `permission_gaps` returns `[]` when every required permission matches |
| `test_missing_permissions_flags_gaps` `:26` | gaps are reported as `name=want` strings |
| `test_missing_permissions_no_permissions_key` `:36` | a missing/non-dict `permissions` key yields all-missing, not a crash |
| `test_status_healthy_requires_install_and_full_privileges` `:43` | `healthy` needs BOTH installed and zero gaps |
| `test_render_report_not_installed_points_to_install_url` `:54` | the not-installed report includes the install URL |
| `test_render_report_verifies_mend_app_id` `:64` | app id 2740 renders as verified Mend-hosted |
| `test_render_report_warns_on_unexpected_app_id` `:82` | a different app id renders a ⚠ warning, not a ✓ |

**`tests/test_renovate_dryrun.py` (333 lines, 26 tests)** — the richer contract:

*Report parsing* — `counts_every_dep` `:68`; `extracts_only_pending_updates` `:73`;
`ignores_current_pins` `:84`; `empty_repo` `:90`; `tallies_deps_per_manager` `:96`;
**`distinguishes_extracted_from_pending` `:106`** (the #288/#299 lesson: matched-nothing
≠ matched-and-current); `tallies_deps_per_datasource` `:123`;
**`counts_a_skipped_dep_as_neither_pending_nor_current` `:129`**.

*Rendering* — `render_report_surfaces_what_each_manager_extracted` `:167`;
`group_stats_render_agrees_with_english` `:176` (the "1 dep ," padding bug);
`render_report_lists_the_change` `:309`; `render_report_when_nothing_pending` `:316`;
`pending_update_render_includes_manager_and_file` `:322`.

*Exit codes* — `bare_run_is_always_zero` `:189`; `check_fails_on_pending_update` `:195`;
`check_passes_when_current` `:200`.

*Invocation invariants (these pin the probed facts)* —
**`test_force_disables_clone_submodules` `:205`** and
**`test_dry_run_mode_is_lookup_not_full` `:218`**.

*Token resolution* — `prefers_the_explicit_renovate_name` `:229`;
`falls_back_to_conventional_env` `:234`; `reads_only_the_names_it_declares` `:244`;
`treats_empty_as_absent` `:269`; `env_promotes_token_to_the_name_renovate_reads` `:274`;
`env_omits_token_when_none_available` `:280`.

*Completeness labelling* — **`incomplete_run_is_labelled_a_floor_not_a_total` `:286`**;
`complete_run_has_no_incomplete_warning` `:301`.

**Contract summary:** every test is a pure function over a JSON fixture or an env
dict. **No test executes the renovate binary.** So the suite is fully portable and
needs neither node nor a token to run.

### C.7 Required binaries / env

| Requirement | Pinned? | Where |
|---|---|---|
| `renovate` binary | **yes** — `npm:renovate = "44.13.2"` | `mise.toml:22` |
| node 24 for the task | **yes** — `tools.node = "24"` | `mise.toml:661` |
| `uv` + the `python` project | yes | `run =` line |
| `gh` (status only) | via mise | `renovate.py:65-76` |
| GitHub token | **not required, but the run is a FLOOR without it** | `renovate_dryrun.py:94-100` |

---

## D. The python-library shape — modular at the module seam, monolithic at the CLI

**Separation of concerns inside `renovate_dryrun.py` is clean and already matches
the (config-parsing | execution | reporting) split the port wants:**

| Concern | Functions |
|---|---|
| env / config construction | `resolve_github_token` `:163`, `renovate_env` `:179`, `_FORCE_CONFIG` `:69`, `RENOVATE_ARGS` `:74` |
| execution | `run_renovate` `:193` (the *only* subprocess call) |
| parsing | `parse_report` `:223`, `_tally` `:205`, `_stats` `:215` |
| reporting | `render_report` `:280`, `PendingUpdate.render` `:113`, `GroupStats.render` `:137` |
| policy | `decide_exit_code` `:331` |
| orchestration | `renovate_dryrun_main` `:352` |

Same shape in `renovate.py`: collection (`_gh` `:65`, `_repo_slug` `:79`,
`_installation` `:85`, `_pr_rows` `:116`, `collect_status` `:145`), policy
(`permission_gaps` `:104`, `healthy` `:59`), rendering (`render_report` `:166`),
orchestration (`renovate_status_main` `:206`).

**Public surface (2 CLI subcommands, 2 modules):**
`dotfiles-setup renovate-dryrun [--json] [--check]` ·
`dotfiles-setup renovate-status [--json]`.

**The one monolith is `main.py`** — a single ~1400+-line argparse file where all
~45 subcommands are registered and dispatched through one lambda table
(`:756-777` registration, `:1404-1408` dispatch). The *renovate logic* is not
monolithic; the *CLI aggregator* is. knowledge-base's equivalent is
`kb_setup.cli:main` (`pyproject.toml:9`), so the port inherits the same shape
either way.

**Verdict for the "skill → modular mise task → thin python library" goal:** the
dry-run module ports almost verbatim. It is ~380 lines with one subprocess call,
zero bash, dataclass-based results, a `--json` machine surface, and a
`--check` gate flag — exactly the wrapper shape knowledge-base already uses.

---

## E. What would NOT port

| Item | Why it does not port |
|---|---|
| **The entire `.devcontainer/` surface** | knowledge-base has no devcontainer. Kills: the `devcontainer` manager + its `pinDigests:false` rule (`renovate.json:25-31`), the ubuntu-digest manager (`:136-148`), the `MISE_VERSION` manager (`:149-160`), the `mise-system.toml` `[bootstrap.packages]` deb manager (`:173-184`), and the whole `deb` datasource / `apt-ubuntu-pockets` rule (`:50-61`). |
| **`customDatasources.gcc-latest`** (`:186-191`) + the gcc manager (`:123-135`) + `gcc-sha-repair.yml` | GCC/clang toolchain, jwakely index, kayari `.deb`. Nothing analogous here. |
| **`clang-p2996` git-refs manager** (`:108-122`) | C++ toolchain; needs `docker-bake.hcl`, which does not exist here. |
| **`docker-bake.hcl`, `dockerfile`, `docker-compose` managers** | No Dockerfile, no bake file, no compose file in knowledge-base. |
| **`.chezmoiversion` manager** (`:96-107`) | knowledge-base is not a chezmoi source. |
| **`hk.pkl` schema manager** (`:83-95`) | ✅ **PORTS — VERIFIED, the one custom manager that transfers.** knowledge-base's `hk.pkl` carries the exact URL shape at **`hk.pkl:1`** (`amends "package://github.com/jdx/hk/releases/download/v1.54.0/hk@1.54.0#/Config.pkl"`) and **`hk.pkl:6`** (`import "…/download/v1.54.0/hk@1.54.0#/Builtins.pkl"`). The version appears **twice per URL** on **both** lines, so the #248 two-`matchStrings` requirement applies verbatim — a single-occurrence match would produce the 404 URL `v<new>/hk@<old>.zip`. Port needs only `managerFilePatterns` narrowed to `/(^|/)hk\.pkl$/` (no `hk-common.pkl`/`hk-image.pkl` here). |
| **`DIVE_VERSION` manager** (`:161-172`) | Points at `.github/workflows/image-analysis.yml`, which does not exist here. |
| **`bats-core` group rule** (`:19-24`) | No bats tests here. |
| **`ignoreDeps: ["CC","CXX"]`** (`:78-81`) | Compiler env vars from the C++ toolchain. |
| **`npm` and `cargo` managers** (`:192-201`) | **VERIFIED dead:** `git ls-files \| grep -E "package\.json$\|Cargo\.toml$"` → **0 tracked files**. Control arm: the same pipeline for `pyproject.toml$` → **1**. |
| **`github-actions` manager** | Would be dead on arrival — knowledge-base has **no `.github/` at all**. It only becomes live if the port creates workflows. |
| **`gcc-sha-repair.yml` App-token pattern** | Needs a GitHub App (`REFRESH_APP_ID` + key) that knowledge-base does not have configured. **UNKNOWN** whether the same App could be reused. |
| **`scripts/*.sh`** | Not an issue: **no `.sh` in dotfiles touches Renovate** (control-armed). The renovate path is already zero-bash and satisfies `zero-bash-logic.md` as-is. |
| **`refresh.yml` lock-refresh job** | Devcontainer-lock specific — but see the B.2 warning: the *problem* it solves (Renovate never regenerates a lockfile) **does** port, because knowledge-base has a committed `mise.lock`. |

---

## F. knowledge-base's current state — the gap

### F.1 `.github/` — **does not exist**

`ls /Users/rmanaloto/dev/github/ray-manaloto/knowledge-base/.github` →
`No such file or directory`. Consistent with `.claude/rules/gh-cli-watch.md`:
*"`.github/` does not exist here. There is no `ci.yml`."*

**Zero renovate references repo-wide:** `git -C <kb> ls-files | grep -i renovate`
→ empty. **Control arm:** the same pipeline `grep -c "currency.toml"` → **1**, so
the probe discriminates. Also `git ls-files | grep -c '\.sh$'` → **0**, confirming
the zero-bash invariant holds.

### F.2 What `mise.toml` pins that Renovate would need to understand

All in `[tools]` (block starts `mise.toml:31`):

| Line | Pin | Renovate manager needed |
|---|---|---|
| `:33` | `python = "3.14.6"` | native `mise` |
| `:34` | `uv = "0.11.28"` | native `mise` |
| `:35` | `hk = "1.54.0"` | native `mise` |
| `:36` | `pkl = "0.32.0"` | native `mise` |
| `:37` | `typos = "1.48.0"` | native `mise` |
| `:42` | `"pipx:graphifyy" = { version = "0.9.34", extras = ["all"] }` | **⚠️ the hard one — see F.4** |
| `:46` | `"conda:ffmpeg" = "8.1.2"` | native `mise` (conda backend) — **UNKNOWN** if Renovate's mise manager resolves `conda:` |
| `:47` | `taplo = "0.10.0"` | native `mise` |
| `:48` | `rumdl = "v0.2.40"` | native `mise` — **note the `v` prefix**, the exact shape that broke pixi (`renovate.json:70-76`) |
| `:49` | `gitleaks = "8.30.1"` | native `mise` |
| `:61` | `"github:agent-sh/agnix" = "0.46.0"` | native `mise` (github backend) |
| `:73` | `fnox = "1.32.0"` | native `mise` |
| `:107` | `codex = "0.146.1"` | native `mise` |
| `:108` | `antigravity-cli = "1.1.10"` | native `mise` |

**14 tool pins.** Also present at the repo root: **`mise.lock`** — which per B.2
Renovate's mise manager will **not** regenerate.

### F.3 `pyproject.toml` — deps Renovate could bump

The ONE root `pyproject.toml`:

- `:6` `dependencies = []` — **the `[project]` table is empty**.
- `:25` `[project.optional-dependencies]` → `fetch = ["trafilatura>=2.0"]` —
  **deliberately a floor, not an `==`**, and the comment (`:12-19`) says so
  explicitly because dotfiles consumes this package as a SHA-pinned git dep.
  An `==` here "would export our preference as someone else's constraint."
  ⚠️ **A Renovate `pep621` manager would want to pin this — and doing so would
  violate a documented, reasoned decision.** It needs an explicit ignore rule.
- `:41` `[dependency-groups]` (PEP 735) →
  `dev = ["ruff==0.15.22", "ty==0.0.62", "pytest==9.1.1", "trafilatura==2.1.0"]`
  — **exact pins, safe to bump**, and the comment (`:38-40`) explains why exact is
  correct here (dev groups bind no consumer). **These 4 are the real Renovate
  targets on the python side.**
- `uv.lock` is committed at the repo root.

**Renovate coverage note — resolved by B.3:** dotfiles' `enabledManagers`
(`renovate.json:192-201`) contains **no python manager at all**, and that is
deliberate: **Dependabot** owns Python there (`.github/dependabot.yml:4-6`,
`package-ecosystem: "pip"`, `directory: "/python"`). Porting only `renovate.json`
would leave knowledge-base's four dev pins unmanaged by anything.

Two routes exist; dotfiles picked the second:

- add `pep621` to `enabledManagers` — but it is **UNKNOWN** whether Renovate's
  `pep621` manager reads PEP 735 `[dependency-groups]` (a newer table than
  `[project.optional-dependencies]`). Needs probing, not assuming.
- add a `dependabot.yml` mirroring B.3, but with `directory: "/"` rather than
  `"/python"` — knowledge-base's `pyproject.toml` is at the **repo root**
  (`pyproject.toml:1`), even though its package source lives at
  `python/src/kb_setup` (`pyproject.toml:51-52`).

### F.4 Two conflicts the port must resolve (facts, not recommendations)

1. **`currency.toml` already owns some of this.** knowledge-base has a tool-currency
   engine (`kb_setup.currency`) with tracked entries at
   `currency.toml:12 [tool.graphify]`, `:321 [tool.ffmpeg]`, `:351 [tool.mise]`,
   `:505 [tool.claude-code]`, `:725 [tool.hk]`, `:812 [tool.fnox]`,
   `:851 [tool.skillopt]` — **7 tools**, with `mise run kb-currency-check` /
   `kb-currency`. Renovate and the currency engine would both watch graphify, hk,
   fnox, ffmpeg and mise. Whether that is duplication or defence-in-depth is a
   design call, not a fact I can settle.
2. **`graphifyy` is the one dotfiles refuses to automerge.** `renovate.json:42-49`
   sets `automerge: false, groupName: null` for `graphifyy` with a long rationale
   about silent data loss. In **knowledge-base** graphify is not a dependency —
   it is *the entire substrate* (`"pipx:graphifyy"`, `mise.toml:42`, with
   `extras = ["all"]`). Note the **extras**: `renovate.json` has no rule that
   preserves an `extras = [...]` table form, and `mise.toml:38-41` warns that the
   bracket-in-name form "strands the pin". **UNKNOWN** whether Renovate's mise
   manager rewrites a `{ version = "...", extras = [...] }` inline table
   correctly — this is the highest-risk unknown in the whole port.

---

## Undetermined (explicitly UNKNOWN)

- Contents of the `github>jdx/renovate-config` preset → so **labels, commit-message
  format, and PR-body template are UNKNOWN** (remote preset, not vendored).
- Whether renovate **44.x** still needs `tools.node = "24"` (all probes cited were
  against 43.x).
- Whether Renovate's mise manager handles `conda:` backends, `github:` backends,
  and the `{version, extras}` inline-table form.
- Whether Renovate's `pep621` manager reads PEP 735 `[dependency-groups]`.
- Exact GitHub App secret names beyond `REFRESH_APP_ID`.

**Closed after the first pass** (kept for the record): knowledge-base's `hk.pkl`
*does* carry the `download/v<X>/hk@<X>` shape (`hk.pkl:1`, `:6`) → the hk manager
ports. knowledge-base has **no** `package.json` / `Cargo.toml` → npm+cargo are dead.

## GitHub repos touched

- [ray-manaloto/dotfiles](https://github.com/ray-manaloto/dotfiles) — the source of the Renovate config, workflows, mise tasks, python modules and tests being ported.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the target repo; confirmed absence of `.github/` and any Renovate surface.
- [jdx/renovate-config](https://github.com/jdx/renovate-config) — the preset `renovate.json:4` extends; **not fetched**, hence the UNKNOWN labels/commit-format.
- [renovatebot/renovate](https://github.com/renovatebot/renovate) — the tool itself; its `initRepo`/`initPlatform`/`parse/env.js` internals are cited in `renovate_dryrun.py`'s docstring (read via that docstring, not from source).
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — `graphifyy`, the package carrying the `automerge:false` rule and knowledge-base's core pin.
- [jdx/hk](https://github.com/jdx/hk) — target of the pkl custom manager; pinned in both repos.
- [twpayne/chezmoi](https://github.com/twpayne/chezmoi) — `.chezmoiversion` custom manager (does not port).
- [bloomberg/clang-p2996](https://github.com/bloomberg/clang-p2996) — git-refs custom manager (does not port).
- [wagoodman/dive](https://github.com/wagoodman/dive) — `DIVE_VERSION` custom manager (does not port).
- [jdx/mise](https://github.com/jdx/mise) — `MISE_VERSION` custom manager + the native mise manager whose lockfile limitation is the key porting constraint.
- [prefix-dev/pixi](https://github.com/prefix-dev/pixi) — the `v`-prefix `extractVersion` precedent relevant to knowledge-base's `rumdl = "v0.2.40"`.
- [actions/create-github-app-token](https://github.com/actions/create-github-app-token) — the App-token step in `gcc-sha-repair.yml`.
- [agent-sh/agnix](https://github.com/agent-sh/agnix) — a knowledge-base pin Renovate would manage.

