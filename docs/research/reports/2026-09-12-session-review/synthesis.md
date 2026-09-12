# Synthesis — 6-lane cold review of the 2026-09-12 round

**Commit examined: `bdd2cb17`** (`bdd2cb175f5f7e0b70ff2eba60f9571bdb5d0543`),
branch `feat/754-plugin-types-contract`. The six lanes examined `c1d8afb8`
(a1–a5) — two commits behind this one; `c1d8afb8` and `bdd2cb17` differ only by
the round's own DAG/decision-page commit and the corpus-loop commit, neither of
which touches `python/` or `.claude/mods/`.

Written by `kb-codex-astra-advisor` (synthesis lane). Sources: the six lane
reports under `.agent/kb/review-round/lanes/`, plus five probes this lane ran
itself, named inline.

**Reading convention used throughout**, because this repo has a standing memory
that a synthesis launders lane confidence into its own: every claim below is
marked either **"per lane a\<N\>, not re-derived"** or **"re-derived here"** with
the command. Nothing is asserted on a lane's authority alone without saying so.

---

## 0. Executive answer to Ray's "it did not properly run"

Session `3b921834` **ran correctly and then died without a closing turn.** The
mechanism is measured, not inferred: its last commit (`c1d8afb8`) landed at
19:27:06 UTC, the tool result returned clean at 19:27:09.678Z, and the **very
next transcript record at 19:27:09.699Z is `"Prompt is too long"`** — the
model's next completion failed on context size (per lane a1, not re-derived; a1
read the raw transcript records). A `/clear` followed 42 seconds later.

So no code work was lost. What was lost is **the turn that would have told Ray
what happened and what was next** — which is precisely why the next session had
to spend seven `/grilling` rounds reconstructing state.

**Survival ratio: 38 of 41 re-derived truth claims held (92.7%).** Denominator
and the three failures are in §4.

---

## 1. Contradictions adjudicated

### C1 — 🔴 `next.origin` citation `claude-code.d.ts:3841-3846`: a4 says WRONG BY ~500 LINES; a2 declined to adjudicate. **a2 is right, a4 is wrong, and I settled it with a live regeneration.**

This is the most consequential adjudication in the round, because a4 graded it
the single clearest "wrong fact" in the 19 promoted reports and recommended
correcting four files including the round's own README.

**The disagreement.** a4 claim #3 ran
`sed -n '3835,3850p' sources/media/claude-code-function-hooks-types.d.ts`, found
`PaneCloseInput`/`PaneCloseOrigin`, and concluded the citation is broken and was
"copied forward into 4+ reports". a2 claim #7 looked at the same vendored file,
found the same mismatch, and explicitly declined to call it a refutation:
*"expected, since it's a stale vendored snapshot, not the file the citation is
about."*

**Re-derived here.** The reports cite `claude-code.d.ts` — the file
`/plugin-types` **generates**, which `mod_runtime.py` writes into a temp CWD and
never commits. The vendored `sources/media/claude-code-function-hooks-types.d.ts`
is a different, older file. I regenerated the real one under an isolated HOME:

```
$ env HOME=<scratch>/home CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 \
    <claude> -p /plugin-types --permission-mode bypassPermissions
rc=0 ; wrote .claude/types/claude-code.d.ts  (9156 lines)

$ sed -n '3838,3850p' <scratch>/work/.claude/types/claude-code.d.ts
       * Set by the host alone, from the environment the call came from (its own
       * MessagePort) and that plugin's seat; nothing a plugin writes reaches it.
       ...
      readonly origin: Origin;
```

**Lines 3841-3846 of the generated file are exactly the `next.origin`
doc-comment. The citation is CORRECT.**

**Why a4 got it wrong, and why it matters more than the finding it replaces.**
The vendored file is 7,966 lines (re-derived: `wc -l`), the generated file is
9,156. The same text sits at vendored `:3336-3343` and generated `:3841-3846` —
a **+505-line offset**. a4 measured that offset and read it as the size of an
error. It is in fact the *signature of a correct citation to the other file*.
This is `change-the-route.md` rule 4 verbatim — **a bare basename is ambiguous
across two files and silently resolves wrong** — committed by the lane whose
entire job was catching that class.

**Disposition: NO ACTION on the citation. FIX NOW on a4's report** — its claim
#3 must be struck before anyone acts on it, because it recommends editing four
tracked files to "correct" something that is right.

**One thing a4 found that DOES survive**: the same doc-comment exists in the
vendored file at `:3336-3343`, which is useful corroboration that the claim is
stable across two Claude Code pins. That half is good and should be kept.

**The CONDITION on my own probe, carried rather than dropped.** I verified
against the **2.1.270** binary, and the banner says the file covers **24
built-in tools** (the isolated-HOME variant lane a3 documents; a run in a
populated HOME reports 30). The reports were written against **2.1.269**,
possibly the 30-tool variant. So strictly, I have shown that *a* generated
`claude-code.d.ts` puts the `next.origin` doc-comment at exactly 3841-3846 —
not that the identical bytes were there on 2.1.269.

**Why that does not weaken the verdict.** An exact six-line match to a cited
range, arrived at independently, is not a coincidence available to a wrong
citation; and it is a far better-armed probe than a4's, which measured a
different file entirely. If anyone wants the stricter arm, it is one command:
regenerate under `~/.local/share/claude/versions/2.1.269` and re-read the same
range. Nobody has run it, and a4's finding must be struck either way — a wrong
instrument cannot refute a citation regardless of what the right one shows.

### C2 — 🔴 Why `kb-mod-runtime-check` was rc 127: a2 said process contention; a3 said a broken PATH wrapper. **a3's route was right; a3's mechanism was wrong; the orchestrator's is right.**

- **a2**: *"a local environment hiccup during this concurrent 5-lane review
  (multiple heavy processes running at once)"* — a supposition with no probe
  behind it.
- **a3**: read the wrapper. Found `…/node/26.8.2/bin/claude` is a 3-line text
  wrapper onto `bin/claude.exe`, `package.json` says 2.1.270, and concluded the
  platform optional dependency `@anthropic-ai/claude-code-darwin-arm64` was not
  installed.
- **Orchestrator, measured after the lanes started** (given to me as
  authoritative): `bin/claude.exe` was a **500-byte placeholder shell script**
  that unconditionally errors; the **207,500,480-byte native binary was present
  and worked when invoked directly**. `node install.cjs` restored the launcher.

**Adjudication: a2 is refuted. a3 found the right layer (the wrapper) but named
the wrong cause (missing native dep) — the native binary was there all along.**
The orchestrator's measurement wins; it is the only one that inspected the
launcher's bytes rather than the dependency tree.

**Re-derived here**: `claude --version` → **rc 0, `2.1.270 (Claude Code)`**, and
my own `/plugin-types` run above returned rc 0. The gate is live again.

**The durable lesson is a2's, not a3's**: *"heavy concurrent processes"* is an
explanation that fits any transient and predicts nothing. It is the shape
`persistence-gate-retry.md` classifies as environmental — and here it would have
had you retry forever against a permanently broken launcher.

### C3 — 🟡 Commit-count claims: a2 says "3 ahead" is false (actually 5); a5 says the DAG's "4 ahead" is false (actually 6). **Not a contradiction — both are right, and together they are one finding.**

a2 measured 5 at `c33a1fb5`; a5 measured 6 at `c1d8afb8`; **re-derived here**:
`git rev-list --count main..HEAD` at `bdd2cb17` → **7**. All three agree with
each other and with the commit graph. The finding is not any one number — it is
that **this repo writes a commit-distance number into a durable artifact three
times in one day and it is wrong all three times**, because the number is
invalidated by the very next commit. `probes-need-a-control-arm.md` rule 6's
second paragraph names exactly this. Disposition in §2.

### C4 — 🟡 a1's §4.1 self-correction vs its own original claim about abandoned lanes. **a1 adjudicated itself correctly; take the correction.**

a1 first reported three `kb-codex-astra-advisor` lanes abandoned at the crash,
then corrected it: `session-audit-lead` completed at 19:12:42Z and its synthesis
was copied into `docs/research/reports/…` at 19:13:05Z — 14 minutes before the
crash; the other two sent INTERIM reports that were read and acted on, and only
their *nested* codex children were unresolved. **Per lane a1, not re-derived.**
The correction is the better claim and a1 named its own instrument error (a
`ListAgents` status column cannot answer "was this work incorporated"; the
transcript's `teammate-message` records can). No action — this is a lane being
honest, recorded so the wrong version does not get quoted from the first half of
its own report.

### C5 — 🟡 a5's finding #1 ("the DAG and grill page are untracked and will be lost") vs current state. **Closed by the orchestrator between a5's write and now.**

**Re-derived here**: `git ls-files` returns both
`docs/dag/2026-09-12-session-review-round.toml` and
`docs/artifacts/session-review-3b921834-grill.html`; `git status --short` is
empty. a5's most expensive finding is **already fixed**. Recorded because a5's
own addendum says it was still open at the time it wrote, and a reader of a5
alone would still act on it.

### C6 — ⚪ MEMORY.md size: a2 relays "30.3KB" (the system reminder), a5 measures 31,479 bytes. **Both correct at their own moment; the file grew between them.**

**Re-derived here**: `wc -c` → **31,479 bytes** now, against the harness's stated
24.4 KB limit — **~26% over**, and 31 of 109 index lines are being cut before any
session sees them. Not a contradiction; a demonstration that this number moves
within a single day. Use a5's, and re-measure rather than quoting it.

### Not settleable from the reports — one probe named

**a3's open item**: whether the audit's *"a URL in a comment can erase a
following property access"* reproduces in SOME TypeScript shape. a3 tried one
shape (variant H) and it did not reproduce; a3 explicitly did not search for one
that does. **Do not record this as refuted.** The probe that settles it: feed
`guard_inventory.strip_ts_comments` a `register.ts` variant carrying `//` inside
a template literal or a regex literal (the two places a non-lexical stripper
mis-detects a comment start) and diff `required_runtime_tokens` against BASE.
Nobody has run that.

---

## 2. Every finding, one ordered list, ranked by what it costs

Ranked by cost to the next session, most expensive first. **D** = defect (a
false statement or a real fault). **P** = process gap. **O** = opportunity /
design option — kept separate per item 3 of the brief, and deliberately ranked
BELOW every defect so it cannot crowd them out.

### FIX NOW — this session

| # | kind | finding | evidence anchor | why now |
|---|---|---|---|---|
| 1 | **D** | **a4's own claim #3 is false.** It grades `claude-code.d.ts:3841-3846` as "wrong by ~500 lines" and recommends correcting `README.md:17`, `fh-synthesis.md:33`, `graphify-extraction-owner.md:858` and the handoff. The citation is CORRECT. | Re-derived here: regenerated `/plugin-types` under an isolated HOME → 9,156-line file; `sed -n '3838,3850p'` is the `next.origin` doc-comment. See §1 C1. | It is a *false correction queued for application to four tracked files*. Acting on it breaks four correct citations. Strike it before anything else in this round moves. |
| 2 | **P** | **`session-audit-a-code.md` was never promoted**, yet `session-audit-synthesis.md:75` cites it as the evidence for the round's #1 P1. It exists only at gitignored `.agent/kb/reports/agents/session-audit-a-code.md`. | Per lane a4 (197 lines / 28,286 bytes on disk, hash matches synthesis's own table at `:718`). Re-derived here: `ls docs/research/reports/2026-09-12-function-hooks-round/` → 19 files, **no `session-audit-a*`**. | `agent-report-persistence.md` 1b: a cited load-bearing report must survive a clone. One `cp` + commit. A `git clean -xdf` destroys the evidence for the round's top finding. |
| 3 | **D** | **"unforgeable" is stated flatly in the round's front door while a later independent lane downgraded it.** `README.md:17` and `fh-synthesis.md` C1 present it as settled; `session-audit-b-claims.md:416` says *"An adversarial 2.1.269 transport-forgery arm was not run, so the stronger runtime word 'unforgeable' remains UNVERIFIABLE beyond the exposed contract."* | Per lane a4 claim 3b, not re-derived (I confirmed the doc-comment text exists, which is the *type-level* fact — not the runtime one). | The caveat was dropped as the claim propagated into the summary. Anyone reading only the README inherits certainty the round did not earn. One qualifier on `README.md:17`. |
| 4 | **P** | **`session-audit-d-vague.md` is a PARTIAL sweep (rc 124 at a 2400s bound) and the file itself never says so.** The fact lives only in three *other* files. | Per lane a4 claim #1 (read the 165-line file end-to-end; no internal timeout notice). | A reader who opens the file alone cannot discover it is incomplete. One line at its top. `verify-before-advancing.md`: an UNVERIFIED item graded honestly by a lane is still not done — and here it is not even graded where it is read. |
| 5 | **D** | **"3 commits ahead of `main`" in `session-2026-09-12-f.md` is false** — it was 5 at `c33a1fb5`, inherited verbatim from handoff `-e` where it was true at `cbd8827d`. | Per lane a2 claim #1. Re-derived here at `bdd2cb17`: `git rev-list --count main..HEAD` → **7**. | The one unambiguously false sentence in the handoff. Cheap, and it is the round's cleanest instance of the inherited-number failure. |
| 6 | **D** | **The `c33a1fb5` P1 fix is UNARMED: revert it and all 26 tests still pass.** Both halves are invisible — `generate_declarations` is monkeypatched in every end-to-end test (`tests/test_mod_runtime.py:355`) so nothing observes its `env`; the stub hardcodes `stdout="stub stdout"` (`:353`) so the new `Unknown command` branch at `:551` is never taken. | Lane a3, measured on a scratch copy: `c33a1fb5^` → **26 passed, rc 0**. a3 wrote the two arms (A12 `if _UNKNOWN_COMMAND in combined:` → `if False:`; A13 drop the env dict) and ran them two-way: both FAIL pre-fix, PASS post-fix, and A12 FAILS when `:551` is severed. | This repo's own standing memory: *the fix is where the defect lives*, and *a clean arm sweep is a claim about your TESTS*. A P1 fix with no arm is the exact shape. a3 has already done the work — it needs committing, not designing. |

### HAND OFF — next session, with the reason each can wait

| # | kind | finding | evidence anchor | why it can wait |
|---|---|---|---|---|
| 7 | **D** | **P1-1 is REAL as a false docstring, not as a wrong verdict.** `mod_runtime.py:50-51` claims *"a new field added to `register.ts` joins the contract with no edit here"* — true only for dotted/optional-chained access outside a template literal. `e["x"]`, `const {x} = e` and `${e.x}` are all INVISIBLE. | Lane a3, 8-variant table measured at `c1d8afb8` against the committed `register.ts`: BASE 11 tokens; variant A (+dotted) → 12; variants **B, C, D → 11, no change**; variant G (drop a read) → 10 **silently**. | The verdict on *today's* `register.ts` is correct (11 tokens). It becomes a live fail-open the moment someone writes ordinary TS. a3 has a prototype + 8 arms; needs review, not discovery. |
| 8 | **D** | **P1-2 is REAL and unmitigated.** `missing_tokens` searches the whole declarations file with no comment stripping and no scoping. A required symbol present only in a *doc comment*, or only on an *unrelated interface*, reads as present. The dotted arm has no boundary at all: `tool.call` matches `on("tool.callback", …)`. | Lane a3, 5-row measured table at `c1d8afb8`; `mod_runtime.py:337-341`, `:316-334`. Control row present (the matcher CAN say absent). | Realistic scenario: Claude Code renames the field and its d.ts carries *"`agentId` is now `agent_id`"* — the guard reads `undefined`, allows everything, and the gate is green. Waits only because the *positional* half needs `tsc`, which is not pinned here. |
| 9 | **D** | **P1-3 is REAL: the gate writes into the caller's real `$HOME`, per run, forever.** `mod_runtime.py:425` inherits `HOME`; only the cwd is isolated (`:528-529`). | Lane a3 measured **13** `~/.claude/projects/…kb-mod-runtime-<random>/` dirs (09:09→13:16). **Re-derived here: 14** — one more, written by the orchestrator's repaired gate run. That +1 is the accumulation arm. Also re-derived: my own isolated-HOME run leaked **nothing** into the real HOME, so a3's fix holds. | Unbounded accumulation, not corruption. a3's fix is prototyped and two-way armed (`HOME` → sibling of `work/`, drop `CLAUDE_CONFIG_DIR`). The `.claude.json` half of the original brief is **first-run only** — a populated home never hits it. |
| 10 | **P** | **S9's `touches` is literally `"UNKNOWN"`, so the DAG's merge-order serialization cannot include the one unit that will edit the most files.** Ordering is positional in a file written before the overlap was known. | Per lane a5 finding #3, not re-derived. | S9 is this round's own fix pass. It waits only because the repair is one sentence: *"S9 always merges after every unit whose `touches` it overlaps, regardless of id order."* |
| 11 | **P** | **`/clear-prep` is an unnamed consumer of `next-ticket`.** DAG unit S7 names only `/session-resume`. | Lane a5 finding #5: `grep -n "next-ticket\|next_ticket" .claude/skills/clear-prep/SKILL.md` → `:59` (fallback next-task source) and `:457` (close-out checklist). Per a5, not re-derived. | If D1 executes against `/session-resume` alone, `/clear-prep` silently calls a deleted task. Waits because D1 itself is deferred behind S7's verdict. |
| 12 | **P** | **Two scopes for the same OWED item, neither aware of the other.** Handoff `-f`: *"remove the `754` edge from those chain rows"*. DAG `[[deferred]] D1`: *"Remove next-ticket and the chain file entirely (8 files)"*. | Lane a5 finding #4: `docs/roadmap/aggregated-research-chain.toml:61-136` still carries `blockers = [754, 755]` etc. — neither edit has happened, so the conflict is latent. Per a5, not re-derived. | Nobody has done either edit yet, so no work is wasted today. One line in D1: *"supersedes handoff -f's narrower item."* |
| 13 | **D** | **The DAG's own `P0` comment says "4 commits ahead"** — measured 6 by a5 at `c1d8afb8`, **7 re-derived here** at `bdd2cb17`. | Lane a5 finding #7; re-derived here. | Nobody merges on a commit count. Fix it when the DAG is next touched — but note it is the *third* wrong commit-distance number of the day (see §1 C3). |
| 14 | **P** | **No rule forces a measured `kb-context` checkpoint inside a long autonomous run.** The target session ran its large self-audit at 19:26 UTC — 60 seconds before it had no room left. | Lane a1 §5.1, not re-derived. `request-clear-prep-at-20-percent-context.md` exists as a *standing call*, read as a soft trigger. | This is the root cause of the whole round. It waits only because it is a rule/gate design question, not a one-line edit — and because the cheap half (commit the handoff early) already happened here by luck. |
| 15 | **P** | **Nothing confirms dispatched lanes are `idle` before a session treats its work as closed.** The round's closing commit landed while 3 lanes were still `running`. | Lane a1 §5.2 + its own §4.1 correction (which narrows the harm: 1 of the 3 fully closed the loop, 2 sent consumed INTERIM reports, and only their nested codex children were unresolved). Not re-derived. | Real, but the measured harm this time was small. A `clear-prep`-adjacent check that refuses to finalize while `ListAgents` reports a `running` teammate is the mechanical form. |
| 16 | **P** | **`advisor-durability.md` anchors a different commit (`aef74afe`) than every `session-audit-*` file's `4cdd8bfb`**, in the same promoted directory. | Per lane a4's inventory table, not re-derived. | Not false — it documents an earlier #754 consult. But a reader must not assume one tree per directory. One line in `README.md`. |
| 17 | **D** | **A retracted framing survives in the round's longest file.** `fh-source-sweep.md:1432` says `tool.check`'s status is *"contested"*; `fh-synthesis.md:175` retracts it (*"both are right and nothing is contested"*). | Per lane a4 contradiction #2, not re-derived. | Correctly labelled as a synthesis correction — but `fh-source-sweep.md` is 1,463 lines, the plausible fatigue point. A one-line "SUPERSEDED by fh-synthesis.md:175" at `:1432`. |
| 18 | **D** | **Two within-report numeric self-contradictions, both already caught by `session-audit-d-vague.md`.** `extract-research-a-live.md:302` "6 of 23" vs its own `:471` "7 of 23"; `graphify-extraction-owner.md:635-645` claims "31 pin sites" over a 30-row table. | Per lane a4 contradictions #3 and #4, not re-derived (a4 did not re-open the gitignored scratch table). | Already caught and recorded. Fix when those reports are next touched. |
| 19 | **O** | **`othmanadi/planning-with-files` already ships the handoff path this repo hand-built** — `task_plan.md`/`findings.md`/`progress.md`, a documented "5-Question Reboot Test", and a Topic Handoff Pattern (`handoffs/<topic>.md`, merged as PR #170, v2.42.0). The plugin is already installed here. | Per lane s7, not re-derived. | Ray has already ruled the plan file becomes the sole carrier; this is the design input for that work, not a defect. |
| 20 | **O** | **The native enforcement triad is unused here: `PreCompact`, `SessionStart(matcher:"compact")`, `SessionEnd(matcher:"clear")`.** `PreCompactHookInput` is a documented first-class type; `mehmeteminduran/claude-session-handoff-plugin` uses PreCompact to *block* compaction until a fresh handoff exists. | Per lane s7 (Context7 against `code.claude.com/docs`), not re-derived. | This is the mechanical answer to finding #14 — but it is a build, not a fix. Note s7's own caveat: upstream `anthropics/claude-code#91910` reports PreCompact/SessionStart(compact) firing for a *subagent's* compaction without agent fields. |
| 21 | **O** | **`agentsview recall brief` is NOT a next-task carrier.** Its unit is a durable extracted FACT (decisions, gotchas, procedures, preferences, warnings) with review states `human_reviewed`/`unreviewed_auto`/`calibrated_auto`/`eval_raw`. No phase, goal or next-step field exists in the schema. | Per lane s7, quoting `agentsview.io/docs/recall/` and the pinned `docs/recall.md`. s7 flags its own negative as **inferred, not quoted** — no doc line says "recall is not for task state". | Answers the orchestrator's question: **orthogonal to the plan file, not a substitute.** The real open question s7 raises is separate and bigger: recall's extractor/review/evidence pipeline near-duplicates this repo's `kb-remember`/`kb-reflect` — which MEMORY.md already records as **write-only, 0 graph nodes**. |

### NO ACTION — with the reason

| finding | why no action |
|---|---|
| a2 claim #7, `next.origin` "UNVERIFIABLE from static repo state" | **Settled here as CONFIRMED** by live regeneration (§1 C1). a2 was right to decline; the answer is now in hand. |
| a4 claim #3, the "~500-line" citation error | **Refuted** (§1 C1). The offset is the delta between two files, not an error. Struck, not fixed. |
| a5 finding #1, the DAG + grill page will be lost | **Already closed.** Re-derived here: both are tracked at `bdd2cb17`; `git status --short` is empty. |
| a5 finding #2, `blocks_all = true` vs S8/S9 running | **Already corrected in the DAG** during the round, per a5's own addendum — and a5 is right that this is evidence the DAG worked. |
| a2's `sources/groups/graphify-ecosystem.toml` taplo failure | **Settled by the orchestrator, control-armed**: a deliberate `hk.pkl` exclusion. 88 tracked `.toml`, hk checks 85, exactly 3 live under `sources/`. Matches `agent-artifact-conventions.md` — a formatter reaching into `sources/**` would falsify provenance. The gate's green was honest. |
| a2's `lint` rc 1 | **Orchestrator contamination, now fixed.** An untracked `docs/dag/…toml` written by the orchestrator failed a gate a review lane then had to attribute. Committed at `bdd2cb17`, taplo reformatted it in the hooks. |
| a2's `kb-mod-runtime-check` rc 127 attributed to contention | **Refuted** (§1 C2). Cause was a 500-byte placeholder launcher. |
| s7's "Anthropic native Session Memory" (claudefa.st) | s7 correctly flags it **UNVERIFIED** — one third-party blog, no primary source. Do not act on it; check `code.claude.com/docs/en/memory` first if anyone wants to. |

---

## 3. Defects vs decisions — the separation, stated plainly

Ray's round is about **false statements and real faults**. It is not about
designs that could be better. The two are mixed together in the lane reports and
they must not be mixed in what gets acted on.

**Defects — a statement that is false, or code that does the wrong thing.**
Findings 1, 3, 5, 6, 7, 8, 9, 13, 17, 18. Ten of them. Every one is either a
sentence that can be corrected or a fault with a prototyped fix.

**Process gaps — nothing is false, but a real thing is not guaranteed.**
Findings 2, 4, 10, 11, 12, 14, 15, 16. Eight. These are where the round's
*machinery* leaked, not its truth.

**Decisions / opportunities — a different design would be better.**
Findings 19, 20, 21. Three, all from s7, all deliberately ranked last.

**The one that would have crowded the others out if it were not separated.** s7's
digest recommends adopting `planning-with-files`' own handoff path and wiring the
native `PreCompact`/`SessionStart(compact)` triad. Both are good, both are
Ray-adjacent (he has already ruled the plan file becomes the sole carrier) — and
**neither is a defect in this round**. They are the *next* round's work. Acting
on them now would mean the ten defects above ship uncorrected while a new
mechanism is built.

**And one genuine risk in the opportunity column, named so it is not lost.**
s7's #2 recommendation rests on `PreCompact` — and s7's own GitHub sweep found
`anthropics/claude-code#91910` OPEN, reporting that PreCompact and
SessionStart(compact) *fire for a subagent's compaction without agent fields*,
with SubagentStop firing against a never-created transcript path. A repo that
runs 22 background teammates in a day (per lane a1) is exactly the repo that
rough edge bites. Per lane s7, not re-derived.

---

## 4. Grading the round's own claims

**The honest answer to "it did not properly run": 38 of 41 re-derived truth
claims held. 92.7%.**

### The denominator, explicitly

| lane | what it re-tested | denominator | held | failed |
|---|---|---|---|---|
| a2 | every claim in `.agent/plans/session-2026-09-12-f.md`, each by a second route | **28** (a2's 30-row table minus rows #5 and #11, which a2 marks as not-claims-in-the-file) | 27 | 1 |
| a4 | the headline claims of the 19 promoted research reports | **9** | 7 | 2 |
| a3 | the three open P1s + the round's own "the fix is UNARMED" statement | **4** | 4 | 0 |
| | | **41** | **38** | **3** |

a1 and a5 are excluded from the ratio deliberately: a1 measured *behaviour*
(what the session did) and a5 measured *absence* (what the outputs fail to say)
— neither re-tests an assertion, so neither has a denominator of claims.

### The three that failed, in full

1. **"3 commits ahead of `main`"** — false; 5 at the handoff's own HEAD. An
   inherited number copied from handoff `-e`, where it was true. (a2 #1.)
2. **"unforgeable", stated flatly** in `README.md:17` and `fh-synthesis.md` C1,
   after `session-audit-b-claims.md:416` had already downgraded it to
   UNVERIFIABLE-beyond-the-exposed-contract. The *type-level* fact holds
   (re-derived here, §1 C1); the *runtime* claim was never armed. (a4 #3b.)
3. **`session-audit-d-vague.md` presented as a clean pass** in the round's index
   when it is an rc-124 partial sweep — and the file itself never says so.
   (a4 #1.)

### What that ratio actually means — read this before quoting the number

**The three failures share one shape and it is not sloppiness.** Every one is a
claim that was **true when first written and became false, or lost its caveat,
as it propagated into a summary**. Not one is an error of measurement. The round
measured well; it *summarised* badly.

**And the round's self-reported gaps were accurate at a rate of 4/4.** Every
place `3b921834` said "this is unverified", "this is unarmed", "this is still
open", a cold lane confirmed it. `c33a1fb5`'s own commit message says *"The
`mod_runtime` fix is UNREVIEWED and UNARMED"* — a3 reverted it and got 26/26
green, proving the self-report exactly right. The handoff's hedge *"treat gates
as UNVERIFIED at HEAD, not as 11/11"* was right too: a2's live re-run found 8/11.

So the defect is asymmetric and the fix is specific: **this round's honesty about
its own limits was excellent; its fidelity when copying a fact forward was not.**
That is a summarisation discipline, not a rigour problem — and it is the same
failure `probes-need-a-control-arm.md` rule 6 and this repo's own
`i-relay-lane-confidence-instead-of-lane-evidence` memory both already name.

### One number that should NOT be read as part of this ratio

a4's claim #3 ("the citation is wrong by ~500 lines") is a **reviewer** error,
not a round error — refuted in §1 C1. It is called out because if it had gone
unadjudicated, this ratio would read 37/41 and four correct citations would have
been "fixed" into wrongness. **The cold review produced one false finding in this
round, and catching it was worth more than the finding it replaced.**

---

## 5. Handoff-ready block

**Not the handoff file.** This is the content `/session-resume` will need when
the orchestrator assembles one at close. Every number below names the lane that
measured it, or says "re-derived here" with the command. No inherited numbers.

### Where you are

- **Branch** `feat/754-plugin-types-contract`, **HEAD `bdd2cb17`**
  (`bdd2cb175f5f7e0b70ff2eba60f9571bdb5d0543`).
- **7 commits ahead of `main`** — re-derived here, `git rev-list --count main..HEAD`.
  🔴 **Re-derive this before quoting it.** It has been written into a durable
  artifact three times today and was wrong all three (§1 C3).
- **Working tree clean** — re-derived here, `git status --short` → empty.
- **No PR open** for this branch — per lane a2 claim #25
  (`gh pr list --head … --state all` → `[]`), not re-derived.
- **No `kb-review` receipt for HEAD** — re-derived here,
  `find .agent/kb/review -iname "*bdd2cb17*"` → 0 files. `kb-ship` and `kb-land`
  both refuse without one.

### Gate truth, with evidence

**There is NO gates artifact for `bdd2cb17`** — re-derived here,
`ls .agent/kb/gates/gates-bdd2cb17*.json` → no matches. The newest is
`gates-c1d8afb8….json`, two commits behind.

That artifact reads **8 passed / 3 failed**, and **every row carries
`dirty: true`** — re-derived here by parsing the JSON. So it does not describe a
committed state at all; it describes a tree with the untracked orchestration DAG
in it.

| gate | rc | status now |
|---|---|---|
| `lint` | **1** | **FIXED.** Cause was the untracked `docs/dag/2026-09-12-session-review-round.toml` — the orchestrator's own file, not the branch. Committed at `bdd2cb17`, taplo reformatted it in the hooks. (Orchestrator, authoritative.) |
| `test` | **2** | **Believed flaky, NOT re-confirmed.** One xdist worker failed `tests/test_codex_lane.py::test_the_bound_kills_the_group_on_a_non_tee_run` with `FileNotFoundError` on `descendant.pid` — a process-group timing race. Matches the shape of **#748** (OPEN). Per lane a2; **a2 did not re-run it alone**, and neither did I. |
| `kb-mod-runtime-check` | **127** | **FIXED.** `bin/claude.exe` in the mise-installed `@anthropic-ai/claude-code` was a 500-byte placeholder; `node install.cjs` restored it. (Orchestrator, authoritative.) Re-derived here: `claude --version` → rc 0, **2.1.270**; and a live `/plugin-types` run → rc 0, 9,156-line `claude-code.d.ts`. |
| the other 8 | 0 | `brain-audit`, `eval`, `graph-size`, `hk-test`, `funnel`, `kb-manifest-audit`, `kb-graphify-catalog`, `kb-lock-drift`. Re-derived here from the artifact. |

🔴 **Run `mise run kb-gates` at `bdd2cb17` on a clean tree before shipping.** Two
of the three failures are fixed and the third is only *believed* flaky. Nobody
has seen this branch green as a committed state.

### What shipped

- **#754 G01 landed** as `4cdd8bfb` — `kb-mod-runtime-check`, the first
  deliberately non-hermetic ship gate. Its own gates artifact is clean:
  **11 rows, all `rc:0`, all `dirty:false`, all `sha` fields matching** — per
  lane a2 claim #3, which opened the JSON directly and cross-checked against
  `GATE_TASKS` in `gates.py:173-201`.
- **Its own P1 fixed** at `c33a1fb5` (the gate was green only because of *where*
  it ran). **SOUND in mechanism, UNARMED as shipped** — lane a3 reverted it on a
  scratch copy and got **26 passed, rc 0**.
- **19 research reports promoted** to
  `docs/research/reports/2026-09-12-function-hooks-round/` — re-derived here,
  `ls …/*.md | wc -l` → 19. **One cited report is missing** (finding #2).
- **26 hermetic tests** in `tests/test_mod_runtime.py` — per lane a2 claim #16,
  `grep -c "^def test_"`.
- **11/11 arms died, 1/1 control held** on
  `docs/research/arms/2026-09-12-g01-mod-runtime.toml` — lane a2 claim #17 ran
  `mise run kb-arms` live, not from a report. Note lane a3's caveat: those 11
  arms attack the *extractor*, and none of them can see the `c33a1fb5` fix.
- **The DAG and the decision page are committed** — re-derived here,
  `git ls-files` returns both. a5's most expensive finding is closed.

### What is owed

**Before shipping this branch:**

1. Strike a4's claim #3 (§1 C1) — it is a false correction aimed at four tracked
   files.
2. Promote `session-audit-a-code.md` (finding #2).
3. Commit lane a3's arms **A12** and **A13** for the `c33a1fb5` fix (finding #6);
   a3 has written and two-way run them.
4. Correct the three false/overstated statements: the commit count, the flat
   "unforgeable", and `session-audit-d-vague.md`'s missing partial-sweep notice.
5. `mise run kb-gates` on a clean tree at HEAD, then a `kb-review` receipt.

**Carried, not done:**

- **Three P1s remain open in `mod_runtime.py`** (findings #7, #8, #9) — all three
  confirmed REAL by lane a3, all three with a prototyped and two-way-armed fix
  at `…/scratchpad/repo/mod_runtime.PROPOSED.py`. Note a3's prototype forces two
  test-file changes (`test_mod_runtime.py:252` and `:346`), both visible.
- **11 tool pins behind, 3 manifests behind** — per lane a2 claims #26/#27, which
  ran `kb-currency-check`. The 11: agnix, claude-code, datamodel-code-generator,
  fnox, graphify, hk, mise, ruff, rumdl, ty, uv. The 3:
  `sources/agentsview.manifest` (added), `sources/antigravity-cli.manifest`
  (changed), `sources/claudex-loop.manifest` (added).
- **`#754` stays OPEN (Ray's call) but must stop blocking** #756/#771/#772/#759/#763
  — and see finding #12: the DAG's D1 may supersede this edit entirely. Do not do
  both.
- **New issues from the round**: #777, #778, #779. #778 is confirmed OPEN and is
  the load-bearing one — *a codex lane cannot query the graph*, so "query the
  graph FIRST" is unfollowable from inside one (per lane a2 claim #12).
- **#767 still OPEN** — 13 codex sessions recorded at `danger-full-access`.

### Traps a fresh session walks into

1. 🔴 **`claude-code.d.ts` is TWO different files and the names collide.** The
   generated 9,156-line one (`/plugin-types` output, written to a temp CWD,
   never committed) and the vendored 7,966-line
   `sources/media/claude-code-function-hooks-types.d.ts`. The same text sits
   ~505 lines apart in them. A cold review lane already resolved a citation to
   the wrong one and graded a correct citation as broken (§1 C1). **Cite the
   path, never the basename.**
2. 🔴 **`kb-mod-runtime-check` writes into your real `$HOME`, every run.** Lane
   a3 measured 13 `~/.claude/projects/…kb-mod-runtime-<random>/` directories;
   **re-derived here: 14** — the count went up by exactly one from the
   orchestrator's single repaired gate run. That +1 is the accumulation arm. The
   fix is prototyped; until it lands, every gate run leaves a transcript in the
   user's profile.
3. 🔴 **An untracked file in your tree will fail a gate that someone else then
   attributes to the branch.** It happened this round: the orchestrator's own DAG
   file reddened `lint`, and lane a2 had to spend budget proving the branch was
   innocent. **Commit or stash before dispatching review lanes.** Note the gates
   artifact records `dirty: true` per row — read that field before believing a
   gate result describes a commit.
4. 🟡 **`taplo fmt --check` fails on three tracked `.toml` files and that is
   correct.** `sources/groups/graphify-ecosystem.toml` and two siblings under
   `sources/` are excluded from hk's FORMATTERS by design. 88 tracked, hk checks
   85, exactly 3 under `sources/`. (Orchestrator, control-armed.) Do not "fix"
   them — a formatter reaching into `sources/**` falsifies provenance.
5. 🟡 **`agentsview` graded the crashed session `outcome: completed`,
   `health_score: 92`, grade A, `peak_context_tokens: 975372`.** (Orchestrator,
   authoritative.) A session that died on `"Prompt is too long"` without a
   closing turn scored an A. **agentsview cannot replace this repo's own session
   review** — it did not detect the failure this whole round exists to examine.
6. 🟡 **MEMORY.md is ~26% over its read limit and lines 79–109 are being cut
   before any session sees them.** Lane a5 measured 31,479 bytes against a
   ~24,986-byte limit; **re-derived here: 31,479**, unchanged. a5 read what is
   being dropped and it is not filler — the "How my own fixes fail" section is in
   the cut. Ray's standing call is **do not hand-compact**; it needs U8's
   generator.
7. 🟡 **`mise run kb-session-search` needs `--no-sync`.** Two foreign harness
   files (a truncated Cursor composer record, an OpenCode part file with an
   invalid UTF-16 surrogate) break the all-or-nothing sync pass. Lane a4 verified
   the workaround live: rc 0, `"synced": false`, real matches.
8. ⚪ **The round's longest file carries a retracted framing.**
   `fh-source-sweep.md:1432` says `tool.check` is "contested"; `fh-synthesis.md:175`
   retracts it. 1,463 lines is a plausible place to stop reading.

### The one durable lesson from this round

**This round's honesty about its own limits was excellent; its fidelity when
copying a fact forward was not.** 4 of 4 self-reported gaps were accurate under
cold re-test. All 3 failed claims were true when written and became false — or
lost their caveat — on the way into a summary (§4). The remedy is not more
rigour at measurement time. It is a rule that a number or a qualifier copied into
a summary is re-derived at the moment of copying, not inherited.

---

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — the repo under review; all six lane reports, the git state, the gates artifacts, the promoted research directory, the vendored and generated `.d.ts`, and the live `/plugin-types` regeneration.
- [kenn-io/agentsview](https://github.com/kenn-io/agentsview) — issues #1470, #1471, #1676 relayed from lanes a2 and a4; not independently re-derived here.
- [anthropics/claude-code](https://github.com/anthropics/claude-code) — issues #70555, #72745, #80883, #90212, #17428, #91910, #86716 relayed from lane s7; not independently re-derived here. #91910 is the one that bears on a recommendation (§3).
- [othmanadi/planning-with-files](https://github.com/othmanadi/planning-with-files) — relayed from lane s7 as the top candidate for the next-task carrier; not independently re-derived here.
- [ddaanet/handoff](https://github.com/ddaanet/handoff) — relayed from lane s7 as the closest existing plugin analogue.
- [mehmeteminduran/claude-session-handoff-plugin](https://github.com/mehmeteminduran/claude-session-handoff-plugin) — relayed from lane s7 for the PreCompact-blocks-compaction pattern.
- [hivellm/rulebook](https://github.com/hivellm/rulebook) — relayed from lane s7 for its explicit decision *against* a forced-hook handoff ritual.
