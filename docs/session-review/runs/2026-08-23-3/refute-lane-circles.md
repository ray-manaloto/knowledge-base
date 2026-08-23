# Refutation probe — "lane circles" finding (review fix->blocker treadmill)

Verifier lane: refute-lane-circles. VERDICT: **REFUTED as quantified** — the
treadmill kernel is real (#331, #337), but both headline numbers and one of the
three exemplars are contradicted by the finding's own cited probes.

## Claim-by-claim

### 1. "on 3 of 4 PRs the cold review ran 3 rounds against a 2-round bound" — REFUTED

Exactly ONE in-window PR ran 3 review rounds: **#331** (session b; b.md:98-111,
"three rounds ... against `kb-review`'s bound of two — Ray ruled it explicitly").

The opposite-answer probe is reading the third report file of each other PR
instead of counting files:

- `review-888df6d0...-cold.md:1-6` (#337): "**No lane re-ran** against
  888df6d0 — the skill bounds this review at two rounds, and round 2 was the
  second." Lane history table: round 1 (7fc5b5e6, 6 findings), round 2
  (3b25a89e, 5 findings). **Two rounds.**
- `review-8751b54e...-cold.md:1-6` (#339): identical wording; round 1
  (7c294a15, 5 findings), round 2 (57279105, 4 findings). **Two rounds.**
- #338: only TWO report files exist (61fa3616, 2c510e52 —
  session-2026-08-18-a.md:157-158), and round 1 was cut off by a Google
  content-policy refusal (visible at review-61fa3616...-cold.md:3).
- #336 (session g, also in-window): 3 files = round 1 (watchdog-killed at codex
  quota) + fix round + policy change; coverage PARTIAL, 9 modules unreviewed
  (g handoff:66-78). Not a 3-round treadmill either.

The probe `ls -la reports/` counts FILES; a fix round leaves a file that is not
a review round, so the probe can only over-count rounds. Under any choice of
"the 4 PRs" ({331,337,338,339} or {336,337,338,339}), the true count is 1 of 4
or 0 of 4, not 3 of 4.

### 2. "#331 rounds 2 and 3 each found a blocker CREATED by the previous fix" — CONFIRMED

session-2026-08-17-b.md:109-111, verbatim, at exactly the cited lines. In scope
(those reviews sit inside transcript de3c5d58, mtime 2026-08-17 06:22).

### 3. "#337 two of round 2's five findings were made by round 1's fix" — CONFIRMED

Round 2 report (review-3b25a89e...-cold.md) findings 1-2 are defects in the
splitlines+shlex tokenising decide() — the mechanism round 1's fix introduced
(the guard was "re-written to TOKENISE with shlex", A18 handoff #337 row); the
fix-round report confirms 5 findings in round 2. Auto-memory
`a-second-review-round-finds-what-the-first-fix-broke` records the same.

### 4. "#338 shipped a bot-found post-merge defect fixed as 11c783b0" — REFUTED (mis-attribution)

`git log --all --follow --format='%h %ad %s' -- python/src/kb_setup/check_first.py`:

    11c783b0 2026-08-18 03:26:54 -0500 fix(check-first): give the -- separator its own branch so the hook cannot hang
    e8f7f4ea 2026-08-17 22:43:21 -0500 feat kb check guard (#337)

Only TWO commits ever touched the file. The defect shipped in **#337**
(e8f7f4ea IS the #337 squash — its subject says so); #338 (791f53c2) never
touched check_first.py. The finding's own evidence string
("git log --follow ... -> 11c783b0, e8f7f4ea") contains the refutation.
11c783b0 sits on docs-directive-addendum (parent 3d957f15), committed by the
current session's post-merge bot triage. The event is real; the PR is wrong.

### 5. "Review+fix consumed ~4h17m of A18's 4h55m (lane reports 22:29->02:46)" — session length CONFIRMED, "consumed" REFUTED

- A18 = transcript 52f5798a: 2026-08-18T03:12:35Z -> 08:07:48Z = local
  22:12:35 -> 03:07:48 = **4h55m13s**. Confirmed.
- Lane report mtimes (stat, local): 22:18:24, 22:29:35, 22:36:51 (#337);
  23:21:02, 23:30:10 (#338); 01:47:22, 02:42:00, 02:46:50 (#339). The finding's
  window start (22:29) is #337 ROUND 2 — it missed the 22:18:24 round-1 report,
  consistent with counting mtimes without reading files.
- **There is a 2h17m12s report-free gap 23:30:10 -> 01:47:22** inside the
  claimed "consumed" window. Per session-2026-08-18-a.md ("What shipped", "What
  the corpus run actually established"), that gap held: #338 ship+land, TWO
  chunk-1 corpus runs (~11 min inference each) + the drift analysis, the
  durable spend-ledger build, the session-review workflow + skill build, the
  blanket-git-add deny build, and the directive recording — all #339 payload or
  corpus work, none of it review+fix.
- Actual lane-report cluster spans: 18m27s + 9m08s + 59m28s = **1h27m**. Even
  the most generous review+fix accounting (session start -> 23:30 plus
  01:47 -> 02:46 plus #339 lane runtime) reaches ~2.3-2.5h, roughly HALF the
  claimed 4h17m.
- The probe (first-to-last report mtime) could only ever produce ~the session
  length: the round STARTED with a review task (g handoff NEXT item 1) and
  ENDED with a pre-ship review, so the span is the session by construction. A
  probe that can only say yes.

### 6. "~2.5h of B's 8h46m" — numerator plausible, denominator wrong

- 8h46m = transcript de3c5d58 (02:36:46Z -> 11:22:39Z = 8h45m53s). But the b
  handoff was written 01:39:26 local — **4h43m before that transcript ends** —
  while every other handoff (c,d,e,f,g,A18) lands within minutes of its
  transcript's end. So de3c5d58 spans round b AND most of round c. Round b
  (handoff-to-handoff) = 21:36 -> 01:39 = **~4h03m**.
- Review+fix in b: session start 21:36 -> last report 23:59:48 (reports
  22:41:28 / 23:13:29 / 23:56:26 / 23:59:48, incl. closing the 8 inherited
  findings before round 1) = ~2h23m = "~2.5h" — plausible. But that is ~60% of
  round b, not ~28% of an 8h46m session. The error UNDERSTATES b's treadmill
  share by inflating the denominator with round c's hours.

## Internal contradiction

The finding's two cited probes contradict its two headline claims: the mtimes
listing shows #338 with two reports (and 22:18:24 as the true first report),
and the git-log output's own second line names "(#337)" as the shipping commit
of the 11c783b0 defect. No sibling lane findings were provided to me to
cross-check; the self-contradiction stands on its own.

## What survives (do not lose this)

The fix->blocker treadmill KERNEL is real and already recorded: #331 ran 3
rounds with rounds 2+3 each finding a blocker created by the previous fix
(b.md:109-111, Ray ruled it), and #337's round 2 found 5 findings of which 2
were created by round 1's fix. The 2-round bound then HELD on #337/#338/#339.
A defensible restatement: "1 of 5 in-window PRs exceeded the 2-round bound
(#331, Ray-ruled); on #337 the fix->new-finding pattern recurred within the
bound; #337 additionally shipped a bot-found post-merge defect (11c783b0).
Review+fix occupied ~2.4h of round b (~60%) and roughly 1.5-2.5h of A18's
4h55m."

## COVERAGE

- REACHED AND ANALYSED: docs/direction/2026-08-18-ray-directives.md (full); all
  7 named handoffs (full); all 40 report mtimes; git history of check_first.py
  and commit 11c783b0 (--all); first/last timestamps of every transcript in
  ~/.claude/projects/-...-knowledge-base (window members identified by span);
  headers + lane-history tables of 4 reports (#337 r2, #337 fix, #338 r1,
  #339 fix).
- OPENED BUT NOT FINISHED: those 4 reports read to line 30-40 only (enough for
  round counts and lane history; finding bodies beyond that unread).
- NEVER REACHED: #336/#331 report bodies (relied on handoffs g/b inventories);
  transcript CONTENT (deliberately — only head/tail timestamp lines extracted);
  GitHub API (PR<->commit mapping taken from squash subjects and handoffs, no
  network).
