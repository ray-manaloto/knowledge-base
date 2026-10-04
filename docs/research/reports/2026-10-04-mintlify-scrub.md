# Mintlify scrub — knowledge-base (2026-10-04)

Lane `kb-20261004T143738.543515000-05.mintlify-scrub`, branch `chore/mintlify-scrub`.

**Ruling (Ray, 2026-10-04, verbatim):** *"remove all references to mintlify - we
no longer need mintlify and its sources are old and outdated and might be
providing incorrect/old information - must scrub from both knowledge-base and
dotfiles projects"*.

## Inventory (measured, `git grep -nic mintlify`, base `26a84f7f`)

13 tracked files matched. Each was classified as **authored** (edited) or a
**verbatim record** (left byte-identical; only authored pointers are fixed).

| File | Hits | Class | Action |
|---|---|---|---|
| `.claude/rules/research-doc-sources.md` | 10 | authored rule | rewritten (below) |
| `sources/REGISTRY.md` | 4 | authored backlog | 3 phrases reworded; history kept |
| `.gitignore` | 1 | authored comment | reworded |
| `docs/research/reports/mise-path-research.md` | 2 | verbatim lane report | kept |
| `docs/research/reports/dotfiles-secret-management.md` | 2 | verbatim lane report | kept |
| `docs/research/reports/2026-09-09-astra-review-lane-research.md` | 2 | verbatim lane report | kept |
| `docs/research/reports/2026-09-12-function-hooks-round/session-audit-e-missed.md` | 1 | verbatim lane report | kept |
| `docs/research/reports/2026-08-28-cli-plugin-anatomy.md` | 1 | verbatim lane report | kept |
| `sources/media/dotfiles-secrets-{rule,guide,evidence}.md` | 1 each | vendored corpus | kept |
| `sources/extractions/dotfiles-secrets-docs.json` | 1 | committed extraction chunk | kept |
| `graphify-out/memory/query_20260723_202752_…md` | 1 | dated work-memory record | kept (see open item) |

`docs/research/README.md` § the no-normalising rule and
`agent-artifact-conventions.md` § *corpus content is never rewritten* govern the
kept rows. The `sources/media`/extraction hits all name dotfiles'
`docs/research/mintlify-cache/` path — a historical fact about dotfiles at
capture time, owned by the sibling dotfiles lane.

## The rule rewrite (`research-doc-sources.md`)

- **Step 0** now names the offline `sources/` corpus beside the graph — the
  replacement chain is: offline corpus → a project's own `llms.txt` / `.md` →
  `ctx7` → raw fetch.
- **Step 2** (`.md` suffix) no longer claims a hosting vendor; it says many docs
  sites serve `.md`, and to check the body because an HTML error page served for
  every input is a 404 (the VitePress case in `mise-path-research.md`).
- **Step 3** (`ctx7`) is keyed on "serves no `llms.txt`/`.md`" instead of a vendor.
- **The § "Why per-repo … MCP URLs are NOT in the chain"** section (16 lines,
  entirely about the vendor's MCP descriptors) is replaced by a 5-line
  § "Third-party doc mirrors are NOT in the chain" carrying Ray's ruling as the
  general principle: fetch from the project's own domain or pinned repo.
- Not byte-synced with dotfiles: the two copies already differed before this
  change (`diff` against `dotfiles` `origin/main`, ~20 differing hunks), so this
  edit introduces no new drift class. Line count 200 → 191 (rule_unscoped budget 200).

## Control arms

- Negative (after): `git grep -il mintlify` over the three edited files → 0,
  while the same command still returns the 10 kept files — so the probe
  discriminates; the zero is not a broken grep.
- No other reference to the deleted section's anchor: `git grep -i mintlify`
  covers any `#why-per-repo-mintlify…` link, and none existed outside the rule.

## Open items for the coordinator

1. `graphify-out/memory/query_20260723_…md` line 14 says *"The mintlify .md URL
   suffix also bypasses nav-chrome truncation"*. Kept as a dated record; the
   underlying claim (`.md` suffix) is still true. Rewrite only if Ray wants the
   memory store scrubbed too.
2. No `sources/*.manifest` or `*.pages.toml` pointed at a mintlify host
   (0 hits), so nothing ingested here needs de-registering. Corpus nodes whose
   text mentions the vendor come only from the kept dotfiles-secrets chunk.

## GitHub repos touched

- [ray-manaloto/dotfiles](https://github.com/ray-manaloto/dotfiles) — compared its `research-doc-sources.md` copy for rule-sync status.
