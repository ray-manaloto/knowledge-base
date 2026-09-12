# Lane a2-handoff-claims — re-testing every claim in `session-2026-09-12-f.md`

Commit examined: **`c1d8afb8`** (current branch HEAD, `feat/754-plugin-types-contract`).
The handoff file itself was written at `c33a1fb573b1`, one commit behind HEAD.

Every sentence was treated as unverified until re-derived by a second route
(`change-the-route.md`): parsing JSON/TOML directly rather than trusting prose,
re-running gates and arms live rather than reading a report about them, hitting
`gh` directly for issue/PR state.

## Summary table

| # | Claim | Verdict | Probe |
|---|---|---|---|
| 1 | HEAD `c33a1fb573b1` is 3 commits ahead of `main` | **REFUTED** | `git rev-list --count main..c33a1fb573b1` = **5**, not 3. Stale/inherited number — the prior handoff (`-e.md`) correctly said "3" when HEAD was `cbd8827d` (verified: 3 there), and this handoff copied the phrase forward without re-deriving it after two more commits (`4cdd8bfb`, `c33a1fb5`) landed. |
| 2 | SHAs `4cdd8bfbc3a2…` and `c33a1fb573b1…` exist and are what the text says | CONFIRMED | `git cat-file -t` on both → `commit`; `git log` shows them at the stated positions |
| 3 | Gates on `4cdd8bfbc3a2…`: 11 passed / 0 failed, every row `dirty:false`, sha matches | CONFIRMED | Opened `.agent/kb/gates/gates-4cdd8bfbc3a2d7919adc8057c34afd487813fa26.json` directly: 11 rows, all `rc:0`, all `dirty:false`, all `sha` fields match the top-level `sha`. `GATE_TASKS` in `gates.py:173-201` also lists exactly these 11 task names, confirming nothing is missing from the tuple. |
| 4 | "the other nine were NOT re-run at `c33a1fb573b1`" | CONFIRMED | `find .agent/kb/gates -iname "*c33a1fb5*"` → 0 files. No artifact exists for that SHA. |
| 5 | (Not in handoff verbatim, but implied by "re-run and report the truth at HEAD") gates at **current** HEAD `c1d8afb8` | **NEW FINDING, not a claim in the file but material** | Ran `mise run kb-gates` live: **8 passed / 3 failed** (`lint` rc=1, `test` rc=2, `kb-mod-runtime-check` rc=127). See § Gates at HEAD below — none of the three failures indict the reviewed commits themselves. |
| 6 | `register.ts:46`: "NEVER BASH", over-broad, forbids the one design that works | CONFIRMED | `sed -n '40,70p' .claude/mods/kb-settings-guard/hooks/register.ts`: line 46 reads literally "NEVER BASH", with no `tool.call`/`tool.check` qualifier anywhere in the file (`grep -n "tool.check\|tool.call"` finds only `tool.call` uses, 5 hits, 0 for `tool.check`). The module registers exclusively via `on("tool.call", …)` (`:202`). So the comment, read on its own, forbids Bash on any event including `tool.check`, which this round's own findings say works. |
| 7 | `next.origin` is host-set/unforgeable, cited at `claude-code.d.ts:3841-3846` (generated, absent from repo) | **UNVERIFIABLE from static repo state** (not refuted) | `.claude/types/claude-code.d.ts` genuinely does not exist on disk (`ls` → No such file). `mod_runtime.py:139` confirms this is `PRIMARY_DECLARATIONS`, generated fresh per run in a `tempfile.TemporaryDirectory` (`:528`), never committed. The only committed candidate, `sources/media/claude-code-function-hooks-types.d.ts` (a different, older Claude Code pin), has **different content** at lines 3841-3846 (`PaneCloseOrigin`, not `next.origin`) — expected, since it's a stale vendored snapshot, not the file the citation is about. I could not re-run `/plugin-types` against the live 2.1.269 binary in this lane to check the exact line numbers (would require a fresh temp-dir invocation outside repo scope and was not attempted given the lane's read-only remit). The claim is internally consistent with the tracked chain (`fh-synthesis.md:33` → `README.md:17` → this handoff) and is not contradicted by anything I could check, but it rests on a file this repo cannot reproduce statically. |
| 8 | "the tool event family is exactly five: `tool.call`, `tool.check`, `tool.describe`, `tool.list`, `tool.register`. `tool.result` DOES NOT EXIST" | CONFIRMED | `docs/research/reports/2026-09-12-function-hooks-round/graph-first-hook.md:156-159`: "The declarations carry 74 event keys; the `tool.*` family is `tool.call`, `tool.check`, `tool.describe`, `tool.list`, `tool.register` — no `tool.result`." This is a live-measured claim inside the tracked report, not merely relayed. The vendored older `.d.ts` corroborates 4 of 5 (`tool.check` postdates that pin, as expected). |
| 9 | `.claude/mods/kb-settings-guard/hooks/register.ts:46` file:line — exists, content matches | CONFIRMED | see #6 |
| 10 | `session-audit-synthesis.md:452` — handoff block at that line | CONFIRMED | `sed -n '440,465p'` at that path shows exactly the "## 5. HANDOFF BLOCK" heading immediately following line 452's table row, matching the handoff's own citation ("handoff block at line 452" is a description carried in `README.md`, not the -f.md handoff itself, but it checks out) |
| 11 | `scratch-isolation-review.md:655` cited elsewhere as the `lane_scratch` scope source | Not directly in -f.md, but the file has 830 lines so line 655 is in-range | `wc -l` = 830 |
| 12 | "codex lanes CANNOT query the graph (#778)" | CONFIRMED | `gh issue view 778` → OPEN, title exactly matches: "A codex lane cannot query the graph — 'query the graph FIRST' is unfollowable from inside one, and lanes silently fall back to grepping" |
| 13 | Issue states: #754, #767, #748, #766, #778, #779, #756, #771, #772, #759, #763 all OPEN | CONFIRMED | `gh issue view <n> --json state,title` for all 11 → every one `OPEN`, titles match what the handoff describes each as being about |
| 14 | #1470 / #1471 (upstream `kenn-io/agentsview`) both OPEN | CONFIRMED | `gh issue view 1470/1471 --repo kenn-io/agentsview --json state` → both `OPEN` |
| 15 | "19 research reports" promoted | CONFIRMED | `ls docs/research/reports/2026-09-12-function-hooks-round/*.md \| wc -l` = 19 |
| 16 | "26 hermetic tests" in `test_mod_runtime.py` | CONFIRMED | `grep -c "^def test_" tests/test_mod_runtime.py` = 26 |
| 17 | "11/11 arms died, 1/1 control" for `docs/research/arms/2026-09-12-g01-mod-runtime.toml` | CONFIRMED, live re-run | `mise run kb-arms -- docs/research/arms/2026-09-12-g01-mod-runtime.toml` → `11/11 arms died; 1/1 controls held` (A0 CONTROL HELD, A1-A11 all DIED). Ran it myself, not read from a report. |
| 18 | "13 collision classes" beyond agent files, incl. `.agent/notepad.md`, `session-review.js:995`, `kb-extract.js:275` | CONFIRMED | `scratch-isolation-review.md:693` heading is literally "## 7. THE FULL COLLISION INVENTORY — 13 classes", 13 numbered items follow. `session-review.js` is 1408 lines (line 995 in range, content at that line is a `parallel(...)` block matching the collision claim's shape); `kb-extract.js` is 287 lines (line 275 in range, content is the `phase('Extract')` fan-out). |
| 19 | "283 'lost' Claude sessions survive in agentsview's archive" | CONFIRMED (relayed accurately) | `agentsview-research.md:96` states the figure and cites upstream `#1470`/`#1471`, both independently confirmed OPEN (#14 above) |
| 20 | "Two `Bash\|Grep` PreToolUse entries exist in `.claude/settings.json`" | CONFIRMED | Parsed `.claude/settings.json` as JSON (not grep) and filtered `PreToolUse` hooks whose matcher contains both `Bash` and `Grep`: exactly 2 entries — graphify's `hook-guard search` and `kb-setup hookguard` |
| 21 | "no `kb-review` receipt exists for `c33a1fb5`" | CONFIRMED | `find .agent/kb/review -iname "*c33a1fb5*"` → 0 files; `ls .agent/kb/review/` shows 150+ receipts but none for this SHA |
| 22 | `docs/artifacts/754-changed-shape.html` — CARRIED, not updated | CONFIRMED | `git log -1 --format=%H -- docs/artifacts/754-changed-shape.html` = `cbd8827d3982…`, i.e. its last edit predates both `4cdd8bfb` and `c33a1fb5`. Untouched this round, matching "CARRIED... Not done." |
| 23 | `guard_inventory.strip_ts_comments` reused, `strip_ts_strings` added — DONE in `4cdd8bfb` | CONFIRMED | `mod_runtime.py:298-299` calls `guard_inventory.strip_ts_comments(register_source)` then its own `strip_ts_strings(no_comments)` (`:274`) |
| 24 | `_stale_generated_files` NOT reused; `mod_runtime.topology_findings` is its own exact-set detector — DONE in `4cdd8bfb` | CONFIRMED | `mod_runtime.py:355` defines `topology_findings`, distinct from `guard_codegen._stale_generated_files` (`guard_codegen.py:287`), and `mod_runtime.py:37` explicitly documents why it does not reuse that function |
| 25 | "no PR open" for this branch | CONFIRMED | `gh pr list --head feat/754-plugin-types-contract --state all --json number,state` → `[]` |
| 26 | "11 pins behind" | CONFIRMED | `mise run kb-currency-check` lists exactly 11 tools "pinned … but upstream had …": agnix, claude-code, datamodel-code-generator, fnox, graphify, hk, mise, ruff, rumdl, ty, uv |
| 27 | "now three manifests behind (agentsview, antigravity-cli, and the new claudex-loop)" | CONFIRMED | Same `kb-currency-check` run: `[graph] corpus inputs changed since the graph was built`: `sources/agentsview.manifest` (added), `sources/antigravity-cli.manifest` (content changed), `sources/claudex-loop.manifest` (added) — exactly 3 |
| 28 | Auto-memory index over its read limit, this round replaced the lead line rather than appending | CONFIRMED, reproduced live | The system reminder in THIS session states MEMORY.md is 30.3KB against a 24.4KB limit and part was cut off — reproducing the exact condition described |
| 29 | "The P1 fix in `c33a1fb5` is UNREVIEWED and UNARMED — no test covers the flag behaviour, no arm proves the FAIL direction" | CONFIRMED | The commit message of `c33a1fb5` itself says verbatim: "The `mod_runtime` fix is UNREVIEWED and UNARMED." `grep -rn "CLAUDE_CODE_ENABLE_FUNCTION_HOOKS" tests/test_mod_runtime.py docs/research/arms/2026-09-12-g01-mod-runtime.toml` → 0 hits in either; only production code (`mod_runtime.py:415,425,559`) references it |
| 30 | "THREE P1s still open in `mod_runtime.py`" (symbol-set shrinkage, `agentId` substring-in-comment, writes into caller's real HOME) | Consistent with commit message's own "Known gaps" section, which lists the same three items verbatim | `git show c33a1fb5` commit body, "## Known gaps" section |

## Gates at HEAD `c1d8afb8` — the truth, re-run live

I ran `mise run kb-gates` (in background, ~9 min) at the actual current HEAD.
Result: **8 passed / 3 failed.** None of the three failures is evidence the
reviewed commits (`4cdd8bfb`, `c33a1fb5`) themselves regressed:

1. **`lint` FAIL (taplo_format)** — caused by an **untracked** file,
   `docs/dag/2026-09-12-session-review-round.toml`. This file is this review
   round's own orchestration DAG (created by the team-lead dispatching this
   very review), not part of the reviewed commits. Confirmed with
   `taplo fmt --check --diff docs/dag/2026-09-12-session-review-round.toml`,
   which reproduces the exact formatting diff hk reported. **Caveat, found
   while chasing this down and worth a separate ticket**: `taplo fmt --check`
   against every git-tracked `.toml` (`taplo fmt --check --diff $(git ls-files
   '*.toml')`) ALSO flags a pre-existing tracked file,
   `sources/groups/graphify-ecosystem.toml` (last touched `f131ea1c`,
   2026-08-12, unchanged since and unchanged at `4cdd8bfb` too). I could not
   determine in this lane's time budget why the historical gates run at
   `4cdd8bfb` recorded `lint rc=0` despite this — hk may cache per-file
   results, or something about how `hk run check --all` was invoked then
   differed. **UNVERIFIED**: whether this tracked-file taplo failure is new or
   has been silently present since Aug 12.
2. **`test` FAIL (rc=2)** — one xdist worker failed
   `tests/test_codex_lane.py::test_the_bound_kills_the_group_on_a_non_tee_run`
   with a `FileNotFoundError` reading `descendant.pid` mid-test — a timing race
   in a process-group-kill test, not a functional regression. This matches the
   *shape* of the flakiness already tracked in **#748** ("the … gate is flaky
   under xdist: two timing-sensitive tests failed in three full kb-gates runs,
   both pass alone" — OPEN, confirmed above), though I did not re-run this
   specific test in isolation to prove it passes alone (time budget).
3. **`kb-mod-runtime-check` FAIL (rc=127)** — `/plugin-types` could not run
   because `claude --version` itself would not run in this environment at the
   moment I ran the gate (`.../mise/installs/node/26.8.2/bin/claude`). This
   looks like a local environment hiccup during this concurrent 5-lane review
   (multiple heavy processes running at once), not a code defect — the same
   task passed cleanly (rc=0) in the historical `4cdd8bfb` gates artifact.

**Bottom line on gates**: the handoff's own hedge — "treat as UNVERIFIED at
HEAD, not as 11/11" — was the right call. At true current HEAD the honest
answer is 8/11, but every one of the 3 failures traces to review-round
contamination (untracked orchestration file), known flakiness (#748), or a
transient environment issue, not a defect newly introduced by `4cdd8bfb` or
`c33a1fb5`. This is new information the handoff did not have (it only said
"not re-run") and should be recorded before anyone assumes a clean re-run.

## The one REFUTED claim, restated plainly

**"3 commits ahead of `main`" is wrong.** At `c33a1fb573b1`, HEAD is **5**
commits ahead of `main` (`c706414e`, `6563b6ef`, `cbd8827d`, `4cdd8bfb`,
`c33a1fb5`). The prior handoff (`session-2026-09-12-e.md`) correctly said "3
commits ahead" when its own HEAD was `cbd8827d` — verified true at the time
(`git rev-list --count 440b9e62..cbd8827d` = 3). This handoff copied the same
phrase forward without re-deriving it after two more commits landed. This is
exactly the "inherited number" failure mode `probes-need-a-control-arm.md`
rule 6 warns about — a number that arrives from a prior handoff with no
control arm reattached to it.

This is a minor, cosmetic miscount (does not change what shipped or what is
owed), but it is the one clearly FALSE sentence in the file.

## Everything else checked and not separately tabled

- `.claude/types/claude-code.d.ts (absent)` parenthetical — CONFIRMED, file genuinely absent (see #7)
- Carried-forward reconciliation section (#767/#748/#766 OPEN; `kb-arms` 127-handling "answered"; `mise run kb-build` "now three manifests behind") — all CONFIRMED above
- "no crons, no scheduled wakeups" — not independently checkable in this lane's scope (no `crontab`/launchd inspection performed); left UNVERIFIABLE

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under review; all commit/gate/issue verification.
- [kenn-io/agentsview](https://github.com/kenn-io/agentsview) — confirmed #1470/#1471 state for the "283 lost sessions" claim.

---

## Team-lead addendum — lane a2's one UNVERIFIED item is now SETTLED

Lane a2 left open: *"whether this tracked-file taplo failure is new or has been
silently present since Aug 12"* for `sources/groups/graphify-ecosystem.toml`.

**Answer: neither. It is a deliberate, documented exclusion, and the gate's green
is honest.** Measured by the team-lead at `bdd2cb17`, control-armed:

| probe | rc |
|---|---|
| `taplo fmt --check sources/groups/graphify-ecosystem.toml` | **1** |
| `taplo fmt --check currency.toml` (control — a file that should pass) | **0** |
| `taplo fmt --check $(git ls-files '*.toml')` | 1 |
| `hk run check --all --step taplo_format` | **PASSES, "85 files"** |

The arithmetic settles it: `git ls-files '*.toml'` = **88**; hk checks **85**;
`git ls-files 'sources/*.toml' 'sources/**/*.toml'` = **3**. Exactly the three
under `sources/` are excluded, by `hk.pkl`'s `proseExclude`/`baseExclude`, whose
own comment names `sources/**` as an authored-docs category the FORMATTERS must
not rewrite. That matches `agent-artifact-conventions.md`: *"Corpus content is
never rewritten to match a rename"* — a formatter reaching into `sources/**`
would falsify the provenance a manifest exists to guarantee.

So `lint` at `4cdd8bfb` reporting rc 0 was not hk caching and not a blind spot.

**The OTHER `lint` failure lane a2 found WAS real and is now fixed.** It traced
to `docs/dag/2026-09-12-session-review-round.toml`, this round's own orchestration
DAG, untracked at the time the lane ran the gate. It is committed at `bdd2cb17`,
taplo reformatted it during the pre-commit hooks, and `git diff HEAD` is clean.
Worth recording as a process lesson rather than a defect: **an untracked file
written by the orchestrator failed a gate that a review lane then attributed to
the branch under review.** The lane was right to flag it and right not to blame
the commits; the orchestrator was the contaminant.
