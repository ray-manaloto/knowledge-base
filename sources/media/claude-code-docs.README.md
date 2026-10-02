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
machines (Invariant 3). `tests/test_vendored_claude_code_docs.py` fails if the
mirror ever moves under an ignored path, or if a page and its provenance row
disagree.

This does not replace `sources/claude-code-docs.manifest` (the
`thevibeworks/claude-code-docs` clone). That source stays, because
`currency.toml` reads Claude Code release notes from its `changelog.md`.

## Provenance: `fetch.tsv`

One row per page: `url`, `http-status|content-type`, method, bytes.

- **232 pages** fetched 2026-10-02: 231 native `.md` and 1 `webclaw` fallback.
- `claude-tag` is the fallback. Its `.md` URL redirects off-site to
  `claude.com/docs/claude-tag/overview`, so the page is the 2026-10-01 webclaw
  capture.
- The set is the union of three inventories: the sitemap, `llms.txt` and a
  webclaw site map. It also includes six plugin pages the site still serves
  but no inventory lists: `discover-plugins`, `plugin-dependencies`,
  `plugin-hints`, `plugin-marketplaces`, `plugin-relevance`,
  `plugins-reference`. They are kept because existing `$CC/…` citations name
  them.
- `routines.md` contains a placeholder `Authorization: Bearer sk-ant-oat01-…`
  example that a default-config gitleaks reports as `curl-auth-header`. It is
  the vendor's illustrative value, not a credential. The repo's
  `.gitleaks.toml` allowlists `^sources/`, so this tree is scanned only by an
  explicit default-config run.

## Per-machine step: point `$CC` at this mirror

`$CC` (dotfiles `research-doc-sources.md` step 00) is
`<kb>/sources/agent-harness-docs/docs/claude-code`. That path is inside a
gitignored clone, so the link cannot be committed. Run this once per machine,
from the knowledge-base root:

```bash
cc=sources/agent-harness-docs/docs/claude-code
[ -L "$cc" ] || mv "$cc" "$cc.orig"
ln -sfn ../../../sources/media/claude-code-docs "$cc"
```

The `.orig` copy keeps the clone's tracked files on disk. Restore it (remove
the link, move `.orig` back) before advancing `agent-harness-docs`, so the
clone's checkout does not see deleted files.
