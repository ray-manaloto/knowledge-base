# Refute: [circles] 20-agent session-review fan-out run TWICE over byte-identical inputs

Started. Probes below, appended as run.

## Probe 1 — the two Workflow tool_use inputs (verbatim)

`jq` over 6697269c-34d2-4355-948e-48b775449a73.jsonl, selecting tool_use name=="Workflow":
only TWO exist in the whole session.

- 17:20:58.835Z toolu_013M7VQTYKQdwaT8YrqCFPt1 args len 1517
- 18:25:45.034Z toolu_01AMRCp5679uWBSEohfJJPTW args len 2842

mode/handoffOut/transcriptDir/since/directive/handoffs/reportDir ARE identical.
`answered` differs (1517 vs 2842 chars). So the finding's parenthetical is accurate;
its headline word "byte-identical" is not.

## Probe 2 — the workflow PROGRAM changed between the runs

`git show --stat bc02fc96` -> committed 2026-08-18T12:53:28-05:00 = **17:53:28Z**,
strictly between the two launches, and it touches
`.claude/workflows/session-review.js  | 60 ++++++++++++++++++++++++++++++-`.
The second run therefore executed a DIFFERENT program. Not a re-run of the same thing.

## Probe 3 — the CHEAP ARM 21s earlier FAILED; it proved the defect, not the fix

18:25:24.694Z Bash:
  mkdir -p docs/session-review/runs/2026-08-18-2 && cp .agent/plans/session-2026-08-18-c.md
  docs/session-review/runs/2026-08-18-2/handoff-c-before-reconcile-fix.md &&
  mise run kb-handoff-check -- .agent/plans/session-2026-08-18-c.md > .../handoff-c-check-before.txt 2>&1
Result 18:25:25.868Z: `captured rc=1`
docs/session-review/runs/2026-08-18-2/handoff-c-check-before.txt tail:
  `20 OK, 6 ambiguous, 0 unverifiable, 2 broken   (only broken exits 1)`
It ran against RUN 3's output and FAILED. It cannot prove a composer fix -- it can only
check a handoff that already exists, and the only producer of a new handoff is the workflow.

## Probe 4 — the sweep INPUT was not the same corpus

Own-transcript records (timestamped lines) present in transcriptDir at each launch:
  run 3 launch 17:20:58.835Z -> 126
  run 4 launch 18:25:45.034Z -> 980   (delta +854, 7.8x)
Control arm on the find: `find . -maxdepth 1 -name '*.jsonl' -newermt "2026-08-18T00:00:00" | wc -l` -> 7 (discriminates).

## Probe 5 — the git subject matter under review changed: 6 commits

`git log --format='%h %cI %s' d7e344f8..a94578cb`:
  a94578cb 2026-08-18T13:17:38-05:00 docs: the correction was wrong too
  bb19a0ec 2026-08-18T13:15:33-05:00 feat(handoff): fail a handoff that dropped the previous backlog
  b7b460c0 2026-08-18T12:59:15-05:00 docs: correct a false premise
  34070912 2026-08-18T12:57:47-05:00 docs(direction): Ray's four artifact comments verbatim
  bc02fc96 2026-08-18T12:53:28-05:00 fix(session-review): the composer never saw the previous handoff
  3fe8e800 2026-08-18T12:30:01-05:00 feat(hook): deny a probe whose command word is not installed

## Probe 6 — NO compose-only path existed, so no cheap arm could prove the fix

`git show bc02fc96:.claude/workflows/session-review.js`:
  L341  const ACTIVE_LANES = MODE === 'handoff' ? LANES.filter((l) => HANDOFF_LANES.has(l.key)) : LANES
The composer runs only after the sweep. There is no `composeOnly` / `reuse` / lane-skip
argument anywhere in the file. Re-running the composer REQUIRES the fan-out.

## Probe 7 — the rerun's output PASSED where run 3's FAILED

Post-rerun gate, 18:58:27Z Bash `mise run kb-handoff-check > /tmp/hc.log`, result 19:01:06.756Z:
  rc=0
  no broken citations in .agent/plans/session-2026-08-18-c.md
  50 OK, 0 ambiguous, 0 unverifiable, 0 broken   (only broken exits 1)
vs the pre-rerun `captured rc=1` / `20 OK, 6 ambiguous, 0 unverifiable, 2 broken`.

## Probe 8 — the nine dropped owed items: 0 before, all present after

before = docs/session-review/runs/2026-08-18-2/handoff-c-before-reconcile-fix.md (10,570 B)
after  = .agent/plans/session-2026-08-18-c.md (18,172 B)
  18-name 0->1 · roster 0->4 · rumdl 0->3 · betterleaks 0->3 · kingfisher 0->3
  agent-harness-docs 0->2 · hk-builtin 0->3 · staleness 0->3 · MAX_ITERATIONS 0->2
CONTROL ARM on the same grep shape against the before file: handoff=7, kb-review=3,
commit=8, graphify=8, issue=10 — the probe discriminates, the zeros are real.

## VERDICT: REFUTED

- "byte-identical inputs" is false three ways: args differ (finding concedes),
  the PROGRAM differed by 60 lines committed 32 min before the relaunch, and the
  transcript corpus the sweep reads grew 126 -> 980 records.
- "existed solely to re-prove a composer fix" is false: run 3's deliverable had
  FAILED its gate 21 s earlier; run 4 was the only route to a passing handoff.
- "The cheap arm had already been run 21 seconds earlier" inverts what that arm
  showed. It exited 1. It proved the defect, not the fix.

CONTRADICTS finding 5: the nine owed items finding 5 reports as "carried a third
consecutive time" are exactly the items run 3 dropped and run 4 restored. Finding 5
is only observable BECAUSE run 4 ran.

SURVIVING NARROWER CLAIM (not the one judged): 20 agents were re-run to exercise a
fix confined to the ONE composer agent, because the workflow has no compose-only
re-entry point. That is a real tooling gap and is worth its own ticket.

## GitHub repos touched

_None._
