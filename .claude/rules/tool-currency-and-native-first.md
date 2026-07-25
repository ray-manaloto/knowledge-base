# Tool Currency & Native-First: Research Release Notes Before Building or Keeping Custom Code

Before you **build** new custom tooling around a managed tool — or **keep**
existing custom tooling that a tool might now do natively — first research that
tool's **release notes / CHANGELOG and latest documentation**. Prefer the
native/framework mechanism. When a native feature supersedes custom code,
**retire the custom code in the same change** and update every doc that
describes it.

This is the currency-over-time sibling of `use-tool-builtins.md`: that rule says
*prefer the built-in over inventing one now*; this rule says *keep checking,
because the built-in you needed may have shipped since you last looked — and the
custom code you wrote may now be dead weight.*

## Why this rule exists

Managed tools move fast, and their **docs lag their code** — the merged
CHANGELOG/PRs are often the only truthful source. Two worked cases:

- **An assumption that a backend had reached lockfile parity did not survive
  probing.** A rule file asserted a feature shipped in a given version and that
  it *retired* a custom snapshot mechanism. Probing found the version had only
  graduated an experimental flag; the underlying gap was still open upstream.
- **The same rule then told readers "do NOT retire" a file that had already
  been deleted**, while a skill file said "RETIRED" — two docs, opposite
  claims, neither checked. **Sync the describing docs in the same change**, or
  the next reader has to adjudicate between them.

The failure mode this prevents: shipping (or preserving) homegrown machinery
for a problem the tool already solves — paying maintenance cost forever, and
often getting a *weaker* result than the native path.

## Rules

1. **Before writing custom tooling around a managed tool, research its release
   notes first.** Walk `research-doc-sources.md` (step 0 is this repo's own
   graph) for the tool's CHANGELOG and the relevant docs page. Assume the docs
   may be stale; cross-check against merged PRs. If the feature you were about
   to hand-write already exists, use it.

2. **Periodically re-check pinned-vs-latest for existing custom code.** For each
   piece of custom tooling wrapping a managed tool, ask "does the tool now do
   this natively?" `mise run kb-currency` produces the retire/bump report.

3. **Prefer native / framework over custom; when a native feature supersedes
   custom code, RETIRE the custom code.** Don't leave a superseded module
   lingering "just in case" — dead custom code rots and misleads. Delete it in
   the same change that adopts the native path.

4. **Verify *which* native mechanism empirically.** A tool often exposes several
   near-synonyms; probe the real behaviour before committing.

5. **Sync the describing docs/skills in the SAME change.** Retiring a module,
   bumping a pin, or swapping custom→native goes stale in `CLAUDE.md`, the rule
   files, and skill files. Update them in the same commit — respecting
   `md-size-budgets.md`.

6. **Justify any custom code that survives the check, in writing.** If a native
   feature exists but is genuinely insufficient, record *why* in the code
   comment or commit body.

## How currency is checked here — the engine lives in THIS repo

`kb_setup.currency` is the shared engine; the sibling dotfiles repo consumes it
as a pinned `uv` git dependency. What each repo declares is its own
`currency.toml`. Two thin tasks:

- `mise run kb-currency-check` → step 1 only: offline, ~10ms, **silent unless
  something drifted**. A SessionStart hook runs it every session.
- `mise run kb-currency` → the full loop (new version + release notes + tracked
  issues + the interview) writing a committed report under `docs/currency/`.

Design facts worth not rediscovering:

- **`mise run kb-currency` always exits 0** and can never be a gate — an
  out-of-date tool is a signal, not a failure. Read the report, not the rc.
- **"Could not check" is never rendered as green.** DRIFT / SKIP / OK are kept
  distinct; a run of nothing-but-SKIPs reports *not verifiable here*, and an
  unreachable upstream reports *latest UNKNOWN*.
- **graphify stamps no version into its own output**, so `kb-build` writes
  `graphify-out/.currency-stamp.json` recording the version that ACTUALLY RAN
  — never the pin, which would launder drift.
- **An unambiguous bump may apply itself**, where unambiguous means all six
  gates pass, and it **fails closed**: anything unreadable is ambiguity, not
  consent.
- **Step 5 can never live in a hook** — a hook is a shell command; only the
  model can call `AskUserQuestion`.

This rule's remaining, un-automatable job is the **native-first judgment**: is a
piece of custom code now superseded by a tool feature? The engine tracks
versions; only a human decides retirement.

## Applies to

All managed tools here: graphify (the big one), mise, hk, uv/ruff/ty, pkl,
taplo, rumdl, gitleaks, typos, agnix, codex, antigravity-cli. Especially
`python/src/kb_setup/` — the largest reservoir of "does the tool do this
natively now?" surface area.

## See also

- `use-tool-builtins.md` — the point-in-time sibling.
- `research-doc-sources.md` — the doc-fetch chain the research step walks.
- `.claude/skills/tool-currency/SKILL.md` — the operational workflow.
- `currency.toml` — what is deep-tracked here.
