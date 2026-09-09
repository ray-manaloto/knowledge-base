---
type: "query"
date: "2026-09-09T17:18:28.105894+00:00"
question: "Why did the first kb-recall-work run take five minutes, and what fixed it?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why did the first kb-recall-work run take five minutes, and what fixed it?

## Answer

The first kb-recall-work run took 4:59 wall: one `gh pr list --head <branch>` per branch (98 in this repo) and one `git rev-list --left-right --count` per branch (516 across three repos). Batching to ONE `gh pr list --state merged --json number,headRefName --limit 3000` per repo and ONE `git for-each-ref --format='%(ahead-behind:<base>)'` per repo (git >= 2.41; this host has 2.50.1) took it to 12 s with identical counts. Lesson: a per-item subprocess in a census is the whole runtime; ask the tool for the batch form first (for-each-ref has ahead-behind, gh pr list has headRefName).


## Outcome

- Signal: useful