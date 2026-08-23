# Refutation probe — "sweep run twice over the same window because run 1 was not durable"

Lane: refuter of the lane-circles finding (sweep re-run). Written as I go.

## Finding under test

"The session-review sweep itself is being run twice in ~36h over an overlapping
window because run 1's aggregation was not durable: F's 2026-08-17 fan-out (2
workflows, 17 reports, 554-line synthesis) swept issue TITLES only and filed no
issues, so the directive ordered the sweep rebuilt (#339) and re-run — the
current session is re-covering the same 13 transcripts with 6 lanes."

## Evidence gathered so far (2026-08-18)

1. `.agent/plans/session-2026-08-17-f.md:255-266` — CONFIRMS "Two background
   workflows, 17 reports on disk" BUT the 17 reports span TWO DIFFERENT
   workflows: `2026-08-17-session-review.md` (554 lines) + 7 per-agent reports
   is the session review; `2026-08-17-agent-memory-research.md` (274 lines) + 8
   per-agent reports is a DIFFERENT subject (agent-memory research). The
   finding's "2 workflows, 17 reports" attributes both to the session-review
   sweep — only ~8 of the 17 files belong to it.

2. `.agent/plans/session-2026-08-17-f.md:220-228` — F itself answered Ray's
   "rerun the review workflow so findings survive /clear?" with **"Not needed
   for capture"**: transcripts persist across /clear, and the synthesis "is now
   in work-memory, auto-memory and this file". What IS owed: sweep issue
   BODIES (titles only), read the 9 handoffs, resolve #2787/#2794. So the
   handoff cited AS evidence says the aggregation WAS captured durably.

3. `ls -la docs/research/reports/` (2026-08-18): `2026-08-17-session-review.md`
   (34,594 bytes, mtime Aug 17 22:43) and `2026-08-17-agent-memory-research.md`
   (25,119 bytes) ARE promoted into the tracked docs tree. NOTE: the finding's
   probe "grep session-review -> 2 files" does not reproduce — only ONE file in
   that dir matches "session-review"; the second promoted file is
   agent-memory-research (does not match the grep). Probe discrepancy in the
   finding's own evidence line.

4. `docs/direction/2026-08-18-ray-directives.md`:
   - :66-67 — "Then the session-review sweep, whose output is durable GitHub
     issues (and/or a wayfinder map), not a report." CONFIRMS re-run ordered
     with a NEW output contract.
   - :76 — "The workflow was rebuilt and committed this session
     (`.claude/workflows/session-review.js` + `kb-session-review` skill). It
     has NOT been run yet." (as of that writing)
   - :94-97 — ruling: output is GITHUB ISSUES.
   - :212-223 — NEXT SESSION'S FIRST TASK (Ray verbatim): "improving the
     session review workflow and running it to aggregate the list of issues …
     and applying it to the project". So the re-run is Ray-ORDERED, instrument
     rebuilt, output form changed.

5. Transcript window probe:
   `find ~/.claude/projects/-…-knowledge-base -maxdepth 1 -name '*.jsonl'
   -newermt "2026-08-17 00:00:00"` -> **14 files now** (control: 236 total
   .jsonl in dir). 10 have 08-17 mtimes (06:22..21:42); **4 have 08-18 mtimes
   (03:07, 03:09, 03:09, 06:17)** — those 4 DID NOT EXIST when run 1 executed
   (~21:42-22:43 on 08-17), so run 1 cannot have covered them. Settled count
   13 vs my 14: one transcript appeared since (consistent with the current
   fan-out writing subagent transcripts into the same dir).

## Decisive probes (all run 2026-08-18)

6. **Run 1's window ≠ run 2's window.**
   `docs/research/reports/2026-08-17-session-review.md:1,11-13` (the committed
   synthesis, its own header): "Session review — **14** Claude Code sessions,
   **2026-08-15 .. 2026-08-17** … exactly 14 files with mtime ≥ **2026-08-15**;
   the 15th (`497d5dcb`) is Aug 14 18:19."
   Run 2's window (settled by Ray): mtime ≥ **2026-08-17**, 13 transcripts.
   Overlap ≈ 10 transcripts (the 08-17-mtime ones); **4 of run 1's 14 (mtime
   08-15/16) are outside run 2, and ≥4 of run 2's set (mtimes 2026-08-18
   03:07/03:09/03:09/06:17) did not exist when run 1 wrote its synthesis**
   (`stat .agent/kb/reports/agents/2026-08-17-session-review.md` → mtime
   2026-08-17 16:24). "Re-covering the same 13 transcripts" is FALSE: run 2
   majority-covers material run 1 could never have seen — including the
   sessions that produced the directive, the addendum, and #338/#339.

7. **Run 1's aggregation IS durable — committed to main and APPLIED.**
   `git log --follow -- docs/research/reports/2026-08-17-session-review.md` →
   `37f6a1c5 feat model limits resolver (#336)`; `git merge-base --is-ancestor
   37f6a1c5 main` → yes; `git status` clean. The SAME commit applied run 1's
   fix #1: `mise.toml:84 gh = "2.97.0"` (git log -S gh → 37f6a1c5). Plus
   work-memory + auto-memory + the handoff (f.md:222-228 "Not needed for
   capture"). So "run 1's aggregation was not durable" is REFUTED for the
   aggregation itself; what was missing is the ORDERED OUTPUT FORM.

8. **"Filed no issues" CONFIRMED** — `gh issue list --state all --limit 60
   --json createdAt,...` (2026-08-18): newest issue is **#335,
   2026-08-17T17:04:43Z**, i.e. created BEFORE run 1's synthesis (16:24 is the
   .agent mtime; promotion 22:43); zero issues created after it. Control: the
   probe returned 40+ issues, so it sees issues; newest-first ordering means
   the --limit 60 bound cannot hide a newer one.

9. **"Swept issue TITLES only" CONFIRMED** — f.md:227-228: "sweep issue
   BODIES (it swept titles only)" — recorded by run 1 itself as an owed
   follow-up, alongside "read the 9 handoffs" and "#2787/#2794".

10. **The finding's own probe does not reproduce.**
    `ls docs/research/reports/ | grep session-review` → **1 file**
    (`2026-08-17-session-review.md`), not 2. The second promoted file is
    `2026-08-17-agent-memory-research.md`, which that grep cannot match.

11. **Rebuild + re-run ordered: CONFIRMED.** Directive :66-67 (output =
    durable GitHub issues, "not a report"), :76 (workflow rebuilt+committed,
    not yet run), :94-97 (ruling: GITHUB ISSUES), :212-223 (Ray's first-task
    ruling: improve the workflow, run it, file, apply). Commits: `2b364443
    feat session review workflow (#339)`, then `022e88f4 feat(session-review):
    bot-reviews and pending-work lanes, lane keys pinned` (this session's
    improvement, per the ruling).

## VERDICT: REFUTED AS STATED (core survives in narrower form)

The finding's two load-bearing claims fail on direct probes:
- **"because run 1's aggregation was not durable"** — the 554-line synthesis
  is merged to main (37f6a1c5/#336) and its first fix applied in the same
  commit; F's handoff itself says capture was durable. The true gap: no
  GitHub issues (ordered form) + titles-only dedup. The re-run is Ray-ordered
  forward work with a rebuilt instrument and a NEW output contract — directed
  iteration, not a circle from lost work.
- **"re-covering the same 13 transcripts"** — run 1 covered 14 files, window
  2026-08-15..17; run 2 covers 13-14, window ≥2026-08-17. ~10 overlap; each
  set has ≥4 members the other lacks; run 2's newest 4 postdate run 1
  entirely.
- Also misattributed: "2 workflows, 17 reports" folds the unrelated
  agent-memory-research workflow (274-line synthesis + 8 reports) into the
  sweep; the session review was 1 workflow, 554-line synthesis + 7 per-agent
  reports (f.md:255-266).

What SURVIVES: two sweeps ~36h apart with ~10-transcript overlap; run 1 filed
zero issues and swept titles only; the rebuild (#339) and re-run are
directive-ordered. The still-owed item run 1 named (issue-BODY sweep) remains
unclosed as of 2026-08-18 — that narrower fact is real and citable.

## Contradictions with other evidence

Other lanes' findings are not visible to this lane. But the finding
contradicts (a) its own cited file — f.md:220-228 answers "rerun so findings
survive /clear?" with "Not needed for capture"; (b) the committed synthesis
header's stated window (08-15..08-17, 14 files) vs "the same 13 transcripts";
(c) the settled-context window ("since 2026-08-17, 13 transcripts"), which is
run 2's window and provably not run 1's.

## COVERAGE

- REACHED AND ANALYSED: session-2026-08-17-f.md (full); the 2026-08-18
  directive (full, incl. addendum and clear-prep rulings); the promoted
  synthesis's first 120 lines (scope header + item 1); ls of
  docs/research/reports/; transcript-dir mtime census (14 files ≥ 08-17,
  control 236 total, run 2026-08-18); gh issue list (60 newest, --state all);
  git log/status for the promoted reports, the workflow, and the gh pin;
  exact reproduction of the finding's grep probe.
- OPENED, NOT FINISHED: the synthesis past line 120 (items 2+ not needed for
  this verdict); .claude/workflows/session-review.js (grepped lane scaffolding
  only — did NOT verify the "6 lanes" count).
- NEVER REACHED: the other six handoffs (b,c,d,e,g,2026-08-18-a) — not needed,
  since f.md and the directive carried the cited evidence; run 1's 7 per-agent
  reports; any .jsonl content (by rule, only stat/counted).
