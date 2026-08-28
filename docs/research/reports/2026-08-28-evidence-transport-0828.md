# Evidence sweep: the Claude↔Codex transport, 2026-08-26 → 2026-08-28

Extends `docs/research/reports/2026-08-27-claude-codex-handoff.md`, whose evidence
stops at the 2026-08-21 round. Read-only sweep. Every 0-count below carries a
same-shaped control arm with known hits, pasted.

**Denominators.**

| corpus | total | mtime ≥ 2026-08-26 |
|---|---|---|
| `.agent/kb/reports/agents/` | **282** files | **41** |
| `.agent/kb/review/reports/` | **168** files | **17** |
| on-disk report corpus in window | **450** | **58** |
| subagent transcripts (`~/.claude/projects/…/*/subagents/**.jsonl`) | **1025** | **109** (107 parsed, 2 empty/unparseable) |

## Answer

**The baseline's cheapest fix has not been adopted, its clock recommendation is
refuted, and its resume recommendation is confirmed.**

1. **The one-sentence prompt fix is real but essentially unused.** Of 109
   in-window dispatch prompts, only **4** instruct BOTH channels (write to a path
   *and* return as the final message) — and all 4 are from the current session.
   **48** say write-only, **55** say neither. **Every one of the 8 lanes that
   needed a resend came from the "neither" arm; 0 came from the other 103.** The
   baseline's direction holds; its magnitude does not — the un-instructed arm's
   resend rate is **8/55 = 14.5%**, not the 8/8 = 100% the baseline reported.
2. **`codex exec --json` carries no timestamps on the installed 0.150.1.** The
   baseline's recommendation 4 ("Emit a clock") does not hold as written. This is
   the single most consequential contradiction in this sweep.
3. **`codex exec resume --last` DOES recover a hard-killed run's state** — the
   baseline's most-likely-to-be-wrong recommendation is now measured and correct.
4. **A new failure class the baseline could not see: the wrapper substituting
   itself for the model.** `codex-lychee-spike` wrote its files with its own Bash
   and never launched `codex exec` (#559, OPEN, 0 comments). Lane name ≠ execution.
5. **The roster is unchanged since 2026-08-06 and #116 is still OPEN with 0
   comments** — the `kb-advisor`/`kb-fallback-reviewer` divergence remains
   unrecorded, exactly as the baseline said, 21 days on.

---

## 1. Did the dispatch prompt carry the both-channels sentence?

Measured over all **109** in-window subagent transcripts (107 parsed) by reading
each transcript's **first** user message — the dispatch prompt itself, which is
stronger evidence than the handoffs, since the handoffs do not quote prompts.

Classification regexes:
- RETURN: `as your final (message|response)` (or `return … as/in your final …`)
- WRITE: `(write|persist|save) … (to|at|into) <path>`

| dispatch prompt class | lanes | needed a resend | rate |
|---|---|---|---|
| **BOTH** (write to path AND return as final message) | **4** | **0** | 0% |
| **RETURN-ONLY** | **0** | — | n/a |
| **WRITE-ONLY** | **48** | **0** | 0% |
| **NEITHER** | **55** | **8** | **14.5%** |
| total | **107** | **8** | 7.5% |

The 4 BOTH prompts: `codex-binary-probe`, `evidence-0828` (this lane),
`trackers-agent-team`, `tool-inventory`. Three are from session
`06441913-…` — i.e. **the fix is being applied only in the session that read the
baseline.**

The 8 resent lanes, all NEITHER: `premises-trackers-v2` (1 follow-up),
`premises-trackers-v3` (2), `premises-trackers-v4` (3), `premises-trackers-v5` (2),
`premise-check` (2), `advisor-spine` (2), `premises-trackers` (2),
`frontier-facts` (2).

**Nulls and their arms.**
- *"0 of 4 BOTH lanes needed a resend"* — arm: the same NUDGE regex, same command
  shape, fires **8 times** on the NEITHER arm. The probe discriminates.
- *"0 prompts use RETURN-ONLY"* — arm: the RET half of the regex fires on 4 files
  (the BOTH cell). It can match; nothing is RETURN-ONLY.
- *"the both-channels sentence appears nowhere in `.agent/plans/` or `.claude/`"* —
  `grep -rn -iE "write the full report to.*(AND|and also).*(return|final message)"`
  → 0 in both trees. Arm: `grep -rn -i "final message"` over the same trees →
  **1 hit**, `.claude/agents/kb-extraction-worker.md:28`. Probe discriminates; the
  sentence is genuinely not in any committed dispatch template.

**Does the baseline's §3a claim hold?** *Partly.* Direction: yes — instructed
prompts still show 0 resends, un-instructed prompts supply 100% of resends.
Magnitude: **no** — 8/8 does not reproduce; it is 8/55. The baseline's "8 in 8"
counted only the 8 lanes it had already identified as nudged, so its denominator
was the numerator. Method difference stated so the two are not averaged.

**Caveat on the instrument.** "Needed a resend" here = a later user turn in the
lane's transcript matching a nudge phrase. It cannot see a resend sent as a
`SendMessage` that the transcript records differently, and it counts a
clarification as a nudge if it uses nudge words. It is a floor, not a census.

---

## 2. Codex lanes: `CODEX SAID:` / `PROCESS:` / timing

Only **3** in-window files contain a `CODEX SAID:` field, and the same 3 are the
only ones in the **entire** corpus (control: `grep -rli "CODEX SAID"` over both
full directories → **3**, so the field is new, not merely rare in-window).

| report | `CODEX SAID:` | `PROCESS:` | launched codex? | timing |
|---|---|---|---|---|
| `codex-trackers.md` | *empty* — "nothing; FINAL is empty; the watchdog killed the process mid-retry" (:36) | `REAPED: 24220 (group dead)` (:37) | **YES** (PID 24220) | **2700 s** watchdog kill (:9, :20) |
| `codex-lychee-spike.md` | `N/A … no codex exec subprocess was invoked for this task. I wrote all five files directly via this session's own Bash tool (heredocs)` (:40) | `…zero matches … no codex process group to reap here` (:42) | **NO — substituted** | none recorded |
| `codex-history-agent-team.md` | quotes the other two (a meta-report) | — | n/a (research lane) | n/a |

| tally over the 3 | count |
|---|---|
| launched a codex process | **1** |
| substituted itself (disclosed) | **1** |
| blank / not applicable (meta-report) | **1** |
| carry a `PROCESS:` field | **2 of 3** |
| carry an explicit duration | **1 of 3** (2700 s) |

`codex-lychee-spike.md:52` is the architect's own annotation: *"the lane
SUBSTITUTED ITSELF … the spike files are therefore CLAUDE-authored."*

**Timing fields more broadly.** Of the **58** in-window report files, **9**
contain any duration-shaped token (`elapsed` / `wall clock` / `watchdog` / `N min`):
`diagram-tool-status`, `fact-libs-and-plugins`, `handoff-verify`,
`lane-evidence-transport`, `size-gate-research`, `advisor-lychee-spike`,
`codex-history-agent-team`, `tool-gap-sweep`, `codex-trackers`. **Control:** the
same command shape on the always-present word `report` matches **53 of 58**, so the
9 is a real scarcity, not a broken grep. The baseline's "the lane protocol emits
no clock" **still holds** — 49 of 58 in-window reports record no duration at all.

The one report with real per-call timing is `codex-binary-probe.md`, and it is a
deliberate probe, not a lane: rc and seconds per question (9 s, 9 s + 7 s, 13 s,
<8 s).

---

## 3. Watchdog kills, timeouts, empty FINALs since 2026-08-26

| class | files | which |
|---|---|---|
| names a watchdog | **3 of 58** | `codex-trackers.md` (first-hand), `lane-evidence-transport.md` + `codex-history-agent-team.md` (both meta-reports *about* earlier kills) |
| names a timeout / "timed out" | **5 of 58** | the 3 above, `handoff-verify.md` (the 900 s resume, pre-window event), `review-fc3e084b-cold.md` — **false positive**, its "timeout" hits are the `timeout` *binary* in `absent_binary.decide("timeout 5 ls")` (:18, :21, :30) |
| names an empty `FINAL` | **3 of 58** | the same 3 |

**Exactly one NEW first-hand kill in the window:** `codex-trackers`, **2700 s**,
`STATUS: timeout`, `FINAL` empty, no commit, work code-complete but uncommitted —
the architect had to run the five live checks and commit the lane's work itself
(`03c2f224db8c`). Root cause recorded on the report (:40): the lane's mandated
`workspace-write` sandbox has **no outbound network**, so the spec's live `gh`
verification could never pass and the lane burned its whole budget retrying it.

**Null with its arm.** *"No other in-window report records a kill."* Arm: the same
`grep -lin "watchdog"` over the **full** (not in-window) directories finds **more**
files, and the `report` control matched 53/58 in-window — the sweep can find text
in these files. The scarcity is real.

**New in this window, not a kill but the same family:** the substitution above
(#559). A watchdog kill produces an *empty* result you can detect; a substitution
produces a *complete, plausible* result attributed to the wrong model family. The
baseline's fragility section has no row for that class.

---

## 4. Roster status — five lines

1. **#116 is still OPEN, titled "The reusable agent team: roles, model/effort per
   role, and allowed tools", with 0 comments** — unchanged since the baseline.
2. **`.claude/agents/` has not been touched since 2026-08-06** (`a41f0b5c`,
   `chore/post 220 (#221)`); six agents, exactly the count the baseline reported.
3. The 2026-08-06 synthesis §5.2 proposed **`kb-fallback-reviewer` (opus/high)**;
   what shipped is **`kb-advisor` (fable/high)** — `kb-extraction-worker` shipped
   as proposed, so this is the *only* divergence, confirming the baseline.
4. **The divergence was never recorded.** §5's tier mapping still says *"`fable` is
   deliberately ABSENT from the standing roster"*
   (`2026-08-06-roster-synthesis.md:262`) while `.claude/agents/kb-advisor.md:5`
   reads `model: fable` — the two documents still contradict each other, and #116's
   0 comments means no adjudication exists anywhere.
5. `kb-advisor.md:79-80` *does* carry the fallback semantics ("when Fable is
   exhausted … re-dispatches this same brief to an Opus subagent"), so the
   capability the synthesis wanted exists — only its attribution is unrecorded.

---

## 5. Contradictions with the baseline

| # | baseline claim | new evidence | verdict |
|---|---|---|---|
| 1 | `2026-08-27-claude-codex-handoff.md:167` — *"**Emit a clock.** `codex exec --json` gives a JSONL event stream; record dispatch, first token, and completion"* | `.agent/kb/reports/agents/codex-binary-probe.md:16` — *"NO timestamp/ts/time/created_at field on any of 6 event lines"*, control-armed on the always-present `"type"` key | **REFUTED on codex-cli 0.150.1.** Recommendation 4 needs an external wall-clock wrapper, not `--json`. |
| 2 | `…handoff.md:200` — *"**Whether `codex exec resume` recovers a watchdog-killed lane's partial state.** Untested. It is the recommendation most likely to be wrong."* | `codex-binary-probe.md:15` — SIGTERM'd 4 s into a turn (`wait` rc=143, no `-o` file written), `resume --last` recalled both the remembered number and mid-task progress | **CONFIRMED.** No longer unmeasured; recommendation 3 stands. |
| 3 | `…handoff.md:104` — *"prompts saying only 'return the full report as your final message' produced **8 in 8**"* | §1 above: 8 resends over **55** un-instructed prompts | **NARROWED.** Direction right, rate wrong by ~7×; the baseline's denominator was its numerator. |
| 4 | `…handoff.md:64-67` — *"the result survives, the notification does not … Nothing was lost **only because** `agent-report-persistence.md` rule 1 requires incremental writes"* | `.agent/plans/session-2026-08-27-i.md:48-60` — v4 and v5 got 3+2 idle notices and 2+1 resends and delivered **nothing**; both were recovered from the **transcript**, not from a report file | **PARTLY REFUTED.** For read-only lane types (premise-verifier, advisor) the disk report does *not* exist to survive — the transcript is the only durable channel. |
| 5 | auto-memory `subagent-lanes-go-idle-without-reporting` — *"one SendMessage recovers the full report in ~1 min"* | `session-2026-08-27-i.md:48-60` — resend worked for v2/v3, **failed for v4 and v5** | **REFUTED.** 2 of 4 resends failed; the settled recovery is transcript-first, one resend at most. |
| 6 | `…handoff.md:118` — *"zero reports record an orphaned codex CLI process surviving a 'completed' task"* | `codex-lychee-spike.md:42` records the opposite shape: an **unrelated pre-existing** `codex-otel` daemon (PID 2648) and **no** lane process | **CONSISTENT** — still zero orphans from a lane; a new report now explicitly probes for them and finds none. |
| 7 | `…handoff.md:213-219` — the roster section's `kb-advisor`/`kb-fallback-reviewer` divergence *"must be resolved by Ray … the swap itself is still unrecorded"* | #116 OPEN, 0 comments; `.claude/agents/` untouched since 2026-08-06 | **UNCHANGED** — no contradiction, just no movement. |

---

## Not measured

- **Whether a resend that *worked* (v2, v3) is distinguishable from one that
  failed (v4, v5) by anything in the prompt.** n=4, and the two arms differ in
  lane type as well as prompt, so it is confounded.
- **Latency of any in-window lane except `codex-trackers` (2700 s) and the
  `codex-binary-probe` sub-second/second-scale probes.** The reports carry no
  clock; §2's scarcity count is the measurement, not a substitute for one.
- **Whether the 4 BOTH-instructed lanes would have needed a resend anyway.** n=4,
  all in one session, all recent; 0/4 is consistent with the fix working and also
  with chance at a 14.5% base rate (P(0 of 4) ≈ 0.54). **This cell cannot
  discriminate.** The baseline's stronger claim rests on its own 12-lane sample,
  which this sweep did not re-verify.
- **`codex app-server`** — exists per `--help`, never executed
  (`codex-binary-probe.md:19`); `mcp-server` works but prints a DEPRECATION warning.
- **Whether #559's substitution recurs.** n=1. The stated hypothesis (a spec that
  forbids the lane's build/verify step invites substitution) is untested.
- **Anything about `agy`/antigravity in this window.** No in-window report
  measures it.

## GitHub repos touched

- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — issues #116 and #559 read via `gh issue view`; all other evidence is local.
