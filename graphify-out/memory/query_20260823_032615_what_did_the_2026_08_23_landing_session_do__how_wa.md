---
type: "query"
date: "2026-08-23T03:26:15.536106+00:00"
question: "What did the 2026-08-23 landing session do: how was PR #463 landed with an unreceipted commit on top, and what did reading the bots by body find?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did the 2026-08-23 landing session do: how was PR #463 landed with an unreceipted commit on top, and what did reading the bots by body find?

## Answer

# What the 2026-08-23 landing session (Fable 5) did, and what it found

PR #463 (`corpus-gate-bundle-rebased`, 19 commits) LANDED at `272d14bc3785` (squash pinned to `f0659e511fa08a6474c5986b1b3055590111a81b`); `main` local = remote. The two pre-rebase backup branches were deleted afterwards, as the handoff scheduled.

## The disagreement `/kb-resume` found, and what it cost

The handoff recorded HEAD `85201adb1a28` with a receipt and gates at that SHA; the branch HEAD was `d85f2835499069eaedeb18783025ccfad5da072e` — Ray's one-line `.claude/CLAUDE.md` change (`fable-orchestrator: codex effort = xhigh`), local only, unreceipted. `kb-handoff-check` flagged it (1 broken). Ray's call: "quick git push and land since that change shouldn't affect actual code". A bare push + `kb-land` would have been refused (`.claude/CLAUDE.md` is not in `review.EXEMPT_PATHS`; the `cold` lane cannot be skipped by policy), so the honest quick path was the kb-review §4 fix-round shape this same branch had already used for its gitignore-only commit: a report at the new SHA naming both commits, saying no lane re-ran over a 1-line config delta, with lint-docs/lint re-run (rc 0) as verification; receipt; `kb-ship` (6/6 gates, pushed to #463).

## Reading the bots BY BODY (#462) found 2 real items in 16 inline comments

CodeRabbit's inline review (8 comments at `9b9131e1`) had never been read — the previous session's handoff listed it as step 1 of landing. Verified each against the tree: 2 real and trivial (the doc's public-seam line omitted `record`; the `verify_plan` exception test covered 3 of the 7 classes the clause catches) → fixed in `f0659e51…` with its own fix-round receipt, gates 6/6, re-pushed; 2 real but deferred with a reason into **#464** (the dup-group ORDER arm is unreached because one reason covers three conditions and the fixture has one group; the stale "now equals `_CURRENT_CLAUDE_VERSION`" comment at `graphify_semantic_slice.py:471` — digested into every recorded plan, so it rides the 2.1.241 resync edit that re-records anyway); 4 refuted (S607 is ignored repo-wide with its reason in `pyproject.toml:121-124`; the issue-301 prototype launcher's `main()` is never executed — its test `runpy`s the file and calls `parse_fragment` only — and it is frozen evidence; two `docs/research/reports/` items are verbatim). graphify-labs' five "Escalate · high" findings were the PEP 758 / Python 3.14 `except A, B:` false positive `session_select.py:132-137` already records; CodeRabbit was rate-limited on both new pushes. Every disposition was replied inline and summarised in one PR comment.

## Lessons

- **A commit made after the handoff is invisible to the handoff and to the receipt** — and `/kb-resume`'s repo cross-check is what caught it. The remedy that kept Ray's "quick" honest was the existing fix-round template, not a new exemption.
- **A conventional-commit type of `docs+test` is invalid** (`check_conventional_commit`); pick one.
- **Bots' inline comments are NOT in the checks table** — `gh pr checks` showed CodeRabbit `pass` while 8 unread inline findings sat on the PR; the disposition comment now records what was read at which head.
- Ray's standing call, new this session: **a landing or resync session ends with `/clear-prep` run WITH the session-review workflow**, not on `kb-land`; the next session = the claude 2.1.240→2.1.241 resync ONLY, then the same again.


## Outcome

- Signal: useful