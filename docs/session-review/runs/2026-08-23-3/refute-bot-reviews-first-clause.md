# Refute attempt — bot-reviews / FIRST_CLAUSE (in progress)

CLAIM: graphify-labs' FIRST_CLAUSE finding on PR #347 ("collapses real coverage
gaps to 'none'") is a LIVE, un-dispositioned bug in the CURRENT session-review.js.
"None, several items require follow-up" (or ';'/':' after None) -> classified clean.

## Probe 1 — the code, at HEAD ff299734
`grep -n` -> FIRST_CLAUSE at .claude/workflows/session-review.js:633,
saysNothing 634-637, isPartial 638-641. Cited range 633-636 is accurate.

`git blame -L 610,645` -> lines 615, 617-637, 640 authored by dcd0b07f
(= PR #347 itself). No later commit touched them. `git log --follow` on the file:
ff299734, dcd0b07f, 2b364443 only.

## Probe 2 — reproduction from the file's OWN bytes (not hand-typed)
sed -n '615,641p' session-review.js > pred.js, appended a case table, ran node:

"None, several items require follow-up"              saysNothing=true | isPartial=false
"None; several items require follow-up"              saysNothing=true | isPartial=false
"None: several items require follow-up"              saysNothing=true | isPartial=false
"None. But three telemetry files were never opened"  saysNothing=true | isPartial=false
"None — this lane is scoped and complete."           saysNothing=true | isPartial=false
"none."                                              saysNothing=true | isPartial=false
"None of the telemetry was reached"                  saysNothing=false | isPartial=true
"Three items opened but not finished"                saysNothing=false | isPartial=true
""                                                   saysNothing=false | isPartial=true

CONTROL ARM (same run): the last three rows return the OPPOSITE answer, so the
probe discriminates. It is not a predicate that can only say "clean".

## Probe 3 — the bot finding exists and was escalated
gh api .../pulls/347/reviews -> graphify-labs[bot] review 4965545610 (20:38:15Z)
body line 200: "**FIRST_CLAUSE regex collapses real coverage gaps to 'none'** —
`.claude/workflows/session-review.js` · _Escalate · medium_ ... agreed by 2 of 2
members but NOT verified ... needs human review".
Also review 4965402541 line 22, earlier wording.

Still to check: any DISPOSITION anywhere; whether real lanes emit the shape.

## Probe 4 — disposition search (the strongest refutation angle, and it failed)
FIRST TRY WAS A BROKEN PROBE, recorded because it is the exact failure this role
guards: `grep -rn "FIRST_CLAUSE" .` returned ONLY session-review.js. `type grep`
shows grep is a shell FUNCTION wrapping ugrep with `--ignore-files`, i.e. it
honours .gitignore and silently skipped all of `.agent/`. Re-run with
`command grep -rn` (real /usr/bin/grep):

  ./.claude/workflows/session-review.js
  ./.agent/kb/review/reports/review-7914e97b…-cold.md
  ./.agent/kb/reports/agents/bot-reviews.md
  (+ .agent/telemetry/*.request.json — LLM request bodies, not dispositions)

No issue: `gh issue list --state all --search "FIRST_CLAUSE"` -> 0 rows;
control `--search "session-review"` -> 5 rows (#344/#340/#376/#352/#343), so the
search discriminates. No commit: `git log --follow` on the file = ff299734,
dcd0b07f, 2b364443; blame puts 633-636 on dcd0b07f (PR #347 ITSELF), untouched
since.

The two things that WERE fixed nearby are different bugs:
- review-7914e97b-cold Finding 4 (P2) = the `says` LOGGER using a different
  predicate. Fixed; confirmed at review-a1333244-cold:52.
- the empty-string default (comment 629-632) = `''` stays PARTIAL. Also different.
Neither report anywhere mentions the comma/semicolon/colon shape.

## Probe 5 — wrong-artifact check (the running copy, not just the repo copy)
`find` over ~/.claude/projects + the repo (control: kb-extract.js found) locates
the snapshot this round actually executes:
  …/773421d1-…/workflows/scripts/session-review-wf_6dc52381-5b8.js (Aug 19 13:52)
`diff <(sed -n '584,610p' RUNNING) <(sed -n '615,641p' REPO)` -> PREDICATE REGION
IDENTICAL. Control: `diff` of lines 300-304 -> differs (the repo copy has newer
prompt text). So the bug is in the copy this very round runs under, not only in
the repo's working tree.

## Probe 6 — how far the misclassification travels (nuance, not refutation)
`interrupted` feeds: the `PARTIAL COVERAGE —` log (665), `PARTIAL LANES:` in both
REPORT_PROMPT (895) and HANDOFF_PROMPT (1018), and `partial_coverage` in the
returned object (1031). BUT lines 893/1017 also pass the RAW coverage object to
both prompts, so the text "None, several items…" is not hidden from the synthesis
model — only from the classification, the log line and the artifact field.

## Probe 7 — has it fired on real data? (also nuance, not refutation)
Ran the file's own predicate over docs/session-review/runs/2026-08-18-1/run.json:
all 7 lanes -> isPartial=true (correct). `unpinned`'s opened_not_finished is
"None — this lane is scoped and complete." (saysNothing=true) but its
never_reached is prose, so the lane still lands partial. No recorded run has yet
been misclassified. The defect is present and reachable, not yet observed firing.

## VERDICT: NOT REFUTED.
