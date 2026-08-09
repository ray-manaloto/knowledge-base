---
type: "query"
date: "2026-08-08T23:37:14.927830+00:00"
question: "What goes wrong when a mutating review lane and the orchestrator share a working tree?"
contributor: "graphify"
outcome: "useful"
---

# Q: What goes wrong when a mutating review lane and the orchestrator share a working tree?

## Answer

A mutating review lane and the orchestrator SHARE ONE WORKING TREE, with no lock and no signal, and the failure is destructive rather than merely confusing. During PR 258's review the round-2 lane restored python/src/kb_setup/check.py over an edit of mine that was in flight, leaving tests/test_check.py referencing a function no longer in the module -- a half-state that would have shipped tests calling into nothing if I had trusted the tree instead of reading git status before committing. The existing note was "never edit while a mutating lane runs". The half that actually bit is sharper: A CLEAN TREE MEANS THE LANE IS BETWEEN MUTATIONS, NOT FINISHED. I checked git status, saw no code changes, concluded the lane had died, and edited. It had not. The same lane also produced NO REPORT AT ALL despite three explicit instructions to write incrementally, never answered a liveness check, and had to be stopped with TaskStop -- while round 1, same lane type and same brief shape, wrote incrementally and produced a strong cited report. So lane death here is SILENT, and pgrep is useless for detecting it because pgrep codex matches the ChatGPT app. Worse, kb-review's receipt records WHICH LANES WERE NAMED, not which produced anything, so a lane that dies having written nothing is indistinguishable in the receipt from one that ran and found nothing; the gap was caught only because I noticed, not by any gate. Filed as issue 259 with four possible directions -- worktree isolation, a liveness deadline that records timeout explicitly, a --died lane receipt field, or the cheap one where the orchestrator writes the report stub at dispatch so an empty stub is unambiguous evidence.

## Outcome

- Signal: useful