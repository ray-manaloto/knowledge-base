# Claude Code docs — native `.md` mirror (vendored)

`sources/media/claude-code-docs/` is a vendored copy of every page of
`https://code.claude.com/docs/en/`, fetched as the site's native markdown
(the page URL with `.md` appended). Issue #829; Ray ruled the location
2026-10-02.

## Why it is vendored here and not under `sources/<name>/`

`sources/*/` is gitignored: every directory there is a build-time clone of a
`sources/<name>.manifest` pin, and `kb-build` deletes and re-clones it. A live
documentation site has no commit to pin, so a manifest cannot reproduce it.
Vendoring under `sources/media/` is what makes the mirror reach git and other
machines (Invariant 3). `tests/test_vendored_claude_code_docs.py` fails if any
mirror file is gitignored, if a page and its provenance row disagree, or if a
file appears that is neither a page nor provenance.

This does not replace `sources/claude-code-docs.manifest` (the
`thevibeworks/claude-code-docs` clone). That source stays, because
`currency.toml` reads Claude Code release notes from its `changelog.md`.

**Not in the graph yet.** `kb-build` reads only manifests and
`sources/extractions/*.json`, so these pages are greppable on disk but invisible
to `kb-query`/`kb-serve` until a host-agent extraction chunk is committed — a
token-cost decision tracked with #118.

## Keeping it current

- `mise run kb-ccdocs-refresh` re-fetches every page, adds any page `llms.txt`
  or `sitemap.xml` newly lists, keeps a previous copy (and says so) when a fetch
  fails, and exits 1 if a listed page can be neither fetched nor kept. It
  rewrites `fetch.tsv`, and advances `fetch.stamp.json` only when every `md`
  page was actually re-fetched — a run that kept old copies exits 1 and leaves
  the stamp (and so the warning below) where it was. Pages are written only
  after every fetch returns, so an interrupted run changes nothing. Commit the
  result.
- `kb-currency-check` (the SessionStart hook) prints a `[ccdocs]` warning once
  `fetch.stamp.json` is 7 or more days old, or unreadable.
  `mise run kb-ccdocs-check` is the same probe with a real exit code.
- Logic: `python/src/kb_setup/ccdocs_mirror.py`.

## Provenance: `fetch.tsv` and `fetch.stamp.json`

One row per page: `url`, `http-status|content-type`, method, bytes. The stamp
records when the last refresh ran and how many pages it kept.

- **232 pages**: 231 native `.md` fetched 2026-10-02, and 1 `webclaw` fallback.
- `claude-tag` is the fallback, captured 2026-10-01. Its `.md` URL now
  redirects off-site to `claude.com/docs/claude-tag/overview`, so every refresh
  keeps that capture rather than storing a redirect.
- The set is the union of the sitemap, `llms.txt`, a 2026-10-01 webclaw site
  map, and six plugin pages the site still serves but no inventory lists:
  `discover-plugins`, `plugin-dependencies`, `plugin-hints`,
  `plugin-marketplaces`, `plugin-relevance`, `plugins-reference`. Four of the
  six are named by existing `$CC/…` citations; all six are kept because the
  site still serves them and the old tree held them.
- The old `$CC` tree's `docs_manifest.json` is not a docs page and is not here.
- `routines.md` contains a placeholder `Authorization: Bearer sk-ant-oat01-…`
  example that a default-config gitleaks reports as `curl-auth-header`. It is
  the vendor's illustrative value, not a credential. The repo's
  `.gitleaks.toml` allowlists `^sources/`, and gitleaks auto-loads that file
  when run inside this repo, so the tree is scanned only by a default-config
  run from OUTSIDE the repo.

## Pointing `$CC` at this mirror

`$CC` (dotfiles `research-doc-sources.md` step 00) is defined as
`$KB/agent-harness-docs/docs/claude-code`. **Redefine it rather than linking
inside that clone:** `CC=$KB/media/claude-code-docs`. Page names are the same
flat `a__b.md` scheme, so every existing `$CC/<page>.md` citation still resolves.

**Do NOT replace `sources/agent-harness-docs/docs/claude-code` with a symlink.**
It is a tracked directory of a pinned clone; replacing it makes git see its
files as deleted, and `kb-build`'s `git checkout --detach <pin>` then aborts
with *"Your local changes … would be overwritten"* whenever the clone is off its
pin — which this host's clone already is. Reproduced in a scratch clone,
2026-10-02 (cold review of `3a02f2de`).
