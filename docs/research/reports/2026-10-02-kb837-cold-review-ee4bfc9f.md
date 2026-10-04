# Cold review, post-rebase — HEAD ee4bfc9f5aac5f09b9121c59e22f955035424d1c

Reviewed HEAD: **ee4bfc9f5aac5f09b9121c59e22f955035424d1c** (`git rev-parse HEAD`). This is a rebase of `feat/kb-837-offline-docs` from 683463b5 onto origin/main 87d8f355c56fea7dba3ebf4a4cc562d8fea4b9f5. The pre-rebase head was 79e044ec.

**Scope:** `git diff 87d8f355...HEAD -- . ':(exclude)docs/research/**' ':(exclude)mise.lock' ':(exclude)uv.lock' ':(exclude)sources/media/**'`. That covers 12 files, +1582/−296.

**Withheld by policy:** `docs/research/**`, the lockfiles and `sources/media/**` content. I did read two things inside them: `mise.lock`'s webclaw entry exists (line 6329), and the agentsview mirror's file list.

**Method:**
- Every probe ran in-process via `uv run [--offline] [--no-project] python /tmp/kb837probe/*.py`, using fakes or real offline data.
- `kb_setup.docs_mirror.__file__` resolves to this worktree's copy.
- I made no network calls, spawned no webclaw, and ran no pytest, lint, gates, arms or build. I did not edit any tracked file.

## Q1: Is the rebased series semantically identical? YES

- `git range-diff 683463b5..79e044ec 87d8f355..HEAD`: all six pairs are `=` (patch-identical), from 8e40ed1b=89c44bb4 through 79e044ec=ee4bfc9f.
- **Control arm:** the same command against `87d8f355..HEAD~1` printed `6: 79e044ec < -: --------`, so the probe can report a difference.
- **Tree level:**
  - `git diff --stat 79e044ec HEAD` and `git diff --stat 683463b5 87d8f355` are the same 8 files with +436/−27.
  - The `mise.toml` hunk is byte-identical apart from the line offset (@@ -469 vs @@ -463).
  - So HEAD = the reviewed tree + exactly main's delta, with no conflict-resolution residue.
- **One real, non-semantic difference:** the rebase moved the committer dates. That matters for finding 3 below.

## Q2: Does anything main gained interact with this branch? No functional interaction

- **The two path sets do not overlap.** Main's delta touches `docs/research/{README,reports/*kb-748*}`, `mise.toml` (a comment in `[tasks.test]` only), `evals.py`, `mcp_probe.py`, `tests/test_cpu_bounded.py` and `tests/test_mcp_serve.py`. It touches none of the branch's files except `mise.toml`, and there the hunks are disjoint: main's is at line ~469, the branch's are at 117, 249 and 1190–1220.
- **Grepping branch files for `evals|mcp_probe|CpuWatch|cpu_bounded|real_graph`** returned only the pre-existing `cli.py:681-683` (`evals.run(...)`).
  - Main's `evals.py` diff adds `class CpuWatch` and refactors the inside of `run_command_cpu_bounded`. It does not touch `run`'s signature.
- **The reverse grep** (main's files for `docs_mirror|ccdocs|webclaw`) gave rc=1.
  - Control: `grep -c CpuWatch evals.py` = 2, so the grep is live.
- **One doctrinal tension** is not a functional interaction; see finding 4.

## Findings

No **BLOCKING** findings.

### 1. P3 (new, latent): a page whose last path segment contains a dot is now silently dropped from every inventory (`python/src/kb_setup/docs_mirror.py:161`)

- `normalise` rejects `Path(relative).suffix not in {"", ".md"}`.
- Executed against the claude-code site:

  | Input | Result |
  |---|---|
  | `…/docs/en/release-notes/v2.1` | `None` |
  | `…/docs/en/sdk/python-v0.2` | `None` |
  | control `…/hooks` | itself |
  | control `…/img.png` | `None` |

- At 683463b5, `ccdocs_mirror._PAGE_URL` was `https://code\.claude\.com/docs/en/[A-Za-z0-9_./-]+`, and `inventory_urls` only stripped `.md` and trailing `.`/`/` (`git show 683463b5:python/src/kb_setup/ccdocs_mirror.py:151-157`). Those URLs **were** pages then.
- **Today, a versioned page appearing upstream would never be mirrored, and nothing would warn.** It is not "missing", because it was never listed.
- If such a row were ever in `fetch.tsv`, the whole site's refresh would also return 127, since `refresh` refuses rows that do not self-normalise (`:460-464`).
- **Does not fire today:** 0 dotted rows across claude-code (232) and agentsview (33), counted via `dm.read_rows`.
- **Fix shape:** treat only a known asset-suffix set (`.png`, `.svg`, `.xml`, `.txt`, `.json`, …) as non-pages, rather than any suffix.

### 2. P3 (interaction with main's `graphify-live-receipt.yml`, process): this PR classifies as REQUIRED for a signed Graphify live receipt

- I fed the real inputs to `live_receipt_scope.needs_live_receipt`:
  - the changed-path list (`git diff --name-only -z 87d8f355 HEAD`, 106 paths)
  - the `-U0` mise.toml diff
  - base and head `mise.lock`
- The result was **`True`**.
- **The triggers:**
  - `python/src/kb_setup/cli.py` is in `SENSITIVE_EXACT` (`live_receipt_scope.py:29`), though the branch only adds a 3-line `docs` dispatch.
  - `MISE_SENSITIVE` (`\buv\b|python`) matches 5 changed `mise.toml` lines: the three new `run = "uv run kb-setup docs …"` lines and the two reworded CI-workflow comment lines.
- The lock half is EXEMPT: `_only_exempt_lock_tools_changed` = True, since webclaw is not an extraction tool.
- Control: a docs-only path set gave `False`.
- **Precedent suggests this is non-blocking:** #849 touched `cli.py` (`06a0234a`) after the workflow landed (#821, `d8a205da`, 2026-09-27) and merged.
- **Unverified (no network):** whether that check is required by branch protection, and whether `kb-land` reads it as binding. Read this as something to expect at land time, not as a code defect.
- **Cheap mitigation:** the comment lines on their own would trigger it via `python`. Rewording `mise.toml:249-250` would not remove the requirement anyway, because `cli.py` alone requires it.

### 3. P3: the codex-docs "age of the last pin advance" is the manifest's last **committer** date, which a rebase resets (`docs_mirror.py:567`, `--format=%cI`)

- Executed on this very rebase: `git log -1 --format='%cI %aI' -- sources/codex-docs.manifest` gives
  - `60a793ac cI=2026-10-02T21:54:28-05:00 aI=2026-10-02T21:29:25-05:00`
  - against pre-rebase `31569976 cI=21:29:25`.
- So every rebase, cherry-pick or squash-merge of the commit restarts the 7-day clock. So does any comment-only edit, which round 2 already noted.
- Today `codex_docs_staleness(root)` returns `''`, and with `now+8d` it returns the finding line.
- **Impact:** the message's label overstates what it measures. The age is a lower bound, not "the last pin advance".
- `%aI` survives rebase. Whether it survives GitHub's squash-merge is unverified.

### 4. P3: a new 10 s wall-clock bound in tests, landing just as main converted the suite's wall bounds to CPU bounds (`tests/test_docs_mirror.py:657-665`, `timeout=10`)

- `_isolated` spawns `python -S` and imports `kb_setup.docs_mirror` plus structlog under a 10 s wall timeout. Two tests use it.
- Main's own `mise.toml:469-482` comment, gained in this rebase, says "a wall bound measures the host" under xdist plus concurrent `lint`.
- **Flake risk only. Unverified:** I did not time it under load, because pytest is forbidden on this host.

### 5. P3: `.github/workflows/docs-refresh.yml:34-41` carries inline shell logic

- The logic is a shell function, two `|| rc=$?` captures and an arithmetic max.
- `zero-bash-logic.md` names only `hk.pkl`/`mise.toml`, and `graphify-live-receipt.yml` is a much larger precedent, so this is a style note, not a violation of the rule's letter.
- `docs_mirror.main` could own the combined `refresh all` + `check` rc. That would make the step one seam.

## Re-verified from prior rounds (still true at this HEAD)

- **The import closure is stdlib + structlog** under the exact CI invocation: `PYTHONPATH=python/src uv run --offline --no-project --python 3.14.7 --with structlog==26.1.0` gave `kb_setup.{docs_mirror,events,manifest,result}` plus `structlog`, msgspec absent, rc 0.
- **CLI dispatch:** `cli._run(["docs","check"])` gives 0, and `["docs","refresh","nope"]` gives 2.
- **Committed mirrors:** `fetch.tsv` holds 232 rows for claude-code and 33 for agentsview, each matching its stamp's `pages`. This matches the memory note's 232/33.
- **No test can spawn real webclaw:** an AST scan found every `dm./cm.refresh|main` call without `page_fetcher`.
  - All of those are either in `test_ccdocs_mirror.py`, where the autouse `_offline_webclaw` fixture fakes both adapters (`:26-32`), or are scenarios whose page responses are only 200-markdown, 404/410 or 5xx/error. None of those responses reaches the fallback (`docs_mirror.py:408`).
  - Every `docs_mirror` refresh test passes `mapper`.
- **agentsview still tracks `.gitkeep`** beside its pages (`git ls-files`). This was round-2 P3 #5 and is unchanged.

## Still unverified (host constraints)

- That mise-action with `install: false` puts the `webclaw`/`uv` shims on PATH.
- Whether `[deps.uv] auto = true` fires through the `uv` shim in CI.
- webclaw's real `--version` output against `currency.toml`'s `version_pattern`.
- Whether the live-receipt check is binding.

## Summary

NO BLOCKING FINDINGS — reviewed ee4bfc9f5aac5f09b9121c59e22f955035424d1c.

- The rebase is patch-identical (range-diff all `=`, control-armed).
- Main's delta does not interact functionally with this branch.
- There are 5 non-blocking P3s. #1 (dotted page names dropped) and #2 (live-receipt REQUIRED) were not raised in earlier rounds.

## GitHub repos touched

_None._ All probes were local. No network was used, and no upstream source was read.
