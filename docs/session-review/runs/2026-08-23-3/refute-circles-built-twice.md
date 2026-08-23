# Refutation lane: "two enforcement mechanisms were built twice" (lane circles)

Status: IN PROGRESS. Written incrementally per agent-report-persistence.md.

## The finding under test

1. check_first: pattern-matching v1 (session G, 7fc5b5e6) -> shlex rewrite (#337)
   "after false positives of a class ALREADY DOCUMENTED in mise-tasks-only.md"
   -> third patch 11c783b0.
2. Spend cap: in-process accumulator (#336) -> durable spend-ledger (#339) after
   the $100 cap reset on every restart.

## Probes run so far

- `git log --all --oneline --follow -- python/src/kb_setup/check_first.py`
  -> ONLY `11c783b0` and `e8f7f4ea` (#337 squash). 7fc5b5e6 is ABSENT from all
  reachable refs' history of this file.
- `git show --stat 7fc5b5e6` -> exists in object store: "feat(guard): deny a
  hand-chained gate" Aug 17 21:26:03 2026, creates check_first.py (86 lines),
  +19 lines to mise-tasks-only.md. Its own message already says "SCOPE, narrow
  on purpose, because every measured defect in this repo's guards has been a
  false positive and never an evasion" — the author KNEW the false-positive
  direction and scoped for it.
- `git log --all --oneline -S 'a regex sees' -- .claude/rules/mise-tasks-only.md`
  -> ONE commit: e8f7f4ea (#337 squash). The sentence the finding quotes as
  "ALREADY DOCUMENTED" was WRITTEN BY the very change the finding says ignored
  it. Causality inverted, pending confirmation of what pre-#337 text existed.
- docs/direction/2026-08-18-ray-directives.md read IN FULL (required).

## Verified so far (commands + results)

1. **7fc5b5e6 never shipped.** `git merge-base --is-ancestor 7fc5b5e6 main` -> rc=1;
   `git branch -a --contains 7fc5b5e6` -> empty. It is an intra-PR branch commit
   (Aug 17 21:26) squashed into e8f7f4ea (#337, Aug 17 22:43) — 77 minutes apart.
   The regex v1 NEVER reached main; the shlex rewrite happened inside PR #337's own
   review round. "Built twice" describes one PR iterated once under the mandatory
   kb-review gate, pre-merge.
2. **Mechanism confirmed:** v1 `_HAND_GATE = re.compile(` (7fc5b5e6:check_first.py:45);
   shipped `shlex.shlex(command, posix=True, ...)` (e8f7f4ea:check_first.py:140).
3. **"ALREADY DOCUMENTED" is temporally inverted.**
   `git log --all -S 'a regex sees' -- .claude/rules/mise-tasks-only.md` -> ONE
   KB-mainline commit: e8f7f4ea itself. The pre-#337 file (e8f7f4ea^) contains NO
   quoting/tokenising text — grep for `quot|heredoc|regex|tokenis|shlex|false positive`
   hits only line 92 ("its only recorded defects were false positives", about the
   SIBLING repo's guard). v1's own +19 rule lines (7fc5b5e6 diff) also lack the
   sentence. The sentence the finding quotes was WRITTEN BY the #337 fix as its own
   postmortem. The finding's probe — reading HEAD's mise-tasks-only.md — has no time
   axis and could only ever produce "documented".
4. **The prior quoting-class documentation is DOTFILES history.** The -S probe also
   matched d5a2f8ed "(#265) (#270)" (2026-07-14) and 0636afc5 "(#406)" — PR numbers
   impossible for this repo. `git name-rev`: both live under
   `salvage/dotfiles-5701ee4e2c3f/heads/...` — the codex-era salvage refs carry
   dotfiles history into this object store. The sibling's #270 fix even REJECTED
   shlex for its guard ("shlex cannot see heredocs at all") and chose masking — so
   the prior documentation did not prescribe the #337 remedy.
5. **11c783b0** ("give the -- separator its own branch so the hook cannot hang",
   Aug 18 03:26) is on the CURRENT unshipped branch docs-directive-addendum only.
   Per the round's settled triage it is the CONFIRMED CodeRabbit finding, fixed and
   armed — i.e. the round OBEYING Ray's "review all bot reviews" directive, not a
   third build. It changes one tokenizer branch, not the mechanism.
6. v1's own commit message already states "every measured defect in this repo's
   guards has been a false positive and never an evasion" and scoped narrowly for
   it — the author knew the DIRECTION; the specific quoting MECHANISM was documented
   in the sibling repo, not in this repo's rule file.

## Completed verification

7. **Spend cap clause CONFIRMED as a sequence.** #336 squash (37f6a1c5) message:
   "cap cumulative spend at $100... The accumulator charges BEFORE the
   disposition". #339 squash (2b364443) message: "make the cumulative spend cap
   survive a restart... `_Spend` seeded at 0.0 and summed records living in a
   `TemporaryDirectory`... `spend-ledger.json` now lives under the RUN NAMESPACE".
   The finding's own probe `git log --all --oneline -S 'spend-ledger' --
   python/src/kb_setup/` -> 2b364443 (also under spelling `spend_ledger`;
   `ledger`/`Ledger` variants add only corpus-runner history). BUT the
   characterization "built twice" as a circle is weakened by handoff (f): the
   accumulator-in-`on_chunk_done` design WAS Ray's ruled spec verbatim — no spec
   or doc required restart durability — and the reset was found by the DESIGNED
   prove-on-one-chunk-before-58 protocol (Ray's decision, handoff d §3), whose
   purpose was to find exactly such defects before the ~$77 spend.
8. **All 7 handoffs read in full** (b, c, d, e, f, g, 2026-08-18-a) plus the
   2026-08-18 directive in full. Session g ends with `feat-kb-check-guard` at ONE
   commit 7fc5b5e6, "UNPUSHED, no PR, NO REVIEW RECEIPT", NEXT = "Run the cold
   lane, write the receipt, ship". 2026-08-18-a lists
   `review-7fc5b5e6...-cold.md` as "#337 round 1".
9. **Round-1 cold report READ** (112 lines, reviews "HEAD 7fc5b5e6"): findings 1
   and 4 are the two quoted-string false-positive DENYs (`git commit -m "...uv
   run ruff check..."`, `rg "pattern; ty check"`), findings 2/3/5 are BYPASSES
   (multiline, introspection-anywhere, flags-before-subcommand). The quoting
   class was caught by the mandatory pre-ship review of a draft commit — the
   process working, not a shipped defect reworked.
10. Branch `feat-kb-check-guard` no longer exists (deleted at land), consistent
   with 7fc5b5e6 being reachable from no ref.

## Verdict: REFUTED as stated (one clause survives, narrowed)

- "TWO mechanisms built twice" -> at most ONE (the cap) in any shipped sense.
- check_first was built ONCE: draft (7fc5b5e6, never on main) -> mandated cold
  round 1 -> shlex rewrite -> shipped e8f7f4ea, 77 minutes wall clock, one PR.
- "ALREADY DOCUMENTED in mise-tasks-only.md" is temporally inverted: the quoted
  sentence was added BY e8f7f4ea. Prior quoting-class documentation exists only
  in SIBLING dotfiles history (d5a2f8ed, #270, 2026-07-14, via
  salvage/dotfiles-5701ee4e2c3f refs) and it prescribed masking while explicitly
  REJECTING shlex. The finding's probe (reading HEAD's rule file) has no time
  axis — it could only produce "documented".
- "patched a third time (11c783b0)" counts the round's settled CodeRabbit
  compliance fix (CONFIRMED, armed) as a circle; it changes one tokenizer branch,
  not the mechanism, and sits on the unshipped docs-directive-addendum branch.
- The finding's own cited evidence probe (`git log --all --oneline --follow --
  python/src/kb_setup/check_first.py`) does NOT contain 7fc5b5e6 — it returns
  exactly e8f7f4ea + 11c783b0 (armed: the probe does return commits for this
  file). The claim's key commit was imported from handoff prose, not from the
  cited probe.
- Honest residue for the synthesist: the false-positive DIRECTION was documented
  in this repo (line 92 pre-#337) and v1's own commit message proves the author
  knew it and still wrote a raw regex; and the cap did ship two iterations of
  its persistence behavior. Both are narrower than the finding.

## Controls run

- 0-result "7fc5b5e6 absent from --follow log": same command lists 2 other
  commits for the same file, so it can find commits.
- 0-result "no quoting text pre-#337": same grep matched line 92 (false
  positive[s]) in the same file version; -S 'every measured defect' returned 3
  commits proving pickaxe finds older occurrences where they exist.
- Ledger token spellings probed: spend-ledger, spend_ledger, ledger, Ledger.
- merge-base --is-ancestor armed implicitly: rc=1 for 7fc5b5e6 vs main while
  e8f7f4ea IS on main (shown by `git log main --oneline`).

## COVERAGE

- REACHED AND ANALYSED: the 2026-08-18 directive (full); all seven handoffs
  (full); check_first.py history across all refs; commits 7fc5b5e6, e8f7f4ea,
  11c783b0, 37f6a1c5 (#336), 2b364443 (#339), d5a2f8ed, 0636afc5, 3bb49a8c
  (messages/stats/targeted content); pre-#337 and v1 versions of
  mise-tasks-only.md; #337 round-1 cold report (full).
- OPENED, NOT FINISHED: review-3b25a89e (#337 round 2) and review-888df6d0
  (#337 fix round) — located on disk, not read; round 1 + auto-memory sufficed.
- NEVER REACHED: raw .jsonl transcripts (git artifacts + handoffs settled every
  claim; no transcript grep was needed); #338/#339 review reports; the dotfiles
  working tree.
