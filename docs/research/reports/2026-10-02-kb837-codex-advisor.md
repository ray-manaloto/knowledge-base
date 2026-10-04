# kb-codex-advisor — kb837 spec, received 2026-10-02 (gpt-6.1-sol, session 01a0ff5a-4518-78b1-b3a5-0f9ecddb7b8b)

Verdict: **DISPATCH-WITH-EDITS.** The full verdict is at about line 6013 of
`.agent/kb/lanes/kb837/advisor/codex.log`. The `-o` file captured a Stop-hook research
failure instead, caused by the Keychain `DOPPLER_TOKEN` in codex's user-global hook.

**Deciding risk:** an HTTP status alone doesn't prove which page you got or that a page is
gone for good. The miss counter counts runs, not time, so a 404 burst over 3 quick re-runs
retires a live page. A webclaw fallback on a 3xx follows the redirect and saves a different
page under the old name, which also resets the miss count.

## Recommended edits

1. Elapsed time must be part of retirement: `count >= 3 AND now - first_seen >= 7d`, or flag
   candidates and leave deletion to a human allowlist.
2. The PageFetcher must return the final status and URL. Reject the result unless the final
   URL normalises to the requested page and the status is 200. On a native 3xx to a
   DIFFERENT page, record a "moved -> target" finding rather than a fetch.
3. A failed, previously fetched webclaw page holds the stamp back, except the grandfathered
   claude-tag row.
4. The mapper is used only on refresh. Measure whether the 219 CC map URLs are a subset of the
   current page set; if not, drop the webclaw inventory for CC or accept the change explicitly.
5. Reject an empty path after normalisation when it is not in `index_sections`.
6. `codex_docs_staleness`: ValueError, subprocess failure or bad timestamp mean UNKNOWN. With
   no clone, fall back to `git log -1 --format=%cI -- sources/codex-docs.manifest`, labelled
   as the age of the last pin advance.
7. Use `raise SystemExit(main(...))`. Keep the rc through the summary. The caller checks the
   Linux lock entries and whether `mise install` triggers `[deps.uv]` uv sync.
8. The implementer may retarget the monkeypatch in
   `test_the_sessionstart_currency_check_runs_the_staleness_probe`, as long as the sentinel
   assertion stays.
9. Describe writes as "deferred", not "atomic". Retirement deletions are deferred too.
10. The agentsview site stays silent while it has no `fetch.tsv`, or the first content lands
    in the same PR.

## Unverified

- How code.claude.com answers for a removed page.
- How webclaw handles redirects, and its rc on a 404.
- How the webclaw map and the inventories overlap for CC.
- Whether `mise install` triggers uv sync.
- Whether webclaw installs on Linux.
