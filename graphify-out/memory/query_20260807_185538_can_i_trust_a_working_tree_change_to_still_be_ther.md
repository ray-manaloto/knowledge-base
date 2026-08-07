---
type: "query"
date: "2026-08-07T18:55:38.955259+00:00"
question: "Can I trust a working-tree change to still be there when I commit?"
contributor: "graphify"
outcome: "corrected"
---

# Q: Can I trust a working-tree change to still be there when I commit?

## Answer

Not in this repo - main is shared with peer sessions. mise run kb-update advanced sources/agent-harness-docs.manifest to e53a7648 (verified: file content plus a git status M line). Later it read 75886c41 again with git status CLEAN and mtime unchanged. Only graph.py 1637 and 1736 call write_commit, both inside update, so no merge/assemble/validate/artifacts path could have done it. Dangerous because the clone was still at the new commit and all 10 extractions came from those bytes, so shipping the old pin breaks invariant 3 while EVERY gate stays green - the revert removes the diff too. Re-verify any working-tree change you care about immediately before committing.

## Outcome

- Signal: corrected