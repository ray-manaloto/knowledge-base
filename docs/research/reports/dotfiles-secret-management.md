# Secret management in `ray-manaloto/dotfiles` — operator notes

**Researched:** 2026-08-21 · **Repo:** `/Users/rmanaloto/dev/github/ray-manaloto/dotfiles` (branch `main`)
**Safety:** no secret VALUES appear in this report. Names, provider types, file paths and byte counts only.

_Status: COMPLETE._

## 0. Headline — point at the existing docs, do not rewrite them

**dotfiles already documents this thoroughly and accurately.** Three files, in
priority order:

| path | lines | what it is |
|---|---:|---|
| `/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/secrets-doppler-fnox-keychain.md` | 593 | **The canonical guide.** Rewritten 2026-08-03, every claim re-measured that day with control arms and no value printed. Holds the four-layer model, the agent contract, the literal add procedure, the diagnosis ladder, and an incident log. |
| `/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/.claude/rules/secrets-out-of-the-shell-env.md` | 196 | **The rule.** The posture, the 2026-08-02 reversal, and the four gates that enforce it. |
| `/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/rules-evidence/secrets-out-of-the-shell-env.md` | — | The measurement/evidence annex: probe tables, the config-wipe timeline, and the pre-reversal (exec-era) sections verbatim. |

Supporting research reports (older, superseded in places):
`docs/research/kb/reports/agents/fnox-write-surface.md` (327 lines),
`.../mise-shell-activation.md`, `.../fnox-export-exec.md`,
`.../fnox-shell-activation.md`, `.../staleness-auditor-secrets-prose.md`;
decision record `docs/research/kb/decisions/secrets-cli-grilling-2026-08-04b.md`.

**Two things in those docs have drifted since 2026-08-03 — see §7.**

---

## 1. Which tool owns secrets

**fnox is the resolver, not the authority.** Four layers, from
`docs/secrets-doppler-fnox-keychain.md:64-73`:

| layer | role | what it holds |
|---|---|---|
| **Doppler** | shared authority — the value of record | project `dotfiles`, config **`dev_personal`** (49 secrets). Config `dev` (43, a strict subset) is a per-clone opt-out only |
| **fnox** | declaration + resolution + optional encrypted cache | `~/.config/fnox/config.toml`; 3 providers: `keychain`, `age`, `doppler_dotfiles_dev_personal` |
| **macOS Keychain** | machine-local bootstrap vault | service **`mde-fnox`**, 2 accounts: `DOPPLER_TOKEN` (unlocks everything else) and `DOPPLER_RO_TOKEN` (scoped RO, deliberately kept out of the shell) |
| **environment** | process delivery | injected by the zsh activation hook; never a source of truth |

Chain: **Keychain → `DOPPLER_TOKEN` → Doppler → fnox declaration → process env.**

So Doppler *and* Keychain are both wired, and both as **providers backing fnox** —
not as separate paths. Keychain holds exactly the bootstrap token; Doppler holds
everything else; `age` is an offline encrypted cache of Doppler's values.

### Is `~/.config/fnox/config.toml` generated, symlinked, templated or hand-written?

**GENERATED, by a sibling repo — not by dotfiles.** Its header reads *"Managed by
`mde-py secrets bootstrap-config`. Do not edit by hand."*
(`docs/secrets-doppler-fnox-keychain.md:151-153`).

The generator lives in `~/dev/github/ray-manaloto/macos-development-environment`
(`src/mde/secrets/manage.py`), installed **editable** into
`$MDE_PROJECT_DIR/.venv/bin/mde-py` — so *which code runs depends on which branch
that sibling repo has checked out*. There is no pinned copy
(`docs/secrets-doppler-fnox-keychain.md:161-164`).

> ✅ **Live check, 2026-08-21.** That clone is on branch
> `fix/bootstrap-config-reroute-through-fnox` at `691e866` — the **fixed** code.
> `grep -c _reconcile_declarations src/mde/secrets/manage.py` → **2**
> (control: a bogus symbol → **0**). `git merge-base --is-ancestor HEAD origin/main`
> says NOT an ancestor, which is expected: #83 was **squash**-merged as `716b17d`,
> so the branch commit differs while the code is the same. **The current checkout
> is safe** — the pre-fix template-rewrite class (mde#82) is not what is loaded.

**Nothing in `dotfiles` produces, templates or symlinks the fnox config.** dotfiles
consumes it. What dotfiles *does* own is the **baseline that detects drift in it**:
`doctor.toml` `[fnox]` pins `env = true` plus the full 50-name `env_true` set,
re-checked every session by `mise run doctor` (`fnox-baseline`).

---

## 2. The provider model, and which fnox verbs are actually used

Live, 2026-08-21 (`fnox 1.33.1`, `fnox check` / `fnox profiles` / `fnox list`,
names only):

```
$ fnox config-files
/Users/rmanaloto/.config/fnox/config.toml     # exactly one — rc=0

$ fnox check
Found 51 secret(s) in profile(s) · Found 3 provider(s) · ✓ healthy   (rc=0)

$ fnox profiles
default (51 secrets)                          # a single profile
```

Three providers; a declaration maps a **name** to a provider plus the provider's
own key, and never holds a value:

| provider | type | backs |
|---|---|---|
| `keychain` | macOS Keychain, service `mde-fnox` | **1** secret: `DOPPLER_TOKEN` — the bootstrap credential |
| `doppler_dotfiles_dev_personal` | Doppler, project `dotfiles`, config `dev_personal` | **50** secrets |
| `age` | local encrypted cache (`sync` target, not a primary) | **49** `sync = { provider = "age" }` blocks |

**50 secrets carry 49 sync blocks and that is correct.** `AGE_PRIVATE_KEY` is the
key that decrypts the age cache, so it cannot be cached in it. Do not "fix" 49→50.

A declaration line looks exactly like this (name only, no value):

```toml
KEY_NAME = { provider = "doppler_dotfiles_dev_personal", value = "KEY_NAME", env = true }
```

`value` is the **provider's key**, not the secret. `env = true` is per-secret and
**overrides the global** `env = true` at `~/.config/fnox/config.toml:2`.

### Which verbs dotfiles actually uses

| verb | used here? | where |
|---|---|---|
| `activate` | **YES — the primary delivery mechanism** | `eval "$(fnox activate zsh 2>/dev/null)"` — `macos-development-environment/home/dot_zshrc.d/50-mde-secrets.zsh:27-29` |
| `exec` | **YES, but only for the devcontainer bring-up** | `dotfiles/mise.toml:309` and `:349` — `fnox exec --non-interactive -- devcontainer up …` |
| `sync` | YES, indirectly | every `mde-secret-*` call runs `fnox sync --provider age --global --force` |
| `list` / `check` / `config-files` / `doctor` | YES — the sanctioned agent probes | agent contract, `docs/secrets-doppler-fnox-keychain.md:300-306` |
| `profiles` / `--profile` | present in 1.33.1, **not used** — a single `default` profile | `fnox profiles` output above |
| `get` / `export` | **FORBIDDEN to agents** — on the MUST NOT list | `docs/secrets-doppler-fnox-keychain.md:315-317` |
| `provider` / `import` / `set` / `lease` / `proxy` / `mcp` / `scan` / `daemon` | **not wired** | see the control arm below |

> 🔬 **Control arm on that last row.** `git grep -nI 'fnox scan' -- '*.pkl'` → **0**
> hits, against **14** for `gitleaks` under the *same command shape*, so the probe
> discriminates (`docs/secrets-doppler-fnox-keychain.md:585-589`). `fnox mcp`,
> `fnox proxy` and `fnox profiles` are listed there as unexplored surface worth a
> look, not as things that are wired.

### ⚠️ `_.fnox-env` is NOT the mechanism — the KB's note on this is wrong

The knowledge-base memory records that *"a `_.fnox-env` entry in the USER-level
mise config is what causes mise to redact values."* **Re-probed 2026-08-21 and
that is not what is configured.** In `~/.config/mise/config.toml`:

```toml
# ~/.config/mise/config.toml:68-79  (values elided)
# mise-env-fnox is intentionally disabled. Empirical reproduction on
# 2026-04-09 showed that enabling it spawns runaway `fnox config-files`
# subprocesses (10+ concurrent at 100% CPU each, shell hangs during
# login-shell sourcing). Authoritative rationale + repro + suspected root
# causes are tracked in:
#   https://github.com/ray-manaloto/macos-development-environment/issues/75
# Secrets env loading is now handled by `fnox activate zsh` in
# home/dot_zshrc.d/50-mde-secrets.zsh, which installs chpwd/precmd hooks
# that decrypt the age-encrypted sync cache into the shell environment.
# See docs/secrets-workflow.md for the full architecture.
[plugins]
fnox-env = "<ELIDED — the plugin URL>"

[env]
…
# ~/.config/mise/config.toml:90
#_.fnox-env = { tools = true }        # <-- COMMENTED OUT
```

So: the **plugin is registered** under `[plugins]` (line 79) but the `[env]`
directive that would activate it is **commented out** (line 90). Two consequences
for anyone writing operator notes:

1. **fnox does not deliver secrets through mise at all.** `fnox activate zsh`
   does, via chpwd/precmd hooks in the shell.
2. **The redaction mise performs is therefore not attributable to `_.fnox-env`.**
   The credentials are ordinary inherited environment variables by the time mise
   runs; mise redacts what it recognises as secret-valued in task output. The
   *effect* the KB note describes is real (mise mangles branch names, SHAs and PR
   numbers in `mise run` output — `docs/secrets-doppler-fnox-keychain.md:580-582`
   records the same thing for short all-digit values); the *cause* it names is not
   configured on this host.

> 🔬 **Control arm.** `grep -n fnox ~/.config/mise/config.toml` → 8 hits (so the
> probe finds fnox lines), of which line 90 is the `_.fnox-env` directive and it
> is comment-prefixed. `grep -c fnox home/dot_config/mise/config.toml.tmpl` → **0**
> in the dotfiles template, against a control of 3 for `settings|env` in that same
> 77-line file — so dotfiles' own mise template mentions fnox nowhere either.

### ⚠️ Which mise template is authoritative is itself contested

`~/.config/mise/config.toml:3-21` carries a warning worth reproducing: **two
chezmoi templates** claim this file —
`macos-development-environment/home/dot_config/mise/config.toml.tmpl` (what
chezmoi currently applies) and
`dotfiles/home/dot_config/mise/config.toml.tmpl` (the future owner, Ray
2026-08-20). Edit the mde one if you want a change to survive today. mise warns
`unknown config file type: …config.toml.tmpl` on every run about the dotfiles
copy — expected noise for a tracked template, not a fault.

---

## 3. THE MAIN QUESTION — how to add a new secret

### 3a. How a secret reaches the environment (the wiring, cited)

```zsh
# macos-development-environment/home/dot_zshrc.d/50-mde-secrets.zsh:24-29
# fnox activate: installs chpwd/precmd hooks that resolve secrets into env.
if command -v fnox >/dev/null 2>&1; then
  eval "$(fnox activate zsh 2>/dev/null)"
fi
```

That file is sourced by `~/.zshrc` through the `~/.zshrc.d/` loader (it is
deliberately framework-neutral — `:1-4`). It is deployed by **chezmoi from the
`macos-development-environment` repo, not from dotfiles**.

> 🔬 **Control-armed:** `find . -name '*mde-secrets*'` inside `dotfiles` → **0**
> hits, while the same `find` shape locates `./mise.toml` → 1. The file exists at
> `macos-development-environment/home/dot_zshrc.d/50-mde-secrets.zsh` and is applied
> to `~/.zshrc.d/50-mde-secrets.zsh` (the only file in that directory).

What `fnox activate zsh` installs (read from its own stdout, structure only):

```zsh
_fnox_hook() {
  trap -- '' SIGINT
  eval "$(…/mise/installs/fnox/1.33.1/fnox hook-env -s zsh)"
  trap - SIGINT
}
precmd_functions=( _fnox_hook … )     # every prompt
chpwd_functions=( _fnox_hook … )      # every cd
```

It also **replaces `fnox` with a shell function** so that `fnox shell` /
`fnox deactivate` can mutate the current shell (confirmed live: `which fnox`
prints a function body, not a path).

**Does an already-running session pick up a new secret?**

| consumer | picks up a new secret without restart? |
|---|---|
| an already-running **interactive zsh** | **YES** — `_fnox_hook` re-runs `fnox hook-env` at the *next prompt*; a bare `cd .` also triggers it |
| a **running** Claude Code / MCP server / `mise run` task / any non-interactive child | **NO** — it holds an env snapshot taken at spawn. `docs/secrets-doppler-fnox-keychain.md:568-570`: *"A running process keeps its env snapshot. After a rotation, restart consumers — a green write proves nothing about live processes."* |

`env = true` is set globally at `~/.config/fnox/config.toml:2` **and** inline on
every declaration, so a new secret is shell-visible by default. `fnox exec` is
**no longer a confinement boundary** — the parent shell already has everything
(`docs/secrets-doppler-fnox-keychain.md:31-32`).

### 3b. The literal procedure — manual path (the one to write down)

From `docs/secrets-doppler-fnox-keychain.md:378-424`, verified against the live
config shape. **Nine steps; do not skip 8.**

```sh
# 1. Decide: key name, consumer, scope, rotation expectation, and that no
#    existing credential can be reused.  The config is ALWAYS dev_personal.

# 2. (HUMAN) create/reveal the credential at the provider's own site.

# 3. Interactive setter — NO value argument, so nothing enters argv or history.
doppler secrets set 'KEY_NAME' \
  --project dotfiles --config dev_personal --silent

# 4. (HUMAN) type the value into the hidden prompt.

# 5. Confirm with a NAMES-ONLY listing (never `doppler secrets get`).
doppler secrets --project dotfiles --config dev_personal --only-names | grep KEY_NAME

# 6. Declare it in fnox.  The declaration holds the NAME, never the value.
fnox edit
#    add exactly this line:
#      KEY_NAME = { provider = "doppler_dotfiles_dev_personal", value = "KEY_NAME", env = true }

# 7. Optional offline cache.  --global is NOT optional (see the trap below).
fnox sync --global -p age KEY_NAME

# 8. REQUIRED: add "KEY_NAME" to doctor.toml's [fnox] env_true list,
#    in the SAME reviewed diff.        <-- this is the dotfiles commit
#    /Users/rmanaloto/dev/github/ray-manaloto/dotfiles/doctor.toml

# 9. Run a narrow consumer health check; report only the non-secret result.
```

**Never:** `doppler secrets set KEY 'value'` (lands in argv and shell history) or
`echo 'value' | doppler secrets set KEY` (plaintext through the tool call).

**Answers to the specific sub-questions:**

- **Which profile/config?** Doppler project `dotfiles`, config **`dev_personal`**.
  Since the 2026-08-03 alignment it serves the host *and* the devcontainer, so
  there is no judgement call left. `dev` is a per-clone opt-out set by a
  **top-level** `[env] DOPPLER_CONFIG = "dev"` in `mise.local.toml` — **never** a
  `[tasks.up]` block, which replaces the whole task. A credential written to `dev`
  reaches nothing by default, and **fails silently**.
  fnox itself has one `default` profile; `--write-profile` is **not** used here.
- **Is a sync/import/re-encrypt step required?** `fnox sync` is *optional* — it
  populates the offline age cache. Skipping it means the secret resolves through a
  live `doppler` subprocess on every read, which is the slow-and-hangable path
  (§6). ⚠️ **`--global` is mandatory**: without it fnox targets a `fnox.toml` in
  the *current directory*, not the user-root config the declaration lives in.
  The dry-run says `to provider age (global):` only with `-g`, and mde's own code
  uses `fnox sync --provider age --global --force`.
- **What gets committed to dotfiles?** **Only the `doctor.toml` `env_true` name.**
  Nothing else. The fnox config lives at `~/.config/fnox/` and is generated by the
  *other* repo; the value lives in Doppler; the age cache is local state.
  **Never commit:** an environment dump, a `__MISE_DIFF` assignment, a value, a
  `.env`, or the fnox config's contents.
- **Do NOT skip step 8.** `mise run doctor`'s `fnox-baseline` compares NAME SETS in
  both directions against `doctor.toml`. Skip it and the next session reports drift
  and someone "fixes" it back by deleting your secret.

> ✅ **Worked example, live in the tree right now.** `git diff doctor.toml` in
> dotfiles shows exactly one uncommitted line: `+ "CLAUDE_CODE_OAUTH_TOKEN",`.
> That is step 8 for the 51st secret, mid-flight. Live `fnox list` and
> `doctor.toml` both report **51** and the name sets match exactly (diff in both
> directions is empty; control: intersection = 51).

### 3c. The wrapper path — `mde-secret-add`

```sh
mde-secret-add KEY_NAME          # does steps 3-7 in one command
mde-secret-update KEY_NAME       # a literal alias for add
mde-secret-remove KEY_NAME       # (alias: mde-secret-rm)
```

These are **live zsh functions in every interactive shell**, not binaries
(`50-mde-secrets.zsh:59-83`). They are wrappers that `eval` the CLI's stdout so
`export KEY=…` takes effect in the *current* shell rather than a child
(`:31-34`), and they guard against the failure being upgraded to success —
`eval` runs only on rc=0 (`:36-56`).

> 🔬 **Control-armed:** `zsh -ic 'type mde-secret-add'` resolves; `type mde-bogus-zzz`
> does not. `which mde-py` returning rc=1 means **nothing** — the wrapper calls
> `$MDE_PROJECT_DIR/.venv/bin/mde-py` by absolute path.

**It still does NOT touch `doctor.toml`.** Step 8 remains manual either way.

**And it churns all 49 age sync ciphertexts on every call** — `add` / `update` /
`remove` each run a full `fnox sync --provider age --global --force`. mde#83 fixed
the config-rewrite class; it did not change the sync.

### 3d. 🔴 `mde-secret-add` is BROKEN on this host right now (2026-08-21)

```
$ .venv/bin/mde-py secrets --help
bad interpreter: …/macos-development-environment/.venv/bin/python: no such file or directory
```

Root cause, control-armed: the venv's `python` is a **dangling symlink** to
`~/.local/share/mise/installs/python/3.14.4/bin/python3.14`, and mise no longer
has 3.14.4 installed.

```
$ ls ~/.local/share/mise/installs/python/
3  3.13  3.13.12  3.13.14  3.14  3.14.5  3.14.6  3.14.7  latest     # no 3.14.4
$ ls ~/.local/share/mise/installs/python/3.14.4/bin/python3.14   -> No such file
$ ls ~/.local/share/mise/installs/python/3.14.7/bin/python3.14   -> exists   (control)
```

**The zsh wrapper's guard does not catch this.** It tests `[[ ! -x "$_bin" ]]`
(`50-mde-secrets.zsh:46`) — `mde-py` *is* executable; it is the interpreter in its
shebang that is gone. So you get a raw `bad interpreter` and rc≠0 rather than the
wrapper's friendly *"run `cd $MDE_PROJECT_DIR && uv sync`"* message.

**Fix before using the wrapper path:** `cd "$MDE_PROJECT_DIR" && uv sync`.
Until then, **use the manual 9-step procedure in §3b** — it depends on nothing
but `doppler` and `fnox`, both of which are healthy.

---

## 4. How mise consumes it

**Not through a fnox plugin.** See §2 — `_.fnox-env` is commented out at
`~/.config/mise/config.toml:90` and the plugin was disabled deliberately
(runaway `fnox config-files` subprocesses, mde#75). By the time mise runs, the
credentials are already ordinary inherited environment variables placed there by
`fnox activate zsh`, so mise inherits them like any other child.

Where mise *does* touch secrets in dotfiles:

| what | file:line | env vars involved |
|---|---|---|
| devcontainer bring-up wrapped in `fnox exec` | `mise.toml:309`, `mise.toml:349` | all 51, via `fnox exec --non-interactive -- devcontainer up --workspace-folder .` |
| `DOPPLER_PROJECT` / `DOPPLER_CONFIG` pinned per-task | `mise.toml:277`, `:343`, `:949` | `DOPPLER_PROJECT = "dotfiles"`, `DOPPLER_CONFIG = "{{ env.DOPPLER_CONFIG \| default(value='dev_personal') }}"` |
| S1 verification: the doppler env file exists and is non-empty | `mise.toml:948-969` | reads `${HOME}/.local/state/dotfiles/doppler.env`, asserts a count and the two `DOPPLER_*` names |
| `mise run doctor` — the fnox baseline check | `mise.toml:595-611` → `python/src/dotfiles_setup/doctor.py` | reads `~/.config/fnox/config.toml`; SessionStart hook; **always exits 0** unless `-- --strict` |
| `mise run reap` — clears wedged `fnox export` children | `mise.toml:1363-1376` → `reap.py` | see §6 |

⚠️ **The redaction the KB note is about is real, but its cause is mis-attributed.**
mise masks values it recognises in `mise run` output — and it over-matches: a short
all-digit value gets masked mid-token (`[redacted][redacted]3` for `113`), which is
why branch names, SHAs and PR numbers come out mangled
(`docs/secrets-doppler-fnox-keychain.md:580-582`). **The workaround the KB already
records is right** — read such figures from a non-`mise` invocation
(`uv run …`) or from a recorded `rc=`. Only the stated *mechanism*
(`_.fnox-env`) is wrong.

**Never run** `mise env --values`, `mise env --json`, or `mise set --values` —
they print live credentials.

---

## 5. Existing documentation — good, and mostly still right

**Yes, dotfiles documents this well; point at it rather than rewriting.** See §0
for the three files. Beyond those:

| path | what it adds |
|---|---|
| `docs/research/kb/reports/agents/fnox-write-surface.md` | 327 lines — the authorized write-probe study that **exonerated fnox** for the config wipe |
| `docs/research/kb/reports/agents/mise-shell-activation.md` | the `_` directive surface, and `:338` records that `_.fnox-env` is registered **but not enabled** |
| `docs/research/kb/reports/agents/fnox-export-exec.md` · `fnox-shell-activation.md` | export/exec semantics; `hook-env` internals |
| `docs/research/kb/decisions/secrets-cli-grilling-2026-08-04b.md` | the decision record behind the CLI shape |
| `docs/research/kb/artifacts/secrets-*.html` · `fnox-doppler-write.html` · `shell-activation.html` | published visual artifacts of the same research |
| `docs/receipts/{436,437,438,440,441,445,460,487,573}.md` | per-issue receipts |
| `docs/research/mintlify-cache/jdx/mise-env-fnox/llms-full.txt` | cached upstream plugin docs (the route not taken) |

The section worth quoting verbatim into any operator note is the **agent
operating contract**, `docs/secrets-doppler-fnox-keychain.md:296-330`:

> **An agent MAY**: resolve tool versions/paths · run `fnox config-files`,
> `fnox doctor`, `fnox check` · list names only (`doppler secrets --only-names`,
> `fnox list` **without** `--values`) · parse the config for **keys and field
> presence** · run dry-run sync/removal · ask a human to type a value into a
> hidden prompt · invoke a narrow consumer and report a non-secret result ·
> report key name, scope, operation, timestamp, outcome.
>
> **An agent MUST NOT**: ask for a secret to be pasted into chat · put a secret
> in a command argument, file, patch, fixture, or tool input · run
> `doppler secrets get`/`download`, `fnox get`, `fnox export`, or
> `fnox list --values` · run `printenv`/`env`/`set` or shell tracing inside a
> secret-injected process · **emit a credential value to its own stdout** · use
> `security … -w`/`-g` to display a Keychain value · read `~/.doppler`, the login
> Keychain DB, an age private key, or a `.env` for plaintext · add
> `--yes`/`--force` to a deletion without explicit authorization · treat a
> successful write as a completed rotation.

And the presence probe, `:334-336`:

```sh
zsh -c '[[ -v KEY_NAME ]] || exit 20; print "credential is present"'
```

⚠️ Its trap, `:338-352`: `${FOO:+SET}${FOO:-ABSENT}` **prints the value**. It
opens with the recommended construct so it reads as compliant, and on an *unset*
variable it looks perfect — which is why an unset-only control arm certifies
nothing. A live Doppler token reached a transcript this way on 2026-08-02.
Now denied by `hook_guard`'s `secret_value_substitution`.

---

## 6. Gotchas an operator will hit

Ordered by how much time each has cost, per the repo's own incident record.

1. 🔴 **A keychain authorization dialog hangs a background process FOREVER, and
   that hang is NOT a locked keychain.** fnox's doppler provider **shells out** to
   the `doppler` CLI (tell: `Doppler: command failed`), so any *uncached*
   doppler-primary secret resolves through a child `doppler` process. If that
   process needs a Keychain item a non-GUI process may not read, macOS raises a
   dialog nothing can answer.
   - Measured cost: **190 stuck processes, load 13.5**; and a separate pile of
     **1,174 wedged mise/shim/git processes each with a stuck `fnox export` child
     — 2,362 to clear, oldest 1d10h** (`mise.toml:1365-1368`).
   - `security show-keychain-info` **prompts unconditionally**, so *its* hang
     proves nothing. Believing it cost ~2 hours on 2026-08-02. The discriminating
     arm: **fnox reads a keychain secret in 0.03s**, which a locked keychain cannot do.
   - **Resolved on this host** by deleting the `doppler-cli` and `gh:github.com`
     keychain entries so both tools fall through to their ENV token.
   - Clear-up tool: `mise run reap -- --pattern 'fnox export'` (dry run; `--kill`
     to signal). ✅ Currently **0** wedged (control: `pgrep -fl fnox` → 1, so the
     probe fires).

2. 🔴 **A silently-empty credential is the default failure mode.** `${VAR:-}`
   interpolation in an MCP/plugin config yields an **empty string** for any
   credential that is absent, misnamed, or unset. The server starts, reports
   healthy, and degrades to an anonymous tier. **Check the consumer's
   authenticated identity, never its connection status.** (This is what the
   Context7 incident was.)

3. 🔴 **`fnox check` cannot see a LOST declaration — it can only pass.** Measured
   both arms on a throwaway fixture (`docs/secrets-doppler-fnox-keychain.md:441-452`):

   | fixture | `fnox check` |
   |---|---|
   | two probe keys **declared** | rc=0 · `Found 52 secret(s)` · ✓ healthy |
   | one declaration **deleted** | rc=0 · `Found 51 secret(s)` · ✓ healthy |

   `check` validates what is *declared*; a line that vanished is not "missing",
   it is unknown. Bare `check` also passes for a declared secret that does not
   resolve — `-a` warns, and only `--if-missing error` returns **rc=1**. The layer
   that CAN see a deletion is `doctor.toml`'s 51-name baseline.

4. ⚠️ **`-c` ADDS a config, it does not isolate one.** fnox merges
   `~/.config/fnox/config.toml` into **every** invocation. A test that forgets this
   reaches live user state — that is how **a mutation test wiped this host's fnox
   config on 2026-08-01**. `fnox config-files` is the arm that shows what is really
   loaded (live: exactly one line).

5. ⚠️ **`fnox sync --global` — `--global` is not optional.** Without it fnox targets
   a `fnox.toml` in the *current directory*, not the user-root config where the
   declaration lives. The dry-run prints `to provider age (global):` only with `-g`.

6. ⚠️ **Every `mde-secret-*` call churns all 49 age sync ciphertexts** (a full
   `fnox sync --provider age --global --force`). mde#83 fixed the config-rewrite
   class; it did not change the sync.

7. ⚠️ **The generator lives in an EDITABLE install of another repo.** Which code
   `mde-secret-add` runs depends on that clone's checked-out branch. Today it is
   `fix/bootstrap-config-reroute-through-fnox` @ `691e866` — the fixed code
   (`_reconcile_declarations` present ×2; control: bogus symbol → 0). One stale
   branch, `feat/secrets-crud-architecture-a`, still carries the **pre-fix template
   rewrite that silently drops declarations**. Nothing detects which branch you are
   on. Delete that branch and the residual risk is zero.

8. ⚠️ **A running process keeps its env snapshot.** After adding or rotating,
   restart consumers. An interactive zsh self-heals at the next prompt (§3a); a
   running Claude Code, MCP server or `mise run` task does not.

9. ⚠️ **`fnox sync` caches.** A Doppler change does not reach the encrypted age
   cache until you re-sync. Diagnose with `fnox sync --dry-run -p age KEY_NAME`,
   which reveals no values.

10. ⚠️ **A stale `MISE_ENV_CACHE` entry can serve a dead name in ONE directory**
    long after the config is byte-identically restored, and `grep` cannot see it —
    the cache is encrypted. Clear `~/.local/state/mise/env-cache`.

11. ⚠️ **Shell startup got slower** — 51 credentials resolve on activation instead
    of 4. The often-quoted "≈1.7s → ≈2.7s" is an **inherited figure the 2026-08-03
    rewrite could not reproduce**: three `zsh -ic true` runs measured
    **0.99s / 1.33s / 3.12s** (control `zsh -f` → 0.058s). Same-input variance
    exceeds the claimed 1s delta. Direction real, magnitude unestablished.

12. ⚠️ **Parse the fnox config, do not pattern-match it.** Three greps written for
    the 2026-08-03 rewrite returned confident zeros — `env = true }` matched 1 of 50
    (field order), `^[A-Z_]* = {` matched 0 (spacing), `grep -c 'env = true'` counted
    the header comment. `tomllib` answered all three in one pass.

**The gates that catch the mistakes** (`.claude/rules/secrets-out-of-the-shell-env.md:95-125`):
`no_env_dump` (hk → `dotfiles-setup env-blob-scan`, deliberately glob-less —
`__MISE_DIFF`, any base64 run decompressing to text naming ≥2 secret-bearing vars,
or a literal value); `betterleaks` (hk.pkl, host-only — it was *documented* as
running for months while wired nowhere); `gitleaks` + `detect_private_key`
(`hk-common.pkl:86,110`); `mise run doctor` (SessionStart); and `hook_guard`'s
`secret_value_substitution`. ⚠️ **No scanner can read `__MISE_DIFF`** — measured on
the same content in two forms, gitleaks 8.30.1 went **2 leaks → 0** and betterleaks
1.7.1 **1 → 0**; compression destroys the patterns both match on.

---

## 7. Live drift found while researching (2026-08-21) — 3 items

Each is a delta against what the docs say, measured today with a control arm.

### 7a. 🔴 FIVE Doppler secrets are not declared in fnox — they reach no shell

```
fnox declared          : 51
doppler dev_personal   : 58 names (55 real + 3 Doppler-auto-injected)

IN DOPPLER, NOT DECLARED IN FNOX  (unreachable from any shell or agent):
   - FIRECRAWL_API_KEY
   - GITHUB_PAT_TOKEN
   - GITHUB_PERSONAL_ACCESS_TOKEN
   - REPOWISE_KNOWLEDGE_BASE_API_KEY
   - REPO_RECOVERY_AGE_IDENTITY_20260813

DECLARED IN FNOX, NOT IN DOPPLER: DOPPLER_TOKEN   (correct — keychain-backed)
CONTROL (intersection): 50
```

This is **step 6 of §3b skipped** — the Doppler write happened, the fnox
declaration did not. It fails exactly as documented: silently.

> 🔬 **Directly relevant to the knowledge-base round in flight.**
> `REPOWISE_KNOWLEDGE_BASE_API_KEY` **exists in Doppler but is NOT in fnox and NOT
> in this shell.** Probed presence-only: `[[ -v REPOWISE_KNOWLEDGE_BASE_API_KEY ]]`
> → **ABSENT** (control: `[[ -v HOME ]]` → present, so the probe discriminates);
> `fnox list | grep -i repowise` → rc=1 (control: `grep -c CONTEXT7_API_KEY` → 1).
> **Before any Repowise API/MCP call can work, that secret needs §3b steps 6-8.**

### 7b. ⚠️ Every "50" in the docs is now **51**

`docs/secrets-doppler-fnox-keychain.md` states 50 declared / 49 doppler-backed
throughout. Live: **51 declared / 50 doppler-backed / 1 keychain / 49 age-sync**.
`doctor.toml` has already been updated to 51 but the change is **uncommitted**
(`git diff doctor.toml` → one added line, `+ "CLAUDE_CODE_OAUTH_TOKEN",`).
The 49 sync-block figure is unchanged and still correct.

### 7c. ⚠️ fnox is **1.33.1**, the docs were measured against **1.32.0**

`fnox --version` → `fnox 1.33.1`, resolved from
`~/.local/share/mise/installs/fnox/1.33.1/fnox`. Nothing observed today
contradicts the 1.32.0-era findings, but the "measured on 1.32.0" condition on
those tables no longer holds and should be re-stated rather than inherited.

---

## 8. What to write in operator notes — the short version

1. **Point at `dotfiles/docs/secrets-doppler-fnox-keychain.md`.** It is 593 lines,
   control-armed, and better than any summary. Do not rewrite it.
2. Carry forward the **chain** (Keychain → `DOPPLER_TOKEN` → Doppler → fnox → env),
   the **9-step add procedure** (§3b), and the **agent contract** (§5).
3. Correct two things the knowledge-base currently believes: `_.fnox-env` is
   **disabled** (§2), and the counts are **51/50/49** not 50/49/49 (§7b).
4. Flag the two live breakages: **`mde-secret-add` cannot run** (§3d) and **five
   Doppler secrets never reach a shell**, `REPOWISE_KNOWLEDGE_BASE_API_KEY`
   among them (§7a).

## GitHub repos touched

- [ray-manaloto/dotfiles](https://github.com/ray-manaloto/dotfiles) — the subject: read `docs/secrets-doppler-fnox-keychain.md`, `.claude/rules/secrets-out-of-the-shell-env.md`, `doctor.toml`, `mise.toml`, `hk-common.pkl`, `home/dot_config/mise/config.toml.tmpl`, and the `docs/research/kb/` reports.
- [ray-manaloto/macos-development-environment](https://github.com/ray-manaloto/macos-development-environment) — owns the fnox config generator (`src/mde/secrets/manage.py`), the zsh activation snippet (`home/dot_zshrc.d/50-mde-secrets.zsh`) and the chezmoi template that currently produces `~/.config/mise/config.toml`. Issues #75 (fnox-env plugin disabled), #82/#83 (config-wipe fix) read via the dotfiles docs that cite them.
- [jdx/fnox](https://github.com/jdx/fnox) — the secrets tool itself; probed live at 1.33.1 (`--version`, `config-files`, `check`, `profiles`, `list`, `activate zsh`).
- [jdx/mise-env-fnox](https://github.com/jdx/mise-env-fnox) — the mise env plugin route that dotfiles deliberately does NOT use; read via the cached upstream docs at `docs/research/mintlify-cache/jdx/mise-env-fnox/llms-full.txt`.
- [jdx/mise](https://github.com/jdx/mise) — env/redaction and `_` directive behaviour, read via the same cached docs and the dotfiles reports citing `src/env.rs:591`.
- [DopplerHQ/cli](https://github.com/DopplerHQ/cli) — the value-of-record CLI; probed names-only (`doppler secrets --only-names`).
- [gitleaks/gitleaks](https://github.com/gitleaks/gitleaks) — one of the two committed-secret scanners wired in `hk-common.pkl`.
