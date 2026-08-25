---
type: "query"
date: "2026-08-25T00:23:18.701606+00:00"
question: "How do I add/update a secret via fnox/Doppler/macOS Keychain, and what actually makes it reach the shell environment?"
contributor: "graphify"
outcome: "useful"
---

# Q: How do I add/update a secret via fnox/Doppler/macOS Keychain, and what actually makes it reach the shell environment?

## Answer

ASK THE GRAPH FIRST — this answer was already in it, and re-researching it cost hours.

`mise run kb-query -- "how do I add a new secret with fnox doppler keychain, and
what makes it reach the shell environment" --prose --idf`

returns the whole workflow, ranked, source-cited. The decisive row (rank 19,
src=sources/media/dotfiles-secrets-evidence.md) states the root cause outright:

  "`env = true` (fnox's own default) is exported to the interactive shell /
   `fnox export`, `fnox exec`, AND `fnox get`. `env = "exec"` is NOT exported to
   the interactive shell. `env = false` is not available to the shell OR
   `fnox exec`. A secret being declared and resolvable does NOT by itself mean it
   reaches the shell — that depends entirely on this per-secret/global `env`
   setting."

THE WORKFLOW, from the graph plus this session's measurements:

  chain: macOS Keychain -> DOPPLER_TOKEN -> Doppler -> fnox declaration -> process env
  Doppler project `dotfiles`, config `dev_personal`.

  1-5. Store the value: `doppler secrets set 'KEY' --project dotfiles
       --config dev_personal --silent` (no value argument — argv and history),
       human types it at the hidden prompt, confirm with a NAMES-ONLY listing.
  6.   Declare it in fnox. Several names stranded -> `mde-py secrets
       bootstrap-config` (whole-config reconcile). One name -> `fnox set KEY KEY
       --provider doppler_dotfiles_dev_personal`. NEVER hand-write the block.
  7.   `fnox sync --global -p age KEY --force`. Without --force it BLOCKS on an
       interactive "Continue? [y/N]" — a 7-minute hang, measured 2026-08-24.
  8.   Add the name to dotfiles `doctor.toml` [fnox] env_true — a drift baseline.
  9.   `env = true` on the declaration is what actually exports it, and NOTHING in
       the runbook sets it. bootstrap-config leaves env=false; adding the name to
       doctor.toml does NOT flip it (tested and refuted 2026-08-24). mde's own
       source calls `env` a hand-added field its reconciler preserves but never
       sets (manage.py:305,388). This is dotfiles#787.

DIAGNOSIS, all from the graph:

  - Stored in Doppler but undeclared in fnox = reaches no shell, silently, because
    `doppler secrets set` succeeded. Compare two names-only listings: `fnox list`
    vs `doppler secrets --only-names`.
  - A HUNG doppler CLI is suspect #1 for a stall: fnox's doppler provider shells
    out, and a keychain authorization dialog blocks that child forever from a
    non-GUI process.
  - A hang is NOT evidence of a locked keychain. `security show-keychain-info`
    prompts unconditionally, so its hang proves nothing — that belief cost ~2
    hours on 2026-08-02.

PROBING, without leaking:

  - Presence is `[[ -v KEY ]]`. NEVER `${KEY:+SET}` — it PRINTS the value when set
    and looks perfect on an unset control arm.
  - The delivery hook is chpwd/precmd-bound, so NO `zsh -c` shell can observe it,
    and such a shell INHERITS the parent env — a merely-inherited value reads as
    PRESENT and fakes a pass. Both directions were hit on 2026-08-24. The honest
    check is a real prompt; fnox announces its own load as `fnox: +N <names>`.
  - Values reach the shell env at all only because `env = true`; the 2026-07-27
    incident shows mise's __MISE_DIFF then carries the whole delta, compressed,
    into every child process.

WHY THIS WAS RE-RESEARCHED ANYWAY: the graph_first hook denies a repo-WIDE search
until one graph query has run, but by design never denies a `Read` of a named file
or a search scoped to ONE file. An evening spent `sed -n`-ing docs/secrets.md is
fully permitted and never triggers the guard. The knowledge was present; the
retrieval discipline was not.


## Outcome

- Signal: useful