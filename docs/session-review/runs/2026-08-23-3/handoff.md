# Session handoff — 2026-08-23 (d) — the session-review round: eight lanes over the execution session; the PR is open and the corpus merges next

- **branch**: `claude-resync-2.1.241` — **12 commits ahead of `main` = `c4ea46a0998b`** (measured `git rev-list --count main..HEAD` this session; the -c handoff said 11, which was a miscount — the 12 commits are listed in §3). **Tree clean** (`git status --porcelain` empty). **PR [#469](https://github.com/ray-manaloto/knowledge-base/pull/469) is OPEN** at head `24d11e49c946` (verified via `gh pr view 469` this session).
- **HEAD**: `24d11e49c946` — review receipt exists for its parent `a7ae6d7be1c0` (`.agent/kb/review/receipt-a7ae6d7be1c0b9addeba0c5c69c56ff5db434b4c.json`); the delta since it is `graphify-out/memory/**` only, which is `review.EXEMPT_PATHS`, so the receipt covers HEAD.
- Gates on `24d11e49c946`: lint rc=0 · test rc=0 · brain-audit rc=0 · eval rc=0 · graph-size rc=0 · hk-test rc=0 — 6 passed, 0 failed. Artifact `.agent/kb/gates/gates-24d11e49c946e13a9ff1f610d3ab1ac7f8d3abd4.json`, re-read this session (its `dirty` field is `null` = could-not-ask, not a dirty tree).
- Gates on `a7ae6d7be1c0`: 6 passed, 0 failed. Artifact `.agent/kb/gates/gates-a7ae6d7be1c0b9addeba0c5c69c56ff5db434b4c.json` (flagged AMBIG by design — run had the work-memory uncommitted).
- This session was the session-review workflow over transcript `f74823ff` (the -c execution round). It wrote lane reports and this handoff; it changed no tracked file. **Review tally: 7 CONFIRMED · 4 REFUTED · 44 NOT TRIAGED · 0 unverified — the refuter DID run.** All 8 lanes returned, ALL PARTIAL (coverage limits are in each lane report under `.agent/kb/reports/agents/2026-08-23-session-review/`).
- Since the -c handoff was written: **graphify-labs' review on PR #469 POSTED at 2026-08-23T18:16:58Z** (COMMENTED — verified via `gh api …/pulls/469/reviews` this session), and its "Graphify Formal Verification" check-run completed `neutral` at 18:09:35Z. **CodeRabbit NEVER RAN on #469**: its comment says both "140 files, 40 over the limit of 100" AND insufficient usage credits — a green check meaning "never asked".
- No background tasks, agents, wakeups or crons left running.

## 1. THE NEXT TASK — Ray, verbatim (unchanged from -c)

> we need to make deep extraction and reflection of the graphify clone repo source the priority

The 26 staged chunks ARE that extraction. In order:

1. **Land PR #469.** Read the bot bodies FIRST: graphify-labs' review (posted 18:16:58Z) and Repowise's comment. CodeRabbit produced NO review (file-count skip + credits — see gotcha 2); do not wait for it, and do not read its green check as "found nothing". Then `mise run kb-land -- 469`.
2. **Merge the corpus — `mise run kb-graphify-semantic-corpus-merge -- <name> --partial` — and NEVER `run` again on this plan.** Two independent lane findings close the door on a third pass:
   - **Cap arithmetic (extraction-readiness, CONFIRMED):** durable spend is $41.777065 of the $63.00 cap (lane-read from `graphify-out/graphify-semantic-corpus-chunks/9e1adc3b7df53844cdc50f4a69f801ef329a47df0d96b7f2f229e5423b1797ad/spend-ledger.json` this session; $21.22 headroom), and a resume re-buys EVERY chunk at full price (the skip is downstream of the provider call — `python/src/kb_setup/graphify_semantic_corpus_run.py`). 26 × the measured $0.952/chunk ≈ $24.7 > $21.22: a third pass aborts around chunk ~22, never reaches 0026, publishes nothing, and burns ~$21.
   - **Content failures (extraction-readiness, NOT TRIAGED but lane-probed):** chunks 0012 and 0026 fail on `fragment-source-scope-mismatch`/`-coverage-mismatch` — a retry sends the same prompt over the same bytes. `17623a32`'s merge-time sanitisation is the right layer and already shipped.
3. Then `mise run kb-merge -- <chunk>` for the assembled extraction, `mise run kb-label`, `mise run kb-reflect` — the reflection half of Ray's sentence.
4. Then branch again (`kb-land` leaves you on `main`).

## 2. What shipped this branch (nothing new this session — the review session commits nothing)

| commit | |
|---|---|
| `b47a5a81badf` | Ray's 08-23 addendum verbatim + the tracked execution plan |
| `4e9f3fe785fc` | claude 2.1.241 resync; pre-spend Claude identity window closed |
| `34bc4557e737` | the -b round's work-memory |
| `8f285ce051d1` | U0 — package-manifest approver + 19 registrations across 8 sources |
| `e4d3d27a5aa3` | U8b0 — transform-then-lint gate for `.claude/workflows/*.js` |
| `17623a327323` | corpus — out-of-scope nodes sanitised on merge, recorded not refused |
| `5ae9f9ff928e` | lint unblocked, sources registered, plan execution log |
| `b9ce6e0a4a8b` | U4b — receipt from a drifted reviewer CLI refused |
| `0e088a04bd65` | antigravity-cli 1.1.17 → 1.1.19 |
| `83ccc44f38d1` | the two cold-lane findings that survived refutation |
| `a7ae6d7be1c0` | corpus provider evidence TRACKED, closing #317 |
| `24d11e49c946` | the -c round's work-memory |

## 3. Issues filed or touched this round

- Closed by the branch: **#317** (`a7ae6d7be1c0`).
- Amended: **#445** (agy settings measurements).
- Open and carried: #468, #467, #446, #397, #417, #409, #426, #429, #431, #411, #454, #460, #462, #464 (graphify-half), #450, #368, #455, #456, #457, #458, #465.
- **UNFILED gaps this review found that deserve numbers** (each is a NOT TRIAGED or CONFIRMED lane finding; file or explicitly decline): the CodeRabbit 100-file cap on corpus-chunk PRs · per-charge spend attribution (the ledger is `{total_usd,charges}` with no rows; $17.02 of $41.78 unattributable — lane-measured) · the proxy-name preflight refusal (`python/src/kb_setup/graphify_semantic_slice.py`, scrub excludes the 4 proxy names it refuses on) · a corpus `status` verb (a run with 2 failed chunks prints `execution_authorized: true`) · `_REDIRECT` entries for the corpus/slice verbs (#429 names the class) · the `mise run <task> | tail` rc-discard deny (36 of 39 such pipes this reviewed session discarded the rc, including all 3 `kb-ship` calls — lane-measured) · the premise-gate A-row trigger (see gotcha 1) · a resume `--repay` confirmation (18 chunks re-bought = $17.06, 41% of the round's spend — lane-measured) · `graphify_semantic_corpus_prototype.py` wire-or-delete.

## 4. NOT TRIAGED — 44 claims nobody confirmed or refuted; they are CLAIMS, not findings

The full JSON is in this run's synthesis inputs; lane reports carry the evidence. By lane, one line each: **bot-reviews**: the CodeRabbit file-cap skip recurs on every future corpus-chunk PR, unfiled. **pending-work**: the salvage/canonical-worktree-snapshot subsystem (7 modules + 4 tests + 18 memory notes, absent from main) still undecided (#368) · 255 refs outside refs/heads incl. 167 dotfiles mirrors, never audited · Ray's "backup directory = that branch + 4 worktrees" fact keeps getting lost from context-prep · the 2026-08-13 FREEZE gate (`~/.codex/archives/repo-recovery/20260813T195951Z/FREEZE-STATUS.md`) was never formally lifted · gh-stack skill branch needs adaptation not merge · two branches explicitly do-NOT-merge · 3 stale remote-only branches deletable · 188-vs-93 file counts never reconciled · 2 stashes droppable. **extraction-readiness**: spend unattributable (above) · proxy refusal (above) · no run-status verb (above) · kb-build's CURRENT blocker is a ONE-ENTRY `ExpectedPartialExtraction` fix for `sources/deer-flow/.agent/skills/blocking-io-guard/templates/anchor.template.py` (warning says line 1, real SyntaxError line 23; #409's inventory counts are stale — partial=5, metadata=13) · #429's corpus verbs unguarded (16h leash bypassable via bare `uv run`) · chunks 0012/0026 fail on content · #417 re-measures to 5 of 73 skip manifests · #464 graphify-half nit carried · prototype module unreachable · #460 stays live (231 issues all one author = accident of authorship) · line anchors for `_receipt_reasons`/`_runtime_reasons` drifted a THIRD time — carry the `git grep -n 'def _receipt_reasons\|def _runtime_reasons'` command, never line numbers. **telemetry**: 7 cache-cold ≥538KB xhigh continuations · request/response id spaces disjoint (per-request cost unattributable by schema) · 7 xhigh turns after <50-token end_turns · 18/32 thread-start signals disagree. **circles**: 56/264 Bash calls were hand-rolled polling (Monitor fetched, never called) · 3 of 4 lanes went idle without reporting, third round running · five OWED items re-typed across 3 handoffs with no status change · kb-ship refused twice serially (wants `--preflight`) · directive item 2 dropped for 7h14m then re-issued · bare asks refused pending explainers, twice · typos-in-hk.pkl third recurrence · the 1,636-line plan doc took 19 tool calls to read (ingest `docs/plans/` or index it) · `python3 … || uv run python` is denied whole. **forgotten**: L4/L7 are literal unanswered Ray questions (AskUserQuestion owed) · U3 is 2/8 bumps and U2 unbuilt · L1's telemetry lines never added to `.codex/config.toml` · U5 (#446, yuting0624 manifest) undone · codex `build = skip` never lifted though U0 built the machinery (`sources/codex.manifest` vs `8f285ce0`). **tooling-gap**: no namespaces/diagnose-failures verbs (hand-rolled `for d in */` loops again) · heredoc pathlib edits where Edit works · `kb-arms` spec hand-guessed 3× (wants `--init`) · a relative `cd` wasted a round-trip · a hand-written `while true` ledger poll. **contradicted**: `sources/codex.manifest` skip-reason contradicts `8f285ce0`.

## 5. GOTCHAS — what misled someone, this round and standing

**New this round (from the lanes and the refuter — the refuted ones are evidence about PROBES):**

1. **The premise-gate never fired all round (CONFIRMED, cost rank 1 — 6h00m of an 8h22m session).** The fable-orchestrator premise-gate script escalates only on 'E' rows; the claim that broke (U8b0 decision 9) was correctly written as an 'A' (architect assumption) row and waved through; zero of five specs had an E row. Remedy is one regex: add 'A' to the trigger at `~/.claude/plugins/cache/fable-orchestrator/fable-orchestrator/1.21.0/scripts/premise-gate.sh` line ~174, and route every implementer spec through premise-verifier (1 of 5 did this round).
2. **`/pulls/N/reviews` under-reports bot activity (REFUTED probe).** graphify-labs was declared missing on #469 while its check-run had already completed 64s before the observation, and its review posted at 13m50s — inside the 3–29 min historical band. CodeRabbit leaves an issue COMMENT, never a review. Before declaring a bot silent: check `…/commits/<sha>/check-runs` AND issue comments, and wait past 30 min.
3. **A bounded read of where a conflict is RAISED cannot see where it was RESOLVED (REFUTED probe).** An 18-line `sed -n` of the plan doc's "Second sweep" produced "never put to Ray"; the settled-decisions table 1,130 lines earlier in the SAME file says "Every branch above was put to Ray and answered". Read `docs/plans/2026-08-23-directive-execution-plan.md` decisions table (~lines 52-79) before citing its later sections. Residual true kernel: U4 proper was genuinely never asked; U4/U5 are undone.
4. **A token-spelling bound inflated "10 of 12 lost" (REFUTED probe).** Nine grep tokens covered only 6 of the 12 L-items, so the number was arithmetically unreachable; 4 of the untested 6 were present in the files searched. Corrected residue: at most 5 (L4, L5, L6, L7, L12) lack a surfacing route. Also: an unquoted zsh `$H` does NOT word-split — 28 uniform "No such file" negatives from one broken probe (MEMORY.md already records this class).
5. **"Zero cleanup in 3 audits" was a bounded enumeration (REFUTED probe).** An unbounded `find` surfaced a FOURTH pending-work lane in gitignored `.agent/`; its headline item HAD been landed (PR #463); and the non-deletion is COMPLIANCE with the unlifted freeze gate + Ray's backup-directory ruling, not neglect. Do not delete worktrees/branches until #368 is decided and the freeze is recorded as lifted.
6. **36 of 39 `mise run <task> … | tail/head` pipes discarded the rc (CONFIRMED)** — including all 3 `kb-ship` gate decisions — while `${pipestatus[1]}` was used correctly twice in the same session. Use `mise run kb-check` / `kb-gates`, or `${pipestatus[1]}`.
7. **A resume re-buys every completed chunk (CONFIRMED, $17.06 = 41% of the round's spend)** — and the behaviour was documented in `graphify_semantic_corpus_authority.py` all along. Never `run` again on this plan (§1).
8. **The orchestrator thread resends full history every turn (CONFIRMED):** 337/1019 in-scope requests >1MB, 58% of 918MB total request bytes. No mechanical fix known; keep long rounds short and clear early.
9. **Two "only memory/ is committed" docs are now FALSE (CONFIRMED):** `CLAUDE.md` (graphify-out row) and `.claude/rules/do-not.md` item 5 vs `a7ae6d7be1c0` tracking 347 files under `graphify-out/` (lane-measured `git ls-files`). Fix both in the next docs commit. Same class: `python/src/kb_setup/gates.py` comment and `.claude/rules/verify-before-advancing.md` both say "four" GATE_TASKS; the tuple has six.

**Standing traps, carried until retired (from -a/-b/-c; none retired this round):** `mise run` redacts SHAs/branches/PR numbers — copy from `uv run kb-setup session-state` · bare `python3` DENIED (and the `|| uv run python` fallback does NOT exempt the command — the whole string is rejected) · `timeout`/`gtimeout` absent on macOS + DENIED · blanket `git add` DENIED · hand-chained ruff/ty DENIED · `rumdl fmt` turns a line-leading issue ref into a heading — join it to the previous line · typos reads `hk.pkl`; describe a flagged token, never spell it · `kb-query` can return TRUNCATED off-corpus results for repo-internal questions — use `graphify explain` / `--prose --idf` · the planner digests its own files (`graphify_semantic_corpus.py`, run/slice/adapter) — any edit = re-record; the merge module is OUTSIDE the digests on purpose (the -c "digest trap") · `record --accept` rmtree's the plan dir a run reads · `kb-artifacts` REWRITES `graph.json` — serialize against `kb-build` · `git worktree remove --force` deletes gitignored `.agent/` sole-copy evidence — copy first · bots edit comments in place; read bodies BEFORE the first `kb-ship` · `kb-gates` concurrent with an agy session reports dirty on every row · `find -newermt "-N min"` silently empty on macOS · zsh aborts a compound command on a failed glob · probes never bare-cd (the Bash cwd persists; it cost a round-trip again this round) · lanes write to `.agent/kb/reports/agents/` ROOT by default (#431) — this round's workaround (a dated subdir) worked; keep passing a dated `reportDir` · subagents: report to a FILE first, then reply, and check the agent's toolset has Write (#432).

## 6. OWED and not done

1. Land PR #469, then the partial merge + label + reflect chain (§1).
2. The doc fixes gotcha 9 names (CLAUDE.md + do-not.md carve-out; gates "four"→six in `gates.py` and `verify-before-advancing.md`) — fold into the next docs commit on a fresh branch.
3. The UNFILED list in §3 — file or decline each.
4. `kb-build` is RED: the one-entry `ExpectedPartialExtraction` fix for the deer-flow template (§4), then re-run `mise run kb-build`.
5. Lift `codex`'s `build = skip` in `sources/codex.manifest` (its stated reason was closed by `8f285ce0`) or re-justify.
6. #468 (clear-prep rewrite — duplicate `.agents/` copy FIRST) · #467 (OpenRouter fallback) · #446/U5 (yuting0624 manifest + currency row) · U3's remaining 6 bumps through U2 once built · remaining plan units U1, U2, U3, U4, U5, U6 (blocked on Ray, #450), U7, U8, U9, U10, U11.
7. AskUserQuestion to Ray: L4 (graphify as agent memory — final output or intermediate steps?) and L7 (why not `mise ls-remote antigravity-cli`?) — literal unanswered questions of his; and the freeze-gate/one-sentence-lift for #368.
8. `docs/currency/` docs drift (the claude-code goal/hooks/skills doc pages changed; baseline deliberately not rolled) — re-read, re-ingest, then `kb-setup currency docs-reviewed --tool claude-code`.
9. Worktree + branch hygiene — BLOCKED behind #368 decision + freeze lift (gotcha 5); when unblocked, copy sole-copy `.agent/` artifacts out first.
10. Promote load-bearing `.agent/` reports to `docs/research/` (this round adds the 8 lane reports + 123 refuter files under `.agent/kb/reports/agents/2026-08-23-session-review/` — promote at least the synthesis-cited ones).
11. `kb-session-reflect` re-run; the `kb-session-review-archive → lint` close wrapper; #462 (bot read/reply task); #454 (MEMORY.md generator); #431 remedy 3 (run-scoped lane filenames); #411's real gap is now SPEND attribution (see §3 unfiled), model/effort being recorded.
12. Long tail carried unchanged from -a/-b (state unknown unless noted): the vendored-docs hazard chunk `sources/extractions/dotfiles-secrets-hazards.json` (absent) · #442's unchecked-stderr shape · the #391 musl comment · `kb-validate-chunks` bounds-check + `--reanchor` · the httpx2 disposition · the heredoc `.read_text()`/`.write_text()` DENY (fold into #239) · PR #410's unswept bot reviews · the extraction-readiness brief's blind spot on unmerged branches · the handoff-lead reconcile gap (unfiled) · `own_transcript` mtime fallback (unfiled) · piped-rc (now 5th round named — see gotcha 6's deny proposal) · `kb-distill`'s one candidate · wrappers for `kb-gates → receipt → ship` and `remember → reflect` · CLAUDE.md "499 MB" figure and `do-not.md` "pinned 0.9.31" label · the `md-size-budgets.md`/`md_budget.py` AGENTS.md contradiction · `cli.py` usage strings from the dispatch table (#429/#412).

## 7. RECONCILIATION — previous handoffs, item by item

### 7a. `.agent/plans/session-2026-08-23-c.md`

- §1.1 land PR #469 after reading bot bodies — **CARRIED** (§1.1 here; amended: graphify-labs POSTED, CodeRabbit NEVER RAN — gotcha 2).
- §1.2 merge the corpus via `chunks.assemble`; 0012/0026 through `17623a32`'s sanitisation — **CARRIED, amended**: `--partial`, and NEVER `run` again (§1.2 cap arithmetic).
- §1.3 `kb-label` then `kb-reflect` — **CARRIED** (§1.3).
- §5 #468 — **CARRIED** (owed 6). §5 #467 — **CARRIED** (owed 6). §5 #445 amendments — **DONE as an issue amendment** last round; the underlying config work **CARRIED** (U4/U5).
- §5 kb-build RED on the deer-flow template — **CARRIED, sharpened**: the review located the exact fix (owed 4; real SyntaxError line 23, warning line 1).
- §5 lift codex `build = skip` — **CARRIED** (owed 5; re-confirmed against the live manifest this session by the contradicted lane).
- §5 remaining units U1–U11, U6 blocked on Ray — **CARRIED** (owed 6/7).
- §5 docs/currency drift — **CARRIED** (owed 8).
- §6 gotcha 1, the digest trap — **CARRIED** (standing traps): `graphify-out/graphify-semantic-corpus/execution-config.json` digests seven code files including `semantic_slice_sha256`; fix scope-mismatches in the merge module, which is outside the digests.
- §6 gotchas 2–9 (severe-but-unreachable findings · resume re-buys · clear-prep invocability · rumdl `#NNN` · typos-in-hk.pkl · pgrep control arm · idle lanes · standing denies) — **ALL CARRIED** into §5 here; the resume re-buy is now quantified ($17.06/41%) and the idle-lanes failure is confirmed as a third consecutive round.
- §7 ship — **DONE** (PR #469 opened in the reviewed session, third `kb-ship` attempt). §7 land — **CARRIED** (§1.1).
- §7 docs drift / plan units / U6 / #462 / #454 / #431r3 / #417 register — **ALL CARRIED** (owed 6, 8, 11; #417 re-measured to 5 of 73 skip manifests this session).
- §7 promote `.agent/` reports — **CARRIED**, scope grown (owed 10).
- §7 worktree + branch hygiene — **CARRIED, re-scoped**: blocked behind #368 + the freeze gate (gotcha 5), not merely untouched.
- §7 `kb-session-reflect` re-run — **CARRIED** (owed 11).
- §7b verify says authorized — **DONE and still true, but** `verify` verifies the PLAN; there is no run-status verb (§3 unfiled) and the run outcome is 24 complete / 2 content-failed.
- §7b editing `_MAX_TOTAL_COST_USD` at `python/src/kb_setup/graphify_semantic_corpus.py:107` — **DROPPED stays DROPPED**, superseded harder: no third pass at all (§1.2), so the cap never needs to move.
- §7b cache-namespace re-plan trap — **CARRIED** (standing traps).
- §7b `kb-handoff-check` reconcile gate — **DONE again for this handoff** (run before ship).
- §7b stale remote-tracking refs — **DROPPED**, closed two rounds ago; cited only to close the citation.
- §7b `kb-session-reflect` + archive-close wrapper — **CARRIED** (owed 11).
- §7b #464 graphify-half message nit — **CARRIED** (owed 11 / §3 unfiled adjacency).
- §7b proxy refusal unfiled + `cli.py` usage strings — **CARRIED, still unfiled** (§3 unfiled; owed 12).

### 7b. `.agent/plans/session-2026-08-23-b.md` — items not already resolved via 7a

- §1 start the corpus run + early-stop cap measurement — **DONE** in the -c round (26/26 staged, $0.948–0.952/chunk measured, cap untouched, 0 `record --accept`).
- §4 docs drift — **CARRIED** (owed 8). §4 gates/review/receipt/ship/land — gates/review/receipt/ship **DONE**, land **CARRIED**. §4 eleven units — **CARRIED** except U0 (`8f285ce0`) and U4b (`b9ce6e0a`) **DONE**. §4 U6 blocked on Ray — **CARRIED**.
- §5 gotchas (rumdl · typos "mis-executes" · guard-breaks-fixtures · record-fixes-tests · kb-check deny · report-to-file-first + toolset check · standing traps incl. kb-query TRUNCATED) — **ALL CARRIED** (standing traps, §5).
- §6 concurrency rules (run disjoint · `kb-artifacts` vs `kb-build` serialization · artifacts safe with kb-build RED · no re-record mid-run) — **CARRIED**; the "no re-record while a run is in flight" clause is now moot (no more runs) but the serialization rules still bind the merge/label/artifacts chain.
- §7 the long carried-unchanged-from-e/f list — **CARRIED wholesale** (owed 12), no item moved this round; state unknown for #442/#446/#391/httpx2 (not re-checked since -b).
- §7 #454 (MEMORY.md 24,225 B / 105 lines re-measured in -b) — **CARRIED**, figure now inherited and unverified (not re-measured this session).
- §7 #431 remedy 3 — **CARRIED**; this round's dated `reportDir` workaround held (no overwrite).
- §7 cap re-derivation — **DONE/superseded** (measured in the -c run; and §1.2 now caps out a third pass entirely).
- §7 2026-08-240/2.1.241 currency rows — 2.1.241 **DONE** (-b, generator-written); 2.1.240 **DROPPED** (retroactive row would be fabricated).

### 7c. `.agent/plans/session-2026-08-23-a.md` — items not already resolved via 7a/7b

- §1 Ray's orchestration directive item 1 (session-review visual artifacts, lanes, telemetry-driven self-improvement, clear-prep conversion) — **CARRIED** under epics #435/#436; the telemetry lane itself is built and ran this session; the remainder (visual artifacts, LSP/tree-sitter, universal loggers, profilers, self-heal) is unstarted. The L-item ledger: L2/L3 live in #468 (**CARRIED**); L9 = U5/#446 (**CARRIED**); L11 discharged in the plan doc (**DONE**); L1's config-toml half, L4, L5, L6, L7, L12 — **CARRIED** (owed 7 covers L4/L7; the rest have no surfacing route — this sentence is now that route).
- §1 item 2 (antigravity) — antigravity-cli 1.1.19 **DONE** (`0e088a04`); plugin-usage review **PARTIALLY DONE** (measurements amended onto #445); U4/#445 reconfig and U5/#446 manifest — **CARRIED**.
- §1b the resync chain steps 1–7 — **DONE** across -b/-c (constants, manifest, currency row, ninth record, window closed in `4e9f3fe785fc`, review+receipt+ship); land — **CARRIED**.
- §6 worktree hygiene with copy step — **CARRIED, re-scoped** behind #368 + freeze (gotcha 5).
- §6 #462 reply-side · #454 generator · #431r3 · kb-session-reflect · promote reports · proxy refusal · cli.py usage — **ALL CARRIED** (owed 3, 10, 11, 12).
- §6 cap re-derivation — **DONE/superseded** (7b).
- §6 #464 comment fix — **DONE** (-b); message-nit graphify half — **CARRIED**.
- §6 doc drift (CLAUDE.md 499 MB · do-not.md 0.9.31 · md-size-budgets/md_budget AGENTS.md contradiction · #417 register) — **CARRIED** (owed 12), plus the NEW gotcha-9 contradictions this review added.
- §6 vendored-docs hazard chunk and the rest of the -e/-f tail — **CARRIED** (owed 12).
- §5 gotchas 1–18 — gotcha 1 (plan→preflight window) **DONE** (`4e9f3fe785fc`); gotchas 2–17 and the §5.18 standing-trap list — **ALL CARRIED** (standing traps, §5 here); §5.15/#431 root-overwrite — **CARRIED**, mitigated this round by the dated subdir.
- §4's 23 NOT TRIAGED — **CARRIED**; several were re-derived by this review's lanes (cap arithmetic, proxy refusal, #417 scope, cli.py usage, gh-stack, stashes, prototype-adjacent gaps) and are now in §4 here with fresher evidence. The running NOT TRIAGED debt is 41 + 25 + 23 + 44 across four rounds (44 measured this session; the rest inherited).
