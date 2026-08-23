# Refute lane: "Currency can-never-gate vs the standing directive's hard gate"

Lane: refute-currency-never-gate. 2026-08-18. **VERDICT: REFUTED as a contradiction**
(the quotes are accurate; the "opposite intent / agent can justify skipping" claims do not survive).

## Finding under test (contradicted.md finding #1)

CLAUDE.md:159 + tool-currency rule:75 assert as DESIGN "mise run kb-currency always exits 0 and
can never serve as a CI gate", vs directive :45 "not doing any work until all critical currency
dependencies are up to date" (:56-58 "a gate on everything else... not a preference"); ":75
concedes nothing blocks work on a stale pin, but the rules still assert the opposite intent, so
an agent citing them can justify skipping enforcement."

## 1. Citation verification — all accurate

- CLAUDE.md:159-160 (Read 2026-08-18): "**`mise run kb-currency` always exits 0** and can never
  serve as a CI gate — an out-of-date tool is a signal, not a failure. Read the report, not the rc."
- .claude/rules/tool-currency-and-native-first.md:75-76: same sentence ("can never be a gate").
- Directive :45 (verbatim), :56-58 (analysis "gate on everything else... not a preference"),
  :75 (status row 2 "nothing BLOCKS work on a stale pin, which is the gap this directive names").

## 2. Why it is refuted anyway

**(a) The two doc sets assert the SAME mechanical fact — the finding's own evidence contains the
agreement.** Directive :75, in the directive's own voice: "nothing BLOCKS work on a stale pin,
which is the gap this directive names." That IS what "always exits 0 / read the report, not the
rc" describes. Two probes of one fact, agreeing. A doc that names a gap to be FILLED (:23 "we
need to enforce this can never happen again" — enforcement to be built) is not contradicted by a
doc accurately stating why the existing task cannot be the filler.

**(b) Equivocation on "gate": the referents differ.** The rules' subject is the TASK
`mise run kb-currency` and its rc/CI semantics. The directive's subject is currency STATE and
agent work-ordering. "This task's rc can never gate" does not assert "staleness must never gate
work" — and the rules' operative clause points the reader AT the drift signal, the input Ray's
gate consumes. The opposite-intent reading requires detaching the em-dash clause from both its
subject and its closing instruction.

**(c) Both sentences remain TRUE after full compliance with the directive — structural, not
timing.** Step 5 of the loop is an AskUserQuestion interview; "Step 5 can never live in a hook —
a hook is a shell command; only the model can call AskUserQuestion" (CLAUDE.md:139-141, rule
:86-87). So the FULL loop can never be an rc gate under any policy; Ray's enforcement, when
built, will be a different mechanism (this repo's deny-hook pattern, e.g. graph_first /
check_first / stage_explicitly), which falsifies neither cited line. A sentence that survives
full compliance with a directive cannot be "the opposite intent" of that directive.

**(d) The phrase is the house idiom for EVERY advisory surface, not a currency policy.**
Transcript probe (14 in-window .jsonl, mtime >= 2026-08-17; `grep -c 'always exits 0'` per file
via find -print0|xargs -0, run 2026-08-18): 10 line-hits across 8 files; control `kb-currency`
hits 11/14 files (max 18), so the probe discriminates. All 14 extracted 260-char windows
(`grep -o '.{130}always exits 0.{130}'`) are about kb-session-reflect / kb-distill ("It always
exits 0 and gates nothing") or a kb-goal-check arms-spec comment — **ZERO about kb-currency,
ZERO citing it to skip anything**. mise-tasks-only.md says the same of kb-distill ("Advisory,
always rc 0, never a gate") and kb-skill-score. Under the finding's reading, any directive
making any advisory tool's subject mandatory would "contradict" all of these rows — the reading
proves too much.

**(e) The claimed exploit has zero occurrences, and every actual deferral traces to Ray, not the
rules.** All 7 handoffs read in full: drift was REPORTED unactioned pre-directive (d Open#5,
e Open#7, f header) and each currency deferral was Ray's explicit ruling — handoff g:57 "Still
deferred by Ray, deliberately: the graphify 0.9.46 bump…"; 18-a:37-40 the clear-prep ordering
("Both are his — the later one is operative"). No handoff, lane report, or transcript window
shows any agent citing the never-gate sentence to justify skipping. The directive is also
mechanically surfaced every round (MEMORY.md first bullet; clear-prep reads the newest
docs/direction/*-ray-directives.md — verified in contradicted.md's own VERIFIED-CONSISTENT
list), and eager zero-skip-policy.md forbids dismissing the drift report the rules point at.

**(f) The "hard gate" premise itself is a priority instruction Ray sequences, not a semantics
claim.** The same directive file, :212-223: the session-review sweep precedes the currency gate
for the first task, "recorded rather than reconciled". A gate that its author re-orders by
ruling operates at the instruction layer — where the rules' rc sentence never spoke. (Settled
block: do not re-litigate.)

**Timeline (git log -S 'always exits 0', run 2026-08-18):** CLAUDE.md sentence introduced
`2302024c` 2026-07-23 (#4); rule sentence `3bb49a8c` 2026-07-24 (#24); neither amended since
(only in-window touch of either file is `37f6a1c5` #336, which -S shows did not touch the
sentence). So the sentences are 26-day-old descriptions of task mechanics that predate the
directive — and per (c) they need no amendment for the directive to hold. The finding's own
REMEDY concedes this: "WHEN the blocking mechanism is built... scoping 'always exits 0' to the
report task only" — a future wording polish contingent on unbuilt work, not a live conflict.

## 3. What survives (the honest residue)

A doc-polish LEAD, exactly as the finding's remedy states: when the enforcement mechanism lands,
scope the sentence and soften "a signal, not a failure" for critical deps (tool-currency rule 5,
"sync describing docs in the same change", will bind at that point). That is not "rules
asserting the opposite intent", and it licenses no skip today.

## 4. Contradictions with other findings in the set

No sibling finding (#2-#12 in contradicted.md) contradicts it — none touches the currency-gate
topic; refute-2787-currency.md CONFIRMED a different currency finding (untracked issue), which is
orthogonal. The tensions are INTERNAL and with the set's own consistency list:
- Finding #1's own cited :75 has the directive asserting the very fact it calls "the opposite
  intent" when the rules state it.
- The set's VERIFIED-CONSISTENT entry ("clear-prep SKILL.md:49 reads the newest
  docs/direction/*-ray-directives.md") undercuts the exploit clause — the rules are never the
  lone voice an agent hears.
- Handoff 18-a:37-40 (Ray sequencing work AHEAD of the currency gate) cuts against the finding's
  "hard gate on everything else" premise being a semantics of the kind rc could contradict.

## 5. Probe-quality note on my own probes

- First per-file transcript count loop returned empty — zsh does not word-split `$F`; a broken
  probe, not a result. Re-run with find -print0 | xargs -0 (per-file counts + control shown).
- The negative "zero currency citations" is armed: same command shape found 14 real occurrences
  of the phrase (other tasks) and the control term in 11/14 files.
- -S probes armed: each returned the sentence's introducing commit (non-empty), and the --since
  filter returned #336.

## COVERAGE

- REACHED AND ANALYSED: docs/direction/2026-08-18-ray-directives.md IN FULL (234 lines);
  CLAUDE.md:145-170; tool-currency-and-native-first.md:55-99 (rest already in loaded context);
  all 7 handoffs IN FULL (b,c,d,e,f,g,18-a); contradicted.md IN FULL (the finding set);
  refute-2787-currency.md IN FULL; tool-currency SKILL.md (grep for gate/exits-0 language —
  carries neither sentence); git -S history of both cited files; 14 in-window transcripts
  (counts + all 14 extracted phrase windows + control term; content never read wholesale).
- OPENED BUT NOT FINISHED: nothing.
- NEVER REACHED: the .jsonl bodies beyond the bounded phrase windows (deliberate); kb-query
  graph pass (docs-vs-docs question, all sources primary and local); GitHub issue backlog for a
  pre-existing enforcement ticket (the directive itself records enforcement as unbuilt, so its
  absence/presence cannot flip the verdict).
