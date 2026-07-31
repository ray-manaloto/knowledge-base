> ## ⚠️ CALLER'S ANNOTATION — 2026-07-31, added at promotion. Read before the report.
>
> The report below is **verbatim and unedited**, per `docs/research/README.md`.
> Five corrections in four numbered points (item 4 bundles two), found by the
> cold lane reviewing the promotion itself. The
> original text stands beneath so both the claim and its refutation are visible.
>
> 1. **"`kind = \"issue\"` is impossible for hk" is WRONG.** The report reasons
>    from `has_issues: false` to "would 404 on every run". GitHub's issues
>    endpoint serves PRs, and `issues.py` never checks `has_issues`. Measured,
>    three arms: `repos/jdx/hk/issues/1099` (a PR) → **200**; `/issues/1098` (a
>    discussion) → 404; `/issues/999999` → 404. So a watch on a hk PR number
>    resolves. The real constraint is that hk's *tracker* is discussions, which
>    404 permanently. **`currency.toml` already carries the corrected reasoning**
>    — that file is the authority, not this report.
>
> 2. **The premise is superseded.** The report opens with "hk is absent from
>    `currency.toml`". It is not, as of `06e1c73`: a `[tool.hk]` block landed in
>    PR #97, differently worded, with different watch `ref`s. The paste-ready
>    block near the end of the report is therefore a proposal that was adopted in
>    spirit and not verbatim. Read `currency.toml` for what actually shipped.
>
> 3. **`#1099` "reaching this repo" is overstated.** The v1.53.0 note says the
>    deadlock needs `fail_fast = false` **and** "any step with `depends` on it".
>    This repo has the first (`hk.pkl:12`) and, by the very ban under discussion,
>    **zero `depends` edges** — the single occurrence of `depends` in `hk.pkl` is
>    the comment forbidding it (`:152`). So the deadlock could never have fired
>    here; the ban is what made it unreachable. The fix is still the reason the
>    ban is now a *choice* rather than a workaround, which is the load-bearing
>    point, but "matches this repo's exact configuration" is not right.
>
> 4. **Two smaller slips.** `mixed_line_ending` is declared at `hk.pkl:164`, not
>    `:166` (`:169` for `check_merge_conflict` is correct). And "every lint step
>    is globbed" is false — `md_size_budget` (`hk.pkl:237-239`) has no `glob`.

# hk currency research — issue #87

**Date**: 2026-07-31
**Repo**: `ray-manaloto/knowledge-base`
**Question**: hk is pinned at 1.52.0 in `mise.toml` and absent from `currency.toml`.
Upstream `jdx/hk` published v1.54.0. What does tracking it actually require?
**Status**: COMPLETE

---

## 0. Orientation and probe hygiene

### The KB graph does not contain this repo's own config

`mise run kb-query -- "hk lint gate builtins exclusive step"` returned
**327 nodes**, every one from ingested third-party corpora
(`packages/gateway-schema/src/*.ts`, `scripts/manage_categories.py`,
`lib/mix/tasks/pr_body.check.ex`, `frontend/tests/unit/...`). Zero hits on this
repo's `hk.pkl`.

**This is a non-empty result, so it is not a broken-probe case** — the graph
answered, and the answer is "hk config is not in the corpus". That is consistent
with `.claude/rules/`-recorded memory *"Toolchain docs absent from the corpus"*
(26 pins, only graphify is a tool we run). Orientation therefore had to come
from reading the repo directly, which is what the rest of this report does.

### Control arms run

Every negative claim below is armed. The arms actually executed:

| Probe | Control arm run alongside | Result |
|---|---|---|
| `grep -rn '1\.52\.0' hk.pkl mise.toml currency.toml` | `grep -rn 'hk' mise.toml` → 3 hits | probe discriminates |
| `grep -n 'default_branch\|fail_fast\|min_hk_version' hk.pkl` | `grep -n '^hooks' hk.pkl` → `242:hooks {` | probe discriminates |
| `grep -rn 'hk' currency.toml` → 1 hit (a comment) | `grep -cn 'graphify' currency.toml` → 34 | probe discriminates |

**Every line number in this report was printed by `grep -n`**, never counted by
eye off a `sed`/`head` window.

---

## 1. What changed in 1.53.0 and 1.54.0?

Source: `gh release view v1.53.0 -R jdx/hk` and `gh release view v1.54.0 -R jdx/hk`
(both `rc=0`, full notes captured). Notes were substantial, not thin — no
merged-PR cross-check was needed to establish *what* changed, though every item
below carries its upstream PR number from the notes themselves.

### v1.53.0 — "Faster config loading and safer stashing" (2026-07-23)

**Added**

- `cargo_deny` builtin (#1081) — runs cargo-deny for Rust dependency policy.

**Fixed**

- **Dependents no longer hang after a failed dependency** (#1099). *"With
  `fail_fast = false`, a failed step returned without marking its dependency
  watch channel as done, so any step with `depends` on it waited forever and the
  run hung."* `fail_fast = true` behaviour unchanged. Fixes discussion #1098.
- **No stashing when a hook has no steps to run** (#1106). A hook resolving to
  zero steps with a dirty worktree stashed and returned early *before* the
  restore ran — leaving a dangling stash and a stripped working tree, each retry
  piling on another stash. Stash-restore failures now also report the
  `~/.local/state/hk/patches/*.patch` backup path. Fixes #1105.

**Changed**

- **Hardened Git invocations against argument injection** (#1101). `--end-of-options`
  before untrusted revisions in `merge-base`, `rev-parse`, `ls-tree`, and diff
  ranges; `ls-remote` shell interpolation replaced with argv. Prevents
  repo-config-controlled refs (`hk.pkl` `default_branch`, `--from-ref`/`--to-ref`)
  and hyphen-prefixed branch names being misread as options.
  **Requires Git 2.30+ for `rev-parse --end-of-options`.**

**Performance**

- Resolved config cached in-process (#1104) — warm-cache `hk validate` on a large
  config 102.60 ms → 55.21 ms (46%).
- Final status snapshot skipped outside debug logging (#1102) — no-op benchmark
  over a 6,156-file repo with 4,000 modified files ~40% faster on both backends.

### v1.54.0 — "17% smaller, up to 31% faster" (2026-07-31, i.e. today)

Headline table (published `x86_64-unknown-linux-gnu` binary, v1.53.0 → v1.54.0):
archive 8.19→7.06 MB, binary 22.01→18.27 MB, startup 2.21→1.52 ms, builtins
loading 2.31→1.62 ms, config validation 3.69→2.94 ms, representative
`check --all` 14.62→13.47 ms.

**Added**

- **`check_failed_files` step setting** (#1123) — opt-in. Runs a file-listing
  command (`check_list_files` or `check_diff`) over the whole job first, then
  runs the detailed `check` only on the paths reported failing. Requires `check`
  plus at least one of `check_diff`/`check_list_files`, validated at
  `hk validate` time.
- **Command effect declarations** (#1121) — each command's usage spec declares
  read/modify/destructive. `check`, `fix`, `run`, `test` deliberately
  unclassified (they execute arbitrary `hk.pkl` steps). Docs-surface change.

**Fixed**

- `tombi-format` no longer prints noise on clean runs (#1117).
- `oxlint` no longer errors on unmatched glob patterns (#1119).

**Performance**

- Faster `mixed-line-ending` and `check-merge-conflict` (#1115) — `memchr` byte
  scanning instead of per-byte iteration; block copies on the `mixed-line-ending`
  fix path. Up to ~2.5x faster checks, ~2.2x faster fixes on large files.
- PGO/BOLT-optimized Linux binary (#1136) — **`x86_64-unknown-linux-gnu` only**.
  Also: stripped/slimmed binary, `panic = "abort"`, Tokio worker threads capped
  at 16.

> The v1.54.0 notes carry the footer *"AI-assisted — Tool: Codex; model:
> openai/gpt-5"*. Recorded as provenance, not as a reason to distrust the
> content — every claim above is cross-checkable against the linked PRs.

---

## 2. Does any of it reach THIS repo's config?

Read first: `hk.pkl` (259 lines). Config surface, all line numbers from `grep -n`:

- `hk.pkl:1` — `amends "package://github.com/jdx/hk/releases/download/v1.52.0/hk@1.52.0#/Config.pkl"`
- `hk.pkl:6` — `import "package://github.com/jdx/hk/releases/download/v1.52.0/hk@1.52.0#/Builtins.pkl"`
- `hk.pkl:9` — `min_hk_version = "1.49.0"`
- `hk.pkl:12` — `fail_fast = false`
- `hk.pkl:242` — `hooks {`
- Builtins in use (`hk.pkl:159-173, 256`): `typos`, `rumdl`, `rumdl_format`,
  `trailing_whitespace`, `newlines`, `mixed_line_ending`, `gitleaks`,
  `detect_private_key`, `check_merge_conflict`, `check_added_large_files`,
  `pkl`, `taplo`, `taplo_format`, `check_conventional_commit`.
- String-command seams (`hk.pkl:175-238`): `uv run ruff check/format`,
  `uv run ty check`, `uv run kb-setup no-lint-skip`, `agnix . --strict`,
  `uv run kb-setup md-budget`.
- `exclusive = true` used for ordering (e.g. `hk.pkl:183` on `ruff_format`);
  `depends` deliberately absent (dotfiles #268).

`grep -n 'default_branch' hk.pkl` → **no match** (control arm `^hooks` → 242, so
the probe discriminates). This repo does not set `default_branch`.

### Verdict per change

| Release | Change | Reaches this repo? | Why |
|---|---|:--:|---|
| 1.53.0 | **#1099 dependents hang after failed dependency** | **YES — and it is the big one** | `hk.pkl:12` sets `fail_fast = false`, the exact trigger condition. See below. |
| 1.53.0 | #1106 no stashing when a hook has no steps | **YES (latent)** | A hook can resolve to zero steps here (every lint step is globbed; a commit touching only excluded paths can select nothing). Bug cost is a dangling stash + stripped worktree. |
| 1.53.0 | #1101 Git argument-injection hardening | **YES, and satisfied** | Host `git version 2.50.1 (Apple Git-155)` ≥ the 2.30 floor `rev-parse --end-of-options` needs. No `default_branch` set here, so the config-controlled-ref vector is narrow, but `--from-ref`/`--to-ref` still apply. |
| 1.53.0 | #1104 config cached in-process | YES (perf only) | Every `hk run check --all` benefits. |
| 1.53.0 | #1102 status snapshot gated behind debug | YES (perf only) | Benefit scales with worktree size; this repo is small, so expect little. |
| 1.53.0 | #1081 `cargo_deny` builtin | **NO** | No Rust; `Cargo.toml` absent. |
| 1.54.0 | #1115 faster `mixed_line_ending`, `check_merge_conflict` | **YES (perf only)** | Both builtins are in use — `hk.pkl:166` and `hk.pkl:169`. |
| 1.54.0 | #1123 `check_failed_files` | **NO (opt-in, unused)** | New step key; nothing here sets it. Available if a future step wants narrowed diagnostics. |
| 1.54.0 | #1121 command effect declarations | **NO (docs surface)** | `check`/`fix`/`run` — the ones this repo drives — are deliberately left unclassified. |
| 1.54.0 | #1117 `tombi-format` quiet | **NO** | This repo uses **`taplo`/`taplo_format`** (`hk.pkl:172-173`), not tombi. |
| 1.54.0 | #1119 `oxlint` unmatched patterns | **NO** | `oxlint` not used. |
| 1.54.0 | #1136 PGO/BOLT binary | **NO on this host** | Artifact is `x86_64-unknown-linux-gnu` only; this machine is `arm64` Darwin. The headline speed table is measured on that Linux binary and **does not transfer to this Mac**. |

### The finding that matters: 1.53.0 #1099 retires the `depends` prohibition's cause

`hk.pkl:151-153` documents the repo's ordering doctrine:

> `exclusive` (a barrier), NOT `depends` (a failed dep deadlocks hk — dotfiles #268)

That prohibition is also encoded in `.claude/rules/long-running-command-hangs.md`
(rule 5: *"hk never releases a dependent whose dependency FAILED, so `depends` +
`fail_fast = false` deadlocks"*) and in dotfiles' `hk.pkl` `no_hk_depends` step.

**hk 1.53.0 #1099 fixes exactly that**, and names the same two conditions: a
failed step under `fail_fast = false`. This repo sets `fail_fast = false` at
`hk.pkl:12`, so it sits precisely in the affected configuration.

Two consequences, and they point in opposite directions — this is a
**native-first judgment call for a human**, not something a currency bump decides:

1. Bumping to ≥1.53.0 removes the *upstream defect* that motivated the ban.
2. It does **not** automatically make `depends` the right choice. `exclusive`
   works today, is deployed, and the doctrine is cross-repo (dotfiles enforces
   `no_hk_depends` mechanically). Changing it is a separate, reviewable decision
   with its own blast radius — and `tool-currency-and-native-first.md` rule 5
   requires syncing every describing doc in the same change (here: `hk.pkl`'s
   comment, the KB rule file, dotfiles' rule + its `no_hk_depends` step).

**What is certain and low-risk**: whether or not `depends` is ever adopted,
≥1.53.0 is strictly safer for the config this repo already has.

### `min_hk_version` is not a blocker

`hk.pkl:9` declares `min_hk_version = "1.49.0"` — a floor, not a ceiling. 1.53/1.54
satisfy it. No edit required for a bump.

---

## 3. Does KB need a `hk_version_parity` equivalent?

**Pkl file count — measured, not assumed.**

```
$ ls *.pkl && find . -name '*.pkl' \
    -not -path './.venv/*' -not -path './sources/*' \
    -not -path './graphify-out/*' -not -path './.git/*' -not -path './raw/*'
hk.pkl
./hk.pkl
```

**1 `.pkl` file: `hk.pkl`.** dotfiles carries three (`hk.pkl`, `hk-common.pkl`,
`hk-image.pkl`), which is why its `hk_version_parity` step exists — three files
whose hk pins can drift apart from each other.

**Verdict: a dotfiles-shaped `hk_version_parity` (pkl-file ↔ pkl-file) is NOT
applicable here. There is only one pkl file, so there is no pkl-to-pkl pair to
compare.**

### But there IS a drift surface, and it is a different one

The hk version is written in **three places across two files**:

| Location | Text |
|---|---|
| `mise.toml:35` | `hk = "1.52.0"` |
| `hk.pkl:1` | `amends "package://github.com/jdx/hk/releases/download/v1.52.0/hk@1.52.0#/Config.pkl"` |
| `hk.pkl:6` | `import "package://github.com/jdx/hk/releases/download/v1.52.0/hk@1.52.0#/Builtins.pkl"` |

(All three printed by `grep -rn '1\.52\.0' hk.pkl mise.toml currency.toml`;
`currency.toml` returned no version hit — see §4.)

So a bump is **not** a one-line `mise.toml` edit: the pkl package URLs pin the
same version twice more, and a `mise.toml`-only bump would leave the binary at
1.54.0 while the config still amends the 1.52.0 `Config.pkl`/`Builtins.pkl`
schemas. That is a real, silent drift axis — the *same class of defect*
dotfiles' check guards, along a different axis (binary↔schema rather than
pkl↔pkl).

**Recommendation**: KB does not need dotfiles' check as written, but the
**binary-pin ↔ pkl-package-URL** parity is worth a gate. Two options, cheapest
first:

- **Cheapest (recommended)**: no new hk step at all — `currency.toml`'s
  `[tool.hk]` entry (§4) already declares `mise_key` and `binary`, so
  `kb-currency-check` reports installed-vs-pin drift every session. Add the
  pkl-URL parity as a small assertion in an existing `kb_setup` check if it
  proves to recur.
- If a gate is wanted now: a `kb_setup` function comparing the `mise.toml` hk pin
  against both `hk.pkl` package URLs, surfaced as one more `uv run kb-setup …`
  hk step (zero-bash-logic shape, same as `no-lint-skip`/`md-budget`).

**I did not implement either** — this task is research-only.

---

## 4. What does a `[tool.hk]` entry look like?

Schema read from `python/src/kb_setup/currency/config.py` (240 lines). The full
field set on `ToolSpec` (`config.py:53-111`): `name` (the table key), `mise_key`,
`binary`, `pypi`, `github`, `extras`, `extra_probes`, `manifest`, `artifact`,
`artifacts`, `stamp`, `expected`, `version_pattern`, `os`, `watch`, `docs_watch`.

`config.py:186-190` — a table needs **either** `mise_key` (mise-managed) **or**
`expected` (self-managed). hk **is** pinned in `[tools]`, so it takes `mise_key`
and must NOT take `expected` (that is mise's and claude-code's shape, for tools
that self-update out of band and cannot honestly be pinned).

### Field-by-field: verified vs guessed

| Field | Value | Verified how |
|---|---|---|
| table key | `hk` | — |
| `mise_key` | `"hk"` | **Verified.** `sync.py:126-136` looks the key up in `mise.toml`'s `[tools]` table; `mise.toml:35` is literally `hk = "1.52.0"`, so the key is the bare string `hk` (not a backend-prefixed one like `pipx:graphifyy`). |
| `binary` | `"hk"` | **Verified redundant-but-explicit.** `config.py:203` — `binary=_str("binary") or name`, so it defaults to the table key. Stating it matches the graphify/ffmpeg/mise entries' house style. |
| `github` | `"jdx/hk"` | **Verified.** `config.py:145` `tracks_upstream` = `bool(pypi or github)`; `github` alone selects the GitHub-releases source, which is where the notes in §1 came from. |
| `pypi` | *omitted* | **Verified appropriate.** hk is a Rust binary published as GitHub release archives (§1 asset list: `hk-aarch64-apple-darwin.tar.gz` etc.), not a PyPI package. |
| `version_pattern` | *omitted* | **Verified empirically — see below.** |
| `os` | *omitted* | **Reasoned, not measured.** hk sits in the ordinary `[tools]` table (`mise.toml:31-35`), unlike graphify/ffmpeg which declare `os = ["macos"]` because their installs are host-only. Omitting means "expected on every host", which is correct for hk. |
| `expected` | *omitted* | **Verified.** Would switch hk onto the self-managed path (`config.py:113-121`) and is wrong for a mise-pinned tool. |
| `extras` / `extra_probes` / `manifest` / `artifact` / `artifacts` / `stamp` / `docs_watch` | *omitted* | **Verified appropriate.** `config.py:56-59`: every field beyond `name`/`mise_key` switches a check ON when present and is simply absent otherwise. hk has no Python extras, no source manifest here, and produces no build artifact to stamp. |
| `watch` | two `kind = "local"` items | **Verified that `kind = "issue"` is unusable — see below.** |

### `version_pattern` is NOT needed — verified, not assumed

```
$ hk --version
hk 1.52.0
rc=0
```

`sync.py:248-249` is the fallback when no pattern is set:

```python
parts = text.split()
return parts[-1].lstrip("v") if parts else ""
```

`"hk 1.52.0".split()` → `["hk", "1.52.0"]` → last field `"1.52.0"`. That is the
bare version, correctly.

This is exactly the conventional `<name> <version>` output `sync.py:218-222`
describes as the case the heuristic is *right* for. Contrast the two entries that
DO need a pattern, and why:

- `mise --version` → `2026.7.16 macos-arm64 (2026-07-29)` — last field is the
  build **date**, so `currency.toml:201` sets `version_pattern = '^v?(\d+\.\d+\.\d+)'`.
- `claude-code` likewise at `currency.toml:265`.

hk prints two fields. **Adding a `version_pattern` here would be adding an
unnecessary failure surface**: `sync.py:241-247` returns `""` on a non-matching
pattern and the caller renders that as "could not read", so a pattern that ever
stops matching turns into a standing could-not-check.

### `kind = "issue"` watch items are IMPOSSIBLE for hk — verified with a control arm

This was a surprise, so it was cross-checked by a second route before being
reported (`probes-need-a-control-arm.md` rule 7).

```
$ gh issue list -R jdx/hk --state open --limit 3
the 'jdx/hk' repository has disabled issues        # exit 1
```

Cross-check via the API, with a control arm on a repo known to have issues on:

```
$ gh api repos/jdx/hk --jq '{has_issues,has_discussions,open_issues_count}'
{"has_discussions":true,"has_issues":false,"open_issues_count":1}

$ gh api repos/ray-manaloto/knowledge-base --jq '{has_issues,has_discussions}'
{"has_issues":true,"has_discussions":false}        # control arm — probe discriminates
```

Both routes agree: **jdx/hk has Issues DISABLED and uses Discussions.** That is
consistent with the release notes themselves, which cite *"discussion #1098"*,
*"discussion #1116"*, *"discussion #1122"*.

Third probe, on a specific referenced number:

```
$ gh api repos/jdx/hk/issues/1105     → 404 Not Found
$ gh api repos/jdx/hk/pulls/1099      → {"merged":true,"state":"closed",
                                         "title":"fix(step): unblock dependents
                                         after failed dependency"}
```

So PR numbers resolve; issue numbers do not. (#1099 merged also independently
confirms the §1 deadlock-fix claim.)

**Why this decides the TOML block**: `issues.py:81-93` fetches a `kind = "issue"`
item with `gh api repos/<repo>/issues/<ref>`, and `issues.py:109-111` turns any
error into `Observation(key=..., error=err)`. On jdx/hk that call 404s
permanently. Per this repo's documented doctrine (`CLAUDE.md`: *"a tracked issue
whose lookup failed blocks gate 5 rather than passing it"*), every run would
carry a standing unreadable watch item and the auto-bump path would be blocked
forever — failing closed on an ambiguity that is not real.

`issues.py:96-103`: `kind = "local"` observes as itself with no network call.
**That is the only usable watch kind for hk**, and it is the right one anyway,
since what is worth re-reading here is our own doctrine decision, not an upstream
ticket.

### Paste-ready block

Append to `currency.toml`. Nothing else in the file needs to change.

```toml
# ---- hk: the lint/hook engine every gate in this repo runs through ------------
#
# `mise run lint` is `hk run check --all`, so hk's behaviour IS the gate. Pinned
# at mise.toml:35; the same version is ALSO written twice as a pkl package URL
# (hk.pkl:1 `amends`, hk.pkl:6 `import`), so a bump is a three-line edit across
# two files, not a one-line pin bump. A mise.toml-only bump leaves the binary
# ahead of the Config.pkl/Builtins.pkl schemas it amends.
#
# No `pypi`: hk ships as GitHub release archives, not a Python package.
# No `version_pattern`: `hk --version` prints `hk 1.52.0`, two fields, so the
# engine's default last-whitespace-field heuristic reads it correctly (verified
# 2026-07-31). Adding a pattern would only add a way for it to stop matching.
# No `os`: hk is in the ordinary `[tools]` table and applies on every host,
# unlike graphify/ffmpeg whose installs are Mac-host-only.
[tool.hk]
mise_key = "hk"
binary = "hk"
github = "jdx/hk"

# jdx/hk has ISSUES DISABLED and uses Discussions (verified 2026-07-31:
# `gh api repos/jdx/hk` -> has_issues=false, has_discussions=true, against a
# control arm on a repo with issues on). A `kind = "issue"` item here would 404
# on every run and stand as a permanent unreadable watch, blocking the
# unambiguous-bump gate forever. Every hk watch item must therefore be `local`.
[[tool.hk.watch]]
kind = "local"
ref = "depends-ban-motivating-defect-fixed-upstream-in-1.53.0"
note = """hk.pkl:151-153 forbids `depends` in favour of `exclusive` because a
failed dependency deadlocks hk (dotfiles #268); the same ban is in
`.claude/rules/long-running-command-hangs.md` rule 5 and in dotfiles' own
`no_hk_depends` hk step.

hk 1.53.0 #1099 ("fix(step): unblock dependents after failed dependency", merged
— verified via `gh api repos/jdx/hk/pulls/1099`) FIXES exactly that, and names
the same two conditions: a failed step under `fail_fast = false`. This repo sets
`fail_fast = false` at hk.pkl:12, so it sat precisely in the affected config.

This does NOT auto-retire the ban. `exclusive` works, is deployed, and the
doctrine is cross-repo. Adopting `depends` is a separate reviewable decision
whose blast radius includes dotfiles' `no_hk_depends` step and two rule files
that must be updated in the SAME change (tool-currency-and-native-first.md
rule 5). Carried here so the question is re-asked, not quietly forgotten.

On each bump: confirm the fix is still present, and decide explicitly whether
`exclusive` remains the chosen mechanism. Recording "still exclusive, on
purpose" is a valid outcome."""

[[tool.hk.watch]]
kind = "local"
ref = "pkl-package-url-must-be-bumped-with-the-mise-pin"
note = """The hk version lives in THREE places: mise.toml:35 (`hk = \"1.52.0\"`),
hk.pkl:1 (`amends \"package://…/v1.52.0/hk@1.52.0#/Config.pkl\"`) and hk.pkl:6
(`import \"package://…/v1.52.0/hk@1.52.0#/Builtins.pkl\"`).

This repo has exactly ONE .pkl file, so dotfiles' `hk_version_parity` step
(which guards pkl-to-pkl drift across its three pkl files) does not port. The
drift axis here is different: binary pin vs pkl package URL. Bumping only
mise.toml runs a 1.54.0 binary against 1.52.0 schemas.

hk.pkl:9 `min_hk_version = \"1.49.0\"` is a FLOOR and needs no edit on a bump.

Re-check on each bump that all three lines moved together:
`grep -rn '<old-version>' hk.pkl mise.toml` must return nothing."""
```

**Verified against the schema**: `mise_key`, `binary`, `github`,
`[[tool.hk.watch]]` with `kind`/`ref`/`note` — all read off `config.py:53-111`
and `config.py:158-217`, and the omissions justified from `config.py:56-59`.
**Guessed / reasoned rather than measured**: only the *omission* of `os` (hk is
cross-platform and this repo has no CI, so there is no second host to observe)
and the editorial content of the two `note` bodies.

**Not run**: `mise run kb-currency` (it writes a report — explicitly out of
scope). So the block above is schema-verified but has **not** been executed
end-to-end by the engine. That is a "could not check here", not a green.

---

## Summary — what tracking hk actually requires

1. **Add `[tool.hk]` to `currency.toml`** (block above). This is the whole of the
   tracking work; the engine needs no change (`config.py:3-7` — adding a tool "is
   a config edit, not an engine change").
2. **Know that a bump is a 3-line edit across 2 files**, not a `mise.toml` pin
   bump: `mise.toml:35` + `hk.pkl:1` + `hk.pkl:6`.
3. **No `hk_version_parity` port.** 1 pkl file here vs dotfiles' 3. The real
   drift axis is binary↔pkl-URL, covered by the second watch item above.
4. **The bump itself is low-risk and worth doing.** Of the twelve changes across
   1.53/1.54, the ones that reach this config are one correctness fix that
   matches this repo's exact configuration (#1099, `fail_fast = false`), one
   latent stash-safety fix (#1106), one security hardening whose Git floor this
   host already meets (#1101, git 2.50.1 ≥ 2.30), and four perf improvements.
   **Nothing is breaking**; `min_hk_version = "1.49.0"` is satisfied.
5. **Do not quote the v1.54.0 headline speed numbers for this machine.** They are
   measured on the PGO/BOLT `x86_64-unknown-linux-gnu` binary (#1136); this host
   is `arm64` Darwin and gets none of that pipeline.
6. **One judgment call is now open, and it is a human's**: 1.53.0 removed the
   upstream defect behind the cross-repo `depends` ban. Whether to change the
   doctrine is a separate reviewable decision, captured as a watch item rather
   than acted on.

**Scope discipline**: no tracked file was modified. `mise run kb-currency` was
not run. This report is the only artifact written.

---

## GitHub repos touched

- [jdx/hk](https://github.com/jdx/hk) — the subject: release notes for v1.53.0 and v1.54.0, the merged PR #1099, and the repo metadata proving Issues are disabled in favour of Discussions.
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — this repo; read `hk.pkl`, `mise.toml`, `currency.toml`, and `python/src/kb_setup/currency/{config,sync,issues}.py` to derive the schema and the drift surface. Issue #87 is the task.
- [ray-manaloto/dotfiles](https://github.com/ray-manaloto/dotfiles) — the sibling carrying `hk_version_parity` and `no_hk_depends`; consulted (via its `CLAUDE.md`/rules in loaded context, not cloned) to establish why that check exists and whether it ports here.
- [EmbarkStudios/cargo-deny](https://github.com/EmbarkStudios/cargo-deny) — named only as the tool behind hk 1.53.0's new `cargo_deny` builtin; assessed as not-applicable (no Rust here). No source read.
