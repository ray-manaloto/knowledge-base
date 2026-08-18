---
type: "query"
date: "2026-08-17T22:19:20.447602+00:00"
question: "How do you land a new secret in Doppler+fnox so it reaches the shell?"
contributor: "graphify"
outcome: "useful"
---

# Q: How do you land a new secret in Doppler+fnox so it reaches the shell?

## Answer

Landing a secret in fnox took three corrections, and each one was a real defect
a dry run or a probe caught rather than reasoning.

1. `fnox set KEY --provider P --key-name KEY` wrote `value = ""`. `--key-name`
   does NOT populate the declaration's `value` field; the provider key name is
   the **positional** argument: `fnox set KEY KEY --provider P`. With an empty
   value fnox asks Doppler for a zero-length secret name and fails with
   `Secret name must be at least one character long`.
2. `--non-interactive true` is a near-miss: clap accepts it and the trailing
   `true` is consumed as the POSITIONAL VALUE, so the dry run showed
   `value: true` — it would have written the literal string "true" as the
   credential. Use the env form `FNOX_NON_INTERACTIVE=true`.
3. **`fnox sync --global --provider age` is NOT optional.** The dotfiles doc
   calls it "Optional offline cache" at step 7; it is actually what makes a
   secret reach a shell. Evidence: 49 of 51 declarations carry a `sync`
   ciphertext and 48 were reachable; the two without one were the only two
   missing. It syncs exactly 1 secret — the 49-ciphertext churn the doc warns
   about is mde's wrapper, not fnox's.

Also measured: `fnox activate zsh` installs chpwd/precmd hooks, so a
`zsh -lc` probe resolves nothing itself — the secrets it sees are INHERITED
from the ancestor shell. A newly-added secret therefore cannot appear in any
shell descended from a session that predates it, and `fnox exec` is the honest
proof of resolution. `mde-secret-add` is not needed at all: `fnox set` is
native, has `--dry-run`, and skips mde entirely (mde is checked out on a fix
branch with a dirty tree; dotfiles has not taken secret-add over — 62
`dotfiles_setup` modules, none secrets/fnox).


## Outcome

- Signal: useful