# Refutation attempt — finding [tooling-gap] #16 (PR reply/disposition posting is hand-rolled)

VERDICT: **NOT REFUTED** (refuted=false). Every clause survived a control-armed probe;
one sub-claim (the command COUNT) is a granularity error that does not touch the substance.

## Claim
Posting per-comment replies + a disposition summary to a PR is a second fully hand-rolled
gh-api workflow, not covered by #462 (which only addresses reading).

## Probe 1 — did it happen? (primary artifact: GitHub API, not the transcript)
`gh api repos/ray-manaloto/knowledge-base/pulls/463/comments --paginate --jq '.[] | "\(.id)\t\(.user.login)\tin_reply_to=\(.in_reply_to_id // "-")\t\(.created_at)"'`
→ 8 `sortakool` replies, `in_reply_to` = each of CodeRabbit's 8 inline ids
  (3837608427/47/87/520/536/562/581/597, 2026-08-23T03:23:07Z–03:23:15Z).
`gh api .../issues/463/comments` → `5383984600 sortakool 2026-08-23T03:23:16Z **Bot review disposition at f0659e51…**`
CONTROL: the same query returns bot rows with `in_reply_to=-` (coderabbitai/graphify-labs/repowise),
so the field discriminates reply from top-level.

## Probe 2 — does any task/module back it?
`grep -n "replies\|POST\|comment" python/src/kb_setup/pr.py` → only 2 prose hits (206, 591); 0 for replies/POST.
CONTROL: `grep -c gh python/src/kb_setup/pr.py` = 33, and `gh pr view` is at pr.py:279 — the grep finds gh usage when present.
Repo-wide: `git grep -niE "gh pr comment|gh api -X POST|issues/[0-9$\{][^ ]*/comments|/replies"` over tracked files
→ 4 hits, ALL in `docs/session-review/runs/2026-08-18-1/bot-reviews.md` (historical READ commands). Zero code.
CONTROL: `git grep -c "gh pr checks"` → 5 files (.claude/CLAUDE.md, do-not.md, gh-cli-watch.md, …).
`mise tasks` (75 tasks listed) contains no PR-comment task; the PR tasks are kb-ship / kb-land / kb-review-receipt only.

## Probe 3 — does #462 cover posting?
`gh issue view 462 --json body` — asks 1–5 and both acceptance boxes are reader-side:
"A `kb_setup.pr` READER for bot comments", "kb-land READS and PRINTS every bot's CURRENT verdict",
"the PR-wait monitor keys on updated_at/body hash", "the bot-reviews lane READS the same bots.json".
Nearest counter: Ray's verbatim directive in the body says "…so we actually read all their comments
**and action on them**", and ask 2 says the record makes "we actioned all their comments" checkable —
but "actioned" there means recording what was READ, and no ask/acceptance builds a poster. Clause holds.
No other issue backs it either: #304 ("KB disposition mapping") is an internal certification status
model with zero mention of posting; #464 is the follow-up tickets from this very round.

## Probe 4 — recurrence (is it a gap or a one-off?)
Transcript `48d40647-…jsonl` (2026-08-22) posted 2 hand-rolled `gh api -X POST …/pulls/459/comments/<id>/replies`
in ONE Bash call; `gh api .../pulls/459/comments --jq '[.[]|select(.user.login=="sortakool")]|length'` = 2.
So: PR #459 (2 replies) then PR #463 (8 replies + 1 summary) — two rounds, same hand-rolled shape.

## Correction to the finding's evidence (granularity, not substance)
"cmd #127 defines reply(), called 8x at cmd #128-135 … cmd #147" reads as 10 separate commands.
Those are LINE numbers in bash_cmds.txt (line 140 is inside a heredoc body, so the file preserves
newlines inside a single command). Shell state does not persist between Bash tool calls, so a
function defined in one call cannot be called by the next — the definition + 8 calls were ONE
invocation, corroborated by the 8 replies landing within 9 s (03:23:07→03:23:15Z). Fewer calls,
same gap.

## Extra fact strengthening the finding
The disposition summary used raw `gh api -X POST …/issues/463/comments -F body=@…` where the native
builtin `gh pr comment 463 --body-file` exists and is the form `docs/issue-tracker.md:173` already
uses for issues (`gh issue comment <n> --body`). So the workflow bypasses a tool builtin as well as
lacking a task (`use-tool-builtins.md`).

## Contradiction with other live findings
None. #15 (reading is hand-rolled, #462 open) is the complementary half — both are consistent with
`pr.py` containing neither a reader nor a poster. #17 (kb-session-reflect saw neither chain) is
consistent with `mise tasks` having no owning task to match against.
