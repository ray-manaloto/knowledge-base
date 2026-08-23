# Refutation lane report — "Lane-availability thrash" (lane circles)

Verdict: **NOT REFUTED** (refuted=false). 7 of 8 sub-claims confirmed at primary
sources with a passing control arm; two NUMERIC details are wrong in the finding
(the until-loop count, and its own agy line-list arithmetic) without touching the
thesis.

NOTE ON FILENAME: `.agent/kb/reports/agents/refute-lane-circles.md` was claimed
mid-flight by a SIBLING verifier working the "review fix->blocker treadmill"
finding (it overwrote my first write). This lane's report moved here; do not
merge the two.

## Sub-claim verdicts (all counts 2026-08-18, this lane)

1. **codex quota inherited-wrong once (b->c) — CONFIRMED.**
   session-2026-08-17-b.md:11 + :232 record "depleted until 2026-08-19 22:29";
   session-2026-08-17-c.md:171-173: "Codex quota is BACK ... a live codex exec
   ... probe returned a real answer. Probe it, do not inherit the exhaustion
   date." Chronology (transcript mtimes): b=de3c5d58 ends 06:22, c=2bf99e26 ends
   09:55 — out, then back, same day.

2. **died mid-#336-review in G, 9 modules never covered, shipped partial on
   Ray's ruling — CONFIRMED.** session-2026-08-17-g.md:66-73 verbatim ("Codex hit
   its account usage limit mid-review (resets 2026-08-19 22:29) after a 600 s
   watchdog kill. Nine modules got no completed pass ... Ray ruled ship and let
   the PR bots review"); the list enumerates exactly 9 modules. Transcript
   cross-check (G=6b974f05, mapped by 379 cmds = G.txt 379 lines): grep -c
   "hit your usage limit" = 4, "watchdog" = 22. CAVEAT that is not a gap:
   G.txt (bash commands) has 0 `codex exec` — the #336 review ran through a
   SUBAGENT lane, so the death is evidenced by the handoff + transcript strings,
   two routes agreeing.

3. **codex out all of A18 — CONFIRMED, with its measurement basis stated.**
   A18=52f5798a (scratchpad paths in A18.txt + 299 cmds = tsv count). Only 2
   codex invocations exist in the whole session command log, both start-of-session
   probes (A18.txt:3,4); the orchestrator note (A18.txt:107) quotes codex live:
   "You've hit your usage limit ... try again at Aug 19th, 2026 10:29 PM";
   session-2026-08-18-a.md:117 "codex was out of credits all session"; transcript
   grep -c "hit your usage limit" = 3. No later codex invocation exists to
   contradict "all session", and the quoted reset (Aug 19 22:29) is a day past
   the session's end. A18 did NOT repeat the b->c inheritance error — it probed.

4. **agy substituted, "~9 lane runs among 14 invocations for 7 persisted
   reports" — SUBSTANTIALLY CONFIRMED; the finding's own arithmetic is sloppy
   both directions.** Re-run of its own probe `grep -n 'agy ' cmds/A18.txt` =
   **14 matches**: 5,6,7,11,12,13,28,70,73,106,219,256,280,293. The finding's
   line-list gave 12 (5 probes + 7 runs): it OMITS line 256 (a real run —
   br4-report.md, #339 round 2) and does not notice line 293 is a MEMORY.md-edit
   heredoc containing "agy " in prose — not an invocation. True classification:
   **5 probes** (5,6,7,12,70), **8 full-prompt lane runs** (11,13,28,73,106,219,
   256,280), 1 prose match (293) = 13 real invocations. Reports: 7 distinct raw
   files; **6 persisted** as lane reports via cp (A18.txt:14,29,104,107,242,262 →
   #337 r1/r2, #338 r1/r2, #339 r1/r2); the 7th (doc-report, the addendum review)
   deliberately NOT persisted (a.md:162-164). The two fix-round reports
   (888df6d0, 8751b54e) appear nowhere in A18.txt — written via the Write tool,
   not agy output. Spelling control arm: bare 'agy' = 15 vs 'agy ' = 14; the
   extra is line 107 prose ("`agy` 1.1.13") — no invocation escapes the token.
   Cross-session control: agy-cmd counts B=0 C=1(a `which codex agy` probe)
   D=0 E=0 F=0 G=0 — the substitution is A18-only, as the finding scopes it.

5. **one run cut off by a content-policy refusal returning a confident partial —
   CONFIRMED.** A18.txt:107 orchestrator note: round 1 on 61fa3616 (#338) "hit a
   Google content-policy refusal mid-run ('The prompt could not be submitted.
   The prompt contains sensitive words ...') and recovered, so it reported on
   chunks.py, graphify_semantic_adapter.py and graphify_sdk.py and reached no
   findings in the rest". a.md:115-117. Transcript: grep -c "sensitive words" = 5.
   Control arm: same greps on B (de3c5d58, the codex-heavy session) = 0 and 0 —
   the strings are signal, not boilerplate.

6. **--mode plan suppresses incremental report writes; a kill loses the run —
   CONFIRMED as the mechanism.** A18.txt:107: "both rounds were run with
   --mode plan, which blocks writes, while the prompt asked the lane to persist
   its report incrementally. Those contradict and plan mode wins, so a watchdog
   kill would have left nothing. Neither round was killed, so nothing was lost."
   a.md:120-122 states it as the standing hazard. (Precision: the LOSS is
   counterfactual — nothing was actually lost.)

7. **"15 until-poll loops" — THE NUMBER IS WRONG; the phenomenon is real.**
   Command-level truth in the same file the finding cites:
   `grep -c 'until .*do sleep' A18.txt` = **10** (lines 131,174,179,189,194,212,
   247,251,261,281). Raw `grep -c 'until ' A18.txt` = 18, of which 8 are PROSE
   inside heredocs/commit messages ("out of credits until 2026-08-19", "until we
   are 100% confident", ...). 15 is reproducible by neither probe; the raw
   transcript yields 14 occurrences of 'do sleep' / 17 of 'until ls' (echoes
   counted), so 15 most likely came from a transcript-level grep counting
   command echoes — a probe that cannot distinguish a run from its quotation.

8. **one loop fired on a PREVIOUS run's receipt, old result nearly reported as
   new — CONFIRMED.** A18.txt:131 is the loop: `until ls
   graphify-out/graphify-semantic-corpus-chunks/*/chunks/0001/receipt.json`
   — the `*` glob matches ANY run namespace, which is the mechanism. The
   session's own round-answer (A18.txt:286): "satisfied by a STALE receipt from a
   previous run, so a new run was stopped before it finished and the old result
   was nearly reported as the new one." a.md:106-109 item 5. Lines 189/194 are
   the re-waits after clearing.

## Could the original probes only produce this answer?

No. The core probes discriminate: the transcript failure-strings return 0 on the
codex-heavy control session B; the 'agy ' spelling misses no invocation (bare-agy
delta is prose); the b->c claim rests on two handoffs asserting OPPOSITE states,
which is the opposite of a one-faced probe. The one probe that failed the test is
the finding's OWN loop count (echo-counting) and its own agy line-list (omits a
run, mis-buckets a prose hit) — defects in the finding's counting, in the
direction of small overstatement, not fabrication.

## Does any other finding in the set contradict it?

None found. The sibling verifier's "review fix->blocker treadmill" notes (seen in
the shared report file) use the same A18 evidence and are CONSISTENT: their
report-inventory reading (#337 three reports, #338 two, #339 three; a.md:154-161)
matches my cp/Write evidence exactly, and their "#338 only 2 rounds" dovetails
with my confirmed #338-round-1 interruption (the refusal consumed one of the two
bounded rounds without buying coverage). Internal to THIS finding, its text
("14 invocations") disagrees with its own evidence list (12) — both slightly off
the re-derived 13 real invocations; the defect is in the finding's probes.

## Directive + handoffs

docs/direction/2026-08-18-ray-directives.md read IN FULL (currency gate,
18-name roster incl. antigravity-cli + codex, sweep-first clear-prep ruling).
All 7 handoffs (b,c,d,e,f,g,a) read in full. d/e/f record no lane usage
(0 codex / 0 agy in their cmds files), consistent with the thrash timeline:
out(b) -> back(c) -> unused(d,e,f) -> out mid-G -> out all A18 -> reset Aug 19 22:29.

## COVERAGE

- REACHED AND ANALYSED: the directive (full); all 7 handoffs (full);
  cmds/A18.txt, C.txt, G.txt (targeted greps + line reads); cmds line counts for
  all 7 sessions; bash-commands.tsv session mapping; transcripts 6b974f05 (G),
  52f5798a (A18), de3c5d58 (B control) via grep counts only (never read into
  context); .agent/kb/review/reports inventory via a.md + A18.txt cp commands.
- OPENED BUT NOT FINISHED: none.
- NEVER REACHED: the persisted lane-report FILES' contents (existence and
  provenance verified via cp commands + handoff inventory; bodies not re-read);
  the B/C/D/E/F transcripts beyond the B control greps; subagent transcripts of
  G's codex reviewer (its death is evidenced by g.md + G-transcript strings).
