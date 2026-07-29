---
type: "query"
date: "2026-07-28T17:21:09.321413+00:00"
question: "How should a range-scan resolve the base commit when ship pushes a raw SHA?"
contributor: "graphify"
outcome: "useful"
---

# Q: How should a range-scan resolve the base commit when ship pushes a raw SHA?

## Answer

git push origin <sha>:refs/heads/<branch> carries the SHA's ENTIRE ancestry, so the scan must cover what the push publishes, not what the branch added. Resolve the merge-base against refs/remotes/origin/<base> AND <base> and reduce with a single 'git merge-base -- <a> <b>' — an ancestor of both by construction. Three traps, each measured in #67: (a) using local <base> alone leaves an unpushed commit on local main BELOW the cutoff and it gets published unscanned; (b) preferring origin blindly NARROWS when local main is behind and the branch forked from the remote tip; (c) 'origin/<base>' is git short-ref precedence and a tag of that name wins, so spell refs/remotes/origin/<base>. And never let a helper map its own subprocess failures onto rc=1 — that is git's 'no such ref' AND 'not an ancestor', so a dead probe reads as a definite answer.

## Outcome

- Signal: useful