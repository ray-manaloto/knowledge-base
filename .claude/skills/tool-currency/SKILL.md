---
name: tool-currency
description: >-
  Run the full tool-currency due-diligence loop for this repo's pinned tooling
  (graphify first; mise/hk/uv/ruff/ty adopt the same shape): validate the install
  is in sync with the pin, the source manifest and the built graph; check for a
  new version; review its release notes; re-check tracked upstream issues; ask
  the user about anything still ambiguous; and commit a tracked report. Use
  whenever the user asks to check tool currency, asks whether tooling is up to
  date or in sync, wants to review release notes or tracked issues before a
  bump, or when the SessionStart hook reports drift. Also use after any graphify
  version change, and before ingesting or rebuilding the graph.
user-invocable: true
---

# Skill: Tool currency

Six steps. The engine (`kb_setup.currency`) does 1–4 and 6; **you** do step 5,
because `AskUserQuestion` can only be called by the model — which is exactly why
this is a skill and not a hook.

## When the SessionStart hook nudged you

The hook runs step 1 only and is silent when clean. If it printed drift, start
here — do not re-derive it.

## Procedure

### 1. Run the engine

```bash
mise run kb-currency -- --json
```

That writes the report under `docs/currency/` and prints a JSON payload per tool:
`sync` (step 1 findings), `upstream` (steps 2–3), `observations`/`moved`
(step 4), and `verdict` (the six-gate outcome).

For a fast, offline, step-1-only answer: `mise run kb-currency-check`.

### 2. Read the verdict before anything else

- `auto_apply: true` — all six gates passed. Proceed to step 4 below.
- `ambiguities: [...]` — **stop and ask**. Each entry already carries the
  `question`, the `detail` (evidence), and a `recommendation`.
- `feature_review: [...]` — **advisory, never blocking**. New-capability lines
  the release notes announced. Present these to the user even on a clean
  auto-apply (step 3a) — "should we adopt this?" is the other half of step 3 —
  but do NOT hold the bump for them.
- `tracked: false` — a presence-only tool (ffmpeg): there is no version to
  chase, so "latest UNKNOWN" is expected, not a failure.

### 3. Step 5 — interview the user

Put **each** ambiguity to the user with `AskUserQuestion`. Use the engine's
`question` verbatim as the question, lead with its `recommendation` as the first
option marked `(Recommended)`, and put the `detail` in the option descriptions so
the user sees the evidence, not just the ask.

Do not batch unrelated gates into one question, and do not answer on the user's
behalf — the whole point of an ambiguity is that the engine refused to guess.

Then record what they said, in the run's detail page under the matching
`### Gate:` heading, replacing `_not yet answered_`.

### 3a. Surface features to adopt (advisory)

If `feature_review` is non-empty, show it to the user as an FYI — one
AskUserQuestion, "these shipped; adopt any config change now, or note for
later?" — **separate from the gates and non-blocking**. A clean auto-apply still
proceeds; this only makes sure a new capability (a new flag, a new backend) does
not slip by unread. The detail page already lists them under "Features to
consider adopting".

### 4. Apply, only if the verdict authorized it

An auto-apply is a **patch** bump whose six gates passed. The engine does the
edits; you branch and ship.

1. Branch first — never commit to `main` (dotfiles
   `.claude/rules/do-not.md` #9; the same rule applies here).
2. Let the engine edit the committable files:

   ```bash
   mise run kb-currency -- --tool <name> apply
   ```

   `apply` re-checks the six gates and **refuses** an unauthorized verdict, then
   moves the `mise.toml` pin **and** re-pins `sources/<name>.manifest` (`ref` →
   the new tag, `commit` → its SHA via `git ls-remote`). It never rebuilds the
   graph and never opens the PR — that stays with you (H3/G8). It guards the
   v1.0.0-tagged-but-not-on-PyPI trap: a tag that resolves nowhere aborts before
   any file is touched.
3. `mise run kb-ship` — the only sanctioned way to open a PR here.

**The graph rebuild is NOT part of the PR.** `graphify-out/graph.json` is
gitignored, so a bump leaves the local graph built by the old version. Step 1
will report **rebuild pending** until you run `mise run kb-build`, which
re-stamps it. That is expected, not a failure.

### 5. Close the loop

If the run revealed something the config should track — a new upstream issue, a
new local finding — add it to `currency.toml` as a `[[tool.<name>.watch]]` entry
in the same change. A finding that is not tracked is a finding that will be
rediscovered.

## Guardrails

- **Never widen the six-gate bar to make a bump pass.** The bar is in
  `decide.py` and fails closed by design; an unreadable release note is
  ambiguity, not consent. Changing it is a deliberate decision to discuss with
  the user, never a way past a specific bump.
- **Never stamp by hand to clear a `rebuild pending`.** `kb-setup currency stamp`
  exists for the build task; running it against artifacts you did not just build
  makes the check assert something false. Rebuild instead.
- **PyPI is the installable truth**, GitHub is the narrative. mise installs from
  PyPI, so a version tagged on GitHub but absent from PyPI cannot be pinned —
  graphify's `v1.0.0` was exactly this on 2026-07-23.
- **Renovate still owns routine bumps.** This skill is the judgment layer
  (in-sync validation, release-note review, tracked issues) — not a second
  version bumper racing it.

## Related

- `currency.toml` — what is tracked, and the watch list.
- `docs/currency/` — the committed run log this produces.
- `python/src/kb_setup/currency/` — the engine; `decide.py` holds the bar.
