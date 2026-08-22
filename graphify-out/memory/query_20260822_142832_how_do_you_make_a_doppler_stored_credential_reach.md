---
type: "query"
date: "2026-08-22T14:28:32.747718+00:00"
question: "How do you make a Doppler-stored credential reach every shell, and what did this round get wrong on the way?"
contributor: "graphify"
outcome: "corrected"
correction: "THREE TIMES THIS ROUND A PROBE WAS THE BROKEN THING, and each cost more than the\nquestion was worth:\n\n1. `zsh -ic '<cmd>'` reported a credential ABSENT three times when it was already\n   declared, synced and resolving. `fnox activate` delivers via a `precmd` hook\n   and `zsh -c` never shows a prompt, so the hook never fires — it measures\n   INHERITANCE, not activation. The tell was an INVERTED CONTROL: `hook-env` is a\n   delta emitter, so it listed the new key and NOT the known-good control.\n2. `grep -c 'bootstrap-config|mde-secret'` over two directories returned 0 and\n   became \"dotfiles runs no sync\". That is a token-spelling bound — a\n   reimplementation under other names is invisible to it. The conclusion was\n   right by luck; only a control-armed probe for the ABSENT MODULE could\n   establish it.\n3. `gitleaks` reported \"no leaks found\" on a sample containing a planted\n   `AKIAIOSFODNN7EXAMPLE` — AWS's own documentation example, which gitleaks\n   allowlists. A control chosen from documentation is a control the tool is built\n   to ignore.\n\nTHE COMMON SHAPE: when the CONTROL looks wrong, suspect the probe before the\nworld. And a mutation/control must be something the check can actually see.\n\nFOURTH, ON MY OWN WRITING: I rewrote docs/secrets.md four times and each rewrite\nintroduced a contradiction with a part I did not re-read — a probe form the new\nsection calls broken, a reference to a table a prior rewrite deleted, counts\ninvalidated by the change in the same commit. One rewrite SILENTLY DELETED an\nentire section, found only by listing headings during an audit. Re-read the whole\ndocument after editing a part of it, or the document argues with itself.\n"
---

# Q: How do you make a Doppler-stored credential reach every shell, and what did this round get wrong on the way?

## Answer

The round asked: make credential management reachable from this repo, and get
REPOWISE_KNOWLEDGE_BASE_API_KEY working like the other Doppler-backed env vars.

WHAT SHIPPED (branch repowise-mcp-0821, 9 commits, gate-green at b499aecaf761,
NO review receipt): docs/secrets.md; three dotfiles secret docs vendored and
extracted (232 nodes); the decision record + takeover spec vendored and extracted
(193 nodes) so the corpus is not one-sided; mcp2cli==3.6.0 in the dev group; a
.gitignore row for graphify-out/.graph.html.stale; the research report promoted
to docs/research/reports/.

THE ANSWER TO THE ORIGINAL QUESTION turned out to be three answers, each
replacing the last:
1. "fnox does not have the key" — true, and incomplete.
2. "run mde-py secrets bootstrap-config" — right owner, WRONG VERB;
   bootstrap-config is the reconciler that `mde-py secrets add` calls.
3. The declaration is two commands, and they ARE the sanctioned mechanism:
   `fnox set KEY KEY --provider doppler_dotfiles_dev_personal --config <path>`
   then `fnox sync --global -p age --force KEY`. mde's `_fnox_declare`
   (manage.py:275) is literally that first call. The key name is the POSITIONAL
   value. `fnox set` alone leaves ['provider','value']; THE SYNC adds `env` and
   `sync`, producing the four-field shape every other declaration has.

THE STRUCTURAL FINDING, which outlives the credential: dotfiles DECIDED on
2026-08-04 to take secrets management over from macos-development-environment,
and decision D5 goes further — DROP FNOX, for Doppler + macOS Keychain. Nothing
was built; both artefacts say "This is a planning artifact. No code ships from
it." Three control-armed probes confirm no secrets verb-set exists. So the
runbook the corpus now holds describes an arrangement scheduled for replacement,
which is why the decision record had to be vendored alongside it.

ALSO IDENTIFIED: the .codex/config.toml writer, after eleven candidates were
refuted across two prior incidents — the ChatGPT desktop app's "Import from
another AI app" on autosync, evidenced by its own Import screen naming both files
at a timestamp matching the file's mtime to the second.


## Outcome

- Signal: corrected
- Correction: THREE TIMES THIS ROUND A PROBE WAS THE BROKEN THING, and each cost more than the
question was worth:

1. `zsh -ic '<cmd>'` reported a credential ABSENT three times when it was already
   declared, synced and resolving. `fnox activate` delivers via a `precmd` hook
   and `zsh -c` never shows a prompt, so the hook never fires — it measures
   INHERITANCE, not activation. The tell was an INVERTED CONTROL: `hook-env` is a
   delta emitter, so it listed the new key and NOT the known-good control.
2. `grep -c 'bootstrap-config|mde-secret'` over two directories returned 0 and
   became "dotfiles runs no sync". That is a token-spelling bound — a
   reimplementation under other names is invisible to it. The conclusion was
   right by luck; only a control-armed probe for the ABSENT MODULE could
   establish it.
3. `gitleaks` reported "no leaks found" on a sample containing a planted
   `AKIAIOSFODNN7EXAMPLE` — AWS's own documentation example, which gitleaks
   allowlists. A control chosen from documentation is a control the tool is built
   to ignore.

THE COMMON SHAPE: when the CONTROL looks wrong, suspect the probe before the
world. And a mutation/control must be something the check can actually see.

FOURTH, ON MY OWN WRITING: I rewrote docs/secrets.md four times and each rewrite
introduced a contradiction with a part I did not re-read — a probe form the new
section calls broken, a reference to a table a prior rewrite deleted, counts
invalidated by the change in the same commit. One rewrite SILENTLY DELETED an
entire section, found only by listing headings during an audit. Re-read the whole
document after editing a part of it, or the document argues with itself.
