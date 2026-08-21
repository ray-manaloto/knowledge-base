# Secrets — where they live, and what an agent in THIS repo may do with them

This repo consumes credentials; it does not own them. The mechanism, the
authority and the enforcement all live in the sibling
[`ray-manaloto/dotfiles`](https://github.com/ray-manaloto/dotfiles), and this
file exists because none of that was reachable from here — a session asking
"how do I add a secret?" got nothing from `docs/`, nothing from `CLAUDE.md`, and
**zero nodes from the graph** (`fnox` → 0, against a 955-node `graphify`
control, 2026-08-21).

**Do not rewrite the dotfiles docs here.** They are 1,355 lines, measured with
control arms, and they move. This file points at them, records the parts that
bind an agent *in this repo*, and flags what this repo does not enforce.

## The authority

Vendored into the corpus at dotfiles commit `6c9c5273df89` so `kb-query` can
answer from them (`sources/media/dotfiles-secrets-*.md`). Read the live copies
when it matters — the vendored ones are a snapshot:

| in dotfiles | lines | what it is |
|---|---:|---|
| `docs/secrets-doppler-fnox-keychain.md` | 593 | the canonical guide: four-layer model, agent contract, add/rotate recipes, diagnosis ladder, incident log |
| `.claude/rules/secrets-out-of-the-shell-env.md` | 196 | the posture rule and the four gates that enforce it |
| `docs/rules-evidence/secrets-out-of-the-shell-env.md` | 566 | the measurement annex — probe tables, the config-wipe timeline, the pre-reversal sections verbatim |

## The chain, in one line

**macOS Keychain → `DOPPLER_TOKEN` → Doppler → fnox declaration → process env.**

- **Doppler** is the value of record — project `dotfiles`, config
  **`dev_personal`** (the host *and* the devcontainer since the 2026-08-03
  alignment, so there is no judgement call left).
- **fnox** declares and resolves; it holds names and provider keys, never
  values. One `default` profile, one config file
  (`~/.config/fnox/config.toml`), three providers: `keychain` (1 secret — the
  bootstrap `DOPPLER_TOKEN`), `doppler_dotfiles_dev_personal` (50), and `age`
  (49 offline-cache `sync` blocks — `AGE_PRIVATE_KEY` cannot cache itself, so
  49 ≠ 50 is correct and must not be "fixed").
- **The environment** is delivery, never a source of truth. Secrets arrive via
  `fnox activate zsh`'s chpwd/precmd hooks, installed by
  `macos-development-environment/home/dot_zshrc.d/50-mde-secrets.zsh:27-29`.

`~/.config/fnox/config.toml` is **generated** — its header says *"Managed by
`mde-py secrets bootstrap-config`. Do not edit by hand."* — by a third repo,
`macos-development-environment`, installed editable. Which code runs therefore
depends on that clone's branch. Nothing in dotfiles produces it; what dotfiles
owns is the drift detector (`doctor.toml` `[fnox]`).

## The agent contract — this is the part that binds a session here

**Allowed** (names, health and structure only): `fnox list`, `fnox check`,
`fnox config-files`, `fnox profiles`, `fnox doctor`, `mise run doctor`, and
`doppler secrets --only-names`.

**Forbidden**: `fnox get`, `fnox export`, `fnox list --values`,
`doppler secrets get`/`download`, `security … -w`/`-g`, `printenv`/`env`/`set`
inside a secret-injected process, reading `~/.doppler` or an age private key,
and emitting a credential value to stdout in any form.

Presence is probed **without** revealing anything:

```sh
zsh -c '[[ -v KEY_NAME ]] || exit 20; print "credential is present"'
```

⚠️ **`${FOO:+SET}${FOO:-ABSENT}` PRINTS THE VALUE when the variable is set.** It
opens with the recommended construct so it reads as compliant, and on an *unset*
variable it looks perfect — so an unset-only control arm certifies nothing. A
live Doppler token reached a transcript this way on 2026-08-02. dotfiles denies
it at the hook (`secret_value_substitution`); **this repo does not** — see
"What this repo does not enforce" below.

## Adding a secret — the nine steps

Condensed from `docs/secrets-doppler-fnox-keychain.md:378-424`; the vendored
copy carries the full text. **Steps 2 and 4 are the human's** — a value is never
typed by an agent, and never appears in argv, history or a tool call.

```sh
# 1. Decide the name, consumer, scope and rotation expectation, and confirm no
#    existing credential can be reused. The config is ALWAYS dev_personal.
# 2. (HUMAN) create or reveal the credential at the provider's own site.

# 3. Interactive setter — NO value argument, so nothing enters argv or history.
doppler secrets set 'KEY_NAME' --project dotfiles --config dev_personal --silent
# 4. (HUMAN) type the value into the hidden prompt.

# 5. Confirm with a NAMES-ONLY listing (never `doppler secrets get`).
doppler secrets --project dotfiles --config dev_personal --only-names | grep KEY_NAME

# 6. Declare it in fnox. The declaration holds the NAME, never the value.
fnox edit
#    KEY_NAME = { provider = "doppler_dotfiles_dev_personal", value = "KEY_NAME", env = true }
#    `value` is the PROVIDER'S KEY, not the secret.

# 7. Optional offline age cache. `--global` is NOT optional (see the trap).
fnox sync --global -p age KEY_NAME

# 8. REQUIRED — add "KEY_NAME" to doctor.toml's [fnox] env_true list in the SAME
#    reviewed diff. This is the only thing that gets committed to dotfiles.
# 9. Run a narrow consumer health check; report only the non-secret result.
```

**Never** `doppler secrets set KEY 'value'` (argv + history) or
`echo 'value' | doppler secrets set KEY` (plaintext through the tool call).

Three traps worth not rediscovering:

- **`fnox sync` without `--global`** targets a `fnox.toml` in the *current
  directory*, not the user-root config the declaration lives in. The dry-run
  says `to provider age (global):` only with `-g`.
- **Skipping step 8** makes `mise run doctor`'s `fnox-baseline` report drift in
  the next session, and someone "fixes" it by deleting the new secret.
- **Doppler config `dev`** is a per-clone opt-out set by a **top-level**
  `[env] DOPPLER_CONFIG = "dev"` in `mise.local.toml` — never a `[tasks.up]`
  block, which replaces the whole task. A credential written to `dev` reaches
  nothing by default, and **fails silently**.

The wrapper `mde-secret-add KEY_NAME` does steps 3–7 in one command (a live zsh
function, not a binary) but **still does not touch `doctor.toml`** — step 8 is
manual either way. As of 2026-08-21 the wrapper is **broken on this host**: the
mde venv's `python` is a dangling symlink to a mise python 3.14.4 that is no
longer installed, and the wrapper's `[[ ! -x "$_bin" ]]` guard does not catch a
dead *interpreter*, so it surfaces as a raw `bad interpreter`. Fix with
`cd "$MDE_PROJECT_DIR" && uv sync`, or use the manual path, which depends only
on `doppler` and `fnox`.

## Diagnosing "the credential is missing"

The failure this repo has already hit twice: **a name written to Doppler but
never declared in fnox reaches no shell, and fails silently.** That is step 6 of
the nine skipped, and nothing announces it — `doppler secrets set` succeeded, so
it looks done.

Two names-only listings settle it in seconds:

```sh
fnox list                                             # what is DECLARED
doppler secrets --project dotfiles --config dev_personal --only-names   # what is STORED
```

A name in the second and not the first is the silent case. A name in the first
and not the second is normal for exactly one entry — `DOPPLER_TOKEN`, which is
keychain-backed by design.

**Measured 2026-08-21: five names were in Doppler and not in fnox** —
`FIRECRAWL_API_KEY`, `GITHUB_PAT_TOKEN`, `GITHUB_PERSONAL_ACCESS_TOKEN`,
`REPOWISE_KNOWLEDGE_BASE_API_KEY` and `REPO_RECOVERY_AGE_IDENTITY_20260813`
(51 declared vs 58 Doppler names, of which 55 are real; intersection 50). The
remedy for each is steps 6-8, not a re-write of the value.

**Do not conclude "the key does not exist" from a fnox probe alone.** `fnox get`
returning nothing is consistent with *never declared* as well as *never created*,
and those have different fixes. It is also a forbidden verb — the honest probe is
`fnox list` against the Doppler names-only listing above.

## The mise redaction trap — and a correction to our own note

mise redaction is a **display** feature: it intercepts task output line by line
and replaces any literal occurrence of a redacted value. `jdx/mise`
`src/redactions.rs:64-81` is an Aho-Corasick multi-pattern replace with **no
word boundaries and no length floor**, so a short secret rewrites unrelated
text — its own test asserts `"token1 and token2"` → `"[redacted]1 and
[redacted]2"`.

**Consequence for every session here: any figure `mise run` prints may be
mangled** — branch names, SHAs, PR numbers. Re-read them from `uv run kb-setup
<cmd>` or plain `git`, which is why `mise-tasks-only.md` carries that exception
for `session-state`.

**`mise.toml:370` attributes this to `_.fnox-env = { tools = true }` in the user
mise config. That attribution is stale.** Re-probed 2026-08-21: the directive is
**commented out** (`~/.config/mise/config.toml:90`) and the plugin, while
registered under `[plugins]`, is deliberately disabled — enabling it spawned
runaway `fnox config-files` subprocesses (mde#75). Secrets do not reach mise
through fnox at all; they are ordinary inherited environment variables by the
time mise runs. The *effect* that note describes is real and still bites; the
*cause* it names is not configured on this host.

## What this repo does NOT enforce

dotfiles denies the value-revealing commands at its PreToolUse hook. **This repo
has no equivalent** — `kb_setup.hook_guard` has no `secret_value_substitution`
and no `fnox get` / `doppler secrets get` redirect (armed 2026-08-21: 0 matches,
against a control of four guards that do exist here — `absent_binary`,
`check_first`, `graph_first`, `stage_explicitly`).

That gap is not theoretical. The session that wrote this file ran
`fnox get GEMINI_API_KEY | wc -c` as a control arm — no value printed or stored,
but a forbidden verb, run precisely because the contract forbidding it was
unreachable from here. This repo's own measurement says a warning does not fix
that class and a deny does (graph-first: 0 of 19 warned vs 62 → 0 denied).

## See also

- `sources/media/dotfiles-secrets-{guide,rule,evidence}.md` — the vendored
  copies, pinned at dotfiles `6c9c5273df89`.
- `mise.toml:360-410` — this repo's redaction writeup, with the correction above.
- `currency.toml` `[tool.fnox]` — fnox is tracked here as an ordinary pinned
  tool (Ray, 2026-07-31: "track it like hk"); this repo touches nothing under
  `~/.config/fnox`.
- `.claude/rules/do-not.md` #11 — this repo edits PROJECT settings only, which
  is why the procedure above is documented here and performed there.
