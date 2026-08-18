# Session-review synthesis — iteration 1 (2026-08-18)

Synthesist: kb-synthesist. This report COMBINES the iter1 lane reports and the
cross-check (refutation) lane's verdicts. **Every number in it is inherited** —
from a lane report, a refutation report, or the run-2 brief. I re-derived
nothing. Where a figure was re-derived, it was the refutation lane that did it,
and I say so. Rankings are by COST OF LEAVING IT UNFIXED.

## Verdict counts

| status | count |
|---|---|
| confirmed by cross-check | **1** |
| refuted by cross-check | **13** |
| unverified (cross-check agent did not return) | 0 |
| **not triaged** (cross-check budget exhausted before reaching them) | **17** |
| total findings received | 31 |

Triage coverage: 14 of 31 findings (45%). Refutation rate among triaged:
**13 of 14 (93%)**. The verifier demonstrably ran — 13 refutations, each with
its own control arms — so a zero-refuted process failure is NOT present. What
IS present is the inverse problem: the sweep lanes' raw output was almost
entirely wrong as stated, and 17 claims (including two claimed BLOCKERS) were
never looked at by anyone.

---

## TIER 1 — the circles. Leaving any of these unfixed re-runs the same failure a third/fourth time.

### 1. The loop still ends before "file the issues" — and the workflow's own report step produced null

Ray's directive: *improve the session-review workflow, RUN it, aggregate the
issues into GitHub issues, apply them.* Status after two runs on 2026-08-18:

- Run 1's workflow deliverable — `.result.report` of `wf_8af76005-9bd` — is
  **null** (refutation-confirmed: `jq -r '.result.report'` → null, agentCount
  78, status "completed"). The ranked report the workflow exists to produce
  was never produced; 36 scratch lane files and a salvage.json exist instead.
- **Zero GitHub issues filed from either run** (refutation re-confirmed with
  the unbounded arm: `gh issue list --limit 1000`, 0 for ≥2026-08-18, control
  4 for ≥2026-08-17). Filing was *deferred by decision* ("merge Run A and
  Run B drafts, then file once") — but that is the third consecutive deferral
  shape, and the finding that predicted it ("still live: YES until this run's
  issues are filed") remains live.

The headline "the deliverable was produced, located, and NEVER READ" was
**REFUTED** — the session read the same data via the workflow journal at
12:29Z/13:29Z and salvaged 69 structured findings to disk. Consumption
happened; **filing did not**, and the null-report defect is real. Fix the
EXISTING tool: `session-review.js`'s report/synthesise phase (why `.result.report`
was null) and make issue-filing a completing step whose issue numbers land in a
TRACKED file. `gh issue create` already exists; no new automation.

### 2. Two claimed BLOCKERS on the current round were NEVER TRIAGED — nobody looked

(S1) HEAD `f772f5eb` has no kb-review receipt and no gates artifact — three
unpushed commits including the 584-line workflow rewrite cannot ship. (S2) run
2's `reportDir` `.agent/kb/reports/agents/iter1` is **gitignored** — every
iter1 artifact, *including this synthesis file*, dies with the working copy,
which is the exact loss mode of directive items 1 and 7, and directly
contradicts Ray's mid-round instruction at 13:06:14Z ("stored in git … datetime
timestamp with nanosecond precision and the git sha of the current workflow").

These carry their untriaged status forward: NOT confirmed, NOT refuted. But
their cost-if-true is the entire round's output, and verifying them costs
minutes (`ls` the receipt, `git check-ignore`). First actions of iteration 2:
verify S1/S2, then `mise run kb-review` → `kb-review-receipt` → `kb-gates`
against HEAD, and repoint `reportDir` at a tracked path
(`docs/research/session-review/<utc-ns>-<sha>/` satisfies Ray's 13:06 text).
Existing tasks cover all of it.

### 3. The sweep's output is not consumable without cross-check — 93% of triaged findings were refuted, and the refutations name RECURRING probe-defect classes

If iteration 2 files issues from unrefuted lane output, it files ~13 wrong
issues per 14. The refutation reports converge on a small set of repeat
offenders, all already named by `.claude/rules/probes-need-a-control-arm.md`:

- **judgment reported as a zero result** ("zero on-point hits" from a command that printed 5 issues);
- **silent defaults as bounds** (`gh issue list` default `--state open --limit 30`, twice);
- **regex bounds that cannot match** (BRE with literal `|` pipes; `[^"]*` dying at the first escaped quote — each could only return 0);
- **wrong-artifact substitution** (stale pinned mirror read as the live doc; a 271,666-byte .md set restated as the 240,734-byte task output; currency.toml read as the whole currency surface while `broad.py` covers the rest);
- **token-spelling bounds** (grep "backup" for a directory spelled `archives/repo-recovery`; grep `agy` for a wrapper spelled `agy-delegate`; `mise run kb-query` counted while `graphify explain` is also compliant);
- **metrics with no attainable passing value** (graph-queries ÷ all Bash commands, when the rule is "one query per session").

Fix the EXISTING tool: the lane prompts in `session-review.js` — require a
verbatim-reproducible probe per claim and both arms stated, and make the
cross-check phase cover 100% of findings BEFORE the filing step, since 17/31
untriaged is what the current budget bought. The refute contract already
exists in the workflow; it is the coverage, not the mechanism, that failed.

### 4. Iteration 2 inherits a false premise about its own scope (UNTRIAGED)

The run-2 brief calls the other 2026-08-18 transcripts "small stubs";
`52f5798a` is 4.57 MB / 2,718 lines — *larger than the session under review* —
and is the session that shipped PR #339 and wrote the handoff. And the sweep's
window silently moved (run 1: since=2026-08-17, 7 handoffs; run 2:
since=2026-08-18, 1 handoff) with no recorded decision, so **the 2026-08-17
window is currently covered by no live run** — only by run-1 lane reports of
which 33 of 36 remain unread. Correct the ALREADY_SETTLED block before run 3.

---

## TIER 2 — confirmed or surviving actionable defects

### 5. CONFIRMED (the only one): python-heredoc file surgery bypasses the Edit tool, 20× in one session, no guard

`uv run python - <<'PY'` read→replace→write on tracked files, 20 times —
recidivism on an already-recorded lesson (`bulk-text-edits-belong-in-the-edit-tool`).
Control arm was run: the hook_guard/check_first redirect tables genuinely do
not cover it. Remedy: **extend the existing `kb_setup.hook_guard`** with a
narrow READ+WRITE-on-tracked-path predicate (read-only diagnostic heredocs stay
allowed). Companion UNTRIAGED gap in the same walker: 23 gate invocations piped
into head/tail (`kb-check` 14/22, `kb-gates` 7, `lint` 2) — the class
`check_first` was built to kill, in a spelling it does not cover. One predicate
on the existing tokenising walker, not a new guard.

### 6. Cold lane: the wrapper EXISTS and was never used, and the agy version is skewed three ways

The "no wrapper exists, build kb_setup.cold_lane" finding was **REFUTED**:
`agy-delegate` ships with the enabled antigravity plugin and reproduces the
exact flag shape the session hand-typed. What survives is worse in a quieter
way: 8 hand-built invocations that drifted (timeouts 20→40m, `--effort high`
appearing and vanishing), and a live skew — `mise which agy` → 1.1.11, Ray's
pin 1.1.13, a branch bump to 1.1.10, with `~/.local/bin/agy` shadowing
(the documented PATH hazard). Remedy: **use `agy-delegate`; resolve the
shadow/pin**. Do NOT build `kb_setup.cold_lane` — that would be the
use-tool-builtins failure the refutation names.

### 7. Corpus staleness makes graph-first structurally weak for exactly the questions this round asked

Two refutation survivors, same root: (a) the `agent-harness-docs` mirror is
pinned before the "Prompt caching in a fan-out" section — both session-review.js
citations resolve exactly against the LIVE doc and are off-by-7 on the mirror,
so the "fabricated citation" finding was refuted but the corpus is stale on
that page; (b) `kb-query` on this repo's own `kb_setup` returns TRUNCATED with
no answer (rc=3, measured live in the refutation) because `python/src` and the
installed graphify are not in the corpus. Every "should have queried the graph"
counterfactual about own-code questions is therefore false today. Fix with
existing tasks: `mise run kb-update -- agent-harness-docs`, `kb-add` the live
workflows page, and decide (AskUserQuestion-worthy) whether to ingest
`python/src/kb_setup`.

---

## TIER 3 — bookkeeping. Real, cheap, and visibly below the circles.

8. **Currency roster residue** — the "9 of 18 untracked" finding was refuted
   (agnix + antigravity-cli are covered by the broad sweep; the ruling cited was
   about a different list), but **7 packages have zero coverage of any kind**:
   anthropic, msgspec, datamodel-code-generator, structlog, trafilatura,
   pytest, pytest-xdist. Adjacent to existing #184/#329. Ray's ordering puts
   this AFTER the sweep — do not re-litigate.
9. **session-review.js lane-coverage gaps** to fold into the filing pass: no
   handoff-durability lane (the sole survivor of the refuted "handoff root
   cause" finding); no cold-takeover lane (untriaged); the backup-directory
   clause is a no-op — but the directory is **known**
   (`~/.codex/archives/repo-recovery/`, named in committed memory and the prior
   lane report), so the fix is publishing that path into a tracked doc and the
   lane's inputs, NOT asking Ray again; the 20%-dual-trigger ruling untracked
   (untriaged); findings need a `files` field before item 8's conflict-free
   batching can exist (untriaged).
10. **Pending-work dispositions** (untriaged or surviving): 7 salvage modules
    path-absent from main, at least one superseded — a function-level dedup is
    owed before calling them net-new; fix-328's two memory notes cherry-pick
    (trivial); `codex/gh-stack-skill` open-or-delete; the one-file
    ecosystem-critique branch; a `.agent/telemetry/` row for
    agent-artifact-conventions.md's table; a one-paragraph teammate delivery
    contract (5 of 7 outbound messages were protocol repair); plan documents in
    a tracked path (merges into item 2/S2); bounding ExitPlanMode churn — noting
    the refutation showed the largest plan growth was a USER requirement, so
    bound presentations and critique plan #1 early, but do not attribute all
    churn to circles.

---

## REFUTED findings — kept whole, because they are evidence about the probes

| # | lane | refuted headline | refuted by | what survives |
|---|---|---|---|---|
| R1 | circles | "deliverable produced, located, NEVER read" | 30 journal reads of `wf_8af76005` after 12:22Z; salvage.json (69 findings); broken `find|awk $5` and literal-pipe BRE probes | `.result.report` null; zero issues filed; lane .md files unopened |
| R2 | forgotten | "handoff gitignored = Ray's #1 root cause, untracked" | the cited gh search actually returns 5 issues incl. #212/#143; clear-prep SKILL documents the mortality as designed, with 2 committed compensating layers; directive says "candidate" | no lane checks handoff durability |
| R3 | contradicted | "kb-synthesist fable dispatch contradicts opus frontmatter" | CLAUDE.md:180's own second half + vendored 4-step resolution doc; frontmatter is live for kb-tool-review.js | design asymmetry note (verifier not overridden, synthesist is) |
| R4 | unpinned | "9 of 18 currency deps untracked, violating the ruling" | `broad.py` + live `mise outdated` covers 2 of the 9; the ruling cited is the EIGHT-pin list; ":118-130 names 18" miscounts its own range | 7 packages with zero coverage |
| R5 | context | "graph-first systematically violated, 0–1% compliance" | replay of `kb_setup.graph_first.decide()` over 1,198 events: 2 violations, 4/5 sessions queried in first 5 commands; unreproducible denominators | nothing |
| R6 | context | "49e2cc30: zero kb-query calls" | `[^"]*` regex dies at an escaped quote; the one query EXISTS, succeeded (168 nodes); guard marker file exists | nothing |
| R7 | tooling-gap | "no wrapper for agy; all re-derived per call" | `agy-delegate --print-command` reproduces the exact shape; plugin enabled; ai-cli-invocation.md mandates it | wrapper unused; invocation drift; 1.1.11/1.1.13/1.1.10 skew |
| R8 | pending-work | "salvage branch has NO trace on origin, no upstream" | `git ls-remote` shows the branch on origin at the same SHA (narrowed fetch refspec hid it); 13 colibri files on main incl. a memory note naming the branch BY SHA | 7 module paths absent from main; disposition still undecided |
| R9 | circles | "10 plans, 42% of calls, two branches built-and-deleted" | plan diffing: zero implementation files touched; dispositions were "file as issue"/"revisit"; biggest jump was a new USER requirement at 13:06; live-transcript totals unstable (203/204/206/207) | 10 presentations, 2h07m, first critique 5 revisions late |
| R10 | forgotten | "currency-gate demand contradicts doctrine, untracked" | #88 IS in the finding's own 7 hits — Ray's prior ruling; the directive is Ray superseding himself; `run.py:69` returns 2, so "always exits 0" is false | no issue yet references the 2026-08-18 directive (scheduled, not forgotten); 2 doc sites to amend if item 10 lands |
| R11 | contradicted | "workflows.md:316/:318 citation fabricated" | live doc matches both lines exactly; mirror is 7 lines behind; sibling :360 citation consistent both ways | corpus staleness on that page |
| R12 | context | "539K tokens recoverable via graph-first" | cited model file does not exist; figure self-contradicts (-117K in its own sentence); all 4 parameters wrong on re-measurement; live query TRUNCATED with no answer | the corpus gap (own code not ingested) |
| R13 | pending-work | "nobody knows which backup directory Ray means" | prior lane report + two COMMITTED memory files name `~/.codex/archives/repo-recovery/` (24 bundles, knowledge-base ones included); "backup" token-spelling bound | the path is under-published: work-memory only, no tracked doc/issue |

A refuted finding is evidence about the probe. Note that R5, R6 and R12 were
all one lane (context) and share one defect family; R2 and R10 (forgotten)
share the gh-defaults family; R13 and iter1/forgotten.md's same claim are ONE
correlated probe defect appearing twice, not corroboration.

## PARTIAL coverage — an interrupted lane reads exactly like a finished one; these did not finish

- **bot-reviews: covered NOTHING.** The lane did not return. Run 1's salvage
  recorded 7 bot-review findings; nobody in iter1 has re-examined any of them,
  and Ray's directive names bot-review dispositioning explicitly. A
  `bot-reviews.md` file exists in the iter1 reportDir, but the lane returned no
  findings and no coverage statement to this synthesis — I did not read the
  file, so its contents are unvouched-for. This is "not covered", never "clean".
- **Cross-check: 17 of 31 findings never triaged** — including both claimed
  blockers (S1/S2) and the run-2 false-premise claim ranked Tier 1 above.
- **circles**: 33 of 36 run-1 reports unread; `wtir3iumk.output` (240,734 B)
  never opened; consecutive plans not diffed by the lane itself (the refutation
  did it); `.agent/telemetry/` never attributed to cost — every "cost" in that
  lane is tool calls and wall clock, never tokens or dollars; subagent-side
  transcripts unmeasured; worktrees/branches out of remit.
- **forgotten**: never read the raw transcript (by design); did not settle
  "unfiled vs legitimately queued" for the addendum items; SKILL.md one grep
  pass only.
- **contradicted**: `.agents/` vs `.claude/` skill mirror not byte-diffed; the
  three sonnet agents' frontmatter unverified; kb_setup code-vs-docstring never
  reached.
- **context**: telemetry skipped; per-call token attribution not done; no
  pre-2026-08-18 baseline; the lane whose triaged findings went 0-for-3.
- **tooling-gap**: sibling agents' command shapes UNCHECKED (not confirmed
  absent); stub transcripts unopened.
- **pending-work**: function-level dedup of the 7 salvage modules owed; no
  reflog/`git fsck --unreachable` walk, so orphaned commits outside named
  refs are possible and unexamined.
- **unpinned**: self-declared complete for its scope; its one triaged finding
  was refuted, so treat its "complete" as complete-with-a-broken-instrument.

## What THIS synthesis got wrong or could not settle

- **I verified nothing.** Every status is inherited from a single-pass
  refutation lane that no one cross-checked. A refutation can itself be wrong;
  R1's refutation demonstrates the risk inside this very set — it caught the
  finding silently substituting one artifact (271,666 B of .md files) for the
  one its own lane report measured (the 240,734 B task output). I have no
  independent evidence the refutations' controls ran as described.
- **This file's location instantiates untriaged S2.** I wrote it where the
  task directed, inside gitignored `.agent/`. If S2 is confirmed, the
  synthesis of the round that diagnosed clone-mortal deliverables is itself
  clone-mortal. I flagged it; I could not resolve it (repointing the
  reportDir is the workflow's contract to change, not mine).
- **The tier ordering has a noise floor.** Tier 1 vs the rest is a confident
  separation. Ordering WITHIN tiers 2–3 is judgment; adjacent swaps are
  within same-input variance and should not be read as measured differences.
- **Untriaged cost_ranks are the sweep's own claims** — the same instrument
  that went 1-for-14 on triage. I used them only to seed ordering and
  overrode them where a refutation's collateral evidence bore on them (e.g.,
  S1/S2 promoted; the "23 piped gates" claim partially corroborated by an
  independent lane note). That override is judgment, not measurement.
- **Live-transcript totals are unsettled and I settled none of them.** The
  session's tool-call total was measured four ways (203/204/206/207); I used
  no absolute total as load-bearing anywhere above.
- **I could not settle whether `bot-reviews.md` on disk contains anything** —
  see the coverage section; reading it was outside what the lanes handed me,
  and a synthesist reading raw evidence becomes an unreviewed fifteenth lane.
- **Condition on the top finding:** "zero issues filed" was true as of the
  refutation probes (2026-08-18, unbounded `--limit 1000` arm). If issues were
  filed after those probes ran, item 1 collapses to just the null-report
  defect. Check before acting on it.

## Existing tools to FIX first (no new automation proposed anywhere above)

1. `session-review.js` — null `.result.report`; filing as a completing step;
   lane-prompt probe contract; cross-check coverage before filing; tracked
   reportDir; corrected ALREADY_SETTLED block.
2. `kb_setup.hook_guard` / `check_first` — two narrow predicates (heredoc
   read+write surgery; piped `kb-check`/`kb-gates`/`lint`).
3. `agy-delegate` adoption + the agy PATH-shadow/pin skew — configuration and
   habit, zero new code.
4. `mise run kb-update -- agent-harness-docs` + `kb-add` the live workflows
   page — existing ingestion tasks close the stale-citation class.
5. `currency.toml` — 7 additions via the existing engine, after the sweep, per
   Ray's stated ordering.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under review; all evidence inherited from its iter1 lane/refutation reports, none re-derived here
- [mrkhachaturov/agent-harness-docs](https://github.com/mrkhachaturov/agent-harness-docs) — cited via inherited refutation R11 (stale pinned mirror vs live code.claude.com docs); not consulted directly by this synthesis
