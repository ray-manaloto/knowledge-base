# Refutation probe — pending-work finding: salvage/skillopt-heldout-evaluation{,-v2}

Claim: "genuinely unlanded pending work with NO TRACKING ISSUE; v2 is the fuller
draft and is NOT a git ancestor of v1's commit"

## Confirmed sub-claims
- Files absent from origin/main (control: cli.py/mise.toml PRESENT):
  skillopt_eval.py ABSENT, skillopt/evaluation/neutral-skill.toml ABSENT,
  .claude/skills/neutral-team-workflow/SKILL.md ABSENT, tests/test_skillopt_eval.py ABSENT.
- Ancestry: NEITHER is an ancestor of the other.
  `git merge-base --is-ancestor v1 v2` rc=1 ; `--is-ancestor v2 v1` rc=1
  control: `--is-ancestor origin/main docs-directive-addendum` rc=0 (probe discriminates).
  NOTE: the offered evidence ran only the v1->v2 direction, which is NOT the
  direction the claim states. Right answer, wrong probe.

## REFUTED sub-claim: "no tracking issue"
Issue **#124 OPEN** "How do we MEASURE whether a skill works? (SkillOpt / SkillLens / plugin-eval)"
label wayfinder:research, updated 2026-08-13T09:11:29Z.
Its comment (2026-08-13T09:11:29Z, sortakool) says "This issue is now a hard
completion gate for the active cross-repository goal" and required acceptance #4:
"Harvest -> mine -> replay -> reflect -> **held-out gate** -> stage -> human-reviewed
adopt ... immutable receipts" — i.e. the held-out gate AND the provenance/receipt
work these two branches implement, filed hours before commit e3577ac3 (2026-08-13 09:37 -0500).

The original probe could only have returned empty:
  `gh issue list --state all --search "skillopt heldout"` -> 0
  `gh issue list --state all --search "neutral-team-workflow"` -> 0
  CONTROL `--search "skillopt"` -> 11 issues incl. #124
  CONTROL `--search '"held-out"'` -> #124
"heldout" is spelled **held-out** in the issue; the two-token AND query is a
token-spelling bound.

## Context that strengthens the refutation
- The branches sit directly on top of the landed SkillOpt line of work:
  v1's merge-base with main is 10ad4220 "feat: add reviewed SkillOpt adapter (#285)"
  (2026-08-13 09:02 -0500; commit 35 min later), v2's is c1891cb9 "Add immutable
  artifact receipt workflow (#286)" (11:50; commit 14 min later).
  #284/#285/#286 all merged 2026-08-13. The salvage commits are the NEXT increment
  of a line that was actively landing that day, not orphan work.
- main's own code names the gap: python/src/kb_setup/skillopt_reviewed.py:890
  `certification="none_no_adoption_or_heldout_claim"` and :792 writes
  `heldout-test-tasks.json` — main stages the held-out split and disclaims the
  claim; the salvage branches implement the gate that closes it. That is #124
  acceptance item 4 verbatim.
- Only two refs anywhere carry skillopt_eval.py (control: cli.py in 31 refs),
  so nothing else preserves this work — unlanded is TRUE.

## Second defect in the offered evidence
"v2 is the fuller draft" is measured against different merge-bases, so the
file-set comparison is contaminated: artifact_download.py / fetch_receipt* /
schemas appear "only in v2" because v2 is based on #286, not because v2 authored
them. On authored delta: v1 = 8 files / 1,191 ins (skillopt_eval.py 737 lines),
v2 = 13 files / 1,546 ins (skillopt_eval.py 960 lines). v2 is fuller for the
shared file but is NOT a superset — v1 carries
skillopt/evaluation/historical-task-authority.json which v2 drops.

## VERDICT: REFUTED (the "no tracking issue" clause)
Unlanded: TRUE. Not-an-ancestor: TRUE (though probed in the wrong direction).
No tracking issue: FALSE — #124 is open, is declared a hard completion gate, and
enumerates the held-out gate as required acceptance.
