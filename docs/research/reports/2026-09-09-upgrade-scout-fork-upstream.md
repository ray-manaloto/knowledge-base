# Scout report: graphify fork vs upstream (2026-09-09)

Read-only fact-finding for a potential graphify upgrade/rebase. Every number
below is cited with the exact command that produced it. Where a probe returns
nothing, a control arm is run and named per `probes-need-a-control-arm.md`.

Context inherited from the dispatch:
- `pyproject.toml:32` pins `graphifyy[all]==0.9.53`
- `pyproject.toml:264` installs from `git+https://github.com/ray-manaloto/graphify` rev `157a957e89a16246bba3a078de2777711ee85e31`
- `sources/graphify.manifest`: url=https://github.com/ray-manaloto/graphify, ref=kb-pin/openai-cli-backend-v0.9.53, commit=157a957e...
- `currency.toml` `[tool.graphify.fork]`: upstream=Graphify-Labs/graphify, base_ref=v0.9.53, base_commit=33362d969292b57eda82f3fbd9eb5f3f5bc9bbc2
- upstream default branch reported as `v8` (not `main`)
- openai-cli backend claimed as upstream PR #3073 (open as of 2026-09-02)

---

## 1. Upstream state (Graphify-Labs/graphify)

**Default branch**: `v8`
Command: `gh api repos/Graphify-Labs/graphify --jq .default_branch` → `v8`

**Latest tags (per_page=5, API order — NOT chronological, see caveat below):**
Command: `gh api 'repos/Graphify-Labs/graphify/tags?per_page=5' --jq '.[] | "\(.name) \(.commit.sha)"'`
```
v1.0.0  0a31c0862b600d0755b0b8da41d6cdf99df135df
v0.9.56 67f99bd0059dd1bac9e44382907ef9f10098b39f
v0.9.55 c9f99018774e2e0380e9f65b3959944559a0d5f6
v0.9.54 937e59a5476fcb2665d6c4f4b7c0d0a4142011b6
v0.9.53 33362d969292b57eda82f3fbd9eb5f3f5bc9bbc2
```

**🔴 `v1.0.0` is NOT the newest tag chronologically or by lineage — it is a stale, diverged branch tip.** This matters because a naive "highest semver" read would pick it.
- `gh api repos/Graphify-Labs/graphify/commits/0a31c0862b600d0755b0b8da41d6cdf99df135df --jq .commit.committer.date` → `2026-04-05T21:40:34Z`
- `gh api repos/Graphify-Labs/graphify/commits/67f99bd0059dd1bac9e44382907ef9f10098b39f --jq .commit.committer.date` (v0.9.56) → `2026-09-07T19:47:42Z` — five months **newer** than v1.0.0.
- `gh api repos/Graphify-Labs/graphify/compare/v0.9.56...v1.0.0 --jq '.ahead_by,.behind_by,.status'` → `28`, `1672`, `diverged` — v1.0.0 has only 28 commits v0.9.56 lacks, but is missing **1672** commits v0.9.56 has. v1.0.0 branched off long ago and was not kept current.
- **Conclusion: the real newest upstream release is `v0.9.56` (2026-09-07), and it equals the `v8` default-branch HEAD** (see next point). Do not target v1.0.0.

**Default-branch HEAD vs newest real tag:**
- `gh api repos/Graphify-Labs/graphify/branches/v8 --jq .commit.sha` → `67f99bd0059dd1bac9e44382907ef9f10098b39f`
- This **equals** the `v0.9.56` tag commit exactly. `v8` HEAD == v0.9.56, confirmed by identical SHA.

**PyPI `graphifyy`:**
Command: `curl -s --max-time 20 https://pypi.org/pypi/graphifyy/json | jq -r '.info.version as $v | $v, (.releases[$v][0].upload_time)'`
→ `0.9.56`, uploaded `2026-09-07T19:57:55` — ~10 minutes after the v0.9.56 tag's commit timestamp (`19:47:42Z`). Two independent sources (GitHub tag metadata, PyPI upload record) agree on both version and time window — cross-check passes.

**Compare `v0.9.53...v8` (i.e. current pin base → upstream HEAD):**
- `gh api repos/Graphify-Labs/graphify/compare/v0.9.53...v8 --jq '.ahead_by,.total_commits'` → `49`, `49` (consistent with each other)
- `gh api repos/Graphify-Labs/graphify/compare/v0.9.53...v8 --jq '.files | length'` → **61 files changed**

**Conflict-surface files named in the dispatch — which ones did upstream touch in this window?**
Command: `grep -E '^(CHANGELOG\.md|graphify/__main__\.py|graphify/cli\.py|...) ' <saved-compare-file-list>`
```
CHANGELOG.md      +42/-0
graphify/cli.py   +31/-3
graphify/llm.py   +40/-4
graphify/serve.py +91/-4
graphify/watch.py +36/-34
pyproject.toml    +2/-1
graphify/install.py +24/-2   (grep -iE 'install|skill' hit; this is the installer file)
```
**`graphify/__main__.py` was NOT touched** by upstream in `v0.9.53...v8` — confirmed with a control arm: `grep -c '__main__\.py'` on the same 61-file list → `0`, then `grep -c 'cli\.py'` on the same file → `1` (proves the grep mechanism itself isn't silently broken). Same control-armed for `graphify/exporters/graphdb.py` → `0`, control `cli.py` → `1`.

Full 61-file list is saved verbatim at
`/private/tmp/claude-501/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base/48c4909c-7c8e-451a-82b5-a9fc01e41cc7/scratchpad/upstream-compare-files.txt`
(scratchpad, not durable — the file list above is the load-bearing excerpt).

**Does upstream's default branch now contain an openai-cli/codex backend? NO.**
- Fetched `graphify/llm.py` at ref `v8` (3495 lines) to scratchpad, then:
  `grep -c 'openai-cli' <file>` → **0**
  Control arm: `grep -c 'claude-cli'` on the **same file** → **23** (proves the file was fetched correctly and grep can match; the 0 is a real answer, not a broken probe).

**Upstream PR #3073 state:**
Command: `gh pr view 3073 --repo Graphify-Labs/graphify --json state,mergedAt,closedAt,updatedAt,title,headRefName`
→ `state: OPEN`, `mergedAt: null`, `closedAt: null`, `updatedAt: 2026-08-25T09:02:57Z`, `title: "feat(llm): openai-cli backend — semantic extraction through the locally authenticated Codex CLI"`, `headRefName: upstream/openai-cli-backend`.
**Still open, unchanged since 2026-08-25 — 15 days stale as of today (2026-09-09).**

**Other PRs mentioning codex/openai-cli backend work** (`gh pr list --repo Graphify-Labs/graphify --state all --search "openai-cli OR codex backend" --limit 10 --json number,title,state,mergedAt`):
| # | title | state |
|---|---|---|
| 3073 | openai-cli backend (Codex CLI) | OPEN |
| 3311 | cursor-cli backend (Cursor Agent CLI) | OPEN |
| 1999 | Route semantic extraction through generic ACP | OPEN |
| 2981 | openai-cli backend (**same title as #3073** — its predecessor) | **CLOSED**, not merged |
| 3255 | defer semantic-extraction backend to `detect_backend()` (#2513) | OPEN |
| 2389 | Entra ID auth for Azure OpenAI backend | OPEN |
| 2735 | governed gateway routing + production graph queries | OPEN |
| 1963 | Add Atlas Cloud backend | OPEN |
| 2208 | Add MiniMax extraction backend | OPEN |
| 3343 | ignore non-runtime dynamic import text | OPEN |

None of the codex/openai-cli PRs are merged. #2981 → closed-without-merge → resupplied as #3073 (this matches `sources/graphify.manifest`'s own note, cross-checked independently here).

---

## 2. Fork state (ray-manaloto/graphify)

**Default branch**: `main` — `gh api repos/ray-manaloto/graphify --jq .default_branch` → `main`
(Note: per the local manifest file, the fork's `main` is itself frozen at `91f4d120` since 2026-05-14 — confirmed below, matches independently.)

**Branches matching `kb-pin/`:**
`gh api 'repos/ray-manaloto/graphify/branches?per_page=100' --jq '.[].name' | grep kb-pin`
```
kb-pin/openai-cli-backend
kb-pin/openai-cli-backend-v0.9.49-tests
kb-pin/openai-cli-backend-v0.9.49
kb-pin/openai-cli-backend-v0.9.50
kb-pin/openai-cli-backend-v0.9.53
```

**HEAD of `kb-pin/openai-cli-backend-v0.9.53`:**
`gh api repos/ray-manaloto/graphify/branches/kb-pin/openai-cli-backend-v0.9.53 --jq .commit.sha` → `157a957e89a16246bba3a078de2777711ee85e31` — **confirms the pin exactly.**

**🔴 The fork does NOT carry upstream's tags as fork-local refs, past v0.9.49.**
`gh api 'repos/ray-manaloto/graphify/tags?per_page=100' --jq '.[].name'` → newest entries: `v1.0.0, v0.9.49, v0.9.48, v0.9.47, ...` down to `v0.7.16`. **No v0.9.50 through v0.9.56 tags exist in the fork's own ref list.**
First attempt to compare `v0.9.53...kb-pin/openai-cli-backend-v0.9.53` **by tag name** → **404 Not Found** (the tag literally isn't a ref in this repo).
Retried using the **raw base commit SHA** instead of the tag name: `gh api repos/ray-manaloto/graphify/compare/33362d969292b57eda82f3fbd9eb5f3f5bc9bbc2...kb-pin/openai-cli-backend-v0.9.53` → **succeeded** (`ahead_by: 8, behind_by: 0`).
**Control arm** — tested whether the fork's compare endpoint can resolve an upstream commit that is NOT an ancestor of any fork branch at all: compared the same base SHA against `67f99bd...` (upstream's current v0.9.56/v8 HEAD, never pushed to any fork ref) → **also succeeded** (`ahead_by: 49, behind_by: 0, status: ahead` — identical numbers to the pure-upstream compare in §1, just resolved through the fork's API). **This means GitHub's compare API can diff two upstream SHAs by number even via the fork endpoint (shared object network for a public fork), so the commits are technically reachable — but this is an API/storage-layer fact, not proof that a plain `git fetch origin` (origin=fork) on a fresh local clone would expose those SHAs without either the tag ref or an explicit `git fetch upstream --tags`.** Practical recommendation unchanged: **fetch the actual upstream remote's tags before rebasing**; don't rely on fork-network SHA reachability as your rebase mechanism.

**The fork's own `v8` and `main` branches are stale snapshots, not tracking mirrors:**
- `gh api repos/ray-manaloto/graphify/branches/v8 --jq .commit.sha` → `282976b2f4066b55cf2fa346c3d5568f7ac044e2`
- `gh api repos/ray-manaloto/graphify/compare/v8...67f99bd0059dd1bac9e44382907ef9f10098b39f --jq '.ahead_by,.behind_by,.status'` → **`127`, `0`, `ahead`** — upstream's real v8/v0.9.56 HEAD is **127 commits ahead** of the fork's own `v8` branch, which has **0** commits the upstream doesn't have (a pure ancestor). **The fork's `v8` branch is a frozen snapshot from the 2026-08-25 rebase onto v0.9.50** (per `sources/graphify.manifest`'s own note: "`v8` HEAD is 43d54acb… REBASED 2026-08-25… compare/282976b2...43d54acb reports ahead_by 17" — that pre-rebase `282976b2` value is exactly what's still sitting on the fork's `v8` branch today, confirming it hasn't moved since).
- Fork's `main` HEAD: `91f4d120b630ee35c79bf3c75ccd186870a808f9` — matches the manifest's independent claim that `main` has been frozen since 2026-05-14.
- **Full fork branch list** (`gh api 'repos/ray-manaloto/graphify/branches?per_page=100' --jq '.[].name'`): `feat/codebuddy-support, fix/default-import-export-edges, fix/extraction-symbol-id-collision, kb-pin/openai-cli-backend(+4 variants), main, prototypes/resolution-experiments, v1..v8`. The `v1`-`v8` branches exist but are NOT continuously synced upstream mirrors — treat every one of them as a point-in-time snapshot, not "get current upstream" shortcuts.

**Fork's 8 patch commits over base v0.9.53** (`gh api .../compare/33362d969292b57eda82f3fbd9eb5f3f5bc9bbc2...kb-pin/openai-cli-backend-v0.9.53 --jq '.commits[]...'`):
```
57245eccb16d 2026-08-23 Azeem              | feat(llm): openai-cli backend — semantic extraction through the locally authenticated Codex CLI
7e2f3897f269 2026-08-23 Azeem              | feat(cli): credential gate knows openai-cli — a present codex CLI is the credential (OAuth), mirroring claude-cli
b34f386ccb83 2026-08-23 Azeem              | fix(openai-cli): disable each configured MCP server per call — a blanket mcp_servers={} does not work
a4842b42099e 2026-08-24 Azeem              | feat: extract --fallback-backend retries a zero-success semantic pass on a second backend
025a24f9b6a5 2026-08-24 Azeem              | test: a partially-succeeded primary pass must not fire the fallback
2819120bf941 2026-08-24 Azeem              | feat: graphify watch --semantic runs LLM extraction automatically on doc changes
72e33a584fcb 2026-08-24 Azeem              | feat: batched UNWIND push for neo4j/falkordb export (--batch-size)
157a957e89a1 2026-08-26 Raymond Manaloto   | fix(openai-cli): only disable MCP servers Codex can actually resolve
```
= 8 commits, matches `ahead_by: 8`. (Cross-checks `sources/graphify.manifest`'s own account: "seven were replayed… an eighth commit then fixed the MCP disable-override defect.")

**Files the fork's 8 patch commits touch** (same compare, `.files[]`):
```
CHANGELOG.md               +5/-0
graphify/__main__.py       +6/-2
graphify/cli.py            +190/-52
graphify/exporters/graphdb.py +95/-47
graphify/llm.py            +429/-3
graphify/watch.py          +91/-5
tests/test_batched_push.py       +242/-0  (new)
tests/test_fallback_backend.py   +267/-0  (new)
tests/test_openai_cli_backend.py +322/-0  (new)
tests/test_watch_semantic.py     +144/-0  (new)
```

**🔴 Conflict-surface overlap (upstream's 61 changed files ∩ fork's 10 changed files) = exactly 4 files:**
| file | upstream Δ (v0.9.53→v8) | fork Δ (v0.9.53→pin) | risk |
|---|---|---|---|
| `CHANGELOG.md` | +42/-0 | +5/-0 | low — manifest notes this was the ONLY conflict in the last rebase (onto v0.9.50), auto-resolvable |
| `graphify/cli.py` | +31/-3 | +190/-52 | **medium-high** — fork rewrites far more of this file |
| `graphify/llm.py` | +40/-4 | +429/-3 | **highest** — fork's entire backend lives here; upstream also edited it |
| `graphify/watch.py` | +36/-34 | +91/-5 | **medium-high** — upstream did a substantial internal rewrite (34 deletions) in a file the fork also heavily edits |

Files the fork touches that upstream did **not** touch in this window (clean-apply expected): `graphify/__main__.py`, `graphify/exporters/graphdb.py`, and the 4 new test files.
Files upstream touched that the fork does **not** touch (no direct conflict, but the merged tree's behavior in these files is 100% upstream's): `graphify/serve.py` (+91/-4, a large rewrite), `graphify/install.py` (+24/-2), `pyproject.toml` (+2/-1), plus 54 other files (mostly extractors/tests — see the saved file list).

---

## 3. What writes `.graphify_version`, and where the skill installer can write

Local clone verified first: `git -C sources/graphify rev-parse HEAD` → `157a957e89a16246bba3a078de2777711ee85e31` (**exact pin match**); `git -C sources/graphify status --short` → only `?? .agent/` (untracked scratch dir, clean otherwise); `git -C sources/graphify remote -v` → `origin https://github.com/ray-manaloto/graphify` (the fork, as expected).

**`.graphify_version` writer** — `grep -rn "graphify_version" sources/graphify/graphify/`:
- `graphify/install.py:239`, `:250`, `:884`, `:914`, `:1086`, `:1721` and `graphify/__main__.py:183`.
- The actual write (e.g. `install.py:239`): `(skill_dst.parent / ".graphify_version").write_text(__version__, encoding="utf-8")` — **it writes only the package `__version__` string** (e.g. `"0.9.53"`), never a commit SHA. This is exactly why `sources/graphify.manifest`'s own comment says the version string "does not move with the fork" and can't distinguish a forked install from a real upstream one — confirmed by reading the actual write call, not just trusting that comment.

**Installer platform table** (`uv run graphify install --help`, allowlisted read-only):
```
Usage: graphify install [--project] [--strict] [--platform P|P]
Platforms: claude, codex, opencode, kilo, aider, copilot, claw, droid, trae,
trae-cn, hermes, kiro, pi, codebuddy, antigravity, antigravity-windows,
windows, kimi, amp, agents, devin, gemini, cursor
```

**Is `.agents/skills/graphify` a real installer target? YES — for THREE different platform values, not just one:**
- `graphify install --platform agents` (bare, skill-only path, `install()` at `install.py:602`) → `_platform_skill_destination` (`install.py:91-97`): project scope → `./.agents/skills/graphify/SKILL.md`; global scope → `~/.agents/skills/graphify/SKILL.md` (explicitly NOT the same as `amp`'s global `~/.config/agents/skills/graphify/SKILL.md` — the code comment at `install.py:94` says so directly).
- `graphify agents install` (the dedicated subcommand, `_agents_platform_install`, ~`install.py:1567`) additionally wires `AGENTS.md` via `_agents_install` (`install.py:1508`).
- `graphify install --project --platform agents` routes through `_project_install` (`install.py:1585`); `agents` falls into the `elif platform_name in ("copilot", "pi", "kimi", "agents")` branch (~`install.py:1654`) which is **skill-only** (SKILL.md + references at the project scope root) — it does **not** call `_agents_install`/wire `AGENTS.md` in that specific path, unlike the dedicated `graphify agents install` subcommand.
- **Two other platforms target the exact same project path** `./.agents/skills/graphify/SKILL.md`: `amp` (`install.py:87-88`, project branch) and `antigravity`/`antigravity-windows` (`install.py:99-102`, project branch). Three platforms, one shared write target — a real collision surface if two are ever installed into the same project (each just overwrites the other's `SKILL.md` variant).

**Does it write `references/` under `.agents/skills/graphify`, or only `SKILL.md`? It writes `references/` too, conditionally.**
`_PLATFORM_CONFIG["agents"]` (`install.py:460-469`) sets `"skill_refs": "agents"`. Per `_packaged_skill_refs_dir` (`install.py:~106-127`), a platform with `skill_refs` set gets the packaged `graphify/skills/<bundle>/references/` sidecar copied in **only if** that bundle directory ships in the installed build; if the bundle directory is present but its own `references/` subdir is missing, `_copy_skill_file` hard-fails rather than silently installing SKILL.md alone.

---

## 4. The installed artifact

`uv run python -c "from importlib.metadata import distribution; print(distribution('graphifyy').read_text('direct_url.json'))"` (run via `uv run --directory` equivalent — repo root cwd):
```json
{"url":"https://github.com/ray-manaloto/graphify","vcs_info":{"vcs":"git","commit_id":"157a957e89a16246bba3a078de2777711ee85e31","requested_revision":"157a957e89a16246bba3a078de2777711ee85e31"}}
```
**Installed commit == pinned commit == fork clone HEAD. Fully reproducible, triple cross-checked** (pyproject.toml pin, manifest pin, local clone HEAD, and now the live installed distribution all agree on `157a957e89a16246bba3a078de2777711ee85e31`).

`uv run graphify --version` → `graphify 0.9.53` (the version string; per §3, this alone cannot and does not reveal it's a fork — only `direct_url.json` can).

---

## 5. GitHub repos touched

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — upstream: default branch, tags, HEAD SHA, PyPI-adjacent release timing, `v0.9.53...v8` compare (ahead_by/files), `llm.py` content at `v8` (openai-cli/claude-cli grep), PR #3073 and related PR search.
- [ray-manaloto/graphify](https://github.com/ray-manaloto/graphify) — the fork: default branch, `kb-pin/*` and other branches, tags (confirmed absence of v0.9.50–v0.9.56), `v8`/`main` branch staleness, the 8-commit patch compare and its file list, confirmed pinned-commit match.
- PyPI (`pypi.org/pypi/graphifyy/json`) is not a GitHub repo; included for the version/date cross-check only.

Not queried this session (read only as prose inside the committed `sources/graphify.manifest`, not verified independently): `TelB-io/graphify` — the manifest states the fork's patches transported fork-to-fork from there via merged PRs, with "PATCHED FOR TELB-COCKPIT" markers surviving in `graphify/llm.py` (x2) and `graphify/__main__.py` (x1). That claim is unverified by this scout; treat it as inherited, not measured here.

## GitHub repos touched

_Appended by the architect session on 2026-09-09 after the scout went idle without a final hand-back; derived from the commands cited above, nothing new read._

- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — upstream: default branch, tags, `v8` HEAD, compare `v0.9.53...v8`, `llm.py` at `v8`, PRs #3073/#2981 and the codex/openai-cli PR list
- [ray-manaloto/graphify](https://github.com/ray-manaloto/graphify) — the fork: `kb-pin/*` branches, compare base→pin, tag list, `v8`/`main` snapshots; installed `direct_url.json`
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — `pyproject.toml`, `sources/graphify.manifest`, `currency.toml`, the pinned clone `sources/graphify/` (`install.py`, `__main__.py`)
