---
type: "query"
date: "2026-08-21T21:57:25.090444+00:00"
question: "Did dotfiles take secrets management over from macos-development-environment, and what is the add-a-credential path today?"
contributor: "graphify"
outcome: "corrected"
correction: "A corpus that ingests only the RUNBOOK for an arrangement is one-sided: it\nanswers \"how does this work\" with detail and says nothing about the arrangement\nhaving been decided-to-be-replaced. Vendoring the decision record alongside the\nrunbook is not documentation tidiness, it is corpus integrity — otherwise the\nnext session reads a superseded design as the intended one.\n\nThe probe error that made this necessary: concluding \"dotfiles runs no sync\"\nfrom a grep for the literal strings `bootstrap-config|mde-secret`. That is a\ntoken-spelling bound — a reimplementation under different names is invisible to\nit. The conclusion happened to be right, and the reasoning could not have\nestablished it; only a control-armed probe for the ABSENCE of a module could.\n"
---

# Q: Did dotfiles take secrets management over from macos-development-environment, and what is the add-a-credential path today?

## Answer

dotfiles DECIDED on 2026-08-04 to take credential management over from
`macos-development-environment`, and decision D5 goes further: DROP FNOX
entirely, for a Doppler + macOS Keychain stack. The north star, in Ray's words:
"Dev projects on the mac having a universal way to crud api keys secrets."

NOTHING WAS BUILT. Both artefacts carry the same banner — "This is a planning
artifact. No code ships from it." Verified 2026-08-21 by three independent
control-armed probes: no `secrets*.py` among 76 `dotfiles_setup` modules
(control: `doctor.py` present), nothing in the argparse registry, nothing in
live `--help`. Tracked as dotfiles #431, both halves unstarted.

So the OLD arrangement is the CURRENT arrangement: mde owns the chezmoi source
root, the shell fragment that populates every terminal, and all credential CRUD
— while mde itself has been deprecated since 2026-08-04.

Today's add path is `mde-secret-add KEY` (a shell function, not a binary),
covering steps 3-7 of the nine-step runbook. `bootstrap-config` is the
RECONCILER that `add_secret` calls, not the add path. Step 8 — adding the name
to `doctor.toml`'s reviewed `env_true` baseline — is still done BY HAND; an
uncommitted instance of exactly that edit sits in the dotfiles working tree.


## Outcome

- Signal: corrected
- Correction: A corpus that ingests only the RUNBOOK for an arrangement is one-sided: it
answers "how does this work" with detail and says nothing about the arrangement
having been decided-to-be-replaced. Vendoring the decision record alongside the
runbook is not documentation tidiness, it is corpus integrity — otherwise the
next session reads a superseded design as the intended one.

The probe error that made this necessary: concluding "dotfiles runs no sync"
from a grep for the literal strings `bootstrap-config|mde-secret`. That is a
token-spelling bound — a reimplementation under different names is invisible to
it. The conclusion happened to be right, and the reasoning could not have
established it; only a control-armed probe for the ABSENCE of a module could.
