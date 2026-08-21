---
type: "query"
date: "2026-08-21T22:45:37.954476+00:00"
question: "What is the CURRENT measured state of the fnox declarations, and how do you fix a name that is in Doppler but reaches no shell?"
contributor: "graphify"
outcome: "corrected"
correction: "`zsh -ic '<cmd>'` IS A BROKEN PROBE for a credential delivered by shell\nactivation. It reported ABSENT three times on a key that was already declared,\nsynced and resolving. `fnox activate` delivers through a `precmd` hook, and\n`zsh -c` runs a command without ever showing a prompt, so the hook never fires —\nthe probe measures env INHERITANCE from the calling shell, not activation.\n\nThe tell was an INVERTED CONTROL: `fnox hook-env -s zsh` emitted 2 export lines,\nthe new key among them, and the known-good control NOT AT ALL, because hook-env\nis a delta emitter and the control was already inherited. When the control looks\nbroken, suspect the probe, not the world.\n\nThe honest form fires the hook first:\n  zsh -ic 'eval \"$(fnox hook-env -s zsh)\"; [[ -v KEY ]] && print present'\nor just opens a new terminal.\n"
---

# Q: What is the CURRENT measured state of the fnox declarations, and how do you fix a name that is in Doppler but reaches no shell?

## Answer

MEASURED 2026-08-21, after REPOWISE_KNOWLEDGE_BASE_API_KEY was declared:
52 secrets declared in fnox, 51 carrying an age `sync` block, 52 carrying inline
`env = true`, global `env = true`. AGE_PRIVATE_KEY is the one without a sync
block — it decrypts the age cache, so `sync == declared - 1` is correct.

THE VENDORED dotfiles DOCS SAY 50 / 49, AND THEY ARE NOT WRONG. They were
measured on 2026-08-03 against the commit they are pinned at (6c9c5273df89), and
13 nodes in this corpus carry those figures. A pinned extraction records what a
source said at its commit; that is provenance, not staleness. What it is NOT is
a current measurement — re-derive with `tomllib` against
~/.config/fnox/config.toml before quoting any of them.

FIVE names were in Doppler and undeclared in fnox. REPOWISE_KNOWLEDGE_BASE_API_KEY
was fixed on 2026-08-21; FOUR remain: FIRECRAWL_API_KEY, GITHUB_PAT_TOKEN,
GITHUB_PERSONAL_ACCESS_TOKEN, REPO_RECOVERY_AGE_IDENTITY_20260813.

THE TWO COMMANDS THAT FIX ONE, and they are the sanctioned mechanism rather than
a workaround — mde's `_fnox_declare` (manage.py:275) is literally a `fnox set`
call:

  fnox set KEY KEY --provider doppler_dotfiles_dev_personal \
    --config "$HOME/.config/fnox/config.toml"
  fnox sync --global -p age --force KEY

The key name goes in as the POSITIONAL value; that is what lands `value = "<KEY>"`.
`fnox set` alone leaves ['provider','value'] — THE SYNC IS WHAT ADDS `env` AND
`sync`, producing the four-field shape every other declaration has. So the sync is
not merely an offline speed cache, which is what this repo's notes called it.

Safe only because the Doppler provider advertises RemoteRead: `fnox set` writes a
declaration and never a remote write. NEVER this shape for a keychain-backed
secret — that provider supports storage, so the positional would be written into
the keychain for real. Scope the sync to one key; the bulk form re-encrypts all 51.


## Outcome

- Signal: corrected
- Correction: `zsh -ic '<cmd>'` IS A BROKEN PROBE for a credential delivered by shell
activation. It reported ABSENT three times on a key that was already declared,
synced and resolving. `fnox activate` delivers through a `precmd` hook, and
`zsh -c` runs a command without ever showing a prompt, so the hook never fires —
the probe measures env INHERITANCE from the calling shell, not activation.

The tell was an INVERTED CONTROL: `fnox hook-env -s zsh` emitted 2 export lines,
the new key among them, and the known-good control NOT AT ALL, because hook-env
is a delta emitter and the control was already inherited. When the control looks
broken, suspect the probe, not the world.

The honest form fires the hook first:
  zsh -ic 'eval "$(fnox hook-env -s zsh)"; [[ -v KEY ]] && print present'
or just opens a new terminal.
