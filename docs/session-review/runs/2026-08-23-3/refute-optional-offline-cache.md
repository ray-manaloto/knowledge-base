# Refutation lane: "dotfiles secrets doc still calls the age sync 'Optional offline cache'"

Lane task: try to REFUTE the finding that
`dotfiles/docs/secrets-doppler-fnox-keychain.md:376` still says "Optional
offline cache" after handoff f measured the sync NOT optional and flagged the
line for correction.

## Probes run (2026-08-18)

1. **Read the doc, lines 350-409** (`/Users/rmanaloto/dev/github/ray-manaloto/dotfiles/docs/secrets-doppler-fnox-keychain.md`).
   Line 376 reads verbatim: `7. Optional offline cache: `fnox sync --global -p age KEY_NAME`.`
   Line 377 warns "**`--global` is not optional**" — but that is about the FLAG
   inside the command, not the step; it was in the committed text the handoff
   author already saw (committed 2026-08-03), so it is not the correction.
2. **grep -n 'Optional' on the doc** → 1 hit, line 376. Control arm:
   `grep -n 'not optional'` → 1 hit, line 377. Both rc=0, probe discriminates.
3. **git log on the doc**: last commit touching it on main is `49ef5bb`
   2026-08-03 15:44:04 -0500 — 14 days BEFORE handoff f. No later commit on main.
4. **git status (dotfiles, branch main)**: doc NOT in modified list. Only
   `doctor.toml` + `.claude/settings.json` modified (the doctor.toml edit is the
   env_true 50→51 change handoff f itself records as uncommitted). So no
   uncommitted correction either.
5. **git log --all --since=2026-08-04 -- <doc>**: one hit, `9c7ff53`
   2026-08-11 on `codex/gh-stack-skill` ("init") — predates handoff f, cannot be
   the correction. Control arm: `git log --all --since=2026-08-04` (no pathspec)
   returns commits, so the probe can find commits in that window.
6. **Newest commit on ANY ref in dotfiles**: 2026-08-15 02:16:39 +0000. The
   entire repo has no commit after handoff f (2026-08-17) at all — a correction
   in a commit is impossible, not merely unfound.
7. **Handoff f item 3** (`.agent/plans/session-2026-08-17-f.md:201-204`), verbatim:
   "**`fnox sync --global --provider age` is NOT optional**, despite the dotfiles
   doc calling it 'Optional offline cache' at step 7. 49 of 51 declarations carry
   a `sync` ciphertext and 48 were reachable; the two without one were the only
   two missing. **That doc line is worth correcting.**"

8. **All seven handoffs read in full** (b, c, d, e, f, g, 2026-08-18-a) plus
   `docs/direction/2026-08-18-ray-directives.md` in full (234 lines): only f
   mentions the doc/fnox sync; no later handoff or directive records a
   correction or a decided-against disposition. Handoff f's ruled NEXT list
   (caps → quick fixes → telemetry) did not include the doc fix — it lives only
   in "Things that will bite", which matches the finding's framing ("flagged",
   not "ruled").
9. **All 9 dotfiles worktrees + stash swept** (2026-08-18): every worktree copy
   of the doc says `Optional offline cache` at line 376 (10/10 copies incl.
   main); `git stash list` is empty (sibling lane's `rev-parse refs/stash`
   rc=128 agrees). No uncommitted correction hides in any worktree.
10. **Sibling lane cross-check**: `refute-dotfiles-uncommitted.md` (same round)
   independently found dotfiles frozen at `6c9c527` (main==origin/main), last
   relevant commits 08-14/08-08, and the doc NOT among modified files — its
   probes AGREE with mine. No finding in the set contradicts this one.

## VERDICT: NOT REFUTED — CONFIRMED on every leg

- Doc line 376 says "Optional offline cache" in the main tree AND all 9
  worktrees; unmodified since `49ef5bb` 2026-08-03; no commit on ANY ref after
  2026-08-15; no stash; doc absent from `git status` modified list. A
  correction is not merely unfound — no place it could exist was left unprobed.
- Handoff f item 3 (lines 201-204) says exactly what the finding cites,
  including "That doc line is worth correcting."
- The original probe could NOT only-produce this answer: the grep discriminates
  ("not optional" → line 377), the git-window probe discriminates (control:
  commits exist in the window), and a corrected doc would have flipped every
  one of these probes.
- ONE immaterial paraphrase garble in the finding: it says "the only two
  missing one were the only two unreachable"; handoff f says "48 were reachable;
  the two without one were the only two missing", and f item 6 separately notes
  AGE_PRIVATE_KEY (which HAS a ciphertext) fails to resolve — so "only two
  unreachable" is not exactly f's arithmetic. The core claim (49/51 measured,
  sync not optional, line flagged, line uncorrected) is unaffected; an issue
  filed from this finding should quote f's sentence, not the paraphrase.
- Known trap for future lanes: grepping the doc for "not optional" hits line
  377 — that is the `--global` FLAG warning, committed 2026-08-03 (before f's
  measurement), coexisting with the step-7 label; it is not a correction and
  not a contradiction.

## GitHub repos touched

_None._ (local repos only: ray-manaloto/dotfiles working tree + git history +
9 worktrees, knowledge-base handoffs + directive + sibling lane reports.)

## COVERAGE

- REACHED AND ANALYSED: the dotfiles doc (lines 350-409 + targeted greps);
  dotfiles git state (log on the doc, status, all-refs since-window log with
  control, worktree list, all 9 worktree doc copies, stash); all 7 named
  handoffs in full; the 2026-08-18 directive in full; contradicted.md item 10
  (the originating lane text); refute-dotfiles-uncommitted.md in full.
- OPENED BUT NOT FINISHED: none.
- NEVER REACHED: the 14 kb transcripts (not needed — the claim is about
  on-disk doc state vs a handoff, both read directly); a live fnox re-probe of
  the 49/51 ciphertext count (would touch secrets; the finding's truth does not
  depend on re-measuring it — the claim is the doc/handoff discrepancy remains,
  not the ciphertext census itself).
