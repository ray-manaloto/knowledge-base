# Refutation lane: kb-review "bounded at two rounds" contradicted by practice?

Task: try to REFUTE the finding that the written two-round bound is contradicted
by institutionalized practice (#331 three cold rounds; #337/#339 three lane
reports each; standing lesson "a fix round needs its own cold pass").

## Findings as I go

### 1. What the written bound actually says (SKILL.md read in full)

- SKILL.md:3, :10 — "bounded at two rounds" confirmed present.
- CLAUDE.md:180 — "bounded at 2 rounds" confirmed present.
- SKILL.md:158-173 (§4): "Round 1 reviews. You fix. Round 2 verifies, and is
  the last round." If round 2 reports blocking: fix, re-run local gates, write
  receipt at fixed SHA "without a third lane round".
- SKILL.md:175-195: the fix path REQUIRES a third REPORT FILE at the new SHA
  ("write a short fix-round report at the new SHA ... No lane re-ran against
  <fixed-sha>"). So one two-round review with one fix produces THREE report
  files by design. Counting report files is a probe that cannot distinguish
  three lane rounds from two rounds + the mandated stub.
- SKILL.md:150-153: a timed-out round's re-aim "is still round 2 of the
  two-round bound, not an extra one" — a second reason report-file counts
  exceed lane-round counts.
- SKILL.md:98-100: "If a diff needs more than this, that is a decision for the
  human reading the summary, not a table for the skill to consult." (About the
  lane set; establishes bound-constrains-the-agent, human decides exceptions.)
- SKILL.md:162-166: the bound's rationale — stop rules fail because the
  REVIEWER decides when to stop; "a count is the only bound that cannot be
  argued with." The bound targets agent self-extension, not human orders.

### 2. #331 leg CONFIRMED as stated (session-2026-08-17-b.md:98-111)

- b:98 "Three rounds of VERIFIED cross-family review, 17 findings, all closed."
- b:109-111: "Rounds 2 and 3 each found a blocker CREATED by the previous
  round's fix. That is why the review ran to three rounds against `kb-review`'s
  bound of two — Ray ruled it explicitly."
- b:232-234: round 4 impossible (codex quota); "Ray ruled ship-now with the
  bound recorded rather than waiting."
- So: ONE instance of exceeding the bound, by explicit human ruling, recorded
  as exceptional in the handoff itself. Human override != agent practice.

### 3. #337/#339 leg REFUTED — the third file is the mandated stub, not a round

Handoff session-2026-08-18-a.md:152-161 itself LABELS the reports:
- #339: `8751b54e` "(#339 fix round)", `57279105` "round 2", `7c294a15` "round 1"
- #338: `2c510e52` "round 2", `61fa3616` "round 1" — TWO reports only
- #337: `888df6d0` "(#337 fix round)", `3b25a89e` "round 2", `7fc5b5e6` "round 1"

Read both fix-round reports:
- review-888df6d0…-cold.md:5-6 (#337): "**No lane re-ran against 888df6d0…** —
  the skill bounds this review at two rounds, and round 2 was the second."
  Lane-history table lines 19-22: exactly rounds 1 and 2, both cold:antigravity.
  Fix verified by kb-gates + kb-check + kb-arms 11/11 — the § 4/§ 4a path.
- review-8751b54e…-cold.md:5-6 (#339): "**No lane re-ran against 8751b54e…** —
  `kb-review` bounds this at two rounds and round 2 was the second."
  Lane-history table lines 18-21: exactly rounds 1 and 2. Arms 5/5.

PROBE-BOUND IDENTIFIED: counting report files (or reading the handoff
inventory as a round count) CANNOT measure rounds — SKILL.md:175-195 mandates a
third report file at the fixed SHA for every two-round review whose round 2
found blockers, precisely so the receipt gate can see it. Any compliant
two-round-with-blocking review produces three files. The probe could only ever
say "three reports"; reading their CONTENTS produces the opposite answer.

So the window's practice is: #337 bound OBEYED (in writing, citing the bound),
#338 two rounds (receipt at round-2 SHA), #339 bound OBEYED (in writing),
#331 exceeded once by Ray's explicit ruling. 2 obey + 1 n/a-under + 1
human-ruled exception != "institutionalized practice" of contradiction. The
two most RECENT reviews (postdating #331 and its lesson) follow the bound
exactly as written — including declining a third cold pass in the very
situation the "fix round needs its own cold pass" lesson describes, using
gates+arms instead, per SKILL.md § 4.

### 4. Directive + remaining handoffs

- docs/direction/2026-08-18-ray-directives.md read IN FULL: zero mention of
  review rounds or the bound. No bearing either way.
- Handoff c (#331 Repowise fix): round 1 (`84a7408d`, NO BLOCKING) + fix-round
  record `7a89a4b7` "honest that no lane re-ran" (c:239-247). Bound obeyed, the
  session immediately AFTER the #331 exception.
- Handoffs d, e, f: no review ran at all (branches explicitly "no kb-review
  receipt ... expected"). Neutral.
- Handoff g (#336): round 1 `f85f848b` + "fix round" `0c4bf6b6` + "policy
  change" `29cfca1f` (g:75-78). Read both extra reports' heads: "**No lane
  re-ran against 0c4bf6b6**" / "**No lane ran against 29cfca1f**". One lane
  round total. Bound obeyed.

### 5. Transcript census (14 in-window .jsonl, mtime >= 2026-08-17)

Command: `find . -maxdepth 1 -name '*.jsonl' -newermt 2026-08-17 | xargs grep -c -i <pat>`,
control `kb-review` = 676 hits (probe discriminates).

- "bound of two" = 6: five are quotes/re-reads of handoff b:109-111 (#331);
  the OTHER TWO (52f5798a) are in-window work-memory: "returned 5 findings and
  2 were regressions the round-1 fix had introduced — **the bound of two rounds
  is what caught them, not the first review**." Practice CREDITING the bound.
- "three rounds" = 26, "round 3" = 16, "third round" = 5: every review-related
  hit traces to #331 (transcript de3c5d58 = the session that ran it; 2bf99e26
  quoting its handoff), incl. twice verbatim: "Round 3 exceeded the skill's
  two-round bound **deliberately, on Ray's** ...". No second three-round review
  exists in the window.

### 6. Doctrine archaeology

- bound text in SKILL.md since 2026-07-30 (`285aaccf`, #77).
- § 4a "Arm your own fixes" since 2026-08-06 (`a41f0b5c`, #221) — BEFORE #331.
  The written doctrine's answer to "fix rounds introduce blockers" is § 4a
  arms + gates + the honest fix-round record, and #337/#339 executed exactly
  that (kb-arms 11/11 and 5/5 on their round-2 fixes).

## VERDICT: REFUTED (the finding's institutionalization pillar inverts on contact)

- Window census: #336 within bound · #331-Repowise-fix within bound · #337
  within bound (bound CITED in its own report) · #338 within bound (2 rounds)
  · #339 within bound (bound CITED) — versus ONE review (#331 main) beyond it,
  by Ray's explicit ruling, recorded as a deviation at every mention. 5-to-1 is
  the opposite of "institutionalized practice"; the two most recent reviews
  post-date the #331 lesson and follow the bound to the letter.
- The #337/#339 evidence is a probe-bound false positive: SKILL.md:175-195
  MANDATES a third report file for every compliant two-round review whose
  round 2 found blockers, so a report-file count can ONLY say "three" —
  compliance and violation are indistinguishable to it. The finding's own
  citation (a:154, a:159) labels those files "(fix round)", and the files
  themselves say "No lane re-ran ... the skill bounds this review at two
  rounds" — the second probe of the same fact disagrees, and the defect is in
  the counting probe.
- The punchline fails too: the pass that "found blockers two rounds running"
  on #337 was ROUND 2 — inside the bound ("the bound of two rounds is what
  caught them"). On #331 only round 3's single blocker lay past the bound, and
  the doctrine assigns exactly that call to the human (SKILL.md:98-100,
  162-166: the bound stops the REVIEWER deciding; the human decides "more");
  the human decided, visibly. An obedient agent under the written doctrine
  runs round 2, arms its fixes (§ 4a), and escalates ambiguity — which is what
  actually happened five reviews out of six.
- What SURVIVES (narrower, not the finding as stated): a real residual tension
  between the memory-lesson "a fix round needs its own cold pass" and § 4's
  "without a third lane round" for the ROUND-2 fix specifically. That is a
  doctrine-tension observation about one residual class, not "institutionalized
  practice contradicting the bound", and #331's Ray-ruling is its recorded,
  working escape valve.

## Contradiction with other findings in the set

Other lanes' findings were not provided to this lane, so no cross-set check was
possible. Internally, the finding contradicts its own cited evidence: the
handoff lines it cites label the third files "(fix round)", and those files
state the opposite of what the finding infers from their existence.

## GitHub repos touched

_None._ All probes were against this repository's working tree, its gitignored
`.agent/` artifacts, and the local transcript directory.

## COVERAGE

- REACHED AND ANALYSED: SKILL.md in full; CLAUDE.md:170-189; all 7 listed
  handoffs in full; docs/direction/2026-08-18-ray-directives.md in full; both
  #337/#339 fix-round reports in full; #336 fix-round + policy-change report
  heads; full reports/ + receipts listing; transcript token census over all 14
  in-window .jsonl (5 tokens + control); git -S archaeology on SKILL.md.
- OPENED BUT NOT FINISHED: #336 round-1 report (used handoff g's summary only);
  the 42 "fix round" transcript hits were not individually sampled.
- NEVER REACHED: full text of round-1/round-2 lane reports for #337/#338/#339
  (round counts taken from their fix-round reports' lane-history tables and
  handoff labels); receipt JSON bodies; transcript content beyond grep windows;
  the other lanes' findings in this verification set.
