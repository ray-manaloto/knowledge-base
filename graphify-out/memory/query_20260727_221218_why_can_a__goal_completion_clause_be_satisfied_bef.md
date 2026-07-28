---
type: "query"
date: "2026-07-27T22:12:18.698912+00:00"
question: "Why can a /goal completion clause be satisfied before any work happens, and what fixes it?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why can a /goal completion clause be satisfied before any work happens, and what fixes it?

## Answer

Because setting a goal starts a turn WITH THE CONDITION ITSELF AS THE DIRECTIVE, and the evaluator is sent 'the condition and the conversation so far'. So every literal string spelled out in the condition is already in the transcript at turn 0: a clause reading 'the transcript contains REDACT-ARM+' is arguably true before the work starts, satisfied by the condition quoting itself. Fix: every sentinel must carry a value that did not exist at authoring time — we use ' @ <sha>' (current git rev-parse --short HEAD) plus an explicit EVIDENCE RULE stating the condition's own text is not evidence. Two siblings from the same constraint: the evaluator runs NO tools (so a clause must be settleable by string match on transcript text, never by reading a file), and it sees ONLY the main conversation (so subagent/Workflow output must be restated inline or it is invisible). Source: docs/goals/README.md, .agent/kb/reports/agents/syn-rubric.md T11/T12.

## Outcome

- Signal: useful