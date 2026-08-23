# refute — [circles] "run 1's lane reports DESTROYED IN PLACE by a FLAT filename"

SHA under review: HEAD = d7e344f8 (branch docs-directive-addendum)

## Confirmed so far (primary artifact)
- `.claude/workflows/session-review.js:200` — `const reportDir = cfg.reportDir || '.agent/kb/reports/agents'`
- `.claude/workflows/session-review.js:236` — ``Write your findings to ${reportDir}/<your-lane>.md AS YOU GO``
  => the lane filename is flat WITHIN reportDir. But reportDir is a PER-INVOCATION cfg key, not a constant.

## Live sizes/mtimes (stat -f '%z %Sm %N' -t '%Y-%m-%d %H:%M:%S', run 2026-08-18)
17822 13:36:29 circles.md      (finding said 1,096)
16778 13:31:37 forgotten.md    (finding said 16,778 — matches)
16373 13:33:24 contradicted.md (finding said 5,902)
24832 13:36:49 bot-reviews.md  (finding said 871)
16538 13:36:58 pending-work.md (finding said 1,180)
12775 06:23:26 tooling-gap.md  (run-1 survivor)
12363 06:23:31 unpinned.md     (run-1 survivor)
11497 06:20:50 context.md      (run-1 survivor)
=> the finding's small sizes were a snapshot of an IN-FLIGHT run-4 write.

## iter1/ mtimes are STAGGERED, docs/ copy is UNIFORM
.agent/kb/reports/agents/iter1/: 09:51, 09:53, 09:55, 09:56, 09:57, 09:59, 10:01, 10:06..10:21
docs/session-review/runs/2026-08-18-1/: ALL 10:23
=> staggered == agents writing directly (reportDir was configured to iter1); uniform == the cp.
=> "Run 2 survives ONLY because a human hand-copied it to iter1" looks FALSE. Verifying next.

## REFUTATION 1 — "Run 2 survives ONLY because a human hand-copied it to iter1/"  => FALSE
Run 2 was LAUNCHED with a run-scoped reportDir. Probe (in ~/.claude/projects/-Users-...-knowledge-base):
  grep -h '"2026-08-18T14:49:2' f1d1c0cf*.jsonl | grep -o 'reportDir[^,}]\{0,60\}'
  -> reportDir\": \".agent/kb/reports/agents/iter1\"
CONTROL (same probe, other launches — proves it discriminates):
  17:20:58 -> reportDir\":\".agent/kb/reports/agents\"    (run 3, flat)
  18:25:45 -> reportDir\":\".agent/kb/reports/agents\"    (run 4, flat)
  11:10:24 -> (no reportDir key; run 1 used the default)
Corroborated by run 2's OWN coverage line (same transcript, task wtf93gqvu, 15:21:54.694Z):
  "All findings written incrementally to .agent/kb/reports/agents/iter1/circles.md (28,782 B) as they were derived."
=> reportDir is a per-invocation cfg key (session-review.js:200). Isolation is SUPPORTED and WAS USED.
   The overwrite is an operator choice of reportDir on runs 3/4, not a workflow that "writes to a FLAT filename".

## REFUTATION 2 — the 271,666 B figure is misattributed
Source of the number, verbatim from run 2's circles coverage line:
  "The other 33 run-1 reports (bot-reviews.md, pending-work.md, unpinned.md, context.md, contradicted.md
   and 28x refute-*.md; 271,666 B total) - existence and sizes confirmed, CONTENTS UNREAD."
=> 271,666 B = 5 lane reports + 28 refuter reports. 28 of the 33 SURVIVE (the finding's own evidence line
   counts 31 files / 207,325 B surviving). Actual bytes lost = 14,916+14,439+13,847+11,726+9,413 = 64,341 B.
   271,666 - 207,325 = 64,341 exactly.

## REFUTATION 3 — "never read" is contradicted by the same coverage line
Run 2's circles lane, opened_not_finished: "run-1's .agent/kb/reports/agents/circles.md - read only its
12 headings plus lines 78-96 ... forgotten.md and tooling-gap.md - headings only."
=> run-1 reports WERE read (partially) by run 2. Not "never read".

## REFUTATION 4 — the source of 271,666 says "36 markdown files", not "lane reports"
docs/session-review/runs/2026-08-18-1/circles.md:249-254
  "Run 1 wrote **36 markdown files, 271,666 bytes**, into ... (circles.md 14,916 B, bot-reviews.md 14,439 B,
   pending-work.md 13,847 B, tooling-gap.md 12,775 B, unpinned.md 12,363 B, contradicted.md 11,726 B,
   context.md 11,497 B, forgotten.md 9,413 B) plus **28 refute-*.md**"
8 lane reports = 100,976 B; 28 refuters = 170,690 B. Overwritten = 64,341 B (5 lane files).
Issue #341 body uses the same figure correctly: "Run 1 ...: 271,666 bytes across 36 files, stranded."

## REFUTATION 5 — "#341 does NOT cover this" is overstated
#341 body (gh issue view 341 --json body): proposes "the run-ledger design Ray asked for - reports stored in
git with a TIMESTAMP and the workflow's git SHA", and fix option 1 "requires a tracked reportDir and promotes
at the end (partially done by hand for run 2 -> docs/session-review/runs/2026-08-18-1/)".
A timestamped per-run directory IS the overwrite fix. #341 also names iter1 as a reportDir in its Evidence
section ("git check-ignore -v .agent/kb/reports/agents/iter1"), i.e. it already knows run 2 was isolated.

## Not refuted (the surviving kernel)
- The DEFAULT reportDir is flat and runs 3+4 reused it, so 5 run-1 lane reports (64,341 B) were overwritten.
- Those bytes are unrecoverable: no subagent Write payloads exist in any transcript.
  Probe: grep -c '"isSidechain":true' *.jsonl -> 0 in 7604bd97 (run-1 host) AND 0 in 6697269c / f1d1c0cf,
  which DID run subagents -> the probe returns 0 even for known-subagent sessions, so absence is real.
- Run 1's lane reports were never promoted to git (git log --all -- 'docs/session-review/**' shows only
  2b7bd6ca + 1c926e9d, and 2b7bd6ca's 21 files are run 2's, mtimes 09:51-10:21 in iter1/).

## VERDICT: REFUTED
Mechanism misattributed (operator reuse of a configurable reportDir, not a workflow that forces a flat name),
headline number overstated 4.2x (271,666 vs 64,341), "hand-copied to iter1" false, "never read" false,
"#341 does not cover this" false, and the quoted "current" sizes were an in-flight snapshot already stale.
