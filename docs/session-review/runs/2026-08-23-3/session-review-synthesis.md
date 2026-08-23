# Session-review synthesis — 2026-08-23 round (PR #469 window)

One ranked review over eight lanes. Ranked by COST OF LEAVING IT UNFIXED, not by
count. Every figure below is INHERITED from a lane report; this synthesis ran no
probes of its own. Where a lane carried a control arm it is noted; where it did
not, the number travels unarmed and is labelled.

## Claim accounting — read this before the ranking

| status | count | meaning |
|---|---|---|
| CONFIRMED (cross-checked, survived) | 7 | verifier ran the claim's own control arm or an independent route |
| REFUTED (cross-checked, failed) | 4 | kept in this report — each is evidence about a probe class |
| NOT TRIAGED (verifier budget ran out) | 44 | nobody looked; **not** confirmed, **not** refuted |
| UNVERIFIED (verifier did not return) | 0 | — |

The verifier DID run (4 refutations exist), but it reached only **11 of 55
claims (20%)**. Of the 11 it reached, **4 were refuted — a 36% refutation
rate**. Applied to the 44 untriaged claims, the honest expectation is that
roughly **14–16 of them are wrong in whole or in part**. Every NOT TRIAGED item
below is therefore a LEAD, not a finding, no matter how confident its prose
reads.

Dedup note: the 44 untriaged claims contain at least three restatements across
lanes — codex `build = skip` appears twice (contradicted rank-3 and forgotten
rank-7), U5/#446-undone appears three times (refuted #12's residual kernel,
the forgotten lane, and via U4/U5 in the directive-drop claim), and the corpus
spend-attribution items form one cluster. Counted once each below.

---

## The ranking

### Tier 1 — the circles: leave these unfixed and the next round pays the same bill

**1. [CONFIRMED] The premise-gate never fires on the row type sessions actually
write.** Decision 9 (U8b0) was re-litigated three times and consumed **6h00m of
an 8h22m session** because `premise-gate.sh` escalates to mandatory
premise-verification only on `E` rows — and the round's five specs contained
**zero** E rows. The claim that blew up was correctly written down as an `A`
(architect assumption) row, i.e. the contract's own admission of an unchecked
claim, and waved through. Control arm: the row-type census returned A/I/L rows
from the same files, so the zero-E result discriminates.
*Cost of leaving it: ~72% of a session, per round, whenever an A row is load-bearing.*
**Caveat this synthesis adds:** the specced remedy edits
`~/.claude/plugins/cache/fable-orchestrator/.../premise-gate.sh` — a file
OUTSIDE the project, which `do-not.md` item 11 forbids touching. The one-regex
fix is right; its ROUTE is not settled here. It must go upstream to the
fable-orchestrator plugin (or a project-scoped override if the plugin supports
one), not into the cache. The secondary remedy — route every implementer spec
through `premise-verifier` (1 of 5 this round did) — is project-local and can
land now.

**2. [CONFIRMED ×2, plus 4 untriaged siblings] The corpus spend circle.** One
cluster, one scheduling decision:
- **A third pass is arithmetically dead** [CONFIRMED]: $41.78 of the $63 cap is
  spent, a resume re-buys EVERY chunk at full price (skip is downstream of the
  provider call; no cache read at the pin), and 26 × $0.952 ≈ $24.7 >
  $21.22 headroom. It would abort near chunk ~22, retry 0012, never reach 0026,
  and publish nothing for ~$21. Two independent routes to the per-chunk rate
  agree (ledger vs artifact sum).
- **This round already paid the repay tax** [CONFIRMED]: 18 chunks re-bought,
  **$17.06 of $41.78 (41%) was work done twice**, and the behaviour was
  documented in `graphify_semantic_corpus_authority.py` the whole time — a
  docs-only fix has already been tried and failed.
- Untriaged siblings, unverified: the ledger cannot attribute **$17.02 / 19 of
  45 charges** to any chunk or pass (no per-charge rows); there is **no verb
  that reports how a RUN went** (`verify` rehashes the PLAN and prints
  `execution_authorized: true` over a 24/2 failure outcome); the two failed
  chunks (0012, 0026) fail on CONTENT (`fragment-source-*-mismatch`), so a
  retry re-sends the same prompt over the same bytes.
*Action for THIS round: do NOT run a third pass. Go straight to
`mise run kb-graphify-semantic-corpus-merge -- <name> --partial`.*
**Caveat:** the extraction-readiness lane states plainly it did NOT read the
merge module's scope-sanitisation code (commit 17623a32) — the very code the
`--partial` recommendation relies on to bin 0012/0026 correctly. Verify that
path (a read, not a run) before scheduling the merge.
*Condition on the arithmetic: it holds at cap = $63.00. Ray has previously
ruled the cap movable (`graphify_semantic_corpus.py:107`); if the cap moves,
finding 2a's conclusion moves with it — the repay tax (2b) does not.*

**3. [CONFIRMED] 36 of 39 piped gate invocations discarded their exit code —
including all 3 `mise run kb-ship` calls.** The gate that decides whether the
branch is safe to push was read through `| tail -25`. One more call captured
the WRONG process's rc via bare `$?` in a zsh pipe. Control arm: the same
session used `${pipestatus[1]}` correctly twice, so the right form was known
and available — this is the **third measured instance** of this repo's own
finding that warnings score ~0 and denies score ~100 (0/19 vs 62→0, 35 pipes,
then 12 more). The remedy is an extension to the EXISTING `kb_setup.hook_guard`
family (same shape as `check_first`), not new machinery.
*Cost of leaving it: every future ship decision rests on an unread rc until the
deny lands.*

**4. [CONFIRMED] Two governing docs state a false invariant that a compliant
agent would enforce destructively.** `CLAUDE.md:169` and `do-not.md` item 5
both say only `graphify-out/memory/` is committed; since `a7ae6d7b` (Ray's #317
ruling) **347 files** are tracked under `graphify-out/`, 106 of them the
paid-for corpus chunks. An agent following do-not.md #5 to the letter would
treat the chunk tree as a violation — the exact "machine-enforced against files
its owner never governed" failure this repo has already lived through once.
Control arm carried: the probe distinguishes the false "only" wording from the
true memory/-is-committed half.
*Fix is two sentences; it must land in the commit that lands this round's PR.*

**5. [NOT TRIAGED — but corroborated by the session's own words] Three of four
lanes committed work and went idle without delivering a report, third
consecutive round.** The session itself said "the #432 pattern again, third
round running" at 12:44. Three rounds of prose in
`agent-report-persistence.md` have scored zero. The proposed `kb-lane-check`
(branch commits with no lane artifact, wired into `kb-ship` beside the receipt
gate) fixes an existing gate rather than adding a new surface. Untriaged: the
timestamps bounding "idle" come from dispatch-to-report gaps, and the circles
lane admits the subagent transcripts were out of scope — duration may
overstate.

### Tier 2 — structural risks that recur but did not burn this round

**6. [CONFIRMED] The orchestrator resends full history every turn: 58% of all
in-scope request bytes (534.8MB of 918.2MB) are >1MB requests; top requests are
2.23–2.24MB with nmsgs climbing 1205→1216.** Confirmed with a scope-match
control arm. No mechanical fix identified by the lane; this is an
INVESTIGATION item (prompt-caching / context strategy for the long
orchestrator thread), not a patch. Ranked below the circles because its remedy
is unknown, not because its cost is small.

**7. [NOT TRIAGED] CodeRabbit never ran on #469 (140 files > its 100 cap) and
every future PR carrying a fresh corpus-chunk commit will trip the same cap.
No issue tracks it.** Partially corroborated in passing by the graphify-labs
refuter, which also read the skip comment — with one caveat the original lane
missed: the same comment ALSO cites exhausted usage credits, so the file cap is
not proven to be the sole cause. The green check means "never asked", the
worst-documented state in this repo's own taxonomy. Remedy is to fix EXISTING
code: teach `kb_setup.pr`'s advisory table to detect the skip and say which
reviewers actually ran, and/or land corpus-chunk trees in their own PRs.

**8. [NOT TRIAGED] #429 is live: the hook has no redirect for the corpus/slice
verbs, so the bare `uv run kb-setup graphify-semantic-corpus run` bypasses the
16h wall-clock leash that only the mise task carries.** The lane's own probe
armed both directions (`decide` fires on `graphify extract .`, abstains on
`path`). The reviewing lane typed the bare form itself and nothing objected.
Fix the existing `_REDIRECT` table.

**9. [NOT TRIAGED] The corpus run refuses to START on any host carrying
HTTP(S)_PROXY/ALL_PROXY/NO_PROXY, and the #334 scrubber deliberately excludes
exactly those four names** — a refusal with no tool-side remedy, on the run Ray
has named the next priority. Fails safe (no spend), needs one hand `env -u`.
Carried in the handoff as unfiled; still unfiled.

**10. [REFUTED claim, LIVE kernel] U4 (#445) and U5 (#446) are undone, and
codex's `build = skip` contradicts the machinery U0 shipped.** The refuted
finding #12 claimed the scope conflict was "never put to Ray" — false (asked
09:06Z, answered 09:09Z, settled-decisions table at plan doc :52–78; the probe
read only the 18 lines where the conflict was RAISED). What survives the
refutation, confirmed by the refuter's own 28-call AskUserQuestion census:
"U4 " scores 0 hits (never asked as itself), U4/U5 are absent from the commit
table, and two untriaged findings show `sources/codex.manifest:49-50` still
cites a skip reason that commit 8f285ce0 made false. The undone-ness is real;
the steamrolled-conflict story is not.

### Tier 3 — process leads worth one action each (untriaged unless marked)

**11. [NOT TRIAGED] Five OWED items re-typed into all three handoffs,
untouched** (kb-session-reflect, worktrees, #417, #431, #429). Remedy fixes an
existing task: `kb-handoff-check` fails at N=3 consecutive CARRIED with no
status change.

**12. [NOT TRIAGED] Ray's directive item 2 (antigravity) was probed for 90
seconds, dropped, and re-issued verbatim by Ray 7h14m later**; an unplanned
U4b was invented mid-round while planned U4/U5 never started. Remedy is the
directive-to-plan reconcile in the existing `kb-handoff-check`.

**13. [NOT TRIAGED] 21% of Bash calls were hand-rolled polling (56/264,
including two `while true` loops) while the Monitor tool sat fetched and
unused.** Per the brief's own rule this synthesis does NOT endorse the proposed
`kb-watch-task` wrapper: **Monitor is the existing tool that already does
this** — the fix is the orchestration skill stating "after ToolSearch selects
Monitor, call Monitor", plus deleting the two while-true loops
(zero-bash-logic violation).

**14. [NOT TRIAGED] The spend ledger + no-status-verb + kb-arms-skeleton +
namespaces cluster.** Four proposals to extend `kb_setup` verbs. The status
verb is the cheapest honest one: `verify_staged_chunk` already performs every
check; it is unwired, not unbuilt. `kb-arms -- --init` closes a
guess-refuse-guess loop with 11 prior recorded occurrences.

**15. [CONFIRMED] gates.py:419 and verify-before-advancing.md:22 both say
GATE_TASKS has four entries; it has six.** Bookkeeping, but the same gap
reopened once already — cite `len(GATE_TASKS)` or fix both strings.

### Tier 4 — bookkeeping, hygiene, and single-fact fixes (visibly below the circles)

All NOT TRIAGED unless marked. One line each; none of these costs a round if
deferred, all cost a sentence now.

- **kb-build's current blocker is claimed to be ONE `ExpectedPartialExtraction`
  entry** (deer-flow template, real SyntaxError at :23, warning says :1) — if
  true, the cheapest unblock in the report; verify its arm before trusting.
- **kb-ship refuses serially** (two refusals, 27m36s) while kb-gates already
  demonstrates evaluate-everything; give ship a preflight that prints all
  failures at once.
- **`python3 … || uv run python …` is denied whole**, twice in one round by two
  agents; one clause in the existing deny message.
- **Three heredoc string-substitution edits on tracked tests** where Edit (used
  16× the same session) was the tool; extend check_first scope.
- **Bare-cd round-trip wasted** — discipline gap already in MEMORY, no new gate.
- **typos re-broke on its own exclusion comment** in hk.pkl, third recurrence of
  the #413 class; move flagged-token annotations out of files typos reads.
- **Two AskUserQuestions asked bare, refused, re-asked with explainers** — the
  skill should ship decision-reversal asks WITH their explainer.
- **Plan-doc navigation cost 19 tool calls / 10 blind sed guesses** — ingest
  docs/plans/** or give the plan an anchored unit index.
- **Pending-work hygiene** (all untriaged, all owned by OPEN #368 — the fix is
  to ACT on #368, not file a fourth audit, and the refuted finding #30 proves
  the freeze gate + Ray's backup-directory designation must be resolved with
  Ray FIRST): 255 refs outside refs/heads never enumerated by any audit; the
  salvage/canonical-worktree-snapshot subsystem (needs a human decision);
  gh-stack skill needs adaptation not merge; two do-NOT-merge branches; three
  stale remote branches; two droppable stashes; the 188-vs-93 count never
  reconciled; the unlifted 2026-08-13 FREEZE-STATUS needs one tracked sentence.
- **Telemetry anomalies not root-caused**: 18/32 null-prev vs cc_prev_req
  disagreement; 7 cache-cold >538KB continuations; 7 xhigh-after-trivial turns
  (0.7% — below any actionable floor this round, flagged for recurrence);
  request→response id spaces are disjoint by schema, so the brief's
  effort-vs-own-response metric is uncomputable as specified.
- **L-item residue, corrected by the refuter: at most 5 of 12** (L4, L5, L6,
  L7, L12) lack a surfacing route — not 10. L4 and L7 are literal unanswered
  questions from Ray; per clarify-before-acting they go to AskUserQuestion.
  L1's telemetry-lines half and U3's 6 remaining bumps are also open.
- **graphify_semantic_corpus_prototype.py**: 465 lines no operator path can
  invoke, importing graphify privates — wire it or retire it under
  tool-currency-and-native-first; unfiled.
- **Prompt-injection (#460)**: the all-231-issues scan found nothing hostile,
  but the lane itself says that is an accident of single-author authorship, not
  evidence the control is unneeded. Ranked low ONLY while authorship stays
  single-account; re-rank if that changes.
- **Receipt-verifier line anchors drifted a third time** — the lane's remedy is
  right and costs nothing: carry the `git grep -n 'def _receipt_reasons'`
  command in briefs, never line numbers.

---

## Refuted findings — kept as evidence about the probes

All four refutations are the SAME defect class: a bounded probe reported its
bound as the world. This is the report's most transferable lesson.

| # | claim | refuted by | probe-defect class |
|---|---|---|---|
| R1 | "The option-1 scope conflict was never put to Ray; the session proceeded on an unconfirmed assumption" | The finding's own cited file, 1,130 lines earlier: settled-decisions table (rows 14/16/17) + "The frontier is empty. Every branch above was put to Ray and answered"; transcript shows the ask at 09:06:55Z, Ray's answer 09:09:24Z, U0 re-asked and WIDENED at 14:17:49Z | line-range bound — an 18-line read of the RAISING site in a 1,636-line file can only ever return "raised, unresolved" |
| R2 | "graphify-labs has not posted on PR #469" | Review posted 18:16:58Z, inside the finding's own 3–29 min band; AND a graphify-labs check run had COMPLETED at 18:09:35Z, 64s before the observation, on an endpoint the probe never read | time bound + route bound — `/pulls/N/reviews` under-reports bot activity (CodeRabbit similarly left only an issue comment) |
| R3 | "THREE audits, zero cleanup, identical inventory across 5+ days" | A FOURTH audit existed in gitignored `.agent/`; its headline item WAS actioned (landed as PR #463, 2026-08-23); inventories differ (24 vs 25 branches; main moved); residual non-deletion is COMPLIANCE with the unlifted freeze + Ray's backup-directory designation, not neglect | scope bound (tracked-files-only enumeration) + inherited framing; free defect: the prior audits contradict each other in both directions |
| R4 | "10 of 12 LOST L-items are unsurfaced by any handoff OWED section" | The nine grep tokens covered only 6 of the 12 items, so 10/12 was arithmetically unreachable from the probe; four "missing" items are present verbatim in the searched files; kb-resume reads directives, not just OWED — corrected residue ≤5 of 12 | token-spelling bound; the refuter's own first attempt also broke (unquoted zsh scalar → uniform false negative), caught by its control arm |

Note what R1's refuter contributed beyond the refutation: its AskUserQuestion
census is the positive evidence behind ranked item 10 (U4 never asked as
itself, L4/L7 never asked) — a refutation that armed a different finding.

---

## Lane coverage — every lane was PARTIAL; what each never reached

An interrupted lane reads exactly like a finished one. It is not. Eight of
eight lanes were partial; zero lanes failed to return.

| lane | the gap that most limits its findings |
|---|---|
| circles | `.agent/telemetry/` never opened → every duration is transcript-timestamp arithmetic; subagent lane transcripts don't exist in scope → "idle lane" durations are dispatch-to-report bounds that may overstate; the five lane reports themselves were not read |
| forgotten | the working-session transcripts behind handoffs a/b/c are out of scope BY CONSTRUCTION — anything Ray said there that never reached a tracked artifact is invisible; #435/#436 full bodies unread, so some L-items may already be captured there |
| contradicted | the transcript was never read directly; the 1,636-line plan only grepped for two terms; hk.pkl not read line-by-line; currency.toml's codex entry located but unread |
| tooling-gap | codex/agy invocations live in subagent transcripts outside scope — the lane can say nothing about them; telemetry sink out of scope |
| bot-reviews | graphify-labs on #469 was genuinely indeterminate at report time (later resolved benign by the refuter); #466's other graphify-labs findings not re-verified line-by-line |
| pending-work | 164 of 167 dotfiles-mirror salvage refs unchecked; refs/preserved and salvage-bundle content never diffed; the reflog gap (#368 names it) remains open in this audit too |
| extraction-readiness | **ZERO mutation arms run**; the merge scope-sanitisation code (17623a32) that the round's top scheduling recommendation depends on is UNREAD; adapter (1,058 lines) and record (690 lines) modules entirely unread; "assemble is unblocked by the red kb-build" is inference, not observation; corpus fragments verified structurally only, never semantically |
| telemetry | cannot attribute any request to a lane (no field carries a lane label; parent_session_id == session_id on every sample); findings 4 and 5 not root-caused; terminal-response count is a bounded estimate |

---

## What this synthesis itself got wrong or could not settle

1. **It verified nothing.** Every number here is inherited. The 7 CONFIRMED
   items arrived with control arms run by their lanes; the 44 NOT TRIAGED
   items arrived with self-reported arms that no second party checked — and
   the measured 36% refutation rate on checked claims says self-reported arms
   are not enough. Treat every untriaged remedy as a lead.
2. **The cost ranking has no common noise floor.** `cost_rank` was assigned
   per-lane by different agents; the values are not comparable, so I re-ranked
   on stated dollar/time evidence. That systematically privileges lanes that
   measured in dollars (extraction-readiness, circles) over lanes whose costs
   are structural (bot-reviews' green-means-never-asked, #460's injection
   surface). If the repo's threat model changes — more authors, public PRs —
   items I put in Tier 4 move up and nothing in this ranking will have flagged
   it.
3. **I could not settle the route for the #1 remedy.** The one-regex
   premise-gate fix targets a plugin file under `~/.claude`, which do-not.md
   #11 forbids editing. Upstream PR vs project-scoped override is a decision
   this synthesis flags and does not make.
4. **The #2 recommendation rests on unread code.** "Merge `--partial`, never
   run again" is the right shape given the arithmetic, but the lane that
   produced it admits it never read the merge path that makes `--partial`
   safe. If 17623a32 does not bin 0012/0026 as believed, the recommendation
   changes. One read settles it; this review did not perform that read.
5. **Conditions carried, per this repo's rule:** the cap arithmetic is true at
   cap=$63 and dies if the cap moves; the CodeRabbit file-cap cause is
   confounded by a credits-exhausted clause in the same comment; the
   idle-lane durations are upper bounds; the "one-entry kb-build fix" claim
   was never cross-checked and sits in the 36%-wrong-expected pool.
6. **Dedup was judgment, not mechanism.** I collapsed codex-skip, U5, and the
   spend cluster by reading; a fourth duplicate may have survived collapsed
   counting. The per-category counts (7/4/44/0) are of INPUT claims, not of
   distinct defects.

## Which existing tools to fix FIRST (no new automation where one exists)

1. `kb_setup.hook_guard` — three extensions in one module: piped-rc deny
   (item 3), corpus-verb redirects (#429, item 8), one clause in the python3
   deny message (Tier 4). Same `_REDIRECT`+test+table-row pattern as every
   prior extension.
2. `graphify_semantic_corpus_run.seeded_spend` — pre-flight cost projection +
   `--repay` refusal, at the SAME call site as the existing already-exceeded
   refusal (items 2a/2b).
3. A `status` verb wiring the EXISTING `verify_staged_chunk` into a reporting
   path (item 2 sibling) — unwired, not unbuilt.
4. `kb-handoff-check` — CARRIED-N=3 failure and directive-to-plan reconcile
   (items 11, 12).
5. `kb-ship` — evaluate all preconditions before refusing, the design
   `kb-gates` already embodies (Tier 4).
6. `kb-arms -- --init` skeleton emitter (item 14).
7. Docs, in this round's PR: CLAUDE.md:169, do-not.md #5, gates.py:419,
   verify-before-advancing.md:22 (items 4, 15).

Explicitly NOT proposed, because an existing tool already does it: a
`kb-watch-task` poller (the Monitor tool exists and was already fetched — use
it); a fourth pending-work audit (act on OPEN #368, with Ray, because the
freeze gate and his backup-directory designation make unilateral cleanup a
directive violation, not a chore).

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — every lane's subject: PR #469, issues #368/#409/#429/#432/#441/#460 et al., source files, transcripts, and bot comments cited throughout
- [ray-manaloto/dotfiles](https://github.com/ray-manaloto/dotfiles) — pending-work lane spot-checked 3 of 167 refs/salvage dotfiles-mirror refs against the live sibling repo
