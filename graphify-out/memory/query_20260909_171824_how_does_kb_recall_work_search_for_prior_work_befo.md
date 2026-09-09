---
type: "query"
date: "2026-09-09T17:18:24.732072+00:00"
question: "How does kb-recall-work search for prior work before designing, and what are its bounds?"
contributor: "graphify"
outcome: "useful"
---

# Q: How does kb-recall-work search for prior work before designing, and what are its bounds?

## Answer

`mise run kb-recall-work -- "<topic>"` (`kb_setup.recall_work`, #727, built 2026-09-09) is phase 0 of every saved workflow: seven probes, each reporting EXAMINED beside MATCHED. tracked files + docs/artifacts pages (git grep --all-match, excluding graphify-out/, sources/, raw/), branches (ONE `git for-each-ref --format=%(ahead-behind:<base>)` per repo + ONE `gh pr list --state merged --json number,headRefName` per repo, matched locally), linked worktrees, issues open AND closed (gh api search/issues, examined = every issue in the repo), plans (.planning, .agent/plans, ~/.claude/plans), work-memory (kb-recall in-process). Sibling checkouts ../graphify and ../dotfiles by default.

Bounds, stated in every report: files need EVERY prefix stem (dependency -> dependenc, upgrade -> upgrad); names need ANY; GitHub search is its own word matcher (for "dependency upgrade" it found #636/#638/#314 and not #647/#670/#701, whose titles say bump/pin). Verdicts: merged (ahead 0 or a merged PR for that head), live, unverified (gh could not be asked / --offline), current (checked out anywhere, never deletable).

Exit contract: nothing examined -> rc 127, no report; examined but 0 topic matches -> report still written (the branch census), rc 127 naming every count. Live measurement: 129/10/8/0/20/13/31 for "dependency upgrade" across three repos in 12 s.


## Outcome

- Signal: useful