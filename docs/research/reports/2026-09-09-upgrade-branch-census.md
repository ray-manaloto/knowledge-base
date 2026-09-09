# Upgrade-related branch/worktree census

Read-only fact-finding for the dependency-upgrade workflow (Ray: it "should
search this project, git local branches or git worktrees, github issues,
plans" so prior work is never forgotten). This covers the BRANCH/WORKTREE
half only. Compiled 2026-09-09 by a read-only subagent for team-lead.

Constraints honored: no files edited in any target repo, no branches checked
out, no `graphify` invoked, no credentials printed, all `git` reads via
`git -C <repo>` with absolute paths, no `cd`, no `git fetch`/`pull` (only
already-present local/remote-tracking refs inspected). `gh pr list` was
attempted read-only per the task's explicit ask; a one-shot connectivity
probe (`codex/graphify-0942` → PR #291) confirmed network/auth worked before
spending time on the other 27 branches, so every branch below got a real
answer rather than a blanket "COULD NOT ASK".

Status: COMPLETE.

## Repo 1: knowledge-base (`/Users/rmanaloto/dev/github/ray-manaloto/knowledge-base`, main = `main`)

Worktrees: **one** — the repo itself, `00e7e5ee [main]`. No other worktrees exist.

Stash (6 entries, none deleted, none inspected further — flagged only):
`stash@{0..3}` are `#710` `.codex/config.toml`-overwrite evidence, unrelated
to upgrades. `stash@{4}` (`On codex/graphify-0942: WIP 2026-08-13 all-tools
currency reports preserved before Graphify 0.9.42 PR`) and `stash@{5}` (`On
main: WIP Graphify 0.9.42 currency assessment 2026-08-13`) are tied to the
now-merged 0.9.42 upgrade (PR #291) and are almost certainly stale, but they
are invisible to any branch scan — worth a `git stash show -p` before ever
running `git stash clear`.

Extra branches matching `upgrade|bump|currency|sync|pin|fork` not in the
supplied list: only **one** genuinely new name,
`chore/agent-harness-docs-resync-registry` (profiled below). Everything else
the grep surfaced was either already in the supplied list or a
`remotes/origin/…` mirror of a local branch already in the list.

| branch | tip (12) + date | ahead | behind | merged (gh) | files touched | purpose (newest subjects) | verdict |
|---|---|---|---|---|---|---|---|
| `analysis/graphify-3073` | `cf727ca50f6e` 2026-08-25 | 2 | 86 | NOT merged (`[]`) | 7 files, +288/-31 | "the fork's exit condition named a PR that can never merge"; "advance the fork pin to 4e986d37 — the ported failure-path tests" | **LIVE WORK, unclear value** — this appears to BE the analysis that concluded upstream PR #3073 can't merge cleanly, which is exactly what today's repo-2 findings independently confirm (see below). Superseded in *outcome* by the pin's actual march to v0.9.53, but never closed/documented as such. Worth a skim, not a blind delete. |
| `feat/currency-path-probe` | `f3bd4e4ebf3a` 2026-08-25 | **0** | 86 | NOT merged (`[]`) | none | none — zero unique commits | **No unique content vs main** — safe to delete regardless of PR status |
| `codex/migration-source-sync` | `e4142ded9ac3` 2026-08-10 | **0** | 127 | NOT merged (`[]`) | none | none | **No unique content** (identical tip to `codex/graphify-0.9.39-kb` below) — safe to delete |
| `round/2026-08-25-e-currency-map` | `0c39cca3317a` 2026-08-25 | 18 | 83 | **MERGED #512** (2026-08-25) | 46 files, +3993/-201 | gitleaks/hk fixes, "#500 respec round 2" | **MERGED** — safe to delete |
| `round/2026-08-25-g-currency-499` | `6cc61d383bca` 2026-08-25 | 9 | 82 | **MERGED #514** (2026-08-25) | 23 files, +2753/-82 | mutant-arm count fix, cold-review rounds, #499 | **MERGED** — safe to delete |
| `round/2026-08-25-h-openai-cli-fork` | `6fbd74a38f5a` 2026-08-26 | 7 | 81 | **MERGED #517** (2026-08-26) | 15 files, +1411/-49 | "move the fork pin to v0.9.50 + the MCP fix" | **MERGED** — safe to delete |
| `round/2026-08-26-a-graphify-coverage` | `a53c0d587c9e` 2026-08-26 | 24 | 80 | **MERGED #542** (2026-08-27) | 72 files, +10691/-238 | funnel round, antigravity-cli pin, code-intel/absent_binary fixes | **MERGED** — safe to delete |
| `feat/phase-g-wave-0` | `cfe3b38fcf68` 2026-09-02 | 3 | 22 | NOT merged (`[]`) | 21 files, +2412/-18 | "Wave 0 complete — provenance groundwork, receipts, contained arms"; LSP-conflict findings | **LIVE WORK** — matches memory exactly (Phase G paused by Ray, no PR). Directly continued by repo-2's unpushed `6ca68bd` below. |
| `salvage/graphify-ecosystem-wip` | `149c02e1ca6f` 2026-08-13 | 1 | 126 | NOT merged (`[]`) | 29 files, +6071/-53 | single commit: "WIP preservation snapshot: /private/tmp/kb-graphify-ecosystem.bmSQpv/repo" | **STALE, likely superseded** — predates the entire 0.9.42→0.9.53 pin chain, but it is a rescued `/private/tmp` scratchpad (memory: such work is normally REAPED with 0 survivors) — recommend a diff skim, not a confident delete |
| `codex/graphify-0942` | `5eda15259498` 2026-08-13 | 2 | 118 | **MERGED #291** (2026-08-13) | 16 files, +257/-29 | "upgrade Graphify to 0.9.42" | **MERGED** (content superseded by 0.9.53, but the branch itself landed) — safe to delete |
| `codex/graphify-0.9.39-kb` | `e4142ded9ac3` 2026-08-10 | **0** | 127 | NOT merged (`[]`) | none | none | **No unique content** — safe to delete |
| `codex/issue-299-graphify-ast-baseline` | `3018dff30da3` 2026-08-14 | 5 | 117 | **MERGED #307** (2026-08-14) | 15 files, +4032/-27 | deterministic AST baseline, admission-review gating | **MERGED** — safe to delete |
| `codex/issue-301-graphify-0943-no-provider` | `8ace6198cf26` 2026-08-14 | 2 | 112 | **MERGED #312** (2026-08-14) | 35 files, +1976/-209 | issue-301 plan for 0.9.43, preserve historical slice compat | **MERGED** — safe to delete |
| `fix/plugin-count-and-codex-pin` | `048b6a7215ec` 2026-08-27 | 4 | 79 | **MERGED #543** (2026-08-27) | 5 files, +51/-26 | gitleaks suppress (#506), codex pin resync to rust-v0.150.1 (#539) | **MERGED** — safe to delete |
| `keep/plugin-count-and-codex-pin` | `d75498847b76` 2026-08-27 | 26 | 80 | NOT merged (`[]`) | 76 files, +10734/-263 | same pin-resync + plugin-count content as `fix/…`, on a stale base that still carries `round/2026-08-26-a`'s 24 commits as "ahead" | **SUPERSEDED by `fix/plugin-count-and-codex-pin`** (#543) — same end-state, old duplicate — safe to delete |
| `chore/skills-1.2.2-sync` | `e0eed632fca7` 2026-08-05 | 2 | 162 | NOT merged (`[]`) | 2 files, +38/-2 | bump codex 0.146.1 / antigravity-cli 1.1.10 | **SUPERSEDED** — codex/antigravity pins have moved far past this elsewhere (rust-v0.150.1+, 1.1.21+) — safe to delete |
| `origin/chore/s1-tool-currency-2026-09-01` | `a7a8dd69cdf4` 2026-09-01 | 5 | 25 | **MERGED #651** (2026-09-01) | 37 files, +1729/-349 | propagate ruff/ty/codegen bumps to every pin site, hk 1.57.0, agnix 0.52.1 | **MERGED** — safe to delete |
| `origin/chore/cli-currency-sweep` | `7a1f54ef98b0` 2026-08-31 | 34 | 30 | **MERGED #639** (2026-08-31) | 40 files, +5124/-271 | CLI-currency round + eli5-visual one-screen-rule closure | **MERGED** — safe to delete (matches memory: "#639 LANDED") |
| `origin/chore/claude-2-1-257-resync` | `dbab142440b0` 2026-09-02 | 9 | 24 | **MERGED #659** (2026-09-02) | 72 files, **+162174**/-91 | "first green kb-build since the N0 resync — 3 of our own gates were wrong" | **MERGED** — safe to delete. The huge insertion count is a build-receipt/artifact diff the branch's own later commit gitignores ("the GREEN build's receipt had no ignore rule") — not a real 162k-line code change. |
| `origin/codex/issue-301-complete-graphify-semantics` | `fd7343e58126` 2026-08-14 | 2 | 113 | **MERGED #311** (2026-08-14) | 6 files, +784/-12 | normalize parser error offsets, sanitized parser diagnostics | **MERGED** — safe to delete. This is issue #301's *other* attempt, alongside `codex/issue-301-graphify-0943-no-provider` (#312) — both landed as separate PRs. |
| `chore/agent-harness-docs-resync-registry` *(found by grep, not in the supplied list)* | `8bc2874ef439` 2026-08-29 | 2 | 57 | **MERGED #606** (2026-08-29) | 6 files, +344/-1 | resync agent-harness-docs, register chenrui333/codex-docs finding | **MERGED** — safe to delete |

**Net for repo 1: of 21 branches examined, only 2 are real unmerged LIVE WORK**
(`feat/phase-g-wave-0`, `analysis/graphify-3073`) **+ 1 ambiguous stale WIP**
(`salvage/graphify-ecosystem-wip`). Everything else is either MERGED (15
branches, safe to delete) or has zero unique content vs `main` (3 branches,
safe to delete regardless of PR state).

## Repo 2: graphify fork (`/Users/rmanaloto/dev/github/ray-manaloto/graphify`)

Single worktree (`/Users/rmanaloto/dev/github/ray-manaloto/graphify`, checked
out to `kb-pin/openai-cli-backend-v0.9.53` at `6ca68bd`). No stash. Working
tree clean (`status --short` empty).

Local branches (`branch -vv`):
- **`kb-pin/openai-cli-backend-v0.9.53`** (current) — tracks
  `origin/kb-pin/openai-cli-backend-v0.9.53`, **1 commit unpushed**:
  `6ca68bd feat(provenance): stamp per-item + run-level extraction provenance (#518 commit 1)`.
- **`pr3073`** @ `4e1cfd6` — a preserved copy of upstream PR #3073 as
  originally submitted (author "Azeem"): `4e1cfd6` (the openai-cli-backend
  feat) → `282976b` (bump to 0.9.49) → `0b5297b` (0.9.49 changelog).

Remote `kb-pin` lineage (`branch -r | grep kb-pin`): `openai-cli-backend`,
`…-v0.9.49`, `…-v0.9.49-tests`, `…-v0.9.50`, `…-v0.9.53` — five successive
pin-advance branches, oldest to newest.

**`6ca68bd` size** (`show --stat`): 5 files, **928 insertions(+), 2
deletions(-)** — `graphify/cli.py` (+182), `graphify/dedup.py` (+57),
`graphify/export.py` (+61), plus two new test files
(`test_cache_producer_identity.py` +325, `test_producer_provenance.py`
+305). Commit message states: full fork suite 5143 passed / 15
pre-existing-baseline failures / 146 skipped / 1 strict xfail. This is real,
verified, **unpushed** Phase G work (#518 commit 1, Ray's "stop at commit 1"
D1 ruling) — a rebase onto a newer graphify tag must carry it.

**`pr3073` ancestry check**: `git merge-base --is-ancestor 4e1cfd6
kb-pin/openai-cli-backend-v0.9.53` → **rc=1 (NOT an ancestor)**. Our fork's
actual first patch (`57245ec`, same author "Azeem", identical subject) is a
*separate* commit object, not upstream's own — i.e. we recreated/cherry-picked
the change rather than merging the PR branch itself. `pr3073` therefore has
**no unshipped value** beyond serving as a reference copy of exactly what
upstream submitted (useful if ever diffing against the real PR #3073, low
priority otherwise).

**Local tags** (`tag -l 'v0.9.5*'`): `v0.9.5, v0.9.50, v0.9.51, v0.9.52,
v0.9.53` — nothing newer visible. Per instructions, **not fetched**; whether
v0.9.54+ exists upstream is unknown from this machine.

**The 9 patch commits** (`v0.9.53..kb-pin/openai-cli-backend-v0.9.53`, oldest
first) a rebase onto a newer tag must replay — **8 already pushed to
origin, 1 unpushed** (`6ca68bd`, listed first below since `log` orders
newest-first):

1. `6ca68bd` 2026-09-02 — provenance stamping (#518 commit 1) — **unpushed**
2. `157a957` 2026-08-25 — fix(openai-cli): only disable MCP servers Codex can resolve
3. `72e33a5` 2026-08-24 — feat: batched UNWIND push for neo4j/falkordb export
4. `2819120` 2026-08-24 — feat: `graphify watch --semantic` auto-runs LLM extraction
5. `025a24f` 2026-08-24 — test: a partially-succeeded primary pass must not fire the fallback
6. `a4842b4` 2026-08-24 — feat: `extract --fallback-backend` retries a zero-success pass
7. `b34f386` 2026-08-23 — fix(openai-cli): disable each configured MCP server per call
8. `7e2f389` 2026-08-23 — feat(cli): credential gate knows openai-cli
9. `57245ec` 2026-08-23 — feat(llm): openai-cli backend (the original feature)

## Repo 3: dotfiles (`/Users/rmanaloto/dev/github/ray-manaloto/dotfiles`)

Default branch: `main` (`origin/HEAD` → `main`). Currently checked out to
**`main` @ `62f416f` (2026-09-09)**, `refactor(tests): share one lock-call
recorder and the staged-line binding (#992)` — i.e. local `main` is fully
current, past even today's two branches under test.

| branch | tip + date | ahead of main | behind | merged (gh) | files touched | purpose | verdict |
|---|---|---|---|---|---|---|---|
| `chore/deps-currency` | `55b6f10` 2026-08-27 | 2 | 94 | NOT merged (`[]`) | 20 files, +5336/-3904 | bump shared host↔image tools, regen image locks | **SUPERSEDED** by the chain below — safe to delete |
| `chore/deps-currency-v2` | `2f19656` 2026-08-27 | 4 | 89 | NOT merged (`[]`) | 20 files, +4923/-3492 | same + "lock uv's linux entries from linux, not macOS" | **SUPERSEDED** — safe to delete |
| `feat/refresh-bump-latest-pins` | `ec54bad` 2026-09-03 | 1 | 21 | NOT merged (`[]`) | 5 files, +1270/-1106 | "re-resolve latest pins with --bump, and move the 29 that were frozen" | **SUPERSEDED** by `fix/refresh-bump-latest-pins-961` (identical subject, redone fresh, merged today) — safe to delete |
| `fix/refresh-bump-latest-pins-961` | `836be7b` **2026-09-09 (today)** | 1 | 3 | **MERGED #989** (2026-09-09) | 3 files, +74/-3 | "re-resolve latest pins with --bump" | **MERGED TODAY** — safe to delete. This is the live "bump every pin to latest" mechanism — see Consolidated. |
| `fix/lock-refresh-root-bump-990` | `3e258ad` **2026-09-09 (today)** | 1 | 2 | **MERGED #991** (2026-09-09) | 2 files, +89/-2 | "re-resolve fuzzy pins at the third mise lock call site" (closes #990) | **MERGED TODAY** — safe to delete |
| `origin/chore/deps-currency-20260831` | `b30d10f` 2026-09-01 | 24 | 51 | **MERGED #885** (2026-09-01) | 112 files, +13191/-1642 | apt-pin security bumps, `.agents`/`.omc` retirement+resync | **MERGED** — safe to delete |
| `origin/chore/deps-currency-safe` | `8e1e580` 2026-08-27 | 1 | 88 | **MERGED #793** (2026-08-27) | 9 files, +440/-426 | host tool + GitHub Actions currency, from renovate-dryrun | **MERGED** — safe to delete |
| `origin/chose/deps-currency-image` *(as named in the task)* | — | — | — | — | — | — | **Does not exist** — typo. Real branch is `origin/chore/deps-currency-image` (confirmed by the branch grep below). |
| `origin/chore/deps-currency-image` *(corrected spelling)* | `7a79554` 2026-08-27 | 3 | 85 | **MERGED #795** (2026-08-28) | 18 files, +2506/-2143 | GCC_LATEST_DEB_SHA256 recompute, bound image-lock regen to declared OS families | **MERGED** — safe to delete |

Two just-merged commits, inspected directly since they are today's work:
- `836be7b` (#989): touched `.github/actions/lock-refresh/action.yml` (+12/-1)
  and `python/src/dotfiles_setup/image_lock.py` (+16/-2) + its test.
- `3e258ad` (#991, closes #990): touched
  `python/src/dotfiles_setup/lock_refresh.py` (+12/-1) + its test.

**Does dotfiles have a reusable "bump every pin to latest" mechanism? Yes —
and it isn't custom code, it's mise's own `mise lock --bump` flag, now wired
through consistently.** `lock_refresh.py:267` calls
`["mise", "lock", "--bump", *tools]`, with the comment at `:248`: *"`--bump`
is the **third instance** of the flag #989 added to the two image [lock
call sites]"* — i.e. PRs #989 (image locks, 2 call sites) and #991 (root
lock, `lock_refresh.py`) made all **3** of dotfiles' `mise lock` call sites
pass `--bump`, so a routine re-lock now also advances pins past their
current semver-range ceiling instead of just re-resolving inside it. No
bespoke "bump" module exists — grepping for `bump` in `mise.toml` and the
python package turns up only comments referencing this same flag. Module:
`/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/python/src/dotfiles_setup/lock_refresh.py`
(root-lock caller) and `image_lock.py` (the two image-lock call sites).

Relevant `mise.toml` tasks (line numbers as of `main@62f416f`):
`tool-currency` (586, thin caller of the **shared** `kb_setup.currency`
engine — the same one this repo owns), `tool-currency-check` (595, offline
drift check), `lock-refresh-root` (1278), `lock`/`lock-shared` (adjacent,
the `--bump`-carrying re-lock tasks), `verify-container-latest` (941),
`p2996-refresh` (1354), `schema-vendor-refresh` (1362, network-using schema
re-download). None of these is a bespoke "bump everything" script — they are
thin `uv run … dotfiles-setup …` callers per dotfiles' own zero-bash-logic
policy, same shape as this repo's `kb-*` tasks.

Additional `upgrade|bump|currency|sync|pin|fork`-matching branches found by
grep but **not individually profiled** (out of the task's named scope; listed
for completeness so nothing is silently dropped): `docs/session-2026-07-16-sync`,
`fix/962-gnupg-apt-pin`, and ~20 more `remotes/origin/…` entries spanning
2026-07 through 2026-08 (`chore/host-tool-bumps-scoped-lock`,
`chore/mise-2026.7.12-upgrade`, `docs/237-count-sync-and-hk-row`,
`docs/448-doc-sync`, `docs/eval-harness-pin-bumped`,
`docs/session-2026-07-14-sync`, `docs/session-2026-07-21-sync`,
`docs/sync-343-and-handoff`, `feat/288-apt-pin-sweep`,
`feat/devcontainer-build-mise-chezmoi-resync`, `feat/graphify-t1-pin`,
`feat/llvm-apt-llvm-org-pinned`, `feat/tier0-currency-bumps`,
`feat/tool-currency-dotfiles`, `fix/391-kb-setup-pin-and-cc-contract`,
`fix/567-dag-topology-pins`, `fix/800-sync-id-labels`,
`fix/841-gcc-pin-os-scoped-smoke`, `fix/apt-pins-332`,
`fix/libssl-dev-apt-pin-stale`, `fix/sync-smoke-platform-env`). Given their
age (mostly July–mid-August) and that `main` is already at `#992`, most are
very likely merged/superseded like their profiled siblings above, but this
was not verified branch-by-branch.

## Consolidated

**LIVE WORK to preserve (do not delete):**
1. **`feat/phase-g-wave-0`** (knowledge-base, `cfe3b38fcf68`) — Phase G Wave 0,
   paused by Ray, no PR yet. Continues directly into:
2. **`6ca68bd`** on `kb-pin/openai-cli-backend-v0.9.53` (graphify fork,
   **unpushed**) — Phase G's actual code (#518 commit 1: per-item + run-level
   extraction provenance, 928 lines, 5143/15/146/1 test result). Must be
   pushed (or replayed) before any rebase onto a newer graphify tag, since a
   rebase target only sees pushed history.
3. **`analysis/graphify-3073`** (knowledge-base, `cf727ca50f6e`) — likely the
   analysis that concluded upstream PR #3073 can't merge cleanly; connects
   directly to today's finding that `pr3073`'s commit is NOT an ancestor of
   our pin branch. Worth reading before deleting, not urgent to act on.
4. **`salvage/graphify-ecosystem-wip`** (knowledge-base, `149c02e1ca6f`) —
   ambiguous value, but it's a rescued `/private/tmp` scratchpad snapshot
   (such work is normally unrecoverable) — diff before deleting.
5. **`pr3073`** (graphify fork, `4e1cfd6`) — low-priority reference copy of
   upstream's actual PR #3073 submission; safe to keep cheaply, safe to
   delete if disk/branch hygiene matters more than the provenance anchor.

**MERGED / no-unique-content — safe to delete (18 in knowledge-base, 6 in
dotfiles):** every other branch in both tables above. In knowledge-base:
`round/2026-08-25-e-currency-map` (#512), `round/2026-08-25-g-currency-499`
(#514), `round/2026-08-25-h-openai-cli-fork` (#517),
`round/2026-08-26-a-graphify-coverage` (#542), `codex/graphify-0942` (#291),
`codex/issue-299-graphify-ast-baseline` (#307),
`codex/issue-301-graphify-0943-no-provider` (#312),
`fix/plugin-count-and-codex-pin` (#543),
`origin/chore/s1-tool-currency-2026-09-01` (#651),
`origin/chore/cli-currency-sweep` (#639),
`origin/chore/claude-2-1-257-resync` (#659),
`origin/codex/issue-301-complete-graphify-semantics` (#311),
`chore/agent-harness-docs-resync-registry` (#606) — all merged; plus
`feat/currency-path-probe`, `codex/migration-source-sync`,
`codex/graphify-0.9.39-kb` (zero unique commits vs main); plus
`keep/plugin-count-and-codex-pin` (superseded duplicate of the merged
`fix/…`) and `chore/skills-1.2.2-sync` (stale codex/antigravity pin bump,
long superseded). In dotfiles: `chore/deps-currency`,
`chore/deps-currency-v2`, `feat/refresh-bump-latest-pins` (all superseded by
today's merged #989/#991), plus `fix/refresh-bump-latest-pins-961` (#989),
`fix/lock-refresh-root-bump-990` (#991),
`origin/chore/deps-currency-20260831` (#885),
`origin/chore/deps-currency-safe` (#793), `origin/chore/deps-currency-image`
(#795) — all merged.

**Reusable dotfiles code for the upgrade workflow:** dotfiles does NOT have a
bespoke "bump everything" module — it uses **mise's own native `mise lock
--bump`** flag, now wired into all 3 of its lock call sites as of today's
PRs #989/#991:
`/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/python/src/dotfiles_setup/lock_refresh.py:267`
(root lock) and `image_lock.py` (the two image-lock sites). If
knowledge-base's upgrade workflow needs "advance every pin past its current
constraint," the native `--bump` flag on whatever `mise lock`/`mise
run kb-*` call site already exists is the pattern to copy — consistent with
this repo's own `use-tool-builtins.md` (prefer the tool's native mechanism
over hand-rolled bump logic). The shared `kb_setup.currency` engine
(`tool-currency`/`tool-currency-check` tasks) is the OTHER reusable piece,
and knowledge-base already owns and consumes it directly.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — branch census, `gh pr list` merged-status checks (21 branches)
- [ray-manaloto/dotfiles](https://github.com/ray-manaloto/dotfiles) — branch census, `gh pr list` merged-status checks (8 branches), mise.toml/`lock_refresh.py` inspection for reusable bump tooling
- [ray-manaloto/graphify](https://github.com/ray-manaloto/graphify) — our fork; confirmed via `git remote -v` (`origin`). Inspected only via local git — no `gh` calls made against it.
- [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) — upstream, configured as the `upstream` remote on the same clone; `pr3073` and the "9 patch commits" are our fork's relationship to this repo's history.
