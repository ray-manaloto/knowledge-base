---
type: "query"
date: "2026-10-03T02:35:37.641407+00:00"
question: "How are the offline agent docs mirrors (Claude Code, agentsview, Codex) kept current, and what are webclaw's traps?"
contributor: "graphify"
outcome: "useful"
---

# Q: How are the offline agent docs mirrors (Claude Code, agentsview, Codex) kept current, and what are webclaw's traps?

## Answer

# KB#837 + #847 — offline agent docs mirrors (2026-10-02)

- The engine is `kb_setup.docs_mirror`, which is multi-site through `SITES`. `ccdocs_mirror` is now a Claude Code compatibility layer.
  - claude-code: 232 pages.
  - agentsview: 33 pages, at `www.agentsview.io`. The apex host returns 307, so it is aliased to www.
- Codex docs did NOT need a new mirror. `sources/codex-docs.manifest` (chenrui333, 6h upstream sync) was 23 days stale. `mise run kb-update -- codex-docs` advances it. Its age is reported by `kb-docs-check` and is kept off SessionStart because it spawns git (~200 ms).
- webclaw 0.6.23 is pinned per project.
  - `--map --no-map-crawl <origin>` is the third inventory. For CC it is a strict subset of the 232 pages; for agentsview it is the same 33 pages as the sitemap.
  - Fallback is `webclaw -f json`. It FOLLOWS REDIRECTS silently: on claude-tag it returned rc 0 with a different page. Accept its output only if `metadata.url` normalises to the requested page. On a 404 it exits rc 1 with empty output.
- Retirement requires 3 consecutive unlisted 404/410 responses AND at least 7 days since the first miss. Misses are stored in `fetch.misses.json`. Counting runs instead of elapsed time would have deleted live pages after a 404 burst; the advisor caught this.
- claude-tag has moved off-site (307 → `claude.com/docs/claude-tag`). It is grandfathered.


## Outcome

- Signal: useful