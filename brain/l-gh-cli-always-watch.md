---
kind: lesson
source: feedback_gh_cli_watch_flag
---

# l-gh-cli-always-watch

Use GitHub CLI's built-in watch modes instead of sleep loops, repeated listings, or grep-based polling.
For pull requests, `gh pr checks <n> --watch` reliably reached terminal pass or failure in the 2026-05-01 validation.
For a run ID, use `gh run watch <id> --exit-status` but cross-check `gh run view <id> --json conclusion`.
This is [[verification-discipline]]: choose the canonical watcher and still verify its known boundary.
