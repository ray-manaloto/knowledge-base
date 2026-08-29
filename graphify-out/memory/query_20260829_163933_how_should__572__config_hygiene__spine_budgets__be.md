---
type: "query"
date: "2026-08-29T16:39:33.108074+00:00"
question: "How should #572 (config hygiene, spine budgets) be implemented, and what did it teach about the codex-implementer lane's sandbox limits?"
contributor: "graphify"
outcome: "useful"
---

# Q: How should #572 (config hygiene, spine budgets) be implemented, and what did it teach about the codex-implementer lane's sandbox limits?

## Answer

# Round answer — #572, config hygiene + provisional spine budgets

Config hygiene for the aggregated-research plugin (marketplace PR #7, merged
`a57f8a96`):

- `aggregated-research/hooks/hooks.json` gained `$schema` (nearest published
  schema is `claude-code-settings.json` — no dedicated hooks-only schema
  exists on schemastore, confirmed 404 control-armed against a bogus-URL
  404) plus a `$comment` explaining that. Confirmed `claude plugin validate`
  does not scan hooks.json content at all, and the settings schema's
  top-level `additionalProperties: true` (read live), so both the CLI gate
  and IDE schema validation stay clean.
- `plugin.json`/`marketplace.json` already had `$schema`. Their non-obvious
  values (`allowCrossMarketplaceDependenciesOn`, `dependencies[].marketplace`)
  are documented in the new `spine-budgets.toml` instead of via `$comment` in
  the manifests — **`claude plugin validate` (this repo's own
  `kb_setup.plugin_validate`) treats ANY unknown-field warning other than
  "No version specified" as a failure**, so a `$comment` there breaks the
  gate. Found this by running the validator myself after codex's first pass
  used `$comment` in both files; fixed by moving the doc out and re-running
  to confirm 0 warnings.
- `aggregated-research/.lsp.json` left untouched: its validating subschema
  (the plugin manifest's `lspServers.anyOf[1]`) rejects any key outside a
  fixed 12-key list, at both the top level and per-server level — there is
  no metadata slot in this schema at all, and no standalone schemastore
  schema for `.lsp.json` either (confirmed 404 for both plausible names).
- New `aggregated-research/spine-budgets.toml`: the four constants the
  future spine agent-dispatch/verify loop (#585) inherits —
  `VOTES_PER_CLAIM=3, REFUTATIONS_REQUIRED=2, MAX_FETCH=15,
  MAX_VERIFY_CLAIMS=25` — extracted verbatim from Claude Code's bundled
  `/deep-research` workflow script, embedded in CLI binary v2.1.247. Cited
  to `ray-manaloto/knowledge-base` commit `03e07cc45f89`
  (`docs/research/reports/2026-08-27-deep-research-internals.md`, promoted
  from `.agent/` this round since it is now load-bearing). States plainly
  these are provisional pending #586's tuning pass and must not be replaced
  with invented numbers.

## Process notes worth carrying

1. **codex-implementer's sandbox cannot create new git refs.** `git branch
   <new>` / `git checkout -b <new>` both fail `Operation not permitted`
   under its `workspace-write` mode; committing onto an EXISTING branch
   works fine. Remedy: pre-create the branch outside the sandbox (as the
   caller), then dispatch a spec whose §6 says "commit onto the existing
   branch, do not create one." First dispatch attempt correctly dissented
   rather than guessing around the restriction.
2. **codex's sandbox also has no network egress** — it could not run
   `mise run kb-plugin-validate` itself (schemastore fetch failed), so it
   left the edits uncommitted and flagged the untested state honestly rather
   than claiming a pass. The caller (with network) ran the validator and
   found the real defect the sandbox limitation had hidden (see below).
3. **A schema's `additionalProperties: true` does not mean a validation TOOL
   accepts unknown keys.** `plugin.json`/`marketplace.json`'s schemas permit
   extra top-level properties, but `claude plugin validate` itself warns on
   any unrecognized field, and this repo's wrapper (`_ALLOWED_WARNINGS`)
   fails on every warning except the one allowlisted "no version" case. A
   spec premise verified against the JSON Schema alone is not the same as a
   premise verified against the actual gate that will run — verify against
   the INSTALLED validator, not just the published schema.
4. **The fully-qualified `Closes owner/repo#N` syntax DOES auto-close
   cross-repo** (confirmed: `ray-manaloto/knowledge-base#572` closed itself
   when marketplace PR #7 merged) — this narrows, but does not retract, the
   standing "cross-repo issues never auto-close" trap from the #569/#570/#571
   rounds: those used a BARE `#N` referring to the wrong repo, which is a
   different (and still-broken) shape.
5. **A cross-family cold review should follow WHO actually wrote the
   diff, not who committed it.** codex-implementer wrote the substantive
   config-hygiene diff; the caller (Claude) only trimmed two lines after
   discovering the validator failure. Routed the cold review to
   `antigravity:review` (Gemini) rather than `codex-reviewer`, since a
   same-family reviewer on codex's own work would share its blind spots.

## Outcome

- Signal: useful