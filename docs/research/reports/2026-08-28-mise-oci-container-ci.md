# mise OCI + mise-first container bootstrap + GHA — research report

Read-only research lane. No writes to this repo's tracked files or git state.
Version used throughout: `mise 2026.8.14 macos-arm64` (`mise exec -- mise --version`,
measured this session). All facts below are cited to files under
`sources/mise/docs/` (the pinned mise clone) or live probes (`mise exec`, `gh api`),
each labeled.

## Answer (headline)

**Yes, "mise oci features" are real and exactly what Ray described**: `mise oci
build`/`run`/`push` (experimental, `sources/mise/docs/cli/oci.md:8,14`) builds
a per-tool-layered OCI image straight from `mise.toml` — no Dockerfile needed at
all for the tool layer. A **mise-first bootstrap** is native too: `mise install`
+ `mise run <task>` is the whole install step, and CI-friendly bootstrapping has
a first-class generator (`mise generate bootstrap`). GHA has an official action
(`jdx/mise-action`, latest `v4.3.0`, published 2026-08-25) with `install: true`.
Headless Claude Code auth for a container is `CLAUDE_CODE_OAUTH_TOKEN` from
`claude setup-token` — already documented in this repo's own `kb-review`
SKILL.md. Plugin marketplace add in a script is non-interactive via `claude
plugin marketplace add <owner/repo>` / `claude plugin install <name>@<mp> --yes`.
Everything below is cited; four items are marked null-with-arm (never claimed
positive without a probe).

---

## 1. What "mise oci features" are

Source: `sources/mise/docs/cli/oci.md` (CLI reference) and
`sources/mise/docs/dev-tools/mise-oci.md` (full doc), both pinned at the repo's
mise clone.

- **`mise oci build`** (`cli/oci.md:20`, `mise-oci.md:82-107`) — turns the
  current `mise.toml` into an OCI image layout on disk (`./mise-oci/` by
  default), **one layer per installed tool**, plus base image layers, the mise
  binary, `[bootstrap.packages]`, `[dotfiles]`, and a synthesized
  `/etc/mise/config.toml`. Bumping one tool's version invalidates only that
  tool's content-addressable layer (`mise-oci.md:6-13,78-80`) — the OCI-native
  answer to Dockerfile layer-cache invalidation.
- **`mise oci run`** (`mise-oci.md:108-146`) — builds (or reuses) the layout and
  runs a command inside it via podman (preferred) or docker; needs one of those
  engines installed (`mise-oci.md:145-146,458-459`) — mise ships **no built-in
  container runtime**.
- **`mise oci push`** (`mise-oci.md:148-241`) — pushes to any OCI Distribution
  v2 registry with mise's **own built-in registry client** — no skopeo/crane/
  docker daemon required. Layer reuse against the destination ref (or
  `--cache-from`) means repeat pushes of a mostly-unchanged toolset transfer
  almost nothing (`mise-oci.md:159-186`). Auth reuses docker/podman credential
  sources (`~/.docker/config.json`, credential helpers) — `docker login
  ghcr.io` is sufficient setup (`mise-oci.md:223-240`); ghcr.io needs a
  `write:packages`-scoped token.
- **Gate**: this is **experimental** — requires `mise settings experimental=true`
  or `MISE_EXPERIMENTAL=1` (`cli/oci.md:14-16`, `mise-oci.md:15-25`). This
  repo already sets `experimental = true` globally in `mise.toml` `[settings]`
  (confirmed by direct read of that section during this session), so no extra
  flag would be needed if this repo drove the build.
- **`[oci]` config section** (`mise-oci.md:242-334`): `from`, `tag`, `workdir`,
  `entrypoint`, `cmd`, `user`/`user_id`/`group_id`, `mount_point`, `[[oci.copy]]`
  (bake host files/dirs into the image), `[oci.env]` (image-only env, does not
  leak into `MISE_*`), `[oci.labels]`. `[bootstrap.packages]` (`apt:`/`apk:`
  entries) and `[dotfiles]` are applied natively to OCI builds too
  (`mise-oci.md:295-334`) — the declarative parts of `mise bootstrap`, ported to
  image builds.
- **Backend coverage** (`mise-oci.md:373-384`): `core, aqua, cargo, npm, go,
  pipx, github, gitlab, forgejo, ubi, spm, http, s3, gem, conda, dotnet` are all
  supported as per-tool layers. **`asdf`/`vfox` are explicitly NOT supported**
  (their install scripts can write outside the per-version dir, breaking the
  one-layer-per-tool invariant) — irrelevant here since this repo's `mise.toml`
  pins are all `npm:`, `pipx:`, `conda:`, or first-party-core tools (`uv`, `python`).
- **Base image**: default `debian:bookworm-slim`, **glibc-based on purpose** —
  Alpine/musl breaks most prebuilt binaries mise installs (node, python wheels)
  (`mise-oci.md:339-345`).
- **Cross-platform caveat, directly relevant to this Mac**: OCI images are
  linux-targeted; building `mise oci build` **on macOS embeds host-native
  (arm64 macOS) binaries** for mise itself and every tool layer, which fail
  with `Exec format error` inside a linux container (`mise-oci.md:414-424`).
  mise warns on this mismatch. **The build must run on a Linux host or inside a
  Linux container** (`docker run -v $PWD:/src -w /src debian mise oci build`
  works per the doc) — i.e. a GHA `ubuntu-latest` runner is the natural place
  to actually run `mise oci build`, not this Mac.
- **`mise generate` family** (`sources/mise/docs/cli/generate.md:11-18`) has
  siblings worth knowing about but distinct from `oci`: `mise generate
  bootstrap` (a standalone install-mise script for CI, see §2),
  `mise generate devcontainer`, `mise generate github-action` (see §3),
  `mise generate task-docs`/`task-stubs`/`tool-stub`. **None of these is
  `mise generate docker`/`dockerfile`** — there is no such subcommand; `mise
  oci build` is the image-producing path, not `generate`.

**Control arm**: `tasks` (a plain mise concept, not oci-specific) also hits
grep for "generate"/"docker" incidentally in doc cross-links, confirming the
search terms aren't over-narrow — but the *positive* claims above are all
anchored to the two files' own headings/subcommand lists, not to incidental
mentions. `mise --version` and `mise ls-remote node` (control below) both ran
and returned real output, so the CLI itself is live in this environment.

---

## 2. A mise-first bootstrap

- **`claude-code` via mise's npm backend — CONFIRMED, control-armed.**
  `mise exec -- mise ls-remote npm:@anthropic-ai/claude-code` returned a real,
  ascending version list ending `2.1.245, 2.1.246, 2.1.247, 2.1.248, 2.1.250`
  (probe run this session). Control arm: `mise exec -- mise ls-remote node`
  also returned a real list (`26.7.0, 26.8.0, 26.8.1`) — the npm-backend path
  discriminates real registry data from a broken/empty query, so the
  claude-code hit is trustworthy, not a null rendered as a version list.
  mise's `npm:` backend needs **no node installed** by default — it queries the
  npm registry directly over HTTP and installs via mise's embedded `aube`
  package manager (`sources/mise/docs/dev-tools/backends/npm.md:8-19`). This
  repo's own `mise.toml` (read directly, ~line 170-185) already pins
  `"npm:@openai/codex" = "0.150.1"`, `antigravity-cli = "1.1.22"`,
  `"npm:ctx7"`, `"npm:firecrawl-cli"` the same way — `"npm:@anthropic-ai/claude-code"
  = "2.1.250"` is the direct-precedent line for a container `mise.toml`, exact
  pin per this repo's own `pin = true` / "Always pin to the LATEST version"
  standing rule (memory: `always-pin-to-the-latest-version.md`).
- **uv + python**: this repo's own `pyproject.toml`/`mise.toml` `[deps.uv]`
  block (`auto = true`, `run = "uv sync --locked"`) is the exact pattern for a
  container that needs the same Python toolchain — `mise install` resolves the
  pinned `uv`/`python` tools, then the `[deps.uv]` hook runs `uv sync --locked`.
- **codex / ctx7 / firecrawl CLIs as `npm:`/`pipx:` pins**: already proven in
  this repo's own `mise.toml` (cited above) — no new mechanism needed, same
  `npm:<pkg> = "<version>"` shape covers a marketplace-plugin dependency CLI.
- **Zero-shell-logic bootstrap**: `mise install && mise run <task>` is the
  whole bootstrap surface; per this repo's own `zero-bash-logic.md`, no
  install-time bash is needed because every recurring step is already a mise
  task backed by python. A container `Dockerfile` therefore reduces to: base
  image → install `mise` itself (curl-pipe-sh, or `mise generate bootstrap`,
  see below) → `COPY mise.toml` (+ lockfile) → `RUN mise install`. **`mise oci
  build` goes one step further and skips the Dockerfile's tool-install RUN
  layers entirely** — it builds those layers itself, natively, from the same
  `mise.toml` (§1).
- **`mise generate bootstrap`** (`sources/mise/docs/continuous-integration.md:25-45`):
  generates a committed `./bin/mise` script that installs and runs the pinned
  mise version, as an alternative to `curl https://mise.run | sh`. Honors
  `MISE_VERSION`/`MISE_INSTALL_PATH`. This is the CI-idiomatic way to pin
  *mise's own* version inside a Dockerfile `RUN` step without a floating
  curl-pipe.
- **Where a plain Dockerfile fits vs `mise oci build`**: two viable paths, not
  mutually exclusive —
  1. **Traditional Dockerfile + `mise install`** (`sources/mise/docs/mise-cookbook/docker.md:1-34`,
     directly documented): `FROM debian:13-slim`, `apt-get install` the few
     system deps mise itself can't provide (`curl git ca-certificates
     build-essential`), `curl https://mise.run | sh`, `ENV PATH=/mise/shims:$PATH`,
     then at build or run time `mise install`. This is the doc's own worked
     example.
  2. **`mise oci build`** (§1): no Dockerfile at all for the tool layer — the
     `[oci]` section of `mise.toml` plus `[[oci.copy]]` (to bake in e.g. a
     wheel or the marketplace repo checkout) replaces it. Requires a Linux
     build host (GHA runner).

  Given this repo's zero-bash-logic stance and Ray's explicit ask ("use mise
  oci features"), **path 2 is the fit** — it needs no Dockerfile, and the
  per-tool-layer cache behavior directly serves "rebuild fast when only the
  plugin CLI version bumped."

---

## 3. GHA workflow

- **`jdx/mise-action`** — **latest `v4.3.0`, published 2026-08-25T10:08:22Z**
  (`gh api repos/jdx/mise-action/releases/latest`, probed this session — real
  API response, not cached). The CI doc's example (`continuous-integration.md:64-94`)
  pins `jdx/mise-action@v3` with `version`, `install: true` (default),
  `cache: true`, `experimental: true`, and an inline `mise_toml:` block — v4 is
  a newer major than the doc's own worked example, so cite the doc's *shape*
  (inputs) but pin `@v4.3.0` in any new workflow, not `@v3`.
- **(a) Build the image**: two options per §1/§2 — either a GHA job on
  `ubuntu-latest` running `mise oci build` (needs `MISE_EXPERIMENTAL=1` unless
  already set in the repo's `mise.toml`, and — per the cross-platform caveat —
  **must run on a Linux runner**, which `ubuntu-latest` satisfies natively), or
  a standard `docker build` step against a Dockerfile using the cookbook
  pattern (§2 path 1). `mise oci push --update-index` is documented for a
  matrix multi-arch build (`mise-oci.md:425-451`, worked GHA sketch already in
  the doc) if both amd64/arm64 are wanted.
- **(b) Run the agent-install test inside it**: headless Claude Code is
  `claude -p "<prompt>"` (`sources/claude-code-docs/content/en/docs/claude-code/headless.md:11-14`).
  For a **reproducible CI check** (no host `.claude/`, no ambient hooks/MCP),
  add `--bare` (`headless.md:35-63`): it skips auto-discovery of hooks, skills,
  commands, subagents, plugins, MCP, auto-memory, and CLAUDE.md — but **still
  loads `.claude/skills/` from a directory named via `--add-dir`**
  (`headless.md:39`), and it needs `ANTHROPIC_API_KEY` (bare mode never reads
  OAuth credentials, `headless.md:43,49`). For the *plugin-install* smoke test
  specifically (not bare — the whole point is verifying the marketplace +
  plugin path), a plain `claude -p "…" ` session authenticated via
  `CLAUDE_CODE_OAUTH_TOKEN` (§4) is the right non-bare mode, since bare mode
  explicitly does **not** read `CLAUDE_CODE_OAUTH_TOKEN`
  (`content/en/docs/claude-code/authentication.md:230`).
  Exit code 0 on success, non-zero on failure (`headless.md:33`) — a normal CI
  gate.
- **(c) Upload artifacts / attach a CLI wheel to a release**:
  `actions/upload-artifact` — **latest `v7.0.1`, published 2026-04-10T17:31:14Z**
  (`gh api repos/actions/upload-artifact/releases/latest`, probed this session).
  For attaching a file to a GitHub Release, `softprops/action-gh-release` —
  **latest `v3.0.2`, published 2026-07-13T14:30:35Z** (same probe method) — or
  the simpler `gh release upload <tag> <file>` (no extra action, since `gh` is
  already this repo's standard CLI per `.claude/rules/gh-cli-watch.md`). Either
  makes the wheel fetchable by a `SessionStart` hook via a plain
  `curl -fsSL https://github.com/<owner>/<repo>/releases/download/<tag>/<file>`.
- **This repo has no `.github/` today** — confirmed by this repo's own
  `.claude/rules/gh-cli-watch.md` ("`.github/` does not exist here... no
  `ci.yml`"), and this task's own framing already states the workflow belongs
  in the **marketplace repo** (`ray-manaloto/claude-code-marketplace`), not
  here. Not independently re-probed against that repo (not this session's
  scope) — **null, arm: would need `gh repo view ray-manaloto/claude-code-marketplace
  --json defaultBranchRef` or an `ls` of its `.github/` from that repo's own
  checkout, neither run this session**.

---

## 4. Headless auth + marketplace add requirements

- **`claude` (2.1.250 pinned via `npm:@anthropic-ai/claude-code` per §2) runs
  in a container with no browser login** via `CLAUDE_CODE_OAUTH_TOKEN`,
  generated once (interactively, outside the container) with
  `claude setup-token` — this repo's own `.claude/skills/kb-review/SKILL.md:36`
  already asserts and cites this ("Ray challenged that too, naming `claude
  setup-token`, and was right"), and the upstream doc confirms and extends it:
  `claude setup-token` opens a one-time browser OAuth flow and **prints a
  one-year token to the terminal without saving it anywhere**
  (`content/en/docs/claude-code/authentication.md:214-222`); export it as
  `CLAUDE_CODE_OAUTH_TOKEN` wherever the CI/container needs to authenticate
  (`:225-226`). It authenticates against the **subscription** (Pro/Max/Team/
  Enterprise), can only make model requests — no Remote Control, no claude.ai
  connectors (`:228`) — and is ranked #5 in the doc's own auth-precedence list
  (`:179-186`), above the interactive `/login` OAuth default (#7) and below
  `apiKeyHelper`/`ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`. **Do not combine
  with `--bare`**: bare mode explicitly never reads `CLAUDE_CODE_OAUTH_TOKEN`
  (`:230`) — for a bare smoke test use `ANTHROPIC_API_KEY` instead.
- **Plugin marketplace add, non-interactive**: `claude plugin marketplace add
  <owner/repo-or-url>` (e.g. `claude plugin marketplace add
  ray-manaloto/claude-code-marketplace`) registers the marketplace from the
  CLI outside any session — the `claude-plugins-official` example shows this
  exact shape for a marketplace that needs registering before first
  interactive launch (`content/en/docs/claude-code/plugins.md:352`). Installing
  a plugin from it needs **`--yes` in a non-interactive shell**: "In a
  non-interactive shell, such as a provisioning script, pass `--yes` to
  `claude plugin install` or `claude plugin update` to accept the command it
  prints" (`plugin-marketplaces.md:545`) — this only matters for
  **command-sourced** plugin entries (ones whose marketplace.json runs a
  install-time command); a git/npm-sourced plugin entry has no command to
  accept. **Auth needed for the git clone itself**: "Claude Code uses your
  existing git credential helpers... HTTPS access via `gh auth login`, macOS
  Keychain, or `git-credential-store`... SSH access works as long as the host
  is already in `known_hosts`" (`plugin-marketplaces.md:677`) — for a
  **public** repo (the definition-of-done's stated case), no credential is
  actually required; git can clone a public GitHub repo anonymously over
  HTTPS. **Null, arm needed**: whether `claude plugin marketplace add` itself
  requires *any* Claude auth (vs. only git access) was not directly stated in
  the excerpted lines — the doc describes git credentials for the clone, not
  Claude Code's own auth state at that point. Not resolved this session; arm:
  run `claude plugin marketplace add <public-repo>` in a container with **no**
  `CLAUDE_CODE_OAUTH_TOKEN` set and see if it succeeds (git clone only) or
  errors demanding login.
- **Seed-and-preinstall alternative** (found incidentally, directly relevant to
  "install once, run many containers"): `CLAUDE_CODE_PLUGIN_CACHE_DIR` +
  `CLAUDE_CODE_PLUGIN_SEED_DIR` (`plugin-marketplaces.md:766-775`) lets a build
  step pre-populate `known_marketplaces.json` + plugin caches at a directory
  during image build, then at container **runtime** set
  `CLAUDE_CODE_PLUGIN_SEED_DIR` and Claude Code registers the seeded
  marketplaces and reuses the cached plugin clones **without re-cloning**,
  "in both interactive mode and non-interactive mode with the `-p` flag"
  (`:772`). This is the natural fit for `[[oci.copy]]` (§1): bake the seed dir
  into the image as a copy layer, so the container never needs network/git
  access at runtime at all.

---

## Proposed minimal artifacts (illustrative, per Ray's "can be tested via CI" ask)

### `mise.toml` (container, ≤40 lines)

```toml
[tools]
"npm:@anthropic-ai/claude-code" = "2.1.250"
"npm:@openai/codex" = "0.150.1"        # if the plugin needs codex, per this repo's own precedent
uv = "latest"
python = "3.14"

[settings]
experimental = true   # required for `mise oci build`/run/push
pin = true

[oci]
from       = "debian:bookworm-slim"
tag        = "ghcr.io/ray-manaloto/claude-agent-sandbox:latest"
user       = "nonroot"
user_id    = 1000
entrypoint = ["claude"]

[bootstrap.packages]
"apt:git" = "latest"
"apt:ca-certificates" = "latest"

[tasks.smoke-test]
run = """
claude plugin marketplace add ray-manaloto/claude-code-marketplace --yes
claude plugin install aggregated-research@claude-code-marketplace --yes
claude -p "list installed plugins" --output-format json
"""
```

### `Dockerfile` (fallback path if `mise oci build` proves insufficient, ≤20 lines)

```Dockerfile
FROM debian:13-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl git ca-certificates build-essential \
    && rm -rf /var/lib/apt/lists/*
ENV MISE_DATA_DIR="/mise" \
    MISE_CONFIG_DIR="/mise" \
    MISE_INSTALL_PATH="/usr/local/bin/mise" \
    PATH="/mise/shims:$PATH"
RUN curl https://mise.run | sh
COPY mise.toml /mise/config.toml
RUN mise install
ENTRYPOINT ["claude"]
```

### `.github/workflows/agent-container.yml` skeleton (marketplace repo, ≤40 lines)

```yaml
name: agent-container
on: [push, pull_request]
jobs:
  build-and-test:
    runs-on: ubuntu-latest   # Linux required — mise oci build embeds host-native binaries otherwise
    permissions:
      contents: write
      packages: write
    steps:
      - uses: actions/checkout@v6
      - uses: jdx/mise-action@v4.3.0
        with:
          experimental: true
      - run: mise oci build --tag ghcr.io/${{ github.repository_owner }}/claude-agent-sandbox:${{ github.sha }}
      - run: mise oci run --owner 1000 -e CLAUDE_CODE_OAUTH_TOKEN=${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }} -- mise run smoke-test
      - uses: actions/upload-artifact@v7.0.1
        with:
          name: agent-container-smoke-log
          path: smoke-test.log
      - if: startsWith(github.ref, 'refs/tags/')
        run: gh release upload ${{ github.ref_name }} dist/cli-wheel.whl
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Every version number above is either pinned to a value measured this session
(`v4.3.0`, `v7.0.1`, `2.1.250`) or an illustrative placeholder (`0.150.1`,
`3.14`) not independently re-verified against this exact task's real plugin
dependency list, which was not provided.

---

## Every null with its arm

| # | Null claim | Arm needed |
|---|---|---|
| N1 | `mise oci build` actually succeeds end-to-end for THIS repo's real tool set (npm/pipx/conda backends only) | run `MISE_EXPERIMENTAL=1 mise oci build` on a Linux host with this repo's `mise.toml` and read the exit code + `./mise-oci/` layout |
| N2 | `claude plugin marketplace add <public-repo>` requires no Claude auth (only git) | run it in a container with `CLAUDE_CODE_OAUTH_TOKEN` unset and observe pass/fail |
| N3 | `.github/` state of `ray-manaloto/claude-code-marketplace` (whether a workflow already exists) | `gh api repos/ray-manaloto/claude-code-marketplace/contents/.github` from that repo, not run this session (out of this repo's read-only scope) |
| N4 | Whether the illustrative `smoke-test` task's exact plugin dependency chain (aggregated-research's own dependency plugins) installs cleanly under `--yes` | requires the actual `marketplace.json` for that plugin, not fetched this session |

## Not measured

- Whether `mise oci push --update-index` multi-arch actually round-trips for
  this container (only the doc's own worked CI sketch was cited, not run).
- Real GHA runtime/cost of a full `mise oci build` for this tool set (no build
  was executed — Linux-only requirement makes it unrunnable on this macOS
  session, confirmed via `mise-oci.md:414-424`, not merely assumed).
- Whether `CLAUDE_CODE_PLUGIN_SEED_DIR` + `[[oci.copy]]` together eliminate
  runtime network access entirely — described in docs, not tested.

## GitHub repos touched

- [jdx/mise](https://github.com/jdx/mise) — pinned source clone at `sources/mise/`; read `docs/cli/oci.md`, `docs/dev-tools/mise-oci.md`, `docs/cli/generate.md`, `docs/mise-cookbook/docker.md`, `docs/continuous-integration.md`, `docs/dev-tools/backends/npm.md`.
- [jdx/mise-action](https://github.com/jdx/mise-action) — queried `releases/latest` via `gh api` for current version/pushed_at.
- [actions/upload-artifact](https://github.com/actions/upload-artifact) — queried `releases/latest` via `gh api`.
- [softprops/action-gh-release](https://github.com/softprops/action-gh-release) — queried `releases/latest` via `gh api`.
- Anthropic's Claude Code docs, vendored at `sources/claude-code-docs/` — read `content/en/docs/claude-code/headless.md`, `authentication.md`, `plugins.md`, `plugin-marketplaces.md`.
