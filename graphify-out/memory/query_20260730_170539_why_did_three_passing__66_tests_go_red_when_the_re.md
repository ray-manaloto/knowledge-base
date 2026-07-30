---
type: "query"
date: "2026-07-30T17:05:39.260888+00:00"
question: "Why did three passing #66 tests go red when the review gate moved from local main to origin/main?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why did three passing #66 tests go red when the review gate moved from local main to origin/main?

## Answer

The conftest fixture builds its repo with 'git init', which has NO refs/remotes/origin/main, while every real clone does. The tests had been relying on a gap between the fixture and the world; the fail-closed refusal was correct and surfaced it. Fixed with 'git update-ref refs/remotes/origin/main' (no remote, no network). Lesson: when a gate starts reading a ref, ask whether the FIXTURE has it — a git-init repo is not a clone.

## Outcome

- Signal: useful