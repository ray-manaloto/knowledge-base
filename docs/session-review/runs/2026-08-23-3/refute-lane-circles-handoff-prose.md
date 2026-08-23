# Refutation lane — "handoff prose re-verified or inherited wrong" (lane circles)

Task: refute the finding if possible. Working notes, incremental.

## Sources read IN FULL

- docs/direction/2026-08-18-ray-directives.md (233 lines)
- .agent/plans/session-2026-08-17-{b,c,d,e,f,g}.md, session-2026-08-18-a.md (all, complete)

## Sub-claim anchors found by reading (file:line)

- 'Complexity is NOT the obvious cause' — b:82-87, bounded to "the four modules this
  round changed" at threshold 6, flags 2 functions, ends "Do not assume #325's cause".
- The correction — c:121-144: "That was wrong, and complexity WAS the cause...
  threshold 6 over those four modules flags **nineteen** functions... including
  `adapter_main`, then at 9". c:98-108: Repowise detail page "named exactly one
  function: `adapter_main`, cyclomatic 9... carrying the entire -0.1"; fix commit
  84a7408d flipped Repowise failure→success measured via gh api (c:92-93).
- Codex quota — b:11 + b:232 "depleted until 2026-08-19 22:29"; c:171-173 "Codex
  quota is BACK... live `codex exec --ephemeral --sandbox read-only` probe returned
  a real answer. Probe it, do not inherit the exhaustion date." Later: g:68-69 codex
  hit limit again mid-#336 (resets 2026-08-19 22:29); a:117 out of credits all session.
- RE-PLAN LAST — b:146, c:156 ("still holds... re-confirmed"), d:79 ("Carried
  forward... NOT to be rediscovered"), a:99 ("RE-PLAN LAST, and a review round is a
  code change"). e:122 "Re-planned and re-authorized twice", g:95 "re-planned FIVE
  times" (phrase absent, practice restated).
- timeout not on PATH — b:181-182 (discovery), c:174-175 ("Re-confirmed this
  session"), d:235-236 ("still not"), e:155 ("still not"). Absent f/g/a.
- tmux leak — b:261, c:293, d:284, e:202 (identical line, `kbprobe-injected-42117`,
  "since 2026-08-11"). Absent from f, g, a — dropped after e.
- currency drift — d:72-75 + d:279-282 ("real drift I did NOT act on"),
  e:200-201 ("drift unactioned"), f:173-179 (0.9.46 "fully investigated, nothing
  applied... Ray's ruling: bump now... not started") + f:47 (Ray deferred),
  g:57-59 ("Still deferred by Ray, deliberately"), a:126-133 ("Currency, ALL EIGHT
  behind pins"). Directive 2026-08-18 lines 45+60-65: hard gate, 8 pins behind.

## Verification probes, as run (2026-08-18)

1. `grep -n "RE-PLAN LAST" <7 handoffs>` → exactly 4: b:146, c:156, d:79, a:99.
   Paraphrase restatements besides: e:122 "Re-planned and re-authorized twice",
   g:95 "re-planned FIVE times". Absent-token control rc=1 → probe discriminates.
   Sub-claim "4+ handoffs" CONFIRMED (exactly 4 with the phrase).
2. `grep -n "not on PATH"` → 4 handoffs: b:181, c:174, d:235, e:155. Transcript
   sweep over /Users/rmanaloto/.claude/projects/-Users-rmanaloto-dev-github-ray-manaloto-knowledge-base,
   `find -newermt 2026-08-17` = 14 files (control `-newermt 2030-01-01` = 0;
   present-string control 'kb-session-reflect' = 28 hits):
   'command not found: timeout' in 4 distinct transcripts (mtimes 08-17 06:22,
   09:55≈c, 21:42≈g, 08-18 03:07=a) + 'which timeout' ×2 in 14:09≈e.
   "Re-probed at least twice" is an UNDERCOUNT: ≥4 re-encounters after b's
   discovery, and g/a still tripped on it AFTER the line was dropped from
   the handoffs. CONFIRMED (stronger than stated).
3. tmux leak: grep → identical line in b:261, c:293, d:284, e:202; zero mentions
   in f/g/a (reboot/restart grep also empty there; control 'branch'=2). Live
   probes: `tmux -L kbprobe-injected-42117 list-sessions` → "error connecting…
   No such file or directory"; `/private/tmp/tmux-501/` holds only `default`
   (Aug 17 17:08); `pgrep -lx tmux` → 28366 (default server, 5 omc-* sessions).
   `sysctl kern.boottime` → **Mon Aug 17 14:42:19 2026** — the machine REBOOTED
   between e (14:05) and f (17:27), which is what cleared the leaked server.
   No fixing action ever occurred: `git log --all --since=2026-08-11 -S kbprobe`
   and `--grep=tmux` both empty (controls: `git grep kbprobe` finds the leaking
   test at tests/test_launch.py:347-350, whose cleanup is `tmux kill-session`
   with check=False; dotfiles `git grep -l tmux` hits 5 files).
   "Silently dropped unfixed" CONFIRMED, with a NUANCE: at f-time the server was
   already gone (reboot), so the dropped item was stale — but the drop was
   unexplained and no one fixed or even re-probed it, which is the finding's
   thesis in miniature.
4. currency drift: restated d:74+279-282 ("did NOT act on"), e:200-201
   ("unactioned"), f:47+173-179 ("fully investigated, nothing applied…not
   started"), g:57-59 ("Still deferred by Ray, deliberately"), a:126-133.
   Second route: `git log --since=2026-08-16 -- mise.toml pyproject.toml uv.lock
   currency.toml` → only #330/#331/#336/#338, none advancing the behind pins
   (#336 added NEW pins gh + anthropic), and the directive's own 2026-08-18
   kb-currency-check (directive:60-65) still reports ALL EIGHT behind, post-dating
   every commit in the window. CONFIRMED. NUANCE: in f and g the non-action was
   Ray's explicit deferral, not session neglect.
5. codex: b:11+232 "depleted until 2026-08-19 22:29"; c:171-173 records the live
   `codex exec --ephemeral --sandbox read-only` probe returning a real answer —
   "Probe it, do not inherit the exhaustion date." Historical, not re-runnable;
   the artifact is explicit and the finding cites it accurately. NUANCE: the same
   reset stamp recurs at g:68 and a:117 (codex re-depleted later), so b's DATE was
   the true window reset; what c refuted was "unusable until then". CONFIRMED as
   an inherit-vs-probe case.
6. complexity/adapter_main: b:82-87 is the bounded list (threshold 6, four
   changed modules, 2 functions, "Do not assume") filed under "What I already
   checked, so you do not repeat it"; c:121-144 is the correction (NINETEEN at
   threshold 6; adapter_main then at 9). Three independent recorded routes agree
   adapter_main=9 was the Repowise cause: the detail page (c:103), the ruff
   second probe (c:104-105), and the fix flipping Repowise failure→success read
   from `gh api …/check-runs` (c:92-93). `git show --stat 84a7408d2680` verified:
   "reduce adapter_main's complexity and arm the refusal path it hid", touches
   graphify_semantic_adapter.py; 7a89a4b7 "state the threshold the complexity
   probe was run at" also exists. Decisive arithmetic needing no re-run: 9 > 6,
   and adapter_main lives in one of b's four modules, so b's own stated
   parameters make its two-row list impossible-as-complete. CONFIRMED.

## Verdict

NOT REFUTED — confirmed on every sub-claim; two probes of each fact agree by
independent routes. The only genuinely bounded probe found anywhere in this
story is b's own four-module threshold-6 list — which is the finding's subject,
not its defect. Three nuances (reboot mooted the tmux symptom before the silent
drop; codex re-depleted later on the same reset stamp; f/g currency inaction was
Ray's explicit deferral) adjust color, not substance.

Cross-finding contradictions: no other findings from the set were provided to
this lane; nothing in the settled block, MEMORY, the directive, or any probe run
here contradicts this finding.

## COVERAGE

- REACHED AND ANALYSED IN FULL: docs/direction/2026-08-18-ray-directives.md
  (233 lines); all seven named handoffs b/c/d/e/f/g/18-a (complete reads);
  grep sweeps with controls over those handoffs; live tmux/socket/boottime
  probes; git log/-S/grep probes in both repos with controls; commit existence
  checks (84a7408d, 7a89a4b7); transcript-signature counts over all 14
  in-window .jsonl (grep-only, never read into context); tests/test_launch.py
  lines 320-374.
- OPENED BUT NOT FINISHED: none.
- NEVER REACHED: re-running ruff C901 at the historical tree 398c7b87 to
  re-count c's "nineteen" (the check_first hook denies hand-chained ruff, and
  the arithmetic + three recorded routes made it unnecessary); the identity of
  the 06:22 transcript with a timeout signature (counted, not attributed);
  the other findings in the lane's set (not provided to me).
