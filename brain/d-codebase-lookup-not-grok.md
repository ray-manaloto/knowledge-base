---
kind: routing-lesson
task_class: research
lane: claude-fallback
verdict: corrected
---

# d-codebase-lookup-not-grok

A codebase where-is-X lookup was sent to `lane-grok` (retired) and was slower + less accurate than an
in-process reader. CORRECTED: codebase lookups stay in-process, not an external lane.
Sharpens [[task-class-research]].

**HISTORICAL** — the grok lane was retired 2026-09-24 (the `grok` CLI is not installed; live-web research now routes to [[lane-antigravity]], see [[routing-doctrine]]). Kept as a record, not as evidence for current routing.
