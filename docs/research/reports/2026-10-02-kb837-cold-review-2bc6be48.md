# Cold review, round 2 — HEAD 2bc6be4874d19fc048cdd031637c2c11a18d7c48

Reviewed HEAD: **2bc6be4874d19fc048cdd031637c2c11a18d7c48** (`git rev-parse HEAD`). Fixed point: 683463b5 (origin/main).

Scope: `git diff 683463b5...HEAD -- . ':(exclude)docs/research/**' ':(exclude)mise.lock' ':(exclude)uv.lock' ':(exclude)sources/media/**'`. That covers 11 files, +1550/−294.

**Withheld by policy:**
- `docs/research/**` (prose). This includes the X1–X5 arms spec, so the commit's claim of "24/24 died" is **unverified**, because I was not allowed to run `kb-arms`.
- `uv.lock`.
- `sources/media/**`. I sampled it, as listed under "Verified" below.

I did read the `mise.lock` diff: it is **+59 lines, the webclaw block only** (`git diff 683463b5...HEAD --stat -- mise.lock`).

**Method:**
- Every probe ran in-process via `uv run --project <worktree> python /tmp/kbrev2/p*.py`. `dm.__file__` confirmed the code under test was the worktree's own copy.
- The fakes were a fetcher, a mapper, a page_fetcher and `git`. In the currency probe, a recording `subprocess.run` stood in for the real one, so webclaw was never spawned.
- I made no network calls and ran no pytest, lint, gates, arms or build. I did not edit any tracked file.

## Round-1 fixes: do they hold? (all executed)

| Round-1 finding | Fix in baa614e6 | Probe and result |
|---|---|---|
| P1: `mise.lock` lacks webclaw | 11 platform entries for 0.6.23 (`mise.lock:6329-6386`) | The entries are present and cover linux-x64/arm64 ± musl ± baseline, macos and windows. The shape matches agnix's block at `:6388`. **Unverified:** the checksums, because there was no cached tarball to hash (`~/.local/share/mise/downloads/github-0x-massi-webclaw` is empty), and the `kb-lock-drift` rc, since `mise lock` may reach the network. |
| P2: SessionStart spawns `git` (~200 ms) | `report_staleness(include_codex=False)` by default (`docs_mirror.py:590-607`), and `run.py:136` calls the default | **HOLDS.** With a spy on `subprocess.run`, `report_staleness(root)` made **0** spawns. The control `include_codex=True` made **1**. I also checked that adding `[tool.webclaw]` did not put a spawn on step 1: `sync.check_sync` for webclaw and for agnix both made **0** subprocess calls under a recording fake, and both returned `in sync`. |
| P3: pin age differs by host | One measure on every host: `git log -1 --format=%cI -- manifest` (`docs_mirror.py:544-587`) | **HOLDS.** On the real repo, the age read 0 and 6 days as silent, and +7 and +8 days as `age of the last pin advance: N days`. `check` gives rc 0 today, because 31569976 advanced the pin. |
| P3: an orphan `fetch.misses.json` entry is never pruned | Prune entries in neither `listed` nor `old` (`docs_mirror.py:469-470`) | **HOLDS.** I seeded an orphan (count 2) and an unlisted row `gone` (count 1). After the refresh, the orphan was gone and `gone` was at count 2, so the non-orphan counter was retained and advanced. |
| P3: a non-normalising row crashes with a `ValueError` | `MirrorUnreadableError` before any fetch (`docs_mirror.py:460-464`) | **HOLDS.** Five bad rows (`?y=1`, `/other/x`, `img.png`, `a/../b`, trailing-slash `hooks/`) each returned **rc 127**, and the mirror directory was byte-identical before and after. In the control (valid rows), the refresh ran with rc 0 and the page was updated. |
| P3: dot segments accepted | Reject `''`, `.` and `..` segments (`docs_mirror.py:170-171`) | **HOLDS.** `a/../b`, `a/./b`, `a//b`, `..` and agentsview `docs/../x` all return None. The controls `a/b`, `hooks/`→`hooks`, `/`→`index`, `docs/`→`docs/index` and `agentsview.io` alias→`www` normalise as expected. |
| P3: pages with no stamp are silent | Silent only when there is no tsv, no stamp and no `*.md` (`docs_mirror.py:528-529`) | **HOLDS.** An empty directory → silent. `.gitkeep` → silent. tsv only → UNKNOWN. pages only → UNKNOWN. |
| P3: stale "only CI workflow" comment | `mise.toml:249-250` reworded | Fixed. |

**Committed mirrors vs the engine** (probe p3, which uses the engine's own `read_rows`, `normalise` and `page_name`):

| Mirror | rows | non-normalising | rows without a page | pages without a row | size mismatches | stamp |
|---|---|---|---|---|---|---|
| claude-code | 232 | 0 | 0 | 0 | 0 | fresh, 232 pages |
| agentsview | 33 | 0 | 0 | 0 | 0 | fresh, 33 pages |

The claude-tag row is the only `webclaw` row, `200|text/html; charset=utf-8 webclaw 17346`, and it is grandfathered. Given the stamp rule at `:487`, that is what lets the run be stamped while the row 307s off-site.

## Findings

No **BLOCKING** findings.

1. **P3: the scheduled CI job becomes red deterministically ≥7 days after each codex-docs pin advance, and nothing automated clears it.**
   - `.github/workflows/docs-refresh.yml:36-40` exits with `max(refresh rc, check rc)`.
   - `check` includes `codex_docs_staleness` (`docs_mirror.py:653-655`), measured from git history, and CI never commits. From day 7 every 6-hourly run fails until a human runs `kb-update -- codex-docs`.
   - Executed: on the real repo, `now+7d` gives the finding line, and `now+6d` gives `''`.
   - Related and **unverified:** if upstream had no new commit, `kb-update` would produce no manifest change, so the remedy the message names could not clear the warning. Any comment-only edit to the manifest would also reset the age.
   - This looks deliberate per baa614e6 ("failing with the worse rc"). I flag it because a guaranteed-red cron is noise.

2. **P3: latent flat-filename aliasing, which this branch's retirement can now act on.**
   - `docs_mirror.py:166,180,502`. `a/b` and `a__b` both normalise to themselves and both map to `a__b.md`. Executed: the comparison is `True`, and the control `x/y` maps to a distinct file.
   - The scheme is pre-existing (683463b5 `ccdocs_mirror.py:102-107`, same regex at `:71`). What is new is `_write_refresh` unlinking `page_name(retired_url)` (`:501-502`). If one alias retires while the other is kept, its row would be left without a page.
   - The round-1 fix comment at `:168-169` says the goal is "one page cannot mirror twice". The inverse case, two pages sharing one file, is still open.
   - No committed URL uses `__`, so this does not fire today.

3. **P3: stale task comment for `kb-ccdocs-refresh`.**
   - `mise.toml:1186-1191` still says "Logic in kb_setup.ccdocs_mirror" and names only "an unreadable inventory" as the cause of rc 127.
   - The logic now lives in `docs_mirror`, which `ccdocs_mirror.py:101` delegates to. That path also returns 127 when the webclaw map is unavailable (`docs_mirror.py:294-299`), so `kb-ccdocs-refresh` now hard-requires webclaw. The comment does not say so.

4. **P3: `report_staleness` hardcodes the display name.**
   - `docs_mirror.py:602`: `"Claude Code" if site.key == "claude-code" else "agentsview"`. A third `SITES` entry would be labelled "agentsview".
   - Read only, not executed. It cannot fire with the two current sites.

5. **P3: the agentsview mirror has no committed-content invariant test.**
   - Claude Code has `tests/test_vendored_claude_code_docs.py`, which checks that every row has a page and allows only the expected stray files. agentsview has no equivalent.
   - It also still carries `.gitkeep` beside 33 pages (`ls`).
   - Today it is consistent: my probe found 33/33 rows↔pages, 0 orphans and 0 size mismatches. Nothing would catch drift, though.

## Still unverified (host constraints)
- Whether `jdx/mise-action` with `install: false`, followed by `mise install github:0xMassi/webclaw uv`, puts both on PATH for the `uv run` step.
- Whether invoking `uv` through a mise shim triggers `[deps.uv] auto = true`. `mise deps --help` (2026.10.0) says auto providers run "before `mise exec` and `mise run`". Under that, plain `mise install` does not trigger it. The shim path is unprobed.
- webclaw's real `--version` output against `version_pattern = '^webclaw (\d+\.\d+\.\d+)'`. The currency probe used a fake.
- The `mise.lock` checksums and the `kb-lock-drift` rc.
- The X1–X5 arms (`kb-arms` not run; the spec is withheld as `docs/research/**`).

## Summary
NO BLOCKING FINDINGS — reviewed 2bc6be4874d19fc048cdd031637c2c11a18d7c48.

- Every round-1 finding is fixed, and each fix held under an executed positive probe plus a control.
- I found no defect introduced by the fixes.
- There are 5 non-blocking P3s, listed above.

## GitHub repos touched
- [0xMassi/webclaw](https://github.com/0xMassi/webclaw): lockfile entries only, read locally. No network access and no binary spawned.
- [chenrui333/codex-docs](https://github.com/chenrui333/codex-docs): the manifest pin was read locally only.
