# Cold review, post-rebase #2 — HEAD b220a2dce1b8e531c25d51cbf0c3851b11e4a51f

Reviewed HEAD: **b220a2dce1b8e531c25d51cbf0c3851b11e4a51f** (`git rev-parse HEAD`, rc 0). Rebase of `feat/kb-837-offline-docs` onto origin/main f639a7bbec9b2c0a451f83514e50139f2ef0e04d; previous head ee4bfc9f5aac5f09b9121c59e22f955035424d1c (on 87d8f355), cold-reviewed in `review-ee4bfc9f5aac5f09b9121c59e22f955035424d1c-cold.md`.

Scope: `git diff f639a7bb...HEAD -- . ':(exclude)docs/research/**' ':(exclude)mise.lock' ':(exclude)uv.lock' ':(exclude)sources/media/**'` — 12 files, +1582/−296 (same totals as the previous scope). Withheld by policy: docs/research prose, lockfiles (read only as classifier INPUT, below), vendored docs content.

Method: in-process `uv run --offline python` probes on /tmp/kb837r3; a scratch commit object built via a temp `GIT_INDEX_FILE` (no tracked file or ref touched). No network, pytest, lint, gates, arms, build or webclaw.

## Q1 — semantically identical? YES (control-armed)

- `git range-diff 87d8f355..ee4bfc9f f639a7bb..HEAD`: all six pairs `=` (89c44bb4=12bbba2c, aff23a26=f0f9f5b7, 60a793ac=18a84795, beeeae33=91f4fcdd, 9ffc6aa2=8533b814, ee4bfc9f=b220a2dc).
- **Control arm (discriminates on CONTENT, not just commit count):** built scratch commit 99540a67 = HEAD~1 + HEAD's tree with `# mutation` appended to `docs_mirror.py` (temp index → `write-tree` c6951d1b → `commit-tree`). `git range-diff 87d8f355..ee4bfc9f f639a7bb..99540a67` printed `6: ee4bfc9f ! 6: 99540a67` with the `+# mutation` hunk (and the dropped trailers). So `=` is a real answer.
- **Tree level:** `git diff ee4bfc9f HEAD` vs `git diff 87d8f355 f639a7bb`, with `index`/`@@` lines stripped → `cmp` rc 0. Only differences are blob ids and the mise.toml hunk offset (@@ -269 vs -263). HEAD = reviewed tree + exactly main's delta, no conflict residue.

## Q2 — does main's new delta interact?

**disable_tools / TOML: no interaction.**
- `tomllib` parses HEAD, base (f639a7bb) and previous (ee4bfc9f) `mise.toml` (rc 0). HEAD `disable_tools` = main's 13 entries; none mention webclaw or uv; `disable_tools ∩ [tools]` = [] at all three refs. HEAD `[tools]` has `github:0xMassi/webclaw` and `uv`; the three new tasks `kb-avdocs-refresh`/`kb-docs-refresh`/`kb-docs-check` are present. Control: same text with `disable_tools = [[` → `TOMLDecodeError: Unclosed array (line 285)`.
- mise itself: `mise tasks ls` rc 0, lists all five docs tasks. `mise which webclaw` rc 0 → `…/github-0x-massi-webclaw/0.6.23/webclaw`; `mise which uv` rc 0 → `…/uv/0.12.8/…`. Control: `mise which codex` rc 1 (`codex is not a mise bin`) — the disabled name is refused, so the probe discriminates.
- `ai-cli-invocation.md` change (self-update verbs) touches nothing the branch reads: `docs_mirror.py` invokes only `git` and the webclaw adapter (grep for `codex|claude|mise exec|subprocess` → only `git log`/site URLs).

**The kb-review SKILL.md addition DOES interact — see finding 1.**

## Findings

No code defects. One land-blocking PROCESS finding, upgraded from the previous report's P3 #2 by main's new SKILL text.

### 1. P2 — BLOCKING AT LAND (process, not code): the PR classifies `REQUIRED` for signed live evidence, `kb-land` treats the failing check as binding, and main's own kb-review SKILL now says such a PR needs Ray's admin merge (`.claude/skills/kb-review/SKILL.md:53`, `.agents/skills/kb-review/SKILL.md:53`; trigger `python/src/kb_setup/cli.py`, `live_receipt_scope.py:28`)

- Fed the workflow's exact inputs (`git diff --no-renames --name-only -z f639a7bb HEAD`, `-U0 … -- mise.toml`, base/head `mise.lock`) to `live_receipt_scope.needs_live_receipt` → **True** (106 paths). Sensitive paths: only `python/src/kb_setup/cli.py`. Lock half EXEMPT (`_only_exempt_lock_tools_changed` = True). `MISE_SENSITIVE` matches 5 mise.toml lines (the 3 `run = "uv run kb-setup docs …"` + the 2 reworded CI comment lines). Removing cli.py alone still → True (the `uv run` task lines). Control: docs-only path set → False.
- What REQUIRED does: `graphify-live-receipt.yml:53-84` (`set -euo pipefail`) then `git show`s `receipts/<PR>/<HEAD>/live-receipt.json` from the evidence branch; main's SKILL line says "nothing produces that evidence today", so the check fails (by reading; not run live — unverified).
- `kb-land` reads it as binding: `pr._ADVISORY_CHECKS` = {CodeRabbit, Repowise} (`pr.py:96`). Fake-row probe of `pr.checks_state`: `Verify signed exact-head live evidence=fail` → `(False, '1 check(s) not green …')`; control `=pass` → `(True, …)`.
- The previous report called this "non-blocking, precedent #849 merged". Main's new SKILL text (this rebase's delta) states the opposite procedure: admin merge, and `enforce_admins: true` makes `gh pr merge --admin` return 405 until toggled. **Unverified (no network):** live branch-protection state.
- No branch-side fix is cheap: a `docs` CLI dispatch must touch `cli.py`, and any `uv run` task line trips `\buv\b`. Action: plan for Ray's admin merge before `kb-land`, rather than a code change.

### 2. P3 (not this branch's code) — `hook_guard` false positive on a quoted grep pattern

`grep -nE '…|Graphify live' python/src/kb_setup/pr.py` was DENIED as "`graphify live` by hand". The guard matched `graphify` inside a quoted `-E` pattern argument. Not in the diff; noted because it reproduces the class `mise-tasks-only.md` says the guards keep failing on (quoted text at a command position). Re-run without that alternative → rc 0.

### Carried forward unchanged (code is patch-identical, so these still hold): previous report's P3 #1 (dotted last segment dropped, `docs_mirror.py:161`), #3 (`%cI` reset by rebase — this rebase reset it again), #4 (10 s wall bound in `tests/test_docs_mirror.py`), #5 (inline shell in `docs-refresh.yml:34-41`). Not re-executed this round except via the range-diff/tree identity above.

## Still unverified
- Live failure of the live-receipt check and branch-protection settings (network).
- mise-action `install: false` PATH shims; webclaw `--version` vs `version_pattern` (as before).

## Summary
Reviewed b220a2dce1b8e531c25d51cbf0c3851b11e4a51f. The rebase is patch-identical, control-armed at commit and tree level. `disable_tools` does not touch webclaw or uv, and the merged mise.toml parses under both tomllib and mise. No new code defects. One P2 blocks LAND: this PR needs signed live evidence that nothing produces. kb-land will refuse, and main's new SKILL text routes the PR to Ray's admin merge.

## GitHub repos touched

_None._ All probes were local.
