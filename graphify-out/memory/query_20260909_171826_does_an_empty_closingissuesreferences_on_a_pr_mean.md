---
type: "query"
date: "2026-09-09T17:18:26.572834+00:00"
question: "Does an empty closingIssuesReferences on a PR mean landing it closes no issue?"
contributor: "graphify"
outcome: "corrected"
correction: "Before claiming \"landing will not close #N\", check BOTH `closingIssuesReferences` (PR body/title) AND the squash body: `git log -1 --format=%B <merge> | grep -E '(close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved)[[:space:]:]+#?N'`. The timeline (`gh api repos/O/R/issues/N/timeline`, event closed, commit_id) is the arbiter after the fact.\n"
---

# Q: Does an empty closingIssuesReferences on a PR mean landing it closes no issue?

## Answer

Reported at /session-resume that landing PR #736 would close neither #735 nor #678 because `gh pr view --json closingIssuesReferences` returned []. Half wrong: #678 closed itself at merge (timeline event `closed` with commit_id = the squash commit daed276f), because the squash body contained "fixed #678" from the memory commit's message. GitHub's closingIssuesReferences shows only body/title links; closing keywords inside the squashed commit body still close issues on merge to the default branch. #735 genuinely needed the hand close.


## Outcome

- Signal: corrected
- Correction: Before claiming "landing will not close #N", check BOTH `closingIssuesReferences` (PR body/title) AND the squash body: `git log -1 --format=%B <merge> | grep -E '(close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved)[[:space:]:]+#?N'`. The timeline (`gh api repos/O/R/issues/N/timeline`, event closed, commit_id) is the arbiter after the fact.
