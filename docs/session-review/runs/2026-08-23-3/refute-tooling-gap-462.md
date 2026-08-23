# Refutation attempt — [tooling-gap] PR bot-comment reading has no task/module (#462 OPEN)

## Probe 1 — graph first
`mise run kb-query -- "read PR bot comments reviews gh api"` -> TRUNCATED, 57 of 255 nodes,
every node from third-party corpora (ruff, codex-rs, yarn cjs). No orientation value.
(Independently corroborates round finding #7.)

## Probe 2 — CONTROL ARM for the grep shape
Unquoted `--include=*.py` was eaten by zsh: `(eval):3: no matches found: --include=*.py`
=> a FALSE ZERO. Re-ran quoted.
Control (token known present): `grep -rn "_ADVISORY_CHECKS" python/ --include='*.py'`
-> 4 hits, python/src/kb_setup/pr.py:94,169,216,217. Probe discriminates.

## Probe 3 — reader tokens across ALL of python/ (quoted)
`grep -rniE "bot_comments|bots\.json|pulls/[^ ]*comments|issues/[^ ]*comments|listReviewComments|review_comments|coderabbit|repowise" python/ --include='*.py'`
-> 21 hits, ALL prose in docstrings/comments naming CodeRabbit as an advisory
   CHECK-RUN name. `pr.py:94 _ADVISORY_CHECKS = frozenset({"CodeRabbit", "Repowise / code health"})`
   is about `gh pr checks` rows, not comments.
-> ZERO hits for bot_comments / bots.json / any comments-API path.

## Probe 4 — widening every bound in the ORIGINAL probe
The finding's own grep was bounded to ONE FILE (`python/src/kb_setup/pr.py`). Widened:
- `git grep -niE "issues/[^ ]*/comments|pulls/[^ ]*/comments|pulls/[^ ]*/reviews|bot_comments|bots\.json"` over ALL tracked files
  -> 17 hits, every one PROSE: `.claude/workflows/session-review.js:496` (an INSTRUCTION to
  run the chain by hand), `docs/direction/2026-08-19-ray-directives.md:161-163`,
  `docs/session-review/runs/2026-08-18-1/bot-reviews.md` (transcribed commands),
  `graphify-out/memory/query_20260819_*.md`. Zero executable readers.
  Control on the same shape: `git grep -c "kb-review-receipt" -- mise.toml` -> 2.
- ALL 78 mise task names enumerated (`grep -oE '^\[tasks\.[a-z0-9_.-]+\]' mise.toml`): no
  kb-bots / kb-pr-* / anything comment-related. `grep -nE "gh api|bot" mise.toml` -> 0.
- ALL 12 `"gh",` subprocess call sites in python/: pr.py x6 (`pr checks`, `pr view --json
  headRefOid`, `pr view --json number,state`, `pr create`, `pr merge`), currency/issues.py,
  currency/upstream.py x2, handoff_reconcile.py, session_state.py, source_groups.py.
  NONE reads an issue comment, review body, or inline comment.
- `tests/`: `bot_comments|bots.json` -> 0 hits (control: `tests/test_pr.py` "advisory" -> 17).
- `gh extension list` -> `gh copilot`, `gh stack` only (control: `gh alias list` -> `co`).
- Enabled plugin `pr-review-toolkit`: its `comment-analyzer` agent is about CODE comments
  ("protect codebases from comment rot"), not PR bot comments — token-spelling trap avoided.
  Only `gh` line in the whole plugin is `commands/review-pr.md:32: gh pr view`.

## Probe 5 — issue state, with a control arm
`gh issue view 462 --json ...` -> state=OPEN, labels=[needs-triage,directive], ncomments=0.
CONTROL: `gh issue view 441` -> state=CLOSED. The probe discriminates.
Body item 1 verbatim: "**A `kb_setup.pr` reader for bot comments** … `bot_comments(pr)` …
Persist the last-seen map per PR under `.agent/kb/pr/<n>/bots.json`". Exactly as cited.
`ls .agent/kb/pr` -> No such file or directory (nothing built it).

## Probe 6 — did the session re-do the read by hand? (verbatim)
scratchpad `.../096161cc-.../bash_cmds.txt`:
 - line 25: `gh pr checks 463` + `gh api …/issues/463/comments --jq '… created=\(.created_at) updated=\(.updated_at) …'` + `gh api …/pulls/463/reviews` + `gh api …/pulls/463/comments`
 - line 26: same 3 endpoints again, `{ … } > .agent/kb/reports/pr-463-bots-read-20260823T0310Z.md`
 - line 127: `reply() { … gh api -X POST "$R/$1/replies" … }`  (finding #16's sibling chain)
 - line 147: `gh api -X POST …/issues/463/comments -F body=@…`
Report file exists on disk: `.agent/kb/reports/pr-463-bots-read-20260823T0310Z.md`.

## Verdict
NOT REFUTED. Every widening of every bound reproduces the zero, each with a control arm.
Extra corroboration the finding does not claim: `session-review.js:496` prescribes only
`pulls/N/reviews` and `pulls/N/comments` — it omits `issues/N/comments`, which is where
Repowise/CodeRabbit post, the exact miss 2026-08-19 already recorded.

Contradiction check vs the round's other findings: NONE. #16 (hand-rolled reply POSTing),
#17 (kb-session-reflect missed both chains) and #19-#22 (bot findings undispositioned)
all presuppose this finding and corroborate it; no probe in the set disagrees.

## GitHub repos touched
- [ray-manaloto/knowledge-base](https://github.com/ray-manaloto/knowledge-base) — issues #462/#441, PR #463 bot comments
