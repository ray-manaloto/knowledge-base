# mise CLI research — recovering the caller's pre-mise PATH

**Agent:** mise-path-research · **Date:** 2026-07-27
**Installed mise:** `2026.7.15 macos-arm64 (2026-07-27)` — i.e. the machine is on the
**latest** release (`v2026.7.15`, published 2026-07-27T18:51:46Z). No "upgrade and it
works" answer is available; whatever is missing is missing in HEAD.

**Corpus fetched (primary sources):**

- `gh api --paginate 'repos/jdx/mise/releases?per_page=100'` → `/tmp/mise_releases.txt`,
  **604 releases**, 13,902 lines, spanning `v2023.8.0` (2023-08-15) → `v2026.7.15`
  (2026-07-27). This is the FULL release history, not "the last several months" —
  the bound the team lead asked for is strictly contained.
- `curl https://mise.jdx.dev/llms.txt` → HTTP 200, 35,745 bytes.
- The installed binary's own `--help` output (see §Probes).

---

## Control arms (run BEFORE any negative is reported)

Same command shape (`grep -ic -- "<term>" mise_releases.txt`) over the same corpus:

| term | class | hits |
|---|---|---|
| `lockfile` | **control (known present)** | 159 |
| `shims` | **control (known present)** | 70 |
| `PATH` | **control (known present)** | 333 |
| `MISE_ORIGINAL_PATH` | target | **0** |
| `__MISE_ORIG_PATH` | target | **0** |
| `ORIG_PATH` | target | **0** |
| `original_path` | target | **0** |
| `MISE_RAW` | target | **0** |
| `MISE_ACTIVATE_AGGRESSIVE` | target | **0** |
| `deny-env` | target | **0** |
| `passthrough` | target | **0** |
| `exec-direct` | target | **0** |
| `--raw` | target | 1 |
| `no-env` | target | 1 |
| `__MISE_DIFF` | target | 4 |

The probe discriminates: three known-present terms return 159/70/333, so a 0 is a
real absence in the release-notes corpus, not a broken grep.

**Token-spelling arm.** `__MISE_ORIG_PATH` returns 0 in the release notes but the
variable **does exist at runtime** on this machine (the team lead measured it). That
is exactly the `LM Studio`-vs-`lmstudio` failure class inverted: *absence from the
release notes is not absence from the product* — it is evidence the variable was
never announced, i.e. it is **internal and undocumented**. Confirmed separately
against the docs corpus below.

**KB-graph arm (cost ladder rung 0).** `mise run kb-query -- "mise original PATH shim
install dirs env diff"` returned only unrelated `graphify/install.py` and frontend
nodes — **mise's docs are not in this corpus**. The graph could not answer this; the
network sources below are not a skipped rung.

**Second corpus (added after the release-notes pass):** a shallow clone of mise HEAD,
`git clone --depth 1 https://github.com/jdx/mise.git /tmp/mise-src` (48 MB) — this is
the **primary** source for both the docs (`docs/**`, which is what
`mise.jdx.dev` renders) and the implementation (`src/**`).

> **Why the docs were cloned rather than curl'd:** `https://mise.jdx.dev/<page>.md`
> returns **HTTP 404** for every page tried (`configuration/settings`,
> `dev-tools/shims`, `cli/exec`, `cli/run`, `tasks/task-configuration`, …). mise's
> docs are **VitePress, not Mintlify**, so the `research-doc-sources.md` step-2
> `.md`-suffix trick does not apply here. `llms.txt` (step 1) exists and returned
> 200/35,745 B but is only an index of page titles + one-line summaries — it does
> not contain flag or variable names, so it cannot answer any of these questions.
> Recording this so the next session does not re-probe it.

---

## Q1 — Is there a documented way to get the PATH as it was **before** mise modified it?

> **CALLER'S ANNOTATION, 2026-07-27 — REFUTED FOR THIS USE CASE. Do not act on
> this section without reading this box.** The finding below is accurate *under
> the condition it was measured in* (`env -i`) and wrong for the condition it was
> requested for (a live, mise-activated session). `get_env` is bound to
> `PRISTINE_ENV`, which — as this very section documents at lines 104-106 —
> "removes each path mise added". Under an activated shell those added paths ARE
> the stale install dirs the caller's check exists to detect, so `get_env`
> launders the drift away.
>
> Re-measured by the caller, one caller PATH carrying BOTH a sentinel dir and a
> stale `pipx-graphifyy` install dir, same probe shape both arms:
>
> | caller | entries | install dirs | sentinel |
> |---|---|---|---|
> | activated shell (the real condition) | 5 | **0** — laundered | present |
> | `env -i` (this report's condition) | 5 | **1** — intact | present |
>
> The sentinel survives both, so the probe discriminates: `get_env` is not
> returning garbage, it is *specifically* removing mise-added path entries. The
> §"Measured proof (both arms)" table below is `env -i`-only for the install-dir
> column, which is exactly where the two conditions diverge — it could not have
> shown this.
>
> Adopting it would have produced a check that **cannot fail** — the same defect
> class as the `__MISE_ORIG_PATH` candidate this report correctly rejects, and
> the one the caller's whole task was to escape. The shipped design keeps
> `CLAUDE_PID` + an OS environment read; `mise.toml` and
> `kb_setup.launch.session_path` now carry a "do not simplify this to `get_env`"
> note with the measurement above.
>
> This is a scope failure, not a sourcing failure: every citation below checks
> out. See `.claude/rules/verify-before-advancing.md` § "Carry a fact's
> CONDITION, not just its source".

### **YES — and it is a documented Tera template function: `get_env(name='PATH')`.**

This is the headline result and it **does** replace a hand-rolled design.

**Citation (docs, primary):** `docs/templates.md:276-280` —

```text
- `get_env(name, [default]) -> String` – Returns the original process environment
  variable value by name. This helper is provided by mise for compatibility with
  older Tera templates. Prefer the `env` variable in new templates when possible.
```

"Returns the **original process environment** variable value by name" is an explicit,
documented promise — not an inference.

**Citation (implementation):** `src/tera.rs:315` —

```rust
tera.register_function("get_env", tera_get_env(env::PRISTINE_ENV.clone()));
```

`PRISTINE_ENV` is defined at `src/env.rs:539-540` as
`get_pristine_env(&__MISE_DIFF, vars_safe().collect())`, and `get_pristine_env`
(`src/env.rs:669-696`) is documented in-source as:

```rust
/// this returns the environment as if __MISE_DIFF was reversed.
/// putting the shell back into a state before hook-env was run
```

It reverses the `__MISE_DIFF` patches **and** removes each path mise added
(`to_remove` / `filter(|p| !to_remove.remove(p))`) — i.e. mise already contains,
internally, exactly the "un-mangle my PATH" routine we were about to write, and
exposes it through a documented template function.

### The exact invocation

```toml
[tasks.cc-doctor]
run = "uv run kb-setup cc-doctor"

[tasks.cc-doctor.env]
CC_CALLER_PATH = "{{ get_env(name='PATH') }}"
```

The task process (and everything it spawns, including `uv run` through the shim)
then sees `$CC_CALLER_PATH` = the invoking process's PATH, untouched. The shim
re-prepends onto `PATH`, **not** onto `CC_CALLER_PATH`, so the double-mangle in the
problem statement does not reach it.

An inline form also works if you would rather not add an env var:
`run = "uv run kb-setup cc-doctor --caller-path '{{ get_env(name=\"PATH\") }}'"`.
The env-var form is preferable — no quoting/ARG_MAX exposure for a 37-entry PATH.

### Measured proof (both arms)

Probe: a task printing entry count / `mise/installs` count / presence of a sentinel
dir, for `$PATH` (runtime), `{{ env.PATH }}`, and `{{ get_env(name='PATH') }}`.

| caller env | `RUNTIME $PATH` | `{{ env.PATH }}` | `{{ get_env(name='PATH') }}` |
|---|---|---|---|
| `env -i PATH=/tmp/SENTINEL_DIR:/usr/bin:/bin:/usr/sbin:/sbin` (5 entries, 0 installs) | 156 entries / **149 installs** / sentinel ✓ | 156 / **149** / ✓ | **5 entries / 0 installs / sentinel ✓** |
| this session's activated shell (32 entries) | 182 / 149 / — | 182 / 149 / — | **32 / 0 / —** |

- **Control arm (probe can show 0):** `env -i PATH=<clean> /tmp/probe.sh` with no
  mise in the chain → `5 entries / 0 install dirs / sentinel present`. The probe
  discriminates.
- **`{{ env.PATH }}` is the trap.** Despite `src/tera.rs:297`
  (`context.insert("env", &*env::PRISTINE_ENV)`), the task-`env` render path
  **overwrites** the `env` context variable with the accumulated (tool-injected)
  environment, so `{{ env.PATH }}` returns the *mangled* PATH — identical to
  `$PATH`, 149 install dirs. `get_env()` is a **registered function** bound to
  `PRISTINE_ENV` at registration time and is not affected by that override. The
  docs' advice to "prefer the `env` variable in new templates" is **exactly wrong
  for PATH**. Use `get_env`.
- **Staleness arm (does the 1h env cache freeze the value?):** back-to-back runs
  from two different caller PATHs —
  `PATH=/tmp/AAA_DIR:/usr/bin:/bin` → `TPL_GETENV entries=3`;
  `PATH=/tmp/BBB_DIR:/usr/bin:/bin:/sbin` → `TPL_GETENV entries=4`.
  It tracks per-invocation; it is **not** served stale from `env_cache`
  (`env_cache=true`, `env_cache_ttl="1h"` on this machine). If you want belt and
  braces, `mise run --fresh-env` exists ("Bypass the environment cache and
  recompute the environment", `mise exec --help` / `docs/cli/run.md`).

### End-to-end proof: the value survives the shim re-entry

The failure mode in the problem statement is the *second* mangle — the task calls
`uv run`, `uv` resolves to `~/.local/share/mise/shims/uv`, and the shim re-enters
mise and re-prepends every install dir. Probe with a real mise-managed tool
(`jq = "1.7.1"` in `[tools]`), invoked from `env -i PATH=/tmp/SENTINEL_DIR:/usr/bin:/bin:/usr/sbin:/sbin`:

```text
shim ran: yes
AFTER-SHIM CC_CALLER_PATH entries=5   installs=0    sentinel=1
AFTER-SHIM $PATH          entries=156 installs=149
```

The shim mangles `PATH`; it does not touch `CC_CALLER_PATH`. The caller's PATH is
intact **after** the shim has run, which is precisely the point at which
`uv run kb-setup cc-doctor` reads it.

### The candidates the team lead named — each disposed of

| candidate | verdict | evidence |
|---|---|---|
| `MISE_ORIGINAL_PATH` | **does not exist** | 0 hits in 604 release notes; 0 files in `docs/`; unset at runtime. Controls: `lockfile` 159 / `shims` 70 / `PATH` 333 in releases; 32/32/153 doc files. |
| `__MISE_ORIG_PATH` | **exists but is useless AND undocumented** | Written **only** by the activate snippet, guarded by `if [ -z "${__MISE_ORIG_PATH:-}" ]` — `src/assets/bash/activate.sh:10-11`, `src/shell/zsh.rs:33-34`, `src/shell/fish.rs:34-35`, `src/shell/pwsh.rs:29-30`. Set **once at activate time and never refreshed** — that is the design, which is why the team lead's inbound sentinel dir never appeared in it. **0 files in `docs/`** (vs 32-file controls) ⇒ internal, `__`-prefixed, not a supported surface. Read back at `src/env.rs:522`. Not set at all under `mise exec` from a clean env (measured). |
| `mise env --json` | **no** — reports the *resulting* env, not the caller's. `mise env --help` lists `-J/--json`, `--json-extended`, `--redacted`, `--values`; nothing for a pre-mise snapshot. |
| task `env` options | **yes, but only as the carrier** — the recovery is `get_env()`, not the `env` block itself. See above. |
| `--raw` / `MISE_RAW` | **no** — `--raw` is *stdio* only: "Read/write directly to stdin/stdout/stderr instead of by line" (`mise run --help`, `mise --help`). `MISE_RAW` : 0 hits in releases (controls 159/70/333). |
| `tools = false` | **does not exist.** `tools = false` / `tools=false` : 0 hits in releases. The real `tools` task option (`docs/tasks/task-configuration.md:238`) is `{ [key]: string }` — *adds* tools for a task; there is no falsy form. |
| `mise exec --no-env` | **no** — `--no-env` (global flag, `MISE_NO_ENV=1`) is "Do not load environment variables **from config files**", i.e. the `[env]` block. Measured: `env -i PATH=<clean> mise --no-env exec -- probe` → still **154 install dirs**. Shipped **v2026.1.3** (2026-01-16), PR [#7560](https://github.com/jdx/mise/pull/7560) by @aacebedo, alongside `--no-hooks`. |
| sandbox `--deny-env` | **no, and it actively makes things worse** — documented as "Block env var inheritance (**only `PATH`**, `HOME`, `USER`, `SHELL`, `TERM`, `LANG` pass through)" (`docs/sandboxing.md:31`). The PATH it passes through is the **mutated** one. Measured: `mise run --deny-env probe` → runtime PATH still 154 entries / 149 installs, while the task's own `TPL_*` env vars were wiped to 1 entry. It also unsets `__MISE_ORIG_PATH`. |

---

## Q2 — Can a mise task run **without** the tool-install-dir PATH injection?

### **NO.** There is no documented (or undocumented) opt-out.

Everything measured, from a clean `env -i` caller with a 5-entry PATH:

| invocation | install dirs injected |
|---|---|
| `mise exec -- probe` | **154** |
| `mise --no-env exec -- probe` | **154** |
| `mise exec --deny-env -- probe` | **154** |
| `mise run probe` | **149** |
| `MISE_DISABLE_TOOLS=1 mise run probe` | **149** |
| `mise --no-config run probe` | task cannot be found — config is where tasks live |
| *(control) no mise at all* | **0** |

Term sweep over `docs/` (controls: `shims` → 32 files, `lockfile` → 32, `PATH` → 153):
`no-tools` → 0, `without tools` → 0, `MISE_NO_TOOLS` → 0, `MISE_ACTIVATE_AGGRESSIVE`
→ 0 in the release corpus.

Two near-misses worth naming so they are not re-investigated:

- **`disable_tools`** (`docs/cli/config/set.md:48`,
  `mise config set settings.disable_tools node,rust`) is a **denylist of tool
  names**, global-scoped, not a per-task PATH switch. Measured with
  `MISE_DISABLE_TOOLS=1`: still 149 install dirs. It also cannot be the answer in
  principle — the task needs `uv` on PATH.
- **`activate_aggressive`** is a real setting and is **`true` on this machine**,
  set in `~/.config/mise/config.toml` (`mise settings --all`). It is documented only
  in `docs/troubleshooting.md` and governs *activation* PATH ordering, not `mise run`
  injection. **Do not change it** — it is global user config, and
  `do-not.md` invariant 11 puts `~/.config` out of bounds for this repo anyway.

**Conclusion for Q2:** the injection is unavoidable. Which is fine, because Q1's
answer means we never needed to avoid it — we capture the caller's PATH *before*
injection instead of suppressing injection.

---

## Q3 — Recent changes to shim PATH behaviour / a "passthrough" mode?

**No general shim-passthrough or exec-direct mode exists** (`passthrough` → 0 hits,
`exec-direct` → 0 hits across 604 releases; controls 159/70/333). Shims re-entering
mise and re-prepending install dirs is the intended design and is unchanged.

What *has* changed since 2026-01 (all from the release corpus) — the theme is
**recursion/fork-bomb containment**, i.e. mise stripping shims from *child*
environments, never exposing the caller's PATH:

| release | item |
|---|---|
| **v2026.2.18** | "`mise exec` now strips its own shims from `PATH` before spawning subprocesses, preventing infinite recursion when a shimmed tool calls itself" ([#8276](https://github.com/jdx/mise/pull/8276)) |
| **v2026.2.21** | Reverts part of #8276: "`mise x` respects virtualenv PATH order again" — the pre-resolution step "resolved bare command names directly to mise-managed tool paths, bypassing PATH entirely" |
| **v2026.3.6** | "Fork bomb prevention strips mise shims from dependency environment PATHs" |
| **v2026.3.10** | "**`mise doctor` detects PATH ordering issues** — when mise is activated (not shims-only), `mise doctor` now checks whether non-mise directories appear before mise-managed tool paths in PATH and lists the specific offending entries" |
| **v2026.3.18** | Two recursion guards: system shims on PATH, and "Fork bomb from `exec()` templates, credential commands, and git credentials — three subprocess-spawning code paths inherited mise shims in PATH" |
| **v2026.5.16** | "Strip the system shims dir from `dependency_env` PATH to prevent npm/go shim re-entry fork-bombs" ([#10019](https://github.com/jdx/mise/pull/10019)) |
| **v2026.6.7** | "`mise activate --shims` no longer re-prepends the directory containing the `mise` executable" ([#10394](https://github.com/jdx/mise/pull/10394)) |
| **v2026.6.10** | "Windows extensionless bash shims now detect WSL …, **drop their own dir from PATH, and `exec` the tool directly**" — the closest thing to passthrough that exists, and it is **Windows/WSL-only** |
| **v2026.7.6** | "**`mise doctor` now warns when a mise shim is shadowed by an earlier executable in `PATH`**" ([#10919](https://github.com/jdx/mise/pull/10919)) |
| **v2026.7.11** | "**shim:** recursion is prevented when the directory env is filtered" ([#10982](https://github.com/jdx/mise/pull/10982)) |

The two `mise doctor` rows are directly relevant to `cc-doctor`: **mise ships its own
PATH-shadowing diagnostic**, which is worth reading before hand-rolling the
equivalent (`use-tool-builtins.md`).

One release note is materially relevant to the *inbound* side of this problem:

> **v2026.5.6** — "Nested `mise -C <dir> exec` correctly resolves the inner toolset's
> tools again — **`__MISE_DIFF` is now propagated to children** so the child no
> longer inherits a mutated PATH that hides its own tools"
> ([#9765](https://github.com/jdx/mise/pull/9765) by @jdx)

That is *why* `get_env()` keeps working through nesting: the child can still reverse
the diff. It also means `__MISE_DIFF` reaches deeper into child processes than it
used to — see Q4.

---

## Q4 — Secrets in `__MISE_DIFF`: known issue, or expected?

### **Expected behaviour, undocumented as a hazard, and never mentioned in any release note.**

**It is not a bug and there is no fix to wait for.**

1. **`__MISE_DIFF` is documented as an inspectable env snapshot**, encoded
   gzip + base64 + msgpack. `docs/mise-cookbook/shell-tricks.md:62-93` gives the
   decoder verbatim:

   ```shell
   function mise_parse_env {
     rq -m < <( zcat -q < <( printf '\x1f\x8b\x08\x00\x00\x00\x00\x00'; base64 -d <<< "$1" ) )
   }
   $ mise_parse_env "${__MISE_DIFF}"   # -> { "new": {...}, "old": {...}, "path": [...] }
   ```

   So "an undocumented msgpack blob" is half right: the *variable* is documented
   (in the cookbook), the *format* is documented, and it deliberately carries the
   **full `new`/`old` env maps**. Anything mise's `[env]` directives resolved —
   including SOPS/age-decrypted secrets and `_.file` loads — lands in `new`.

2. **Redaction never touches it.** Control-armed grep of mise HEAD:
   `redact` appears **232 times across `src/`** (`src/redactions.rs`,
   `src/logger.rs`, `src/cmd.rs`, `src/cli/run.rs`, `src/cli/env.rs`,
   `src/config/env_directive/**`, `src/toolset/**`) but **0 times in
   `src/env_diff.rs`** and **0 times in `src/hook_env.rs`** — the two files that
   build and serialize `__MISE_DIFF`. The control arm proves the grep works.

   The docs say why, explicitly: *"Redactions work by **intercepting task output
   line-by-line**, so they require a non-`raw` output mode"*
   (`docs/environments/index.md:170`). Redaction is a **display** feature over
   stdout/stderr. It was never an env-var confidentiality mechanism.

3. **Release-note sweep found nothing.** `__MISE_DIFF` appears in exactly **4**
   release-note lines across the entire 604-release history, none security-related:
   - **v2026.5.6** — propagate `__MISE_DIFF` to children ([#9765](https://github.com/jdx/mise/pull/9765))
   - **v2025.11.4** — pwsh: remove `__MISE_DIFF` instead of `__MISE_WATCH` on deactivate ([#6886](https://github.com/jdx/mise/pull/6886))
   - **v2024.12.13** — sort keys in `__MISE_DIFF` to make the serialised value deterministic ([#3640](https://github.com/jdx/mise/pull/3640))
   - **v2024.11.28** — remove `__MISE_WATCH`/`__MISE_DIFF` on `mise deactivate` ([#3178](https://github.com/jdx/mise/pull/3178))

   No hardening, no redaction, no CVE-shaped item. Control arm: `lockfile` 159 /
   `shims` 70 / `PATH` 333 over the same corpus, so 4-and-none-security is a real
   result.

4. **The exposure got *wider* in v2026.5.6**, not narrower: propagating
   `__MISE_DIFF` to child `mise` invocations means the blob travels further down
   the process tree than it did before 2026-05-11.

**Practical read for this repo.** Anything that dumps a task's environment —
a diagnostic, a bug report, a CI log, an agent transcript — will exfiltrate every
secret mise's `[env]` resolved, base64'd so it survives naive secret-scanners
(gitleaks will not match a gzip'd msgpack blob). Two mitigations, neither of which
needs upstream:

- Any env dump written by `kb_setup` should **drop `__MISE_DIFF` (and `__MISE_SESSION`)
  by name** before writing. `clean_env()` is already the natural home for that.
- `mise env --redacted --values` (`docs/environments/index.md:159-166`) enumerates the
  values mise itself considers sensitive, if a scrubber wants a denylist.

Worth filing upstream as a hardening request; it is not currently tracked as one.

---

## Q5 — Secondary: release items materially useful to a task-heavy mise repo

Kept short, newest-first, only items that plausibly change something here.

- **v2026.7.15** — *Experimental task output caching.* Also: circular-dependency
  detection now runs on the **fully resolved** graph (covers `wait_for`,
  `{{usage.*}}` deps, `depends_post`) and reports a concrete cycle path before any
  task runs. And `mise generate task-docs --inject` now errors loudly when the
  `<!-- mise-tasks -->` markers are missing/reversed instead of clobbering the file.
- **v2026.7.14** — every mise command now **declares its effect**: read-only /
  modifies state / destructive, surfaced in the command reference. That is a
  ready-made allowlist for `kb_setup.hook_guard`'s read-only carve-out — currently a
  hand-maintained list (`path`/`explain`/`god-nodes`/`affected`/`diagnose`). Requires
  usage 4.0 (`min_usage_version` bumped).
- **v2026.7.11** — *Task source tracking* and activation speedups.
- **v2026.7.6 / v2026.3.10** — the two `mise doctor` PATH diagnostics described in Q3.
  **Read these before writing more of `cc-doctor` by hand.**
- **v2026.7.1 / v2026.7.2** — **Tera v2 templates** (with a `MISE_TERA_V1` escape
  hatch, whose explicit `[settings]`/env use now emits deprecation warnings as of
  v2026.7.2). Since the Q1 recommendation is a template function, this is the one
  compatibility axis to keep an eye on: `get_env` is documented as the
  *compatibility* helper for "older Tera templates" — but it is also the only one
  that returns the pristine value, so it must not be "modernised" to `env.PATH`.
- **v2026.7.0** — **shell expansion by default** (`env_shell_expand=true`, confirmed
  on this machine via `mise settings --all`), monorepo lockfiles, task usage mounts.
- **v2026.6.3** — `auto_env`. **v2026.5.12** — `minimum-release-age` (a real currency
  lever: it would let `currency.toml` refuse a release younger than N days).
- **v2026.5.11 / v2026.6.2 / v2026.6.5 / v2026.6.13** — provenance verification at
  lock time, supply-chain defaults, trust hardening, aqua attestation. Relevant to
  `currency.toml`'s `extra_probes` story.
- **v2026.5.2** — fail-fast parallel tasks, curated lockfiles, stable monorepo task
  roots.
- **`--locked` global flag** (`mise --help`): "Require lockfile URLs to be present
  during installation… prevents API calls to GitHub, aqua registry, etc." — a
  hermetic-build lever for `kb-build`, and a network-flake mitigation matching
  `persistence-gate-retry.md`.

---

## Probes run (with their control arms)

| probe | control arm | result |
|---|---|---|
| `grep -ic <term> mise_releases.txt` (604 releases) | `lockfile`=159, `shims`=70, `PATH`=333 | discriminates; 0s are real |
| `grep -ril <term> /tmp/mise-src/docs` | `shims`=32 files, `lockfile`=32, `PATH`=153 | discriminates |
| `grep -rn redact /tmp/mise-src/src` | 232 total hits across src | `env_diff.rs`=0, `hook_env.rs`=0 — real absence |
| task PATH probe (`entries` / `mise/installs` / sentinel) | `env -i PATH=<clean> /tmp/probe.sh` → 5 / 0 / 1 | can show 0 install dirs |
| `get_env` staleness | two different caller PATHs back-to-back → 3 vs 4 entries | not cache-frozen |
| `mise.jdx.dev/<page>.md` | every one of 9 pages → HTTP 404, identical 27,150-byte body | it is a 404 page, not content — VitePress, not Mintlify |
| KB graph (`mise run kb-query`) | returned unrelated `graphify/install.py` nodes | mise docs are **not** in this corpus; the network hop was not a skipped rung |

**Inherited-number discipline.** Every number in this report was measured in this
session on this machine, except the team lead's "37 entries / 154 install dirs /
192 entries" figures, which are cited as *theirs* and were not re-derived (my own
harness shell is mise-activated, so its baseline differs: 190 entries / 154
installs). The clean-`env -i` arms above are the re-derivation that matters.

---

## GitHub repos touched

- [jdx/mise](https://github.com/jdx/mise) — the subject: all 604 GitHub releases via `gh api`, plus a shallow clone of HEAD for `docs/**` (templates, sandboxing, environments, tasks, cookbook) and `src/**` (`env.rs`, `env_diff.rs`, `hook_env.rs`, `tera.rs`, `shell/*.rs`, `assets/bash/activate.sh`).
- [jdx/mise-action](https://github.com/jdx/mise-action) — named in `docs/environments/index.md:203` as auto-redacting `redact = true` values in CI; read only as a cross-reference for the Q4 redaction-scope claim.
- [keats/tera](https://github.com/keats/tera) — the template engine behind `get_env`/`env`; referenced from `docs/templates.md:36` and relevant to the v2026.7.1 Tera v2 migration noted in Q5.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — this repo's own graph was queried as cost-ladder rung 0 (`mise run kb-query`); returned only graphify-source nodes, confirming mise's docs are not ingested here.

