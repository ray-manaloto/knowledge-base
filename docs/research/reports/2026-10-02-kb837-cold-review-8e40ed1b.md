# Cold review — HEAD 8e40ed1b0a48d7d5792c91dc704d96605ed78946

Reviewed HEAD: **8e40ed1b0a48d7d5792c91dc704d96605ed78946** (`git rev-parse HEAD`), fixed point 683463b5.
Scope: `git diff 683463b5...HEAD -- . ':(exclude)docs/research/**' ':(exclude)mise.lock' ':(exclude)uv.lock'`, which covers 11 files.
Method: every probe ran in-process with fakes through `uv run --project <worktree> python /tmp/kbrev/*.py`, and `docs_mirror.__file__` confirmed the code under test was the worktree's own copy. I did not spawn webclaw and made no network calls. I ran no pytest, lint, gates or build.

## Findings

### P1, BLOCKING (ship gate): `mise.lock` was not updated for the newly pinned `github:0xMassi/webclaw`
- `mise.toml:122` adds `"github:0xMassi/webclaw" = "0.6.23"`. `mise.toml:280` sets `lockfile = true`.
- `grep -n "webclaw\|0xMassi" mise.lock` returns 0 hits. Control arm: `grep -n agnix mise.lock` finds the `[[tools."github:agent-sh/agnix"]]` block at line 6329, so the probe discriminates. `git diff 683463b5...HEAD --stat -- mise.lock` is empty, and the working tree is clean apart from the untracked `docs/research/...`.
- `kb-lock-drift` is a ship gate. `python/src/kb_setup/lock_drift.py:26-38` describes exactly this class: an added tool is `old_versions == []` in `mise lock --dry-run --json`.
- **Unverified:** the gate's actual rc. I did not run `mise lock` because it may reach the network. The missing lock entry itself is verified.

### P2, non-blocking: the SessionStart `currency check` now spawns `git` on every session, measured at about 190–245 ms
- `python/src/kb_setup/currency/run.py:132-134` now calls `docs_mirror.report_staleness`, which reaches `codex_docs_staleness` (`docs_mirror.py:522-562`). With no clone present, that runs `git log -1 --format=%cI -- sources/codex-docs.manifest`, a history walk.
- Measured three times in-process: 244.4 ms, 189.9 ms, 199.7 ms for that call alone.
- The run.py docstring was updated (`run.py:5`). Root `CLAUDE.md` still advertises `kb-currency-check` as "offline ~10ms", and that claim is now false by more than 10×.
- It also fires today. The real repo returns `age of the last pin advance: 22 days`, so every SessionStart now prints a `[codexdocs]` block, and `docs check` gives rc 1. I measured `dm.main(root, ["check"])` returning 1. This is by design ("not drift"), but it lands as permanent noise until `kb-update -- codex-docs` runs.

### P3: `codex_docs_staleness` measures two different quantities depending on the host (`docs_mirror.py:533-546`)
- With the clone present it reports the upstream commit date of the pin. Without it, it reports the date of the repo commit that last touched the manifest. The same committed state can therefore give different ages on different hosts, and the message labels which one it used.
- **Unverified on a clone host:** this worktree has no `sources/codex-docs/` (`ls` returns ENOENT), so only the no-clone branch was exercised live.

### P3: Stale comment `mise.toml:249`, "this repo's only CI workflow (graphify-live-receipt.yml)"
- This commit adds `.github/workflows/docs-refresh.yml`. `ls .github/workflows` shows both files, and the new one does install a mise-managed tool.

### P3: Orphaned `fetch.misses.json` entries are never pruned (`docs_mirror.py:348-374, 492-496`)
- `_retire` only touches URLs in `listed | old`. A misses entry for a URL in neither set is rewritten forever.
- Probe G: I seeded `{".../orphan": {count: 2}}` and ran a clean refresh, and the entry was still present afterwards.

### P3: An existing `fetch.tsv` row that no longer normalises crashes refresh with an uncaught `ValueError` instead of `Rc.NOT_RUN` (`docs_mirror.py:460` calls `page_name` at `:169-174`)
- Probe: rows `.../x?y=1`, `https://code.claude.com/other/x` and `.../img.png` each RAISED `ValueError: not a claude-code docs page`.
- No damage results: the mirror dir held only `fetch.tsv` afterwards, so nothing was written. It is a traceback rather than the module's own "COULD NOT ASK" path.
- Control: all 232 committed Claude Code rows normalise to themselves and map to existing files (0 bad, 0 orphans in either direction), so this does not fire today.

### P3: Dot-segments are accepted as page paths (`docs_mirror.py:164`)
- The regex `[A-Za-z0-9_./-]+` accepts `a/../b`. `normalise(agentsview, ".../a/../b")` returns `.../a/../b`, which becomes the page `a__..__b.md`, and `normalise(cc, ".../docs/en/..")` returns `.../docs/en/..`.
- There is **no path traversal**: `page_name` replaces every `/`, so the target is always `mirror/<name>`. The impact is only that an inventory containing dot-segments could create duplicate pages.

### P3: Claude Code staleness is weakened when `fetch.tsv` is missing (`docs_mirror.py:506-507`)
- At 683463b5, a mirror *directory* with no readable stamp reported `freshness UNKNOWN`. Now, with no `fetch.tsv`, it is silent. The tests were edited to `touch` `FETCH_TSV` to keep passing (`tests/test_ccdocs_mirror.py:168,184,339`).
- The change is needed for the `.gitkeep`-only agentsview mirror, but it was applied to every site.

### P3: A retirement candidate holds the stamp back for up to a week (`docs_mirror.py:469-472`)
- Probe B: on day 0 and day 3, the unlisted 404 page is `kept`, `stamped=False`, and refresh returns FINDINGS. The stamp advances only when the page retires on day 7. This matches the docstring ("Failed previous pages hold the stamp back"), but it means the staleness warning can fire purely because of a pending retirement.

## Claims verified (control-armed)
- **Import closure is "stdlib plus structlog"** (`docs_mirror.py:16-17`). The new non-stdlib top-level modules after `import kb_setup.docs_mirror` are `['kb_setup', 'structlog']`.
- **Retirement needs 3 misses spanning 7 days.** Probe B: misses 1 and 2 (days 0 and 3) give candidates; day 7 gives RETIRED, file deleted, row removed, misses file removed, stamped. A network error resets the counter (probe D: the misses file is gone after an error). That matches the docstring and test `:201`.
- **webclaw never recovers a moved page.** `_moved` returns True for an off-site Location and for a same-path Location with a query. It returns False for `/docs/en/a.md`, `//code.claude.com/docs/en/a` and the relative `a`. Fallback with an off-site `final_url` is rejected and reported missing (probe E). A same-site final URL is accepted, with the row `200|text/markdown; source=webclaw  webclaw`.
- **An unavailable mapper writes nothing.** `main(... refresh claude-code)` with `mapper → None` returns 127 (probe A). Note the behaviour change this implies: `ccdocs refresh` now hard-requires webclaw on PATH (`docs_mirror.py:288-293`).
- **CLI dispatch.** `docs refresh` returns 2 and `docs refresh nope` returns 2.
- **agentsview index mapping** matches the measured table in the (withheld) research findings: `/` and `/docs/` map to `index` and `docs/index`, and `sitemap.xml` and `llms.txt` normalise to None.
- **currency.toml `[tool.webclaw]`** parses through `currency.config.load` into a ToolSpec with `version_args=('--version',)`. The pattern matches `webclaw 0.6.23` and not `webclaw v0.6.23`. **Unverified:** webclaw's real `--version` output, because spawning it is forbidden.
- **webclaw flags exist in the pinned binary.** `strings` on `~/.local/share/mise/installs/github-0x-massi-webclaw/0.6.23/webclaw` contains `no-map-crawl` and `--map`. The control `no-such-flag-xyz` returns 0 hits. **Unverified:** the JSON field shape `content.markdown` / `metadata.url`.
- **`uv.lock` structlog is 26.1.0**, matching the CI `--with structlog==26.1.0`. `mise.toml:44` pins python `3.14.7`, matching CI `--python 3.14.7`.

## Unverified (could not run under host constraints)
- Whether `jdx/mise-action` with `install: false` puts webclaw's shim on PATH for the `uv run` step in `.github/workflows/docs-refresh.yml`.
- Whether `[deps.uv] auto = true` (`mise.toml:261-263`) makes `mise install` in CI run `uv sync --locked`, which would pull the graphify environment the workflow deliberately avoids.
- The real `kb-lock-drift` rc.

## Summary
- **1 BLOCKING finding (P1):** `mise.lock` has no entry for the newly pinned webclaw.
- **1 P2:** a 190–245 ms git subprocess now runs on the SessionStart path, against CLAUDE.md's "~10ms" claim.
- **6 P3s.**
- The core engine's documented safety properties held under every probe I constructed: deferred writes, the redirect and fallback guard, retirement count plus age, and the import closure.

## GitHub repos touched
- [0xMassi/webclaw](https://github.com/0xMassi/webclaw): binary strings of the pinned 0.6.23 install only. No source read and no network access.
