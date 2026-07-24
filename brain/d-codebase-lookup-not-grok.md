---
kind: routing-lesson
task_class: research
lane: claude-fallback
verdict: corrected
---

# d-codebase-lookup-not-grok

A codebase where-is-X lookup was sent to [[lane-grok]] and was slower + less accurate than an
in-process reader. CORRECTED: codebase lookups stay in-process, not an external lane.
Sharpens [[task-class-research]].
