# KB#837 + KB#847 — offline agent docs mirrors: findings (2026-10-02)

Lane `kb837-offline-docs`, branch `feat/kb-837-offline-docs`, base `683463b5`.
Every probe below was run this session; each negative has its control arm named.

## Codex docs are already a separate, self-refreshing source

#837 reads `sources/agent-harness-docs/docs/codex` as "about 2 months stale". That
tree is **superseded for Codex** (`sources/agent-harness-docs.manifest` comment,
decision #605) by `sources/codex-docs.manifest` → `chenrui333/codex-docs`, an
upstream mirror that auto-syncs every 6h.

| fact | value | probe |
|---|---|---|
| pinned commit | `262d53df92e9cf7495206e64e3f6c4edc757116f`, committed 2026-09-09T20:38:30Z | `gh api repos/chenrui333/codex-docs/commits/<sha>` |
| upstream `main` | `4f2dd1b793dcb0e5fc08d4fe6c76f9b7acb5d3b3`, committed 2026-10-02T21:56:55Z | `git ls-remote` + `gh api …/commits/main` (agree) |

So the Codex fix is a **pin advance** (`mise run kb-update -- codex-docs`) plus a
staleness signal, not a new native mirror ("native mirror … if upstream does not
refresh" — it does).

## agentsview serves native markdown and two inventories

| URL (www.agentsview.io) | result |
|---|---|
| `/llms.txt` | 200 text/plain, 41 `.md` entries |
| `/sitemap.xml` | 200 application/xml, 33 `<loc>` |
| `/docs/configuration.md` | **200 text/markdown** (positive arm) |
| `/docs/bogus-xyz-404.md` | **404 text/html** (negative arm) |
| `/docs/index.md`, `/index.md`, `/guide.md` | 200 text/markdown |
| `/docs.md`, `/.md`, `/docs/configuration/index.md` | 404 |
| `/docs/configuration` | 308 → `/docs/configuration/` |
| any `https://agentsview.io/…` (apex) | **307 → www** |

Consequences: both inventories list the APEX host, which redirects, and the mirror
fetcher refuses redirects — so the host must be rewritten to `www`. URL mapping is
not uniform: `/docs/` → `docs/index.md` and `/` → `index.md`, while `/docs/x/` →
`docs/x.md` (`docs/x/index.md` 404s).

## webclaw

- Latest release `v0.6.23` (2026-09-14), assets for darwin + linux gnu/musl, so a
  CI runner can install it through mise's `github:` backend.
- Only pinned in the user-global mise config today (`~/.config/mise/config.toml:226`).
- `webclaw --map --no-map-crawl <root>`: sitemap-only discovery, one URL per line.
  `https://www.agentsview.io` → 33 URLs; `https://code.claude.com` → 2,616 URLs, of
  which 219 under `/docs/en/`. Control arm: `…/docs/en/overview` as root → 0 URLs
  ("no URLs found"), so the root must be the site origin.
- `--map` WITH the crawl fallback adds `?tab=` query URLs and `.png` assets — noise,
  so the sitemap-only form is the inventory.

## GitHub repos touched

- [chenrui333/codex-docs](https://github.com/chenrui333/codex-docs) — Codex docs mirror; pin vs upstream HEAD
- [0xMassi/webclaw](https://github.com/0xMassi/webclaw) — release list and assets for the pin
- [jdx/mise-action](https://github.com/jdx/mise-action) — v5.0.1 SHA for the CI workflow pin
- [kenn-io/agentsview](https://github.com/kenn-io/agentsview) — docs site source (already `sources/agentsview.manifest`)
