# Secrets — where they live, and what an agent in THIS repo may do with them

> ⚠️ **Everything below describes an arrangement that was decided to be
> REPLACED, and the replacement has not been built.** On 2026-08-04 dotfiles
> resolved to take credential management over from
> `macos-development-environment` — and decision **D5 goes further: drop fnox
> entirely**, for Doppler + macOS Keychain. Both artefacts carry the same banner:
> *"This is a planning artifact. No code ships from it."* Verified 2026-08-21 by
> three control-armed probes: **nothing is built.** So the fnox runbook here is
> what RUNS, not what was intended to last. See "The takeover" below before
> treating any of it as the end state.

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

⚠️ **A bare `#N` in any of them is another repo's issue** — `dotfiles` or
`macos-development-environment` — never one of ours, and this corpus's
own #418, #432 and #441 all exist and are unrelated. It is not derivable which:
only a minority are markdown-linked, and the unlinked default is inconsistent
(`macos-development-environment#82` is qualified inline while `#83`, also an
mde issue, is bare). Each vendored file carries this caveat in its `issue_refs`
frontmatter; treat an unlinked ref as AMBIGUOUS and resolve it upstream.

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
  bootstrap `DOPPLER_TOKEN`), `doppler_dotfiles_dev_personal`, and `age`
  (offline-cache `sync` blocks). **Measured 2026-08-21: 52 declared, 51 with a
  sync block, 52 with inline `env = true`.** `AGE_PRIVATE_KEY` is the one without
  a sync block — it decrypts the age cache, so it cannot live in it, and
  `sync == declared - 1` is correct and must not be "fixed". Every count here
  moves whenever a credential is added; re-derive with `tomllib` rather than
  quoting this line. The vendored dotfiles docs say **50/49**, correctly, for
  their pinned commit.
- **The environment** is delivery, never a source of truth. Secrets arrive via
  `fnox activate zsh`'s chpwd/precmd hooks, installed by
  `macos-development-environment/home/dot_zshrc.d/50-mde-secrets.zsh:27-29`.

`~/.config/fnox/config.toml` is owned by `mde-py secrets bootstrap-config` — its
header says *"Managed by … Do not edit by hand."* — from a third repo,
`macos-development-environment`, installed editable, so which code runs depends on
that clone's branch.

**It RECONCILES; it does not regenerate.** Since mde #83 (`716b17d`, 2026-08-03)
it adds and drops declarations by invoking `fnox`, writing the file directly only
when it does not exist. The "regenerates from a template" behaviour — which lost
the `env` mode and every opt-in by construction — is pre-fix, and survives only on
one stale local branch. Saying "generated" invites the wrong mental model of the
blast radius.

What dotfiles owns is the drift detector (`doctor.toml` `[fnox]`) — and not
passively: its `env_true` list is a reviewed baseline **a human hand-edits on
every add**.

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

⚠️ That form only sees what the CALLING shell already has. For a credential just
declared, fire the activation hook or open a new terminal — see "Diagnosing" below.

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

# 6. Declare it in fnox. The declaration holds the NAME, never the value:
#    KEY_NAME = { provider = "doppler_dotfiles_dev_personal", value = "KEY_NAME", env = true }
#    `value` is the PROVIDER'S KEY, not the secret.
#    ⚠️ The guide shows `fnox edit`. Prefer `fnox set KEY KEY --provider …`,
#    which is what the reconciler itself runs — see "Fixing a stranded name".

# 7. Age sync. `--global` is NOT optional, and neither is this step if you want
#    the declaration to MATCH the others — see below.
fnox sync --global -p age KEY_NAME

# 8. The reviewed PROCESS requires this: add "KEY_NAME" to doctor.toml's [fnox]
#    env_true list in the SAME diff. The only thing committed to dotfiles.
#    Not required for the credential to WORK; required so `mise run doctor`
#    does not report it as unsanctioned drift, which a later session may
#    "fix" by deleting it.
# 9. Run a narrow consumer health check; report only the non-secret result.
```

**Never** `doppler secrets set KEY 'value'` (argv + history) or
`echo 'value' | doppler secrets set KEY` (plaintext through the tool call).

### Which command actually adds one, today

**`mde-secret-add KEY_NAME`** — a shell function (not a binary) from
`~/.zshrc.d/50-mde-secrets.zsh`, sourced from **mde**, which calls
`$MDE_PROJECT_DIR/.venv/bin/mde-py secrets add KEY` and `eval`s the emitted
`export` line so the value lands in the *current* shell. It covers **steps 3–7**.

`which mde-py` returning rc=1 proves nothing — it is never on `$PATH`; only the
function reaches it (control: `which doppler` resolves).

**Step 8 is still yours by hand**, and there is live proof: the dotfiles working
tree currently carries an uncommitted `doctor.toml` edit adding
`+ "CLAUDE_CODE_OAUTH_TOKEN",`. The takeover spec's user story 2 — *"I want the
add verb to update the reviewed baseline in the same run"* — is exactly what does
not exist yet.

**`bootstrap-config` is the reconciler, not the add path.** `add_secret`
(`manage.py:151`) calls it as its own step 6, to give the new key a fnox entry.
Reach for it directly only in the case this round hit: a credential **already in
Doppler that reaches no shell**, where reconciling is the whole fix.

⚠️ **Do not hand-write a declaration** (`fnox set --global`, or editing the config)
— the file's header says *"Managed by `mde-py secrets bootstrap-config`. Do not
edit by hand."* An earlier version of this section recommended exactly that, and
was wrong (Ray, 2026-08-21: *"i dont want to invent a new way"*).

## Diagnosing "the credential is missing"

**A name written to Doppler but never declared in fnox reaches no shell, and
fails silently** — `doppler secrets set` succeeded, so it looks done. Two
names-only listings settle it:

```sh
fnox list                                                              # DECLARED
doppler secrets --project dotfiles --config dev_personal --only-names  # STORED
```

A name in the second and not the first is that case. A name in the first and not
the second is normal for exactly one entry — `DOPPLER_TOKEN`, keychain-backed by
design.

**Measured 2026-08-21: five names were stranded that way.**
`REPOWISE_KNOWLEDGE_BASE_API_KEY` was fixed the same day; **four remain** —
`FIRECRAWL_API_KEY`, `GITHUB_PAT_TOKEN`, `GITHUB_PERSONAL_ACCESS_TOKEN`,
`REPO_RECOVERY_AGE_IDENTITY_20260813`.

### ⚠️ `zsh -ic '<cmd>'` is a BROKEN probe for this

It reported ABSENT three times on a credential that was already correctly
declared, synced and resolving. `fnox activate` delivers through a **`precmd`
hook**, and `zsh -c` runs a command without ever showing a prompt, so the hook
never fires — the probe measures env *inheritance from the calling shell*, not
activation.

The tell was an inverted control: `fnox hook-env -s zsh` emitted **2** export
lines, the new key among them, and the known-good control **not at all** — because
`hook-env` is a **delta emitter** and the control was already inherited. A probe
whose control looks broken is usually the probe.

The honest forms:

```sh
# fire the hook, as a prompt would
zsh -ic 'eval "$(fnox hook-env -s zsh)"; [[ -v KEY_NAME ]] && print present || print ABSENT'

# or just open a new terminal
```

`fnox exec -- …` resolving while the shell does not is the guide's documented
"REAL FAULT" signature — but only once the probe itself is sound.

### Fixing a stranded name — the two commands

```sh
fnox set KEY_NAME KEY_NAME --provider doppler_dotfiles_dev_personal \
  --config "$HOME/.config/fnox/config.toml"
fnox sync --global -p age --force KEY_NAME
```

This is what mde's `add_secret` runs internally (`_fnox_declare`, `manage.py:275`,
is literally a `fnox set` call), so it is the sanctioned mechanism, not a
workaround. The key name goes in as the **positional value** — that is what lands
`value = "<KEY>"` in the declaration.

`fnox set` alone leaves `['provider', 'value']`; **the sync is what adds `env` and
`sync`**, giving the four-field shape every other declaration has. So step 7 is
not merely a speed cache, which is what an earlier version of this file called it.

⚠️ **Safe only because the provider is Doppler**, which advertises `RemoteRead`
only — `fnox set` writes a declaration and never a remote write. **Never this
shape for a `keychain`-backed secret**: that provider supports storage, so the
positional value would be written into the keychain for real.

Scope the sync to the one key. mde's bulk form re-encrypts all 51 ciphertexts on
every call.

## The takeover — decided 2026-08-04, not built

`docs/research/kb/decisions/secrets-cli-grilling-2026-08-04b.md` (vendored here as
`sources/media/dotfiles-secrets-decision.md`) records six decisions. The north
star, in Ray's words:

> *"Dev projects on the mac having a universal way to crud api keys secrets."*

| | decision | status |
|---|---|---|
| D1 | scoping = additive declaration + reconcile; buys **zero confinement**, accepted | settled |
| D2 | declarations use fnox's native hierarchy | **voided by D5** |
| D3 | storage is the status quo — Keychain holds only `DOPPLER_TOKEN`, Doppler owns CRUD | settled |
| D4 | the highest-value verbs are **rotate / classify / retire**, not create | settled |
| **D5** | **DROP FNOX. The stack becomes Doppler + macOS Keychain.** Reverses the earlier "fnox stays" ruling, on measurement | **settled** |
| D6 | language deferred, near-zero variance | open |

**Built: nothing.** Three independent control-armed probes on 2026-08-21 — no
`secrets*.py` among 76 `dotfiles_setup` modules (control: `doctor.py` present),
nothing in the argparse registry, nothing in live `--help`.

The migration ledger (dotfiles **#431**, both halves unstarted) still has mde
owning the chezmoi source root, the shell fragment that populates every terminal,
and all credential CRUD — while mde is itself **deprecated** as of 2026-08-04.
Full ledger: `sources/media/dotfiles-secrets-takeover-spec.md`.

**Why this section exists at all.** Without it the corpus is one-sided: the three
runbook documents describe the fnox arrangement in detail and say nothing about
its being superseded, so a future session would read it as the intended design.
That is a corpus-integrity problem, not a documentation nicety.

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
